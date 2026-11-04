import json

from django.core.management.base import BaseCommand, CommandError

from library.profile import get_profile
from library.services.correction_patterns import correction_patterns, current_compatibility


class Command(BaseCommand):
    help = "Report recurring saved correction patterns as JSON, without fetching or changing data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--check-current",
            action="store_true",
            help="Also check newest reviews against current retained-source extraction.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Maximum captures to check with --check-current (1-1000; default 100).",
        )

    def handle(self, *args, **options):
        if not 1 <= options["limit"] <= 1000:
            raise CommandError("--limit must be between 1 and 1000.")
        report = correction_patterns(get_profile().key)
        if options["check_current"]:
            report["current_compatibility"] = current_compatibility(
                get_profile().key, limit=options["limit"]
            )
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
