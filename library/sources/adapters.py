"""Profile-independent adapter dispatch and the shared source contract."""

from urllib.parse import urlsplit

from django.utils.module_loading import import_string

from library.profile import get_profile, source_name
from library.services.errors import ImportFailure
from library.sources.base import Part, Source, image_url, parse_html
from library.sources.capitalization import author_names, normalize_subtitle
from library.sources.classification import clean_attribution, clean_authors
from library.sources.embeds import compact_social_embeds

__all__ = ["Part", "Source", "image_url", "parse_html", "discover", "extract"]


def adapter_for(url):
    profile = get_profile()
    host = urlsplit(url).hostname
    host = profile.aliases.get(host, host)
    for site in profile.sources:
        if site.host == host:
            return import_string(site.adapter)
    raise ImportFailure(f"No source adapter registered for {host}.", "unsupported")


def discover(soup, url, *, force_book=False):
    if force_book and urlsplit(url).hostname != "www.marxists.org":
        raise ImportFailure(
            "Linked-section book reimport is currently supported for Marxists Internet Archive.",
            "unsupported",
        )
    adapter = adapter_for(url)
    source = (
        adapter.discover(soup, url, force_book=True)
        if force_book else adapter.discover(soup, url)
    )
    if source.book and not any(part.url == url and not part.section for part in source.parts):
        source.parts.insert(0, Part(url, "Contents", role="preface", use_source_headings=True))
    if source.book:
        source.__dict__["_contents_url"] = url
    source.metadata["author"] = clean_attribution(source.metadata.get("author", ""))
    if "authors" in source.metadata:
        source.metadata["authors"] = clean_authors(source.metadata["authors"])
    if not source.metadata.get("author", "").strip():
        source.metadata["author"] = source_name(url)
        source.metadata["author_is_fallback"] = True
    if "subtitle" in source.metadata:
        source.metadata["subtitle"] = normalize_subtitle(
            source.metadata["subtitle"],
            names=author_names(source.metadata["author"]),
            language=source.metadata.get("language", "en"),
        )
    return source


def extract(soup, url, **options):
    index = options.pop("index", False)
    section = options.pop("section", "")
    if section:
        from library.sources.index_sections import content, selected

        return selected(content(soup, url), section, use_source_headings=not options.get("book"))
    if index:
        from library.sources.index_sections import mark_sections

        mark_sections(soup, url)
        options["index"] = True
        options["book"] = False
    compact_social_embeds(soup)
    return adapter_for(url).extract(soup, url, **options)
