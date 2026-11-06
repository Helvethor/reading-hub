import re
from dataclasses import dataclass, field
from importlib import import_module
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.staticfiles import finders
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

from library.versions import APP_VERSION

SORTS = {"newest": "-created_at", "oldest": "created_at", "title": "title"}


@dataclass(frozen=True)
class SourceSite:
    host: str
    label: str
    adapter: str
    catalogue_adapter: str = ""
    catalogue_seeds: tuple[str, ...] = ()
    catalogue_fetch_articles: bool = False


@dataclass(frozen=True)
class SiteProfile:
    key: str
    name: str
    tagline: str
    headline: str
    introduction: str
    footer: str
    theme_css: str
    sources: tuple[SourceSite, ...]
    aliases: dict[str, str]
    asset_paths: dict[str, tuple[str, ...]]
    admin_theme_css: str = ""
    adapter_version: str = "1"
    sort_choices: tuple[str, ...] = ("newest", "oldest", "title")
    default_sort: str = "newest"
    source_filter: bool = True
    page_size: int = 20
    max_pages: int = 100
    max_bytes: int = 100 * 1024 * 1024
    request_timeout: int = 30
    request_interval: int = 1
    catalogue_enabled: bool = False
    topic_rules: dict[str, tuple[str, ...]] = field(default_factory=dict)
    author_locations: tuple[str, ...] = ()
    corpus_service: str = ""
    catalogue_redirects: dict[str, str] = field(default_factory=dict)
    reading_paper: str = "#f8f6f0"
    reading_ink: str = "#282c28"

    def validate(self):
        def fail(message):
            raise ImproperlyConfigured(f"Invalid Reading Hub profile: {message}")

        if not re.fullmatch(r"[a-z][a-z0-9-]*", self.key):
            fail("key must be a lowercase slug")
        if any(not re.fullmatch(r"#[0-9a-fA-F]{6}", color)
               for color in (self.reading_paper, self.reading_ink)):
            fail("reading colors must be six-digit hexadecimal colors")
        if self.corpus_service:
            service = import_string(self.corpus_service)
            if not all(
                callable(getattr(service, name, None)) for name in ("step", "close", "report")
            ):
                fail("corpus_service must expose step, close, and report")
        if not isinstance(self.author_locations, tuple) or any(
            not isinstance(place, str) or not place.strip() for place in self.author_locations
        ):
            fail("author_locations must be a tuple of nonempty place names")
        if not isinstance(self.topic_rules, dict) or any(
            not isinstance(label, str)
            or not label.strip()
            or not isinstance(terms, tuple)
            or not terms
            or any(not isinstance(term, str) or not term.strip() for term in terms)
            for label, terms in self.topic_rules.items()
        ):
            fail("topic_rules must map topic names to nonempty tuples of literal phrases")
        if not self.sources or len({s.host for s in self.sources}) != len(self.sources):
            fail("provide sources with distinct canonical hosts")
        hosts = {s.host for s in self.sources}
        for origin, destination in self.catalogue_redirects.items():
            start, end = urlsplit(origin), urlsplit(destination)
            if (
                start.scheme != "https"
                or start.hostname not in hosts
                or end.scheme != "https"
                or not end.hostname
                or start.username
                or end.username
                or start.password
                or end.password
                or start.port
                or end.port
                or start.fragment
                or end.fragment
            ):
                fail("catalogue_redirects must map source HTTPS URLs to exact public HTTPS URLs")
        for host in hosts | set(self.aliases) | set(self.asset_paths):
            if not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", host) or "." not in host:
                fail(f"invalid hostname {host}")
        if any(target not in hosts for target in self.aliases.values()):
            fail("aliases must target registered sources")
        if hosts & set(self.aliases):
            fail("canonical source hosts must not also be aliases")
        for site in self.sources:
            adapter = import_string(site.adapter)
            if not callable(getattr(adapter, "discover", None)) or not callable(
                getattr(adapter, "extract", None)
            ):
                fail(f"{site.adapter} must expose discover and extract")
            if self.catalogue_enabled:
                if not site.catalogue_adapter or not site.catalogue_seeds:
                    fail(f"{site.host} requires a catalogue adapter and seed URLs")
                catalogue = import_string(site.catalogue_adapter)
                if not all(
                    callable(getattr(catalogue, name, None)) for name in ("links", "metadata")
                ):
                    fail(f"{site.catalogue_adapter} must expose links and metadata")
                for seed in site.catalogue_seeds:
                    parts = urlsplit(seed)
                    if (
                        parts.scheme != "https"
                        or parts.netloc != site.host
                        or parts.fragment
                        or len(seed) > 2048
                    ):
                        fail(f"{site.host} requires canonical HTTPS seed URLs")
            if type(site.catalogue_fetch_articles) is not bool:
                fail("catalogue_fetch_articles must be a boolean")
        for paths in self.asset_paths.values():
            if not paths or any(not p.startswith("/") or p.startswith("//") for p in paths):
                fail("asset hosts require explicit absolute path prefixes")
        if not self.sort_choices or any(choice not in SORTS for choice in self.sort_choices):
            fail("sort_choices must use newest, oldest, or title")
        if self.default_sort not in self.sort_choices:
            fail("default_sort must be enabled")
        for name in ("page_size", "max_pages", "max_bytes", "request_timeout", "request_interval"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                fail(f"{name} must be a positive integer")
        if not isinstance(self.source_filter, bool):
            fail("source_filter must be a boolean")
        if type(self.catalogue_enabled) is not bool:
            fail("catalogue_enabled must be a boolean")
        if (
            not self.theme_css.endswith(".css")
            or self.theme_css.startswith("/")
            or ".." in self.theme_css
        ):
            fail("theme_css must be a relative static CSS path")
        if not finders.find(self.theme_css):
            fail(f"theme stylesheet not found: {self.theme_css}")
        if self.admin_theme_css and (
            not self.admin_theme_css.endswith(".css")
            or self.admin_theme_css.startswith("/")
            or ".." in self.admin_theme_css
            or not finders.find(self.admin_theme_css)
        ):
            fail("admin_theme_css must be a relative static CSS path")
        if not self.adapter_version:
            fail("adapter_version must identify the profile's extraction rules")
        return self


def get_profile():
    profile = import_module(settings.READING_HUB_PROFILE).PROFILE
    if not isinstance(profile, SiteProfile):
        raise ImproperlyConfigured("READING_HUB_PROFILE must export a SiteProfile named PROFILE")
    return profile


def source_name(url):
    host = urlsplit(url).hostname
    profile = get_profile()
    host = profile.aliases.get(host, host)
    return next((site.label for site in profile.sources if site.host == host), host or url)


def site_context(request):
    from library.themes import selected_theme, theme_choices, themed_profile

    profile = themed_profile(request)
    return {
        "site": profile,
        "reading_hub_profile": profile,
        "app_version": APP_VERSION,
        "theme_choices": theme_choices(),
        "selected_theme": selected_theme(request),
        "sort_labels": [
            (key, {"newest": "Newest first", "oldest": "Oldest first", "title": "Title A–Z"}[key])
            for key in profile.sort_choices
        ],
    }
