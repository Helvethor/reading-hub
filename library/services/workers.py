import fcntl
import logging
import os
import resource
import subprocess
import sys
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path

from django.conf import settings
from django.db import transaction

from library.models import WorkerInstance, WorkerPool
from library.profile import get_profile

logger = logging.getLogger("library")
_children = {}
_thread_lock = threading.RLock()
ACTIVE = {"starting", "running", "stopping"}


class WorkerControlError(Exception):
    pass


def worker_directory():
    directory = settings.DATA_DIR / "workers"
    directory.mkdir(mode=0o700, exist_ok=True)
    return directory


@contextmanager
def control_lock():
    with _thread_lock, (worker_directory() / "control.lock").open("a") as file:
        fcntl.flock(file, fcntl.LOCK_EX)
        yield


def configured_pool():
    pool, _ = WorkerPool.objects.get_or_create(profile=get_profile().key)
    for number in range(1, pool.worker_count + 1):
        pool.workers.get_or_create(number=number, defaults={"memory_mib": pool.memory_mib})
    return pool


def process_identity(pid):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(") ", 1)[1].split()
        return None if fields[0] == "Z" else fields[19]
    except FileNotFoundError, ProcessLookupError:
        return None


def process_info(worker):
    if not worker.pid or not worker.token or process_identity(worker.pid) != worker.process_start:
        return None
    try:
        args = Path(f"/proc/{worker.pid}/cmdline").read_bytes().split(b"\0")
        if b"run_import_worker" not in args or str(worker.token).encode() not in args:
            return None
        pages = Path(f"/proc/{worker.pid}/statm").read_text().split()
        return {
            "rss": int(pages[1]) * os.sysconf("SC_PAGE_SIZE"),
            "virtual": int(pages[0]) * os.sysconf("SC_PAGE_SIZE"),
        }
    except FileNotFoundError, ProcessLookupError:
        return None


def reconcile(worker):
    child = _children.get(worker.pk)
    code = child.poll() if child else None
    if child and code is not None:
        del _children[worker.pk]
    info = process_info(worker)
    if not info and worker.status in ACTIVE:
        error = "Worker process exited unexpectedly. Inspect its log before restarting."
        if code is not None:
            error = f"Worker exited with code {code}. Inspect its log before restarting."
        WorkerInstance.objects.filter(pk=worker.pk, token=worker.token).update(
            status="failed",
            desired_running=False,
            restart_requested=False,
            activity="Process exited",
            error=error,
        )
        worker.refresh_from_db()
        from library.services.pipeline import fail_job

        for job in worker.jobs.filter(status="running"):
            fail_job(job, "Worker process exited. Inspect its log before retrying.", "interrupted")
    return info


def _start(worker):
    if reconcile(worker):
        if not worker.desired_running:
            raise WorkerControlError("Worker is stopping. Wait for it to finish before starting.")
        return
    with (settings.DATA_DIR / "worker.lock").open("a") as legacy:
        try:
            fcntl.flock(legacy, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise WorkerControlError(
                "An unmanaged command-line worker is running. Stop it before starting the pool."
            ) from exc
    token = uuid.uuid4()
    WorkerInstance.objects.filter(pk=worker.pk).update(
        token=token,
        status="starting",
        desired_running=True,
        restart_requested=False,
        pid=None,
        process_start="",
        error="",
        activity="Starting",
    )
    environment = {
        **os.environ,
        "READING_HUB_DATA": str(settings.DATA_DIR.resolve()),
        "READING_HUB_PROFILE": settings.READING_HUB_PROFILE,
        "DJANGO_SETTINGS_MODULE": os.environ.get("DJANGO_SETTINGS_MODULE", "config.settings"),
    }
    try:
        with (worker_directory() / f"{worker.pk}.log").open("ab", buffering=0) as log:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-u",
                    str(settings.BASE_DIR / "manage.py"),
                    "run_import_worker",
                    "--worker-id",
                    str(worker.pk),
                    "--token",
                    str(token),
                ],
                cwd=settings.BASE_DIR,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                close_fds=True,
                start_new_session=True,
            )
        _children[worker.pk] = process
        WorkerInstance.objects.filter(pk=worker.pk, token=token).update(
            pid=process.pid,
            process_start=process_identity(process.pid) or "",
        )
    except OSError as exc:
        logger.exception("Unable to start worker %s", worker.pk)
        WorkerInstance.objects.filter(pk=worker.pk, token=token).update(
            status="failed",
            desired_running=False,
            activity="Start failed",
            error=str(exc),
        )
        raise WorkerControlError(f"Unable to start worker: {exc}") from exc


def operate(action, worker_id=None):
    if action not in {"start", "stop", "restart"}:
        raise WorkerControlError("Unknown worker operation.")
    with control_lock():
        pool = configured_pool()
        workers = pool.workers.all()
        if worker_id is not None:
            workers = workers.filter(pk=worker_id)
            if not workers.exists():
                raise WorkerControlError("Unknown worker.")
        elif action != "stop":
            workers = workers.filter(number__lte=pool.worker_count)
        for worker in workers:
            if action != "stop" and worker.number > pool.worker_count:
                raise WorkerControlError("This worker is outside the configured pool.")
            live = reconcile(worker)
            if action == "stop":
                WorkerInstance.objects.filter(pk=worker.pk).update(
                    desired_running=False,
                    restart_requested=False,
                    status="stopping" if live else "stopped",
                    activity="Finishing current task" if live else "Stopped",
                )
            elif action == "restart" and live:
                WorkerInstance.objects.filter(pk=worker.pk).update(
                    desired_running=True,
                    restart_requested=True,
                    activity="Restart after current task",
                )
            else:
                _start(worker)


def validate_memory(memory_mib):
    if not 256 <= memory_mib <= 8192:
        raise WorkerControlError("Memory ceiling must be between 256 and 8192 MiB.")


def save_pool(worker_count, memory_mib):
    validate_memory(memory_mib)
    if not 1 <= worker_count <= 8:
        raise WorkerControlError("Worker count must be between 1 and 8.")
    with control_lock(), transaction.atomic():
        pool = configured_pool()
        pool.worker_count, pool.memory_mib = worker_count, memory_mib
        pool.save(update_fields=["worker_count", "memory_mib"])
        configured_pool()
        pool.workers.update(memory_mib=memory_mib)
        for worker in pool.workers.filter(number__gt=worker_count):
            live = process_info(worker)
            WorkerInstance.objects.filter(pk=worker.pk).update(
                desired_running=False,
                restart_requested=False,
                status="stopping" if live else "stopped",
                activity="Finishing current task" if live else "Stopped",
            )


def save_worker(worker_id, memory_mib):
    validate_memory(memory_mib)
    with control_lock():
        pool = configured_pool()
        if not pool.workers.filter(pk=worker_id).update(memory_mib=memory_mib):
            raise WorkerControlError("Unknown worker.")


def worker_rows():
    with control_lock():
        pool = configured_pool()
        rows = []
        for worker in pool.workers.order_by("number"):
            info = reconcile(worker)
            if worker.number > pool.worker_count and not info:
                continue
            job = worker.jobs.filter(status="running").select_related("document").first()
            rows.append(
                {
                    "worker": worker,
                    "live": bool(info),
                    "rss": info["rss"] if info else 0,
                    "virtual": info["virtual"] if info else 0,
                    "job": job,
                    "pending_memory": bool(info and worker.applied_memory_mib != worker.memory_mib),
                }
            )
        return pool, rows


def release_memory_limit():
    _, hard = resource.getrlimit(resource.RLIMIT_AS)
    resource.setrlimit(resource.RLIMIT_AS, (hard, hard))
