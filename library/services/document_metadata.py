"""Shared bibliographic presentation for retained reader and PDF metadata."""

from django.conf.locale import LANG_INFO
from django.utils.translation import get_language_info

# Single-value text fields, mostly mirroring marxists.org editorial-note labels.
TEXT_FIELDS = (
    ("original_title", "Original title"),
    ("publisher", "Publisher"),
    ("series", "Series"),
    ("publication_note", "Publication history"),
    ("source_edition", "Source edition"),
    ("translation_note", "Translation"),
    ("online_version", "Online version"),
    ("transcription", "Transcription/markup"),
    ("proofreading", "Proofreading"),
    ("rights", "Rights"),
    ("notes", "Other notes"),
)
PERSON_FIELDS = {"editor": "editor", "translator": "translator", "unknown": "contributor"}
DATE_FIELDS = {
    "written": ("written", "Written"),
    "delivered": ("delivered", "Delivered"),
    "publication": ("publication", "Published"),
    "online_edition": ("online_edition", "Online edition"),
    "unknown": ("date", "Date (role unconfirmed)"),
}
# Ordered keys a reviewer can show on or hide from the generated title page.
TITLE_PAGE_FIELDS = (
    "original_title", "author", "editor", "translator", "contributor", "publisher", "series",
    "written", "delivered", "publication", "online_edition", "date", "publication_note",
    "source_edition", "translation_note", "online_version", "transcription", "proofreading",
    "rights", "notes", "language", "original_language", "subjects", "source_url",
)
DEFAULT_HIDDEN = frozenset({"online_version", "transcription", "proofreading", "rights", "notes"})


def title_page_selection(metadata):
    chosen = metadata.get("title_page_fields")
    if isinstance(chosen, list):
        return set(chosen)
    return set(TITLE_PAGE_FIELDS) - DEFAULT_HIDDEN


def language_name(code):
    code = code.lower().replace("_", "-")
    if code == "und":
        return "Unknown language"
    known = code if code in LANG_INFO else code.split("-")[0]
    return get_language_info(known)["name"] if known in LANG_INFO else code


def text_value(metadata, key):
    return "; ".join(line.strip() for line in metadata[key].splitlines() if line.strip())


def metadata_entries(metadata):
    """Return (selection key, label, value) for every filled bibliographic field."""
    entries = []
    if metadata.get("original_title"):
        entries.append(("original_title", "Original title", metadata["original_title"]))
    if metadata.get("author") and not metadata.get("author_is_fallback"):
        entries.append(("author", "Author", metadata["author"]))
    roles = {
        "editor": "Editor",
        "translator": "Translator",
        "unknown": "Contributor (role unconfirmed)",
    }
    for person in metadata.get("contributors", []):
        if person["role"] in roles:
            entries.append((PERSON_FIELDS[person["role"]], roles[person["role"]], person["name"]))
    for key, label in (("publisher", "Publisher"), ("series", "Series")):
        if metadata.get(key):
            entries.append((key, label, metadata[key]))
    dates = metadata.get("date_facts", [])
    for date in dates:
        value = date["value"]
        if date.get("end_value"):
            value += f" / {date['end_value']}"
        key, label = DATE_FIELDS[date["type"]]
        entries.append((key, label, value))
    if metadata.get("published") and not any(date["type"] == "publication" for date in dates):
        entries.append(("publication", "Published", metadata["published"]))
    for key, label in TEXT_FIELDS[3:]:
        if metadata.get(key):
            entries.append((key, label, text_value(metadata, key)))
    for key, label in (("language", "Language"), ("original_language", "Original language")):
        if metadata.get(key):
            entries.append((key, label, language_name(metadata[key])))
    if metadata.get("topics"):
        entries.append(("subjects", "Subjects", ", ".join(metadata["topics"])))
    return entries


def metadata_rows(metadata):
    shown = title_page_selection(metadata)
    return [(label, value) for key, label, value in metadata_entries(metadata) if key in shown]


def source_url_shown(metadata):
    return "source_url" in title_page_selection(metadata)
