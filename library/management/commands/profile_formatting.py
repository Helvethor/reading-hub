import json
from statistics import median
from time import perf_counter, process_time

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from library.models import Rendition
from library.profile import get_profile
from library.services.errors import ImportFailure
from library.services.pipeline import fingerprint, format_rendition
from library.versions import APP_VERSION, FORMAT_VERSION


class Command(BaseCommand):
    help = "Measure offline formatting of a retained rendition without publishing or fetching."

    def add_arguments(self, parser):
        parser.add_argument("rendition", type=int)
        parser.add_argument("--runs", type=int, default=1, help="Formatting runs (1-5; default 1).")

    def handle(self, *args, **options):
        if not 1 <= options["runs"] <= 5:
            raise CommandError("--runs must be between 1 and 5.")
        try:
            rendition = Rendition.objects.select_related("snapshot", "document").get(
                pk=options["rendition"]
            )
        except Rendition.DoesNotExist as exc:
            raise CommandError("Retained rendition not found.") from exc
        profile = get_profile()
        if rendition.metadata.get("profile") != profile.key:
            raise CommandError("Select a rendition belonging to the active profile.")
        runs = []
        for _ in range(options["runs"]):
            queries = 0
            query_seconds = 0.0

            def measure(execute, sql, params, many, context):
                nonlocal queries, query_seconds
                queries += 1
                started = perf_counter()
                try:
                    return execute(sql, params, many, context)
                finally:
                    query_seconds += perf_counter() - started

            started, cpu = perf_counter(), process_time()
            stages = {}
            try:
                with connection.execute_wrapper(measure):
                    source, html, structure, stylesheet, warnings = format_rendition(
                        rendition.snapshot.manifest, [], timings=stages
                    )
            except (ValueError, ImportFailure, OSError) as exc:
                raise CommandError(f"Offline formatting failed: {exc}") from exc
            elapsed, cpu_elapsed = perf_counter() - started, process_time() - cpu
            output_digest = fingerprint(
                [html, structure, source.metadata, source.title, stylesheet]
            )
            runs.append(
                {
                    "elapsed_seconds": elapsed,
                    "cpu_seconds": cpu_elapsed,
                    "database_queries": queries,
                    "database_execute_seconds": query_seconds,
                    "stages_seconds": stages,
                    "html_bytes": len(html.encode()),
                    "parts": len(structure["parts"]),
                    "toc_entries": len(structure["toc"]),
                    "output_digest": output_digest,
                    "warnings": warnings,
                }
            )
        if len({run["output_digest"] for run in runs}) != 1:
            raise CommandError("Output changed between runs; timings are not comparable. Retry.")
        self.stdout.write(
            json.dumps(
                {
                    "rendition": rendition.pk,
                    "snapshot": rendition.snapshot_id,
                    "url": rendition.document.url,
                    "profile": profile.key,
                    "app_version": APP_VERSION,
                    "format_version": FORMAT_VERSION,
                    "adapter_version": profile.adapter_version,
                    "runs": runs,
                    "median_elapsed_seconds": median(run["elapsed_seconds"] for run in runs),
                    "limitations": [
                        "Retained snapshot bytes with current corrections and organization.",
                        "Does not reproduce the historical edition or publish a new one.",
                        "Excludes network, PDF, snapshot selection and publication transactions.",
                        "Query timing excludes some row fetching and Python materialization.",
                        "Stage elapsed times include their database execution time.",
                        "Same-process repeats may benefit from OS caches; no cold-cache claim.",
                        "Output stability is not parser accuracy or a concurrency guarantee.",
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
