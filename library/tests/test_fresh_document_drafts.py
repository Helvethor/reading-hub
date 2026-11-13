import io
import json
import tempfile
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from library.models import (
    Blob,
    CatalogueEntry,
    ContentOrganization,
    CrawlCapture,
    Document,
    DocumentDraftBase,
    DocumentEditRevision,
    DocumentPublication,
    Job,
    Rendition,
    Snapshot,
    SourceCorrection,
)
from library.profile import get_profile
from library.services.catalogue import configured_sites
from library.services.corrections import save_correction
from library.services.document_edits import DocumentEditConflict, create_draft, save_revision
from library.services.document_publication import prepare_publication, publish_revision
from library.services.fresh_document_drafts import create_fresh_draft, preview_fresh_draft
from library.services.organizations import current_spec
from library.services.pipeline import format_rendition, snapshot_digest
from library.services.semantic_documents import fingerprint
from library.services.storage import blob_path, store_blob
from library.tests.test_sources import ARTICLE, article_html


@override_settings(READING_HUB_EDITOR_PILOT=True)
class FreshDraftTests(TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        settings = override_settings(DATA_DIR=Path(temporary.name))
        settings.enable()
        self.addCleanup(settings.disable)
        self.reviewer = get_user_model().objects.create_user("reviewer", is_staff=True)
        self.client.force_login(self.reviewer)
        document = Document.objects.create(url=ARTICLE)
        page_digest = store_blob(article_html())
        image = io.BytesIO()
        Image.new("RGB", (3, 3), "red").save(image, format="PNG")
        digest = store_blob(image.getvalue())
        self.blob = Blob.objects.create(
            digest=digest, size=len(image.getvalue()), media_type="image/png",
        )
        manifest = {
            "pages": [{
                "url": ARTICLE, "resolved_url": ARTICLE, "digest": page_digest,
                "headers": {"content-type": "text/html"},
            }],
            "assets": {"https://www.marxists.org/image.jpg": {
                "digest": digest, "size": self.blob.size, "media_type": self.blob.media_type,
            }},
        }
        snapshot = Snapshot.objects.create(
            document=document, digest=snapshot_digest(manifest), manifest=manifest, warnings=[],
        )
        self.rendition = Rendition.objects.create(
            document=document, snapshot=snapshot, identity="historical",
            output_digest="old-output", title="Historical title", metadata={"language": "en"},
            html='<section id="c1"><p>Historical output.</p></section>',
            structure={"toc": [], "parts": []}, stylesheet="old stylesheet",
            warnings=[], app_version="old", adapter_version="old", format_version="old",
        )
        self.url = reverse("document-fresh-draft", args=[self.rendition.pk])
        no_network = patch("library.services.fetch.Fetcher.fetch",
                           side_effect=AssertionError("Fresh retained generation must be offline"))
        no_network.start()
        self.addCleanup(no_network.stop)

    def counts(self):
        return [model.objects.count() for model in (
            DocumentDraftBase, DocumentEditRevision, Rendition, Snapshot, Blob,
            Job, DocumentPublication,
        )]

    def test_preview_is_offline_read_only_deterministic_and_binds_real_output(self):
        counts = self.counts()
        proposal = preview_fresh_draft(self.rendition)
        self.assertEqual(proposal, preview_fresh_draft(self.rendition))
        self.assertEqual(self.counts(), counts)
        evidence = proposal["evidence"]
        self.assertEqual(evidence["kind"], "fresh-retained-source")
        self.assertEqual(evidence["anchor"]["identity"], "historical")
        self.assertNotEqual(proposal["document"]["html"], self.rendition.html)
        self.assertEqual(proposal["document"]["metadata"]["layout"],
                         {"version": 1, "defaults": "type", "overrides": {}})
        self.rendition.refresh_from_db()
        self.assertNotIn("layout", self.rendition.metadata,
                         "Fresh generation must not restyle the historical edition.")
        self.assertEqual(evidence["manifest"], self.rendition.snapshot.manifest)
        self.assertEqual(evidence["profile_digest"], fingerprint(evidence["profile_configuration"]))
        self.assertEqual(evidence["assets"], [self.blob.pk])
        self.assertEqual(evidence["generation"]["corrections"], [])
        self.assertTrue(evidence["generation"]["parts"])
        self.assertEqual(evidence["generation"]["organization"]["specification"], None)

    def test_confirm_creates_only_separate_unverified_base_without_replaying_saved_edits(self):
        old = create_draft(self.rendition, self.reviewer)
        revision = save_revision(old, self.reviewer, old.document, 0, review="full")
        proposal = preview_fresh_draft(self.rendition)
        counts = self.counts()
        fresh = create_fresh_draft(self.rendition, self.reviewer, proposal["digest"])
        self.assertEqual(self.counts(), [counts[0] + 1, *counts[1:]])
        self.assertNotEqual(fresh.pk, old.pk)
        self.assertEqual(fresh.document, proposal["document"])
        self.assertEqual(fresh.evidence_digest, fingerprint(fresh.evidence))
        self.assertEqual(fresh.evidence["confirmation"]["preview_digest"], proposal["digest"])
        self.assertEqual(fresh.revisions.count(), 0)
        self.assertEqual(revision.review, "full")
        self.assertEqual(old.document["title"], "Historical title")
        row = save_revision(fresh, self.reviewer, fresh.document, 0)
        self.assertEqual(row.review, "partial")

    def test_changed_rules_or_wrong_confirmation_refuse_without_writes(self):
        proposal = preview_fresh_draft(self.rendition)
        counts = self.counts()
        for token in (None, "wrong"):
            with self.assertRaises(DocumentEditConflict):
                create_fresh_draft(self.rendition, self.reviewer, token)
        with patch("library.versions.APP_VERSION", "changed"):
            with self.assertRaises(DocumentEditConflict):
                create_fresh_draft(self.rendition, self.reviewer, proposal["digest"])
        profile = get_profile()
        with patch("library.services.fresh_document_drafts.get_profile",
                   return_value=replace(profile, page_size=profile.page_size + 1)):
            with self.assertRaises(DocumentEditConflict):
                create_fresh_draft(self.rendition, self.reviewer, proposal["digest"])
        self.assertEqual(self.counts(), counts)

    def test_wrapper_conversion_is_previewed_and_explicit_confirmation_is_recorded(self):
        def wrapped(*args, **kwargs):
            source, html, structure, stylesheet, warnings = format_rendition(*args, **kwargs)
            return source, f'<span id="wrapper">{html}</span>', structure, stylesheet, warnings

        with patch("library.services.fresh_document_drafts.format_rendition", side_effect=wrapped):
            response = self.client.get(self.url)
            self.assertContains(response, "Proposed semantic wrapper conversions")
            proposal = response.context["proposal"]
            self.assertEqual(len(proposal["repairs"]), 1)
            self.assertIn('<div id="wrapper">', proposal["document"]["html"])
            draft = create_fresh_draft(self.rendition, self.reviewer, proposal["digest"])
        self.assertIn('<span id="wrapper">', draft.evidence["generated_html"])
        self.assertTrue(draft.evidence["confirmation"]["explicitly_approved"])

    def site(self):
        return next(site for site in configured_sites() if site.host == "www.marxists.org")

    def test_actual_applied_correction_is_pinned_and_new_revision_invalidates_preview(self):
        capture = CrawlCapture.objects.create(
            site=self.site(), url=ARTICLE,
            response=self.rendition.snapshot.manifest["pages"][0],
        )
        correction = save_correction(
            capture, self.reviewer, {"metadata": {"title": "Reviewed source title"}},
            0, "Source checked", record_feedback=False,
        )
        proposal = preview_fresh_draft(self.rendition)
        applied = proposal["evidence"]["generation"]["corrections"]
        self.assertEqual(len(applied), 1)
        self.assertEqual(applied[0]["id"], correction.pk)
        self.assertEqual(applied[0]["reviewer"], self.reviewer.pk)
        self.assertEqual(applied[0]["binding"]["expected"], correction.expected)
        self.assertEqual(applied[0]["binding"]["revision"], 1)
        self.assertEqual(proposal["document"]["title"], "Reviewed source title")
        counts = self.counts()
        save_correction(
            capture, self.reviewer, {"metadata": {"title": "Reviewed source title"}},
            1, "New review", record_feedback=False,
        )
        updated = preview_fresh_draft(self.rendition)
        self.assertEqual(updated["document"]["html"], proposal["document"]["html"])
        self.assertEqual(updated["document"]["title"], proposal["document"]["title"])
        self.assertNotEqual(updated["digest"], proposal["digest"])
        with self.assertRaises(DocumentEditConflict):
            create_fresh_draft(self.rendition, self.reviewer, proposal["digest"])
        self.assertEqual(self.counts(), counts)

    def test_old_adapter_correction_is_not_silently_skipped_or_reapplied(self):
        capture = CrawlCapture.objects.create(
            site=self.site(), url=ARTICLE,
            response=self.rendition.snapshot.manifest["pages"][0],
        )
        correction = save_correction(
            capture, self.reviewer, {}, 0, "Review", record_feedback=False,
        )
        SourceCorrection.objects.filter(pk=correction.pk).update(adapter_version="obsolete")
        counts = self.counts()
        response = self.client.get(self.url)
        self.assertContains(response, "needs revalidation", status_code=422)
        self.assertContains(response, "Inspect retained source corrections", status_code=422)
        self.assertEqual(self.counts(), counts)

    def test_original_inputs_explicitly_exclude_legacy_corrections_and_organization(self):
        capture = CrawlCapture.objects.create(
            site=self.site(), url=ARTICLE, response=self.rendition.snapshot.manifest["pages"][0],
        )
        correction = save_correction(
            capture, self.reviewer, {"metadata": {"title": "Old corrected title"}},
            0, "Old correction", record_feedback=False,
        )
        SourceCorrection.objects.filter(pk=correction.pk).update(adapter_version="obsolete")
        spec = current_spec(ARTICLE)
        spec["title"] = "Old organization title"
        entry = CatalogueEntry.objects.create(site=self.site(), url=ARTICLE, title="Article")
        ContentOrganization.objects.create(
            entry=entry, specification=spec, rendition=self.rendition,
        )
        counts = self.counts()
        proposal = preview_fresh_draft(self.rendition, original_source=True)
        self.assertEqual(proposal["document"]["title"], "Test article")
        self.assertEqual(proposal["evidence"]["generation"]["corrections"], [])
        self.assertEqual(proposal["evidence"]["generation"]["organization"]["specification"], None)
        self.assertEqual(proposal["evidence"]["input_policy"], "original-retained-source")
        self.assertEqual(self.counts(), counts)
        response = self.client.get(self.url, {"inputs": "original"})
        self.assertContains(response, 'name="inputs" value="original"')
        self.assertContains(response, "without previous source corrections")
        self.assertEqual(self.client.post(self.url, {
            "inputs": "reviewed", "confirm": "yes", "preview_digest": proposal["digest"],
        }).status_code, 422)
        response = self.client.post(self.url, {
            "inputs": "original", "confirm": "yes", "preview_digest": proposal["digest"],
        })
        self.assertEqual(response.status_code, 302)
        draft = DocumentDraftBase.objects.get()
        save_revision(draft, self.reviewer, draft.document, 0)
        self.assertEqual(prepare_publication(draft, 1)["output"]["title"], "Test article")

    def test_generation_input_mode_is_bound_to_confirmation(self):
        normal = preview_fresh_draft(self.rendition)
        original = preview_fresh_draft(self.rendition, original_source=True)
        self.assertNotEqual(normal["digest"], original["digest"])
        with self.assertRaises(DocumentEditConflict):
            create_fresh_draft(
                self.rendition, self.reviewer, normal["digest"], original_source=True,
            )
        with self.assertRaises(ValueError):
            preview_fresh_draft(self.rendition, original_source="yes")
        self.assertEqual(self.client.get(self.url, {"inputs": "unknown"}).status_code, 422)

    def test_exact_organization_spec_is_pinned_and_change_invalidates_preview(self):
        entry = CatalogueEntry.objects.create(
            site=self.site(), url=ARTICLE, title="An article",
        )
        spec = current_spec(ARTICLE)
        spec["title"] = "Organized title"
        organization = ContentOrganization.objects.create(
            entry=entry, specification=spec, rendition=self.rendition,
        )
        proposal = preview_fresh_draft(self.rendition)
        self.assertEqual(proposal["document"]["title"], "Organized title")
        self.assertEqual(proposal["evidence"]["generation"]["organization"], {
            "id": organization.pk, "rendition": self.rendition.pk, "specification": spec,
        })
        organization.specification = {**spec, "title": "New organization title"}
        organization.save()
        with self.assertRaises(DocumentEditConflict):
            create_fresh_draft(self.rendition, self.reviewer, proposal["digest"])

    def test_pinned_base_does_not_reapply_later_source_corrections_on_save_or_publication(self):
        proposal = preview_fresh_draft(self.rendition)
        fresh = create_fresh_draft(self.rendition, self.reviewer, proposal["digest"])
        capture = CrawlCapture.objects.create(
            site=self.site(), url=ARTICLE,
            response=self.rendition.snapshot.manifest["pages"][0],
        )
        save_correction(
            capture, self.reviewer, {"metadata": {"title": "Later source correction"}},
            0, "New review", record_feedback=False,
        )
        revision = save_revision(fresh, self.reviewer, fresh.document, 0)
        candidate = prepare_publication(fresh, 1)
        self.assertEqual(candidate["output"]["title"], proposal["document"]["title"])
        self.assertEqual(revision.document["html"], fresh.document["html"])
        self.assertEqual(revision.document["title"], fresh.document["title"])

    def test_publication_checks_snapshot_and_bound_asset_integrity(self):
        proposal = preview_fresh_draft(self.rendition)
        fresh = create_fresh_draft(self.rendition, self.reviewer, proposal["digest"])
        value = {**fresh.document, "html": fresh.document["html"]
                 + f'<img src="/assets/{self.blob.pk}/" alt="Retained"/>'}
        save_revision(fresh, self.reviewer, value, 0)
        Blob.objects.filter(pk=self.blob.pk).update(media_type="image/jpeg")
        with self.assertRaisesMessage(ValueError, "differs from fresh"):
            prepare_publication(fresh, 1)
        Blob.objects.filter(pk=self.blob.pk).update(media_type="image/png")
        blob_path(self.blob.pk).write_bytes(b"corrupt")
        with self.assertRaisesMessage(ValueError, "unavailable or corrupt"):
            prepare_publication(fresh, 1)
        Snapshot.objects.filter(pk=self.rendition.snapshot_id).update(manifest={})
        fresh = DocumentDraftBase.objects.get(pk=fresh.pk)
        with self.assertRaisesMessage(DocumentEditConflict, "snapshot evidence changed"):
            prepare_publication(fresh, 1)

    def test_corrupt_page_and_asset_missing_record_or_size_are_explicit(self):
        entry = self.rendition.snapshot.manifest["pages"][0]
        path = blob_path(entry["digest"])
        original = path.read_bytes()
        path.write_bytes(b"corrupt")
        with self.assertRaisesMessage(OSError, "checksum"):
            preview_fresh_draft(self.rendition)
        path.write_bytes(original)
        Blob.objects.filter(pk=self.blob.pk).update(size=1)
        with self.assertRaisesMessage(ValueError, "size"):
            preview_fresh_draft(self.rendition)
        Blob.objects.filter(pk=self.blob.pk).delete()
        with self.assertRaisesMessage(ValueError, "no blob record"):
            preview_fresh_draft(self.rendition)

    def test_manifest_tampering_is_rejected(self):
        snapshot = self.rendition.snapshot
        snapshot.manifest["assets"] = {}
        with self.assertRaisesMessage(ValueError, "snapshot"):
            preview_fresh_draft(self.rendition)

    def test_preview_then_post_opens_saved_base_and_integrates_comparison(self):
        counts = self.counts()
        response = self.client.get(self.url)
        self.assertContains(response, "Saved editor revisions are not replayed")
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(self.counts(), counts)
        digest = response.context["proposal"]["digest"]
        self.assertEqual(self.client.post(self.url, {"preview_digest": digest}).status_code, 422)
        self.assertEqual(self.client.post(self.url, {
            "preview_digest": "wrong", "confirm": "yes",
        }).status_code, 409)
        response = self.client.post(self.url, {"preview_digest": digest, "confirm": "yes"})
        self.assertEqual(response.status_code, 302)
        draft = DocumentDraftBase.objects.get()
        with patch("library.document_editor_views.finders.find", return_value="built"):
            response = self.client.get(response["Location"])
        self.assertContains(response, "fresh offline generation")
        self.assertEqual(response.context["initial"]["revision"], 0)
        comparison = reverse("document-comparison", args=[self.rendition.pk])
        response = self.client.get(comparison, {"draft": draft.pk, "to": 0})
        self.assertContains(response, "Fresh offline generation")
        self.assertNotContains(response, "not a newly regenerated source draft")
        self.assertEqual(response.context["before"], draft.document)

    def test_permissions_csrf_feature_flag_and_missing_source(self):
        self.assertEqual(self.client.put(self.url).status_code, 405)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.reviewer)
        self.assertEqual(protected.post(self.url, {"confirm": "yes"}).status_code, 403)
        with override_settings(READING_HUB_EDITOR_PILOT=False):
            self.assertEqual(self.client.get(self.url).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.client.force_login(get_user_model().objects.create_user("reader"))
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.client.force_login(self.reviewer)
        blob_path(self.rendition.snapshot.manifest["pages"][0]["digest"]).unlink()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 422)
        self.assertNotContains(response, "Create working copy", status_code=422)

    def test_separate_base_saves_reopens_and_publishes_through_existing_reviewer_views(self):
        proposal = preview_fresh_draft(self.rendition)
        fresh = create_fresh_draft(self.rendition, self.reviewer, proposal["digest"])
        editor = reverse("document-editor", args=[self.rendition.pk])
        value = {**fresh.document, "title": "Reviewed fresh draft"}
        response = self.client.post(editor, json.dumps({
            "draft": str(fresh.pk), "revision": 0, "document": value,
            "conversion_approval": None, "review": "partial",
            "verified_sections": [], "editorial": False,
        }), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["revision"], 1)
        with patch("library.document_editor_views.finders.find", return_value="built"):
            reopened = self.client.get(editor, {"draft": fresh.pk})
        self.assertEqual(reopened.context["initial"]["document"], response.json()["document"])
        publication = reverse("document-publication", args=[self.rendition.pk])
        query = f"?draft={fresh.pk}&revision=1"
        response = self.client.get(publication + query)
        self.assertContains(response, "Reviewed fresh draft")
        self.assertContains(response, "Not verified as a whole document")
        digest = response.context["candidate"]["digest"]
        response = self.client.post(publication + query, {
            "confirm": "yes", "revision": 1, "preview_digest": digest,
        })
        self.assertEqual(response.status_code, 302)
        reader = self.client.get(response["Location"])
        self.assertContains(reader, "Reviewed fresh draft")
        self.assertContains(reader, "Section one")
        self.assertEqual(DocumentPublication.objects.count(), 1)

    def test_evaluation_copy_retains_fresh_generation_and_publication_contract(self):
        from library.services.reviewer_evaluation import create_task, start_run

        proposal = preview_fresh_draft(self.rendition)
        fresh = create_fresh_draft(self.rendition, self.reviewer, proposal["digest"])
        task = create_task(
            fresh, self.reviewer, title="Fresh article review", scope="Article",
            instructions="Check the source against the article.",
        )
        run = start_run(task, self.reviewer, practice=True)
        self.assertEqual(run.draft.evidence["kind"], "fresh-retained-source")
        self.assertEqual(run.draft.evidence["generation"], fresh.evidence["generation"])
        save_revision(run.draft, self.reviewer, run.draft.document, 0)
        self.assertEqual(prepare_publication(run.draft, 1)["output"]["title"],
                         fresh.document["title"])

    def test_correction_branch_retains_fresh_assets_and_exact_generation(self):
        from library.services.document_edits import branch_draft

        proposal = preview_fresh_draft(self.rendition)
        fresh = create_fresh_draft(self.rendition, self.reviewer, proposal["digest"])
        value = {**fresh.document, "title": "Corrected fresh title"}
        row = save_revision(fresh, self.reviewer, value, 0, review="full")
        branch = branch_draft(fresh, self.reviewer, 1)
        self.assertEqual(branch.document, row.document)
        self.assertEqual(branch.evidence["generation"], fresh.evidence["generation"])
        self.assertEqual(branch.evidence["asset_bindings"], fresh.evidence["asset_bindings"])
        saved = save_revision(branch, self.reviewer, value, 0)
        self.assertEqual(saved.review, "partial")
        self.assertEqual(prepare_publication(branch, 1)["output"]["title"], value["title"])

    def test_publication_uses_fresh_output_styles_and_assets_not_historical_edition(self):
        proposal = preview_fresh_draft(self.rendition)
        fresh = create_fresh_draft(self.rendition, self.reviewer, proposal["digest"])
        # Bind the retained image absent from the historical edition's asset relations.
        value = deepcopy(fresh.document)
        value["html"] += f'<figure><img src="/assets/{self.blob.pk}/" alt="Retained"/></figure>'
        save_revision(fresh, self.reviewer, value, 0)
        candidate = prepare_publication(fresh, 1)
        self.assertEqual(candidate["assets"], [self.blob.pk])
        self.assertNotEqual(candidate["output"]["stylesheet"], self.rendition.stylesheet)
        result = publish_revision(fresh, self.reviewer, 1, candidate["digest"])
        self.assertEqual(result.rendition.snapshot_id, self.rendition.snapshot_id)
        self.assertEqual(result.rendition.assets.get().blob_id, self.blob.pk)
        self.rendition.refresh_from_db()
        self.assertEqual(
            self.rendition.html, '<section id="c1"><p>Historical output.</p></section>',
        )
        self.assertEqual(fresh.revisions.get().review, "partial")
