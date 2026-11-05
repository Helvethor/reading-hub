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
}
CLASSES = {
    "document-subtitle", "media-credit", "note-backlink", "missing-image", "quotation",
    *(f"text-align-{value}" for value in ("left", "right", "center", "justify")),
    *(f"text-{style}-{state}" for style in (
        "italic", "bold", "underline", "strikethrough", "superscript", "subscript"
    ) for state in ("on", "off")),
}
ATTRIBUTES = {
    **{tag: {"data-toc-style"} for tag in ("h2", "h3", "h4", "h5", "h6")},
    "section": {
        "data-section-url", "data-section-role", "data-section-title",
        "data-section-group", "data-excerpt-parent", "data-excerpt-url", "data-toc-style",
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
                "preface", "chapter", "appendix", "postscript",
            }:
                raise ValueError("Choose a supported section role.")
            if name == "data-toc-style" and value not in {
                "disc", "decimal", "upper-roman", "lower-roman", "upper-alpha", "lower-alpha",
            }:
                raise ValueError("Choose a supported ToC numbering style.")
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


def document_issues(document, asset_digests):
    """Incomplete relationships may be saved, but never certified as verified."""
    soup = BeautifulSoup(document["html"], "html.parser")
    ids = {node["id"] for node in soup.select("[id]")}
    issues = []
    for section in soup.select("section[data-excerpt-parent], section[data-excerpt-url]"):
        parent_id = section.get("data-excerpt-parent")
        parent = soup.find("section", id=parent_id) if parent_id else None
        if parent is None or parent is section:
            issues.append(
                "Excerpt origin must identify another section: " + (parent_id or "(none)")
            )
        visited = {id(section)}
        while parent is not None:
            if id(parent) in visited:
                issues.append("Excerpt origin linkage must not contain a cycle.")
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
            issues.append("Section title must identify a heading owned by that section: "
                          + section["data-section-title"])
    for anchor in soup.select("a[href^='#']"):
        if unquote(anchor["href"][1:]) not in ids:
            issues.append(f"Unresolved internal target: {anchor['href']}")
    for image in soup.select("img"):
        digest = ASSET.fullmatch(image["src"])[1]
        if digest not in asset_digests:
            issues.append(f"Asset is not bound to the generated draft: {digest}")
    if soup.select_one(".missing-image"):
        issues.append("The document contains an unavailable-image placeholder.")
    if not soup.get_text(strip=True) and not soup.find(["img", "hr"]):
        issues.append("The document has no readable content.")
    return issues
