from django.contrib.auth.decorators import login_required
from django.core import signing
from django.db import OperationalError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from library.metadata_views import metadata_reviewer_required
from library.models import Annotation, BookMembershipDecision, Document, Rendition
from library.profile import get_profile
from library.services.book_membership import (
    catalogue_book,
    commit_membership,
    decisions_for,
    preview_membership,
)
from library.services.errors import ImportFailure
from library.services.fetch import canonical_url
from library.services.organizations import member_destination
from library.sources.adapters import adapter_for

SALT = "catalogue-membership-v1"


def membership_root(version):
    entry = catalogue_book(version)
    if entry and entry.url != version.document.url:
        document = Document.objects.filter(url=entry.url).first()
        parent = document.latest() if document else None
        if parent:
            return parent
    return version


@require_http_methods(["GET", "POST"])
@metadata_reviewer_required
def editor_membership(request, pk):
    version = get_object_or_404(Rendition.objects.select_related("document", "snapshot"), pk=pk)
    try:
        adapter_for(version.document.url)
    except ImportFailure as exc:
        raise Http404("Work unavailable in the active profile.") from exc
    root = membership_root(version)
    if root.pk != version.pk:
        return redirect("document-editor-membership", pk=root.pk)
    book = catalogue_book(root)
    context = {"version": root, "book": book}
    try:
        if book is None:
            raise ValueError("Import this work into the catalogue before changing membership.")
        if request.method == "POST":
            reason = request.POST.get("reason", "").strip()
            action = request.POST.get("action", "")
            if action == "apply":
                payload = signing.loads(request.POST.get("token", ""), salt=SALT, max_age=1800)
                if (
                    payload["reviewer"] != request.user.pk
                    or payload["preview"]["book"] != book.pk
                    or payload["preview"]["profile"] != get_profile().key
                ):
                    raise ValueError("This preview belongs to another reviewer or catalogue work.")
                if request.POST.get("confirm") != "yes":
                    raise ValueError("Explicitly confirm this catalogue-wide routing change.")
                context["saved_decision"] = commit_membership(
                    payload["preview"], request.user, payload["reason"],
                )
            else:
                if not reason or len(reason) > 2000:
                    raise ValueError("Explain the membership change in 1-2000 characters.")
                undo = None
                url = request.POST.get("url", "")
                if action == "undo-preview":
                    undo = get_object_or_404(
                        BookMembershipDecision.objects.select_related("entry__site"),
                        pk=request.POST.get("decision"), entry__site__profile=get_profile().key,
                    )
                    if book.pk not in {undo.before["book"], undo.after["book"]}:
                        raise ValueError("Choose a decision affecting this catalogue work.")
                    url = undo.entry.url
                    action = "detach" if undo.before["book"] is None else "attach"
                result = preview_membership(book, url, action, undo=undo)
                context.update(preview=result, reason=reason)
                context["token"] = signing.dumps(
                    {"reviewer": request.user.pk, "reason": reason, "preview": result},
                    salt=SALT, compress=True,
                )
    except (ValueError, ImportFailure, OSError, signing.BadSignature) as exc:
        context["error"] = str(exc)
    except OperationalError as exc:
        if "locked" not in str(exc).lower():
            raise
        context["error"] = "Another writer is active. Nothing was saved; preview again."
    if book:
        context["members"] = book.chapters.order_by("url")
        context["decisions"] = decisions_for(book)
    response = render(
        request, "library/editor_membership.html", context,
        status=422 if context.get("error") else 200,
    )
    response["Cache-Control"] = "no-store"
    return response


@require_http_methods(["GET", "POST"])
@metadata_reviewer_required
def workspace(request):
    if request.method == "POST":
        return HttpResponse(
            "Ordered organization editing is retired. Use the catalogue membership page "
            "for ownership or the document editor for section order, titles and roles.",
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
            pk=request.GET["review_capture"], site__profile=get_profile().key,
        ).first()
        if capture:
            document = Document.objects.filter(url=capture.url).first()
            rendition = document.latest() if document else None
    if rendition is None:
        return redirect("work-review")
    return redirect("document-editor-membership", pk=membership_root(rendition).pk)


@require_GET
@login_required
def preserved_annotations(request):
    annotations = Annotation.objects.filter(owner=request.user).select_related(
        "rendition__document",
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
    route = "reader-pdf" if pdf else "reader"
    return redirect(reverse(route, args=[rendition.pk]) + ("#" + section if section else ""))
