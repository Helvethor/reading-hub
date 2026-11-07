from urllib.parse import urlencode, urlsplit

from django.conf import settings
from django.http import Http404
from django.urls import reverse

from library.models import CatalogueEntry, CrawlCapture, Document, Rendition
from library.profile import get_profile

REVIEW_PAGES = {
    "work-review",
    "document-editor",
    "document-editor-membership",
    "rendition-corrections",
    "correction-workspace",
    "correction-revisions",
    "catalogue-overlay",
    "content-organization",
    "metadata-review",
}


def navigation(request, context):
    route = request.resolver_match.url_name if request.resolver_match else ""
    user = request.user
    if route not in REVIEW_PAGES or not (
        user.is_authenticated and (user.is_staff or user.has_perm("library.review_metadata"))
    ):
        return {}
    capture = context.get("capture")
    capture_id = request.GET.get("review_capture")
    if capture is None and capture_id:
        if not capture_id.isdecimal():
            raise Http404("Invalid reviewer source.")
        capture = (
            CrawlCapture.objects.select_related("site")
            .filter(pk=capture_id, site__profile=get_profile().key)
            .first()
        )
        if capture is None:
            raise Http404("Reviewer source unavailable in this profile.")
    version = context.get("version")
    version_id = request.GET.get("review_version")
    if version is None and version_id:
        if not version_id.isdecimal():
            raise Http404("Invalid reviewer version.")
        version = (
            Rendition.objects.select_related("document", "snapshot").filter(pk=version_id).first()
        )
        if version is None:
            raise Http404("Reviewer version unavailable.")
    url = (
        version.document.url
        if version
        else (capture.url if capture else request.GET.get("url", ""))
    )
    if route == "content-organization" and request.GET.get("url") and request.GET["url"] != url:
        url = request.GET["url"]
        version, capture = None, None
    if version and urlsplit(version.document.url).hostname not in {
        source.host for source in get_profile().sources
    }:
        raise Http404("Reviewer version unavailable in this profile.")
    entry = (
        CatalogueEntry.objects.select_related("book")
        .filter(url=url, site__profile=get_profile().key)
        .first()
        if url
        else None
    )
    if entry and entry.book_id:
        url = entry.book.url
    if (
        version
        and capture
        and not any(
            page["url"] == capture.url and page["digest"] == capture.response.get("digest")
            for page in version.snapshot.manifest["pages"]
        )
    ):
        # A work may have newer source evidence; do not claim it belongs to this version.
        version = None
        url = entry.book.url if entry and entry.book_id else capture.url
    if not version and url:
        document = Document.objects.filter(url=url).first()
        if document:
            version = document.latest()
    if not capture and version:
        page = version.snapshot.manifest["pages"][0]
        capture = (
            CrawlCapture.objects.select_related("site")
            .filter(
                site__profile=get_profile().key,
                url=page["url"],
                response__digest=page["digest"],
            )
            .order_by("-captured_at", "-pk")
            .first()
        )
    params = {}
    if version:
        params["review_version"] = version.pk
    if capture:
        params["review_capture"] = capture.pk
    if url:
        params["url"] = url

    def link(name, args=None, extra=None):
        query = {**params, **(extra or {})}
        return reverse(name, args=args) + ("?" + urlencode(query) if query else "")

    items = [
        {"label": "Review overview", "url": link("work-review"), "active": route == "work-review"},
    ]
    if version and settings.READING_HUB_EDITOR_PILOT:
        items.append(
            {
                "label": "Document editor",
                "url": link("document-editor", [version.pk], {"start": "source"}),
                "active": route == "document-editor",
            }
        )
    elif version:
        items.append(
            {
                "label": "Source editor",
                "url": link("rendition-corrections", [version.pk]),
                "active": route == "rendition-corrections",
            }
        )
    if version:
        items.append(
            {
                "label": "Page membership",
                "url": link("document-editor-membership", [version.pk]),
                "active": route == "document-editor-membership",
            }
        )
    if capture:
        items.extend(
            [
                {
                    "label": "Catalogue metadata",
                    "url": link("catalogue-overlay", [capture.pk]),
                    "active": route == "catalogue-overlay",
                },
                {
                    "label": "Source revision history",
                    "url": link("correction-revisions", [capture.pk]),
                    "active": route == "correction-revisions",
                },
            ]
        )
    items.append(
        {
            "label": "Metadata review",
            "url": link("metadata-review", extra={"language": "all"} if capture else None),
            "active": route == "metadata-review",
        }
    )
    sources, source_error = [], ""
    if version:
        from library.services.corrections import rendition_correction_sources
        from library.services.errors import ImportFailure

        try:
            sources = rendition_correction_sources(version)
        except (ValueError, ImportFailure, OSError) as exc:
            source_error = str(exc)
        for source in sources:
            source["selected"] = bool(
                capture and source["url"] == capture.url
                and all(
                    source["page"].get(key) == capture.response.get(key)
                    for key in ("digest", "headers", "resolved_url")
                )
            )
    return {
        "items": items,
        "capture": capture,
        "version": version,
        "url": url,
        "title": version.title if version else (entry.title if entry else url),
        "query": urlencode(params),
        "params": params,
        "reading_url": reverse("reader", args=[version.pk]) if version else "",
        "sources": sources,
        "source_error": source_error,
    }
