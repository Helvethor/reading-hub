"""Derive corrected edition structure without rewriting pinned source evidence."""

from copy import deepcopy

from library.services.book_views import section_title


def section_structure(soup, original, organization=None):
    structure = deepcopy(original)
    originals = {part["id"]: part for part in structure.get("parts", []) if part.get("id")}
    parts = []
    for section in soup.select("section[id]"):
        part = deepcopy(originals.get(section["id"], {}))
        for field in ("parent", "use_source_headings", "excerpt", "section", "excerpt_origin"):
            part.pop(field, None)
        heading = section_title(section)
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
