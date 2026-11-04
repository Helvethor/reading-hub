import re
import unicodedata
from datetime import date, datetime
from functools import lru_cache


def unique(values):
    result = {}
    for value in values:
        value = value.strip()
        if value:
            result.setdefault(value.casefold(), value)
    return list(result.values())


def split_authors(value):
    value = clean_attribution(value)
    # Editorial roles following a name are attribution qualifiers, not co-authors.
    value = re.sub(r",\s*(?:rédaction|redaction|editor|editorial board)\b", "", value, flags=re.I)
    value = re.sub(r"\s+[-–—]\s+", ";", value)
    return clean_authors(
        re.split(r"\s*(?:;| & | and | et | und | y | e |,)\s*", value, flags=re.I)
    )


def clean_authors(values):
    places = author_places()
    names = []
    for value in unique(values):
        value = normalize_website_author(clean_attribution(value))
        if not value:
            continue
        parts = [part.strip() for part in value.split(",")]
        while len(parts) > 1 and (fold(parts[-1]) in places or is_date(parts[-1])):
            parts.pop()
        names.append(", ".join(parts))
    # A city is an affiliation only in the presence of a separate author.
    if any(fold(name) not in places for name in names):
        names = [name for name in names if fold(name) not in places]
    return unique(names)


def normalize_website_author(value):
    if re.fullmatch(r"(?:www\.)?[a-z0-9-]{3,}(?:\.[a-z0-9-]{2,})+", value, re.I):
        return value.casefold()
    return value


def is_date(value):
    value = value.strip()
    if re.fullmatch(r"[12]\d{3}", value):
        return True
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}.*)?", value):
        try:
            datetime.fromisoformat(value)
            return True
        except ValueError:
            return False
    match = re.fullmatch(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", value)
    if match:
        day, month, year = map(int, match.groups())
        try:
            date(year, month, day)
            return True
        except ValueError:
            return False
    months = (
        "january|february|march|april|may|june|july|august|september|october|november|december|"
        "janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|decembre|"
        "januar|februar|marz|juni|juli|oktober|dezember"
    )
    return bool(
        re.fullmatch(
            rf"(?:\d{{1,2}}[.\s]+\s*)?(?:{months})(?:\s+\d{{1,2}},?)?\s+\d{{4}}",
            fold(value),
        )
    )


def clean_attribution(value):
    value = value.strip()
    if is_date(value):
        return ""
    while True:
        cleaned = re.sub(r"\s*\([^()]*\)", "", value).strip()
        if cleaned == value:
            break
        value = cleaned
    places = author_places()
    while "," in value:
        head, tail = value.rsplit(",", 1)
        if not is_date(tail) and fold(tail.strip()) not in places:
            break
        if "," in head:
            prefix, previous = head.rsplit(",", 1)
            if is_date(previous.strip() + ", " + tail.strip()):
                value = prefix.strip()
                continue
        value = head.strip()
    return "" if is_date(value) else value


def normalize_language(value):
    value = value.strip().replace("_", "-").lower()
    if len(value) > 35 or not re.fullmatch(r"[a-z]{2,8}(?:-[a-z0-9]{1,8})*", value):
        return ""
    return value.split("-", 1)[0]


@lru_cache(maxsize=16)
def known_places(values):
    return frozenset(fold(place) for place in values)


def author_places():
    from library.profile import get_profile

    profile = get_profile()
    return known_places(
        profile.author_locations
        + tuple(source.host for source in profile.sources)
        + tuple(profile.aliases)
    )


def fold(value):
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(char)
    )


def infer_topics(text, rules):
    text = fold(text)
    result = []
    for label, terms in rules.items():
        hits = sum(
            len(re.findall(r"(?<!\w)" + re.escape(fold(term)) + r"(?!\w)", text))
            for term in unique(fold(term) for term in terms)
        )
        if hits >= 2:
            result.append(label)
    return result
