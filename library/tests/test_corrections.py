import json
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from library.correction_views import parsed_people, preview
from library.models import (
    AuthorAlias,
    CanonicalAuthor,
    CatalogueEntry,
    CrawlCapture,
    Job,
    MetadataSuggestion,
    PageTypeDecision,
    SourceCorrection,
)
from library.profile import get_profile
from library.services.catalogue import configured_sites
from library.services.corrections import (
    SCHEMA_VERSION,
    CorrectionConflict,
    apply_expected,
    apply_retained_correction,
    block_rows,
    extraction,
    save_correction,
    validate_expected,
)
from library.services.errors import ImportFailure
from library.services.fetch import Response
from library.services.pipeline import claim_job, enqueue, process_job
from library.services.storage import save_response
from library.tests.test_sources import ARTICLE, BOOK, article_html, book_index, chapter


class CorrectionTests(TestCase):
    def test_subtitle_metadata_can_be_reviewed_cleared_and_validated(self):
        source, part, body, _ = extraction(self.capture)
        for subtitle in ("Exact Subtitle", ""):
            expected = {"metadata": {"subtitle": subtitle}}
            validate_expected(expected, body, source)
            result = preview(source, part, body, expected)
            self.assertEqual(result["metadata"]["subtitle"], subtitle)
        for subtitle in (None, 2, [], "a" * 1001):
            with self.subTest(subtitle=type(subtitle)):
                with self.assertRaisesMessage(ValueError, "subtitle"):
                    validate_expected({"metadata": {"subtitle": subtitle}}, body, source)
        saved = save_correction(
            self.capture, self.reviewer, {"metadata": {"subtitle": "Reviewed subtitle"}},
            0, "Checked source subtitle",
        )
        self.assertEqual(saved.expected["metadata"]["subtitle"], "Reviewed subtitle")
        response = self.client.get(reverse("correction-workspace", args=[self.capture.pk]))
        self.assertRedirects(response, reverse("work-review"), fetch_redirect_response=False)
        history = self.client.get(reverse("correction-revisions", args=[self.capture.pk]))
        self.assertContains(history, "Reviewed subtitle")
        self.assertContains(history, saved.source_digest)

    def test_retained_lookup_fetches_only_latest_revision_with_capture_and_site(self):
        for revision in range(3):
            save_correction(
                self.capture,
                self.reviewer,
                {"metadata": {"title": f"Reviewed {revision}"}},
                revision,
                "Review",
            )
        latest = save_correction(self.capture, self.reviewer, {}, 3, "Reset")
        source, _, body, _ = extraction(self.capture)
        original_title = source.title
        with self.assertNumQueries(1) as queries:
            result = apply_retained_correction(source, body, self.capture.response, metadata=True)
            self.assertEqual(result.capture.site.profile, get_profile().key)
        self.assertEqual(result.pk, latest.pk)
        self.assertEqual(source.title, original_title)
        self.assertIn("LIMIT 1", queries.captured_queries[0]["sql"].upper())

    def test_retained_lookup_preserves_explicit_correction_iterables(self):
        correction = save_correction(
            self.capture, self.reviewer, {"metadata": {"title": "Explicit"}}, 0, "Review"
        )
        source, _, body, _ = extraction(self.capture)
        with self.assertNumQueries(0):
            result = apply_retained_correction(
                source, body, self.capture.response, metadata=True, corrections=[correction]
            )
        self.assertEqual(result.pk, correction.pk)
        self.assertEqual(source.title, "Explicit")

    def test_dividers_are_editable_without_renumbering_existing_blocks(self):
        from bs4 import BeautifulSoup

        body = BeautifulSoup(
            "<div>Unwrapped intro<p>Before</p><hr><h4>Section one</h4>"
            "<p>Body</p><hr><h4>Section two</h4></div>",
            "html.parser",
        ).div
        without_dividers = BeautifulSoup(str(body), "html.parser").div
        for divider in without_dividers.select("hr"):
            divider.decompose()
        original = block_rows(without_dividers)
        rows = block_rows(body)
        self.assertEqual(rows[: len(original)], original)
        self.assertEqual([row["tag"] for row in rows[len(original) :]], ["hr", "hr"])
        self.assertEqual(rows[len(original)]["text"], "Horizontal divider before: Section one")
        source, part, _, _ = extraction(self.capture)
        expected = {"blocks": [{"index": len(original), "action": "exclude"}]}
        validate_expected(expected, body, source)
        result = preview(source, part, body, expected)
        parsed = BeautifulSoup(result["html"], "html.parser")
        self.assertEqual(len(parsed.select("hr")), 1)
        self.assertIn("Section one", parsed.get_text())
        self.assertEqual(len(body.select("hr")), 2)
        apply_expected(
            source,
            body,
            {
                "blocks": [
                    {"index": 0, "action": "h2"},
                    {"index": len(original), "action": "exclude"},
                ]
            },
        )
        self.assertEqual(body.select_one("h2").get_text(), "Before")
        self.assertEqual(len(body.select("hr")), 1)

    def test_page_type_classification_and_undo_apply_to_url_without_deleting_evidence(self):
        second = CrawlCapture.objects.create(
            site=self.capture.site,
            url=self.capture.url,
            response=self.capture.response,
        )
        other = CrawlCapture.objects.create(
            site=self.capture.site,
            url=ARTICLE + "other/",
            response=self.capture.response,
        )
        entry = CatalogueEntry.objects.create(
            site=self.capture.site, url=ARTICLE, title="Test work", language="en"
        )
        suggestion = MetadataSuggestion.objects.create(
            capture=self.capture,
            entry=entry,
            field="author",
            value="Test person",
            method="test",
            fingerprint="d" * 64,
        )
        endpoint = reverse("correction-page-type", args=[self.capture.pk])
        self.assertEqual(
            self.client.post(
                endpoint,
                {"action": "discovery", "reason": "Author bibliography", "revision": "0"},
            ).status_code,
            410,
        )
        from library.services.page_types import classify

        decision = classify(
            self.capture, self.reviewer, "discovery", "Author bibliography", "0"
        )
        for row in (self.capture, second, entry):
            row.refresh_from_db()
            self.assertTrue(row.discovery_only)
        other.refresh_from_db()
        self.assertFalse(other.discovery_only)
        self.assertEqual(PageTypeDecision.objects.get(), decision)
        self.assertEqual(decision.reviewer, self.reviewer)
        self.assertEqual(decision.reason, "Author bibliography")
        self.assertEqual(
            self.client.post(
                endpoint,
                {"action": "undo", "reason": "Mistaken page type", "revision": str(decision.pk)},
            ).status_code,
            410,
        )
        self.assertNotContains(self.client.get(reverse("metadata-review")), "Test person")
        history = self.client.get(reverse("correction-revisions", args=[self.capture.pk]))
        self.assertContains(history, "Page classification evidence (read-only)")
        self.assertContains(history, "Author bibliography")
        from library.services.page_types import is_discovery_page
        from library.sources.base import parse_html
        from profiles.marxist.catalogue import MarxistCatalogue

        self.assertTrue(
            is_discovery_page(
                MarxistCatalogue, parse_html(article_html()), ARTICLE, site=self.capture.site
            )
        )
        with self.assertRaisesMessage(ImportFailure, "discovery index"):
            enqueue(ARTICLE)
        from library.services.page_types import classify

        classify(
            self.capture,
            self.reviewer,
            "undo",
            "Mistaken page type",
            str(decision.pk),
        )
        for row in (self.capture, second, entry):
            row.refresh_from_db()
            self.assertFalse(row.discovery_only)
        self.assertEqual(PageTypeDecision.objects.count(), 2)
        suggestion.refresh_from_db()
        self.assertEqual(suggestion.status, "pending")
        self.assertContains(self.client.get(reverse("metadata-review")), "Test person")
        self.assertFalse(
            is_discovery_page(
                MarxistCatalogue, parse_html(article_html()), ARTICLE, site=self.capture.site
            )
        )

    def test_page_type_requires_permission_csrf_reason_and_current_revision(self):
        endpoint = reverse("correction-page-type", args=[self.capture.pk])
        self.assertEqual(self.client.get(endpoint).status_code, 405)
        response = self.client.post(
            endpoint, {"action": "discovery", "reason": "Index", "revision": "0"}
        )
        self.assertEqual(response.status_code, 410)
        self.assertFalse(PageTypeDecision.objects.exists())
        from library.services.page_types import classify

        with self.assertRaisesMessage(ValueError, "1-2000"):
            classify(self.capture, self.reviewer, "discovery", "", "0")
        classify(self.capture, self.reviewer, "discovery", "Index", "0")
        with self.assertRaisesMessage(ValueError, "changed since"):
            classify(self.capture, self.reviewer, "undo", "Stale form", "0")
        self.assertEqual(PageTypeDecision.objects.count(), 1)
        self.capture.refresh_from_db()
        self.assertTrue(self.capture.discovery_only)
        untrusted = Client()
        untrusted.force_login(get_user_model().objects.create_user("reader"))
        self.assertEqual(untrusted.post(endpoint, {}).status_code, 403)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.reviewer)
        self.assertEqual(csrf_client.post(endpoint, {}).status_code, 403)

    def test_undo_restores_prior_flags_and_classifies_captures_created_after_the_decision(self):
        from library.services.page_types import classify

        self.capture.discovery_only = True
        self.capture.save(update_fields=["discovery_only"])
        decision = classify(self.capture, self.reviewer, "discovery", "Reviewed directory", "0")
        later = CrawlCapture.objects.create(
            site=self.capture.site,
            url=ARTICLE,
            response=self.capture.response,
            discovery_only=True,
        )
        classify(
            self.capture, self.reviewer, "undo", "Return to automatic detection", str(decision.pk)
        )
        self.capture.refresh_from_db()
        later.refresh_from_db()
        self.assertTrue(self.capture.discovery_only)
        self.assertFalse(later.discovery_only)

    def test_manual_classification_blocks_already_queued_import_and_offline_reformat(self):
        from library.services.page_types import classify
        from library.services.pipeline import prepare_pages

        job = enqueue(ARTICLE)
        classify(self.capture, self.reviewer, "discovery", "Listing, not prose", "0")
        with self.assertRaisesMessage(ImportFailure, "discovery index"):
            prepare_pages({"pages": [self.capture.response]})
        with patch("library.services.fetch.Fetcher.fetch") as fetch:
            self.assertIsNone(process_job(claim_job()))
        fetch.assert_not_called()
        job.refresh_from_db()
        self.assertEqual(job.status, Job.Status.FAILED)
        self.assertEqual(job.error_code, "discovery")

    def test_source_hyperlink_and_page_type_control_survive_extraction_error(self):
        url = reverse("correction-workspace", args=[self.capture.pk])
        response = self.client.get(url)
        self.assertRedirects(response, reverse("work-review"), fetch_redirect_response=False)
        mutation = self.client.post(
            reverse("correction-page-type", args=[self.capture.pk]),
            {"action": "discovery", "reason": "Unsupported layout", "revision": "0"},
        )
        self.assertEqual(mutation.status_code, 410)
        self.assertFalse(PageTypeDecision.objects.exists())

    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        setting = override_settings(DATA_DIR=Path(temp.name), ALLOWED_HOSTS=["testserver"])
        setting.enable()
        self.addCleanup(setting.disable)
        self.reviewer = get_user_model().objects.create_user("reviewer")
        self.reviewer.groups.add(Group.objects.get(name="Metadata reviewers"))
        self.client.force_login(self.reviewer)
        site = configured_sites().get(host="communistusa.org")
        self.capture = CrawlCapture.objects.create(
            site=site,
            url=ARTICLE,
            response=save_response(
                Response(ARTICLE, article_html("<p>Unwanted block</p>"), "text/html", {}),
                ARTICLE,
            ),
        )
        self.url = reverse("correction-update", args=[self.capture.pk])

    def edits(self):
        source, part, body, _ = extraction(self.capture)
        rows = block_rows(body)
        heading = next(row["index"] for row in rows if row["tag"].startswith("h"))
        unwanted = next(row["index"] for row in rows if row["text"] == "Unwanted block")
        return {
            "metadata": {
                "title": "Reviewed title",
                "language": "fr",
                "topics": ["Labour"],
                "dates": [{"value": "1848", "type": "publication"}],
                "people": [
                    {"name": "Friedrich Engels", "source_name": "Engels", "role": "author"},
                    {"name": "Jorn Andersen", "source_name": "Jorn Andersen", "role": "unknown"},
                ],
            },
            "blocks": [
                {"index": heading, "action": "h4"},
                {"index": unwanted, "action": "exclude"},
            ],
        }

    def test_workspace_and_export_require_reviewer_permission_and_csrf(self):
        regular = get_user_model().objects.create_user("reader")
        self.client.force_login(regular)
        for name in ("correction-workspace", "correction-export"):
            self.assertEqual(
                self.client.get(reverse(name, args=[self.capture.pk])).status_code, 403
            )
        self.assertEqual(
            self.client.post(self.url, "{}", content_type="application/json").status_code,
            403,
        )
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.reviewer)
        self.assertEqual(
            csrf.post(self.url, "{}", content_type="application/json").status_code, 403
        )
        self.client.force_login(self.reviewer)
        self.assertEqual(
            self.client.post(self.url, "{}", content_type="application/json").status_code, 410
        )
        self.assertFalse(SourceCorrection.objects.exists())

    def test_workspace_source_html_is_inert_and_preview_has_no_scripts(self):
        self.capture.response = save_response(
            Response(
                ARTICLE,
                article_html(
                    '<p onclick="alert(1)"><a href="https://example.org/">Safe text</a></p>'
                    '<script>alert(2)</script><iframe src="https://example.org/"></iframe>'
                    '<img src="https://example.org/x" onerror="alert(3)">'
                    "<p>Unwanted block</p>"
                ),
                "text/html",
                {},
            ),
            ARTICLE,
        )
        self.capture.save(update_fields=["response"])
        response = self.client.get(reverse("correction-workspace", args=[self.capture.pk]))
        self.assertRedirects(response, reverse("work-review"), fetch_redirect_response=False)
        source, part, body, _ = extraction(self.capture)
        expected = self.edits()
        validate_expected(expected, body, source)
        result = preview(source, part, body, expected)
        self.assertNotIn("Unwanted block", result["html"])
        self.assertEqual(result["title"], "Reviewed title")
        for unsafe in ("<script", "<iframe", "onclick=", "onerror=", "href=", "src="):
            self.assertNotIn(unsafe, result["html"])
        self.assertEqual(result["structure"]["toc"][0]["level"], 4)
        self.assertFalse(SourceCorrection.objects.exists())

    def test_save_preserves_baseline_and_records_complete_revisions(self):
        expected = self.edits()
        correction = save_correction(self.capture, self.reviewer, expected, 0, "Reviewed source")
        self.assertEqual(correction.revision, 1)
        self.assertEqual(correction.original["title"], "Test article")
        self.assertEqual(correction.expected, expected)
        self.assertEqual(correction.source_digest, self.capture.response["digest"])
        self.assertEqual(correction.reviewer, self.reviewer)
        reset = save_correction(self.capture, self.reviewer, {}, 1, "Reset")
        self.assertEqual(reset.revision, 2)
        self.assertEqual(SourceCorrection.objects.count(), 2)
        exported = self.client.get(reverse("correction-export", args=[self.capture.pk])).json()
        self.assertEqual(exported["dataset_schema"], SCHEMA_VERSION)
        self.assertEqual(len(exported["corrections"]), 2)
        self.assertEqual(exported["corrections"][1]["expected"], expected)
        self.assertNotIn("password", json.dumps(exported))

    def test_conflicting_reviewer_revision_does_not_overwrite_history(self):
        save_correction(self.capture, self.reviewer, {}, 0, "Initial")
        with self.assertRaises(CorrectionConflict):
            save_correction(
                self.capture,
                self.reviewer,
                {"metadata": {"title": "Other review"}},
                0,
                "Stale",
            )
        self.assertEqual(SourceCorrection.objects.count(), 1)
        with self.assertRaises(CorrectionConflict):
            save_correction(self.capture, self.reviewer, {}, 0, "")

    def test_review_shows_scoped_people_and_blocks_old_proposal_approval(self):
        suggestion = MetadataSuggestion.objects.create(
            capture=self.capture,
            field="author",
            value="A. Hennaut Wrong title",
            normalized_value="a hennaut wrong title",
            method="test",
            fingerprint="f" * 64,
        )
        expected = {
            "metadata": {
                "people": [
                    {"name": "Adhémar Hennaut", "source_name": "A. Hennaut", "role": "author"},
                    {"name": "Other person", "source_name": "Other", "role": "unknown"},
                ]
            }
        }
        correction = save_correction(self.capture, self.reviewer, expected, 0, "")
        target = reverse("metadata-review")
        response = self.client.get(target, {"language": "all"})
        self.assertContains(response, "Corrected attribution for this captured page")
        self.assertContains(response, "Adhémar Hennaut")
        self.assertContains(response, "Other person")
        self.assertContains(response, "Original parsed proposal")
        self.assertNotContains(response, 'value="approve"')
        decision = reverse("metadata-review-decision", args=[suggestion.pk])
        failed = self.client.post(decision, {"action": "approve"}, HTTP_ACCEPT="application/json")
        self.assertEqual(failed.status_code, 400)
        self.assertIn("saved people/roles correction", failed.json()["error"])
        self.assertFalse(CanonicalAuthor.objects.exists())
        self.assertFalse(AuthorAlias.objects.exists())
        self.assertEqual(
            self.client.post(
                decision, {"action": "reject"}, HTTP_ACCEPT="application/json"
            ).status_code,
            200,
        )
        correction.refresh_from_db()
        self.assertEqual(correction.expected, expected)
        suggestion.refresh_from_db()
        self.assertEqual(suggestion.value, "A. Hennaut Wrong title")
        self.assertEqual(suggestion.status, "rejected")

    def test_review_honours_reset_clear_and_stale_people_corrections(self):
        suggestion = MetadataSuggestion.objects.create(
            capture=self.capture,
            field="author",
            value="Original person",
            normalized_value="original person",
            method="test",
            fingerprint="e" * 64,
        )
        correction = save_correction(
            self.capture, self.reviewer, {"metadata": {"people": []}}, 0, ""
        )
        response = self.client.get(reverse("metadata-review"), {"language": "all"})
        self.assertContains(response, "Attribution explicitly cleared")
        SourceCorrection.objects.filter(pk=correction.pk).update(adapter_version="old")
        response = self.client.get(reverse("metadata-review"), {"language": "all"})
        self.assertContains(response, "needs revalidation")
        save_correction(self.capture, self.reviewer, {}, 1, "Reset")
        response = self.client.get(reverse("metadata-review"), {"language": "all"})
        self.assertNotContains(response, "Corrected attribution for this captured page")
        self.assertContains(response, 'value="approve"')
        suggestion.refresh_from_db()
        self.assertEqual(suggestion.status, "pending")

    def test_accept_saved_correction_resolves_review_with_exact_revision_audit(self):
        suggestion = MetadataSuggestion.objects.create(
            capture=self.capture,
            field="author",
            value="Broken name and title",
            normalized_value="broken name and title",
            method="test",
            fingerprint="d" * 64,
        )
        correction = save_correction(
            self.capture, self.reviewer, {"metadata": {"people": []}}, 0, "Clear attribution"
        )
        page = self.client.get(reverse("metadata-review"), {"language": "all"})
        self.assertContains(page, "Accept saved correction and resolve review")
        url = reverse("metadata-review-decision", args=[suggestion.pk])
        data = {"action": "accept_correction", "correction_id": str(correction.pk)}
        response = self.client.post(url, data, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["status"], "superseded")
        event = suggestion.review_events.get()
        self.assertEqual(event.correction, correction)
        self.assertEqual(event.reviewer, self.reviewer)
        self.assertEqual(event.previous_status, "pending")
        self.assertFalse(AuthorAlias.objects.exists())
        self.assertFalse(CanonicalAuthor.objects.exists())
        self.assertEqual(SourceCorrection.objects.count(), 1)
        repeat = self.client.post(url, data, HTTP_ACCEPT="application/json")
        self.assertFalse(repeat.json()["changed"])
        self.assertEqual(suggestion.review_events.count(), 1)
        self.assertNotContains(
            self.client.get(reverse("metadata-review"), {"language": "all"}), suggestion.value
        )
        history = self.client.get(
            reverse("metadata-review"), {"language": "all", "status": "superseded"}
        )
        self.assertContains(history, "Accepted correction revision 1")

    def test_accept_saved_correction_rejects_missing_changed_and_stale_revisions(self):
        suggestion = MetadataSuggestion.objects.create(
            capture=self.capture,
            field="author",
            value="Old proposal",
            normalized_value="old proposal",
            method="test",
            fingerprint="c" * 64,
        )
        url = reverse("metadata-review-decision", args=[suggestion.pk])
        data = {"action": "accept_correction", "correction_id": ""}
        self.assertEqual(
            self.client.post(url, data, HTTP_ACCEPT="application/json").status_code, 400
        )
        first = save_correction(self.capture, self.reviewer, {"metadata": {"people": []}}, 0, "")
        data["correction_id"] = str(first.pk)
        second = save_correction(self.capture, self.reviewer, {"metadata": {"people": []}}, 1, "")
        self.assertEqual(
            self.client.post(url, data, HTTP_ACCEPT="application/json").status_code, 400
        )
        data["correction_id"] = str(second.pk)
        original = second.original.copy()
        original["body_digest"] = "wrong"
        SourceCorrection.objects.filter(pk=second.pk).update(original=original)
        self.assertEqual(
            self.client.post(url, data, HTTP_ACCEPT="application/json").status_code, 400
        )
        SourceCorrection.objects.filter(pk=second.pk).update(
            original=second.original, adapter_version="old"
        )
        self.assertEqual(
            self.client.post(url, data, HTTP_ACCEPT="application/json").status_code, 400
        )
        suggestion.refresh_from_db()
        self.assertEqual(suggestion.status, "pending")
        self.assertFalse(suggestion.review_events.exists())

    def test_parsed_people_preserve_components_without_guessing_roles(self):
        self.assertEqual(
            parsed_people({"author": "Friedrich Engels / Jorn Andersen"}),
            [
                {
                    "name": "Friedrich Engels / Jorn Andersen",
                    "source_name": "Friedrich Engels / Jorn Andersen",
                    "role": "unknown",
                }
            ],
        )
        self.assertEqual(
            [person["role"] for person in parsed_people({"authors": ["Engels", "Andersen"]})],
            ["unknown", "unknown"],
        )
        self.assertEqual(parsed_people({"author": "Site", "author_is_fallback": True}), [])
        self.assertEqual(
            parsed_people(
                {"contributors": [{"name": "Editor", "role": "editor", "source_name": "Ed."}]}
            ),
            [{"name": "Editor", "role": "editor", "source_name": "Ed."}],
        )
        workspace = self.client.get(reverse("correction-workspace", args=[self.capture.pk]))
        self.assertRedirects(workspace, reverse("work-review"), fetch_redirect_response=False)
        self.assertFalse(SourceCorrection.objects.exists())

    def test_canonical_lookup_reuses_reviewed_alias_matches_without_changing_facts(self):
        author = CanonicalAuthor.objects.create(name="Vladimir Lenin")
        AuthorAlias.objects.create(
            author=author,
            reviewed_by=self.reviewer,
            name="Lenin",
            normalized_name="lenin",
            surname_key="lenin",
        )
        target = reverse("correction-person-matches")
        response = self.client.get(target, {"q": "Lenin"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["candidates"][0]["name"], "Vladimir Lenin")
        self.assertEqual(self.client.get(target, {"q": ""}).status_code, 400)
        self.assertEqual(self.client.get(target, {"q": "x" * 501}).status_code, 400)
        self.assertEqual(self.client.get(target, {"q": "Nobody"}).json()["candidates"], [])
        reader = get_user_model().objects.create_user("ordinary-person-lookup")
        self.client.force_login(reader)
        self.assertEqual(self.client.get(target, {"q": "Lenin"}).status_code, 403)
        self.assertFalse(SourceCorrection.objects.exists())
        self.assertEqual(AuthorAlias.objects.count(), 1)

    def test_canonical_person_selection_is_scoped_and_preserves_separate_roles(self):
        author = CanonicalAuthor.objects.create(
            name="Friedrich Engels", authority_uri="https://example.org/engels"
        )
        expected = self.edits()
        expected["metadata"]["people"][0]["canonical"] = {
            "name": author.name,
            "authority_uri": author.authority_uri,
        }
        expected["metadata"]["people"][0]["role"] = "translator"
        source, part, body, _ = extraction(self.capture)
        validate_expected(expected, body, source)
        result = preview(source, part, body, expected)
        self.assertEqual(result["metadata"]["authors"], [])
        contributors = result["metadata"]["contributors"]
        self.assertEqual(contributors[0]["canonical"]["name"], author.name)
        self.assertEqual(contributors[0]["role"], "translator")
        self.assertEqual(contributors[1]["role"], "unknown")
        self.assertFalse(AuthorAlias.objects.exists())
        save_correction(self.capture, self.reviewer, expected, 0, "Reviewed contributors")
        exported = self.client.get(reverse("correction-export", args=[self.capture.pk])).json()
        self.assertEqual(exported["corrections"][0]["schema_version"], SCHEMA_VERSION)
        self.assertEqual(exported["corrections"][0]["expected"], expected)
        expected["metadata"]["people"][0]["name"] = "Other name"
        with self.assertRaises(ValueError):
            validate_expected(expected, body, source)
        expected["metadata"]["people"][0]["name"] = author.name
        author.delete()
        with self.assertRaises(ValueError):
            validate_expected(expected, body, source)
        self.assertEqual(SourceCorrection.objects.count(), 1)

    def test_history_uses_latest_language_and_preserves_all_revisions(self):
        first = save_correction(
            self.capture,
            self.reviewer,
            {"metadata": {"language": "fr", "title": "French title"}},
            0,
            "First",
        )
        history = self.client.get(reverse("correction-history"))
        self.assertContains(history, "French title")
        self.assertContains(history, "1 corrected captures")
        second = save_correction(
            self.capture, self.reviewer, {"metadata": {"language": "da"}}, 1, "Danish"
        )
        self.assertContains(self.client.get(reverse("correction-history")), "0 corrected captures")
        all_history = self.client.get(reverse("correction-history"), {"language": "all"})
        self.assertContains(all_history, "1 corrected captures")
        self.assertEqual(all_history.context["page"].object_list[0].pk, second.pk)
        revisions = self.client.get(reverse("correction-revisions", args=[self.capture.pk]))
        self.assertContains(revisions, "Revision 1")
        self.assertContains(revisions, "Revision 2")
        self.assertContains(revisions, "French title")
        self.assertEqual(
            self.client.get(reverse("correction-revisions", args=[self.capture.pk])).status_code,
            200,
        )
        self.assertEqual(SourceCorrection.objects.count(), 2)
        self.assertEqual(first.expected["metadata"]["language"], "fr")
        self.assertEqual(
            self.client.get(reverse("correction-history"), {"language": "invalid"}).status_code, 404
        )

    def test_history_baseline_language_reset_permissions_and_pagination(self):
        self.capture.response = save_response(
            Response(
                ARTICLE, article_html().replace(b"<html>", b'<html lang="en">'), "text/html", {}
            ),
            ARTICLE,
        )
        self.capture.save(update_fields=["response"])
        for revision in range(22):
            save_correction(self.capture, self.reviewer, {}, revision, "Baseline")
        history = self.client.get(reverse("correction-history"))
        self.assertContains(history, "1 corrected captures")
        self.assertContains(history, "Reset to baseline")
        page = self.client.get(reverse("correction-revisions", args=[self.capture.pk]), {"page": 2})
        self.assertEqual(len(page.context["page"]), 2)
        self.assertContains(page, "Revision 1")
        regular = get_user_model().objects.create_user("history-reader")
        self.client.force_login(regular)
        self.assertEqual(self.client.get(reverse("correction-history")).status_code, 403)
        self.assertEqual(
            self.client.get(reverse("correction-revisions", args=[self.capture.pk])).status_code,
            403,
        )

    def test_date_editor_and_partial_date_round_trip(self):
        dates = [
            {"value": "1891", "type": "publication"},
            {"value": "1891-02", "type": "written"},
            {"value": "2000-02-29", "type": "online_edition"},
            {"value": "1892", "type": "unknown"},
        ]
        expected = {"metadata": {"dates": dates}}
        source, part, body, _ = extraction(self.capture)
        validate_expected(expected, body, source)
        result = preview(source, part, body, expected)
        self.assertEqual(result["metadata"]["date_facts"], dates)
        correction = save_correction(self.capture, self.reviewer, expected, 0, "Add date facts")
        workspace = self.client.get(reverse("correction-workspace", args=[self.capture.pk]))
        self.assertRedirects(workspace, reverse("work-review"), fetch_redirect_response=False)
        cleared = save_correction(
            self.capture,
            self.reviewer,
            {"metadata": {"dates": []}},
            correction.revision,
            "Clear dates",
        )
        cleared_preview = preview(source, part, body, cleared.expected)
        self.assertEqual(cleared_preview["metadata"]["date_facts"], [])
        self.assertEqual(cleared_preview["metadata"]["published"], "")
        reset = save_correction(self.capture, self.reviewer, {}, cleared.revision, "Reset")
        self.assertEqual(reset.expected, {})

    def test_invalid_values_are_errors_not_partial_saves(self):
        for expected in [
            {"unexpected": True},
            {"metadata": {"language": "fr-FR"}},
            {"metadata": {"title": ""}},
            {"metadata": {"dates": [{"value": "1848-02-31", "type": "publication"}]}},
            {"metadata": {"dates": [{"value": "1891-13", "type": "written"}]}},
            {"metadata": {"dates": [{"value": "", "type": "unknown"}]}},
            {
                "metadata": {
                    "dates": [
                        {"value": "1891", "type": "publication"},
                        {"value": "1892", "type": "publication"},
                    ]
                }
            },
            {"metadata": {"people": [{"name": "X", "source_name": "X", "role": "guessed"}]}},
            {"blocks": [{"index": 100000, "action": "exclude"}]},
            {"blocks": [{"index": 0, "action": "script"}]},
            {"blocks": [{"index": 0, "action": []}]},
            {"metadata": {"dates": [{"value": "1848", "type": {}}]}},
            {"metadata": {"people": [{"name": "X", "source_name": "X", "role": []}]}},
        ]:
            with self.subTest(expected=expected):
                source, _, body, _ = extraction(self.capture)
                with self.assertRaises((ValueError, TypeError)):
                    validate_expected(expected, body, source)
        self.assertFalse(SourceCorrection.objects.exists())

    def test_date_ranges_preserve_precision_history_and_export(self):
        dates = [
            {"value": "1891", "end_value": "1892", "type": "publication"},
            {"value": "1890-02", "end_value": "1891-03", "type": "written"},
            {"value": "2000-02-29", "end_value": "2000-03-01", "type": "online_edition"},
        ]
        expected = {"metadata": {"dates": dates}}
        source, part, body, _ = extraction(self.capture)
        validate_expected(expected, body, source)
        result = preview(source, part, body, expected)
        self.assertEqual(result["metadata"]["published"], "1891 / 1892")
        self.assertEqual(result["metadata"]["date_facts"], dates)
        save_correction(self.capture, self.reviewer, expected, 0, "Add date ranges")
        workspace = self.client.get(reverse("correction-workspace", args=[self.capture.pk]))
        self.assertRedirects(workspace, reverse("work-review"), fetch_redirect_response=False)
        exported = self.client.get(reverse("correction-export", args=[self.capture.pk])).json()
        self.assertEqual(exported["dataset_schema"], SCHEMA_VERSION)
        self.assertEqual(exported["corrections"][0]["schema_version"], SCHEMA_VERSION)
        self.assertEqual(exported["corrections"][0]["expected"]["metadata"]["dates"], dates)

    def test_invalid_date_ranges_are_not_saved(self):
        for end in ("1890", "1892-02", "", None, [], "1892-02-30"):
            with self.subTest(end=end):
                expected = {
                    "metadata": {
                        "dates": [{"value": "1891", "end_value": end, "type": "publication"}]
                    }
                }
                source, _, body, _ = extraction(self.capture)
                with self.assertRaises((ValueError, TypeError)):
                    validate_expected(expected, body, source)
        self.assertFalse(SourceCorrection.objects.exists())

    def test_legacy_date_corrections_still_apply_and_keep_schema_version(self):
        correction = save_correction(self.capture, self.reviewer, self.edits(), 0, "")
        SourceCorrection.objects.filter(pk=correction.pk).update(schema_version=1)
        source, _, body, _ = extraction(self.capture)
        apply_retained_correction(
            source, body, {**self.capture.response, "url": ARTICLE}, metadata=True
        )
        self.assertEqual(source.metadata["published"], "1848")
        exported = self.client.get(reverse("correction-export", args=[self.capture.pk])).json()
        self.assertEqual(exported["corrections"][0]["schema_version"], 1)

    def test_roles_and_empty_explicit_metadata_are_respected(self):
        source, _, body, _ = extraction(self.capture)
        expected = self.edits()
        validate_expected(expected, body)
        apply_expected(source, body, expected)
        self.assertEqual(source.metadata["authors"], ["Friedrich Engels"])
        self.assertEqual(source.metadata["contributors"][1]["role"], "unknown")
        apply_expected(source, body, {"metadata": {"people": [], "dates": [], "topics": []}})
        self.assertEqual(source.metadata["authors"], [])
        self.assertEqual(source.metadata["published"], "")
        self.assertEqual(source.metadata["topics"], [])

    def test_unwrapped_text_is_editable_without_reindexing_existing_blocks(self):
        from bs4 import BeautifulSoup

        from library.services.corrections import BLOCKS, digest

        body = BeautifulSoup(
            '<div><a id="top" href="/">MIA</a> Bare text <span>Inline label</span>'
            "<h4>Subtitle</h4><p>Keep <em>inline prose</em>.</p>"
            '<p><a href="#top">Return</a></p><!-- Ignore comment --></div>',
            "html.parser",
        ).div
        before = digest(str(body))
        legacy = body.select(BLOCKS)
        rows = block_rows(body)
        self.assertEqual(
            [row["text"] for row in rows[: len(legacy)]],
            [node.get_text(" ", strip=True) for node in legacy],
        )
        extra = rows[len(legacy) :]
        self.assertEqual(
            [row["text"].strip() for row in extra], ["MIA", "Bare text", "Inline label"]
        )
        self.assertEqual(digest(str(body)), before)
        source, part, _, _ = extraction(self.capture)
        expected = {
            "blocks": [
                {"index": extra[0]["index"], "action": "exclude"},
                {"index": 0, "action": "subtitle"},
            ]
        }
        validate_expected(expected, body)
        result = preview(source, part, body, expected)
        output = BeautifulSoup(result["html"], "html.parser")
        self.assertNotIn("MIA", output.get_text())
        self.assertEqual(output.select_one("p.document-subtitle").get_text(), "Subtitle")
        self.assertEqual(result["structure"]["toc"], [])
        self.assertIn("inline prose", output.get_text())
        for anchor in output.select("a[id]"):
            self.assertTrue(anchor["id"])
        with self.assertRaises(ValueError):
            validate_expected(
                {"blocks": [{"index": extra[0]["index"], "action": "subtitle"}]}, body
            )

    def test_offline_reformat_publishes_subtitle_and_excludes_unwrapped_label(self):
        self.capture.response = save_response(
            Response(ARTICLE, article_html('<a id="top">MIA</a>'), "text/html", {}), ARTICLE
        )
        self.capture.save(update_fields=["response"])
        _, _, body, _ = extraction(self.capture)
        row = next(row for row in block_rows(body) if row["text"] == "MIA")
        expected = {
            "blocks": [
                {"index": row["index"], "action": "exclude"},
                {"index": 0, "action": "subtitle"},
            ]
        }
        save_correction(self.capture, self.reviewer, expected, 0, "Remove navigation")
        with patch(
            "library.services.pipeline.Fetcher.fetch", side_effect=AssertionError("network")
        ):
            enqueue(ARTICLE)
            version = process_job(claim_job())
        self.assertIsNotNone(version, Job.objects.latest("created_at").error)
        self.assertNotIn("MIA", version.html)
        self.assertIn('class="document-subtitle"', version.html)
        self.assertEqual(version.structure["toc"], [])
        self.assertIn(".document-subtitle", version.stylesheet)

    def test_reviewed_heading_does_not_rebase_untouched_headings(self):
        self.capture.response = save_response(
            Response(
                ARTICLE,
                article_html("<h5>Other heading</h5>"),
                "text/html",
                {},
            ),
            ARTICLE,
        )
        source, part, body, _ = extraction(self.capture)
        result = preview(source, part, body, {"blocks": [{"index": 0, "action": "h6"}]})
        self.assertEqual([item["level"] for item in result["structure"]["toc"]], [6, 3])

    def test_override_is_digest_scoped_and_stale_adapter_fails_explicitly(self):
        save_correction(self.capture, self.reviewer, self.edits(), 0, "")
        source, _, body, _ = extraction(self.capture)
        different = {**self.capture.response, "url": ARTICLE, "digest": "a" * 64}
        self.assertIsNone(apply_retained_correction(source, body, different, metadata=True))
        entry = {**self.capture.response, "url": ARTICLE}
        with (
            patch(
                "library.services.corrections.get_profile",
                return_value=replace(get_profile(), adapter_version="future"),
            ),
            self.assertRaisesMessage(ImportFailure, "revalidation"),
        ):
            apply_retained_correction(source, body, entry, metadata=True)

    def test_offline_reformat_applies_saved_correction_and_preserves_old_version(self):
        with patch(
            "library.services.pipeline.Fetcher.fetch", side_effect=AssertionError("network")
        ):
            enqueue(ARTICLE)
            first = process_job(claim_job())
            self.assertIsNotNone(first)
            old_html = first.html
            expected = self.edits()
            author = CanonicalAuthor.objects.create(name="Friedrich Engels")
            expected["metadata"]["people"][0]["canonical"] = {
                "name": author.name,
                "authority_uri": author.authority_uri,
            }
            expected["metadata"]["dates"][0]["end_value"] = "1849"
            correction = save_correction(self.capture, self.reviewer, expected, 0, "")
            enqueue(ARTICLE, Job.Mode.REFORMAT, first.snapshot)
            second = process_job(claim_job())
        job = Job.objects.latest("created_at")
        self.assertEqual(job.status, "ready", job.error)
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(second.title, "Reviewed title")
        self.assertEqual(second.metadata["authors"], ["Friedrich Engels"])
        self.assertEqual(
            second.metadata["contributors"][0]["canonical"],
            expected["metadata"]["people"][0]["canonical"],
        )
        self.assertEqual(second.metadata["topics"], ["Labour"])
        self.assertEqual(second.metadata["published"], "1848 / 1849")
        self.assertEqual(second.metadata["date_facts"], expected["metadata"]["dates"])
        self.assertEqual(second.metadata["corrections"], [correction.pk])
        self.assertNotIn("Unwanted block", second.html)
        self.assertEqual(second.structure["toc"][0]["level"], 4)
        first.refresh_from_db()
        self.assertEqual(first.html, old_html)
        self.assertIn("Unwanted block", first.html)
        save_correction(self.capture, self.reviewer, {}, 1, "Restore baseline")
        with patch(
            "library.services.pipeline.Fetcher.fetch", side_effect=AssertionError("network")
        ):
            enqueue(ARTICLE, Job.Mode.REFORMAT, first.snapshot)
            reset = process_job(claim_job())
        self.assertEqual(reset.html, first.html)
        self.assertEqual(reset.title, first.title)

    def test_standalone_chapter_correction_applies_before_book_heading_removal(self):
        from library.services.corrections import digest
        from library.services.pipeline import prepare_pages

        site = configured_sites().get(host="www.marxists.org")
        captures = []
        for url, content in [
            (BOOK, book_index()),
            (BOOK.replace("index.htm", "chapter1.htm"), chapter(1, "<p>Remove this notice</p>")),
            (BOOK.replace("index.htm", "chapter2.htm"), chapter(2)),
        ]:
            captures.append(
                CrawlCapture.objects.create(
                    site=site,
                    url=url,
                    response=save_response(Response(url, content, "text/html", {}), url),
                )
            )
        capture = captures[1]
        _, _, body, _ = extraction(capture)
        rows = block_rows(body)
        target = next(row for row in rows if "Remove this notice" in str(row))
        correction = save_correction(
            capture,
            self.reviewer,
            {"blocks": [{"index": target["index"], "action": "exclude"}]},
            0,
            "Remove source notice",
        )
        original_digest = digest(str(body))
        manifest = {"pages": [c.response for c in captures]}
        with patch(
            "library.services.pipeline.Fetcher.fetch", side_effect=AssertionError("network")
        ):
            source, pages = prepare_pages(manifest)
        self.assertEqual(source.metadata["corrections"], [correction.pk])
        self.assertNotIn("Remove this notice", str(pages[1][1]))
        self.assertIn("Chapter 1", str(pages[1][1]))
        correction.refresh_from_db()
        self.assertEqual(correction.original["body_digest"], original_digest)
        correction.original["body_digest"] = "0" * 64
        correction.save(update_fields=["original"])
        with self.assertRaisesMessage(ImportFailure, "Revalidate it at /corrections/"):
            prepare_pages(manifest)

    def test_book_index_metadata_applies_to_assembled_book_without_network(self):
        site = configured_sites().get(host="www.marxists.org")
        captures = []
        for url, content in [
            (BOOK, book_index()),
            (BOOK.replace("index.htm", "chapter1.htm"), chapter(1)),
            (BOOK.replace("index.htm", "chapter2.htm"), chapter(2)),
        ]:
            captures.append(
                CrawlCapture.objects.create(
                    site=site,
                    url=url,
                    response=save_response(Response(url, content, "text/html", {}), url),
                )
            )
        index = captures[0]
        source, _, body, _ = extraction(index)
        self.assertTrue(source.book)
        self.assertTrue(block_rows(body))
        response = self.client.get(reverse("correction-workspace", args=[index.pk]))
        self.assertRedirects(response, reverse("work-review"), fetch_redirect_response=False)
        correction = save_correction(
            index, self.reviewer, {"metadata": {"title": "Verified book title"}}, 0, ""
        )
        with patch(
            "library.services.pipeline.Fetcher.fetch", side_effect=AssertionError("network")
        ):
            enqueue(BOOK)
            rendition = process_job(claim_job())
        self.assertIsNotNone(rendition, Job.objects.latest("created_at").error)
        self.assertEqual(rendition.title, "Verified book title")
        self.assertEqual(rendition.metadata["corrections"], [correction.pk])
        self.assertIn("First chapter", rendition.html)
        self.assertIn("Second chapter", rendition.html)
        self.assertIn("Subsection 1", rendition.html)
        self.assertIn("Subsection 2", rendition.html)

    def test_cover_exclusion_is_editable_and_applies_to_book_assembly_without_touching_chapters(
        self,
    ):
        from copy import deepcopy

        from library.services.correction_datasets import dataset, parse_dataset, prepare_import
        from library.services.corrections import apply_expected, extraction, validate_expected
        from library.services.pipeline import prepare_pages

        site = configured_sites().get(host="www.marxists.org")
        markup = book_index().replace(
            b"</body>",
            b'<img src="cover.png" alt="Title image">'
            b'<img src="other.png" alt="Other image"></body>',
        )
        captures = []
        for url, content in [
            (BOOK, markup),
            (BOOK.replace("index.htm", "chapter1.htm"), chapter(1)),
            (BOOK.replace("index.htm", "chapter2.htm"), chapter(2)),
        ]:
            captures.append(
                CrawlCapture.objects.create(
                    site=site,
                    url=url,
                    response=save_response(Response(url, content, "text/html", {}), url),
                )
            )
        index = captures[0]
        response = self.client.get(reverse("correction-workspace", args=[index.pk]))
        self.assertRedirects(response, reverse("work-review"), fetch_redirect_response=False)
        expected = {"metadata": {"excluded_covers": [BOOK.replace("index.htm", "cover.png")]}}
        correction = save_correction(index, self.reviewer, expected, 0, "Exclude title banner")
        exported = dataset([correction])
        self.assertEqual(exported["dataset_schema"], SCHEMA_VERSION)
        plan = prepare_import(parse_dataset(json.dumps(exported).encode()))
        self.assertEqual(plan[0]["record"]["expected"], expected)
        legacy = deepcopy(exported)
        legacy["dataset_schema"] = 4
        legacy["corrections"][0]["schema_version"] = 4
        with self.assertRaisesMessage(ValueError, "require correction schema 5"):
            prepare_import(parse_dataset(json.dumps(legacy).encode()))
        source, _, body, _ = extraction(index)
        cover = expected["metadata"]["excluded_covers"][0]
        for invalid in ("cover.png", [None], [cover, cover], ["file:///cover.png"]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_expected({"metadata": {"excluded_covers": invalid}}, body, source)
        apply_expected(source, body, expected)
        apply_expected(source, body, expected)
        self.assertEqual(len(source.metadata["covers"]), 1)
        manifest = {"pages": [c.response for c in captures]}
        with patch(
            "library.services.pipeline.Fetcher.fetch", side_effect=AssertionError("network")
        ):
            source, pages = prepare_pages(manifest)
        self.assertEqual(source.metadata["corrections"], [correction.pk])
        self.assertIsNone(pages[0][1].find("img", src="cover.png"))
        self.assertEqual(pages[0][1].find("img")["src"], "other.png")
        self.assertEqual(len(pages[0][1].select("img")), 1)
        self.assertEqual(len(pages), 3)
        with self.assertRaisesMessage(ValueError, "not present"):
            save_correction(
                index,
                self.reviewer,
                {"metadata": {"excluded_covers": ["https://www.marxists.org/not-a-cover.png"]}},
                1,
                "",
            )
        save_correction(index, self.reviewer, {}, 1, "Restore cover")
        _, restored = prepare_pages(manifest)
        self.assertIsNotNone(restored[0][1].find("img", src="cover.png"))
        self.assertEqual(len(restored[0][1].select("img")), 2)
        _, _, restored_body, _ = extraction(index)
        image = next(
            row for row in block_rows(restored_body) if row["tag"] == "img"
            and row["text"] == "Title image"
        )
        save_correction(
            index, self.reviewer,
            {"blocks": [{"index": image["index"], "action": "exclude"}]},
            2, "Exclude the index image block",
        )
        _, excluded = prepare_pages(manifest)
        self.assertIsNone(excluded[0][1].find("img", src="cover.png"))
        self.assertEqual(len(excluded[0][1].select("img")), 1)
