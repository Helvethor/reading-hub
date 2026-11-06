"""Read-only publication projections matching the editor's generated book views."""

import re

from bs4 import BeautifulSoup, NavigableString, Tag

HEADINGS = {"h2", "h3", "h4", "h5", "h6"}
STYLES = {"disc", "decimal", "upper-roman", "lower-roman", "upper-alpha", "lower-alpha"}
TOC_ENTRY = {"show", "hide"}
# Matched against the title's letters only, so "Notes:", "ENDNOTES" or "End-notes" all qualify.
AUTOMATIC_HIDDEN_TITLES = {
    "notes", "note", "endnotes", "endnote", "end notes", "footnotes", "footnote",
}


def automatically_hidden(title):
    return " ".join(re.findall(r"[^\W\d_]+", title.casefold())) in AUTOMATIC_HIDDEN_TITLES


def toc_visibility(node, title):
    """Return (setting, hidden itself): explicit show/hide overrides the Notes rule."""
    setting = node.get("data-toc-entry")
    if setting and setting not in TOC_ENTRY:
        raise ValueError(f"Unsupported ToC visibility: {setting}")
    return setting or "auto", setting == "hide" or not setting and automatically_hidden(title)


def marker_text(style, number):
    if style == "none":
        return ""
    if style == "disc":
        return "\u2022"
    text = ""
    if style.endswith("alpha"):
        while number:
            number, digit = divmod(number - 1, 26)
            text = chr(65 + digit) + text
    elif style.endswith("roman") and number < 4000:
        for value, letters in (
            (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"),
            (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"),
            (5, "V"), (4, "IV"), (1, "I"),
        ):
            count, number = divmod(number, value)
            text += letters * count
    else:
        text = str(number)
    return (text.lower() if style.startswith("lower") else text) + "."


def section_title(section):
    headings = [
        heading for heading in section.find_all(HEADINGS)
        if heading.find_parent("section") is section
    ]
    target = section.get("data-section-title")
    return next((heading for heading in headings if target and heading.get("id") == target),
                headings[0] if headings else None)


def book_entries(soup):
    positions, ends = {}, {}
    cursor = 0

    def locate(parent):
        nonlocal cursor
        for node in parent.children:
            if not isinstance(node, Tag):
                if isinstance(node, NavigableString) and node.strip():
                    cursor += len(node)
                continue
            positions[id(node)] = cursor
            cursor += 1
            locate(node)
            cursor += 1
            ends[id(node)] = cursor

    locate(soup)
    parts = []

    def visit(parent):
        children = [node for node in parent.children if isinstance(node, Tag)]
        for index, node in enumerate(children):
            position, end = positions[id(node)], ends[id(node)]
            if node.name == "section":
                heading = section_title(node)
                parts.append({
                    "from": position + 1, "to": end - 1, "node": node,
                    "heading": heading,
                    "title": (heading.get_text().strip() if heading is not None else "")[:120]
                    or node.get("id") or "Untitled section",
                })
            elif node.name in HEADINGS:
                following = next((sibling for sibling in children[index + 1:]
                                  if sibling.name == "section" or sibling.name in HEADINGS
                                  and sibling.name <= node.name), None)
                parts.append({
                    "from": position,
                    "to": positions[id(following)] if following is not None else (
                        ends[id(parent)] - 1 if parent is not soup else cursor
                    ),
                    "node": node, "heading": node,
                    "title": node.get_text().strip()[:120] or "Untitled heading",
                })
            if node.name not in HEADINGS:
                visit(node)

    visit(soup)
    unique, ranges = [], set()
    for part in parts:
        span = (part["from"], part["to"])
        if span not in ranges:
            unique.append(part)
            ranges.add(span)
    counts = {}
    for index, part in enumerate(unique):
        parents = [
            other for other in range(index)
            if unique[other]["from"] <= part["from"] and unique[other]["to"] >= part["to"]
        ]
        parent = min(parents, key=lambda other: unique[other]["to"] - unique[other]["from"],
                     default=-1)
        part["depth"] = unique[parent]["depth"] + 1 if parent >= 0 else 0
        style = part["node"].get("data-toc-style", "none")
        if style != "none" and style not in STYLES:
            raise ValueError(f"Unsupported ToC numbering style: {style}")
        key = (parent, style)
        number = counts.get(key, 0) + 1
        if style != "none":
            counts[key] = number
        part.update(style=style, number=number, marker=marker_text(style, number))
        part["toc_entry"], hidden = toc_visibility(part["node"], part["title"])
        # Hiding an entry hides its nested entries; navigation still lists all of them.
        part["in_toc"] = not hidden and (parent < 0 or unique[parent]["in_toc"])
    return unique


def publication_toc(soup):
    """Assign navigation targets only; never insert numbering into saved prose."""
    used = {node["id"] for node in soup.select("[id]")}
    toc = []
    for index, part in enumerate(book_entries(soup), 1):
        target = part["node"]
        if not target.get("id"):
            identifier = f"heading-{index}"
            while identifier in used:
                identifier += "-h"
            target["id"] = identifier
            used.add(identifier)
        toc.append({
            "id": target["id"], "title": part["title"], "level": part["depth"] + 2,
            "style": part["style"], "number": part["number"], "marker": part["marker"],
            "editor_entry": True, "in_toc": part["in_toc"],
        })
    return toc


def publication_view(html, saved_entries=()):
    soup = BeautifulSoup(html, "html.parser")
    toc = publication_toc(soup)
    titles = {entry["id"]: entry["title"] for entry in saved_entries if entry.get("editor_entry")}
    for entry in toc:
        if entry["id"] in titles:
            entry["title"] = titles[entry["id"]]
    for part in book_entries(soup):
        if part["marker"] and part["heading"] is not None:
            heading = part["heading"]
            previous = heading.get("data-reading-marker", "")
            heading["data-reading-marker"] = previous + part["marker"] + " "
    return {"content_html": str(soup), "entries": toc}
