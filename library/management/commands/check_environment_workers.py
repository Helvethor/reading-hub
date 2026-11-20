from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from library.services.environment_workers import read_supervisor_status


class Command(BaseCommand):
    help = "Check that the environment worker supervisor is running."

    def handle(self, *args, **options):
        status = read_supervisor_status()
        if (
            not settings.READING_HUB_AUTO_WORKERS
            or not status
            or status["expected_workers"] < 1
            or status["live_workers"] != status["expected_workers"]
        ):
            raise CommandError("The environment worker supervisor is not healthy.")
