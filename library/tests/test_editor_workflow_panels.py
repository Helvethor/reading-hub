import json
from unittest.mock import patch

from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from library.document_editor_views import baseline
from library.models import DocumentDraftBase, DocumentPublication
from library.services.document_edits import branch_draft, save_revision
from library.services.document_publication import prepare_publication
from library.tests import test_document_edits as foundation


@override_settings(READING_HUB_EDITOR_PILOT=True)
class EditorWorkflowPanelTests(TestCase):
    def setUp(self):
        foundation.DocumentEditTests.setUp(self)
        self.reviewer.is_staff = True
        self.reviewer.save(update_fields=["is_staff"])
        self.client.force_login(self.reviewer)
        patcher = patch("library.document_editor_views.finders.find", return_value="built")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.editor = reverse("document-editor", args=[self.rendition.pk])
        self.history = reverse("document-editor-history", args=[self.rendition.pk])
        self.comparison = reverse("document-comparison", args=[self.rendition.pk])
        self.publication = reverse("document-publication", args=[self.rendition.pk])
        self.fresh = reverse("document-fresh-draft", args=[self.rendition.pk])
        self.row = save_revision(
            self.draft, self.reviewer, {**self.draft.document, "title": "Saved revision"}, 0,
        )

    def test_multiple_histories_stay_in_workspace_with_choice_and_pinned_baseline(self):
        branch_draft(self.draft, self.reviewer, 1)
        before = DocumentDraftBase.objects.count()
        response = self.client.get(self.editor)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["choose_history"])
        self.assertTrue(response.context["initial"]["choose_history"])
        self.assertIsNone(response.context["initial"]["draft"])
        self.assertEqual(DocumentDraftBase.objects.count(), before)
        response = self.client.get(self.editor, {"draft": self.draft.pk})
        self.assertFalse(response.context["choose_history"])
        self.assertFalse(response.context["initial"]["choose_history"])
        self.assertEqual(response.context["initial"]["document"], self.row.document)
        self.assertEqual(response.context["initial"]["baseline_document"], self.draft.document)

    def test_baseline_endpoint_checks_and_returns_exact_saved_state(self):
        factory = RequestFactory()
        for number, expected in [(0, self.draft), (1, self.row)]:
            request = factory.get("/", {"draft": self.draft.pk, "revision": number})
            request.user = self.reviewer
            response = baseline(request, self.rendition.pk)
            result = json.loads(response.content)
            self.assertEqual(result["document"], expected.document)
            self.assertEqual(result["digest"], expected.document_digest)
            self.assertEqual(result["revision"], number)
            self.assertEqual(response["Cache-Control"], "no-store")
        request = factory.get("/", {"draft": self.draft.pk, "revision": 99})
        request.user = self.reviewer
        self.assertEqual(baseline(request, self.rendition.pk).status_code, 422)

    def test_embedded_history_branches_without_switching_editor(self):
        response = self.client.get(self.history, {
            "draft": self.draft.pk, "revision": 1, "embedded": 1,
        })
        self.assertContains(response, 'name="revision" value="1"')
        self.assertContains(response, "embedded=1")
        self.assertNotContains(response, 'class="site-header"')
        response = self.client.post(self.history + "?embedded=1", {
            "draft": self.draft.pk, "revision": 1,
        })
        self.assertEqual(response.status_code, 200)
        branch = DocumentDraftBase.objects.exclude(pk=self.draft.pk).get()
        self.assertEqual(branch.document, self.row.document)
        self.assertContains(response, f'?draft={branch.pk}" data-workflow-switch')
        self.assertEqual(self.draft.revisions.count(), 1)

    def test_embedded_comparison_binds_saved_revision_and_form(self):
        response = self.client.get(self.comparison, {
            "draft": self.draft.pk, "from": 0, "to": 1, "embedded": 1,
        })
        self.assertContains(response, 'name="embedded" value="1"')
        self.assertContains(response, 'name="to" min="0" value="1"')
        self.assertContains(response, "Unsaved editor changes are not included")
        self.assertNotContains(response, 'class="site-header"')

    def test_fresh_confirmation_creates_without_automatic_switch(self):
        with patch("library.document_editor_views.create_fresh_draft",
                   return_value=self.draft) as create:
            response = self.client.post(self.fresh + "?embedded=1", {
                "inputs": "original", "preview_digest": "exact", "confirm": "yes",
            })
        create.assert_called_once_with(
            self.rendition, self.reviewer, "exact", original_source=True,
        )
        self.assertContains(response, f'?draft={self.draft.pk}" data-workflow-switch')

    def test_embedded_publication_requires_confirmation_and_displays_published_result(self):
        candidate = prepare_publication(self.draft, 1)
        url = self.publication + f"?draft={self.draft.pk}&revision=1&embedded=1"
        preview = self.client.get(url)
        self.assertContains(preview, f'name="draft" value="{self.draft.pk}"')
        self.assertContains(preview, f'name="preview_digest" value="{candidate["digest"]}"')
        response = self.client.post(url, {
            "draft": self.draft.pk, "revision": 1, "preview_digest": candidate["digest"],
        })
        self.assertEqual(response.status_code, 422)
        self.assertFalse(DocumentPublication.objects.exists())
        response = self.client.post(url, {
            "draft": self.draft.pk, "revision": 1, "preview_digest": candidate["digest"],
            "confirm": "yes",
        })
        self.assertContains(response, "Published saved revision 1")
        self.assertContains(response, "Saved revision")
        self.assertNotContains(response, 'class="site-header"')
        self.assertEqual(DocumentPublication.objects.count(), 1)

    def test_browser_frame_policy_only_allows_marked_panel_responses(self):
        editor = self.client.get(self.editor)
        self.assertIn("frame-src 'self'", editor["Content-Security-Policy"])
        self.assertIn("frame-ancestors 'none'", editor["Content-Security-Policy"])
        self.assertEqual(editor["X-Frame-Options"], "DENY")

        # This fixture has no complete retained snapshot; exercise the rendered error panel.
        with patch("library.document_editor_views.preview_fresh_draft",
                   side_effect=ValueError("Preview unavailable")):
            for url, params in (
                (self.history, {}),
                (self.comparison, {"draft": self.draft.pk, "to": 1}),
                (self.publication, {"draft": self.draft.pk, "revision": 1}),
                (self.fresh, {}),
                (reverse("document-editor-membership", args=[self.rendition.pk]), {}),
            ):
                with self.subTest(url=url):
                    normal = self.client.get(url, params)
                    self.assertEqual(normal["X-Frame-Options"], "DENY")
                    self.assertIn("frame-ancestors 'none'", normal["Content-Security-Policy"])
                    embedded = self.client.get(url, {**params, "embedded": "1"})
                    self.assertEqual(embedded["X-Frame-Options"], "SAMEORIGIN")
                    self.assertIn("frame-ancestors 'self'", embedded["Content-Security-Policy"])
                    self.assertNotIn("frame-src 'self'", embedded["Content-Security-Policy"])

        reader = self.client.get(reverse("reader", args=[self.rendition.pk]), {"embedded": "1"})
        self.assertEqual(reader["X-Frame-Options"], "DENY")
        self.assertIn("frame-ancestors 'none'", reader["Content-Security-Policy"])
        self.assertNotIn("frame-src 'self'", reader["Content-Security-Policy"])
