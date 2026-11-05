"""Derive corrected edition structure without rewriting pinned source evidence."""

from copy import deepcopy


def section_structure(soup, original, organization=None):
    structure = deepcopy(original)
    originals = {part["id"]: part for part in structure.get("parts", []) if part.get("id")}
    parts = []
    for section in soup.select("section[id]"):
        part = deepcopy(originals.get(section["id"], {}))
        for field in ("parent", "use_source_headings", "excerpt", "section", "excerpt_origin"):
            part.pop(field, None)
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
        for attribute, field in (("data-section-url", "url"), ("data-section-group", "group")):
            if section.has_attr(attribute):
                part.pop(field, None)
                if section[attribute]:
                    part[field] = section[attribute]
        if section.get("data-excerpt-parent"):
            part["excerpt_origin"] = {"section": section["data-excerpt-parent"]}
            if section.get("data-excerpt-url"):
                part["excerpt_origin"]["url"] = section["data-excerpt-url"]
        parent = section.find_parent("section", id=True)
        if parent:
            part["parent"] = parent["id"]
        else:
            part.pop("parent", None)
        parts.append(part)
    structure["parts"] = parts
    structure["book"] = organization["book"] if organization is not None else bool(
        original.get("book"),
    )
    return structure
