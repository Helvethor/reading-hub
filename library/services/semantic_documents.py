"""Version-one semantic HTML documents; no source rewriting or publication."""

import hashlib
import json
import re
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup

from library.sources.normalize import TAGS

SCHEMA_VERSION = 1
MAX_BYTES = 2 * 1024 * 1024
MAX_NODES = 20000
MAX_DEPTH = 100
VOID = {"br", "hr", "img"}
INLINE = {
    "strong", "b", "em", "i", "u", "s", "small", "sup", "sub", "a", "span",
    "br", "img", "code", "abbr", "cite",
    "q",
}
CLASSES = {
    "document-subtitle", "media-credit", "note-backlink", "missing-image", "quotation",
    *(f"text-align-{value}" for value in ("left", "right", "center", "justify")),
    *(f"text-{style}-{state}" for style in (
        "italic", "bold", "underline", "strikethrough", "superscript", "subscript"
    ) for state in ("on", "off")),
}
ATTRIBUTES = {
    **{tag: {"data-toc-style", "data-toc-entry", "data-layout-before"} for tag in ("h2", "h3", "h4", "h5", "h6")},
    "section": {
        "data-section-url", "data-section-role", "data-section-title", "data-section-label",
        "data-section-group", "data-excerpt-parent", "data-excerpt-url", "data-toc-style",
        "data-toc-entry", "data-layout-before",
    },
    "a": {"href", "title", "aria-label", "rel"},
    "img": {"src", "alt", "loading", "decoding"},
    "th": {"colspan", "rowspan"},
    "td": {"colspan", "rowspan"},
}
CHILDREN = {
    "ul": {"li"}, "ol": {"li"}, "dl": {"dt", "dd"},
    "table": {"caption", "thead", "tbody", "tfoot", "tr"},
    "thead": {"tr"}, "tbody": {"tr"}, "tfoot": {"tr"}, "tr": {"td", "th"},
}
PARENTS = {
    "li": {"ul", "ol"}, "dt": {"dl"}, "dd": {"dl"},
    "caption": {"table"}, "thead": {"table"}, "tbody": {"table"}, "tfoot": {"table"},
    "tr": {"table", "thead", "tbody", "tfoot"}, "td": {"tr"}, "th": {"tr"},
    "figcaption": {"figure"},
}
ASSET = re.compile(r"/assets/([0-9a-f]{64})/")


def encode(value):
    def validate_json(item, depth=0):
        if depth > MAX_DEPTH:
            raise ValueError("Document evidence exceeds the nesting limit.")
        if isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                raise ValueError("Document evidence requires string JSON keys.")
            for child in item.values():
                validate_json(child, depth + 1)
        elif isinstance(item, list):
            for child in item:
                validate_json(child, depth + 1)
        elif item is not None and type(item) not in {str, int, float, bool}:
            raise ValueError("Document evidence requires JSON values without coercion.")

    validate_json(value)
    try:
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise ValueError("Document evidence must be finite UTF-8 JSON.") from exc
    if len(raw) > MAX_BYTES:
        raise ValueError("A semantic document supports at most 2 MiB of JSON.")
    return raw


def fingerprint(value):
    return hashlib.sha256(encode(value)).hexdigest()


class SemanticNestingError(ValueError):
    pass


class SemanticParser(HTMLParser):
    def __init__(self, *, validate_nesting=True):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.nodes = 0
        self.validate_nesting = validate_nesting

    def handle_starttag(self, tag, attrs):
        self.nodes += 1
        if tag not in TAGS or self.nodes > MAX_NODES or len(self.stack) >= MAX_DEPTH:
            raise ValueError("Unsupported semantic element or document complexity limit.")
        parent = self.stack[-1] if self.stack else None
        if self.validate_nesting and (
            (parent in CHILDREN and tag not in CHILDREN[parent])
            or (tag in PARENTS and parent not in PARENTS[tag])
            or (parent in INLINE | {"p", "h2", "h3", "h4", "h5", "h6", "pre"}
                and tag not in INLINE)
            or (tag == "a" and "a" in self.stack)
            or (tag == "cite" and "cite" in self.stack)
            or (tag == "img" and "q" in self.stack)
            or (tag in {"p", "h2", "h3", "h4", "h5", "h6"} and "p" in self.stack)
        ):
            raise SemanticNestingError(f"Invalid semantic nesting for {tag}.")
        names = [name for name, _ in attrs]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate semantic attributes are not supported.")
        for name, value in attrs:
            if value is None or name not in {"id", "class"} | ATTRIBUTES.get(tag, set()):
                raise ValueError(f"Unsupported semantic attribute: {tag}.{name}.")
            if name == "id" and (not value or re.search(r"[\s\x00-\x1f]", value)):
                raise ValueError("Targets require a nonempty ID without whitespace.")
            if name == "class" and not set(value.split()) <= CLASSES:
                raise ValueError("Unsupported semantic presentation class.")
            if name in {"colspan", "rowspan"} and not re.fullmatch(r"[1-9][0-9]{0,2}", value):
                raise ValueError("Table spans must be integers from 1 to 999.")
            if name == "src" and not ASSET.fullmatch(value):
                raise ValueError("Images must reference a retained local asset.")
            if name == "href":
                self.validate_link(value)
            if name in {"data-section-url", "data-excerpt-url"}:
                if name == "data-section-url" and not value:
                    continue
                self.validate_link(value)
                if urlsplit(value).scheme not in {"http", "https"}:
                    raise ValueError("Section URLs require an explicit HTTP(S) URL.")
            if name == "data-section-role" and value not in {
                "preface", "chapter", "appendix", "postscript", "article",
            }:
                raise ValueError("Choose a supported section role.")
            if name == "data-section-label" and (
                not value.strip() or len(value) > 500 or re.search(r"[\x00-\x1f\x7f]", value)
            ):
                raise ValueError("Article titles support 1-500 characters without controls.")
            if name == "data-toc-style" and value not in {
                "disc", "decimal", "upper-roman", "lower-roman", "upper-alpha", "lower-alpha",
            }:
                raise ValueError("Choose a supported ToC numbering style.")
            if name == "data-toc-entry" and value not in {"show", "hide"}:
                raise ValueError("Choose a supported ToC visibility.")
            if name == "data-layout-before" and value not in {"continuous", "new-page"}:
                raise ValueError("Choose a supported part separation.")
            if name in {"data-section-title", "data-excerpt-parent"} and (
                not value or re.search(r"[\s\x00-\x1f]", value)
            ):
                raise ValueError(
                    "Section bindings require a nonempty target ID without whitespace."
                )
            if name == "data-section-group" and (
                len(value) > 1000 or re.search(r"[\x00-\x1f\x7f]", value)
            ):
                raise ValueError("Section groups support at most 1000 characters without controls.")
            if name == "rel" and not set(value.split()) <= {"noopener", "noreferrer"}:
                raise ValueError("Unsupported link relationship.")
            if name == "loading" and value not in {"lazy", "eager"}:
                raise ValueError("Unsupported image loading value.")
            if name == "decoding" and value not in {"async", "sync", "auto"}:
                raise ValueError("Unsupported image decoding value.")
        if tag == "img" and "src" not in names:
            raise ValueError("An image requires a retained local asset.")
        if tag not in VOID:
            self.stack.append(tag)

    @staticmethod
    def validate_link(value):
        if value.startswith("#") and len(value) > 1 and not re.search(r"\s", value):
            return
        if re.search(r"[\s\x00-\x1f\\]", value):
            raise ValueError("Invalid semantic link.")
        try:
            parsed = urlsplit(value)
            valid = (
                parsed.scheme in {"http", "https"} and parsed.hostname
                and not parsed.username and not parsed.password
            ) or (parsed.scheme == "mailto" and parsed.path and not parsed.netloc)
        except ValueError as exc:
            raise ValueError("Invalid semantic link.") from exc
        if not valid:
            raise ValueError("Links require a fragment or an explicit HTTP(S)/mailto URL.")

    def handle_startendtag(self, tag, attrs):
        if tag not in VOID:
            raise ValueError("Only void semantic elements may self-close.")
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag:
            raise ValueError("Semantic HTML must have explicitly balanced elements.")

    def handle_data(self, data):
        if data.strip() and (
            not self.stack or (self.validate_nesting and self.stack[-1] in CHILDREN)
        ):
            raise ValueError("Semantic text requires a paragraph or another text container.")

    def handle_comment(self, data):
        raise ValueError("Comments are not semantic document content.")

    def handle_decl(self, decl):
        raise ValueError("Document declarations are not supported.")

    def handle_pi(self, data):
        raise ValueError("Processing instructions are not supported.")

    def unknown_decl(self, data):
        raise ValueError("Unknown document declarations are not supported.")


def canonical_document(value):
    if (
        not isinstance(value, dict)
        or set(value) != {"version", "title", "metadata", "html"}
        or type(value["version"]) is not int or value["version"] != SCHEMA_VERSION
        or not isinstance(value["title"], str) or not 1 <= len(value["title"].strip()) <= 1000
        or not isinstance(value["metadata"], dict) or not isinstance(value["html"], str)
    ):
        raise ValueError("Choose a version-one semantic document with title, metadata and HTML.")
    encode(value)
    parser = SemanticParser()
    parser.feed(value["html"])
    parser.close()
    if parser.stack:
        raise ValueError("Semantic HTML has unclosed elements.")
    soup = BeautifulSoup(value["html"], "html.parser")
    if any(
        section.get("data-section-role") != "article"
        for section in soup.select("section[data-section-label]")
    ):
        raise ValueError("Article titles require the Article section role.")
    ids = [node["id"] for node in soup.select("[id]")]
    if len(ids) != len(set(ids)):
        raise ValueError("Semantic target IDs must be unique.")
    for node in soup.find_all(True):
        node.attrs = dict(sorted(node.attrs.items()))
        if node.has_attr("class"):
            node["class"] = sorted(set(node["class"]))
        if node.name == "a" and node.has_attr("href"):
            node["rel"] = ["noopener", "noreferrer"]
    return json.loads(encode({**value, "html": str(soup)}))


def inline_quote_presentation(html, format_version):
    if str(format_version) != "21":
        return html
    soup = BeautifulSoup(html, "html.parser")
    pairs = {("\u201c", "\u201d"), ("\u00ab", "\u00bb"),
             ("\u201e", "\u201c"), ('"', '"')}
    for quotation in soup.find_all("q"):
        text = quotation.get_text()
        if text and any(text.startswith(opening) and text.endswith(closing)
                        for opening, closing in pairs):
            quotation["data-rh-q-literal"] = "true"
    return str(soup)


def inline_quote_stylesheet(stylesheet, format_version):
    if str(format_version) != "21" or "data-rh-q-literal" in stylesheet:
        return stylesheet
    return stylesheet + """
.reader-content q { quotes: "“" "”" "‘" "’"; }
.reader-content q:lang(fr) { quotes: "« " " »" "“" "”"; }
.reader-content q:lang(de) { quotes: "„" "“" "‚" "‘"; }
.reader-content q::before { content: open-quote; }
.reader-content q::after { content: close-quote; }
.reader-content q[data-rh-q-literal]::before,
.reader-content q[data-rh-q-literal]::after { content: none; }
"""


def document_issue_details(document, asset_digests):
    """Return ordered, locatable content findings without weakening schema checks."""
    soup = BeautifulSoup(document["html"], "html.parser")
    ids = {node["id"] for node in soup.select("[id]")}
    issues = []
    occurrences = {}

    def add(code, message, *, node=None, target="", locator=None, blocking=False):
        key = (code, target)
        occurrences[key] = occurrences.get(key, 0) + 1
        locator = dict(locator or {"kind": "document"})
        if "occurrence" in locator:
            locator["occurrence"] = occurrences[key]
        section = node if node and node.name == "section" else (
            node.find_parent("section") if node else None
        )
        heading = section.find(["h2", "h3", "h4", "h5", "h6"]) if section else None
        context = " ".join(node.get_text(" ", strip=True).split()) if node else ""
        if len(context) > 240:
            context = context[:237].rstrip() + "..."
        section_label = (
            section.get("data-section-label", "")
            or (heading.get_text(" ", strip=True) if heading else "")
            or section.get("id", "")
        ) if section else ""
        issues.append({
            "code": code,
            "message": message,
            "target": target,
            "context": context,
            "section": section_label,
            "occurrence": occurrences[key],
            "locator": locator,
            "blocking": blocking,
        })

    for section in soup.select("section[data-excerpt-parent], section[data-excerpt-url]"):
        parent_id = section.get("data-excerpt-parent")
        parent = soup.find("section", id=parent_id) if parent_id else None
        if parent is None or parent is section:
            target = parent_id or "(none)"
            add(
                "missing-excerpt-origin",
                "Excerpt origin must identify another section: " + target,
                node=section, target=target,
                locator={"kind": "section", "occurrence": 1},
            )
        visited = {id(section)}
        while parent is not None:
            if id(parent) in visited:
                add(
                    "cyclic-excerpt-origin",
                    "Excerpt origin linkage must not contain a cycle.",
                    node=section, target=parent_id or "",
                    locator={"kind": "section", "occurrence": 1},
                )
                break
            visited.add(id(parent))
            target = parent.get("data-excerpt-parent")
            parent = soup.find("section", id=target) if target else None
    for section in soup.select("section[data-section-title]"):
        heading = soup.find(id=section["data-section-title"])
        if (
            heading is None or heading.name not in {"h2", "h3", "h4", "h5", "h6"}
            or heading.find_parent("section") is not section
        ):
            target = section["data-section-title"]
            add(
                "missing-section-title",
                "Section title must identify a heading owned by that section: " + target,
                node=section, target=target,
                locator={"kind": "section", "occurrence": 1},
            )
    for anchor in soup.select("a[href^='#']"):
        if unquote(anchor["href"][1:]) not in ids:
            add(
                "unresolved-internal-link",
                f"Unresolved internal target: {anchor['href']}",
                node=anchor, target=anchor["href"],
                locator={
                    "kind": "anchor", "href": anchor["href"],
                    "occurrence": 1,
                },
            )
    for image in soup.select("img"):
        digest = ASSET.fullmatch(image["src"])[1]
        if digest not in asset_digests:
            add(
                "unbound-asset",
                f"Asset is not bound to the generated draft: {digest}",
                node=image, target=digest,
                locator={"kind": "image", "src": image["src"], "occurrence": 1},
                blocking=True,
            )
    for placeholder in soup.select(".missing-image"):
        add(
            "unavailable-image",
            "The document contains an unavailable-image placeholder.",
            node=placeholder, target=placeholder.get("data-source", ""),
            locator={
                "kind": "missing-image",
                "occurrence": 1,
            },
        )
    if not soup.get_text(strip=True) and not soup.find(["img", "hr"]):
        add("no-readable-content", "The document has no readable content.")
    return issues


def document_issues(document, asset_digests):
    """Incomplete relationships may be saved, but never certified as verified."""
    return [
        issue["message"] for issue in document_issue_details(document, asset_digests)
    ]
