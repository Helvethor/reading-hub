from django.db import OperationalError, transaction
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from library.document_editor_views import get_version, panel_context
from library.metadata_views import metadata_reviewer_required
from library.models import CrawlCapture
from library.profile import get_profile
from library.services.corrections import retain_rendition_capture
from library.services.errors import ImportFailure
from library.services.page_types import classify, latest_decision


@require_http_methods(["GET", "POST"])
@metadata_reviewer_required
def source_policy(request, pk):
    version = get_version(pk)
    pages = version.snapshot.manifest.get("pages", [])
    values = request.POST if request.method == "POST" else request.GET
    error, notice, status = "", "", 200
    page, capture, decision = 0, None, None
    try:
        page = int(values.get("page", "0"))
        if not 0 <= page < len(pages):
            raise ValueError("Choose a retained page from this edition.")
        if request.method == "POST":
            if values.get("confirm") != "yes":
                raise ValueError(
                    "Confirm that this source policy affects the catalogue and future imports."
                )
            with transaction.atomic():
                capture = retain_rendition_capture(version, page)
                decision = classify(
                    capture, request.user, values.get("action", ""),
                    values.get("reason", ""), values.get("revision", ""),
                )
            notice = (
                "Source policy saved. Existing editions, editor drafts "
                "and annotations are unchanged."
            )
        else:
            capture = CrawlCapture.objects.filter(
                site__profile=get_profile().key, url=pages[page]["url"],
            ).select_related("site").order_by("-captured_at", "-pk").first()
            if capture:
                decision = latest_decision(capture.site, capture.url)
    except (ValueError, ImportFailure, OSError) as exc:
        error, status = str(exc), 422
    except OperationalError as exc:
        if "locked" not in str(exc).lower():
            raise
        error, status = "Another writer is active. Reload this source policy and retry.", 409
    response = render(request, "library/editor_source_policy.html", {
        **panel_context(request), "version": version, "pages": pages,
        "page": page, "decision": decision, "policy_error": error, "notice": notice,
    }, status=status)
    if request.GET.get("embedded") == "1":
        response.editor_panel = True
    return response
