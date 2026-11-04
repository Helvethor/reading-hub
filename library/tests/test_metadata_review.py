from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.db import connection
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from library.catalogue_views import group_keys
from library.management.commands.propose_catalogue_metadata import retained_captures
from library.models import (
    AuthorAlias,
    CanonicalAuthor,
    CatalogueAuthor,
    CatalogueEntry,
    CrawlCapture,
    CrawlSite,
    MetadataReviewEvent,
    MetadataSuggestion,
)
from library.services.catalogue import configured_sites
from library.services.fetch import Response
from library.services.metadata_review import candidate_author_matches, normalize_author_name
from library.services.storage import save_response
from library.tests.test_sources import PARAGRAPH


class RetainedCaptureConcurrencyTests(TransactionTestCase):
    def test_processing_a_capture_does_not_hold_a_read_lock_against_workers(self):
        site = configured_sites().get(host="communistusa.org")
        CrawlCapture.objects.bulk_create(
            [
                CrawlCapture(site=site, url=f"https://communistusa.org/{index}/", response={})
                for index in range(101)
            ]
        )
        captures = retained_captures(CrawlCapture.objects.order_by("-captured_at", "-pk"))
        first = next(captures)
        other = connection.copy()
        try:
            with other.cursor() as cursor:
                cursor.execute(
                    "UPDATE library_crawlcapture SET url = url WHERE id = %s", [first.pk]
                )
        finally:
            other.close()
        self.assertEqual(len(list(captures)), 100)


class MetadataReviewTests(TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        setting = override_settings(DATA_DIR=Path(temp.name))
        setting.enable()
        self.addCleanup(setting.disable)
        configured_sites()
        self.site = CrawlSite.objects.get(host="communistusa.org")
        self.reviewer = get_user_model().objects.create_user("reviewer", password="test")
        self.reviewer.groups.add(Group.objects.get(name="Metadata reviewers"))
        self.client = Client()
        self.client.force_login(self.reviewer)

    def add_capture(self, url, title="Test article"):
        markup = (
            '<html lang="en"><head><meta property="og:title" content="'
            + title
            + '"><meta name="author" content="Fredrick Engels">'
            '</head><body><time datetime="1917-10-25"></time>'
            '<div class="et_pb_post_content"><p>' + PARAGRAPH + "</p></div></body></html>"
        ).encode()
        response = Response(url, markup, "text/html", {})
        saved = save_response(response, url)
        capture = CrawlCapture.objects.create(site=self.site, url=url, response=saved)
        entry = CatalogueEntry.objects.create(site=self.site, url=url, title=title)
        return capture, entry

    def test_review_group_can_access_global_queue_but_regular_users_cannot(self):
        MetadataSuggestion.objects.create(
            field=MetadataSuggestion.Field.AUTHOR,
            value="Fredrick Engels",
            normalized_value="fredrick engels",
            method="test",
            fingerprint="a" * 64,
        )
        response = self.client.get(reverse("metadata-review"), {"language": "all"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fredrick Engels")

        regular = get_user_model().objects.create_user("reader", password="test")
        self.client.force_login(regular)
        self.assertEqual(self.client.get(reverse("metadata-review")).status_code, 403)

    def test_offline_candidate_command_preserves_evidence_and_does_not_apply_facts(self):
        capture, entry = self.add_capture("https://communistusa.org/sample/")
        with patch("library.services.fetch.Fetcher.fetch", side_effect=AssertionError("network")):
            call_command(
                "propose_catalogue_metadata",
                host="communistusa.org",
                limit=10,
                stdout=None,
            )
        suggestions = MetadataSuggestion.objects.filter(capture=capture)
        author = suggestions.get(field=MetadataSuggestion.Field.AUTHOR)
        date = suggestions.get(field=MetadataSuggestion.Field.PUBLISHED)
        self.assertEqual(author.value, "Fredrick Engels")
        self.assertEqual(author.evidence[0]["url"], capture.url)
        self.assertEqual(date.value, "1917-10-25")
        self.assertEqual(date.date_type, MetadataSuggestion.DateType.PUBLICATION)
        entry.refresh_from_db()
        self.assertEqual(entry.author, "")
        self.assertEqual(entry.published, "")
        self.assertTrue(all(suggestion.status == "pending" for suggestion in suggestions))

    def test_approving_author_alias_links_all_exact_uses_without_rewriting_byline(self):
        _, first = self.add_capture("https://communistusa.org/first/", "First work")
        _, second = self.add_capture("https://communistusa.org/second/", "Second work")
        first.author = "Fredrick Engels"
        first.authors = ["Fredrick Engels"]
        first.save(update_fields=["author", "authors"])
        second.author = "Fredrick Engels"
        second.authors = ["Fredrick Engels"]
        second.save(update_fields=["author", "authors"])
        suggestion = MetadataSuggestion.objects.create(
            field=MetadataSuggestion.Field.AUTHOR,
            value="Fredrick Engels",
            normalized_value="fredrick engels",
            method="test",
            fingerprint="b" * 64,
        )
        response = self.client.post(
            reverse("metadata-review-decision", args=[suggestion.pk]),
            {
                "action": "approve",
                "canonical_name": "Friedrich Engels",
                "authority_uri": "https://www.wikidata.org/entity/Q7338",
            },
        )
        self.assertEqual(response.status_code, 302)
        suggestion.refresh_from_db()
        author = CanonicalAuthor.objects.get(name="Friedrich Engels")
        self.assertEqual(author.authority_uri, "https://www.wikidata.org/entity/Q7338")
        self.assertTrue(AuthorAlias.objects.filter(author=author, name="Fredrick Engels").exists())
        self.assertEqual(CatalogueAuthor.objects.filter(author=author).count(), 2)
        self.assertEqual(suggestion.status, MetadataSuggestion.Status.APPROVED)
        first.refresh_from_db()
        self.assertEqual(first.author, "Fredrick Engels")

    def test_date_type_is_retained_and_writing_date_does_not_become_publication_date(self):
        _, entry = self.add_capture("https://communistusa.org/dates/")
        suggestion = MetadataSuggestion.objects.create(
            entry=entry,
            field=MetadataSuggestion.Field.PUBLISHED,
            value="1847",
            date_type=MetadataSuggestion.DateType.WRITTEN,
            evidence=[{"excerpt": "Written: 1847"}],
            method="archive-labelled-date",
            fingerprint="c" * 64,
        )
        queue = self.client.get(
            reverse("metadata-review"), {"field": "published", "language": "all"}
        )
        self.assertContains(queue, "Written date: 1847")
        response = self.client.post(
            reverse("metadata-review-decision", args=[suggestion.pk]) + "?field=published",
            {"action": "approve"},
        )
        self.assertEqual(response["Location"], "/metadata/review/?field=published")
        entry.refresh_from_db()
        suggestion.refresh_from_db()
        self.assertEqual(entry.published, "")
        self.assertEqual(suggestion.status, MetadataSuggestion.Status.APPROVED)
        self.assertEqual(suggestion.date_type, MetadataSuggestion.DateType.WRITTEN)

    def test_rejecting_candidate_only_records_the_review_decision(self):
        _, entry = self.add_capture("https://communistusa.org/topic/")
        suggestion = MetadataSuggestion.objects.create(
            entry=entry,
            field=MetadataSuggestion.Field.TOPIC,
            value="Marxist theory",
            evidence=[{"excerpt": "Marxist theory"}],
            method="test",
            fingerprint="d" * 64,
        )
        self.client.post(
            reverse("metadata-review-decision", args=[suggestion.pk]), {"action": "reject"}
        )
        suggestion.refresh_from_db()
        entry.refresh_from_db()
        self.assertEqual(suggestion.status, MetadataSuggestion.Status.REJECTED)
        self.assertEqual(entry.topics, [])

    def test_author_alias_normalization_handles_accents_and_punctuation(self):
        self.assertEqual(normalize_author_name("Friedrich Engels"), "friedrich engels")
        self.assertEqual(normalize_author_name("Róża Luxemburg"), "róża luxemburg")

    def test_background_approval_returns_author_and_does_not_queue_flash_messages(self):
        suggestion = MetadataSuggestion.objects.create(
            field="author", value="Lenin", method="test", fingerprint="4" * 64
        )
        url = reverse("metadata-review-decision", args=[suggestion.pk])
        response = self.client.post(
            url,
            {"action": "approve", "canonical_name": "Vladimir Lenin"},
            HTTP_ACCEPT="application/json",
        )
        person = CanonicalAuthor.objects.get(name="Vladimir Lenin")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "changed": True,
                "status": "approved",
                "author": {"id": person.pk, "name": person.name},
            },
        )
        again = self.client.post(url, {"action": "approve"}, HTTP_ACCEPT="application/json")
        self.assertEqual(again.status_code, 200)
        self.assertFalse(again.json()["changed"])
        self.assertEqual(again.json()["status"], "approved")
        self.assertEqual(CanonicalAuthor.objects.count(), 1)
        page = self.client.get(reverse("metadata-review"))
        self.assertNotContains(page, "Metadata decision recorded.")

    def test_background_rejection_and_validation_error(self):
        suggestion = MetadataSuggestion.objects.create(
            field="author", value="Lenin", method="test", fingerprint="5" * 64
        )
        url = reverse("metadata-review-decision", args=[suggestion.pk])
        invalid = self.client.post(
            url,
            {"action": "approve", "authority_uri": "invalid"},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertIn("valid authority", invalid.json()["error"])
        suggestion.refresh_from_db()
        self.assertEqual(suggestion.status, "pending")
        self.assertFalse(CanonicalAuthor.objects.exists())
        rejected = self.client.post(url, {"action": "reject"}, HTTP_ACCEPT="application/json")
        self.assertEqual(rejected.json(), {"changed": True, "status": "rejected", "author": None})

    def test_background_decisions_require_permission_and_csrf(self):
        suggestion = MetadataSuggestion.objects.create(
            field="author", value="Lenin", method="test", fingerprint="6" * 64
        )
        url = reverse("metadata-review-decision", args=[suggestion.pk])
        regular = get_user_model().objects.create_user("non-reviewer")
        self.client.force_login(regular)
        self.assertEqual(
            self.client.post(
                url, {"action": "approve"}, HTTP_ACCEPT="application/json"
            ).status_code,
            403,
        )
        guarded = Client(enforce_csrf_checks=True)
        guarded.force_login(self.reviewer)
        self.assertEqual(
            guarded.post(url, {"action": "approve"}, HTTP_ACCEPT="application/json").status_code,
            403,
        )
        suggestion.refresh_from_db()
        self.assertEqual(suggestion.status, "pending")

    def test_dry_run_deduplicates_authors_and_never_links_reviewed_aliases(self):
        self.add_capture("https://communistusa.org/first-dry/")
        self.add_capture("https://communistusa.org/second-dry/")
        output = StringIO()
        call_command("propose_catalogue_metadata", host=self.site.host, dry_run=True, stdout=output)
        self.assertIn("1 author, 2 published", output.getvalue())
        self.assertFalse(MetadataSuggestion.objects.exists())
        person = CanonicalAuthor.objects.create(name="Friedrich Engels")
        AuthorAlias.objects.create(
            author=person,
            reviewed_by=self.reviewer,
            name="Fredrick Engels",
            normalized_name="fredrick engels",
            surname_key="engels",
        )
        call_command(
            "propose_catalogue_metadata", host=self.site.host, dry_run=True, stdout=StringIO()
        )
        self.assertFalse(CatalogueAuthor.objects.exists())
        self.assertFalse(MetadataSuggestion.objects.exists())

    def test_reviewed_capture_author_is_visible_when_listing_byline_is_empty(self):
        capture, entry = self.add_capture("https://communistusa.org/empty-byline/")
        call_command("propose_catalogue_metadata", host=self.site.host, stdout=StringIO())
        suggestion = MetadataSuggestion.objects.get(field=MetadataSuggestion.Field.AUTHOR)
        self.client.post(
            reverse("metadata-review-decision", args=[suggestion.pk]),
            {"action": "approve", "canonical_name": "Friedrich Engels"},
        )
        self.assertTrue(CatalogueAuthor.objects.filter(entry=entry).exists())
        self.assertEqual(group_keys(entry, "author", {}), ["Friedrich Engels"])
        entry.refresh_from_db()
        self.assertEqual(entry.author, "")
        response = self.client.get(
            reverse("catalogue"),
            {
                "q": "Friedrich Engels",
                "group": "author",
                "then": "",
                "branch": '["Friedrich Engels"]',
            },
        )
        self.assertContains(response, entry.title)
        self.assertContains(response, "Friedrich Engels")
        self.assertEqual(suggestion.capture_id, capture.pk)

    def test_review_links_normalized_whitespace_variants(self):
        _, entry = self.add_capture("https://communistusa.org/whitespace/")
        entry.authors = ["Fredrick  Engels"]
        entry.save(update_fields=["authors"])
        suggestion = MetadataSuggestion.objects.create(
            field=MetadataSuggestion.Field.AUTHOR,
            value="Fredrick Engels",
            normalized_value="fredrick engels",
            method="test",
            fingerprint="e" * 64,
        )
        self.client.post(
            reverse("metadata-review-decision", args=[suggestion.pk]),
            {"action": "approve", "canonical_name": "Friedrich Engels"},
        )
        self.assertTrue(CatalogueAuthor.objects.filter(entry=entry).exists())

    def test_author_candidates_match_spelling_variants_by_surname(self):
        person = CanonicalAuthor.objects.create(name="Friedrich Engels")
        AuthorAlias.objects.create(
            author=person,
            reviewed_by=self.reviewer,
            name="Friedrich Engels",
            normalized_name="friedrich engels",
            surname_key="engels",
        )
        matches = candidate_author_matches("Fredrick Engels")
        self.assertEqual(matches[0][0], person)
        self.assertGreater(matches[0][1], 0.55)

    def test_matching_canonical_name_after_approving_a_short_alias(self):
        first = MetadataSuggestion.objects.create(
            field=MetadataSuggestion.Field.AUTHOR,
            value="Lenin",
            method="test",
            fingerprint="f" * 64,
        )
        self.client.post(
            reverse("metadata-review-decision", args=[first.pk]),
            {"action": "approve", "canonical_name": "Vladimir Lenin"},
        )
        person = CanonicalAuthor.objects.get(name="Vladimir Lenin")
        self.assertEqual(candidate_author_matches("Vladimir Lenin"), [(person, 1.0)])
        second = MetadataSuggestion.objects.create(
            field=MetadataSuggestion.Field.AUTHOR,
            value="Vladimir Lenin",
            method="test",
            fingerprint="1" * 64,
        )
        response = self.client.get(
            reverse("metadata-review"), {"field": "author", "language": "all"}
        )
        self.assertContains(
            response,
            f'<option value="{person.pk}" selected>Vladimir Lenin (similarity 1.00)</option>',
            html=True,
        )
        self.client.post(
            reverse("metadata-review-decision", args=[second.pk]),
            {"action": "approve", "author_id": person.pk},
        )
        self.assertEqual(CanonicalAuthor.objects.count(), 1)
        self.assertEqual(
            set(person.aliases.values_list("name", flat=True)), {"Lenin", "Vladimir Lenin"}
        )

    def test_correcting_artifacts_keeps_original_evidence_and_existing_person_name(self):
        _, entry = self.add_capture("https://communistusa.org/artifact/")
        entry.author = "Lenin [0]"
        entry.authors = ["Lenin [0]"]
        entry.save(update_fields=["author", "authors"])
        person = CanonicalAuthor.objects.create(name="Vladimir Lenin")
        suggestion = MetadataSuggestion.objects.create(
            field=MetadataSuggestion.Field.AUTHOR,
            value="Lenin [0]",
            method="test",
            fingerprint="3" * 64,
            evidence=[{"url": entry.url, "excerpt": "Lenin [0]"}],
        )
        self.client.post(
            reverse("metadata-review-decision", args=[suggestion.pk]),
            {
                "action": "approve",
                "author_id": person.pk,
                "canonical_name": "This must not rename the existing person",
            },
        )
        person.refresh_from_db()
        suggestion.refresh_from_db()
        self.assertEqual(person.name, "Vladimir Lenin")
        self.assertEqual(suggestion.value, "Lenin [0]")
        self.assertEqual(suggestion.evidence[0]["excerpt"], "Lenin [0]")
        self.assertEqual(person.aliases.get().name, "Lenin [0]")
        self.assertEqual(group_keys(entry, "author", {}), ["Vladimir Lenin"])

    def test_rejected_author_is_retained_and_not_requeued(self):
        self.add_capture("https://communistusa.org/rejected-author/")
        call_command("propose_catalogue_metadata", host=self.site.host, stdout=StringIO())
        suggestion = MetadataSuggestion.objects.get(field=MetadataSuggestion.Field.AUTHOR)
        evidence = suggestion.evidence
        self.client.post(
            reverse("metadata-review-decision", args=[suggestion.pk]), {"action": "reject"}
        )
        call_command("propose_catalogue_metadata", host=self.site.host, stdout=StringIO())
        suggestion.refresh_from_db()
        self.assertEqual(suggestion.status, MetadataSuggestion.Status.REJECTED)
        self.assertEqual(suggestion.reviewed_by, self.reviewer)
        self.assertIsNotNone(suggestion.reviewed_at)
        self.assertEqual(suggestion.evidence, evidence)
        self.assertEqual(MetadataSuggestion.objects.filter(field="author").count(), 1)
        self.assertFalse(AuthorAlias.objects.exists())
        self.assertFalse(CatalogueAuthor.objects.exists())
        self.assertContains(
            self.client.get(reverse("metadata-review"), {"status": "rejected", "language": "all"}),
            "Fredrick Engels",
        )

    def test_all_existing_people_are_selectable_without_a_similarity_match(self):
        person = CanonicalAuthor.objects.create(name="Vladimir Lenin")
        MetadataSuggestion.objects.create(
            field=MetadataSuggestion.Field.AUTHOR,
            value="A different script or pen name",
            method="test",
            fingerprint="2" * 64,
        )
        self.assertEqual(candidate_author_matches("A different script or pen name"), [])
        response = self.client.get(
            reverse("metadata-review"), {"field": "author", "language": "all"}
        )
        self.assertContains(response, 'label="Other existing people"')
        self.assertContains(
            response, f'<option value="{person.pk}">Vladimir Lenin</option>', html=True
        )

    def test_review_language_defaults_and_filters_preserve_other_evidence(self):
        archive = configured_sites().get(host="www.marxists.org")
        for code, section in [("de", "deutsch"), ("fr", "francais"), ("da", "dansk")]:
            capture = CrawlCapture.objects.create(
                site=archive, url=f"https://www.marxists.org/{section}/sample.htm", response={}
            )
            MetadataSuggestion.objects.create(
                capture=capture,
                field="author",
                value=f"Person {code}",
                method="test",
                fingerprint=code * 32,
            )
        _, entry = self.add_capture("https://communistusa.org/english/")
        entry.language = "en"
        entry.save(update_fields=["language"])
        MetadataSuggestion.objects.create(
            entry=entry, field="topic", value="English topic", method="test", fingerprint="en" * 32
        )
        page = self.client.get(reverse("metadata-review"))
        self.assertContains(page, "Person de")
        self.assertContains(page, "Person fr")
        self.assertContains(page, "English topic")
        self.assertNotContains(page, "Person da")
        french = self.client.get(reverse("metadata-review"), {"language": "fr"})
        self.assertContains(french, "Person fr")
        self.assertNotContains(french, "Person de")
        self.assertContains(
            self.client.get(reverse("metadata-review"), {"language": "all"}), "Person da"
        )
        self.assertEqual(MetadataSuggestion.objects.count(), 4)
        self.assertEqual(
            self.client.get(reverse("metadata-review"), {"language": "bad"}).status_code, 404
        )

    def test_reopen_preserves_decisions_and_does_not_apply_metadata(self):
        suggestion = MetadataSuggestion.objects.create(
            field="author", value="Test Person", method="test", fingerprint="7" * 64
        )
        url = reverse("metadata-review-decision", args=[suggestion.pk])
        self.client.post(url, {"action": "reject"})
        rejected_at = MetadataReviewEvent.objects.get().created_at
        invalid = self.client.post(url, {"action": "reopen"}, HTTP_ACCEPT="application/json")
        self.assertEqual(invalid.status_code, 400)
        reopened = self.client.post(
            url,
            {"action": "reopen", "reason": "Review the source again"},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(reopened.json(), {"changed": True, "status": "pending", "author": None})
        suggestion.refresh_from_db()
        self.assertIsNone(suggestion.reviewed_by)
        self.assertIsNone(suggestion.reviewed_at)
        events = list(suggestion.review_events.all())
        self.assertEqual([event.status for event in events], ["rejected", "pending"])
        self.assertEqual(events[0].created_at, rejected_at)
        self.assertEqual(events[1].reason, "Review the source again")
        repeated = self.client.post(
            url, {"action": "reopen", "reason": "Retry"}, HTTP_ACCEPT="application/json"
        )
        self.assertFalse(repeated.json()["changed"])
        self.assertEqual(suggestion.review_events.count(), 2)
        self.assertFalse(AuthorAlias.objects.exists())
        self.assertFalse(CatalogueAuthor.objects.exists())
        self.client.post(url, {"action": "approve", "canonical_name": "Test Person"})
        denied = self.client.post(
            url, {"action": "reopen", "reason": "Undo"}, HTTP_ACCEPT="application/json"
        )
        self.assertEqual(denied.status_code, 400)
        self.assertEqual(suggestion.review_events.count(), 3)

    def test_legacy_rejection_is_preserved_before_reopening(self):
        from django.utils import timezone

        timestamp = timezone.now()
        suggestion = MetadataSuggestion.objects.create(
            field="author",
            value="Legacy",
            method="test",
            fingerprint="8" * 64,
            status="rejected",
            reviewed_by=self.reviewer,
            reviewed_at=timestamp,
        )
        response = self.client.post(
            reverse("metadata-review-decision", args=[suggestion.pk]),
            {"action": "reopen", "reason": "Recheck legacy evidence"},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(suggestion.review_events.first().created_at, timestamp)
        self.assertEqual(suggestion.review_events.first().status, "rejected")
        page = self.client.get(reverse("metadata-review"), {"language": "all"})
        self.assertContains(page, "Decision history")
        self.assertContains(page, "Recheck legacy evidence")

    def test_reopen_requires_reviewer_and_csrf(self):
        suggestion = MetadataSuggestion.objects.create(
            field="author",
            value="Rejected",
            method="test",
            fingerprint="9" * 64,
            status="rejected",
        )
        url = reverse("metadata-review-decision", args=[suggestion.pk])
        guarded = Client(enforce_csrf_checks=True)
        guarded.force_login(self.reviewer)
        self.assertEqual(
            guarded.post(url, {"action": "reopen", "reason": "Recheck"}).status_code, 403
        )
        regular = get_user_model().objects.create_user("reopen-reader")
        self.client.force_login(regular)
        self.assertEqual(
            self.client.post(url, {"action": "reopen", "reason": "Recheck"}).status_code, 403
        )
        suggestion.refresh_from_db()
        self.assertEqual(suggestion.status, "rejected")
        self.assertEqual(suggestion.review_events.count(), 0)

    def test_recorded_language_takes_precedence_over_archive_section_fallback(self):
        archive = configured_sites().get(host="www.marxists.org")
        capture = CrawlCapture.objects.create(
            site=archive, url="https://www.marxists.org/francais/test.htm", response={}
        )
        entry = CatalogueEntry.objects.create(
            site=archive,
            url=capture.url,
            title="Non-French content",
            language="da",
        )
        MetadataSuggestion.objects.create(
            capture=capture,
            entry=entry,
            field="author",
            value="Danish evidence",
            method="test",
            fingerprint="a1" * 32,
        )
        self.assertNotContains(self.client.get(reverse("metadata-review")), "Danish evidence")
        self.assertContains(
            self.client.get(reverse("metadata-review"), {"language": "all"}), "Danish evidence"
        )

    def test_catalogue_group_uses_reviewed_name_and_keeps_unmatched_coauthors(self):
        _, entry = self.add_capture("https://communistusa.org/coauthors/")
        entry.authors = ["Fredrick Engels", "Unmapped Author"]
        entry.author = "Fredrick Engels and Unmapped Author"
        entry.save(update_fields=["authors", "author"])
        person = CanonicalAuthor.objects.create(name="Friedrich Engels")
        CatalogueAuthor.objects.create(
            entry=entry,
            author=person,
            source_name="Fredrick Engels",
            reviewed_by=self.reviewer,
        )

        self.assertEqual(
            group_keys(entry, "author", {}),
            ["Friedrich Engels", "Unmapped Author"],
        )
