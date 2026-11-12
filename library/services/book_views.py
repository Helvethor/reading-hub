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


# Mirrors headingLabel() in frontend/section-info.js.
BRACKETED_NOTE = re.compile(r"\[\s*(?:\d{1,4}|[a-z]|[*\u2020\u2021\u00a7\u00b6]{1,3})\s*\]", re.I)
BARE_NOTE = re.compile(r"\d{1,4}|[*\u2020\u2021\u00a7\u00b6]{1,3}")


def note_reference(node, heading):
    if node.name not in {"sup", "a", "span"} or (
        node.name == "span" and "text-superscript-on" not in node.get("class", [])
    ):
        return False
    ancestors = []
    for parent in node.parents:
        if parent is heading:
            break
        ancestors.append(parent)
    scope = [node, *ancestors, *node.find_all(True)]
    superscript = any(item.name == "sup" or "text-superscript-on" in item.get("class", [])
                      for item in scope)
    internal = any(item.name == "a" and item.get("href", "").startswith("#") for item in scope)
    text = node.get_text().strip()
    if BRACKETED_NOTE.fullmatch(text):
        return superscript or internal
    return bool(BARE_NOTE.fullmatch(text)) and superscript and internal


def heading_label(heading):
    """Navigation/ToC label: the heading text without note references like [8]."""
    text = heading.get_text()
    copy = BeautifulSoup(str(heading), "html.parser").find(heading.name)
    removed = False
    while note := next((node for node in copy.find_all(True) if note_reference(node, copy)), None):
        note.decompose()
        removed = True
    return " ".join(copy.get_text().split()) if removed else text


def section_title(section):
    headings = [
        heading for heading in section.find_all(HEADINGS)
        if heading.find_parent("section") is section
    ]
    target = section.get("data-section-title")
    return next((heading for heading in headings if target and heading.get("id") == target),
                headings[0] if headings else None)


def book_entries(soup, document_title="", book=False):
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
    root_sections = [
        section for section in soup.select("section[id]")
        if section.find_parent("section") is None
    ]

    def visit(parent):
        children = [node for node in parent.children if isinstance(node, Tag)]
        for index, node in enumerate(children):
            position, end = positions[id(node)], ends[id(node)]
            if node.name == "section":
                heading = section_title(node)
                role = node.get("data-section-role")
                root_article = (
                    role == "article" and not book
                    and node.find_parent("section") is None and len(root_sections) == 1
                )
                if role == "article":
                    title = document_title.strip() if root_article else node.get(
                        "data-section-label", ""
                    ).strip()
                    title = title or "Untitled article"
                else:
                    title = (heading_label(heading).strip() if heading is not None else "")[:120]
                    title = title or node.get("id") or "Untitled section"
                parts.append({
                    "from": position + 1, "to": end - 1, "node": node,
                    "heading": heading,
                    "title": title[:120],
                    "raw_title": title[:120] if role == "article" else (
                        (heading.get_text().strip() if heading is not None else "")[:120]
                    ),
                    "root_article": root_article,
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
                    "title": heading_label(node).strip()[:120] or "Untitled heading",
                    "raw_title": node.get_text().strip()[:120],
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


def publication_toc(soup, document_title="", *, book=False):
    """Assign navigation targets only; never insert numbering into saved prose."""
    used = {node["id"] for node in soup.select("[id]")}
    toc = []
    for index, part in enumerate(book_entries(soup, document_title, book), 1):
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
            "editor_entry": True,
            "in_toc": part["in_toc"] and not part.get("root_article", False),
        })
    return toc


def part_layout(metadata, book=False):
    from library.services.document_metadata import book_pages

    pages = book_pages(metadata, book)
    work_type = metadata.get("work_type")
    book_like = (
        work_type in {"book", "anthology", "pamphlet", "report"}
        if work_type and work_type != "other" else bool(book)
    )
    reason = work_type if work_type and work_type != "other" else (
        f"classification fallback ({'book' if book else 'article'})"
    )
    layout = metadata.get("layout", {})
    modern = layout.get("version") == 1 and layout.get("defaults") != "legacy"
    overrides = layout.get("overrides", {})
    result = {}
    for part in ("title", "toc", "body", "metadata", "edition"):
        value = "continuous"
        if modern:
            if book_like and part in {"toc", "body", "metadata"}:
                value = "new-page"
            if part == "edition" and book_like and not pages["metadata_page"]:
                value = "new-page"
        elif (
            part == "body" and (pages["contents_page"] or pages["title_layout"] == "full")
            or part == "toc" and pages["title_layout"] == "full" or part == "metadata"
        ):
            value = "new-page"
        result[part] = {
            "value": overrides.get(part, value),
            "reason": reason if modern else "preserved legacy pagination",
            "origin": "override" if part in overrides else "default" if modern else "legacy",
        }
    result["title"]["value"] = "continuous"
    return result


def layout_context(metadata, book=False):
    layout = metadata.get("layout", {})
    return {
        "layout_boundaries": part_layout(metadata, book),
        "layout_policy": bool(layout),
        "layout_policy_version": 1,
    }


def apply_part_layout(soup, metadata, book):
    """Apply presentation attributes to a projection, never immutable semantic HTML."""
    layout = metadata.get("layout", {})
    modern = layout.get("version") == 1 and layout.get("defaults") != "legacy"
    work_type = metadata.get("work_type")
    book_like = work_type in {"book", "anthology", "pamphlet", "report"} if (
        work_type and work_type != "other"
    ) else bool(book)
    parts = book_entries(soup, book=book)
    body_start = next((node for node in soup.children if isinstance(node, Tag)), None)
    body_separation = part_layout(metadata, book)["body"]["value"]
    for part in parts:
        node = part["node"]
        explicit = node.get("data-layout-before")
        role = node.get("data-section-role")
        default = "new-page" if (
            modern and book_like and node.name == "section" and part["depth"] == 0
            and (not role or role in {"chapter", "article", "appendix"})
        ) else "continuous"
        if layout or explicit:
            node["data-layout-before"] = explicit or default
            # The body wrapper already applies this coincident first boundary.
            if node is body_start or (
                node.name in HEADINGS and node.parent is body_start
                and not any(isinstance(item, Tag) for item in node.previous_siblings)
            ):
                if node["data-layout-before"] == "new-page":
                    body_separation = "new-page"
                node["data-layout-before"] = "continuous"
    return body_separation


def publication_view(html, saved_entries=(), document_title="", *, book=False, metadata=None):
    soup = BeautifulSoup(html, "html.parser")
    toc = publication_toc(soup, document_title, book=book)
    titles = {entry["id"]: entry["title"] for entry in saved_entries if entry.get("editor_entry")}
    parts = book_entries(soup, document_title, book)
    for entry, part in zip(toc, parts, strict=True):
        # Older saved entries kept note markers; only a deliberate different title wins.
        if titles.get(entry["id"], part["raw_title"]) != part["raw_title"]:
            entry["title"] = titles[entry["id"]]
    for part in parts:
        heading = part["heading"]
        if heading is None:
            continue
        if part["marker"]:
            previous = heading.get("data-reading-marker", "")
            heading["data-reading-marker"] = previous + part["marker"] + " "
        if part["title"] != part["raw_title"]:
            heading["data-reading-label"] = part["title"]
    result = {"entries": toc}
    if metadata is not None:
        result["body_separation"] = apply_part_layout(soup, metadata, book)
    return {**result, "content_html": str(soup)}
