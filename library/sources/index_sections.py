"""Bounded editorial sections following a book's contents navigation."""

import hashlib
from copy import deepcopy

from bs4 import Tag

from library.services.errors import ImportFailure
from library.sources.base import Part


def sections(soup, url):
    """Conservatively recognize direct-sibling prose sections after a contents table."""
    result = []
    for index, heading in enumerate(soup.select("h1,h2,h3,h4,h5,h6")):
        if heading.find_parent(["table", "nav", "footer"]):
            continue
        previous = heading.find_previous_sibling("table") or heading.find_previous_sibling(
            "blockquote"
        )
        if previous is None or len(previous.select("a[href]")) < 2:
            continue
        title = heading.get_text(" ", strip=True)
        if not title:
            continue
        nodes = []
        for sibling in heading.next_siblings:
            if isinstance(sibling, Tag):
                if sibling.name in {"hr", "nav", "footer"}:
                    break
                if sibling.name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                    if int(sibling.name[1]) <= int(heading.name[1]):
                        break
                if set(sibling.get("class", [])) & {"footer", "navigation", "information", "skip"}:
                    break
            nodes.append(sibling)
        prose = sum(
            len(node.get_text(" ", strip=True))
            - sum(len(link.get_text(" ", strip=True)) for link in node.select("a"))
            for node in nodes
            if isinstance(node, Tag) and node.name in {"p", "blockquote", "pre"}
        )
        if prose < 100:
            continue
        key = f"index-{index}-{hashlib.sha256(title.encode()).hexdigest()[:12]}"
        result.append((Part(url, title, role="appendix", section=key), [heading, *nodes]))
    return result


def content(soup, url):
    body = soup.new_tag("div")
    for part, nodes in sections(soup, url):
        section = soup.new_tag("section", id=part.section)
        for index, node in enumerate(nodes):
            copied = deepcopy(node)
            if index == 0:
                copied["data-index-section-title"] = part.section
            section.append(copied)
        body.append(section)
    return body


def mark_sections(soup, url):
    """Keep legacy section identities inside the complete index body."""
    for part, nodes in sections(soup, url):
        section = soup.new_tag("section", id=part.section)
        nodes[0].insert_before(section)
        for index, node in enumerate(nodes):
            if index == 0:
                node["data-index-section-title"] = part.section
            section.append(node.extract())


def selected(body, key, *, use_source_headings=True):
    section = body.find("section", id=key)
    if section is None:
        raise ImportFailure(
            f"Index section {key} is absent or excluded. Review the source and organization.",
            "incomplete",
        )
    result = deepcopy(section)
    if not use_source_headings:
        heading = result.find(attrs={"data-index-section-title": key})
        if heading:
            # Keep source targets even when the part title supplies the visible heading.
            heading.name = "span"
            for child in list(heading.contents):
                if isinstance(child, Tag) and (child.get("id") or child.get("name")):
                    child.clear()
                else:
                    child.extract()
    if not result.get_text(strip=True) and not result.find(["img", "table"]):
        raise ImportFailure(f"Index section {key} has no remaining content.", "incomplete")
    return result
