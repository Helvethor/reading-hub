"""Derive corrected edition structure without rewriting pinned source evidence."""

from copy import deepcopy


def section_structure(soup, original):
    structure = deepcopy(original)
    originals = {part["id"]: part for part in structure.get("parts", []) if part.get("id")}
    ids = {node["id"] for node in soup.select("[id]")}
    missing = originals.keys() - ids
    if missing:
        raise ValueError(
            "Retain source part targets before publishing: " + ", ".join(sorted(missing))
        )
    parts = []
    for section in soup.select("section[id]"):
        part = deepcopy(originals.get(section["id"], {}))
        headings = [
            node for node in section.find_all(["h2", "h3", "h4", "h5", "h6"])
            if node.find_parent("section") is section
        ]
        title_id = section.get("data-section-title")
        heading = next((node for node in headings if node.get("id") == title_id), None)
        if heading is None and headings:
            heading = headings[0]
        part.update({
            "id": section["id"],
            "title": heading.get_text(" ", strip=True) if heading else part.get(
                "title", section["id"],
            ),
            "role": section.get("data-section-role", part.get("role", "chapter")),
        })
        if section.get("data-section-url"):
            part["url"] = section["data-section-url"]
        parent = section.find_parent("section", id=True)
        if parent:
            part["parent"] = parent["id"]
        else:
            part.pop("parent", None)
        parts.append(part)
    # Historical documents can retain a source-part target on a non-section node.
    for target, part in originals.items():
        if not any(item["id"] == target for item in parts):
            parts.append(part)
    structure["parts"] = parts
    structure["pages"] = len({part["url"] for part in parts if part.get("url")}) or original.get(
        "pages", 1,
    )
    structure["book"] = bool(structure.get("book") or len(parts) > 1)
    return structure
