import fcntl
import os
import resource
import sys
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections
from django.utils import timezone
from django.utils.module_loading import import_string

from library.models import CatalogueWorker, CrawlSite, WorkerInstance
from library.profile import get_profile
from library.services.catalogue import configured_sites, crawl_step, recover_crawls
from library.services.pipeline import claim_job, fail_job, process_job, recover_interrupted
from library.services.workers import process_identity, release_memory_limit, worker_directory


class Command(BaseCommand):
    help = "Run a worker. Use the web controls for managed pools; --once runs one maintenance step."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")
        parser.add_argument("--worker-id", type=int)
        parser.add_argument("--token")

    def handle(self, *args, **options):
        if not settings.READING_HUB_ALLOW_WORKERS:
            raise CommandError("Workers are disabled in this isolated environment.")
        worker = None
        if options["worker_id"] is not None:
            worker = WorkerInstance.objects.filter(
                pk=options["worker_id"],
                token=options["token"],
                pool__profile=get_profile().key,
                desired_running=True,
            ).first()
            if not worker:
                raise CommandError("Worker start request is no longer valid.")
        with (settings.DATA_DIR / "worker.lock").open("a") as legacy:
            try:
                fcntl.flock(legacy, (fcntl.LOCK_SH if worker else fcntl.LOCK_EX) | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise CommandError(
                    "An import worker is already running for this data directory."
                ) from exc
            if not worker:
                self.run_loop(None, options["once"])
                return
            with (worker_directory() / f"{worker.pk}.lock").open("a") as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as exc:
                    raise CommandError("This worker is already running.") from exc
                try:
                    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
                    limit = worker.memory_mib * 1024**2
                    if hard != resource.RLIM_INFINITY and limit > hard:
                        raise CommandError("Configured memory exceeds the inherited OS hard limit.")
                    resource.setrlimit(resource.RLIMIT_AS, (limit, hard))
                    WorkerInstance.objects.filter(pk=worker.pk, token=worker.token).update(
                        pid=os.getpid(),
                        process_start=process_identity(os.getpid()),
                        started_at=timezone.now(),
                        applied_memory_mib=worker.memory_mib,
                        status="running",
                        error="",
                        activity="Idle",
                    )
                    restart = self.run_loop(worker, options["once"])
                except Exception as exc:
                    release_memory_limit()
                    WorkerInstance.objects.filter(pk=worker.pk, token=worker.token).update(
                        status="failed",
                        desired_running=False,
                        restart_requested=False,
                        error=f"{type(exc).__name__}: {exc}",
                        activity="Worker failed",
                    )
                    for job in worker.jobs.filter(status="running"):
                        fail_job(
                            job, "Worker failed. Inspect its log before retrying.", "worker_failed"
                        )
                    raise
                finally:
                    resource.setrlimit(resource.RLIMIT_AS, (soft, hard))
            if restart:
                os.execv(
                    sys.executable,
                    [
                        sys.executable,
                        "-u",
                        str(settings.BASE_DIR / "manage.py"),
                        "run_import_worker",
                        "--worker-id",
                        str(worker.pk),
                        "--token",
                        str(worker.token),
                    ],
                )

    def run_loop(self, worker, once):
        self.stdout.write("Import worker ready")
        configured_sites()
        self.corpus = None
        self.recovered_sites = set()
        self.cursor = worker.number - 1 if worker else 0
        try:
            while True:
                close_old_connections()
                now = timezone.now()
                if worker:
                    worker.refresh_from_db()
                    if not worker.desired_running or worker.restart_requested:
                        restart = worker.desired_running and worker.restart_requested
                        WorkerInstance.objects.filter(pk=worker.pk, token=worker.token).update(
                            status="starting" if restart else "stopped",
                            restart_requested=False,
                            activity="Restarting" if restart else "Stopped",
                        )
                        return restart
                    WorkerInstance.objects.filter(pk=worker.pk, token=worker.token).update(
                        heartbeat=now,
                        activity="Looking for work",
                    )
                CatalogueWorker.objects.update_or_create(
                    profile=get_profile().key, defaults={"heartbeat": now}
                )
                recover_interrupted()
                job = claim_job(worker)
                worked = waiting = False
                if job:
                    self.stdout.write(f"Processing {job.pk}: {job.document.url}")
                    process_job(job)
                else:
                    worked, waiting = self.background_step(worker)
                if once:
                    return False
                if not job and not worked:
                    self.activity(
                        worker,
                        "Waiting for a free crawl / sampling slot"
                        if waiting
                        else "Idle: no enabled background work",
                    )
                    time.sleep(2)
        finally:
            if self.corpus:
                self.corpus.close()

    def activity(self, worker, stage):
        if worker:
            WorkerInstance.objects.filter(pk=worker.pk).update(
                heartbeat=timezone.now(),
                activity=stage[:250],
            )

    def background_step(self, worker):
        profile = get_profile()
        tasks = (
            list(
                CrawlSite.objects.filter(
                    profile=profile.key,
                    host__in=[s.host for s in profile.sources],
                    enabled=True,
                )
                .order_by("pk")
                .values_list("pk", "host")
            )
            if profile.catalogue_enabled
            else []
        )
        if profile.corpus_service:
            tasks.append((None, "Archive sampling"))
        if not tasks:
            return False, False
        # Shared during rolling upgrades; legacy workers hold this exclusively.
        with (settings.DATA_DIR / "background.lock").open("a") as compatibility:
            try:
                fcntl.flock(compatibility, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except BlockingIOError:
                return False, True
            waiting = False
            start = self.cursor % len(tasks)
            for offset in range(len(tasks)):
                index = (start + offset) % len(tasks)
                site_id, label = tasks[index]
                filename = f"crawl-{site_id}.lock" if site_id is not None else "sampling.lock"
                with (settings.DATA_DIR / filename).open("a") as lane:
                    try:
                        fcntl.flock(lane, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        waiting = True
                        continue
                    self.activity(worker, f"Processing {label}")
                    if site_id is None:
                        if self.corpus is None:
                            self.corpus = import_string(profile.corpus_service)()
                            if hasattr(self.corpus, "progress"):
                                self.corpus.progress = lambda stage: self.activity(
                                    worker, f"Archive sampling: {stage}"
                                )
                        worked = self.corpus.step()
                    else:
                        recover_crawls(
                            site_id=site_id,
                            clear_fetchers=site_id not in self.recovered_sites,
                        )
                        self.recovered_sites.add(site_id)
                        worked = crawl_step(
                            site_id=site_id,
                            progress=lambda stage, label=label: self.activity(
                                worker, f"{label}: {stage}"
                            ),
                        )
                    self.cursor = (index + 1) % len(tasks)
                    if worked:
                        return True, False
            return False, waiting
