import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from library.services.correction_benchmark import benchmark_report

MAX_MANIFEST_BYTES = 1024 * 1024


class Command(BaseCommand):
    help = "Validate a local, work-separated correction benchmark manifest offline."

    def add_arguments(self, parser):
        parser.add_argument("manifest", help="Path to a local JSON benchmark manifest.")

    def handle(self, *args, **options):
        path = Path(options["manifest"])
        try:
            with path.open("rb") as stream:
                raw = stream.read(MAX_MANIFEST_BYTES + 1)
        except OSError as exc:
            raise CommandError(f"Cannot read benchmark manifest: {exc}") from exc
        if len(raw) > MAX_MANIFEST_BYTES:
            raise CommandError("Benchmark manifest exceeds the 1 MiB limit.")
        try:
            manifest = json.loads(raw)
            report = benchmark_report(manifest)
        except (ValueError, UnicodeDecodeError, RecursionError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
