from copy import deepcopy
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from library.models import DocumentDraftBase, DocumentEditRevision, ReviewerRun, ReviewerTask
from library.services.document_edits import (
    DocumentEditConflict,
    branch_draft,
    save_revision,
)
from library.services.document_publication import prepare_publication
from library.services.semantic_documents import fingerprint
from library.tests import test_document_edits as foundation


@override_settings(READING_HUB_EDITOR_PILOT=True)
class CorrectionHistoryTests(TestCase):
    def setUp(self):
        foundation.DocumentEditTests.setUp(self)
        self.reviewer.is_staff = True
        self.reviewer.save(update_fields=["is_staff"])
        self.client.force_login(self.reviewer)
        assets = patch("library.document_editor_views.finders.find", return_value="built")
        assets.start()
        self.addCleanup(assets.stop)
        self.url = reverse("document-editor", args=[self.rendition.pk])
        self.history = reverse("document-editor-history", args=[self.rendition.pk])

    def edit(self, draft=None, number=0, title="Corrected title", **kwargs):
        draft = draft or self.draft
        return save_revision(
            draft, self.reviewer, {**draft.document, "title": title}, number, **kwargs,
        )

    def test_open_continues_exact_latest_without_task_or_mutation(self):
        row = self.edit()
        before = (DocumentDraftBase.objects.count(), DocumentEditRevision.objects.count())
        response = self.client.get(self.url)
        self.assertEqual(response.context["initial"]["document"], row.document)
        self.assertEqual(response.context["initial"]["revision"], 1)
        self.assertContains(response, "Mark reviewed")
        self.assertContains(response, "Version history")
        self.assertNotContains(response, "Define a review task")
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(before, (
            DocumentDraftBase.objects.count(), DocumentEditRevision.objects.count(),
        ))
        self.assertFalse(ReviewerTask.objects.exists())
        self.assertFalse(ReviewerRun.objects.exists())
        source = self.client.get(self.url + "?start=source")
        self.assertIsNone(source.context["initial"]["draft"])
        self.assertEqual(source.context["initial"]["document"], self.draft.document)

    def test_ambiguous_histories_require_choice_and_explicit_draft_stays_pinned(self):
        self.edit()
        branch = branch_draft(self.draft, self.reviewer, 1)
        before = (DocumentDraftBase.objects.count(), DocumentEditRevision.objects.count())
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["initial"]["choose_history"])
        self.assertContains(response, '"choose_history": true')
        self.assertIsNone(response.context["initial"]["draft"])
        self.assertEqual(response.context["initial"]["revision"], 0)
        selected = self.client.get(self.url + f"?draft={self.draft.pk}")
        self.assertEqual(selected.context["draft"], self.draft)
        self.assertFalse(selected.context["initial"]["choose_history"])
        history = self.client.get(self.history + "?embedded=1")
        self.assertContains(history, str(branch.pk))
        self.assertContains(history, f'{self.url}?start=source" data-workflow-switch')
        source = self.client.get(self.url + "?start=source")
        self.assertFalse(source.context["initial"]["choose_history"])
        self.assertContains(source, '"choose_history": false')
        self.assertIsNone(source.context["initial"]["draft"])
        self.assertEqual(source.context["initial"]["document"], self.draft.document)
        self.assertEqual(before, (DocumentDraftBase.objects.count(),
                                  DocumentEditRevision.objects.count()))

    def test_branch_exact_old_revision_preserves_newer_versions_and_publication(self):
        original = self.edit(review="full", editorial=True)
        self.edit(number=1, title="Later correction")
        before = deepcopy(self.draft.evidence)
        branch = branch_draft(self.draft, self.reviewer, 1)
        self.assertEqual(branch.document, original.document)
        self.assertFalse(branch.revisions.exists())
        self.assertEqual(
            branch.evidence["correction_origin"]["document_digest"], original.document_digest,
        )
        self.assertEqual(branch.evidence["correction_origin"]["revision"], 1)
        self.assertEqual(
            branch.evidence["correction_origin"]["evidence_digest"], self.draft.evidence_digest,
        )
        self.assertEqual(self.draft.evidence, before)
        self.assertEqual(self.draft.revisions.first().document["title"], "Later correction")
        row = self.edit(branch, title="Branch correction")
        self.assertEqual(row.review, "partial")
        self.assertTrue(row.editorial)
        self.assertEqual(row.lineage["document_digest"], original.document_digest)
        self.assertEqual(row.lineage["revision"], 0)
        candidate = prepare_publication(branch, 1)
        self.assertEqual(candidate["output"]["title"], "Branch correction")
        second = branch_draft(branch, self.reviewer, 1)
        self.edit(second, title="Another branch")
        self.assertEqual(prepare_publication(second, 1)["output"]["title"], "Another branch")

    def test_base_branch_integrity_and_invalid_revision(self):
        branch = branch_draft(self.draft, self.reviewer, 0)
        self.assertEqual(branch.document_digest, self.draft.document_digest)
        for invalid in (-1, True, "1", 99):
            with self.assertRaises(ValueError):
                branch_draft(self.draft, self.reviewer, invalid)
        self.draft.document["title"] = "Tampered"
        with self.assertRaisesMessage(ValueError, "integrity"):
            branch_draft(self.draft, self.reviewer, 0)

    def test_new_saves_pin_immediate_parent_and_stale_save_is_rejected(self):
        first = self.edit()
        second = self.edit(number=1, title="Second")
        self.assertEqual(first.lineage["document_digest"], self.draft.document_digest)
        self.assertEqual(second.lineage["document_digest"], first.document_digest)
        self.assertEqual(second.lineage["revision"], 1)
        with self.assertRaises(DocumentEditConflict):
            self.edit(number=1)
        with self.assertRaisesMessage(ValueError, "immutable"):
            second.save()

    def test_history_get_is_read_only_post_is_csrf_protected_and_exact(self):
        row = self.edit()
        before = DocumentDraftBase.objects.count()
        query = f"?draft={self.draft.pk}&revision=1"
        response = self.client.get(self.history + query)
        self.assertEqual(response.context["selected"]["row"], row)
        self.assertContains(response, "Start a separate correction")
        self.assertEqual(DocumentDraftBase.objects.count(), before)
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.reviewer)
        self.assertEqual(
            secure.post(self.history, {"draft": self.draft.pk, "revision": 1}).status_code, 403,
        )
        created = self.client.post(self.history, {"draft": self.draft.pk, "revision": 1})
        self.assertEqual(created.status_code, 302)
        branch = DocumentDraftBase.objects.get(pk=created.url.split("draft=")[1])
        self.assertEqual(branch.document_digest, fingerprint(row.document))
        self.assertEqual(self.client.post(
            self.history, {"draft": self.draft.pk, "revision": 900},
        ).status_code, 422)
        self.assertEqual(self.client.get(self.history + "?draft=invalid").status_code, 422)

    def test_profile_permission_and_pilot_controls(self):
        anonymous = Client()
        self.assertEqual(anonymous.get(self.history).status_code, 302)
        with override_settings(READING_HUB_EDITOR_PILOT=False):
            self.assertEqual(self.client.get(self.history).status_code, 404)
        with patch("library.document_editor_views.get_profile") as profile:
            profile.return_value.key = "another-profile"
            self.assertEqual(self.client.get(
                self.history + f"?draft={self.draft.pk}",
            ).status_code, 404)

    def test_comparison_export_exposes_new_lineage_without_certifying_training_data(self):
        row = self.edit()
        url = reverse("document-comparison", args=[self.rendition.pk])
        exported = self.client.get(url, {
            "draft": self.draft.pk, "to": 1, "download": "1",
        }).json()
        self.assertEqual(exported["later"]["lineage"], row.lineage)
        self.assertEqual(exported["semantics"], "saved_comparison_not_verified_training_pair")
        self.assertEqual(exported["later"]["review"], "partial")

    def test_history_escapes_saved_markup(self):
        row = save_revision(self.draft, self.reviewer, {
            **self.draft.document, "title": "<unsafe title>",
            "html": '<section id="c1"><p>Saved &lt;script&gt; text.</p></section>',
        }, 0)
        response = self.client.get(self.history, {"draft": self.draft.pk, "revision": 1})
        self.assertContains(response, "&lt;unsafe title&gt;")
        self.assertContains(response, "&lt;section")
        self.assertNotContains(response, row.document["html"])
