"""Read-only, bounded comparison of exact immutable draft documents."""

import difflib
import json
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag
from django.utils.html import escape, format_html, format_html_join

from library.services.semantic_documents import fingerprint

MAX_TOKENS = 6000
MAX_LINES = 400
MAX_LINE_LENGTH = 2000
MAX_VISUAL_BLOCKS = 300
MAX_VISUAL_WORDS = 6000

_WORD = re.compile(r"\w+|\s+|[^\w\s]+", re.UNICODE)
_SEMANTIC_TAGS = {
    "a", "article", "aside", "b", "blockquote", "br", "cite", "code", "dd", "del",
    "div", "dl", "dt", "em", "figcaption", "figure", "footer", "h1", "h2", "h3",
    "h4", "h5", "h6", "hr", "i", "ins", "li", "mark", "ol", "p", "pre", "q",
    "section", "small", "span", "strong", "sub", "sup", "table", "tbody", "td",
    "th", "thead", "tr", "ul",
}
_DROP_TAGS = {"embed", "iframe", "object", "script", "style", "template"}


def _safe_href(value):
    value = str(value or "").strip()
    parsed = urlsplit(value)
    if parsed.scheme and parsed.scheme.lower() not in {"http", "https", "mailto"}:
        return ""
    if not parsed.scheme and value.startswith("//"):
        return ""
    return value


def _safe_semantic_html(node):
    if isinstance(node, NavigableString):
        return escape(str(node))
    if not isinstance(node, Tag) or node.name in _DROP_TAGS:
        return ""
    if node.name == "img":
        alt = node.get("alt", "").strip() or "No text alternative"
        return format_html('<span class="lineage-media-label">Image: {}</span>', alt)

    children = format_html_join(
        "", "{}", ((_safe_semantic_html(child),) for child in node.children),
    )
    if node.name not in _SEMANTIC_TAGS:
        return children
    if node.name in {"br", "hr"}:
        return format_html("<{}>", node.name)
    if node.name == "a":
        href = _safe_href(node.get("href"))
        if href:
            return format_html('<a href="{}">{}</a>', href, children)
        return format_html("<span>{}</span>", children)
    return format_html("<{0}>{1}</{0}>", node.name, children)


def _semantic_text(node):
    if isinstance(node, NavigableString):
        return str(node)
    if not isinstance(node, Tag) or node.name in _DROP_TAGS:
        return ""
    if node.name == "img":
        return f" Image: {node.get('alt', '').strip() or 'No text alternative'} "
    return "".join(_semantic_text(child) for child in node.children)


def _block(node):
    if isinstance(node, Tag):
        text = " ".join(_semantic_text(node).split())
        tag = node.name
        signature = (node.name, *(child.name for child in node.find_all(True)))
        value = _safe_semantic_html(node)
        source = str(node)
    else:
        text = str(node).strip()
        tag = "text"
        signature = ()
        value = escape(text)
        source = text
    return {
        "tag": tag, "signature": signature, "text": text,
        "html": value, "source": source,
    }


def _visual_blocks(soup, section_id=""):
    root = soup.find("section", id=section_id) if section_id else soup
    if root is None:
        return []
    return [
        _block(node) for node in root.children
        if (isinstance(node, Tag) or str(node).strip())
        and not (isinstance(node, Tag) and node.name in _DROP_TAGS)
    ]


def _unsectioned_blocks(soup):
    remaining = BeautifulSoup(str(soup), "html.parser")
    for section in remaining.select("section[id]"):
        section.decompose()
    return _visual_blocks(remaining)


def _word_changes(before, after):
    old, new = before.split(), after.split()
    if max(len(old), len(new)) > 1500:
        return None
    removed, added = [], []
    for operation, old_start, old_end, new_start, new_end in difflib.SequenceMatcher(
        None, old, new, autojunk=False,
    ).get_opcodes():
        if operation in {"delete", "replace"}:
            removed.extend(old[old_start:old_end])
        if operation in {"insert", "replace"}:
            added.extend(new[new_start:new_end])
    return {
        "before": " ".join(removed),
        "after": " ".join(added),
    }


def _visual_sections(before_html, after_html, selected_section="", section_labels=None):
    section_labels = section_labels or {}
    before_soup = BeautifulSoup(before_html, "html.parser")
    after_soup = BeautifulSoup(after_html, "html.parser")
    if selected_section:
        section_ids = [selected_section]
    else:
        section_ids = list(section_labels)
        if not section_ids:
            section_ids = [""]
        else:
            before_other = _unsectioned_blocks(before_soup)
            after_other = _unsectioned_blocks(after_soup)
            if before_other or after_other:
                section_ids.append(None)
    output = []
    for index, section_id in enumerate(section_ids):
        if section_id is None:
            old, new = before_other, after_other
        else:
            old = _visual_blocks(before_soup, section_id)
            new = _visual_blocks(after_soup, section_id)
        section_markup = "".join(
            block["source"] for block in old + new
        )
        words = sum(len(_WORD.findall(block["text"])) for block in old + new)
        limited = (
            len(old) > MAX_VISUAL_BLOCKS
            or len(new) > MAX_VISUAL_BLOCKS
            or words > MAX_VISUAL_WORDS
            or len(Tokens(section_markup).lines) > MAX_TOKENS
        )
        groups = []
        if not limited:
            matcher = difflib.SequenceMatcher(
                None,
                [block["source"] for block in old],
                [block["source"] for block in new],
                autojunk=False,
            )
            for operation, old_start, old_end, new_start, new_end in matcher.get_opcodes():
                if operation == "equal":
                    unchanged = old[old_start:old_end]
                    if unchanged:
                        groups.append({
                            "unchanged": True, "count": len(unchanged),
                            "blocks": [block["html"] for block in unchanged],
                        })
                    continue
                old_changed, new_changed = old[old_start:old_end], new[new_start:new_end]
                pairs = max(len(old_changed), len(new_changed))
                for pair_index in range(pairs):
                    before = old_changed[pair_index] if pair_index < len(old_changed) else None
                    after = new_changed[pair_index] if pair_index < len(new_changed) else None
                    words_diff = None
                    if before and after and before["signature"] == after["signature"]:
                        words_diff = _word_changes(before["text"], after["text"])
                        if words_diff and not any(words_diff.values()):
                            words_diff = None
                    groups.append({
                        "unchanged": False,
                        "before_html": before["html"] if before else "",
                        "after_html": after["html"] if after else "",
                        "before_kind": before["tag"] if before else "",
                        "after_kind": after["tag"] if after else "",
                        "word_changes": words_diff,
                        "structure_only": bool(
                            before and after and before["text"] == after["text"]
                            and before["source"] != after["source"]
                        ),
                    })
        changes = [group for group in groups if not group["unchanged"]]
        for change_index, group in enumerate(changes):
            group["anchor"] = f"lineage-difference-{index + 1}-{change_index + 1}"
        for change_index, group in enumerate(changes):
            if change_index:
                group["previous_anchor"] = changes[change_index - 1]["anchor"]
            if change_index + 1 < len(changes):
                group["next_anchor"] = changes[change_index + 1]["anchor"]
        output.append({
            "id": section_id,
            "anchor": f"lineage-change-section-{index + 1}",
            "label": section_labels.get(
                section_id, "Unsectioned content" if section_id is None else "Whole document",
            ),
            "groups": groups,
            "changed": bool(changes),
            "limited": limited,
        })
    return output


def _metadata_changes(before, after):
    def flatten(value, prefix=""):
        if isinstance(value, dict):
            output = {}
            for key, child in value.items():
                path = f"{prefix}.{key}" if prefix else str(key)
                output.update(flatten(child, path))
            return output
        if isinstance(value, list):
            output = {}
            for index, child in enumerate(value):
                output.update(flatten(child, f"{prefix}[{index}]"))
            return output
        display = value if isinstance(value, str) else json.dumps(
            value, ensure_ascii=False, sort_keys=True,
        )
        return {prefix or "value": display}

    old, new = flatten(before), flatten(after)
    return [
        {
            "field": key, "before": old.get(key, "Not present"),
            "after": new.get(key, "Not present"),
        }
        for key in sorted(old.keys() | new.keys()) if old.get(key) != new.get(key)
    ]


class Tokens(HTMLParser):
    def __init__(self, markup):
        super().__init__(convert_charrefs=False)
        self.lines = []
        self.feed(markup)
        self.close()

    def handle_starttag(self, tag, attrs):
        self.lines.append(self.get_starttag_text())

    def handle_startendtag(self, tag, attrs):
        self.lines.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        self.lines.append(f"</{tag}>")

    def handle_data(self, data):
        self.lines.extend(data.splitlines(keepends=True))

    def handle_entityref(self, name):
        self.lines.append(f"&{name};")

    def handle_charref(self, name):
        self.lines.append(f"&#{name};")


def document_sections(value):
    sections = {}
    for node in BeautifulSoup(value["html"], "html.parser").select("section[id]"):
        identifier = node["id"]
        if identifier in sections:
            raise ValueError("Section identifiers are ambiguous in this saved document.")
        heading = node.find(["h1", "h2", "h3", "h4", "h5", "h6"])
        sections[identifier] = {
            "label": (heading.get_text(" ", strip=True)[:100] if heading else identifier),
            "html": str(node),
        }
    return sections


def compare_documents(before, after, section="", *, include_visual=True):
    """Compare exact documents and optionally prepare safe semantic blocks."""
    changed = [key for key in ("title", "metadata", "html") if before[key] != after[key]]
    before_sections, after_sections = document_sections(before), document_sections(after)
    sections = {**before_sections, **after_sections}
    if section and section not in sections:
        raise ValueError("Choose an identified section from these saved documents.")
    old_html = before_sections.get(section, {}).get("html", "") if section else before["html"]
    new_html = after_sections.get(section, {}).get("html", "") if section else after["html"]
    old, new = Tokens(old_html).lines, Tokens(new_html).lines
    prefix = 0
    while prefix < min(len(old), len(new)) and old[prefix] == new[prefix]:
        prefix += 1
    suffix = 0
    while (
        suffix < min(len(old), len(new)) - prefix
        and old[len(old) - suffix - 1] == new[len(new) - suffix - 1]
    ):
        suffix += 1
    start = max(0, prefix - 3)
    old_end = min(len(old), len(old) - suffix + 3)
    new_end = min(len(new), len(new) - suffix + 3)
    old, new = old[start:old_end], new[start:new_end]
    limited = len(old) > MAX_TOKENS or len(new) > MAX_TOKENS
    lines = []
    truncated = False
    if not limited:
        for index, line in enumerate(difflib.unified_diff(
            old, new, fromfile="Earlier HTML", tofile="Later HTML", lineterm="", n=3,
        )):
            if index >= MAX_LINES:
                truncated = True
                break
            clipped = len(line) > MAX_LINE_LENGTH
            truncated |= clipped
            marker = " [line clipped]"
            lines.append({
                "text": line[:MAX_LINE_LENGTH - len(marker)] + marker if clipped else line,
                "kind": "added" if line.startswith("+") and not line.startswith("+++") else
                        "removed" if line.startswith("-") and not line.startswith("---") else
                        "context",
            })
    labels = {key: value["label"] for key, value in sections.items()}
    visual_sections = (
        _visual_sections(before["html"], after["html"], section, labels)
        if include_visual else []
    )
    return {
        "changed_fields": changed, "html_changed": old_html != new_html,
        "before_digest": fingerprint(before), "after_digest": fingerprint(after),
        "lines": lines, "limited": limited, "truncated": truncated,
        "omitted_prefix_tokens": start,
        "section": section,
        "sections": [{"id": key, "label": value["label"]} for key, value in sections.items()],
        "metadata_changes": _metadata_changes(before["metadata"], after["metadata"]),
        "visual_sections": visual_sections,
        "visual_changed": any(item["changed"] for item in visual_sections),
        "metadata_before": json.dumps(before["metadata"], ensure_ascii=False, indent=2,
                                      sort_keys=True),
        "metadata_after": json.dumps(after["metadata"], ensure_ascii=False, indent=2,
                                     sort_keys=True),
    }
