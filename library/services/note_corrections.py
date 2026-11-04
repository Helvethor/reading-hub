"""Explicit source-link repairs, bound to the unchanged extraction blocks."""

from bs4 import Tag


def reference_rows(body, nodes):
    indices = {id(node): index for index, node in enumerate(nodes)}
    rows = []
    for anchor in body.select("a[href]"):
        owner = next((parent for parent in anchor.parents if id(parent) in indices), None)
        if owner is None:
            continue
        links = owner.select("a[href]")
        link = next(index for index, node in enumerate(links) if node is anchor)
        rows.append(
            {
                "block": indices[id(owner)],
                "link": link,
                "text": anchor.get_text(" ", strip=True) or "(image/empty link)",
                "href": str(anchor["href"]),
            }
        )
    return rows


def note_nodes(value, nodes):
    if not isinstance(value, list) or len(value) > 200:
        raise ValueError("Note repairs must be a list of at most 200 references.")
    used = set()
    result = []

    def resolve(selection):
        if (
            not isinstance(selection, dict)
            or set(selection) != {"block", "link"}
            or any(type(index) is not int or index < 0 for index in selection.values())
            or selection["block"] >= len(nodes)
        ):
            raise ValueError("Choose an existing source link by block and link index.")
        block = nodes[selection["block"]]
        links = block.select("a[href]") if isinstance(block, Tag) else []
        if selection["link"] >= len(links):
            raise ValueError("The selected source link no longer exists.")
        anchor = links[selection["link"]]
        if id(anchor) in used or not anchor.get_text(strip=True):
            raise ValueError("Each reference/backlink must be a distinct existing text link.")
        used.add(id(anchor))
        return anchor

    for item in value:
        if not isinstance(item, dict) or set(item) != {"reference", "target", "backlink"}:
            raise ValueError("Each note repair requires reference, target and backlink fields.")
        index = item["target"]
        if type(index) is not int or not 0 <= index < len(nodes):
            raise ValueError("Choose an existing note target block.")
        target = nodes[index]
        if (
            not isinstance(target, Tag)
            or target.name not in {"p", "li"}
            or not target.get_text(strip=True)
        ):
            raise ValueError("A note target must be a non-empty paragraph or list item.")
        reference = resolve(item["reference"])
        if any(parent is target for parent in reference.parents):
            raise ValueError("A note reference cannot be inside its own target.")
        backlink = resolve(item["backlink"]) if item["backlink"] is not None else None
        if backlink is not None and not any(parent is target for parent in backlink.parents):
            raise ValueError("An existing backlink must be inside the selected note target.")
        root = target
        while root.parent is not None:
            root = root.parent
        for node in (reference, target):
            value = node.get("id")
            if value and any(
                other is not node and value in (other.get("id"), other.get("name"))
                for other in root.select("[id],a[name]")
            ):
                raise ValueError("A selected note/reference has an ambiguous duplicate source ID.")
        result.append((reference, target, backlink))
    return result


def validate_note_conflicts(associations, nodes, edits):
    for reference, target, backlink in associations:
        affected = [reference, target] + ([backlink] if backlink is not None else [])
        for edit in edits:
            node = nodes[edit["index"]]
            if any(
                node is selected
                or any(node is parent for parent in selected.parents)
                or any(selected is parent for parent in node.parents)
                for selected in affected
            ):
                raise ValueError(
                    "Do not combine note repairs with edits to their blocks or containers."
                )


def apply_notes(associations, body):
    used_ids = {
        str(node[attr])
        for node in body.select("[id],a[name]")
        for attr in ("id", "name")
        if node.get(attr)
    }

    def ensure_id(node, prefix):
        if not node.get("id"):
            value = prefix
            while value in used_ids:
                value += "-n"
            node["id"] = value
            used_ids.add(value)
        return str(node["id"])

    for index, (reference, target, backlink) in enumerate(associations):
        # Retain existing targets; new IDs cannot shadow source IDs or named anchors.
        target_id = ensure_id(target, f"reviewed-note-{index}")
        reference_id = ensure_id(reference, f"reviewed-reference-{index}")
        reference["href"] = "#" + target_id
        reference.__dict__["_reviewed_note_reference"] = True
        if backlink is not None:
            backlink["href"] = "#" + reference_id
            backlink.__dict__["_reviewed_note_reference"] = False
            backlink.__dict__["_reviewed_note_backlink"] = True
