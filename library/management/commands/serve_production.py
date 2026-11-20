import signal
import subprocess
import sys
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from library.services.environment_workers import read_supervisor_status


class Command(BaseCommand):
    help = "Run the production worker supervisor and web server as one service."

    def handle(self, *args, **options):
        if settings.READING_HUB_ENVIRONMENT != "production":
            raise CommandError("This service command is only available in production.")

        stopping = False

        def request_stop(signum, frame):
            nonlocal stopping
            stopping = True

        signal.signal(signal.SIGTERM, request_stop)
        signal.signal(signal.SIGINT, request_stop)
        worker_supervisor = subprocess.Popen(
            [sys.executable, "manage.py", "manage_environment_workers"],
            stdin=subprocess.DEVNULL,
        )
        web = None
        failure = None
        try:
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                if worker_supervisor.poll() is not None:
                    raise CommandError(
                        "The production worker supervisor exited before becoming ready."
                    )
                status = read_supervisor_status()
                if status and status["pid"] == worker_supervisor.pid:
                    break
                time.sleep(0.2)
            else:
                raise CommandError("The production worker supervisor did not become ready.")

            web = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "gunicorn",
                    "--bind",
                    "0.0.0.0:8000",
                    "--workers",
                    "1",
                    "--access-logfile",
                    "-",
                    "config.production_wsgi:application",
                ],
                stdin=subprocess.DEVNULL,
            )
            while not stopping:
                if worker_supervisor.poll() is not None:
                    failure = "The production worker supervisor exited unexpectedly."
                    break
                if web.poll() is not None:
                    failure = f"The production web server exited with status {web.returncode}."
                    break
                time.sleep(0.2)
        finally:
            if worker_supervisor.poll() is None:
                worker_supervisor.send_signal(signal.SIGTERM)
                worker_supervisor.wait()
            if web and web.poll() is None:
                web.send_signal(signal.SIGTERM)
                try:
                    web.wait(timeout=60)
                except subprocess.TimeoutExpired as exc:
                    web.kill()
                    raise CommandError(
                        "The production web server did not stop gracefully within 60 seconds."
                    ) from exc
        if failure:
            raise CommandError(failure)
