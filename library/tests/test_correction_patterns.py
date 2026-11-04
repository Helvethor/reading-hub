import json
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from library.models import CatalogueEntry, CrawlCapture, SourceCorrection
from library.services.correction_patterns import correction_patterns, current_compatibility
from library.services.corrections import save_correction
from library.tests import test_corrections


class CorrectionPatternTests(TestCase):
    setUp = test_corrections.CorrectionTests.setUp

    def save(self, capture=None, revision=0, expected=None):
        return save_correction(
            capture or self.capture,
            self.reviewer,
            expected if expected is not None else {"blocks": [{"index": 0, "action": "exclude"}]},
            revision,
            "Pattern example",
        )

    def test_latest_revision_and_duplicate_capture_are_not_independent_examples(self):
        first = self.save()
        self.save(revision=1)
        duplicate = CrawlCapture.objects.create(
            site=self.capture.site, url=self.capture.url, response=self.capture.response
        )
        self.save(duplicate)
        report = correction_patterns(first.profile)
        self.assertEqual(report["revisions"], 3)
        self.assertEqual(report["active_captures"], 2)
        self.assertEqual(report["independent_corrected_examples"], 1)
        self.assertEqual(report["groups"][0]["operation_count"], 1)

    def test_current_compatibility_is_opt_in_and_preserves_records(self):
        correction = self.save()
        before = list(SourceCorrection.objects.values())
        output = StringIO()
        with patch("library.services.correction_patterns.extraction") as extract:
            call_command("correction_patterns", stdout=output)
            extract.assert_not_called()
        self.assertNotIn("current_compatibility", json.loads(output.getvalue()))
        output = StringIO()
        call_command("correction_patterns", check_current=True, stdout=output)
        report = json.loads(output.getvalue())["current_compatibility"]
        self.assertEqual(report["checked"], 1)
        self.assertEqual(report["remaining"], 0)
        self.assertEqual(report["status_counts"], {"compatible": 1})
        self.assertEqual(report["results"][0]["correction"], correction.pk)
        self.assertEqual(list(SourceCorrection.objects.values()), before)

    def test_compatibility_reports_binding_changes_without_extraction(self):
        correction = self.save()
        SourceCorrection.objects.filter(pk=correction.pk).update(
            adapter_version="old-adapter", source_digest="0" * 64
        )
        with patch("library.services.correction_patterns.extraction") as extract:
            result = current_compatibility(correction.profile)["results"][0]
            extract.assert_not_called()
        self.assertEqual(result["status"], "needs_revalidation")
        self.assertEqual(
            result["reasons"], ["Retained source digest changed.", "Adapter version changed."]
        )

    def test_compatibility_reports_changed_body_and_missing_source(self):
        correction = self.save()
        original = {**correction.original, "body_digest": "0" * 64}
        SourceCorrection.objects.filter(pk=correction.pk).update(original=original)
        report = current_compatibility(correction.profile)
        self.assertEqual(report["results"][0]["status"], "needs_revalidation")
        self.assertEqual(report["results"][0]["reasons"], ["Extracted body changed."])
        with patch(
            "library.services.correction_patterns.extraction",
            side_effect=OSError("Retained blob is missing"),
        ):
            result = current_compatibility(correction.profile)["results"][0]
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["reasons"], ["Retained blob is missing"])

    def test_compatibility_limits_newest_captures_and_skips_reset_and_future_schema(self):
        correction = self.save()
        self.save(revision=1, expected={})
        duplicate = CrawlCapture.objects.create(
            site=self.capture.site, url=self.capture.url, response=self.capture.response
        )
        future = self.save(duplicate)
        SourceCorrection.objects.filter(pk=future.pk).update(schema_version=999)
        with patch("library.services.correction_patterns.extraction") as extract:
            report = current_compatibility(correction.profile, limit=1)
            self.assertEqual(report["total"], 2)
            self.assertEqual(report["remaining"], 1)
            self.assertEqual(report["status_counts"], {"reset": 1})
            full = current_compatibility(correction.profile)
            extract.assert_not_called()
        self.assertEqual(full["status_counts"], {"reset": 1, "unsupported": 1})
        self.assertEqual(full["checked"], 2)

    def test_compatibility_rejects_bad_limits_and_unexpected_failures_propagate(self):
        correction = self.save()
        for limit in (0, -1, 1001):
            with self.assertRaises(ValueError):
                current_compatibility(correction.profile, limit=limit)
            with self.assertRaises(CommandError):
                call_command(
                    "correction_patterns", check_current=True, limit=limit, stdout=StringIO()
                )
        with self.assertRaisesMessage(ValueError, "active profile"):
            current_compatibility("another-profile")
        with patch(
            "library.services.correction_patterns.extraction",
            side_effect=RuntimeError("Unexpected programming failure"),
        ):
            with self.assertRaises(RuntimeError):
                current_compatibility(correction.profile)

    def test_compatibility_surfaces_invalid_operations_not_success(self):
        correction = self.save()
        SourceCorrection.objects.filter(pk=correction.pk).update(
            expected={"blocks": [{"index": 99999, "action": "exclude"}]}
        )
        result = current_compatibility(correction.profile)["results"][0]
        self.assertEqual(result["status"], "unavailable")
        self.assertTrue(result["reasons"])

    def test_reset_removes_historical_operations_from_pattern_counts(self):
        first = self.save()
        self.save(revision=1, expected={})
        report = correction_patterns(first.profile)
        self.assertEqual(report["active_resets"], 1)
        self.assertEqual(report["groups"], [])
        self.assertEqual(SourceCorrection.objects.count(), 2)

    def test_multiple_operations_per_example_and_distinct_work_counts(self):
        first = self.save(
            expected={
                "blocks": [{"index": 0, "action": "exclude"}, {"index": 1, "action": "exclude"}]
            }
        )
        second = CrawlCapture.objects.create(
            site=self.capture.site, url=self.capture.url + "part/", response=self.capture.response
        )
        self.save(second)
        book = CatalogueEntry.objects.create(
            site=self.capture.site, url=self.capture.url, title="Work"
        )
        CatalogueEntry.objects.create(
            site=self.capture.site, url=second.url, title="Part", book=book
        )
        report = correction_patterns(first.profile)
        self.assertEqual(report["independent_corrected_examples"], 2)
        self.assertEqual(sum(g["operation_count"] for g in report["groups"]), 3)
        self.assertTrue(all(g["works"] == 1 for g in report["groups"]))
        for group in report["groups"]:
            self.assertEqual(len(group["work_breakdown"]), 1)
            work = group["work_breakdown"][0]
            self.assertEqual(work["url"], book.url)
            self.assertEqual(work["operation_count"], group["operation_count"])
            self.assertEqual(work["independent_examples"], group["independent_examples"])
            self.assertEqual(work["source_urls"], group["source_urls"])
        self.assertEqual(correction_patterns("different-profile")["groups"], [])

    def test_unknown_schema_is_reported_not_treated_as_verified_evidence(self):
        first = self.save()
        SourceCorrection.objects.filter(pk=first.pk).update(schema_version=999)
        report = correction_patterns(first.profile)
        self.assertEqual(report["unsupported"], [{"correction": first.pk, "schema": 999}])
        self.assertEqual(report["groups"], [])

    def test_command_emits_json_and_preserves_records(self):
        self.save(expected={"metadata": {"topics": []}})
        before = list(SourceCorrection.objects.values())
        output = StringIO()
        call_command("correction_patterns", stdout=output)
        report = json.loads(output.getvalue())
        self.assertEqual(report["groups"][0]["operation"], "metadata:topics")
        self.assertEqual(list(SourceCorrection.objects.values()), before)
        self.assertTrue(report["limitations"])

    def test_recurring_operations_group_across_layouts_and_keep_breakdown(self):
        first = self.save()
        second = CrawlCapture.objects.create(
            site=self.capture.site,
            url=self.capture.url + "different/",
            response=self.capture.response,
        )
        other = self.save(second)
        original = other.original
        original["blocks"].append({"index": 999, "tag": "hr", "text": "Divider"})
        SourceCorrection.objects.filter(pk=other.pk).update(original=original)
        groups = correction_patterns(first.profile)["groups"]
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["source_urls"], 2)
        self.assertEqual(groups[0]["works"], 2)
        self.assertEqual(len(groups[0]["layout_proxies"]), 2)

    def test_conflicting_duplicate_answers_are_reported_and_not_counted(self):
        first = self.save()
        duplicate = CrawlCapture.objects.create(
            site=self.capture.site, url=self.capture.url, response=self.capture.response
        )
        second = self.save(duplicate, expected={"metadata": {"topics": []}})
        report = correction_patterns(first.profile)
        self.assertEqual(report["conflicting_examples"], 1)
        self.assertEqual(report["independent_corrected_examples"], 0)
        self.assertEqual(report["groups"], [])
        conflict = report["conflicts"][0]
        self.assertEqual(conflict["url"], self.capture.url)
        self.assertEqual(conflict["source_digest"], first.source_digest)
        self.assertEqual(
            [review["correction"] for review in conflict["reviews"]], [first.pk, second.pk]
        )
        self.assertTrue(all(not review["reset"] for review in conflict["reviews"]))

    def test_reset_conflict_is_not_silently_used_as_positive_or_negative_evidence(self):
        first = self.save()
        duplicate = CrawlCapture.objects.create(
            site=self.capture.site, url=self.capture.url, response=self.capture.response
        )
        self.save(duplicate, expected={})
        report = correction_patterns(first.profile)
        self.assertEqual(report["active_resets"], 1)
        self.assertEqual(report["conflicting_examples"], 1)
        self.assertTrue(report["conflicts"][0]["reviews"][-1]["reset"])
        self.assertEqual(report["groups"], [])
        self.save(revision=1, expected={})
        report = correction_patterns(first.profile)
        self.assertEqual(report["active_resets"], 2)
        self.assertEqual(report["conflicts"], [])
        self.assertEqual(report["groups"], [])

    def test_superseding_conflict_restores_single_deduplicated_example(self):
        first = self.save()
        duplicate = CrawlCapture.objects.create(
            site=self.capture.site, url=self.capture.url, response=self.capture.response
        )
        self.save(duplicate, expected={"metadata": {"topics": []}})
        self.save(duplicate, revision=1)
        report = correction_patterns(first.profile)
        self.assertEqual(report["conflicts"], [])
        self.assertEqual(report["independent_corrected_examples"], 1)
        self.assertEqual(report["groups"][0]["operation_count"], 1)

    def test_distinct_work_breakdown_does_not_treat_chapters_as_held_out_works(self):
        first = self.save()
        other_capture = CrawlCapture.objects.create(
            site=self.capture.site, url=self.capture.url + "other/", response=self.capture.response
        )
        self.save(other_capture)
        report = correction_patterns(first.profile)
        group = report["groups"][0]
        self.assertEqual(group["works"], 2)
        self.assertEqual(
            [work["url"] for work in group["work_breakdown"]],
            sorted([self.capture.url, other_capture.url]),
        )
        self.assertTrue(all(work["independent_examples"] == 1 for work in group["work_breakdown"]))
