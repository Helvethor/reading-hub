import json
from copy import deepcopy

from bs4 import BeautifulSoup, Tag
from django.contrib import messages
from django.core import signing
from django.core.paginator import Paginator
from django.db import OperationalError
from django.db.models import F, OuterRef, Subquery
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from library.metadata_views import metadata_reviewer_required
from library.models import CanonicalAuthor, CrawlCapture, Rendition, SourceCorrection
from library.profile import get_profile
from library.review_filters import REVIEW_LANGUAGES, correction_language_filter, review_language
from library.services.correction_datasets import (
    MAX_BYTES,
    MAX_RECORDS,
    commit_import,
    dataset,
    parse_dataset,
    prepare_import,
)
from library.services.corrections import (
    CorrectionConflict,
    apply_expected,
    baseline,
    block_rows,
    editable_nodes,
    extraction,
    latest,
    rendition_correction_sources,
    retain_rendition_capture,
    save_correction,
    validate_expected,
)
from library.services.errors import ImportFailure
from library.services.metadata_review import candidate_author_matches
from library.services.note_corrections import reference_rows
from library.services.page_types import classify, latest_decision
from library.sources.base import Source
from library.sources.normalize import normalize


@require_GET
@metadata_reviewer_required
def rendition_sources(request, pk):
    from library.organization_views import redirect_member

    rendition = get_object_or_404(Rendition.objects.select_related("document", "snapshot"), pk=pk)
    destination = redirect_member(rendition.document, version=rendition)
    if destination:
        return destination
    sources, error = [], ""
    try:
        sources = rendition_correction_sources(rendition)
    except (ValueError, ImportFailure, OSError) as exc:
        error = str(exc)
    return render(
        request,
        "library/reader_corrections.html",
        {"version": rendition, "correction_sources": sources, "correction_source_error": error},
        status=422 if error else 200,
    )


@require_POST
@metadata_reviewer_required
def rendition_source(request, pk):
    from library.organization_views import redirect_member

    rendition = get_object_or_404(Rendition.objects.select_related("document", "snapshot"), pk=pk)
    destination = redirect_member(rendition.document, version=rendition)
    if destination:
        return destination
    try:
        capture = retain_rendition_capture(rendition, int(request.POST.get("page", "")))
    except (ValueError, ImportFailure, OSError) as exc:
        messages.error(request, str(exc))
        return redirect("rendition-corrections", pk=rendition.pk)
    except OperationalError as exc:
        if "locked" not in str(exc).lower():
            raise
        messages.error(request, "Another writer is active. Retry opening the retained source.")
        return redirect("rendition-corrections", pk=rendition.pk)
    if request.POST.get("review_version") == str(rendition.pk):
        from django.urls import reverse

        return redirect(
            reverse("correction-workspace", args=[capture.pk]) + f"?review_version={rendition.pk}"
        )
    return redirect("correction-workspace", pk=capture.pk)


def capture_for_review(pk):
    capture = get_object_or_404(CrawlCapture.objects.select_related("site"), pk=pk)
    if capture.site.profile != get_profile().key:
        raise Http404("Switch to the capture's profile to review it.")
    return capture


@require_http_methods(["GET", "POST"])
@metadata_reviewer_required
def excerpts(request, pk):
    from library.services.source_excerpts import (
        definitions_for_capture,
        evidence,
        normalized_preview,
        revision_data,
        save_definition,
    )

    capture = capture_for_review(pk)
    try:
        entry = {**capture.response, "url": capture.url}
        if request.method == "POST":
            row = save_definition(capture, request.user, json.loads(request.body))
            return JsonResponse({"saved": revision_data(row),
                                 "definitions": definitions_for_capture(capture)})
        return JsonResponse({
            **evidence(entry),
            "html": normalized_preview(entry),
            "definitions": definitions_for_capture(capture),
            "history": [
                revision_data(row) for row in capture.excerpts.select_related(
                    "capture", "reviewer"
                ).order_by("-pk")
            ],
        })
    except (ValueError, ImportFailure, OSError) as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    except OperationalError as exc:
        if "locked" not in str(exc).lower():
            raise
        return JsonResponse(
            {"error": "Another writer is active. No revision saved; reload and retry."},
            status=409,
        )


@require_GET
@metadata_reviewer_required
def person_matches(request):
    query = request.GET.get("q", "").strip()
    if not query or len(query) > 500:
        return JsonResponse({"error": "Enter a person name of 1-500 characters."}, status=400)
    authors = list(CanonicalAuthor.objects.all())
    ranked = candidate_author_matches(query, authors=authors)
    candidates = [
        {"name": author.name, "authority_uri": author.authority_uri} for author, _ in ranked
    ]
    ids = {author.pk for author, _ in ranked}
    others = CanonicalAuthor.objects.filter(name__icontains=query).exclude(pk__in=ids)[:20]
    return JsonResponse(
        {
            "candidates": candidates,
            "others": [
                {"name": author.name, "authority_uri": author.authority_uri} for author in others
            ],
        }
    )


def preview(source, part, body, expected):
    from difflib import SequenceMatcher

    from library.services.presentation import inline_alignment, source_text
    from library.services.preview_blocks import mark_blocks, mark_unwrapped_text

    excerpt_blocks = body.__dict__.get("_excerpt_blocks", [])
    source, body = deepcopy(source), deepcopy(body)
    blocks, nodes = mark_blocks(body)
    for row, node in zip(blocks, nodes, strict=True):
        row["source_text"] = source_text(node)
        row["align"] = inline_alignment(node)
    for node, index in zip(nodes, excerpt_blocks, strict=False):
        if isinstance(node, Tag) and index is not None:
            node.__dict__["_reviewed_excerpt_block"] = index
    apply_expected(source, body, expected)
    # Wrap only surviving uncovered text after original-index operations resolve.
    soup = BeautifulSoup("", "html.parser")
    soup.append(body)
    mark_unwrapped_text(nodes, soup)
    # A page-level preview deliberately does not claim to assemble a complete book.
    page = Source(source.title, source.metadata, [part], False)
    html, structure = normalize([(part, body)], page, {}, review=True)
    inert = BeautifulSoup(html, "html.parser")
    for link in inert.select("a[href]"):
        del link["href"]
    for row in blocks:
        rendered = inert.select_one(f'[data-preview-block="{row["index"]}"]')
        text = rendered.get_text() if rendered else ""
        original_text = row["source_text"]
        mapping = [None] * len(text)
        def folded(value):
            return [char.lower() if len(char.lower()) == 1 else char for char in value]

        current, original_characters = folded(text), folded(original_text)
        if current == original_characters:
            row["text_map"] = list(range(len(text)))
            continue
        for match in SequenceMatcher(None, current, original_characters).get_matching_blocks():
            for offset in range(match.size):
                mapping[match.a + offset] = match.b + offset
        row["text_map"] = mapping
    html = str(inert)
    return {
        "title": source.title,
        "metadata": source.metadata,
        "html": html,
        "structure": structure,
        "blocks": blocks,
    }


@require_GET
@metadata_reviewer_required
def workspace(request, pk):
    capture = capture_for_review(pk)
    page_type = {
        "page_type_decision": latest_decision(capture.site, capture.url),
        "page_type_history": capture.site.page_type_decisions.filter(url=capture.url)[:10],
    }
    if capture.discovery_only:
        return render(request, "library/discovery_capture.html", {"capture": capture, **page_type})
    try:
        source, part, body, soup = extraction(capture, excerpt_mapping=True)
        current = latest(capture)
        from library.services.corrections import legacy_index_metadata

        original = baseline(source, body)
        stale = current and (
            current.adapter_version != get_profile().adapter_version
            or current.source_digest != capture.response["digest"]
            or (
                current.original["body_digest"] != original["body_digest"]
                and not legacy_index_metadata(current, body)
            )
        )
        expected = {} if current is None or stale else current.expected
        try:
            result = preview(source, part, body, expected)
        except ImportFailure as exc:
            from library.services.preview_blocks import mark_blocks

            result = {
                "title": source.title,
                "metadata": source.metadata,
                "html": "",
                "blocks": mark_blocks(deepcopy(body))[0],
                "error": f"Preview unavailable: {exc}. Repair the links below and preview again.",
            }
    except (ImportFailure, OSError, ValueError) as exc:
        return render(
            request,
            "library/corrections.html",
            {"capture": capture, "load_error": str(exc), **page_type},
            status=422,
        )
    return render(
        request,
        "library/corrections.html",
        {
            "capture": capture,
            **page_type,
            "current": current,
            "stale": stale,
            "source_text": soup.get_text(" ", strip=True),
            "source_html": str(soup),
            "original": original,
            "blocks": block_rows(body),
            "note_links": reference_rows(body, editable_nodes(body)),
            "expected": expected,
            "parsed_people": parsed_people(source.metadata),
            "preview": result,
            "metadata_only": source.book
            and not body.get_text(strip=True)
            and part not in source.parts,
            "revisions": capture.corrections.select_related("reviewer")[:20],
        },
    )


@require_POST
@metadata_reviewer_required
def page_type(request, pk):
    capture = capture_for_review(pk)
    try:
        classify(
            capture,
            request.user,
            request.POST.get("action", ""),
            request.POST.get("reason", ""),
            request.POST.get("revision", ""),
        )
    except (ValueError, ImportFailure, OSError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Page type updated for this URL and all retained captures.")
    if request.GET:
        from django.urls import reverse

        return redirect(
            reverse("correction-workspace", args=[capture.pk]) + "?" + request.GET.urlencode()
        )
    return redirect("correction-workspace", pk=capture.pk)


def parsed_people(metadata):
    contributors = metadata.get("contributors")
    if isinstance(contributors, list) and contributors:
        return [
            {
                "source_name": person.get("source_name") or person.get("name", ""),
                "name": person.get("name", ""),
                "role": person.get("role")
                if person.get("role") in {"author", "editor", "translator", "exclude", "unknown"}
                else "unknown",
            }
            for person in contributors
            if isinstance(person, dict) and person.get("name")
        ]
    if metadata.get("author_is_fallback"):
        return []
    names = metadata.get("authors") or [metadata.get("author", "")]
    if isinstance(names, str):
        names = [names]
    return [
        {"source_name": name, "name": name, "role": "unknown"}
        for name in names
        if isinstance(name, str) and name.strip()
    ]


def filtered_corrections(request):
    language = review_language(request)
    newest = SourceCorrection.objects.filter(capture_id=OuterRef("capture_id")).order_by(
        "-revision"
    )
    corrections = (
        SourceCorrection.objects.filter(profile=get_profile().key, capture__discovery_only=False)
        .annotate(newest_pk=Subquery(newest.values("pk")[:1]))
        .filter(pk=F("newest_pk"))
        .filter(correction_language_filter(language))
        .select_related("capture__site", "reviewer")
        .order_by("-created_at", "-pk")
    )
    source = request.GET.get("source", "").strip()[:253]
    if source:
        corrections = corrections.filter(capture__site__host=source)
    return corrections, language, source


@require_GET
@metadata_reviewer_required
def history(request):
    corrections, language, source = filtered_corrections(request)
    page = Paginator(corrections, 30).get_page(request.GET.get("page"))
    return render(
        request,
        "library/correction_history.html",
        {
            "page": page,
            "language": language,
            "languages": REVIEW_LANGUAGES,
            "source": source,
        },
    )


@require_GET
@metadata_reviewer_required
def dataset_export(request):
    corrections, _, _ = filtered_corrections(request)
    try:
        value = dataset(corrections.order_by("capture_id")[: MAX_RECORDS + 1])
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    response = JsonResponse(value, json_dumps_params={"ensure_ascii": False})
    response["Content-Disposition"] = 'attachment; filename="reading-hub-corrections.json"'
    return response


@require_http_methods(["GET", "POST"])
@metadata_reviewer_required
def dataset_import(request):
    context = {}
    status = 200
    if request.method == "POST":
        try:
            action = request.POST.get("action")
            if action == "preview":
                upload = request.FILES.get("dataset")
                if upload is None:
                    raise ValueError("Choose a correction dataset JSON file.")
                value = parse_dataset(upload.read(MAX_BYTES + 1))
                rows = prepare_import(value)
                # Sign exactly the inspected records and local revision baselines.
                # No server-side staging or database writes occur during preview.
                value["corrections"] = [row["record"] for row in rows]
                payload = {
                    "user": request.user.pk,
                    "profile": get_profile().key,
                    "dataset": value,
                    "bases": {str(row["capture"].pk): row["base_revision"] for row in rows},
                }
                context.update(
                    {
                        "rows": rows,
                        "token": signing.dumps(payload, salt="correction-dataset", compress=True),
                        "new_count": sum(not row["duplicate"] for row in rows),
                    }
                )
            elif action == "confirm":
                token = request.POST.get("token", "")
                if len(token) > MAX_BYTES * 2:
                    raise ValueError("Import preview is too large; upload fewer revisions.")
                payload = signing.loads(token, salt="correction-dataset", max_age=1800)
                if payload["user"] != request.user.pk or payload["profile"] != get_profile().key:
                    raise ValueError("This import preview belongs to another reviewer or profile.")
                created, skipped = commit_import(payload["dataset"], request.user, payload["bases"])
                context["success"] = (
                    f"Imported {created} new revisions; "
                    f"skipped {skipped} already imported revisions."
                )
            else:
                raise ValueError("Choose preview or confirm.")
        except signing.BadSignature:
            context["error"] = "Import preview is invalid or expired. Upload the dataset again."
        except (ValueError, ImportFailure, OSError) as exc:
            context["error"] = str(exc)
            status = 409 if isinstance(exc, CorrectionConflict) else 400
        if context.get("error") and status == 200:
            status = 400
    return render(
        request,
        "library/correction_dataset.html",
        context,
        status=status,
    )


@require_GET
@metadata_reviewer_required
def revisions(request, pk):
    capture = capture_for_review(pk)
    page = Paginator(capture.corrections.select_related("reviewer"), 20).get_page(
        request.GET.get("page")
    )
    return render(request, "library/correction_revisions.html", {"capture": capture, "page": page})


@require_POST
@metadata_reviewer_required
def update(request, pk):
    capture = capture_for_review(pk)
    if len(request.body) > 256_000:
        return JsonResponse({"error": "Correction exceeds the 256 KB limit."}, status=413)
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict) or set(data) - {"expected", "revision", "reason", "action"}:
            raise ValueError("Invalid correction request.")
        action = data.get("action")
        if not isinstance(action, str) or action not in {"preview", "save"}:
            raise ValueError("Choose preview or save.")
        expected = data.get("expected", {})
        reason = data.get("reason", "")
        if not isinstance(reason, str) or len(reason) > 4000:
            raise ValueError("Reason must contain at most 4000 characters.")
        source, part, body, _ = extraction(capture, excerpt_mapping=True)
        expected = validate_expected(expected, body, source)
        result = preview(source, part, body, expected)
        if action == "save":
            revision = data.get("revision")
            if type(revision) is not int or revision < 0:
                raise ValueError("Invalid base revision.")
            correction = save_correction(capture, request.user, expected, revision, reason)
            result["revision"] = correction.revision
        return JsonResponse(result)
    except CorrectionConflict as exc:
        return JsonResponse({"error": str(exc)}, status=409)
    except (ValueError, ImportFailure, OSError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)


@require_GET
@metadata_reviewer_required
def export(request, pk):
    capture = capture_for_review(pk)
    try:
        value = dataset(capture.corrections.select_related("capture")[: MAX_RECORDS + 1])
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    response = JsonResponse(
        value,
        json_dumps_params={"ensure_ascii": False},
    )
    response["Content-Disposition"] = (
        f'attachment; filename="capture-{capture.pk}-corrections.json"'
    )
    return response
