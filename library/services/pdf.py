"""Cached, bounded PDF export with no network or arbitrary filesystem resources."""

import fcntl
import logging
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from django.conf import settings

from library.versions import APP_VERSION

logger = logging.getLogger("library")
STYLES = Path(__file__).resolve().parent.parent / "static" / "library"


def split_pdf_paragraph(paragraph, fraction):
    """Split prose without losing inline markup, links, or unique anchor IDs."""
    import copy

    from bs4 import NavigableString, Tag

    text = paragraph.get_text()
    target = int(len(text) * fraction)
    boundary = text.rfind(" ", 0, target)
    if boundary <= 0 or boundary >= len(text) - 1:
        return None

    def split(node, remaining):
        if isinstance(node, NavigableString):
            value = str(node)
            return NavigableString(value[:remaining]), NavigableString(value[remaining:])
        left, right = copy.copy(node), copy.copy(node)
        left.clear()
        right.clear()
        right.attrs.pop("id", None)
        right.attrs.pop("name", None)
        for child in node.children:
            length = len(child.get_text() if isinstance(child, Tag) else str(child))
            if remaining >= length:
                left.append(copy.copy(child))
            elif remaining <= 0:
                right.append(copy.copy(child))
            else:
                before, after = split(child, remaining)
                left.append(before)
                right.append(after)
            remaining -= length
        return left, right

    before, after = split(paragraph, boundary)
    before["style"] = before.get("style", "") + ";margin-bottom:0"
    after["style"] = after.get("style", "") + ";margin-top:0;text-indent:0"
    paragraph.replace_with(after)
    after.insert_before(before)
    return before


def defer_pdf_figures(markup, document):
    """Fill figure-induced gaps within their chapter, preserving prose order."""
    from bs4 import BeautifulSoup, Tag
    from weasyprint.formatting_structure.boxes import BlockBox, TextBox

    soup = BeautifulSoup(markup, "html.parser")
    positions = {}
    for page_number, page in enumerate(document.pages):
        for box in page._page_box.descendants():
            if isinstance(box, BlockBox) and box.element is not None:
                key = box.element.get("data-pdf-flow")
                if key:
                    positions.setdefault(key, []).append((page_number, box.height, box.position_y))
    changed = False
    for figure in soup.select("figure[data-pdf-flow]"):
        if not figure.select("img") or "quotation" in figure.get("class", []):
            continue
        key = figure["data-pdf-flow"]
        locations = positions.get(key, [])
        if not locations:
            continue
        page_number = locations[0][0]
        if page_number == 0:
            continue
        current = document.pages[page_number]._page_box
        heading_elements = {
            element
            for box in current.descendants()
            if box.element_tag in {"h1", "h2", "h3", "h4", "h5", "h6"} and box.element is not None
            for element in box.element.iter()
        }
        if any(
            isinstance(box, TextBox)
            and box.position_y < locations[0][2]
            and box.element not in heading_elements
            and box.text.strip()
            for box in current.descendants()
        ):
            continue
        previous = document.pages[page_number - 1]._page_box
        bottom = max(
            (
                box.position_y + box.height
                for box in previous.descendants()
                if isinstance(box, TextBox) or box.element_tag == "img"
            ),
            default=previous.content_box_y(),
        )
        gap = previous.content_box_y() + previous.height - bottom
        if gap < previous.height * 0.18:
            continue
        figures = [figure]
        moved_height = 0
        following = []
        for sibling in figure.next_siblings:
            if not isinstance(sibling, Tag):
                if str(sibling).strip():
                    break
                continue
            if sibling.name == "figure" and sibling.select("img"):
                if "quotation" in sibling.get("class", []):
                    break
                figures.append(sibling)
                continue
            if (
                sibling.name not in {"p", "blockquote", "ul", "ol", "h2", "h3", "h4", "h5", "h6"}
                or sibling.select("img,figure")
                or "document-subtitle" in sibling.get("class", [])
            ):
                break
            if sibling.get_text(strip=True):
                height = sum(
                    height for _, height, _ in positions.get(sibling.get("data-pdf-flow"), [])
                )
                remaining = gap - moved_height
                if sibling.name == "p" and height > remaining > 80:
                    prefix = split_pdf_paragraph(sibling, remaining / height * 0.85)
                    if prefix is not None:
                        following.append(prefix)
                        break
                following.append(sibling)
                moved_height += height
            if following and sibling.name not in {"h2", "h3", "h4", "h5", "h6"}:
                break
        while following and following[-1].name in {"h2", "h3", "h4", "h5", "h6"}:
            following.pop()
        if following:
            cursor = following[-1]
            for deferred in figures:
                cursor.insert_after(deferred.extract())
                cursor = deferred
            changed = True
    return str(soup) if changed else None


def mark_pdf_flow(markup):
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(markup, "html.parser")
    for paragraph in soup.select(".reader-content p"):
        if not paragraph.get_text(strip=True) and not paragraph.select("img,svg,video,hr"):
            # Empty source paragraphs interrupt the heading's keep-with-next chain.
            if paragraph.get("id"):
                anchor = soup.new_tag("a", id=paragraph["id"])
                paragraph.insert_before(anchor)
            paragraph.unwrap()
    for index, node in enumerate(
        soup.select(
            ".reader-content figure, .reader-content p, .reader-content blockquote, "
            ".reader-content ul, .reader-content ol, .reader-content h2, "
            ".reader-content h3, .reader-content h4, .reader-content h5, .reader-content h6"
        )
    ):
        node["data-pdf-flow"] = str(index)
    return str(soup)


class PDFExportError(Exception):
    pass


def pdf_filename(title):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', "-", title)
    name = " ".join(name.split()).strip(" .")[:150].rstrip(" .") or "Untitled"
    if re.fullmatch(r"(?i:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", name):
        name = "_" + name
    return name + ".pdf"


class RenderErrors(logging.Handler):
    def __init__(self):
        super().__init__(logging.ERROR)
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def render_pdf(version, destination):
    from django.template.loader import render_to_string
    from weasyprint import CSS, HTML

    from library.profile import source_name
    from library.services.document_metadata import metadata_rows
    from library.services.storage import read_blob

    assets = {
        f"https://reading-hub.invalid/assets/{asset.blob_id}/": asset.blob
        for asset in version.assets.select_related("blob")
    }
    failures = []

    def fetch(url, *args, **kwargs):
        blob = assets.get(url)
        if blob is None:
            failures.append(f"PDF resource is not an image belonging to this version: {url}")
            raise ValueError(failures[-1])
        try:
            data = read_blob(blob.pk)
        except OSError as exc:
            failures.append(f"Cached PDF image unavailable: {exc}")
            raise
        return {"string": data, "mime_type": blob.media_type}

    markup = render_to_string(
        "library/pdf.html",
        {
            "version": version,
            "display_author": version.metadata.get("author", "").strip()
            or source_name(version.document.url),
            "metadata_rows": metadata_rows(version.metadata),
        },
    )
    # WeasyPrint logs resource failures and continues; never publish a partial success.
    errors = RenderErrors()
    renderer_logger = logging.getLogger("weasyprint")
    renderer_logger.addHandler(errors)
    try:
        stylesheets = [
            CSS(string=version.stylesheet, url_fetcher=fetch),
            CSS(filename=str(STYLES / "print.css"), url_fetcher=fetch),
        ]
        markup = mark_pdf_flow(markup)
        # Moves are forward-only; remeasure after each layout rather than treating
        # an earlier move as proof that later image gaps have been filled.
        for attempt in range(32):
            document = HTML(
                string=markup, base_url="https://reading-hub.invalid/", url_fetcher=fetch
            ).render(stylesheets=stylesheets)
            if failures or errors.messages:
                raise PDFExportError("; ".join(failures + errors.messages))
            if attempt == 31:
                break
            updated = defer_pdf_figures(markup, document)
            if updated is None:
                break
            markup = mark_pdf_flow(updated)
        if failures or errors.messages:
            raise PDFExportError("; ".join(failures + errors.messages))
        document.write_pdf(destination)
        if failures or errors.messages:
            raise PDFExportError("; ".join(failures + errors.messages))
    finally:
        renderer_logger.removeHandler(errors)
        errors.close()


def cached_pdf(version):
    directory = settings.DATA_DIR / "pdf"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    destination = directory / f"{version.pk}-{version.identity}-{APP_VERSION}.pdf"
    if destination.exists():
        return destination
    with (directory / "render.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise PDFExportError("Another PDF is being prepared. Please retry shortly.") from exc
        if destination.exists():
            return destination
        name = None
        try:
            with tempfile.NamedTemporaryFile(dir=directory, suffix=".pdf", delete=False) as file:
                name = file.name
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "library.services.pdf",
                    str(version.pk),
                    name,
                ],
                cwd=settings.BASE_DIR,
                env={
                    **os.environ,
                    "READING_HUB_DATA": str(settings.DATA_DIR.resolve()),
                    "READING_HUB_PROFILE": settings.READING_HUB_PROFILE,
                    "DJANGO_SETTINGS_MODULE": "config.settings",
                },
                capture_output=True,
                timeout=120,
                check=False,
            )
            if result.returncode != 0:
                logger.error(
                    "PDF export %s failed: %s",
                    version.pk,
                    result.stderr.decode(errors="replace")[-8000:],
                )
                raise PDFExportError(
                    "PDF generation failed. Check the application log; "
                    "the cached reader is unchanged."
                )
            with open(name, "rb") as file:
                if file.read(5) != b"%PDF-":
                    raise PDFExportError("PDF generation returned an invalid file.")
            os.replace(name, destination)
        except subprocess.TimeoutExpired as exc:
            raise PDFExportError("PDF generation exceeded its 120-second limit.") from exc
        finally:
            if name and os.path.exists(name):
                os.unlink(name)
    return destination


def main():
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (1024 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (100 * 1024 * 1024,) * 2)
    import django

    django.setup()
    from library.models import Rendition

    render_pdf(Rendition.objects.select_related("document").get(pk=int(sys.argv[1])), sys.argv[2])


if __name__ == "__main__":
    main()
