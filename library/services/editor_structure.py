"""Derive corrected edition structure without rewriting pinned source evidence."""

from copy import deepcopy

from library.services.book_views import section_title


def legacy_article_root(soup, original, metadata):
    parts = original.get("parts", [])
    roots = [
        section for section in soup.select("section[id]") if section.find_parent("section") is None
    ]
    if (
        metadata.get("work_type") == "article"
        and original.get("book") is False
        and len(parts) == 1
        and parts[0].get("role") == "chapter"
        and len(roots) == 1
        and roots[0].get("id") == parts[0].get("id")
        and roots[0].get("data-section-role") is None
    ):
        return roots[0]
    return None


def apply_legacy_article_role(soup, original, metadata):
    section = legacy_article_root(soup, original, metadata)
    if section is not None:
        section["data-section-role"] = "article"
    return section


def section_structure(soup, original, organization=None, *, document_title="", metadata=None):
    structure = deepcopy(original)
    originals = {part["id"]: part for part in structure.get("parts", []) if part.get("id")}
    apply_legacy_article_role(soup, structure, metadata or {})
    is_book = (
        organization["book"]
        if organization is not None
        else bool(
            structure.get("book"),
        )
    )
    root_sections = [
        section for section in soup.select("section[id]") if section.find_parent("section") is None
    ]
    parts = []
    for section in soup.select("section[id]"):
        part = deepcopy(originals.get(section["id"], {}))
        for field in ("parent", "use_source_headings", "excerpt", "section", "excerpt_origin"):
            part.pop(field, None)
        heading = section_title(section)
        role = section.get("data-section-role", part.get("role", "chapter"))
        parent = section.find_parent("section", id=True)
        if role == "article":
            standalone_root = not is_book and parent is None and len(root_sections) == 1
            if standalone_root:
                label = document_title.strip()
                section.attrs.pop("data-section-label", None)
            else:
                label = section.get("data-section-label")
            if not label and not standalone_root and part.get("role") == "article":
                label = part.get("title", "")
            if not label:
                raise ValueError(f"Article section {section['id']} needs its own retained title.")
            title = label
        else:
            title = (
                heading.get_text(" ", strip=True)
                if heading
                else part.get(
                    "title",
                    section["id"],
                )
            )
        part.update(
            {
                "id": section["id"],
                "title": title,
                "role": role,
            }
        )
        for attribute, field in (("data-section-url", "url"), ("data-section-group", "group")):
            if section.has_attr(attribute):
                part.pop(field, None)
                if section[attribute]:
                    part[field] = section[attribute]
        if section.get("data-excerpt-parent"):
            part["excerpt_origin"] = {"section": section["data-excerpt-parent"]}
            if section.get("data-excerpt-url"):
                part["excerpt_origin"]["url"] = section["data-excerpt-url"]
        if parent:
            part["parent"] = parent["id"]
        else:
            part.pop("parent", None)
        parts.append(part)
    structure["parts"] = parts
    structure["book"] = is_book
    return structure
