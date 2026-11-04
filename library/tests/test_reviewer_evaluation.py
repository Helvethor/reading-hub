from dataclasses import replace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from library.models import (
    DocumentDraftBase,
    DocumentEditRevision,
    DocumentPublication,
    Rendition,
    ReviewerResult,
    ReviewerRun,
    ReviewerTask,
)
from library.profile import get_profile
from library.services.document_edits import DocumentEditConflict, save_revision
from library.services.document_publication import prepare_publication
from library.services.reviewer_evaluation import create_task, record_result, start_run
from library.services.semantic_documents import fingerprint
from library.tests import test_document_edits as foundation


def observations(**changes):
    return {
        "outcome": "completed", "active_minutes": None, "remaining_errors": None,
        "severe_errors": None, "keyboard": "not_tested", "screen_reader": "not_tested",
        "narrow_screen": "not_tested", "notes": "Checked only the stated paragraph.",
        **changes,
    }


def posted_observations(**changes):
    return {key: "" if value is None else value
            for key, value in observations(**changes).items()}


@override_settings(READING_HUB_EDITOR_PILOT=True)
class EvaluationTests(TestCase):
    def setUp(self):
        foundation.DocumentEditTests.setUp(self)
        self.reviewer.is_staff = True
        self.reviewer.save(update_fields=["is_staff"])
        self.client.force_login(self.reviewer)
        self.task = create_task(
            self.draft, self.reviewer, title="Correct an article",
            scope="First paragraph only; exclude the rest.",
            instructions="Compare the retained source, repair the paragraph and save.",
        )

    def counts(self):
        return [model.objects.count() for model in (
            DocumentDraftBase, DocumentEditRevision, ReviewerTask, ReviewerRun,
            ReviewerResult, Rendition, DocumentPublication,
        )]

    def test_task_pins_base_not_current_edits_and_gets_never_write(self):
        save_revision(self.draft, self.reviewer, {
            **self.draft.document, "title": "Not the starting document",
        }, 0, review="full")
        before = self.counts()
        for url in (
            reverse("reviewer-tasks"), reverse("reviewer-task", args=[self.task.pk]),
            reverse("reviewer-task-new", args=[self.rendition.pk]) + f"?draft={self.draft.pk}",
        ):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(before, self.counts())
        run = start_run(self.task, self.reviewer, practice=True)
        self.assertEqual(run.draft.document, self.draft.document)
        self.assertNotEqual(run.draft.pk, self.draft.pk)
        self.assertEqual(run.draft.revisions.count(), 0)
        self.assertTrue(run.practice)
        self.assertEqual(run.draft.evidence["evaluation_origin"]["task"], self.task.pk)
        self.assertEqual(fingerprint(run.draft.evidence), run.draft.evidence_digest)
        second = start_run(self.task, self.reviewer, practice=False)
        self.assertEqual(run.draft.document, second.draft.document)
        self.assertNotEqual(run.draft.pk, second.draft.pk)

    def test_record_binds_exact_revision_with_unknowns_and_never_verifies_or_publishes(self):
        run = start_run(self.task, self.reviewer, practice=False)
        row = save_revision(run.draft, self.reviewer, {
            **run.draft.document, "title": "Corrected",
        }, 0)
        result = record_result(run, self.reviewer, 1, observations())
        self.assertEqual(result.revision_id, row.pk)
        self.assertEqual(result.observations["active_minutes"], None)
        self.assertEqual(result.binding["document_digest"], row.document_digest)
        self.assertEqual(result.binding["saved_review"], "partial")
        self.assertEqual(DocumentPublication.objects.count(), 0)
        self.assertEqual(Rendition.objects.count(), 1)
        save_revision(run.draft, self.reviewer, {
            **row.document, "title": "Later",
        }, 1)
        result.refresh_from_db()
        self.assertEqual(result.binding["document_digest"], row.document_digest)
        with self.assertRaises(DocumentEditConflict):
            record_result(run, self.reviewer, 2, observations())
        candidate = prepare_publication(run.draft, 2)
        self.assertEqual(candidate["output"]["title"], "Later")

    def test_blocked_run_can_record_unchanged_base_and_zero_is_not_unknown(self):
        run = start_run(self.task, self.reviewer, practice=True)
        result = record_result(run, self.reviewer, 0, observations(
            outcome="blocked", active_minutes=0, remaining_errors=2, severe_errors=1,
            keyboard="blocked",
        ))
        self.assertIsNone(result.revision)
        response = self.client.get(reverse("reviewer-run", args=[run.pk]))
        self.assertContains(response, "Result recorded")
        self.assertContains(response, "<dd>0</dd>", html=True)
        self.assertContains(response, "practice")

    def test_reject_foreign_revision_owner_invalid_numbers_and_inconsistent_error_counts(self):
        run = start_run(self.task, self.reviewer, practice=False)
        save_revision(self.draft, self.reviewer, self.draft.document, 0)
        with self.assertRaisesMessage(ValueError, "saved revision"):
            record_result(run, self.reviewer, 1, observations())
        other = get_user_model().objects.create_user("other")
        with self.assertRaisesMessage(ValueError, "reviewer who started"):
            record_result(run, other, 0, observations())
        for values in (
            {"active_minutes": -1}, {"active_minutes": True}, {"remaining_errors": 100001},
            {"remaining_errors": 1, "severe_errors": 2}, {"severe_errors": 0},
            {"notes": ""}, {"keyboard": "passed"}, {"outcome": "accepted"},
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                record_result(run, self.reviewer, 0, observations(**values))
        self.assertEqual(ReviewerResult.objects.count(), 0)

    def test_tasks_runs_results_are_immutable(self):
        run = start_run(self.task, self.reviewer, practice=False)
        result = record_result(run, self.reviewer, 0, observations())
        for row in (self.task, run, result):
            with self.assertRaisesMessage(ValueError, "immutable"):
                row.save()
            with self.assertRaisesMessage(ValueError, "immutable"):
                row.delete()
            with self.assertRaisesMessage(ValueError, "immutable"):
                type(row).objects.filter(pk=row.pk).update(pk=row.pk)
            with self.assertRaisesMessage(ValueError, "immutable"):
                type(row).objects.filter(pk=row.pk).delete()

    def test_profile_and_tampered_evidence_refused(self):
        other = replace(get_profile(), key="other")
        with patch("library.services.reviewer_evaluation.get_profile", return_value=other):
            with self.assertRaisesMessage(ValueError, "profile"):
                start_run(self.task, self.reviewer, practice=True)
        self.task.starting_draft.document = {**self.draft.document, "title": "Tampered"}
        with self.assertRaisesMessage(ValueError, "integrity"):
            start_run(self.task, self.reviewer, practice=True)

    def test_app_update_preserves_original_task_binding_and_records_run_versions_separately(self):
        original = self.task.binding
        with patch("library.versions.APP_VERSION", "later-runtime"):
            run = start_run(self.task, self.reviewer, practice=False)
            result = record_result(run, self.reviewer, 0, observations())
        self.assertEqual(result.binding["task_binding"], original)
        self.assertEqual(result.binding["run_app_version"], "later-runtime")
        self.assertEqual(result.binding["recorded_with_app"], "later-runtime")

    def test_invalid_task_draft_id_and_foreign_profile_are_explicit(self):
        url = reverse("reviewer-task-new", args=[self.rendition.pk])
        self.assertEqual(self.client.get(url, {"draft": "invalid"}).status_code, 422)
        with patch("library.reviewer_evaluation_views.get_profile",
                   return_value=replace(get_profile(), key="other")):
            self.assertEqual(self.client.get(
                reverse("reviewer-task", args=[self.task.pk]),
            ).status_code, 404)

    def test_browser_form_workflow_and_exact_saved_result(self):
        new_url = reverse("reviewer-task-new", args=[self.rendition.pk])
        response = self.client.post(new_url + f"?draft={self.draft.pk}", {
            "title": "Quote review", "scope": "Preface only", "instructions": "Repair attribution.",
        })
        self.assertEqual(response.status_code, 302)
        task = ReviewerTask.objects.order_by("-pk").first()
        response = self.client.post(reverse("reviewer-task", args=[task.pk]), {"mode": "measured"})
        self.assertEqual(response.status_code, 302)
        run = ReviewerRun.objects.get()
        url = reverse("reviewer-run", args=[run.pk])
        self.assertContains(self.client.get(url), "Open working draft")
        with patch("library.document_editor_views.finders.find", return_value="built"):
            editor = self.client.get(
                reverse("document-editor", args=[self.rendition.pk]), {"draft": run.draft_id},
            )
        self.assertContains(editor, "Isolated evaluation working draft")
        save_revision(run.draft, self.reviewer, run.draft.document, 0)
        response = self.client.post(url, {**posted_observations(), "revision": 1})
        self.assertEqual(response.status_code, 302)
        self.assertContains(self.client.get(url), "Result recorded")
        response = self.client.post(url, {**posted_observations(), "revision": 1})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(ReviewerResult.objects.count(), 1)

    def test_invalid_form_is_visible_and_never_creates_partial_records(self):
        counts = self.counts()
        url = reverse("reviewer-task-new", args=[self.rendition.pk]) + f"?draft={self.draft.pk}"
        self.assertEqual(self.client.post(url, {"title": ""}).status_code, 422)
        self.assertEqual(self.client.post(
            reverse("reviewer-task", args=[self.task.pk]), {"mode": "unknown"},
        ).status_code, 422)
        self.assertEqual(self.counts(), counts)
        run = start_run(self.task, self.reviewer, practice=False)
        url = reverse("reviewer-run", args=[run.pk])
        response = self.client.post(url, {
            **posted_observations(), "revision": 0, "remaining_errors": 1, "severe_errors": 2,
        })
        self.assertEqual(response.status_code, 422)
        self.assertContains(response, "Provide a total error count", status_code=422)
        self.assertEqual(ReviewerResult.objects.count(), 0)

    def test_access_controls_csrf_pilot_and_run_privacy(self):
        run = start_run(self.task, self.reviewer, practice=True)
        task_url = reverse("reviewer-task", args=[self.task.pk])
        run_url = reverse("reviewer-run", args=[run.pk])
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.reviewer)
        self.assertEqual(protected.post(task_url, {"mode": "measured"}).status_code, 403)
        response = protected.post(run_url, {**posted_observations(), "revision": 0})
        self.assertEqual(response.status_code, 403)
        with override_settings(READING_HUB_EDITOR_PILOT=False):
            self.assertEqual(self.client.get(run_url).status_code, 404)
            self.assertEqual(self.client.get(reverse("reviewer-tasks")).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(task_url).status_code, 302)
        other = get_user_model().objects.create_user("another-reviewer", is_staff=True)
        self.client.force_login(other)
        self.assertEqual(self.client.get(run_url).status_code, 404)
        other.is_staff = False
        other.save()
        self.assertEqual(self.client.get(task_url).status_code, 403)

    def test_untrusted_task_and_observation_text_is_escaped(self):
        self.task = create_task(
            self.draft, self.reviewer, title="<script>title</script>",
            scope="<img src=x>", instructions="<script>instructions</script>",
        )
        response = self.client.get(reverse("reviewer-task", args=[self.task.pk]))
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>instructions</script>")
        run = start_run(self.task, self.reviewer, practice=False)
        record_result(run, self.reviewer, 0, observations(notes="<script>notes</script>"))
        response = self.client.get(reverse("reviewer-run", args=[run.pk]))
        self.assertContains(response, "&lt;script&gt;notes")
        self.assertNotContains(response, "<script>notes</script>")
