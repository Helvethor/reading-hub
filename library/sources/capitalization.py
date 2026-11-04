import re
import unicodedata

from bs4 import Comment

from library.sources.classification import normalize_website_author

WORDS = re.compile(r"[^\W\d_]+", re.UNICODE)
ACRONYMS = {
    "US",
    "USA",
    "UK",
    "EU",
    "UE",
    "USSR",
    "URSS",
    "CIA",
    "FBI",
    "NATO",
    "OTAN",
    "UN",
    "ONU",
    "RCA",
    "RCP",
    "PCF",
    "SPD",
    "NEP",
    "ISBN",
    "PDF",
    "HTML",
    "WWI",
    "WWII",
}
NAMES = {
    name.casefold(): name
    for name in (
        "Marx",
        "Engels",
        "Lenin",
        "Lénine",
        "Lenine",
        "Trotsky",
        "Stalin",
        "Staline",
        "Hegel",
        "Kautsky",
        "Plekhanov",
        "Plékhanov",
        "Pannekoek",
        "Bebel",
        "Feuerbach",
        "Bogdanov",
        "Woods",
        "Zola",
        "France",
        "Paris",
        "Europe",
        "Russie",
        "Russia",
    )
}
NAME_PARTICLES = {"de", "du", "des", "van", "von", "der", "den", "da", "dos", "di"}
ROMAN = re.compile(r"(?=[MDCLXVI]+$)M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$")
FRENCH_SPELLINGS = (
    "armée armées armé armés capitalisée complémentaire complémentaires "
    "démocratie démocraties démocratique démocratiques démolie démolies "
    "dépassement détachement détachements deuxième économie économies "
    "économique économiques édition éditions état états expérience expériences "
    "héroïque héroïques matérialisme matérialiste matérialistes "
    "opprimée opprimées opprimé opprimés polémique polémiques "
    "préface préfaces première premières prolétariat prolétarien prolétarienne "
    "révolution révolutions révolutionnaire révolutionnaires "
    "société sociétés spécial spéciaux spéciale spéciales "
    "supérieure supérieures supérieur supérieurs théorie théories unité unités"
).split()
FRENCH_ACCENTS = {
    "".join(
        char for char in unicodedata.normalize("NFD", word) if not unicodedata.combining(char)
    ): word
    for word in FRENCH_SPELLINGS
}
FRENCH_NAMES = {"lenine": "Lénine", "plekhanov": "Plékhanov"}


def case_characters(text, *, author=False, names=None, language="en"):
    characters = list(text)
    if not text.isupper():
        return characters
    known_names = NAMES | (names or {})
    french = language.lower().split("-")[0] == "fr"
    if french:
        known_names |= FRENCH_NAMES
    sentence_start = True
    previous_end = 0
    for match in WORDS.finditer(text):
        word = match.group()
        between = text[previous_end : match.start()]
        if re.search(r"[.!?:]\s", between):
            sentence_start = True
        initial = len(word) == 1 and text[match.end() :].startswith(".")
        roman = ROMAN.fullmatch(word) and not text[match.end() :].startswith(("'", "\u2019"))
        if word in ACRONYMS or roman or initial:
            replacement = word
        elif french and word.casefold() in FRENCH_NAMES:
            replacement = FRENCH_NAMES[word.casefold()]
        elif author:
            replacement = (
                word.lower()
                if (word.casefold() in NAME_PARTICLES and not sentence_start)
                else word.title()
            )
        elif word.casefold() in known_names:
            replacement = known_names[word.casefold()]
        else:
            replacement = FRENCH_ACCENTS.get(word.lower(), word.lower()) if french else word.lower()
            if sentence_start:
                replacement = replacement[0].upper() + replacement[1:]
        # Keep offsets tied to original characters, including Unicode case expansions.
        if len(replacement) == len(word):
            characters[match.start() : match.end()] = list(replacement)
        else:
            for index, char in enumerate(word, match.start()):
                characters[index] = char.lower()
            if sentence_start or author:
                characters[match.start()] = word[0].upper()
        sentence_start = False
        previous_end = match.end()
    return characters


def normalize_capitalization(text, *, author=False, names=None, language="en"):
    if author:
        text = normalize_website_author(text)
    return "".join(case_characters(text, author=author, names=names, language=language))


def normalize_subtitle(text, *, names=None, language="en"):
    words = WORDS.findall(text)
    if (
        sum(word.isupper() for word in words) >= 2
        and all(word.isupper() or word.islower() for word in words)
        and sum(len(word) for word in words if word.isupper()) >
        sum(len(word) for word in words) / 2
    ):
        text = text.upper()
    return normalize_capitalization(text, names=names, language=language)


def author_names(author):
    return {
        word.casefold(): word
        for word in WORDS.findall(author)
        if len(word) > 1 and word[0].isupper() and not word.isupper()
    }


def normalize_heading(heading, names, *, language="en"):
    numbered = False
    breaks = heading.find_all("br", recursive=False)
    if len(breaks) == 1:
        marker = breaks[0]
        prefix = "".join(
            node.get_text() if hasattr(node, "get_text") else str(node)
            for node in reversed(list(marker.previous_siblings))
        ).strip()
        if ROMAN.fullmatch(prefix):
            previous = marker.previous_sibling
            if isinstance(previous, str):
                previous.replace_with(str(previous).rstrip())
            marker.replace_with(". ")
            numbered = True
    nodes = [node for node in heading.find_all(string=True) if not isinstance(node, Comment)]
    if numbered:
        for index, node in enumerate(nodes):
            text = re.sub(r"\s+", " ", str(node))
            if index == 0:
                text = text.lstrip()
            if index == len(nodes) - 1:
                text = text.rstrip()
            node.replace_with(text)
        heading.smooth()
        for node in list(heading.find_all(string=True)):
            if not isinstance(node, Comment):
                node.replace_with(re.sub(r"\s+", " ", str(node)))
        nodes = [node for node in heading.find_all(string=True) if not isinstance(node, Comment)]
    text = "".join(str(node) for node in nodes)
    characters = case_characters(text, names=names, language=language)
    offset = 0
    for node in nodes:
        end = offset + len(str(node))
        replacement = "".join(characters[offset:end])
        if language.lower().split("-")[0] == "fr":
            replacement = re.sub(r"\b(doit) a (?=[A-ZÀ-ÖØ-Þ])", r"\1 à ", replacement)
        if replacement != str(node):
            node.replace_with(replacement)
        offset = end
