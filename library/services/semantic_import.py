"""Explicit, bounded conversion of retained reader HTML into an editing draft."""

from bs4 import BeautifulSoup, NavigableString

from library.services.semantic_documents import (
    INLINE,
    SemanticNestingError,
    SemanticParser,
    canonical_document,
    fingerprint,
)

CONVERSION_VERSION = 1


def preservation_evidence(soup):
    """Preserve text boundaries, attributes and element order, not just plain text."""
    return [
        {"text": str(node), "depth": len(list(node.parents))}
        if isinstance(node, NavigableString) else {
            "tag": node.name,
            "depth": len(list(node.parents)),
            "attributes": {
                name: sorted(value) if isinstance(value, list) else value
                for name, value in node.attrs.items()
                if not (node.name == "a" and name == "rel")
            },
        }
        for node in soup.descendants
    ]


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
        before = preservation_evidence(soup)
        before_elements = [item for item in before if "tag" in item]
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
                before_elements[index]["tag"] = "div"
        if not repairs:
            raise ValueError(
                "Legacy structure needs manual conversion; no safe repair is defined."
            ) from exc
        if preservation_evidence(soup) != before:
            raise ValueError(
                "Legacy conversion changed content or attributes unexpectedly."
            ) from exc
        document = canonical_document({**value, "html": str(soup)})
        # Canonicalization may reorder attributes/rel, but must not change content.
        if preservation_evidence(BeautifulSoup(document["html"], "html.parser")) != before:
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
