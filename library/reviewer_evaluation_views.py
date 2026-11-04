from django.conf import settings
from django.db import OperationalError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from library.document_editor_views import get_draft, get_version
from library.forms import ReviewerResultForm, ReviewerTaskForm
from library.metadata_views import metadata_reviewer_required
from library.models import ReviewerRun, ReviewerTask
from library.profile import get_profile
from library.services.document_edits import DocumentEditConflict
from library.services.errors import ImportFailure
from library.services.reviewer_evaluation import create_task, record_result, start_run


def enabled():
    if not settings.READING_HUB_EDITOR_PILOT:
        raise Http404("The document editor pilot is disabled.")


def page(request, context, status=200):
    response = render(request, "library/reviewer_evaluation.html", context, status=status)
    response["Cache-Control"] = "no-store"
    return response


@require_GET
@metadata_reviewer_required
def tasks(request):
    enabled()
    return page(request, {
        "tasks": ReviewerTask.objects.filter(
            starting_draft__profile=get_profile().key,
        ).select_related("starting_draft__rendition").order_by("-pk")[:50],
        "recent_runs": ReviewerRun.objects.filter(
            reviewer=request.user, draft__profile=get_profile().key,
        ).select_related("task", "result").order_by("-pk")[:20],
    })


@require_http_methods(["GET", "POST"])
@metadata_reviewer_required
def new_task(request, pk):
    source = get_version(pk)
    try:
        draft = get_draft(request.GET.get("draft"), source)
    except ValueError as exc:
        return page(request, {"error": str(exc)}, 422)
    form = ReviewerTaskForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            task = create_task(draft, request.user, **form.cleaned_data)
            return redirect("reviewer-task", pk=task.pk)
        except (ValueError, ImportFailure) as exc:
            form.add_error(None, str(exc))
        except OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            return page(request, {
                "task_form": form, "starting_draft": draft,
                "error": "Another writer is active. Retry saving the task.",
            }, 409)
    return page(request, {"task_form": form, "starting_draft": draft},
                422 if form.is_bound and form.errors else 200)


@require_http_methods(["GET", "POST"])
@metadata_reviewer_required
def task_detail(request, pk):
    enabled()
    task = get_object_or_404(
        ReviewerTask.objects.select_related("starting_draft__rendition__document"),
        pk=pk, starting_draft__profile=get_profile().key,
    )
    error, status = "", 200
    if request.method == "POST":
        try:
            if request.POST.get("mode") not in {"practice", "measured"}:
                raise ValueError("Choose practice or an evaluation run.")
            run = start_run(task, request.user, practice=request.POST["mode"] == "practice")
            return redirect("reviewer-run", pk=run.pk)
        except (ValueError, ImportFailure) as exc:
            error, status = str(exc), 422
        except OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            error, status = "Another writer is active. Retry starting the run.", 409
    return page(request, {"task": task, "error": error}, status)


@require_http_methods(["GET", "POST"])
@metadata_reviewer_required
def run_detail(request, pk):
    enabled()
    run = get_object_or_404(
        ReviewerRun.objects.select_related(
            "task__starting_draft", "draft__rendition__document", "reviewer",
        ), pk=pk, draft__profile=get_profile().key, reviewer=request.user,
    )
    result = getattr(run, "result", None)
    form = ReviewerResultForm(
        request.POST if request.method == "POST" else None, run=run,
    )
    error, status = "", 200
    if request.method == "POST":
        if result:
            error, status = (
                "This result is immutable. Start another run to make a new observation.", 409,
            )
        elif form.is_valid():
            values = dict(form.cleaned_data)
            number = values.pop("revision")
            try:
                record_result(run, request.user, number, values)
                return redirect("reviewer-run", pk=run.pk)
            except DocumentEditConflict as exc:
                error, status = str(exc), 409
            except (ValueError, ImportFailure) as exc:
                error, status = str(exc), 422
            except OperationalError as exc:
                if "locked" not in str(exc).lower():
                    raise
                error, status = "Another writer is active. Retry recording your result.", 409
        else:
            status = 422
    return page(request, {
        "run": run, "task": run.task, "result": result, "result_form": form,
        "error": error,
        "editor_url": reverse("document-editor", args=[run.draft.rendition_id])
        + f"?draft={run.draft_id}",
    }, status)
