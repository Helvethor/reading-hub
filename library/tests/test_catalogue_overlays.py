from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from library.models import (
    CanonicalAuthor,
    CatalogueAuthor,
    CatalogueEntry,
    CatalogueOverlayDecision,
    MetadataSuggestion,
    SourceCorrection,
)
from library.services.catalogue import enrich_from_rendition, save_entry
from library.services.catalogue_overlays import binding, commit, proposal
from library.services.corrections import CorrectionConflict, save_correction
from library.services.metadata_review import catalogue_author_names, review_suggestion
from library.sources.catalogue import CatalogueLink
from library.tests import test_corrections


class CatalogueOverlayTests(TestCase):
    setUp = test_corrections.CorrectionTests.setUp

    def setUp_entry(self, metadata=None):
        self.entry = CatalogueEntry.objects.create(
            site=self.capture.site,
            url=self.capture.url,
            title="Original title",
            author="Original author",
            authors=["Original author"],
            language="en",
            published="1900",
            topic="Old topic",
            topics=["Old topic"],
        )
        return save_correction(
            self.capture,
            self.reviewer,
            {"metadata": metadata or {"title": "Reviewed title"}},
            0,
            "Review source",
        )

    def apply(self):
        return commit(self.capture, self.reviewer, binding(proposal(self.capture)), "Fix catalogue")

    def test_explicit_apply_and_undo_are_audited_and_do_not_modify_correction(self):
        correction = self.setUp_entry()
        plan = proposal(self.capture)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.title, "Original title")
        decision = commit(self.capture, self.reviewer, binding(plan), "Reviewed title")
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.title, "Reviewed title")
        self.assertEqual(decision.correction, correction)
        self.assertEqual(decision.reviewer, self.reviewer)
        undo = commit(
            self.capture, self.reviewer, binding(proposal(self.capture, undo=True)), "Undo title"
        )
        self.assertEqual(undo.undo_of, decision)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.title, "Original title")
        self.assertEqual(self.entry.metadata_overrides, {})
        self.assertEqual(SourceCorrection.objects.count(), 1)
        correction.refresh_from_db()
        self.assertEqual(correction.expected, {"metadata": {"title": "Reviewed title"}})

    def test_checked_crawl_updates_underlying_values_and_undo_uses_latest(self):
        self.setUp_entry()
        self.apply()
        save_entry(
            self.capture.site,
            CatalogueLink(
                self.capture.url,
                "New source title",
                True,
                author="New Author",
            ),
            checked=True,
        )
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.title, "Reviewed title")
        self.assertEqual(self.entry.metadata_baseline["title"], "New source title")
        self.assertEqual(self.entry.author, "New Author")
        commit(self.capture, self.reviewer, binding(proposal(self.capture, undo=True)), "Undo")
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.title, "New source title")

    def test_partial_new_correction_replaces_overlay_and_undo_restores_previous(self):
        self.setUp_entry()
        self.apply()
        save_correction(
            self.capture, self.reviewer, {"metadata": {"language": "fr"}}, 1, "Language"
        )
        self.apply()
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.title, "Original title")
        self.assertEqual(self.entry.language, "fr")
        commit(self.capture, self.reviewer, binding(proposal(self.capture, undo=True)), "Undo")
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.title, "Reviewed title")
        self.assertEqual(self.entry.language, "en")

    def test_author_roles_are_scoped_and_old_global_links_do_not_leak(self):
        self.setUp_entry(
            {
                "people": [
                    {"source_name": "Writer", "name": "Correct Writer", "role": "author"},
                    {"source_name": "Editor", "name": "Editor", "role": "editor"},
                    {"source_name": "Unknown", "name": "Unknown", "role": "unknown"},
                ]
            }
        )
        author = CanonicalAuthor.objects.create(name="Wrong canonical person")
        CatalogueAuthor.objects.create(
            entry=self.entry,
            author=author,
            source_name="Original author",
            reviewed_by=self.reviewer,
        )
        self.apply()
        self.entry.refresh_from_db()
        self.assertEqual(catalogue_author_names(self.entry), ["Correct Writer"])
        self.assertEqual(CatalogueAuthor.objects.count(), 1)
        commit(self.capture, self.reviewer, binding(proposal(self.capture, undo=True)), "Undo")
        self.entry.refresh_from_db()
        self.assertIn("Wrong canonical person", catalogue_author_names(self.entry))

    def test_explicit_clears_and_nonpublication_dates_remain_empty(self):
        self.setUp_entry(
            {
                "people": [],
                "topics": [],
                "dates": [
                    {"value": "1848", "type": "written"},
                ],
            }
        )
        self.apply()
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.authors, [])
        self.assertEqual(catalogue_author_names(self.entry), [])
        self.assertEqual(self.entry.topics, [])
        self.assertEqual(self.entry.published, "")

    def test_stale_catalogue_or_new_correction_and_replay_fail(self):
        self.setUp_entry()
        expected = binding(proposal(self.capture))
        self.entry.title = "Concurrent title"
        self.entry.save()
        with self.assertRaises(CorrectionConflict):
            commit(self.capture, self.reviewer, expected, "Apply")
        expected = binding(proposal(self.capture))
        save_correction(self.capture, self.reviewer, {"metadata": {"title": "Newer"}}, 1, "New")
        with self.assertRaises(CorrectionConflict):
            commit(self.capture, self.reviewer, expected, "Apply")
        expected = binding(proposal(self.capture))
        commit(self.capture, self.reviewer, expected, "Apply")
        with self.assertRaises(CorrectionConflict):
            commit(self.capture, self.reviewer, expected, "Replay")

    def test_stale_source_and_required_reason_are_rejected(self):
        correction = self.setUp_entry()
        with self.assertRaisesMessage(ValueError, "reason"):
            commit(self.capture, self.reviewer, binding(proposal(self.capture)), " ")
        correction.original = {**correction.original, "body_digest": "a" * 64}
        correction.save()
        with self.assertRaisesMessage(ValueError, "stale"):
            proposal(self.capture)
        self.assertFalse(CatalogueOverlayDecision.objects.exists())

    def test_missing_entry_discovery_and_book_member_fail_explicitly(self):
        with self.assertRaisesMessage(ValueError, "No catalogue entry"):
            proposal(self.capture)
        self.setUp_entry()
        self.entry.discovery_only = True
        self.entry.save()
        with self.assertRaisesMessage(ValueError, "Discovery"):
            proposal(self.capture)
        self.entry.discovery_only = False
        book = CatalogueEntry.objects.create(
            site=self.capture.site, url=self.capture.url + "book", title="Book"
        )
        self.entry.book = book
        self.entry.save()
        with self.assertRaisesMessage(ValueError, "belongs to a book"):
            proposal(self.capture)

    def test_enrichment_and_metadata_review_respect_overlays(self):
        self.setUp_entry({"title": "Reviewed title", "topics": [], "dates": []})
        self.apply()
        from types import SimpleNamespace

        enrich_from_rendition(
            SimpleNamespace(
                metadata={"published": "2001", "topics": ["New topic"], "topic": "New topic"},
                title="Imported title",
                document=SimpleNamespace(url=self.capture.url, aliases=[]),
            )
        )
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.title, "Reviewed title")
        self.assertEqual(self.entry.published, "")
        suggestion = MetadataSuggestion.objects.create(
            capture=self.capture,
            entry=self.entry,
            field="topic",
            value="Extra topic",
            method="test",
            fingerprint="f" * 64,
        )
        review_suggestion(suggestion, "approve", self.reviewer)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.topics, [])
        self.assertEqual(self.entry.metadata_baseline["topics"], ["New topic", "Extra topic"])
        commit(self.capture, self.reviewer, binding(proposal(self.capture, undo=True)), "Undo")
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.title, "Imported title")
        self.assertEqual(self.entry.published, "2001")
        self.assertEqual(self.entry.topics, ["New topic", "Extra topic"])

    def test_signed_confirm_permissions_csrf_tampering_and_history(self):
        self.setUp_entry()
        url = reverse("catalogue-overlay", args=[self.capture.pk])
        response = self.client.get(url)
        self.assertContains(response, "Original title")
        self.assertContains(response, "Reviewed title")
        token = response.context["token"]
        self.assertEqual(
            self.client.post(
                url,
                {
                    "action": "confirm",
                    "token": token + "x",
                    "reason": "Apply",
                },
            ).status_code,
            400,
        )
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.reviewer)
        self.assertEqual(csrf.post(url, {"token": token}).status_code, 403)
        user = get_user_model().objects.create_user("not-reviewer")
        outsider = Client()
        outsider.force_login(user)
        self.assertEqual(outsider.get(url).status_code, 403)
        self.assertEqual(outsider.post(url, {"token": token}).status_code, 403)
        self.assertEqual(
            self.client.post(
                url,
                {
                    "action": "confirm",
                    "token": token,
                    "reason": "Apply",
                },
            ).status_code,
            302,
        )
        self.assertContains(self.client.get(url), "Apply")
        self.assertEqual(
            self.client.post(
                url,
                {
                    "action": "confirm",
                    "token": token,
                    "reason": "Replay",
                },
            ).status_code,
            409,
        )

    def test_preview_tokens_expire_and_are_bound_to_reviewer(self):
        self.setUp_entry()
        url = reverse("catalogue-overlay", args=[self.capture.pk])
        token = self.client.get(url).context["token"]
        with patch("django.core.signing.time.time", return_value=10**11):
            self.assertContains(
                self.client.post(
                    url,
                    {
                        "action": "confirm",
                        "token": token,
                        "reason": "Apply",
                    },
                ),
                "invalid or expired",
                status_code=400,
            )
        second = get_user_model().objects.create_superuser("second-reviewer")
        self.client.force_login(second)
        self.assertContains(
            self.client.post(
                url,
                {
                    "action": "confirm",
                    "token": token,
                    "reason": "Apply",
                },
            ),
            "another reviewer",
            status_code=400,
        )
        self.assertFalse(CatalogueOverlayDecision.objects.exists())

    def test_catalogue_browsing_search_and_overlay_history_link(self):
        self.setUp_entry(
            {
                "people": [
                    {"source_name": "Writer", "name": "Correct Writer", "role": "author"},
                ]
            }
        )
        author = CanonicalAuthor.objects.create(name="Obsolete Identity")
        CatalogueAuthor.objects.create(
            entry=self.entry,
            author=author,
            source_name="Original author",
            reviewed_by=self.reviewer,
        )
        self.apply()
        url = reverse("catalogue")
        response = self.client.get(url, {"q": "Correct Writer", "group": "author", "then": ""})
        self.assertEqual(response.context["total_count"], 1)
        response = self.client.get(url, {"q": "Obsolete Identity"})
        self.assertEqual(response.context["total_count"], 0)
        response = self.client.get(
            url,
            {"q": "Correct Writer", "branch": '["Correct Writer"]', "group": "author", "then": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("catalogue-overlay", args=[self.capture.pk]))
        self.assertContains(response, "Reviewed catalogue overlay")

    def test_metadata_rebuild_preserves_overlay_and_undo_evidence(self):
        from io import StringIO

        from django.core.management import call_command

        self.setUp_entry({"language": "fr", "title": "Reviewed title"})
        self.apply()
        call_command("rebuild_catalogue_metadata", stdout=StringIO(), stderr=StringIO())
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.language, "fr")
        self.assertEqual(self.entry.title, "Reviewed title")
        self.assertEqual(CatalogueOverlayDecision.objects.count(), 1)

    def test_unrelated_entries_and_saved_correction_changes_are_not_implicitly_applied(self):
        self.setUp_entry()
        other = CatalogueEntry.objects.create(
            site=self.capture.site, url=self.capture.url + "other", title="Other work"
        )
        self.apply()
        save_correction(self.capture, self.reviewer, {}, 1, "Reset source correction")
        self.entry.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(self.entry.title, "Reviewed title")
        self.assertEqual(other.title, "Other work")
        with self.assertRaisesMessage(ValueError, "no catalogue metadata"):
            proposal(self.capture)
        commit(
            self.capture,
            self.reviewer,
            binding(proposal(self.capture, undo=True)),
            "Remove overlay",
        )
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.title, "Original title")
