from django.db.models import Q
from django.http import Http404

REVIEW_LANGUAGES = (
    ("readable", "German, English and French"),
    ("de", "German"),
    ("en", "English"),
    ("fr", "French"),
    ("all", "All languages (including unknown)"),
)
ARCHIVE_SECTIONS = {"de": "deutsch", "en": "english", "fr": "francais"}


def review_language(request):
    language = request.GET.get("language", "readable")
    if language not in dict(REVIEW_LANGUAGES):
        raise Http404("Unknown review language filter.")
    return language


def suggestion_language_filter(language):
    if language == "all":
        return Q()
    languages = ("de", "en", "fr") if language == "readable" else (language,)
    result = Q(entry__language__in=languages)
    unknown = Q(entry__isnull=True) | Q(entry__language__in=["", "und"])
    for code in languages:
        result |= unknown & Q(
            capture__url__startswith=f"https://www.marxists.org/{ARCHIVE_SECTIONS[code]}/"
        )
    if "en" in languages:
        for section in ("archive", "history", "reference", "subject"):
            result |= unknown & Q(capture__url__startswith=f"https://www.marxists.org/{section}/")
    return result


def correction_language_filter(language):
    if language == "all":
        return Q()
    languages = ("de", "en", "fr") if language == "readable" else (language,)
    return Q(expected__metadata__language__in=languages) | (
        ~Q(expected__metadata__has_key="language") & Q(original__metadata__language__in=languages)
    )
