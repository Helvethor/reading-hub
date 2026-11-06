import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.db import OperationalError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from library.metadata_views import metadata_reviewer_required
from library.models import (
    Annotation,
    ContentOrganizationDecision,
    Document,
    Rendition,
)
from library.profile import get_profile
from library.services.errors import ImportFailure
from library.services.fetch import canonical_url
from library.services.organizations import (
    change_plan,
    commit_change,
    current_spec,
    entries,
    member_destination,
    preview_change,
    undo_plan,
)
from library.sources.adapters import adapter_for

SALT = "content-organization-v1"


def membership_root(version):
    entry = (
        entries()
        .filter(url=version.document.url)
        .select_related("book")
        .first()
    )
    if entry and entry.book_id:
        document = Document.objects.filter(url=entry.book.url).first()
        parent = document.latest() if document else None
        if parent:
            return parent
    return version


def _membership_decisions(root_url):
    rows = ContentOrganizationDecision.objects.filter(profile=get_profile().key).select_related(
        "reviewer", "undo_of"
    ).order_by("-created_at", "-pk")[:100]
    relevant = []
    for decision in rows:
        affected = {
            spec["url"]
            for spec in (*decision.before, *decision.after)
        } | {
            part["url"]
            for spec in (*decision.before, *decision.after)
            for part in spec["parts"]
        }
        if root_url in affected:
            relevant.append(decision)
        if len(relevant) == 30:
            break
    return relevant


def _decision_affects_url(decision, url):
    return any(
        spec["url"] == url or any(part["url"] == url for part in spec["parts"])
        for spec in (*decision.before, *decision.after)
    )


def _membership_context(request, version):
    root = membership_root(version)
    context = {
        "version": root,
        "embedded": request.GET.get("embedded") == "1",
        "panel_base": (
            "library/embedded_panel_base.html"
            if request.GET.get("embedded") == "1"
            else "library/base.html"
        ),
        "decisions": _membership_decisions(root.document.url),
    }
    return root, context


@require_http_methods(["GET", "POST"])
@metadata_reviewer_required
def editor_membership(request, pk):
    if not settings.READING_HUB_EDITOR_PILOT:
        raise Http404("The document editor pilot is disabled.")
    version = get_object_or_404(
        Rendition.objects.select_related("document", "snapshot"), pk=pk
    )
    try:
        adapter_for(version.document.url)
    except ImportFailure as exc:
        raise Http404("Edition unavailable in the active profile.") from exc

    root, context = _membership_context(request, version)
    if root.pk != version.pk:
        query = "?embedded=1" if context["embedded"] else ""
        return redirect(reverse("document-editor-membership", args=[root.pk]) + query)

    try:
        if request.method == "GET":
            spec = current_spec(root.document.url)
            context["specification"] = json.dumps(spec, indent=2, ensure_ascii=False)
        elif request.POST.get("action") == "apply":
            payload = signing.loads(request.POST.get("token", ""), salt=SALT, max_age=1800)
            if (
                payload.get("reviewer") != request.user.pk
                or payload.get("profile") != get_profile().key
                or payload.get("edition") != root.pk
            ):
                raise ValueError("This preview belongs to another reviewer, profile or edition.")
            if request.POST.get("preserve_annotations") != "yes":
                raise ValueError("Explicitly acknowledge the private annotation handling policy.")
            undo = (
                get_object_or_404(ContentOrganizationDecision, pk=payload.get("undo"))
                if payload.get("undo")
                else None
            )
            decision = commit_change(payload, request.user, payload["reason"], undo_of=undo)
            context["saved_decision"] = decision
            context["saved_renditions"] = [
                (url, rendition_id)
                for url, rendition_id in decision.evidence["renditions"].items()
            ]
            spec = current_spec(root.document.url)
            context["specification"] = json.dumps(spec, indent=2, ensure_ascii=False)
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
                if not _decision_affects_url(undo, root.document.url):
                    raise ValueError("Choose an organization decision affecting this work.")
                before, after = undo_plan(undo)
                context["specification"] = json.dumps(after[0], indent=2, ensure_ascii=False)
            elif request.POST.get("action") == "preview":
                before, after = change_plan(json.loads(context["specification"]))
            else:
                raise ValueError("Choose Preview or Preview undo.")
            result = preview_change(before, after, undo_of=undo)
            context["preview"] = result
            context["token"] = signing.dumps(
                {
                    "reviewer": request.user.pk,
                    "profile": get_profile().key,
                    "edition": root.pk,
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
    response = render(
        request,
        "library/editor_membership.html",
        context,
        status=422 if context.get("error") else 200,
    )
    if context["embedded"]:
        response.editor_panel = True
    response["Cache-Control"] = "no-store"
    return response


@require_http_methods(["GET", "POST"])
@metadata_reviewer_required
def workspace(request):
    if request.method == "POST":
        return HttpResponse(
            "Standalone organization editing is retired. "
            "Use the edition's editor membership panel.",
            status=410,
        )
    rendition = None
    version_id = request.GET.get("review_version")
    if version_id and version_id.isdecimal():
        rendition = Rendition.objects.select_related("document").filter(pk=version_id).first()
    if rendition is None and request.GET.get("url"):
        try:
            url = canonical_url(request.GET["url"])
        except ValueError:
            url = ""
        document = Document.objects.filter(url=url).first() if url else None
        rendition = document.latest() if document else None
    if rendition is None and request.GET.get("review_capture", "").isdecimal():
        from library.models import CrawlCapture

        capture = CrawlCapture.objects.filter(
            pk=request.GET["review_capture"], site__profile=get_profile().key
        ).first()
        if capture:
            document = Document.objects.filter(url=capture.url).first()
            rendition = document.latest() if document else None
    if rendition is None:
        return redirect("work-review")
    if not settings.READING_HUB_EDITOR_PILOT:
        return HttpResponse(
            "Standalone organization editing is retired, and the document editor "
            "is currently disabled.",
            status=503,
        )
    root = membership_root(rendition)
    target = reverse("document-editor-membership", args=[root.pk])
    if request.GET.get("embedded") == "1":
        target += "?embedded=1"
    response = redirect(target)
    if request.GET.get("embedded") == "1":
        response.editor_panel = True
    return response


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
