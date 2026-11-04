import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from library.models import CorrectionFeedback, CrawlCapture
from library.services.correction_benchmark import benchmark_report
from library.services.correction_feedback import record_verified_heading_keep
from library.services.corrections import block_rows, extraction, save_correction
from library.services.fetch import Response
from library.services.storage import save_response
from library.tests import test_corrections
from library.tests.test_sources import article_html


class CorrectionFeedbackTests(TestCase):
    setUp = test_corrections.CorrectionTests.setUp
    edits = test_corrections.CorrectionTests.edits

    def heading_index(self, capture):
        _, _, body, _ = extraction(capture)
        return next(row["index"] for row in block_rows(body) if row["tag"].startswith("h"))

    def other_capture(self):
        url = self.capture.url + "?benchmark=held-out"
        return CrawlCapture.objects.create(
            site=self.capture.site,
            url=url,
            response=save_response(
                Response(url, article_html("<p>Independent held-out prose.</p>"), "text/html", {}),
                url,
            ),
        )

    def same_body_different_source_capture(self):
        url = self.capture.url + "?benchmark=duplicate-body"
        return CrawlCapture.objects.create(
            site=self.capture.site,
            url=url,
            response=save_response(
                Response(
                    url,
                    article_html("<p>Unwanted block</p>", title="Different page metadata"),
                    "text/html",
                    {},
                ),
                url,
            ),
        )

    def manifest(self, second=None):
        examples = [
            {
                "capture_id": self.capture.pk,
                "work_key": "development-work",
                "split": "development",
                "layout_key": "article-v1",
            }
        ]
        if second is not None:
            examples.append(
                {
                    "capture_id": second.pk,
                    "work_key": "held-out-work",
                    "split": "held_out",
                    "layout_key": "article-v2",
                }
            )
        return {"format_version": 1, "task": "block-type", "examples": examples}

    def test_direct_correction_saves_emit_bound_operation_labels(self):
        index = self.heading_index(self.capture)
        expected = {
            "blocks": [{"index": index, "action": "h3"}],
            "metadata": {"title": "Reviewed title"},
        }
        correction = save_correction(self.capture, self.reviewer, expected, 0, "Correct heading")
        labels = list(CorrectionFeedback.objects.filter(correction=correction))
        operation = f"block-type:{index}"
        self.assertEqual({row.operation for row in labels}, {operation})
        heading = next(row for row in labels if row.operation == operation)
        self.assertEqual(heading.decision, CorrectionFeedback.Decision.CORRECTION)
        self.assertEqual(heading.value, expected["blocks"][0])
        self.assertEqual(heading.correction_revision, 1)
        self.assertEqual(heading.source_digest, self.capture.response["digest"])
        self.assertEqual(heading.body_digest, correction.original["body_digest"])
        with self.assertRaisesMessage(ValueError, "append-only"):
            heading.save()
        with self.assertRaisesMessage(ValueError, "append-only"):
            heading.delete()
        with self.assertRaisesMessage(ValueError, "append-only"):
            CorrectionFeedback.objects.filter(pk=heading.pk).update(value={})
        with self.assertRaisesMessage(ValueError, "append-only"):
            CorrectionFeedback.objects.filter(pk=heading.pk).delete()

    def test_removed_operations_are_superseded_and_reset_is_explicit(self):
        expected = self.edits()
        heading = next(edit for edit in expected["blocks"] if edit["action"] != "exclude")
        heading["action"] = "h3"
        correction = save_correction(
            self.capture, self.reviewer, expected, 0, "Initial correction"
        )
        reset = save_correction(self.capture, self.reviewer, {}, 1, "Restore source")
        rows = list(CorrectionFeedback.objects.filter(capture=self.capture))
        reset_event = next(
            row
            for row in rows
            if row.correction_id == reset.pk and row.decision == CorrectionFeedback.Decision.RESET
        )
        superseded = [
            row for row in rows if row.correction_id == reset.pk and row.decision == "superseded"
        ]
        self.assertEqual(reset_event.operation, "block-type:*")
        self.assertEqual(reset_event.decision, CorrectionFeedback.Decision.RESET)
        self.assertTrue(superseded)
        self.assertTrue(all(row.correction_revision == reset.revision for row in superseded))
        self.assertEqual(correction.feedback_events.count(), 1)

    def test_no_op_block_type_selection_is_not_mislabeled_as_a_correction(self):
        index = self.heading_index(self.capture)
        save_correction(
            self.capture,
            self.reviewer,
            {"blocks": [{"index": index, "action": "h4"}]},
            0,
            "No-op type selection",
        )
        self.assertFalse(
            CorrectionFeedback.objects.filter(
                capture=self.capture, decision=CorrectionFeedback.Decision.CORRECTION
            ).exists()
        )

    def test_verified_keep_requires_an_explicit_reason_and_exact_source_target(self):
        index = self.heading_index(self.capture)
        label = record_verified_heading_keep(
            self.capture, self.reviewer, index, "Checked heading against source."
        )
        self.assertEqual(label.operation, f"block-type:{index}")
        self.assertEqual(label.decision, CorrectionFeedback.Decision.VERIFIED_KEEP)
        self.assertEqual(label.value["tag"], block_rows(extraction(self.capture)[2])[index]["tag"])
        self.assertEqual(label.correction_revision, 0)
        self.assertEqual(label.reason, "Checked heading against source.")
        with self.assertRaisesMessage(ValueError, "requires a reason"):
            record_verified_heading_keep(self.capture, self.reviewer, index, " ")
        with self.assertRaisesMessage(ValueError, "existing source block"):
            record_verified_heading_keep(self.capture, self.reviewer, 10000, "Checked")
        self.assertEqual(CorrectionFeedback.objects.count(), 1)

    def test_benchmark_reports_labels_and_unknowns_without_metrics(self):
        save_correction(
            self.capture,
            self.reviewer,
            {"blocks": [{"index": self.heading_index(self.capture), "action": "h3"}]},
            0,
            "Correct heading",
        )
        second = self.other_capture()
        record_verified_heading_keep(
            second, self.reviewer, self.heading_index(second), "Checked independently."
        )
        report = benchmark_report(self.manifest(second))
        self.assertEqual(report["metrics_status"], "not_evaluated_no_candidate_predictions")
        self.assertEqual(report["splits"]["development"]["labels"], {"explicit_corrections": 1})
        self.assertEqual(report["splits"]["held_out"]["labels"], {"verified_keeps": 1})
        self.assertEqual(report["splits"]["development"]["work_breakdown"][0]["labels"], {
            "explicit_corrections": 1
        })
        self.assertEqual(
            report["splits"]["held_out"]["captures_with_adjudicated_block_type_labels"], 1
        )

    def test_benchmark_rejects_work_layout_and_duplicate_evidence_leakage(self):
        second = self.other_capture()
        manifest = self.manifest(second)
        manifest["examples"][1]["work_key"] = manifest["examples"][0]["work_key"]
        with self.assertRaisesMessage(ValueError, "work group"):
            benchmark_report(manifest)

        manifest = self.manifest(second)
        manifest["examples"][1]["layout_key"] = manifest["examples"][0]["layout_key"]
        with self.assertRaisesMessage(ValueError, "layout group"):
            benchmark_report(manifest)

        second.response = self.capture.response
        second.save(update_fields=["response"])
        with self.assertRaisesMessage(ValueError, "source digest group"):
            benchmark_report(self.manifest(second))

    def test_benchmark_rejects_repeated_nonempty_body_across_splits(self):
        second = self.same_body_different_source_capture()
        self.assertNotEqual(second.response["digest"], self.capture.response["digest"])
        report = self.manifest(second)
        report["examples"][1]["layout_key"] = "different-template"
        with self.assertRaisesMessage(ValueError, "body digest group"):
            benchmark_report(report)

    def test_imported_revision_is_not_a_label_and_invalidates_prior_revision_labels(self):
        index = self.heading_index(self.capture)
        save_correction(
            self.capture,
            self.reviewer,
            {"blocks": [{"index": index, "action": "h3"}]},
            0,
            "Local correction",
        )
        save_correction(
            self.capture,
            self.reviewer,
            {"metadata": {"title": "Imported title"}},
            1,
            "Transferred review",
            record_feedback=False,
        )
        self.assertEqual(CorrectionFeedback.objects.count(), 1)
        second = self.other_capture()
        report = benchmark_report(self.manifest(second))
        self.assertEqual(report["splits"]["development"]["labels"], {})

    def test_management_command_reads_only_local_json_and_reports_invalid_manifest(self):
        second = self.other_capture()
        with TemporaryDirectory() as directory:
            path = Path(directory) / "benchmark.json"
            path.write_text(json.dumps(self.manifest(second)), encoding="utf-8")
            output = []
            stream = StringIO()
            call_command("correction_benchmark", str(path), stdout=stream)
            output = json.loads(stream.getvalue())
            self.assertEqual(output["examples_checked"], 2)
            path.write_text("{", encoding="utf-8")
            with self.assertRaises(CommandError):
                call_command("correction_benchmark", str(path), stdout=StringIO())


class CorrectionFeedbackManifestTests(TestCase):
    setUp = test_corrections.CorrectionTests.setUp

    def test_manifest_requires_both_splits_and_rejects_malformed_split_values(self):
        manifest = {
            "format_version": 1,
            "task": "block-type",
            "examples": [
                {"capture_id": self.capture.pk, "work_key": "work", "split": "development"}
            ],
        }
        with self.assertRaisesMessage(ValueError, "both development and held_out"):
            benchmark_report(manifest)
        manifest["examples"][0]["split"] = []
        manifest["examples"].append(
            {"capture_id": self.capture.pk + 1, "work_key": "other", "split": "held_out"}
        )
        with self.assertRaises((ValueError, TypeError)):
            benchmark_report(manifest)
