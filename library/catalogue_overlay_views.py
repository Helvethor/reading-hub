from django.contrib import messages
from django.core import signing
from django.db import OperationalError
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from library.correction_views import capture_for_review
from library.metadata_views import metadata_reviewer_required
from library.models import CatalogueOverlayDecision
from library.profile import get_profile
from library.services.catalogue_overlays import binding, commit, proposal
from library.services.corrections import CorrectionConflict
from library.services.errors import ImportFailure

SALT = "catalogue-overlay-v1"


@require_http_methods(["GET", "POST"])
@metadata_reviewer_required
def workspace(request, pk):
    capture = capture_for_review(pk)
    plan, token, error, status = None, "", "", 200
    undo = request.GET.get("action") == "undo"
    reason = request.POST.get("reason", "")
    if request.method == "POST":
        try:
            signed = signing.loads(request.POST.get("token", ""), salt=SALT, max_age=1800)
            if (
                signed["user"] != request.user.pk
                or signed["profile"] != get_profile().key
                or signed["capture"] != capture.pk
            ):
                raise ValueError("This preview belongs to another reviewer, profile or capture.")
            if request.POST.get("action") != "confirm":
                raise ValueError("Choose confirmation after preview.")
            commit(capture, request.user, signed["plan"], reason)
            messages.success(
                request, "Catalogue overlay decision saved. Reader versions are unchanged."
            )
            from django.urls import reverse

            destination = reverse("catalogue-overlay", args=[pk])
            query = request.GET.copy()
            query.pop("action", None)
            return redirect(destination + ("?" + query.urlencode() if query else ""))
        except signing.BadSignature:
            error, status = "Preview is invalid or expired. Reload and preview again.", 400
        except CorrectionConflict as exc:
            error, status = str(exc), 409
        except (ValueError, ImportFailure, OSError) as exc:
            error, status = str(exc), 400
        except OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            error, status = "Another writer is active. Reload the preview before retrying.", 409
    try:
        plan = proposal(capture, undo=undo)
        token = signing.dumps(
            {
                "user": request.user.pk,
                "profile": get_profile().key,
                "capture": capture.pk,
                "plan": binding(plan),
            },
            salt=SALT,
            compress=True,
        )
    except (ValueError, ImportFailure, OSError) as exc:
        if not error:
            error = str(exc)
    history = CatalogueOverlayDecision.objects.filter(
        entry__site=capture.site, entry__url=capture.url
    ).select_related("reviewer", "correction")[:30]
    return render(
        request,
        "library/catalogue_overlay.html",
        {
            "capture": capture,
            "plan": plan,
            "token": token,
            "error": error,
            "history": history,
            "undo": undo,
            "reason": reason,
        },
        status=status,
    )
