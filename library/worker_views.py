import logging

from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from library.account_views import administrator_required
from library.forms import WorkerMemoryForm, WorkerPoolForm
from library.models import WorkerInstance
from library.profile import get_profile
from library.services.catalogue import configured_sites
from library.services.workers import (
    WorkerControlError,
    operate,
    save_pool,
    save_worker,
    worker_directory,
    worker_rows,
)

logger = logging.getLogger("library")


def queues():
    return (
        configured_sites().annotate(
            pending_count=Count("frontier", filter=Q(frontier__status="pending"))
        )
        if get_profile().catalogue_enabled
        else []
    )


def context(pool_form=None, invalid_worker=None, memory_form=None, error=""):
    pool, rows = worker_rows()
    for row in rows:
        worker = row["worker"]
        row["form"] = (
            memory_form
            if worker.pk == invalid_worker and memory_form is not None
            else WorkerMemoryForm(
                initial={"memory_mib": worker.memory_mib}, prefix=f"worker-{worker.pk}"
            )
        )
    return {
        "pool": pool,
        "rows": rows,
        "control_error": error,
        "pool_form": pool_form
        or WorkerPoolForm(
            initial={"worker_count": pool.worker_count, "memory_mib": pool.memory_mib}
        ),
        "queues": queues(),
    }


@require_GET
@administrator_required
def controls(request):
    return render(request, "library/workers.html", context())


@require_POST
@administrator_required
def control(request, pk=None):
    if pk is not None:
        get_object_or_404(WorkerInstance, pk=pk, pool__profile=get_profile().key)
    action = request.POST.get("action")
    pool_form = memory_form = None
    error = ""
    try:
        if action == "save":
            if pk is None:
                pool_form = WorkerPoolForm(request.POST)
                if pool_form.is_valid():
                    save_pool(**pool_form.cleaned_data)
                    return redirect("worker-controls")
            else:
                memory_form = WorkerMemoryForm(request.POST, prefix=f"worker-{pk}")
                if memory_form.is_valid():
                    save_worker(pk, **memory_form.cleaned_data)
                    return redirect("worker-controls")
        else:
            operate(action, pk)
            return redirect("worker-controls")
    except WorkerControlError as exc:
        error = str(exc)
    except OSError as exc:
        logger.exception("Worker control failed")
        error = f"Unable to control worker processes: {exc}"
    return render(
        request,
        "library/workers.html",
        context(pool_form, pk, memory_form, error),
        status=400,
    )


@require_GET
@administrator_required
def status(request):
    _, rows = worker_rows()
    return JsonResponse(
        {
            "workers": [
                {
                    "id": row["worker"].pk,
                    "status": row["worker"].status,
                    "live": row["live"],
                    "pid": row["worker"].pid if row["live"] else None,
                    "rss": row["rss"],
                    "activity": (row["job"].stage if row["job"] else row["worker"].activity),
                    "error": row["worker"].error,
                    "heartbeat": row["worker"].heartbeat.isoformat()
                    if row["worker"].heartbeat
                    else "",
                    "pending_memory": row["pending_memory"],
                    "applied_memory_mib": row["worker"].applied_memory_mib,
                    "restart_requested": row["worker"].restart_requested,
                }
                for row in rows
            ],
            "queues": [
                {
                    "id": site.pk,
                    "status": site.status,
                    "enabled": site.enabled,
                    "pending": site.pending_count,
                    "pages": site.pages,
                    "max_pages": site.max_pages,
                    "error": site.error,
                }
                for site in queues()
            ],
        }
    )


@require_GET
@administrator_required
def log(request, pk):
    get_object_or_404(WorkerInstance, pk=pk, pool__profile=get_profile().key)
    path = worker_directory() / f"{pk}.log"
    try:
        with path.open("rb") as file:
            file.seek(0, 2)
            file.seek(max(0, file.tell() - 16384))
            text = file.read().decode("utf-8", errors="replace")
    except FileNotFoundError:
        text = "No process log yet. This worker has not been started."
    return HttpResponse(text, content_type="text/plain; charset=utf-8")
