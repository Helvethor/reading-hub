import logging
from dataclasses import replace
from urllib.parse import urlsplit

from django.db import transaction
from django.utils import timezone
from django.utils.module_loading import import_string

from library.models import (
    CatalogueEntry,
    CatalogueWorker,
    ContentOrganization,
    CrawlCapture,
    CrawlPage,
    CrawlSite,
    Document,
)
from library.profile import get_profile
from library.services.errors import ImportFailure, LimitExceeded
from library.services.fetch import Fetcher, canonical_url
from library.services.page_types import is_discovery_page, latest_decision
from library.services.storage import save_response
from library.sources.base import parse_html
from library.sources.capitalization import normalize_capitalization
from library.sources.catalogue import CatalogueLink
from library.sources.classification import (
    clean_attribution,
    clean_authors,
    normalize_language,
    split_authors,
    unique,
)

logger = logging.getLogger("library")
FETCHERS = {}


class CrawlPaused(Exception):
    pass


def configured_sites():
    profile = get_profile()
    if not profile.catalogue_enabled:
        return CrawlSite.objects.none()
    for source in profile.sources:
        site, _ = CrawlSite.objects.get_or_create(
            profile=profile.key,
            host=source.host,
            defaults={"fetch_articles": source.catalogue_fetch_articles},
        )
        for seed in source.catalogue_seeds:
            CrawlPage.objects.get_or_create(site=site, url=canonical_url(seed))
    return CrawlSite.objects.filter(profile=profile.key, host__in=[s.host for s in profile.sources])


@transaction.atomic
def save_entry(site, link, *, language="", checked=False):
    from library.services.catalogue_overlays import update_metadata

    if not link.title.strip():
        return
    language = normalize_language(link.language or language)
    author = normalize_capitalization(
        clean_attribution(link.author[:1000]), author=True, language=language
    )
    authors = clean_authors(
        normalize_capitalization(name, author=True, language=language)
        for name in (link.authors or split_authors(author))
    )
    topics = unique(link.topics or [part.strip() for part in link.topic.split(",")])
    values = {
        "title": normalize_capitalization(link.title[:1000], language=language),
        "author": author,
        "authors": authors,
        "published": link.published[:100],
        "language": language,
        "topic": normalize_capitalization(link.topic[:500], language=language),
        "topics": topics,
        "era": link.era[:100],
    }
    entry, created = CatalogueEntry.objects.get_or_create(site=site, url=link.url, defaults=values)
    if not created:
        entry = CatalogueEntry.objects.select_for_update().get(pk=entry.pk)
        # Sparse index hints must not erase metadata already read from an article.
        updates = {}
        for name, value in values.items():
            if (checked and name in {"author", "authors", "topic", "topics"}) or (
                value and (checked or not entry.metadata_baseline.get(name, getattr(entry, name)))
            ):
                updates[name] = value
        update_metadata(entry, updates)
    if checked:
        entry.checked_at = timezone.now()
    decision = latest_decision(site, link.url)
    if decision and decision.discovery_only:
        entry.discovery_only = True
    organization = ContentOrganization.objects.filter(entry=entry).first()
    if organization:
        update_metadata(entry, {"title": organization.specification["title"]})
    entry.save()
    return entry


@transaction.atomic
def register_book(site, url, source, *, rendition=None):
    if not source.book:
        return None
    parts = [part for part in source.parts if part.url != url]
    book = save_entry(
        site,
        CatalogueLink(
            url,
            source.title,
            True,
            author=source.metadata.get("author", ""),
            authors=tuple(source.metadata.get("authors", [])),
            language=source.metadata.get("language", ""),
            published=source.metadata.get("published", ""),
        ),
        checked=True,
    )
    if ContentOrganization.objects.filter(entry=book).exists():
        return book
    if book.book_id:
        raise ImportFailure(
            "A book contents page is already part of another book.", "book_structure"
        )
    document = Document.objects.filter(url=url).first()
    rendition = rendition or (document.latest() if document else None)
    if not rendition or not rendition.structure.get("book"):
        return book
    rendered = rendition.structure.get("parts") or rendition.snapshot.manifest.get("parts", [])
    if [part.url for part in source.parts] != [part["url"] for part in rendered]:
        return book
    if book.chapters.filter(membership_reviewed=False).exclude(
        url__in=[part.url for part in parts],
    ).exists():
        raise ImportFailure(
            "Automatic book membership changed. Review content organization.", "book_structure"
        )
    for part in parts:
        chapter = save_entry(
            site,
            CatalogueLink(
                part.url,
                part.title,
                True,
                author=source.metadata.get("author", ""),
                language=source.metadata.get("language", ""),
            ),
        )
        if chapter is None:
            raise ImportFailure("A book chapter has no title.", "book_structure")
        if chapter.membership_reviewed:
            continue
        if chapter.book_id and chapter.book_id != book.pk:
            raise ImportFailure(f"Chapter belongs to another book: {part.url}", "book_structure")
        if chapter.chapters.exists():
            raise ImportFailure("Nested book membership is not supported.", "book_structure")
        if (
            ContentOrganization.objects.filter(entry=chapter).exists()
            and chapter.book_id != book.pk
        ):
            raise ImportFailure(
                f"Reviewed work organization prevents automatic attachment: {part.url}",
                "book_structure",
            )
        chapter.book = book
        chapter.save(update_fields=["book"])
    return book


@transaction.atomic
def enrich_from_rendition(rendition):
    from library.services.catalogue_overlays import update_metadata

    profile = get_profile()
    if not profile.catalogue_enabled:
        return
    metadata = rendition.metadata
    values = {"title": rendition.title, "checked_at": timezone.now()}
    if normalize_language(metadata.get("language", "")):
        values["language"] = normalize_language(metadata["language"])
    for field, limit in (("author", 1000), ("published", 100), ("topic", 500), ("era", 100)):
        if metadata.get(field) and not (field == "author" and metadata.get("author_is_fallback")):
            values[field] = (
                clean_attribution(metadata[field][:limit])
                if field == "author"
                else metadata[field][:limit]
            )
    if not metadata.get("author_is_fallback") and metadata.get("author"):
        values["authors"] = clean_authors(
            metadata.get("authors") or split_authors(metadata["author"])
        )
    if "topics" in metadata:
        values["topics"] = metadata["topics"]
        values["topic"] = metadata.get("topic", "")[:500]
    entries = CatalogueEntry.objects.select_for_update().filter(
        site__profile=profile.key,
        url__in=[rendition.document.url, *rendition.document.aliases],
    )
    for entry in entries:
        update_metadata(entry, values)
        entry.save()


def recover_crawls(*, site_id=None, clear_fetchers=True):
    sites = CrawlSite.objects.filter(profile=get_profile().key)
    if site_id is not None:
        sites = sites.filter(pk=site_id)
    CrawlPage.objects.filter(site__in=sites, status="fetching").update(
        status="pending", error="Interrupted request will be retried."
    )
    sites.filter(enabled=True, status="running").update(status="ready")
    if clear_fetchers:
        if site_id is None:
            FETCHERS.clear()
        else:
            FETCHERS.pop(site_id, None)


def crawl_step(*, site_id=None, progress=None):
    profile = get_profile()
    if not profile.catalogue_enabled:
        return False
    sites = CrawlSite.objects.filter(
        profile=profile.key,
        host__in=[s.host for s in profile.sources],
        enabled=True,
    )
    if site_id is not None:
        sites = sites.filter(pk=site_id)
    site = sites.order_by("last_step", "pk").first()
    if not site:
        return False
    source = next(s for s in profile.sources if s.host == site.host)
    now = timezone.now()
    site.last_step = now
    site.heartbeat = now
    site.save(update_fields=["last_step", "heartbeat"])
    if site.pages >= site.max_pages or site.downloaded >= site.max_bytes:
        CrawlSite.objects.filter(pk=site.pk, enabled=True).update(
            enabled=False,
            status="limited",
            error="Page or byte limit reached. Raise limits to resume.",
        )
        return True
    pending = site.frontier.filter(status="pending")
    prefer_article = site.fetch_articles and site.pages % 2 == 1
    page = (
        pending.filter(is_article=prefer_article).order_by("pk").first()
        or pending.order_by("pk").first()
    )
    if not page:
        status = (
            "complete_with_errors" if site.frontier.filter(status="failed").exists() else "complete"
        )
        CrawlSite.objects.filter(pk=site.pk, enabled=True).update(enabled=False, status=status)
        return True
    if page.is_article and not site.fetch_articles:
        page.status = "skipped"
        page.save(update_fields=["status"])
        return True

    def check_enabled(stage):
        if not CrawlSite.objects.filter(pk=site.pk, enabled=True).exists():
            raise CrawlPaused()
        now = timezone.now()
        CrawlSite.objects.filter(pk=site.pk).update(heartbeat=now)
        CatalogueWorker.objects.filter(profile=profile.key).update(heartbeat=now)
        if progress:
            progress(stage)

    adapter = import_string(source.catalogue_adapter)
    fetcher = FETCHERS.setdefault(site.pk, Fetcher(source_host=site.host))
    fetcher.progress = check_enabled
    if site.pages == 0:
        fetcher.robot_rules.clear()
    fetcher.downloaded = 0
    fetcher.pages.clear()
    fetcher.byte_limit = site.max_bytes - site.downloaded
    fetcher.request_interval = site.request_interval
    page.status = "fetching"
    page.save(update_fields=["status"])
    site.pages += 1
    CrawlSite.objects.filter(pk=site.pk, enabled=True).update(status="running", pages=site.pages)
    try:
        media_types = adapter.media_types(page.url) if hasattr(adapter, "media_types") else None
        response = (
            fetcher.fetch(page.url, media_types=media_types)
            if media_types
            else fetcher.fetch(page.url)
        )
        if progress:
            progress(f"Parsing {page.url}")
        resolved_host = urlsplit(response.url).hostname
        outside_source = profile.aliases.get(resolved_host, resolved_host) != site.host
        soup = (
            adapter.parse_response(response)
            if hasattr(adapter, "parse_response")
            else parse_html(response.body, response.headers)
        )
        discovery_only = not outside_source and (
            is_discovery_page(adapter, soup, page.url, site=site)
            or is_discovery_page(adapter, soup, response.url, site=site)
        )
        if page.is_article and not outside_source:
            CrawlCapture.objects.create(
                site=site,
                url=page.url,
                response=save_response(response, page.url),
                discovery_only=discovery_only,
            )
        if discovery_only:
            CatalogueEntry.objects.filter(site=site, url=page.url).update(discovery_only=True)
            page.is_article = False
        language = adapter.language(soup, response.url) if hasattr(adapter, "language") else "en"
        metadata = (
            None if outside_source or discovery_only else adapter.metadata(soup, response.url)
        )
        if metadata:
            if not page.is_article:
                CrawlCapture.objects.create(
                    site=site, url=page.url, response=save_response(response, page.url)
                )
            # Keep the requested canonical URL stable across redirects.
            save_entry(site, replace(metadata, url=page.url), language=language, checked=True)
            if hasattr(adapter, "book_source"):
                source = adapter.book_source(soup, response.url)
                if source:
                    register_book(site, page.url, source)
        count = site.frontier.count()
        links = (
            ()
            if outside_source or (metadata and page.is_article)
            else adapter.links(soup, response.url)
        )
        for link in links:
            if progress and count % 100 == 0:
                progress(f"Cataloguing links; {count} URLs queued")
            try:
                url = canonical_url(link.url)
            except ImportFailure as exc:
                if exc.code == "unsupported":
                    continue
                raise
            if urlsplit(url).hostname != site.host:
                continue
            existing = site.frontier.filter(url=url).first()
            if not existing:
                if count >= site.max_urls:
                    raise LimitExceeded(
                        "Discovered URL limit reached. Raise the URL limit to resume."
                    )
                CrawlPage.objects.create(site=site, url=url, is_article=link.is_article)
                count += 1
            elif link.is_article and not existing.is_article and existing.status == "pending":
                existing.is_article = True
                existing.save(update_fields=["is_article"])
            if link.is_article:
                save_entry(site, replace(link, url=url), language=language)
        page.status = "done"
        page.error = ""
        CrawlSite.objects.filter(pk=site.pk, enabled=True).update(status="ready")
    except CrawlPaused:
        page.status = "pending"
    except LimitExceeded as exc:
        page.status = "pending"
        page.error = str(exc)
        CrawlSite.objects.filter(pk=site.pk, enabled=True).update(
            enabled=False, status="limited", error=str(exc)
        )
        logger.warning("Catalogue limit for %s: %s", site.host, exc)
    except ImportFailure as exc:
        page.status = "failed"
        page.error = str(exc)
        fields = {"error": str(exc), "status": "ready"}
        if exc.code in {"rate_limited", "network", "unsafe_url"}:
            fields.update(enabled=False, status="failed")
        CrawlSite.objects.filter(pk=site.pk, enabled=True).update(**fields)
        logger.warning("Catalogue request failed for %s: %s", page.url, exc)
    except MemoryError:
        from library.services.workers import release_memory_limit

        release_memory_limit()
        page.status = "failed"
        page.error = (
            "Memory allocation failed. Adjust worker resources before resuming this source."
        )
        CrawlSite.objects.filter(pk=site.pk).update(
            enabled=False, status="failed", error=page.error
        )
        logger.exception("Catalogue worker memory exhausted for %s", page.url)
        raise
    except OSError as exc:
        page.status = "failed"
        page.error = f"Unable to cache crawler HTML: {exc}"
        CrawlSite.objects.filter(pk=site.pk).update(
            enabled=False, status="failed", error=page.error
        )
        logger.exception("Catalogue storage failed for %s", page.url)
        raise
    finally:
        page.save(update_fields=["status", "error", "is_article"])
        CrawlSite.objects.filter(pk=site.pk).update(
            downloaded=site.downloaded + fetcher.downloaded, heartbeat=timezone.now()
        )
    return True


def change_site(site, action, values=None):
    with transaction.atomic():
        site = CrawlSite.objects.select_for_update().get(pk=site.pk)
        if values:
            for name, value in values.items():
                setattr(site, name, value)
        if action == "pause":
            site.enabled = False
            site.status = "paused"
        elif action in {"resume", "restart"}:
            if action == "restart":
                if site.enabled or site.frontier.filter(status="fetching").exists():
                    raise ValueError(
                        "Pause the crawl and wait for its current request before restarting."
                    )
                site.frontier.update(status="pending", error="")
                site.pages = 0
                site.downloaded = 0
            else:
                site.frontier.filter(status="failed").update(status="pending", error="")
            if site.fetch_articles:
                site.frontier.filter(status="skipped").update(status="pending")
            site.enabled = True
            site.status = "ready"
            site.error = ""
        site.save()
