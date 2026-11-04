import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.db import OperationalError
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from library.metadata_views import metadata_reviewer_required
from library.models import Annotation, ContentOrganizationDecision, Rendition
from library.profile import get_profile
from library.services.document_edits import preview_rendition_import
from library.services.errors import ImportFailure
from library.services.fetch import canonical_url
from library.services.organizations import (
    change_plan,
    commit_change,
    current_spec,
    entries,
    member_destination,
    preview_change,
    retained_manifest,
    stored_source,
    undo_plan,
)

SALT = "content-organization-v1"


def section_candidates(url):
    from library.services.storage import read_blob
    from library.sources.base import parse_html
    from library.sources.index_sections import sections

    if not stored_source(url).book:
        return []
    manifest, _ = retained_manifest({"url": url, "parts": []})
    entry = manifest["pages"][0]
    soup = parse_html(read_blob(entry["digest"]), entry.get("headers", {}))
    return [
        {
            "url": part.url,
            "title": part.title,
            "role": part.role,
            "section": part.section,
            "use_source_headings": part.use_source_headings,
        }
        for part, _ in sections(soup, url)
    ]


@require_http_methods(["GET", "POST"])
@metadata_reviewer_required
def workspace(request):
    if request.method == "GET" and request.GET.get("source_evidence") == "1":
        try:
            from library.services.source_excerpts import (
                definitions_for_entry,
                evidence,
                select_excerpt,
            )

            url = canonical_url(request.GET.get("source_url", ""))
            manifest, _ = retained_manifest({"url": url, "parts": []})
            entry = manifest["pages"][0]
            result = evidence(entry)
            result["definitions"] = definitions_for_entry(entry)
            if "start" in request.GET and "end" in request.GET:
                selection = {
                    "version": 1,
                    "source_digest": request.GET.get("source_digest", ""),
                    "start": int(request.GET["start"]),
                    "end": int(request.GET["end"]),
                }
                body = select_excerpt(entry, selection)
                result["selection"] = selection
                result["text"] = body.get_text("\n", strip=True)
            return JsonResponse(result)
        except (ValueError, ImportFailure, OSError) as exc:
            return JsonResponse({"error": str(exc)}, status=422)
    context = {
        "decisions": ContentOrganizationDecision.objects.filter(
            profile=get_profile().key
        ).select_related("reviewer", "undo_of")[:30],
    }
    try:
        if request.method == "GET":
            url = canonical_url(request.GET.get("url", ""))
            member = entries().filter(url=url, book__isnull=False).select_related("book").first()
            if member:
                url = member.book.url
            spec = current_spec(url)
            context["specification"] = json.dumps(spec, indent=2, ensure_ascii=False)
            context["section_candidates"] = section_candidates(url)
        elif request.POST.get("action") == "apply":
            payload = signing.loads(request.POST.get("token", ""), salt=SALT, max_age=1800)
            if payload["reviewer"] != request.user.pk or payload["profile"] != get_profile().key:
                raise ValueError("This preview belongs to another reviewer or profile.")
            if request.POST.get("preserve_annotations") != "yes":
                raise ValueError("Explicitly acknowledge the private annotation handling policy.")
            undo = (
                get_object_or_404(ContentOrganizationDecision, pk=payload["undo"])
                if payload["undo"]
                else None
            )
            decision = commit_change(payload, request.user, payload["reason"], undo_of=undo)
            source_url = payload["before"][0]["url"]
            target_spec = next(
                (spec for spec in payload["after"] if spec["url"] == source_url),
                None,
            )
            if target_spec is None:
                target_spec = next(
                    (
                        spec for spec in payload["after"]
                        if any(part["url"] == source_url for part in spec["parts"])
                    ),
                    None,
                )
            rendition_id = (
                decision.evidence["renditions"].get(target_spec["url"])
                if target_spec else None
            )
            editor_url, editor_limitation = None, None
            if settings.READING_HUB_EDITOR_PILOT:
                if rendition_id:
                    rendition = get_object_or_404(Rendition, pk=rendition_id)
                    try:
                        preview_rendition_import(rendition)
                    except (ValueError, ImportFailure) as exc:
                        editor_limitation = (
                            "The document editor cannot open this edition yet: " + str(exc)
                        )
                    else:
                        editor_url = (
                            reverse("document-editor", args=[rendition_id]) + "?start=source"
                        )
                else:
                    editor_limitation = (
                        "The organization change was saved, but no resulting editor edition "
                        "was identified."
                    )
            return render(
                request,
                "library/organization_saved.html",
                {
                    "decision": decision,
                    "url": payload["after"][0]["url"],
                    "editor_url": editor_url,
                    "editor_limitation": editor_limitation,
                },
            )
        else:
            reason = request.POST.get("reason", "").strip()
            context["reason"] = reason
            context["specification"] = request.POST.get("specification", "")
            if not reason or len(reason) > 2000:
                raise ValueError("Explain the organization decision in 1-2000 characters.")
            undo = None
            if request.POST.get("action") == "undo-preview":
                undo = get_object_or_404(
                    ContentOrganizationDecision,
                    pk=request.POST.get("decision"),
                    profile=get_profile().key,
                )
                before, after = undo_plan(undo)
                context["specification"] = json.dumps(after[0], indent=2, ensure_ascii=False)
                context["section_candidates"] = section_candidates(after[0]["url"])
            elif request.POST.get("action") == "preview":
                before, after = change_plan(json.loads(context["specification"]))
                context["section_candidates"] = section_candidates(after[0]["url"])
            else:
                raise ValueError("Choose Preview or Preview undo.")
            result = preview_change(before, after, undo_of=undo)
            context["preview"] = result
            context["token"] = signing.dumps(
                {
                    "reviewer": request.user.pk,
                    "profile": get_profile().key,
                    "reason": reason,
                    "before": before,
                    "after": after,
                    "revision": result["revision"],
                    "digests": [work["digest"] for work in result["works"]],
                    "undo": undo.pk if undo else None,
                },
                salt=SALT,
                compress=True,
            )
    except (ValueError, ImportFailure, OSError, signing.BadSignature) as exc:
        context["error"] = str(exc)
    except OperationalError as exc:
        if "locked" not in str(exc).lower():
            raise
        context["error"] = "Another writer is active. No partial change was saved; preview again."
    if context.get("specification"):
        try:
            from library.services.source_excerpts import definitions_for_entry

            spec = json.loads(context["specification"])
            manifest, _ = retained_manifest(spec)
            context["excerpt_definitions"] = [
                item for entry in manifest["pages"] for item in definitions_for_entry(entry)
            ]
        except (ValueError, ImportFailure, OSError, KeyError, TypeError) as exc:
            context["excerpt_definition_error"] = str(exc)
    return render(
        request,
        "library/organization.html",
        context,
        status=422 if context.get("error") else 200,
    )


@require_GET
@login_required
def preserved_annotations(request):
    annotations = Annotation.objects.filter(owner=request.user).select_related(
        "rendition__document"
    )
    return render(request, "library/preserved_annotations.html", {"annotations": annotations})


def redirect_member(document, *, version=None, stylesheet=False, pdf=False):
    if version is not None and hasattr(version, "document_publication"):
        return None
    try:
        target = member_destination(document, version)
    except ImportFailure as exc:
        raise Http404(str(exc)) from exc
    if target is None:
        return None
    rendition, section = target
    if stylesheet:
        return redirect("reader-css", pk=rendition.pk)
    if pdf:
        from django.urls import reverse

        return redirect(reverse("reader-pdf", args=[rendition.pk]) + "#" + section)
    from django.urls import reverse

    return redirect(reverse("reader", args=[rendition.pk]) + "#" + section)
