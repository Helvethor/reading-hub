from urllib.parse import urlencode

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.db import OperationalError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from library.document_editor_views import panel_context, panel_response
from library.models import (
    Document,
    DocumentDraftBase,
    DocumentEditRevision,
    DocumentPublication,
    DocumentReaderSelection,
    Rendition,
)
from library.services.document_lineage import (
    LineageConflict,
    LineageLimitExceeded,
    archive_impact,
    archive_lineage,
    build_lineage,
    restore_archive,
)
from library.services.document_comparison import compare_documents
from library.services.document_edits import preview_rendition_import
from library.services.errors import ImportFailure
from library.services.semantic_documents import fingerprint
from library.services.document_versions import (
    restore_reader_fallback,
    select_reader_target,
)


def _saved_lineage_document(document, node):
    node_type = node["type"]
    if node_type in {"revision", "review"}:
        row = DocumentEditRevision.objects.filter(
            draft_id=node["draft_id"], revision=node["revision_number"],
            draft__rendition__document=document,
        ).first()
        if row is None:
            raise ValueError("The exact saved revision is unavailable for comparison.")
        value, expected = row.document, row.document_digest
    elif node_type in {"history", "generation"} and node.get("draft_id"):
        draft = DocumentDraftBase.objects.filter(
            pk=node["draft_id"], rendition__document=document,
        ).first()
        if draft is None:
            raise ValueError("The exact working-copy base is unavailable for comparison.")
        value, expected = draft.document, draft.document_digest
    elif node_type in {"edition", "publication"}:
        rendition = Rendition.objects.filter(
            pk=node["rendition_id"], document=document,
        ).first()
        if rendition is None:
            raise ValueError("The exact saved edition is unavailable for comparison.")
        if node_type == "publication":
            try:
                row = DocumentPublication.objects.select_related("revision").get(
                    rendition=rendition,
                ).revision
            except DocumentPublication.DoesNotExist:
                raise ValueError(
                    "The publication's exact saved revision is unavailable for comparison."
                ) from None
            value, expected = row.document, row.document_digest
        else:
            value = preview_rendition_import(rendition)["document"]
            expected = ""
    else:
        raise ValueError(
            "This item has no saved semantic content for comparison. Retained source HTML "
            "is not treated as an equivalent saved version."
        )
    if not isinstance(value, dict) or not {"title", "metadata", "html"} <= value.keys():
        raise ValueError("The saved semantic content is malformed and cannot be compared.")
    if expected and fingerprint(value) != expected:
        raise ValueError("The saved content digest does not match; comparison is unavailable.")
    return value


def _lineage_comparison(document, lineage, compare_with=""):
    selected = lineage["selected"]
    if selected.get("outside_scope"):
        return None, "Focus this item into the current genealogy scope before comparing it."
    if selected.get("unknown_ancestry") and not compare_with:
        return None, selected["unknown_ancestry"]
    if compare_with:
        selectable = {
            node["id"] for node in lineage["timeline"]
            if node["type"] in {
                "edition", "publication", "generation", "revision", "review",
            }
            and not node["context_only"]
            and not node["archived"]
            and node["id"] != selected["id"]
        }
        if compare_with not in selectable:
            return None, "Choose a saved version visible in the current genealogy scope."
    before_id = compare_with or selected.get("parent_id")
    if not before_id or before_id.startswith("work:"):
        return None, "This item has no verified saved-content parent to compare."
    nodes = lineage["nodes"]
    before_node = nodes.get(before_id)
    if before_node is None:
        return None, "The exact verified parent is unavailable; no substitute was selected."
    if before_node.get("unknown_ancestry") and not compare_with:
        return None, before_node["unknown_ancestry"]
    try:
        before = _saved_lineage_document(document, before_node)
        after = _saved_lineage_document(document, selected)
        result = compare_documents(before, after)
    except (ValueError, ImportFailure) as exc:
        return None, str(exc)
    return {
        "before_label": before_node["label"],
        "after_label": selected["label"],
        "before_title": before["title"],
        "after_title": after["title"],
        "before_id": before_id,
        "after_id": selected["id"],
        "result": result,
        "review_only": (
            selected.get("type") == "review"
            and not result["changed_fields"]
        ),
    }, ""


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
    if filter_name not in {
        "all", "sources", "publications", "corrections", "generations", "archived",
    }:
        filter_name = "all"
    scope_name = request.GET.get("scope", "branch")
    reader_target = document.reader_target()
    default_anchor = f"edition:{reader_target.pk}" if reader_target else f"work:{document.pk}"
    anchor_id = request.GET.get("anchor") or default_anchor
    selected_id = request.GET.get("selected") or anchor_id
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
            if action in {"select-reader-target", "restore-reader-fallback"}:
                expected_value = request.POST.get("expected_rendition", "")
                expected_rendition = (
                    int(expected_value) if expected_value.isdecimal() else None
                )
                if request.POST.get("confirm") != "yes":
                    raise LineageConflict(
                        "Explicitly confirm the reviewed reader-version selection."
                    )
                if action == "select-reader-target":
                    select_reader_target(
                        document,
                        request.POST.get("rendition_id", ""),
                        request.user,
                        expected_rendition,
                        request.POST.get("reason", ""),
                    )
                    selected_id = f"edition:{request.POST.get('rendition_id', '')}"
                else:
                    restore_reader_fallback(
                        document, request.user, expected_rendition,
                        request.POST.get("reason", ""),
                    )
                    selected_id = "work"
                params = {"filter": "all", "selected": selected_id}
                if request.GET.get("embedded") == "1":
                    params["embedded"] = "1"
                return redirect(
                    reverse("document-lineage", args=[document.pk])
                    + f"?{urlencode(params)}"
                )
            raise LineageConflict("Choose an explicit archive or restore action.")

        lineage = build_lineage(
            document, selected=selected_id, filter_name=filter_name,
            scope_name=scope_name, anchor=anchor_id,
        )
        if request.GET.get("archive"):
            selected_id = request.GET["archive"]
            lineage = build_lineage(
                document, selected=selected_id, filter_name=filter_name,
                scope_name=scope_name, anchor=anchor_id,
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
                scope_name=scope_name, anchor=anchor_id,
            )
            if request.POST.get("action") == "archive":
                preview = archive_impact(lineage, selected_id)
        except (LineageConflict, LineageLimitExceeded, ValueError) as refresh_error:
            error = f"{error} Current impact preview unavailable: {refresh_error}"

    reader_fallback = document.source_generated_reader_fallback()
    if lineage and lineage.get("selected"):
        selected = lineage["selected"]
        selected_rendition_id = selected.get("rendition_id")
        selected["can_select_reader_target"] = bool(
            can_review
            and selected_rendition_id
            and not selected.get("archived")
            and not selected.get("context_only")
            and (
                not document.reader_selection_explicit
                or not reader_target
                or reader_target.pk != selected_rendition_id
            )
        )

    comparison = None
    comparison_error = ""
    compare_with = request.GET.get("compare_with", "")
    compare_choices = []
    if can_review and lineage and lineage.get("selected"):
        comparison, comparison_error = _lineage_comparison(
            document, lineage, compare_with,
        )
        visible_nodes = lineage["timeline"]
        compare_choices = [
            node for node in visible_nodes
            if node["type"] in {
                "edition", "publication", "generation", "revision", "review",
            }
            and node["id"] != lineage["selected"]["id"]
            and not node["context_only"]
            and not node["archived"]
        ]

    return panel_response(request, "library/document_lineage.html", {
        "document": document, "version": reader_target, "lineage": lineage, "lineage_error": error,
        "lineage_filter": filter_name, "archive_preview": preview,
        "restore_selected": restore_selected, "selected_id": selected_id,
        "lineage_scope": scope_name, "anchor_id": anchor_id,
        "comparison": comparison, "comparison_error": comparison_error,
        "compare_with": compare_with, "compare_choices": compare_choices,
        "reader_target": reader_target,
        "reader_fallback": reader_fallback,
        "can_reset_reader_fallback": bool(
            can_review
            and reader_target
            and reader_fallback
            and (
                document.reader_selection_explicit
                or reader_target.pk != reader_fallback.pk
            )
        ),
        "reader_selection_explicit": document.reader_selection_explicit,
        "can_edit_work": can_review,
        "can_review": can_review,
        "reader_selection_history": DocumentReaderSelection.objects.filter(
            document=document,
        ).select_related("previous_rendition", "rendition", "reviewer").order_by(
            "-created_at", "-pk",
        )[:20],
        "embedded": panel_context(request)["embedded"], "can_review": can_review,
    }, status=status)
