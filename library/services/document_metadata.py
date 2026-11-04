"""Shared bibliographic presentation for retained reader and PDF metadata."""

from django.conf.locale import LANG_INFO
from django.utils.translation import get_language_info


def metadata_rows(metadata):
    rows = []
    if metadata.get("author") and not metadata.get("author_is_fallback"):
        rows.append(("Author", metadata["author"]))
    roles = {
        "editor": "Editor",
        "translator": "Translator",
        "unknown": "Contributor (role unconfirmed)",
    }
    for person in metadata.get("contributors", []):
        if person["role"] in roles:
            rows.append((roles[person["role"]], person["name"]))
    labels = {
        "written": "Written",
        "publication": "Published",
        "online_edition": "Online edition",
        "unknown": "Date (role unconfirmed)",
    }
    dates = metadata.get("date_facts", [])
    for date in dates:
        value = date["value"]
        if date.get("end_value"):
            value += f" / {date['end_value']}"
        rows.append((labels[date["type"]], value))
    if metadata.get("published") and not any(date["type"] == "publication" for date in dates):
        rows.append(("Published", metadata["published"]))
    if metadata.get("language"):
        code = metadata["language"].lower().replace("_", "-")
        known = code if code in LANG_INFO else code.split("-")[0]
        name = get_language_info(known)["name"] if known in LANG_INFO else code
        rows.append(("Language", "Unknown language" if code == "und" else name))
    if metadata.get("topics"):
        rows.append(("Subjects", ", ".join(metadata["topics"])))
    return rows
