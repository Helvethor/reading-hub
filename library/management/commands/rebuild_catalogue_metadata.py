from django.core.management.base import BaseCommand
from django.utils.module_loading import import_string

from library.models import CrawlCapture, Snapshot
from library.profile import get_profile
from library.services.catalogue import configured_sites, save_entry
from library.services.catalogue_overlays import persist_metadata
from library.services.errors import ImportFailure
from library.services.storage import read_blob
from library.sources.base import parse_html
from library.sources.capitalization import normalize_capitalization
from library.sources.classification import (
    clean_attribution,
    clean_authors,
    normalize_language,
    split_authors,
    unique,
)


class Command(BaseCommand):
    help = "Rebuild catalogue metadata and topics from cached HTML, without network requests."

    def handle(self, *args, **options):
        profile = get_profile()
        sites = {site.host: site for site in configured_sites()}
        if not sites:
            self.stdout.write("Catalogue is disabled.")
            return
        adapters = {
            source.host: import_string(source.catalogue_adapter) for source in profile.sources
        }
        count = 0
        failures = []
        seen = set()

        def enrich(site, response):
            key = (site.pk, response["url"])
            if key in seen:
                return 0
            adapter = adapters[site.host]
            try:
                soup = parse_html(read_blob(response["digest"]), response["headers"])
                link = adapter.metadata(soup, response["url"])
            except ImportFailure as exc:
                failures.append((response["url"], str(exc)))
                self.stderr.write(f"Skipped {response['url']}: {exc.code}: {exc}")
                seen.add(key)
                return 0
            language = (
                adapter.language(soup, response["url"]) if hasattr(adapter, "language") else ""
            )
            if link:
                save_entry(site, link, language=language, checked=True)
                seen.add(key)
                return 1
            if language and language != "und":
                for entry in site.entries.filter(url=response["url"]):
                    persist_metadata(entry.pk, {"language": language})
                seen.add(key)
            return 0

        # Newest captures fill gaps first; sparse historical copies never erase richer data.
        # Exhaust read cursors before writes to avoid SQLite lock-upgrade deadlocks.
        for capture in CrawlCapture.objects.filter(site__in=sites.values()).order_by(
            "-captured_at", "-pk"
        ):
            count += enrich(capture.site, capture.response)
        for snapshot in Snapshot.objects.select_related("document").order_by("-fetched_at", "-pk"):
            from urllib.parse import urlsplit

            host = profile.aliases.get(
                urlsplit(snapshot.document.url).hostname, urlsplit(snapshot.document.url).hostname
            )
            if host in sites:
                count += enrich(sites[host], snapshot.manifest["pages"][0])
        for site in sites.values():
            for entry in site.entries.all():
                for field, value in entry.metadata_baseline.items():
                    setattr(entry, field, value)
                author = normalize_capitalization(
                    clean_attribution(entry.author), author=True, language=entry.language
                )
                authors = clean_authors(
                    normalize_capitalization(name, author=True, language=entry.language)
                    for name in (entry.authors or split_authors(entry.author))
                )
                topics = entry.topics or unique(entry.topic.split(","))
                adapter = adapters[site.host]
                language = (entry.language if entry.language != "und" else "") or (
                    normalize_language(adapter.language(parse_html(b""), entry.url))
                    if hasattr(adapter, "language")
                    else ""
                )
                if (author, authors, topics, language) != (
                    entry.author,
                    entry.authors,
                    entry.topics,
                    entry.language,
                ):
                    persist_metadata(
                        entry.pk,
                        {
                            "author": author,
                            "authors": authors,
                            "topics": topics,
                            "language": language,
                        },
                    )
        self.stdout.write(f"Read {count} cached document metadata records; no network used.")
        if failures:
            self.stdout.write(f"Skipped {len(failures)} unsupported cached sources; details above.")
