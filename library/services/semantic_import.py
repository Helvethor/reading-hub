"""Explicit, bounded conversion of retained reader HTML into an editing draft."""

import re

from bs4 import BeautifulSoup, NavigableString

from library.services.semantic_documents import (
    INLINE,
    SemanticNestingError,
    SemanticParser,
    canonical_document,
    fingerprint,
)

CONVERSION_VERSION = 2


def _preservation_item(node):
    if isinstance(node, NavigableString):
        return {"text": str(node), "depth": len(list(node.parents))}
    return {
        "tag": node.name,
        "depth": len(list(node.parents)),
        "attributes": {
            name: sorted(value) if isinstance(value, list) else value
            for name, value in node.attrs.items()
            if not (node.name == "a" and name == "rel")
        },
    }


def preservation_evidence(soup):
    """Preserve text boundaries, attributes and element order, not just plain text."""
    return [_preservation_item(node) for node in soup.descendants]


def _canonical_text_evidence(evidence):
    compacted = []
    for item in evidence:
        if (
            "text" in item and not item["text"].strip() and compacted
            and "text" in compacted[-1] and not compacted[-1]["text"].strip()
            and compacted[-1]["depth"] == item["depth"]
        ):
            compacted[-1]["text"] += item["text"]
        else:
            compacted.append(dict(item))
    return compacted


def _protect_list_whitespace(list_node, soup, created_wrappers, synthetic_evidence):
    wrapper_count = 0
    for node in list(list_node.find_all(string=True)):
        text = str(node)
        if text.strip() or not re.fullmatch(r"[ \t\n]+", text) or not re.search(r"[ \t]", text):
            continue
        replacements = []
        for part in re.findall(r"[ \t]+|\n+", text):
            if part[0] in " \t":
                wrapper = soup.new_tag("span")
                wrapper.append(NavigableString(part))
                created_wrappers.add(id(wrapper))
                wrapper_count += 1
                replacements.append(wrapper)
            else:
                replacements.append(NavigableString(part))
        for replacement in replacements:
            node.insert_before(replacement)
            if isinstance(replacement, NavigableString):
                synthetic_evidence[id(replacement)] = _preservation_item(replacement)
            else:
                text_node = replacement.string
                synthetic_evidence[id(text_node)] = _preservation_item(text_node)
        node.extract()
    return wrapper_count


def _repair_list_flow(list_node, soup, created_wrappers, depth_adjustments):
    pending = []
    previous_item = None
    changed = False

    def contains_content(nodes):
        for node in nodes:
            if isinstance(node, NavigableString):
                if str(node).strip():
                    return True
            elif node.name != "br":
                return True
        return False

    def append_to_previous(nodes):
        nonlocal changed
        for node in nodes:
            if id(previous_item) not in created_wrappers:
                moved_nodes = (
                    (node,) if isinstance(node, NavigableString)
                    else (node, *node.descendants)
                )
                for moved_node in moved_nodes:
                    identity = id(moved_node)
                    depth_adjustments[identity] = depth_adjustments.get(identity, 0) + 1
            previous_item.append(node.extract())
        changed = True

    def prepend_to_item(item, nodes):
        nonlocal changed
        if id(item) not in created_wrappers:
            for node in nodes:
                moved_nodes = (
                    (node,) if isinstance(node, NavigableString)
                    else (node, *node.descendants)
                )
                for moved_node in moved_nodes:
                    identity = id(moved_node)
                    depth_adjustments[identity] = depth_adjustments.get(identity, 0) + 1
        for node in reversed(nodes):
            item.insert(0, node.extract())
        changed = True

    def wrap_pending():
        nonlocal pending, previous_item, changed
        item = soup.new_tag("li")
        pending[0].insert_before(item)
        for node in pending:
            item.append(node.extract())
        created_wrappers.add(id(item))
        previous_item = item
        pending = []
        changed = True

    def whitespace_only(nodes):
        return all(
            isinstance(node, NavigableString) and not str(node).strip()
            for node in nodes
        )

    def flush_pending(next_item=None):
        if not pending:
            return
        if whitespace_only(pending) and next_item is not None:
            prepend_to_item(next_item, pending)
            pending.clear()
        elif whitespace_only(pending) and previous_item is not None:
            append_to_previous(pending)
            pending.clear()
        else:
            wrap_pending()

    for child in list(list_node.contents):
        if getattr(child, "name", None) == "li":
            flush_pending(next_item=child)
            previous_item = child
        elif getattr(child, "name", None) == "br":
            if contains_content(pending):
                pending.append(child)
                wrap_pending()
            elif pending:
                pending.append(child)
                wrap_pending()
            elif previous_item is not None:
                append_to_previous([child])
            else:
                pending.append(child)
        elif isinstance(child, NavigableString) and not str(child).strip():
            pending.append(child)
        else:
            pending.append(child)
    flush_pending()
    return changed


def _expected_after_repairs(
    soup, original, created_wrappers, depth_adjustments, synthetic_evidence
):
    expected = []
    for node in soup.descendants:
        if id(node) in synthetic_evidence:
            expected.append(synthetic_evidence[id(node)])
            continue
        if id(node) in created_wrappers:
            expected.append(_preservation_item(node))
            continue
        item = dict(original[id(node)])
        item["depth"] += sum(
            id(parent) in created_wrappers for parent in node.parents
        ) + depth_adjustments.get(id(node), 0)
        expected.append(item)
    return expected


def preview_import(value, *, binding=None):
    """Return a deterministic proposal; never save, certify or change its source."""
    repairs = []
    try:
        document = canonical_document(value)
    except SemanticNestingError as exc:
        # Relax nesting only, never unsafe attributes, malformed markup or limits.
        parser = SemanticParser(validate_nesting=False)
        parser.feed(value["html"])
        parser.close()
        if parser.stack:
            raise ValueError("Legacy conversion requires balanced semantic HTML.") from exc
        soup = BeautifulSoup(value["html"], "html.parser")
        original_nodes = list(soup.descendants)
        original = {
            id(node): _preservation_item(node)
            for node in original_nodes
        }
        element_indices = {
            id(node): index for index, node in enumerate(soup.find_all(True))
        }
        created_wrappers = set()
        depth_adjustments = {}
        synthetic_evidence = {}
        list_flow_nodes = []
        nodes = list(soup.find_all(True))
        for index, node in reversed(list(enumerate(nodes))):
            if node.name == "span" and any(
                getattr(child, "name", None) and child.name not in INLINE
                for child in node.children
            ):
                # A generic span around blocks has no valid inline semantics.
                # Preserve all attributes/content and disclose the block-wrapper change.
                repairs.append({
                    "element": index, "id": node.get("id"), "operation": "block-wrapper",
                    "before": "span", "after": "div",
                })
                node.name = "div"
                original[id(node)]["tag"] = "div"
        for node in list(soup.find_all(["ul", "ol"])):
            has_direct_flow = any(
                getattr(child, "name", None) != "li"
                and (
                    not isinstance(child, NavigableString)
                    or str(child).strip()
                )
                for child in node.contents
            )
            if not has_direct_flow:
                continue
            if _repair_list_flow(node, soup, created_wrappers, depth_adjustments):
                list_flow_nodes.append(node)
                repairs.append({
                    "element": element_indices[id(node)],
                    "id": node.get("id"),
                    "operation": "list-flow",
                    "before": "direct list content",
                    "after": "list items",
                })
        for node in list_flow_nodes:
            wrapper_count = _protect_list_whitespace(
                node, soup, created_wrappers, synthetic_evidence
            )
            if wrapper_count:
                repair = next(
                    item for item in repairs
                    if item["element"] == element_indices[id(node)]
                    and item["operation"] == "list-flow"
                )
                repair["whitespace_wrappers"] = wrapper_count
        if not repairs:
            raise ValueError(
                "Legacy structure needs manual conversion; no safe repair is defined."
            ) from exc
        expected = _expected_after_repairs(
            soup, original, created_wrappers, depth_adjustments, synthetic_evidence
        )
        if preservation_evidence(soup) != expected:
            raise ValueError(
                "Legacy conversion changed content or attributes unexpectedly."
            ) from exc
        document = canonical_document({**value, "html": str(soup)})
        # HTML serialization can merge adjacent whitespace-only text nodes.
        if _canonical_text_evidence(
            preservation_evidence(BeautifulSoup(document["html"], "html.parser"))
        ) != _canonical_text_evidence(expected):
            raise ValueError(
                "Legacy conversion could not preserve exact semantic content."
            ) from exc
    repairs.sort(key=lambda item: item["element"])
    report = {
        "version": CONVERSION_VERSION,
        "source_digest": fingerprint(value),
        "document_digest": fingerprint(document),
        "binding": {} if binding is None else binding,
        "repairs": repairs,
    }
    return {
        "document": document,
        "conversion": report,
        "approval_digest": fingerprint(report),
        "requires_approval": bool(repairs),
    }
