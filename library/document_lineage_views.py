from urllib.parse import urlencode

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.db import OperationalError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from library.document_editor_views import panel_context, panel_response
from library.models import Document
from library.services.document_lineage import (
    LineageConflict,
    LineageLimitExceeded,
    archive_impact,
    archive_lineage,
    build_lineage,
    restore_archive,
)


@require_http_methods(["GET", "POST"])
def workspace(request, pk):
    document = get_object_or_404(Document, pk=pk)
    error, status, lineage, preview, restore_selected = "", 200, None, None, None
    can_review = bool(
        request.user.is_authenticated and (
            request.user.is_staff or request.user.has_perm("library.review_metadata")
        )
    )
    filter_name = request.GET.get("filter", "all")
    if filter_name not in {"all", "publications", "corrections", "generations", "archived"}:
        filter_name = "all"
    selected_id = request.GET.get("selected", "")
    try:
        if request.method == "POST":
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not can_review:
                raise PermissionDenied("Metadata reviewer access required.")
            action = request.POST.get("action")
            if action == "archive":
                if request.POST.get("confirm") != "yes":
                    raise LineageConflict("Explicitly confirm the reviewed archive impact.")
                operation = archive_lineage(
                    document, request.POST.get("node_id", ""), request.user,
                    request.POST.get("preview_digest", ""), request.POST.get("reason", ""),
                )
                params = {
                    "filter": "archived", "selected": operation.scope["target_id"],
                }
                if request.GET.get("embedded") == "1":
                    params["embedded"] = "1"
                return redirect(
                    reverse("document-lineage", args=[document.pk])
                    + f"?{urlencode(params)}"
                )
            if action == "restore":
                if request.POST.get("confirm") != "yes":
                    raise LineageConflict("Explicitly confirm restoring this archive operation.")
                restore_archive(
                    document, request.POST.get("archive_id", ""), request.user,
                    request.POST.get("reason", ""),
                )
                params = {"filter": "all", "selected": request.POST.get("node_id", "")}
                if request.GET.get("embedded") == "1":
                    params["embedded"] = "1"
                return redirect(
                    reverse("document-lineage", args=[document.pk])
                    + f"?{urlencode(params)}"
                )
            raise LineageConflict("Choose an explicit archive or restore action.")

        lineage = build_lineage(
            document, selected=selected_id, filter_name=filter_name,
        )
        if request.GET.get("archive"):
            selected_id = request.GET["archive"]
            lineage = build_lineage(
                document, selected=selected_id, filter_name=filter_name,
            )
            preview = archive_impact(lineage, selected_id)
        if request.GET.get("restore"):
            archive_id = request.GET["restore"]
            restore_selected = next(
                (item for item in lineage["archive_history"] if item["id"] == archive_id),
                None,
            )
            if restore_selected is None:
                raise LineageConflict("The selected archive operation is unavailable.")
    except LineageLimitExceeded as exc:
        error, status = str(exc), 422
    except (LineageConflict, ValueError) as exc:
        error, status = str(exc), 409 if "changed" in str(exc).lower() else 422
    except OperationalError as exc:
        if "locked" not in str(exc).lower():
            raise
        error, status = "Another writer is active. Reload and retry this lineage action.", 409
    if request.method == "POST" and lineage is None:
        selected_id = request.POST.get("node_id", "")
        try:
            lineage = build_lineage(
                document, selected=selected_id,
                filter_name="archived" if request.POST.get("action") == "restore" else "all",
            )
            if request.POST.get("action") == "archive":
                preview = archive_impact(lineage, selected_id)
        except (LineageConflict, LineageLimitExceeded, ValueError) as refresh_error:
            error = f"{error} Current impact preview unavailable: {refresh_error}"

    return panel_response(request, "library/document_lineage.html", {
        "document": document, "lineage": lineage, "lineage_error": error,
        "lineage_filter": filter_name, "archive_preview": preview,
        "restore_selected": restore_selected, "selected_id": selected_id,
        "embedded": panel_context(request)["embedded"], "can_review": can_review,
    }, status=status)
