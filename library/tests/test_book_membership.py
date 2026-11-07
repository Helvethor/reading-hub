from copy import deepcopy
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from library.models import (
    BookMembershipDecision,
    CatalogueEntry,
    ContentOrganization,
    Document,
    Job,
    Rendition,
)
from library.services.book_membership import commit_membership, preview_membership
from library.services.catalogue import register_book
from library.services.document_edits import create_draft
from library.services.organizations import current_spec, member_destination
from library.services.pipeline import claim_job, enqueue, process_job
from library.sources.adapters import discover, parse_html
from library.tests import test_organizations as fixtures
from library.tests.test_sources import ARTICLE, BOOK, book_index


@override_settings(READING_HUB_EDITOR_PILOT=True, ALLOWED_HOSTS=["testserver"])
class BookMembershipTests(TestCase):
    setUp = fixtures.OrganizationTests.setUp
    response = fixtures.OrganizationTests.response

    def root(self):
        return CatalogueEntry.objects.get(url=BOOK)

    def preview(self, url, action):
        return preview_membership(self.root(), url, action)

    def apply(self, preview):
        return commit_membership(preview, self.reviewer, "Verified catalogue routing")

    def test_attach_routes_to_landing_page_without_rebuilding_or_inserting(self):
        enqueue(ARTICLE)
        article = process_job(claim_job())
        draft = create_draft(self.book, self.reviewer)
        original = deepcopy(draft.evidence)
        editions = Rendition.objects.count()
        proposal = self.preview(ARTICLE, "attach")
        self.assertFalse(BookMembershipDecision.objects.exists())
        self.apply(proposal)
        self.assertEqual(Rendition.objects.count(), editions)
        draft.refresh_from_db()
        self.assertEqual(draft.evidence, original)
        self.assertEqual(CatalogueEntry.objects.get(url=ARTICLE).book_id, self.root().pk)
        self.assertEqual(member_destination(article.document, article), (self.book, ""))
        self.assertRedirects(
            self.client.get(reverse("reader", args=[article.pk])),
            reverse("reader", args=[self.book.pk]), fetch_redirect_response=False,
        )
        self.assertFalse(ContentOrganization.objects.exists())

    def test_detach_missing_standalone_previews_offline_build_without_changing_book(self):
        url = self.spec["parts"][1]["url"]
        self.assertFalse(Document.objects.filter(url=url).exists())
        draft = create_draft(self.book, self.reviewer)
        before = (draft.document, draft.evidence, self.book.html)
        with patch("library.services.fetch.Fetcher.fetch") as fetch:
            proposal = self.preview(url, "detach")
            self.assertIn("spec", proposal["standalone"])
            self.assertFalse(Document.objects.filter(url=url).exists())
            decision = self.apply(proposal)
            fetch.assert_not_called()
        standalone = Document.objects.get(url=url).latest()
        self.assertFalse(standalone.structure["book"])
        self.assertIsNone(CatalogueEntry.objects.get(url=url).book_id)
        self.assertTrue(CatalogueEntry.objects.get(url=url).membership_reviewed)
        self.book.refresh_from_db()
        draft.refresh_from_db()
        self.assertEqual((draft.document, draft.evidence, self.book.html), before)
        self.assertEqual(member_destination(standalone.document, standalone), None)
        undo = preview_membership(self.root(), url, "attach", undo=decision)
        self.apply(undo)
        self.assertEqual(CatalogueEntry.objects.get(url=url).book_id, self.root().pk)
        self.assertEqual(BookMembershipDecision.objects.count(), 2)

    def test_explicit_detach_and_attach_survive_register_and_source_reformat(self):
        url = self.spec["parts"][1]["url"]
        self.apply(self.preview(url, "detach"))
        register_book(
            self.sites["www.marxists.org"], BOOK, discover(parse_html(book_index()), BOOK),
        )
        self.assertIsNone(CatalogueEntry.objects.get(url=url).book_id)
        enqueue(BOOK, Job.Mode.REFORMAT, self.book.snapshot)
        process_job(claim_job())
        self.assertIsNone(CatalogueEntry.objects.get(url=url).book_id)
        self.assertEqual(current_spec(BOOK), self.spec)

    def test_stale_preview_conflicts_active_imports_and_missing_sources(self):
        url = self.spec["parts"][1]["url"]
        proposal = self.preview(url, "detach")
        self.apply(proposal)
        with self.assertRaisesMessage(ValueError, "not a member"):
            self.apply(proposal)
        with self.assertRaisesMessage(ValueError, "Missing retained page"):
            self.preview(BOOK.replace("index.htm", "absent.htm"), "attach")
        with self.assertRaisesMessage(ValueError, "already belongs"):
            self.preview(self.spec["parts"][2]["url"], "attach")
        Job.objects.create(document=self.book.document, mode=Job.Mode.REFRESH)
        with self.assertRaisesMessage(ValueError, "active import"):
            self.preview(self.spec["parts"][2]["url"], "detach")

    def test_attach_and_undo_remain_authoritative_after_source_discovery(self):
        enqueue(ARTICLE)
        process_job(claim_job())
        decision = self.apply(self.preview(ARTICLE, "attach"))
        register_book(
            self.sites["www.marxists.org"], BOOK, discover(parse_html(book_index()), BOOK),
        )
        self.assertEqual(CatalogueEntry.objects.get(url=ARTICLE).book_id, self.root().pk)
        self.apply(preview_membership(self.root(), ARTICLE, "detach", undo=decision))
        self.assertIsNone(CatalogueEntry.objects.get(url=ARTICLE).book_id)
        self.assertTrue(CatalogueEntry.objects.get(url=ARTICLE).membership_reviewed)
        with self.assertRaisesMessage(ValueError, "not a member"):
            preview_membership(self.root(), ARTICLE, "detach", undo=decision)

    def test_members_missing_from_corrected_structure_do_not_use_pinned_source_anchors(self):
        url = self.spec["parts"][1]["url"]
        document = Document.objects.create(url=url)
        self.book.structure = {**self.book.structure, "parts": []}
        self.book.save(update_fields=["structure"])
        self.assertEqual(member_destination(document), (self.book, ""))

    def test_permission_csrf_and_tampered_confirmation(self):
        url = reverse("document-editor-membership", args=[self.book.pk])
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.reviewer)
        self.assertEqual(strict.post(url, {"action": "detach"}).status_code, 403)
        user = get_user_model().objects.create_user("reader-only")
        self.client.force_login(user)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.reviewer)
        self.assertEqual(
            self.client.post(url, {"action": "apply", "token": "tampered",
                                   "confirm": "yes"}).status_code, 422,
        )
        self.assertFalse(BookMembershipDecision.objects.exists())

    def test_page_has_only_ownership_controls_and_requires_confirmation(self):
        url = reverse("document-editor-membership", args=[self.book.pk])
        page = self.client.get(url)
        self.assertContains(page, "Catalogue book membership")
        self.assertNotContains(page, 'name="specification"')
        self.assertNotContains(page, "Move up")
        preview = self.client.post(url, {
            "action": "detach", "url": self.spec["parts"][1]["url"], "reason": "Separate",
        })
        self.assertEqual(preview.status_code, 200)
        token = preview.context["token"]
        self.assertEqual(
            self.client.post(url, {"action": "apply", "token": token}).status_code, 422,
        )
        applied = self.client.post(url, {"action": "apply", "token": token, "confirm": "yes"})
        self.assertContains(applied, "Catalogue membership saved")
        decision = BookMembershipDecision.objects.get()
        with self.assertRaisesMessage(IntegrityError, "append-only"), transaction.atomic():
            BookMembershipDecision.objects.filter(pk=decision.pk).update(reason="rewrite")
