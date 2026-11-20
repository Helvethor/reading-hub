import fcntl
import signal
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from library.services.environment_workers import (
    clear_supervisor_status,
    write_supervisor_status,
)
from library.services.workers import (
    WorkerControlError,
    configured_pool,
    operate,
    process_info,
    worker_rows,
)


class Command(BaseCommand):
    help = "Maintain the configured managed worker pool for a long-running environment."

    def handle(self, *args, **options):
        if not settings.READING_HUB_AUTO_WORKERS:
            raise CommandError("Automatic workers are disabled in this environment.")

        worker_directory = settings.DATA_DIR / "workers"
        worker_directory.mkdir(mode=0o700, exist_ok=True)
        with (worker_directory / "supervisor.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise CommandError("An environment worker supervisor is already running.") from exc

            stopping = False

            def request_stop(signum, frame):
                nonlocal stopping
                stopping = True

            signal.signal(signal.SIGTERM, request_stop)
            signal.signal(signal.SIGINT, request_stop)
            status = None
            try:
                status = self.start_pool()
                self.stdout.write("Environment worker supervisor ready")
                last_attempt = {}
                while not stopping:
                    pool, rows = worker_rows()
                    now = time.monotonic()
                    for row in rows:
                        worker = row["worker"]
                        if (
                            worker.status == "failed"
                            or (worker.started_at is None and not row["live"])
                        ) and now - last_attempt.get(worker.pk, 0) >= 10:
                            try:
                                operate("start", worker.pk)
                            except WorkerControlError as exc:
                                self.stderr.write(f"Worker {worker.number} restart failed: {exc}")
                            last_attempt[worker.pk] = now
                    live = sum(row["live"] for row in rows)
                    status = write_supervisor_status(
                        expected=pool.worker_count,
                        live=live,
                    )
                    time.sleep(2)
            finally:
                try:
                    operate("stop")
                    self.wait_for_workers_to_stop()
                finally:
                    if status:
                        clear_supervisor_status(status)

    def start_pool(self):
        pool = configured_pool()
        for worker in pool.workers.filter(number__lte=pool.worker_count):
            operate("start", worker.pk)
        for worker in pool.workers.filter(number__gt=pool.worker_count):
            if process_info(worker):
                operate("stop", worker.pk)

        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            _, rows = worker_rows()
            if rows and all(row["live"] for row in rows):
                return write_supervisor_status(
                    expected=pool.worker_count,
                    live=len(rows),
                )
            time.sleep(0.2)
        raise CommandError("The configured worker pool did not become ready.")

    def wait_for_workers_to_stop(self):
        while True:
            _, rows = worker_rows()
            if not any(row["live"] for row in rows):
                return
            time.sleep(0.5)
