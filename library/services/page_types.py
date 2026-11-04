import logging

from django.db import transaction
from django.db.models import Q
from django.utils.module_loading import import_string

from library.models import (
    CatalogueEntry,
    CrawlCapture,
    CrawlPage,
    CrawlSite,
    MetadataSuggestion,
    PageTypeDecision,
)
from library.profile import get_profile
from library.services.errors import ImportFailure
from library.services.metadata_review import normalize_author_name
from library.services.storage import read_blob
from library.sources.base import parse_html
from library.sources.classification import split_authors

logger = logging.getLogger("library")


def preserve_readable_author_reviews(suggestions):
    profile = get_profile()
    sources = {source.host: source for source in profile.sources}
    kept = []
    for suggestion in list(suggestions):
        urls = [
            item["url"]
            for item in suggestion.evidence
            if isinstance(item, dict) and item.get("url")
        ]
        candidates = (
            CrawlCapture.objects.filter(
                site__profile=profile.key,
                url__in=urls,
                discovery_only=False,
            )
            .select_related("site")
            .order_by("-captured_at", "-pk")
        )
        for capture in list(candidates):
            source = sources.get(capture.site.host)
            if source is None or not source.catalogue_adapter:
                continue
            adapter = import_string(source.catalogue_adapter)
            try:
                soup = parse_html(
                    read_blob(capture.response["digest"]), capture.response.get("headers", {})
                )
                link = adapter.metadata(soup, capture.url)
            except ImportFailure as exc:
                logger.warning(
                    "Cannot use capture %s as readable review evidence: %s", capture.pk, exc
                )
                continue
            names = (link.authors or split_authors(link.author)) if link else []
            if normalize_author_name(suggestion.value) not in {
                normalize_author_name(name) for name in names
            }:
                continue
            MetadataSuggestion.objects.filter(
                pk=suggestion.pk, status=MetadataSuggestion.Status.PENDING
            ).update(capture=capture, entry=None)
            kept.append((suggestion.pk, capture.pk))
            break
    return kept


def latest_decision(site, url):
    return PageTypeDecision.objects.filter(site=site, url=url).first()


def is_discovery_page(adapter, soup, url, *, site=None):
    decisions = PageTypeDecision.objects.filter(url=url)
    decisions = (
        decisions.filter(site=site)
        if site is not None
        else decisions.filter(site__profile=get_profile().key)
    )
    decision = decisions.first()
    return bool(
        decision
        and decision.discovery_only
        or hasattr(adapter, "is_discovery_page")
        and adapter.is_discovery_page(soup, url)
    )


@transaction.atomic
def classify(capture, reviewer, action, reason, revision):
    site = CrawlSite.objects.select_for_update().get(pk=capture.site_id)
    current = latest_decision(site, capture.url)
    if str(current.pk if current else 0) != revision:
        raise ValueError("Page type changed since this page was opened. Reload before saving.")
    if action not in {"discovery", "undo"}:
        raise ValueError("Choose a supported page type action.")
    reason = reason.strip()
    if not reason or len(reason) > 2000:
        raise ValueError("Explain the page type decision in 1-2000 characters.")
    if action == "undo" and (current is None or not current.discovery_only):
        raise ValueError("There is no active manual index classification to undo.")
    if action == "discovery" and current and current.discovery_only:
        raise ValueError("This URL already has a manual index classification.")
    captures = list(CrawlCapture.objects.filter(site=site, url=capture.url))
    entries = list(CatalogueEntry.objects.filter(site=site, url=capture.url))
    previous = {
        "captures": {str(row.pk): row.discovery_only for row in captures},
        "entries": {str(row.pk): row.discovery_only for row in entries},
    }
    if action == "discovery":
        CrawlCapture.objects.filter(pk__in=[row.pk for row in captures]).update(discovery_only=True)
        CatalogueEntry.objects.filter(pk__in=[row.pk for row in entries]).update(
            discovery_only=True
        )
        CrawlPage.objects.filter(site=site, url=capture.url, status="done", is_article=True).update(
            status="pending", error=""
        )
        CrawlPage.objects.filter(site=site, url=capture.url).update(is_article=False)
        preserve_readable_author_reviews(
            MetadataSuggestion.objects.filter(
                status=MetadataSuggestion.Status.PENDING,
                field=MetadataSuggestion.Field.AUTHOR,
            ).filter(
                Q(capture__site=site, capture__url=capture.url)
                | Q(entry__site=site, entry__url=capture.url)
            )
        )
    else:
        source = next(source for source in get_profile().sources if source.host == site.host)
        adapter = import_string(source.catalogue_adapter) if source.catalogue_adapter else None
        automatic = None
        for row in captures:
            flag = current.previous_flags["captures"].get(str(row.pk))
            if flag is None:
                soup = parse_html(
                    read_blob(row.response["digest"]), row.response.get("headers", {})
                )
                flag = bool(
                    adapter
                    and hasattr(adapter, "is_discovery_page")
                    and adapter.is_discovery_page(soup, row.url)
                )
            CrawlCapture.objects.filter(pk=row.pk).update(discovery_only=flag)
            automatic = flag
        for row in entries:
            flag = current.previous_flags["entries"].get(str(row.pk), bool(automatic))
            CatalogueEntry.objects.filter(pk=row.pk).update(discovery_only=flag)
    return PageTypeDecision.objects.create(
        site=site,
        url=capture.url,
        discovery_only=action == "discovery",
        previous_flags=previous,
        reviewer=reviewer,
        reason=reason,
    )
