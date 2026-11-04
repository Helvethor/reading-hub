"""Transient source mapping for review previews, never persisted in extraction."""

from bs4 import Tag

from library.services.corrections import block_rows, editable_nodes


def mark_blocks(body):
    nodes = editable_nodes(body)
    indices = {id(node): index for index, node in enumerate(nodes)}
    rows = block_rows(body)
    for row, node in zip(rows, nodes, strict=True):
        row["parents"] = [indices[id(parent)] for parent in node.parents if id(parent) in indices]
        if isinstance(node, Tag):
            node.__dict__["_reviewed_source_block"] = row["index"]
    return rows, nodes


def mark_unwrapped_text(nodes, soup):
    for index, node in enumerate(nodes):
        if isinstance(node, Tag) or node.parent is None:
            continue
        # Exclusions may have detached an ancestor, rather than this text itself.
        if not any(parent is soup for parent in node.parents):
            continue
        wrapper = soup.new_tag("span")
        wrapper.__dict__["_reviewed_source_block"] = index
        node.wrap(wrapper)
