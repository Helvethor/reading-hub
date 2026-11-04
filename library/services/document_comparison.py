"""Read-only, bounded comparison of exact immutable draft documents."""

import difflib
import json
from html.parser import HTMLParser

from bs4 import BeautifulSoup

from library.services.semantic_documents import fingerprint

MAX_TOKENS = 6000
MAX_LINES = 400
MAX_LINE_LENGTH = 2000


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


def compare_documents(before, after, section=""):
    """Token differences expose markup as well as prose; never render source HTML."""
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
    return {
        "changed_fields": changed, "html_changed": old_html != new_html,
        "before_digest": fingerprint(before), "after_digest": fingerprint(after),
        "lines": lines, "limited": limited, "truncated": truncated,
        "omitted_prefix_tokens": start,
        "section": section,
        "sections": [{"id": key, "label": value["label"]} for key, value in sections.items()],
        "metadata_before": json.dumps(before["metadata"], ensure_ascii=False, indent=2,
                                      sort_keys=True),
        "metadata_after": json.dumps(after["metadata"], ensure_ascii=False, indent=2,
                                     sort_keys=True),
    }
