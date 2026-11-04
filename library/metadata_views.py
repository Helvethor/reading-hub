from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from library.models import CanonicalAuthor, MetadataSuggestion
from library.profile import get_profile
from library.review_filters import REVIEW_LANGUAGES, review_language, suggestion_language_filter
from library.services.errors import ImportFailure
from library.services.metadata_review import (
    candidate_author_matches,
    review_suggestion,
    scoped_author_correction,
)


def metadata_reviewer_required(view):
    @wraps(view)
    def guarded(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not request.user.is_staff and not request.user.has_perm("library.review_metadata"):
            raise PermissionDenied("Metadata reviewer access required.")
        return view(request, *args, **kwargs)

    return guarded


def review_url(request):
    query = request.GET.urlencode()
    return f"/metadata/review/?{query}" if query else "/metadata/review/"


@require_GET
@metadata_reviewer_required
def metadata_review(request):
    status = request.GET.get("status", MetadataSuggestion.Status.PENDING)
    field = request.GET.get("field", "")
    if status not in MetadataSuggestion.Status.values:
        raise Http404("Unknown metadata review status.")
    if field and field not in MetadataSuggestion.Field.values:
        raise Http404("Unknown metadata suggestion field.")
    language = review_language(request)
    capture = None
    if request.GET.get("review_capture"):
        from library.correction_views import capture_for_review

        value = request.GET["review_capture"]
        if not value.isdecimal():
            raise Http404("Invalid reviewer source.")
        capture = capture_for_review(int(value))
    suggestions = (
        MetadataSuggestion.objects.filter(status=status)
        .filter(
            Q(entry__site__profile=get_profile().key)
            | Q(capture__site__profile=get_profile().key)
            | Q(entry__isnull=True, capture__isnull=True)
        )
        .filter(suggestion_language_filter(language))
        .select_related("entry__site", "capture__site", "reviewed_by")
        .prefetch_related("review_events__reviewer", "review_events__correction")
    )
    if status == MetadataSuggestion.Status.PENDING:
        suggestions = suggestions.exclude(
            Q(capture__discovery_only=True) | Q(entry__discovery_only=True)
        )
    if field:
        suggestions = suggestions.filter(field=field)
    if capture:
        suggestions = suggestions.filter(
            Q(capture__url=capture.url, capture__site=capture.site)
            | Q(entry__url=capture.url, entry__site=capture.site)
        )
    source = request.GET.get("source", "").strip()[:253]
    if source:
        suggestions = suggestions.filter(
            Q(entry__site__host=source) | Q(capture__site__host=source)
        )
    page = Paginator(suggestions.order_by("created_at", "pk"), 30).get_page(request.GET.get("page"))
    authors = list(CanonicalAuthor.objects.all())
    for suggestion in page:
        suggestion.scoped_correction = scoped_author_correction(suggestion)
        if suggestion.scoped_correction:
            suggestion.corrected_people = suggestion.scoped_correction.expected["metadata"][
                "people"
            ]
            correction = suggestion.scoped_correction
            suggestion.correction_stale = (
                correction.source_digest != suggestion.capture.response.get("digest")
                or correction.adapter_version != get_profile().adapter_version
            )
        suggestion.author_matches = (
            candidate_author_matches(suggestion.value, authors=authors)
            if suggestion.field == MetadataSuggestion.Field.AUTHOR
            else []
        )
        suggested_ids = {author.pk for author, _ in suggestion.author_matches}
        suggestion.other_authors = [author for author in authors if author.pk not in suggested_ids]
    return render(
        request,
        "library/metadata_review.html",
        {
            "page": page,
            "capture": capture,
            "status": status,
            "field": field,
            "source": source,
            "statuses": MetadataSuggestion.Status.choices,
            "fields": MetadataSuggestion.Field.choices,
            "language": language,
            "languages": REVIEW_LANGUAGES,
        },
    )


@require_POST
@metadata_reviewer_required
def metadata_review_decision(request, pk):
    suggestion = get_object_or_404(
        MetadataSuggestion.objects.filter(
            Q(entry__site__profile=get_profile().key)
            | Q(capture__site__profile=get_profile().key)
            | Q(entry__isnull=True, capture__isnull=True)
        ),
        pk=pk,
    )
    action = request.POST.get("action", "")
    wants_json = request.headers.get("Accept") == "application/json"
    try:
        changed = review_suggestion(
            suggestion,
            action,
            request.user,
            author_id=request.POST.get("author_id", ""),
            canonical_name=request.POST.get("canonical_name", ""),
            authority_uri=request.POST.get("authority_uri", ""),
            reason=request.POST.get("reason", ""),
            correction_id=request.POST.get("correction_id", ""),
        )
    except (CanonicalAuthor.DoesNotExist, ValueError, ImportFailure, OSError) as exc:
        error = str(exc) or "The selected author identity is unavailable."
        if wants_json:
            return JsonResponse({"error": error}, status=400)
        messages.error(request, error)
    else:
        if wants_json:
            suggestion.refresh_from_db()
            author = None
            if suggestion.field == MetadataSuggestion.Field.AUTHOR:
                link = suggestion.links.select_related("author").first()
                if link:
                    author = {"id": link.author_id, "name": link.author.name}
                elif changed and action == "approve":
                    if request.POST.get("author_id"):
                        person = CanonicalAuthor.objects.get(pk=request.POST["author_id"])
                    else:
                        name = request.POST.get("canonical_name", "").strip() or suggestion.value
                        person = CanonicalAuthor.objects.get(name=name[:500])
                    author = {"id": person.pk, "name": person.name}
            return JsonResponse({"changed": changed, "status": suggestion.status, "author": author})
        if changed:
            messages.success(request, "Metadata decision recorded.")
        else:
            messages.info(request, "This suggestion was already reviewed.")
    return redirect(review_url(request))
