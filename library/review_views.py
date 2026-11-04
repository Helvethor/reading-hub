from django.conf import settings
from django.shortcuts import render
from django.views.decorators.http import require_GET

from library.metadata_views import metadata_reviewer_required
from library.review_navigation import navigation


@require_GET
@metadata_reviewer_required
def overview(request):
    return render(
        request,
        "library/work_review.html",
        {
            "review": navigation(request, {}),
            "editor_pilot": settings.READING_HUB_EDITOR_PILOT,
        },
    )
