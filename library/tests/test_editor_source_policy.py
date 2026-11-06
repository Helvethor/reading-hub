from django.test import Client, TestCase, override_settings
from django.urls import reverse

from library.models import CrawlCapture, PageTypeDecision
from library.tests import test_organizations as fixtures


@override_settings(READING_HUB_EDITOR_PILOT=True)
class EditorSourcePolicyTests(TestCase):
    response = fixtures.OrganizationTests.response

    def setUp(self):
        fixtures.OrganizationTests.setUp(self)
        self.url = reverse("document-editor-source-policy", args=[self.book.pk])

    def test_inspection_is_read_only_and_embedded_policy_is_scoped(self):
        before = (CrawlCapture.objects.count(), PageTypeDecision.objects.count())
        response = self.client.get(self.url, {"embedded": "1"})
        self.assertContains(response, "Retained-source classification")
        self.assertContains(response, "all matching captures/catalogue entries")
        self.assertEqual(response["X-Frame-Options"], "SAMEORIGIN")
        self.assertEqual(before, (CrawlCapture.objects.count(), PageTypeDecision.objects.count()))
        standalone = self.client.get(self.url)
        self.assertEqual(standalone["X-Frame-Options"], "DENY")

    def test_classification_and_undo_preserve_exact_edition_and_require_current_revision(self):
        original = self.book.html
        response = self.client.post(self.url + "?embedded=1", {
            "page": "0", "action": "discovery", "revision": "0",
            "reason": "Synthetic index policy check", "confirm": "yes",
        })
        self.assertContains(response, "Source policy saved.")
        decision = PageTypeDecision.objects.get()
        capture = CrawlCapture.objects.get(url=self.book.document.url)
        self.assertTrue(capture.discovery_only)
        stale = self.client.post(self.url, {
            "page": "0", "action": "undo", "revision": "0",
            "reason": "Stale undo", "confirm": "yes",
        })
        self.assertContains(stale, "changed since", status_code=422)
        self.assertEqual(PageTypeDecision.objects.count(), 1)
        response = self.client.post(self.url, {
            "page": "0", "action": "undo", "revision": str(decision.pk),
            "reason": "Undo synthetic index policy", "confirm": "yes",
        })
        self.assertContains(response, "Source policy saved.")
        capture.refresh_from_db()
        self.assertFalse(capture.discovery_only)
        self.book.refresh_from_db()
        self.assertEqual(self.book.html, original)
        self.assertEqual(PageTypeDecision.objects.count(), 2)

    def test_confirmation_validation_and_csrf_precede_any_capture_or_decision_write(self):
        before = (CrawlCapture.objects.count(), PageTypeDecision.objects.count())
        for values in (
            {"page": "0", "action": "discovery", "revision": "0", "reason": "No confirmation"},
            {"page": "-1", "confirm": "yes"},
            {"page": "0", "action": "discovery", "revision": "0", "reason": "", "confirm": "yes"},
        ):
            with self.subTest(values=values):
                self.assertEqual(self.client.post(self.url, values).status_code, 422)
                self.assertEqual(before, (
                    CrawlCapture.objects.count(), PageTypeDecision.objects.count(),
                ))
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.reviewer)
        self.assertEqual(csrf.post(self.url, {"confirm": "yes"}).status_code, 403)
