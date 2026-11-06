"""Cached, bounded PDF export with no network or arbitrary filesystem resources."""

import fcntl
import hashlib
import json
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
PDF_PRESENTATION_VERSION = 13


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


def pdf_content_boxes(page):
    from weasyprint.formatting_structure.boxes import MarginBox

    for child in page._page_box.children:
        if not isinstance(child, MarginBox):
            yield from child.descendants()


def defer_pdf_figures(markup, document):
    """Fill figure-induced gaps within their chapter, preserving prose order."""
    from bs4 import BeautifulSoup, Tag
    from weasyprint.formatting_structure.boxes import BlockBox, TextBox

    soup = BeautifulSoup(markup, "html.parser")
    positions = {}
    for page_number, page in enumerate(document.pages):
        for box in pdf_content_boxes(page):
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
        current = document.pages[page_number]
        heading_elements = {
            element
            for box in pdf_content_boxes(current)
            if box.element_tag in {"h1", "h2", "h3", "h4", "h5", "h6"} and box.element is not None
            for element in box.element.iter()
        }
        if any(
            isinstance(box, TextBox)
            and box.position_y < locations[0][2]
            and box.element not in heading_elements
            and box.text.strip()
            for box in pdf_content_boxes(current)
        ):
            continue
        previous_page = document.pages[page_number - 1]
        previous = previous_page._page_box
        bottom = max(
            (
                box.position_y + box.height
                for box in pdf_content_boxes(previous_page)
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


def running_sections(markup):
    from bs4 import BeautifulSoup

    from library.services.book_views import section_title

    soup = BeautifulSoup(markup, "html.parser")
    for section in soup.select(".reader-content section"):
        title = section_title(section)
        if title is not None:
            title["data-pdf-section"] = title.get("data-reading-marker", "") + title.get_text(
                " ", strip=True,
            )
        else:
            section["data-pdf-section"] = section.get("id", "Untitled section")
    for heading in soup.select(".reader-content h2, .reader-content h3"):
        if heading.find_parent("section") is None:
            heading["data-pdf-section"] = heading.get("data-reading-marker", "") + heading.get_text(
                " ", strip=True,
            )
    return str(soup)


def render_pdf(version, destination, reading_style=None, theme=""):
    from django.template.loader import render_to_string
    from weasyprint import CSS, HTML
    from weasyprint.text.fonts import FontConfiguration

    from library.profile import source_name
    from library.services.book_views import publication_view
    from library.services.document_metadata import metadata_context, with_metadata_page
    from library.services.reading_styles import DEFAULTS, FONT_FILES, style_css, validate_style
    from library.services.storage import read_blob
    from library.themes import profile_for_theme
    from library.views import contents_tree, toc_tree

    reading_style = validate_style(DEFAULTS if reading_style is None else reading_style)
    assets = {
        f"https://reading-hub.invalid/assets/{asset.blob_id}/": asset.blob
        for asset in version.assets.select_related("blob")
    }
    failures = []

    def fetch(url, *args, **kwargs):
        prefix = "https://reading-hub.invalid/static/library/fonts/"
        if url.startswith(prefix) and url.removeprefix(prefix) in FONT_FILES:
            path = STYLES / "fonts" / url.removeprefix(prefix)
            try:
                data = path.read_bytes()
            except OSError as exc:
                failures.append(f"Bundled PDF font unavailable: {path.name}")
                raise ValueError(failures[-1]) from exc
            return {
                "string": data, "mime_type": "font/otf" if path.suffix == ".otf" else "font/ttf",
            }
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

    generated_book = bool(getattr(version, "document_publication", None))
    projection = publication_view(version.html, version.structure["toc"]) if generated_book else {
        "content_html": version.html, "entries": version.structure.get("toc", []),
    }
    markup = render_to_string(
        "library/pdf.html",
        {
            "version": version,
            "display_author": version.metadata.get("author", "").strip()
            or source_name(version.document.url),
            **metadata_context(version.metadata, version.title, version.metadata.get(
                "author", "").strip() or source_name(version.document.url),
                version.structure.get("book"), version.document.url),
            "content_html": projection["content_html"],
            "toc": toc_tree(with_metadata_page(
                projection["entries"], version.metadata, version.structure.get("book"))),
            "generated_book": generated_book,
            "contents_toc": contents_tree(projection["entries"]),
        },
    )
    # WeasyPrint logs resource failures and continues; never publish a partial success.
    errors = RenderErrors()
    renderer_logger = logging.getLogger("weasyprint")
    renderer_logger.addHandler(errors)
    try:
        font_config = FontConfiguration()
        stylesheets = [
            CSS(string=version.stylesheet, url_fetcher=fetch),
            CSS(filename=str(STYLES / "print.css"), url_fetcher=fetch),
            CSS(string=style_css(
                reading_style, font_base="https://reading-hub.invalid/static/library/fonts/",
                profile=profile_for_theme(theme),
            ), url_fetcher=fetch, font_config=font_config),
        ]
        markup = mark_pdf_flow(running_sections(markup))
        # Moves are forward-only; remeasure after each layout rather than treating
        # an earlier move as proof that later image gaps have been filled.
        for attempt in range(32):
            document = HTML(
                string=markup, base_url="https://reading-hub.invalid/", url_fetcher=fetch
            ).render(stylesheets=stylesheets, font_config=font_config)
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


def cached_pdf(version, reading_style=None, theme=""):
    from library.services.reading_styles import DEFAULTS, style_digest, validate_style
    from library.themes import profile_for_theme

    reading_style = validate_style(DEFAULTS if reading_style is None else reading_style)
    profile = profile_for_theme(theme)
    palette = ""
    if reading_style["palette"] == "theme":
        palette = "-" + hashlib.sha256(
            (profile.reading_paper + profile.reading_ink).encode("ascii")
        ).hexdigest()[:16]
    directory = settings.DATA_DIR / "pdf"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    destination = directory / (
        f"{version.pk}-{version.identity}-{APP_VERSION}-{style_digest(reading_style)}"
        f"{palette}-p{PDF_PRESENTATION_VERSION}.pdf"
    )
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
                    json.dumps(reading_style, sort_keys=True),
                    name,
                ],
                cwd=settings.BASE_DIR,
                env={
                    **os.environ,
                    "READING_HUB_DATA": str(settings.DATA_DIR.resolve()),
                    "READING_HUB_PROFILE": settings.READING_HUB_PROFILE,
                    "READING_HUB_PDF_THEME": theme,
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
    from library.services.reading_styles import validate_style

    render_pdf(
        Rendition.objects.select_related("document").get(pk=int(sys.argv[1])), sys.argv[3],
        validate_style(json.loads(sys.argv[2])),
        theme=os.environ.get("READING_HUB_PDF_THEME", ""),
    )


if __name__ == "__main__":
    main()
