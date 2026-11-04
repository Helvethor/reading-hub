import json
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from library.models import ContentOrganizationDecision, Rendition, SourceCorrection
from library.services.pipeline import format_rendition
from library.tests import test_organizations


class FormattingProfileTests(TestCase):
    setUp = test_organizations.OrganizationTests.setUp
    response = test_organizations.OrganizationTests.response

    def test_measures_real_retained_book_without_fetch_or_publication(self):
        before = {
            model: list(model.objects.values())
            for model in (Rendition, SourceCorrection, ContentOrganizationDecision)
        }
        output = StringIO()
        with patch(
            "library.services.fetch.Fetcher.fetch",
            side_effect=AssertionError("Network is forbidden"),
        ):
            call_command("profile_formatting", self.book.pk, runs=2, stdout=output)
        report = json.loads(output.getvalue())
        self.assertEqual(report["snapshot"], self.book.snapshot_id)
        self.assertEqual(len(report["runs"]), 2)
        self.assertEqual(len({run["output_digest"] for run in report["runs"]}), 1)
        for run in report["runs"]:
            self.assertGreaterEqual(run["elapsed_seconds"], 0)
            self.assertGreaterEqual(run["cpu_seconds"], 0)
            self.assertGreater(run["database_queries"], 0)
            self.assertGreaterEqual(run["database_execute_seconds"], 0)
            self.assertGreater(run["html_bytes"], 0)
            self.assertEqual(run["parts"], 3)
            self.assertEqual(
                set(run["stages_seconds"]),
                {
                    "prepare_pages_seconds",
                    "metadata_and_assets_seconds",
                    "normalize_seconds",
                    "stylesheet_seconds",
                },
            )
            self.assertTrue(all(value >= 0 for value in run["stages_seconds"].values()))
            self.assertLessEqual(sum(run["stages_seconds"].values()), run["elapsed_seconds"])
        for model, rows in before.items():
            self.assertEqual(list(model.objects.values()), rows)

    def test_stage_instrumentation_does_not_change_formatted_output(self):
        manifest = self.book.snapshot.manifest
        baseline = format_rendition(manifest, [])
        timings = {}
        with patch("library.services.pipeline.perf_counter", side_effect=[10, 12, 15, 20, 21]):
            measured = format_rendition(manifest, [], timings=timings)
        self.assertEqual(measured, baseline)
        self.assertEqual(
            timings,
            {
                "prepare_pages_seconds": 2,
                "metadata_and_assets_seconds": 3,
                "normalize_seconds": 5,
                "stylesheet_seconds": 1,
            },
        )
        self.assertNotIn("timings", measured[0].metadata)
        with patch("library.services.pipeline.perf_counter") as clock:
            self.assertEqual(format_rendition(manifest, []), baseline)
            clock.assert_not_called()

    def test_invalid_limits_missing_or_wrong_profile_fail(self):
        for runs in (0, -1, 6):
            with self.assertRaises(CommandError):
                call_command("profile_formatting", self.book.pk, runs=runs, stdout=StringIO())
        with self.assertRaisesMessage(CommandError, "not found"):
            call_command("profile_formatting", 999999, stdout=StringIO())
        Rendition.objects.filter(pk=self.book.pk).update(metadata={"profile": "another"})
        with self.assertRaisesMessage(CommandError, "active profile"):
            call_command("profile_formatting", self.book.pk, stdout=StringIO())

    def test_failure_is_explicit_and_unstable_output_is_rejected(self):
        with patch(
            "library.management.commands.profile_formatting.format_rendition",
            side_effect=OSError("Missing retained blob"),
        ):
            with self.assertRaisesMessage(CommandError, "Missing retained blob"):
                call_command("profile_formatting", self.book.pk, stdout=StringIO())
        with patch(
            "library.management.commands.profile_formatting.fingerprint",
            side_effect=["first", "second"],
        ):
            with self.assertRaisesMessage(CommandError, "Output changed"):
                call_command("profile_formatting", self.book.pk, runs=2, stdout=StringIO())
