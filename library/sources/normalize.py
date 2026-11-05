import hashlib
import re
from urllib.parse import unquote, urldefrag, urljoin

import nh3
from bs4 import BeautifulSoup

from library.services.errors import ImportFailure
from library.services.fetch import canonical_url
from library.services.presentation import inline_alignment
from library.sources.adapters import image_url
from library.sources.capitalization import author_names, normalize_heading

TAGS = {
    "section",
    "div",
    "p",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "blockquote",
    "ul",
    "ol",
    "li",
    "table",
    "thead",
    "tbody",
    "tfoot",
    "tr",
    "th",
    "td",
    "caption",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "s",
    "small",
    "sup",
    "sub",
    "a",
    "span",
    "br",
    "hr",
    "figure",
    "figcaption",
    "img",
    "pre",
    "code",
    "dl",
    "dt",
    "dd",
    "abbr",
    "cite",
}


def make_id(prefix, value):
    return prefix + "-" + hashlib.sha256(value.encode()).hexdigest()[:16]


def heading_toc(body):
    toc = []
    used_ids = {node["id"] for node in body.select("[id]")}
    for index, heading in enumerate(body.select("h2, h3, h4, h5, h6"), 1):
        if "id" not in heading.attrs:
            heading["id"] = f"heading-{index}"
            while heading["id"] in used_ids:
                heading["id"] += "-h"
            used_ids.add(heading["id"])
        title = heading.get_text(" ", strip=True)
        if heading.__dict__.get("_reviewed_numbered_title"):
            title = re.sub(r"^([0-9IVXLCDMA-Za-z]+)\s+([.)])", r"\1\2", title)
        toc.append({"id": heading["id"], "level": int(heading.name[1]), "title": title})
    return toc


def normalize_quotations(body, soup):
    for paragraph in list(body.find_all("p")):
        if paragraph.find_parent(["blockquote", "figure", "figcaption", "li", "td", "th"]):
            continue
        text = paragraph.get_text("", strip=False).strip()
        if len(text) < 40 or (text[0], text[-1]) not in {
            ("\u201c", "\u201d"),
            ("\u00ab", "\u00bb"),
            ("\u201e", "\u201c"),
            ('"', '"'),
        }:
            continue
        between = []
        attribution = None
        for sibling in paragraph.next_siblings:
            if isinstance(sibling, str) and not sibling.strip():
                between.append(sibling)
                continue
            attribution = sibling
            break
        if getattr(attribution, "name", None) != "p":
            continue
        credit = attribution.get_text(" ", strip=True)
        match = re.match(r"^[-\u2013\u2014]\s+(\S)", credit)
        if not match or not match[1].isupper() or len(credit) > 500:
            continue
        figure = soup.new_tag("figure", attrs={"class": "quotation"})
        paragraph.insert_before(figure)
        blockquote = soup.new_tag("blockquote")
        figure.append(blockquote)
        blockquote.append(paragraph.extract())
        for whitespace in between:
            figure.append(whitespace.extract())
        caption = soup.new_tag("figcaption")
        figure.append(caption)
        caption.append(attribution.extract())


def strip_outer_quotes(node):
    nodes = [text for text in node.find_all(string=True) if text.strip()]
    if not nodes:
        return
    first, last = nodes[0], nodes[-1]
    opening, closing = str(first).lstrip()[0], str(last).rstrip()[-1]
    if (opening, closing) not in {
        ("\u201c", "\u201d"),
        ("\u00ab", "\u00bb"),
        ("\u201e", "\u201c"),
        ('"', '"'),
    }:
        return
    if first is last:
        text = str(first)
        start, end = len(text) - len(text.lstrip()), len(text.rstrip()) - 1
        first.replace_with(text[:start] + text[start + 1 : end] + text[end + 1 :])
    else:
        text = str(first)
        start = len(text) - len(text.lstrip())
        first.replace_with(text[:start] + text[start + 1 :])
        text = str(last)
        end = len(text.rstrip()) - 1
        last.replace_with(text[:end] + text[end + 1 :])


def discard_empty_containers(body, *, review=False):
    preserved = {"br", "hr", "img", "table", "thead", "tbody", "tfoot", "tr", "td", "th"}
    for node in reversed(body.find_all(True)):
        if (
            node.name in preserved or node.has_attr("id")
            or (review and node.has_attr("data-excerpt-block"))
        ):
            continue
        if not node.get_text(strip=True) and all(
            child.name == "br" for child in node.find_all(True, recursive=False)
        ):
            node.decompose()


def normalize(pages, source, assets, *, review=False):
    result = BeautifulSoup("", "html.parser")
    target_map = {}
    page_roots = {}
    sections = []
    group = None
    names = author_names(source.metadata.get("author", ""))
    for index, (part, body) in enumerate(pages):
        numbered_title = next(
            (
                node for node in body.find_all(True)
                if node.__dict__.get("_reviewed_numbered_title")
                and node.__dict__["_reviewed_numbered_title"].casefold()
                == part.title.casefold()
            ),
            None,
        )
        prefix = f"c{index + 1}"
        url = canonical_url(part.url)
        root = result.new_tag("section", id=prefix)
        if not part.section:
            page_roots.setdefault(url, prefix)
        if source.book:
            if part.group and part.group != group:
                group = part.group
                group_heading = result.new_tag("h2", id=f"part-{index + 1}")
                group_heading.string = group
                result.append(group_heading)
            if not part.use_source_headings and numbered_title is None:
                heading = result.new_tag("h3" if part.group else "h2", id=prefix + "-title")
                heading.string = part.title
                root.append(heading)
        # Build a map before stripping source attributes. Duplicate IDs are made unique,
        # while links resolve to the first occurrence, matching browser behavior.
        seen = set()
        for number, node in enumerate(body.find_all(True)):
            old_ids = [node.get("id")]
            if node.name == "a":
                old_ids.append(node.get("name"))
            old = next((value for value in old_ids if value), None)
            new_id = None
            if old:
                new_id = make_id(prefix, str(old))
                for value in old_ids:
                    if value:
                        target_map.setdefault((url, unquote(str(value))), new_id)
                if new_id in seen:
                    new_id += f"-{number}"
                seen.add(new_id)
            alignment = node.__dict__.pop("_reviewed_alignment", inline_alignment(node))
            presentation = node.__dict__.pop("_reviewed_presentation", [])
            kept = {}
            for attr in (
                "href",
                "src",
                "alt",
                "title",
                "colspan",
                "rowspan",
                "data-src",
                "data-lazy-src",
            ):
                if attr in node.attrs:
                    kept[attr] = node[attr]
            node.attrs = kept
            if node.__dict__.pop("_reviewed_subtitle", False):
                node["class"] = "document-subtitle"
            if node.__dict__.pop("_reviewed_media_credit", False):
                node["class"] = "media-credit"
            if node.__dict__.pop("_reviewed_note_backlink", False):
                node["class"] = "note-backlink"
                node["aria-label"] = "Back to reference"
            classes = node.get("class", [])
            classes = classes.split() if isinstance(classes, str) else list(classes)
            if alignment:
                classes.append(f"text-align-{alignment}")
            classes.extend(presentation)
            if classes:
                node["class"] = classes
            if new_id:
                node["id"] = new_id
            if node.name == "a":
                fragment = urldefrag(str(node.get("href", "")))[1]
                if node.__dict__.pop(
                    "_reviewed_note_reference",
                    bool(re.search(r"(ftn|note|_edn)", fragment, re.I))
                    and not re.search(r"ref", fragment, re.I),
                ):
                    node["data-note-reference"] = "true"
            if re.fullmatch(r"h[1-6]", node.name):
                if node.get_text(" ", strip=True):
                    node["data-original-level"] = node.name[1]
                else:
                    node.name = "div"
            if node.name == "img":
                remote = image_url(node, url)
                info = assets.get(remote)
                if info and info.get("digest"):
                    node.attrs = {
                        "src": f"/assets/{info['digest']}/",
                        "alt": node.get("alt", ""),
                        "loading": "lazy",
                        "decoding": "async",
                    }
                else:
                    description = node.get("alt") or remote
                    node.name = "span"
                    node.attrs = {"class": "missing-image"}
                    node.string = f"[Image unavailable: {description}]"
                if new_id:
                    node["id"] = new_id
            if node.name not in TAGS and not re.fullmatch(r"h[1-6]", node.name):
                node.name = "span"
            source_block = node.__dict__.pop("_reviewed_source_block", None)
            if review and source_block is not None:
                node["data-preview-block"] = str(source_block)
            excerpt_block = node.__dict__.pop("_reviewed_excerpt_block", None)
            if review and excerpt_block is not None:
                node["data-excerpt-block"] = str(excerpt_block)
        headings = body.select("[data-original-level]")
        original_levels = [
            node.__dict__.get("_reviewed_original_level", int(node["data-original-level"]))
            for node in headings
        ]
        if headings:
            minimum = min((level for level in original_levels if level is not None), default=2)
            base = (4 if part.group else 3) if source.book else 2
            if part.use_source_headings:
                base = 3 if part.group else 2
            for node in headings:
                numbered_chapter = (
                    source.book and node is numbered_title
                    and "_reviewed_heading_level" not in node.__dict__
                )
                level = node.__dict__.pop(
                    "_reviewed_heading_level",
                    min(6, base + int(node["data-original-level"]) - minimum),
                )
                node.name = f"h{level}"
                if numbered_chapter:
                    node.name = "h3" if part.group else "h2"
                del node["data-original-level"]
        normalize_quotations(body, result)
        for quotation in body.select("blockquote"):
            paragraphs = quotation.find_all("p", recursive=False)
            if len(paragraphs) == 1:
                strip_outer_quotes(paragraphs[0])
            elif not paragraphs:
                strip_outer_quotes(quotation)
        for node in list(body.contents):
            root.append(node.extract())
        result.append(root)
        sections.append((url, root))
    for url, section in sections:
        for anchor in section.select("a[href]"):
            raw = str(anchor["href"])
            absolute, fragment = urldefrag(urljoin(url, raw))
            try:
                target_page = canonical_url(absolute)
            except ImportFailure:
                if not raw.startswith(("https://", "http://", "mailto:")):
                    del anchor["href"]
                continue
            target = target_map.get((target_page, unquote(fragment))) if fragment else None
            if target_page in page_roots or target:
                if fragment and not target:
                    raise ImportFailure(
                        f"Unresolved internal link: {urljoin(url, raw)}", "incomplete"
                    )
                anchor["href"] = "#" + (target or page_roots[target_page])
            else:
                anchor["href"] = urljoin(url, raw)
    discard_empty_containers(result, review=review)
    for heading in result.select("h2, h3, h4, h5, h6"):
        normalize_heading(heading, names, language=source.metadata.get("language", "en"))
    toc = heading_toc(result)
    used_ids = {node["id"] for node in result.select("[id]")}
    # Give each local note target a return link when the source supplies none.
    nodes_by_id = {node["id"]: node for node in result.select("[id]")}
    for anchor in list(result.select("a[href^='#']")):
        destination = nodes_by_id.get(anchor["href"][1:])
        if not destination:
            raise ImportFailure(f"Unresolved reader link: {anchor['href']}", "incomplete")
        if not anchor.has_attr("data-note-reference"):
            continue
        if destination.name == "a":
            destination = destination.find_parent(["p", "li"]) or destination.parent
        if not anchor.get("id"):
            value = f"ref-{len(used_ids)}"
            while value in used_ids:
                value += "-n"
            anchor["id"] = value
            used_ids.add(anchor["id"])
        if not destination.find("a", href="#" + anchor["id"]):
            backlink = result.new_tag("a", href="#" + anchor["id"])
            backlink["class"] = "note-backlink"
            backlink["aria-label"] = "Back to reference"
            backlink.string = " [back]"
            destination.append(backlink)
    html = nh3.clean(
        str(result),
        tags=TAGS,
        attributes={
            "*": (
                {"id", "class", "data-preview-block", "data-excerpt-block"}
                if review else {"id", "class"}
            ),
            "a": {"href", "title", "class", "aria-label"},
            "img": {"src", "alt", "loading", "decoding"},
            "span": {"class"},
            "p": {"class"},
            "div": {"class"},
            "figure": {"class"},
            "th": {"colspan", "rowspan"},
            "td": {"colspan", "rowspan"},
        },
        url_schemes={"http", "https", "mailto"},
        link_rel="noopener noreferrer",
        strip_comments=True,
    )
    return html, {
        "toc": toc,
        "book": source.book,
        "pages": len(pages),
        "parts": [
            {
                "url": canonical_url(part.url),
                "title": part.title,
                "role": part.role,
                "id": f"c{index + 1}",
                **(
                    {
                        **({"section": part.section} if part.section else {}),
                        "origin": "contents-page",
                        "authorship": "unspecified",
                    }
                    if part.section or (
                        source.book and part.url == source.__dict__.get("_contents_url")
                        and not part.excerpt
                    )
                    else {}
                ),
                **(
                    {"excerpt": part.excerpt, "origin": "reviewed-source-excerpt",
                     "authorship": "unspecified"}
                    if part.excerpt else {}
                ),
            }
            for index, (part, _) in enumerate(pages)
        ],
    }
