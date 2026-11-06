import json
import uuid

from django.conf import settings
from django.contrib.staticfiles import finders
from django.db import OperationalError, transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from library.metadata_views import metadata_reviewer_required
from library.models import DocumentDraftBase, Rendition, ReviewerRun
from library.profile import get_profile, source_name
from library.services.book_views import publication_view
from library.services.document_comparison import compare_documents
from library.services.document_edits import (
    DocumentEditConflict,
    branch_draft,
    create_draft,
    preview_rendition_import,
    save_revision,
    saved_state,
)
from library.services.document_publication import prepare_publication, publish_revision
from library.services.editor_sources import original_section, source_page
from library.services.errors import ImportFailure
from library.services.fresh_document_drafts import create_fresh_draft, preview_fresh_draft
from library.services.semantic_documents import MAX_BYTES
from library.sources.adapters import adapter_for


def panel_context(request):
    embedded = request.GET.get("embedded") == "1"
    return {
        "embedded": embedded,
        "panel_base": "library/embedded_panel_base.html" if embedded else "library/base.html",
    }


def panel_response(request, template, context, status=200):
    response = render(request, template, {**context, **panel_context(request)}, status=status)
    if request.GET.get("embedded") == "1":
        response.editor_panel = True
    response["Cache-Control"] = "no-store"
    return response


@require_http_methods(["GET", "POST"])
@metadata_reviewer_required
def workspace(request, pk):
    from library.services.reading_styles import style_context

    version = get_version(pk)
    if request.method == "POST":
        return save(request, version)
    if not all(finders.find(path) for path in (
        "library/generated/editor-pilot.js", "library/generated/editor-pilot.css",
    )):
        return render(request, "library/document_editor.html", {
            "version": version,
            "editor_error": "The pilot assets are not built. Run npm ci and npm run build.",
        }, status=503)
    error, initial, draft, choose_history = "", None, None, False
    histories = DocumentDraftBase.objects.filter(
        rendition=version, profile=get_profile().key,
    ).exclude(pk__in=ReviewerRun.objects.values("draft_id")).order_by("-created_at")
    try:
        draft_id = request.GET.get("draft")
        if not draft_id and request.GET.get("start") != "source":
            choices = list(histories[:2])
            if len(choices) == 1:
                draft_id = str(choices[0].pk)
            elif len(choices) > 1:
                choose_history = True
        if draft_id:
            draft = get_draft(draft_id, version)
            revision = draft.revisions.first()
            saved_state(draft, revision.revision if revision else 0)
            initial = {
                "document": revision.document if revision else draft.document,
                "baseline_document": draft.document,
                "structure": draft.evidence.get("structure", version.structure),
                "draft": str(draft.pk), "revision": revision.revision if revision else 0,
                "approval_digest": None, "requires_approval": False, "repairs": [],
                "editorial": revision.editorial if revision else
                draft.evidence.get("correction_origin", {}).get("editorial", False),
                "saved_review": revision.review if revision else None,
                "saved_verified_sections": revision.verified_sections if revision else [],
            }
        else:
            proposal = preview_rendition_import(version)
            initial = {
                "document": proposal["document"], "draft": None, "revision": 0,
                "baseline_document": proposal["document"],
                "structure": version.structure,
                "approval_digest": proposal["approval_digest"],
                "requires_approval": proposal["requires_approval"],
                "repairs": proposal["conversion"]["repairs"],
                "editorial": False,
                "saved_review": None,
                "saved_verified_sections": [],
            }
    except (ValueError, ImportFailure) as exc:
        error = str(exc)
    if initial is not None:
        from django.conf.locale import LANG_INFO
        from django.utils.translation import get_language_info

        initial["choose_history"] = choose_history
        initial["presentation"] = {
            "sourceName": source_name(version.document.url),
            "sourceUrl": version.document.url,
            "languages": {code: get_language_info(code)["name"] for code in LANG_INFO},
        }
    try:
        reading_style = style_context(request)
    except ValueError as exc:
        error, reading_style = str(exc), {}
    response = render(request, "library/document_editor.html", {
        **reading_style,
        "version": version, "initial": initial, "editor_error": error, "draft": draft,
        "choose_history": choose_history,
        "evaluation_run": ReviewerRun.objects.filter(draft=draft, reviewer=request.user).first()
        if draft else None,
    }, status=422 if error else 200)
    response["Cache-Control"] = "no-store"
    return response


@require_http_methods(["GET", "POST"])
@metadata_reviewer_required
def history(request, pk):
    version = get_version(pk)
    error, status, draft, selected, switch_url = "", 200, None, None, None
    try:
        values = request.POST if request.method == "POST" else request.GET
        identifier = values.get("draft")
        if identifier:
            draft = get_draft(identifier, version)
        if request.method == "POST":
            if draft is None:
                raise ValueError("Choose a correction history.")
            number = int(request.POST.get("revision", ""))
            branch = branch_draft(draft, request.user, number)
            switch_url = reverse("document-editor", args=[pk]) + f"?draft={branch.pk}"
            if not panel_context(request)["embedded"]:
                return redirect(switch_url)
        if draft and "revision" in request.GET:
            number = int(request.GET["revision"])
            selected = {"number": number, "row": saved_state(draft, number)}
    except (ValueError, ImportFailure) as exc:
        error, status = str(exc), 422
    except OperationalError as exc:
        if "locked" not in str(exc).lower():
            raise
        error, status = "Another writer is active. Retry starting from this version.", 409
    histories = DocumentDraftBase.objects.filter(
        rendition=version, profile=get_profile().key,
    ).exclude(pk__in=ReviewerRun.objects.values("draft_id")).select_related("reviewer")
    return panel_response(request, "library/document_editor_history.html", {
        "version": version, "draft": draft, "selected": selected,
        "histories": histories.order_by("-created_at"),
        "revisions": draft.revisions.select_related("reviewer") if draft else [],
        "history_error": error, "switch_url": switch_url,
    }, status=status)


def get_version(pk):
    if not settings.READING_HUB_EDITOR_PILOT:
        raise Http404("The document editor pilot is disabled.")
    version = get_object_or_404(
        Rendition.objects.select_related("document", "snapshot"), pk=pk
    )
    try:
        adapter_for(version.document.url)
    except ImportFailure as exc:
        raise Http404("Edition unavailable in the active profile.") from exc
    return version


@require_GET
@metadata_reviewer_required
def retained_source(request, pk):
    source = get_version(pk)
    try:
        page = int(request.GET.get("page", "0"))
        values = request.GET.get("blocks")
        selection = None if values is None else [int(value) for value in values.split(",")]
        draft_id = request.GET.get("draft")
        draft = get_draft(draft_id, source) if draft_id else None
        if draft:
            saved_state(draft, 0)
        assets = (
            draft.evidence["assets"] if draft else
            source.assets.values_list("blob_id", flat=True)
        )
        if request.GET.get("original_section"):
            result = original_section(
                source, request.GET["original_section"], allowed_assets=assets,
            )
        else:
            result = source_page(source, page, selection, allowed_assets=assets)
    except (ValueError, ImportFailure, OSError) as exc:
        response = JsonResponse({"error": str(exc)}, status=422)
    else:
        response = JsonResponse(result)
    response["Cache-Control"] = "no-store"
    return response


@require_http_methods(["GET", "POST"])
@metadata_reviewer_required
def fresh_draft(request, pk):
    source = get_version(pk)
    values = request.POST if request.method == "POST" else request.GET
    mode = values.get("inputs", "reviewed")
    if mode not in {"original", "reviewed"}:
        return HttpResponse("Choose original or reviewed generation inputs.", status=422)
    original_source = mode == "original"
    proposal, error, status, switch_url = None, "", 200, None
    try:
        if request.method == "POST":
            if request.POST.get("confirm") != "yes":
                raise ValueError("Explicitly confirm starting a separate regenerated draft.")
            draft = create_fresh_draft(
                source, request.user, request.POST.get("preview_digest"),
                original_source=original_source,
            )
            switch_url = reverse("document-editor", args=[pk]) + f"?draft={draft.pk}"
            if not panel_context(request)["embedded"]:
                return redirect(switch_url)
        else:
            proposal = preview_fresh_draft(source, original_source=original_source)
    except DocumentEditConflict as exc:
        error, status = str(exc), 409
    except (ValueError, ImportFailure, OSError) as exc:
        error, status = str(exc), 422
    except OperationalError as exc:
        if "locked" not in str(exc).lower():
            raise
        error, status = "Another writer is active. Review a fresh preview and retry.", 409
    return panel_response(request, "library/document_fresh_draft.html", {
        "source": source, "proposal": proposal, "generation_error": error,
        "input_mode": mode, "original_source": original_source, "switch_url": switch_url,
    }, status=status)


@require_http_methods(["GET", "POST"])
@metadata_reviewer_required
def publication(request, pk):
    from library.services.document_metadata import metadata_rows
    from library.services.reading_styles import style_context
    from library.views import toc_tree

    source = get_version(pk)
    error, candidate, published, status = "", None, None, 200
    try:
        draft = get_draft(request.GET.get("draft"), source)
        values = request.POST if request.method == "POST" else request.GET
        revision = int(values.get("revision", ""))
        if request.method == "POST":
            if values.get("draft") and values["draft"] != str(draft.pk):
                raise ValueError("The submitted draft does not match the preview.")
            if values.get("confirm") != "yes":
                raise ValueError("Explicitly confirm publication of this saved revision.")
            result = publish_revision(
                draft, request.user, revision, values.get("preview_digest"),
            )
            if not panel_context(request)["embedded"]:
                return redirect("reader", pk=result.rendition_id)
            published = result
        else:
            candidate = prepare_publication(draft, revision)
            if request.GET.get("stylesheet") == "1":
                return HttpResponse(
                    candidate["output"]["stylesheet"], content_type="text/css; charset=utf-8",
                )
        reading_style = style_context(request)
    except DocumentEditConflict as exc:
        error, status = str(exc), 409
    except (ValueError, ImportFailure) as exc:
        error, status, candidate = str(exc), 422, None
    except OperationalError as exc:
        if "locked" not in str(exc).lower():
            raise
        error, status, candidate = (
            "Another writer is active. Reload the publication preview.", 409, None,
        )
    context = {"source": source, "publication_error": error, "published": published}
    if candidate or published:
        version = published.rendition if published else Rendition(
            document=source.document, snapshot=source.snapshot, **candidate["output"])
        context.update({
            **reading_style, "style_preview": True,
            "version": version, "candidate": candidate,
            "toc": toc_tree(version.structure["toc"]),
            "display_author": version.metadata.get("author", "").strip()
            or source_name(source.document.url),
            "metadata_rows": metadata_rows(version.metadata),
            "content_html": publication_view(
                version.html, version.structure["toc"],
            )["content_html"],
        })
    return panel_response(request, "library/document_publication.html", context, status=status)


def get_draft(value, version):
    try:
        identifier = uuid.UUID(value)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Choose a valid document draft.") from exc
    return get_object_or_404(
        DocumentDraftBase, pk=identifier, rendition=version, profile=get_profile().key,
    )


@require_GET
@metadata_reviewer_required
def baseline(request, pk):
    source = get_version(pk)
    try:
        draft = get_draft(request.GET.get("draft"), source)
        revision = int(request.GET.get("revision", ""))
        row = saved_state(draft, revision)
    except (ValueError, ImportFailure) as exc:
        response = JsonResponse({"error": str(exc)}, status=422)
    else:
        response = JsonResponse({
            "draft": str(draft.pk), "revision": revision,
            "document": row.document, "digest": row.document_digest,
        })
    response["Cache-Control"] = "no-store"
    return response


@require_GET
@metadata_reviewer_required
def comparison(request, pk):
    source = get_version(pk)
    try:
        draft = get_draft(request.GET.get("draft"), source)
        latest = draft.revisions.first()
        later = int(request.GET.get("to", latest.revision if latest else 0))
        earlier = int(request.GET.get("from", 0))
        if not 0 <= earlier <= later:
            raise ValueError(
                "Choose ordered, nonnegative revision numbers; zero is the draft base."
            )

        def document(number):
            if number == 0:
                return draft.document, draft
            row = get_object_or_404(draft.revisions, revision=number)
            return row.document, row

        before, before_row = document(earlier)
        after, after_row = document(later)
        result = compare_documents(before, after, request.GET.get("section", ""))
    except (ValueError, ImportFailure) as exc:
        return panel_response(request, "library/document_comparison.html", {
            "source": source, "comparison_error": str(exc),
        }, status=422)
    if request.GET.get("download") == "1":
        def state_info(number, row, value):
            return {
                "revision": number, "document": value,
                "document_digest": row.document_digest, "reviewer": row.reviewer_id,
                "created_at": row.created_at.isoformat(),
                "review": row.review if number else None,
                "verified_sections": row.verified_sections if number else [],
                "editorial": row.editorial if number else False,
                "lineage": row.lineage if number else draft.evidence.get("correction_origin"),
            }

        response = JsonResponse({
            "version": 1, "semantics": "saved_comparison_not_verified_training_pair",
            "draft": str(draft.pk), "source_rendition": source.pk,
            "profile": draft.profile, "evidence": draft.evidence,
            "selected_html_section": result["section"],
            "evidence_digest": draft.evidence_digest,
            "earlier": state_info(earlier, before_row, before),
            "later": state_info(later, after_row, after),
        }, json_dumps_params={"ensure_ascii": False, "indent": 2})
        response["Content-Disposition"] = 'attachment; filename="saved-document-comparison.json"'
    else:
        response = panel_response(request, "library/document_comparison.html", {
            "source": source, "draft": draft, "earlier": earlier, "later": later,
            "before": before, "after": after, "before_row": before_row, "after_row": after_row,
            "comparison": result,
        })
    response["Cache-Control"] = "no-store"
    return response


def save(request, version):
    if request.content_type != "application/json":
        return JsonResponse({"error": "Send an application/json document draft."}, status=400)
    if len(request.body) > MAX_BYTES + 65536:
        return JsonResponse({"error": "The draft request exceeds its size limit."}, status=413)
    try:
        value = json.loads(request.body)
        if not isinstance(value, dict) or set(value) != {
            "draft", "revision", "document", "conversion_approval",
            "review", "verified_sections", "editorial",
        }:
            raise ValueError(
                "Provide the draft, expected revision, document, review scope, verified "
                "sections, editorial flag and conversion approval."
            )
        with transaction.atomic():
            if value["draft"] is None:
                if type(value["revision"]) is not int or value["revision"] != 0:
                    raise ValueError("A new draft starts at revision zero.")
                draft = create_draft(
                    version, request.user, conversion_approval=value["conversion_approval"],
                )
            else:
                draft = get_draft(value["draft"], version)
                if value["conversion_approval"] is not None:
                    raise ValueError("A saved draft does not need another conversion approval.")
            row = save_revision(
                draft, request.user, value["document"], value["revision"],
                review=value["review"], verified_sections=value["verified_sections"],
                editorial=value["editorial"],
            )
    except DocumentEditConflict as exc:
        return JsonResponse({"error": str(exc)}, status=409)
    except (ValueError, UnicodeDecodeError, RecursionError, ImportFailure) as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    except OperationalError as exc:
        if "locked" not in str(exc).lower():
            raise
        return JsonResponse({
            "error": "Another writer is active. Retry saving this draft.",
        }, status=409)
    return JsonResponse({
        "draft": str(draft.pk), "revision": row.revision, "document": row.document,
        "issues": row.issues, "review": row.review,
        "verified_sections": row.verified_sections, "editorial": row.editorial,
    })
