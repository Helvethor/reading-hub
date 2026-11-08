import json
from copy import deepcopy
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from library.models import (
    Annotation,
    Blob,
    CatalogueEntry,
    ContentOrganization,
    CrawlSite,
    Document,
    DocumentDraftBase,
    DocumentLineageArchive,
    DocumentLineageRestore,
    DocumentReaderSelection,
    DocumentVersion,
    Rendition,
    RenditionAsset,
    Snapshot,
)
from library.profile import get_profile
from library.services.document_edits import (
    DocumentEditConflict,
    branch_draft,
    create_draft,
    save_revision,
)
from library.services.document_lineage import (
    archive_impact,
    archive_lineage,
    archived_draft_ids,
    build_lineage,
    node_is_archived,
    restore_archive,
)
from library.services.document_publication import prepare_publication, publish_revision
from library.services.document_versions import create_working_copy
from library.services.pipeline import snapshot_digest
from library.services.semantic_documents import fingerprint


@override_settings(READING_HUB_EDITOR_PILOT=True)
class DocumentLineageTests(TestCase):
    def setUp(self):
        self.reviewer = get_user_model().objects.create_user("lineage-reviewer")
        self.reviewer.is_staff = True
        self.reviewer.save(update_fields=["is_staff"])
        self.work = Document.objects.create(
            url="https://www.marxists.org/test/lineage-article", title="A work",
        )
        manifest = {
            "pages": [{
                "url": self.work.url, "resolved_url": self.work.url, "digest": "c" * 64,
            }],
            "assets": {},
        }
        self.snapshot = Snapshot.objects.create(
            document=self.work, digest=snapshot_digest(manifest), manifest=manifest,
        )
        self.rendition = self.create_rendition(
            self.work, self.snapshot, "Article edition",
            '<section id="c1"><p>Source text.</p></section>', book=False,
        )
        self.draft = create_draft(self.rendition, self.reviewer)

    def create_rendition(self, work, snapshot, title, html, *, book):
        structure = {"toc": [], "book": book}
        metadata = {"language": "en"}
        stylesheet = "retained stylesheet"
        return Rendition.objects.create(
            document=work, snapshot=snapshot, identity=fingerprint(
                [work.pk, snapshot.pk, title, html]
            ),
            title=title, metadata=metadata, structure=structure, html=html,
            stylesheet=stylesheet, warnings=[], app_version="0.30.0",
            adapter_version="19", format_version="19",
            output_digest=fingerprint([html, structure, metadata, title, stylesheet]),
        )

    def save(self, draft=None, document=None, revision=0, **options):
        draft = draft or self.draft
        return save_revision(
            draft, self.reviewer, document or draft.document, revision, **options,
        )

    def publish(self, draft, revision):
        candidate = prepare_publication(draft, revision)
        return publish_revision(draft, self.reviewer, revision, candidate["digest"])

    def test_exact_publication_ancestry_forks_and_review_only_revisions(self):
        first = self.save(review="full")
        second = self.save(
            document={**first.document, "html": '<section id="c1"><p>Corrected.</p></section>'},
            revision=1,
        )
        publication = self.publish(self.draft, 2)
        branch = branch_draft(self.draft, self.reviewer, 1)
        branch_revision = self.save(
            branch, {**first.document, "title": "Branched title"}, 0,
        )

        lineage = build_lineage(self.rendition.document)
        publication_node = lineage["nodes"][f"edition:{publication.rendition_id}"]
        self.assertEqual(publication_node["type"], "publication")
        self.assertEqual(
            publication_node["parent_id"], f"revision:{self.draft.pk}:{second.revision}",
        )
        branch_history = lineage["nodes"][f"history:{branch.pk}"]
        self.assertEqual(
            branch_history["parent_id"], f"revision:{self.draft.pk}:{first.revision}",
        )
        self.assertEqual(
            lineage["nodes"][f"revision:{self.draft.pk}:1"]["change_kind"],
            "Review-only; content unchanged",
        )
        self.assertEqual(
            lineage["nodes"][f"revision:{branch.pk}:{branch_revision.revision}"]["change_kind"],
            "Metadata-only change",
        )
        ancestry = []
        cursor = publication_node
        while cursor:
            ancestry.append(cursor["id"])
            cursor = lineage["nodes"].get(cursor["parent_id"])
        self.assertIn(f"snapshot:{self.rendition.snapshot_id}", ancestry)
        self.assertEqual(
            sum(node["type"] == "snapshot" for node in lineage["nodes"].values()), 1,
        )
        self.assertTrue(lineage["nodes"][f"revision:{self.draft.pk}:2"]["latest"])
        filtered = build_lineage(
            self.rendition.document, selected=publication_node["id"],
            filter_name="corrections",
        )

        def contains(node, node_id):
            return node["id"] == node_id or any(
                contains(child, node_id) for child in node["children"]
            )

        self.assertTrue(contains(filtered["tree"], publication_node["id"]))
        self.assertTrue(filtered["selected"]["context_only"])

    def test_review_only_event_keeps_publication_continuation_on_same_content(self):
        reviewed = self.save(review="partial")
        publication = self.publish(self.draft, reviewed.revision)
        review_event = self.save(
            document=reviewed.document, revision=reviewed.revision, review="full",
        )
        self.assertEqual(
            review_event.document_version_id, publication.revision.document_version_id,
        )

        lineage = build_lineage(
            self.rendition.document, selected=f"edition:{publication.rendition_id}",
        )
        self.assertTrue(lineage["selected"]["publication_is_latest"])

        self.client.force_login(self.reviewer)
        response = self.client.get(
            reverse("document-editor", args=[publication.rendition_id]),
        )
        self.assertRedirects(
            response,
            reverse("document-editor", args=[self.rendition.pk])
            + f"?draft={self.draft.pk}",
        )

        version_count = DocumentVersion.objects.count()
        continuation = branch_draft(self.draft, self.reviewer, review_event.revision)
        self.assertEqual(DocumentVersion.objects.count(), version_count)
        self.assertEqual(
            continuation.branch.base_version_id, review_event.document_version_id,
        )

    def test_shared_snapshot_fresh_generation_and_unknown_ancestry_are_explicit(self):
        other = self.create_rendition(
            self.work, self.snapshot, "Alternative generated edition",
            self.rendition.html, book=False,
        )
        evidence = deepcopy(self.draft.evidence)
        evidence.update({
            "kind": "fresh-retained-source", "snapshot": self.rendition.snapshot_id,
            "snapshot_digest": self.rendition.snapshot.digest,
            "rendition": other.pk,
            "anchor": {
                "rendition": other.pk, "identity": other.identity,
                "output_digest": other.output_digest, "snapshot": other.snapshot_id,
                "snapshot_digest": other.snapshot.digest,
            },
            "input_policy": {"mode": "reviewed"},
            "legacy_application": {"saved_editor_revisions": "not replayed"},
        })
        fresh = create_working_copy(
            other, self.reviewer, self.draft.document, evidence,
            profile=self.draft.profile, parent_version=None,
            origin="source_generated", source_snapshot=other.snapshot,
        )
        fresh_revision = save_revision(
            fresh, self.reviewer, fresh.document, 0,
        )
        fresh_branch = branch_draft(fresh, self.reviewer, fresh_revision.revision)
        unknown_evidence = deepcopy(self.draft.evidence)
        unknown_evidence["correction_origin"] = {
            "draft": "missing-draft", "revision": 7,
        }
        unknown = DocumentDraftBase.objects.create(
            rendition=self.rendition, profile=self.draft.profile,
            document=self.draft.document, document_digest=self.draft.document_digest,
            evidence=unknown_evidence, evidence_digest=fingerprint(unknown_evidence),
            reviewer=self.reviewer,
        )

        lineage = build_lineage(self.rendition.document)
        fresh_generation = lineage["nodes"][f"generation:{fresh.pk}"]
        self.assertEqual(fresh_generation["parent_id"], f"snapshot:{self.rendition.snapshot_id}")
        self.assertEqual(fresh_generation["input_policy"], {"mode": "reviewed"})
        self.assertEqual(
            lineage["nodes"][f"history:{fresh.pk}"]["parent_id"], fresh_generation["id"],
        )
        self.assertEqual(
            lineage["nodes"][f"history:{fresh_branch.pk}"]["parent_id"],
            f"revision:{fresh.pk}:{fresh_revision.revision}",
        )
        self.assertNotIn(f"generation:{fresh_branch.pk}", lineage["nodes"])
        self.assertTrue(
            lineage["nodes"][f"history:{unknown.pk}"]["unknown_ancestry"].startswith(
                "Unknown historical ancestry"
            )
        )
        snapshot_children = lineage["nodes"][f"snapshot:{self.rendition.snapshot_id}"]["children"]
        sibling_editions = [
            lineage["nodes"][node_id] for node_id in snapshot_children
            if lineage["nodes"][node_id]["type"] == "edition"
        ]
        self.assertTrue({self.rendition.pk, other.pk} <= {
            node["rendition_id"] for node in sibling_editions
        })

    def test_corrupt_evidence_and_missing_selection_are_reported(self):
        Snapshot.objects.filter(pk=self.snapshot.pk).update(
            manifest={"pages": None, "assets": {}}, warnings="corrupt",
        )
        evidence = deepcopy(self.draft.evidence)
        evidence["legacy_application"] = "corrupt"
        corrupt_draft = DocumentDraftBase.objects.create(
            rendition=self.rendition, profile=self.draft.profile,
            document=self.draft.document, document_digest=self.draft.document_digest,
            evidence=evidence, evidence_digest=self.draft.evidence_digest,
            reviewer=self.reviewer,
        )

        lineage = build_lineage(
            self.rendition.document, selected=f"history:{corrupt_draft.pk}",
        )
        snapshot_node = lineage["nodes"][f"snapshot:{self.snapshot.pk}"]
        history_node = lineage["nodes"][f"history:{corrupt_draft.pk}"]
        self.assertTrue(snapshot_node["integrity_errors"])
        self.assertTrue(history_node["integrity_errors"])
        self.assertEqual(lineage["selected"]["id"], f"history:{corrupt_draft.pk}")

        missing = build_lineage(
            self.rendition.document, selected="revision:missing:99",
        )
        self.assertEqual(missing["selected"]["type"], "work")
        self.assertIn("requested lineage element is missing", missing["selection_error"])

    def test_multi_page_book_lineage_keeps_generation_forks_and_publication_links(self):
        book = Document.objects.create(
            url="https://www.marxists.org/test/lineage-book/index", title="Lineage Book",
        )
        snapshots = []
        renditions = []
        for generation in range(2):
            manifest = {
                "pages": [
                    {
                        "url": f"{book.url}/part-{page}",
                        "resolved_url": f"{book.url}/part-{page}",
                        "digest": f"{generation + 4}{page}" * 32,
                    }
                    for page in range(1, 4)
                ],
                "assets": {},
            }
            snapshot = Snapshot.objects.create(
                document=book, digest=snapshot_digest(manifest), manifest=manifest,
            )
            snapshots.append(snapshot)
            renditions.append(self.create_rendition(
                book, snapshot, f"Book generation {generation + 1}",
                '<section id="p1"><h2>Part one</h2><p>First.</p></section>'
                '<section id="p2"><h2>Part two</h2><p>Second.</p></section>',
                book=True,
            ))
        source_draft = create_draft(renditions[0], self.reviewer)
        reviewed = save_revision(
            source_draft, self.reviewer, source_draft.document, 0, review="full",
        )
        corrected = save_revision(
            source_draft, self.reviewer,
            {**reviewed.document, "html":
                '<section id="p1"><h2>Part one</h2><p>Corrected.</p></section>'
                '<section id="p2"><h2>Part two</h2><p>Second.</p></section>'},
            1,
        )
        publication = self.publish(source_draft, 2)
        fork = branch_draft(source_draft, self.reviewer, 1)
        save_revision(fork, self.reviewer, fork.document, 0)
        publication_draft = create_draft(publication.rendition, self.reviewer)
        save_revision(publication_draft, self.reviewer, publication_draft.document, 0)

        fresh_base = create_draft(renditions[1], self.reviewer)
        fresh_evidence = deepcopy(fresh_base.evidence)
        fresh_evidence.update({
            "kind": "fresh-retained-source", "snapshot": snapshots[1].pk,
            "snapshot_digest": snapshots[1].digest,
            "rendition": renditions[1].pk,
            "anchor": {
                "rendition": renditions[1].pk, "identity": renditions[1].identity,
                "output_digest": renditions[1].output_digest,
                "snapshot": snapshots[1].pk, "snapshot_digest": snapshots[1].digest,
            },
            "input_policy": {"mode": "original"},
            "legacy_application": {"saved_editor_revisions": "not replayed"},
        })
        fresh = create_working_copy(
            renditions[1], self.reviewer, fresh_base.document, fresh_evidence,
            profile=fresh_base.profile, parent_version=None,
            origin="source_generated", source_snapshot=renditions[1].snapshot,
        )
        lineage = build_lineage(book)
        first_pages = lineage["nodes"][f"snapshot:{snapshots[0].pk}"]["manifest"]["pages"]
        second_pages = lineage["nodes"][f"snapshot:{snapshots[1].pk}"]["manifest"]["pages"]
        self.assertEqual(len(first_pages), 3)
        self.assertEqual(len(second_pages), 3)
        self.assertEqual(
            lineage["nodes"][f"edition:{publication.rendition_id}"]["parent_id"],
            f"revision:{source_draft.pk}:{corrected.revision}",
        )
        self.assertEqual(
            lineage["nodes"][f"history:{fork.pk}"]["parent_id"],
            f"revision:{source_draft.pk}:{reviewed.revision}",
        )
        self.assertEqual(
            lineage["nodes"][f"history:{publication_draft.pk}"]["parent_id"],
            f"revision:{source_draft.pk}:{corrected.revision}",
        )
        self.assertEqual(
            lineage["nodes"][f"history:{fresh.pk}"]["parent_id"],
            f"generation:{fresh.pk}",
        )

    def test_archive_impact_preserves_publication_and_restore_respects_overlaps(self):
        first = self.save()
        publication = self.publish(self.draft, 1)
        branch = branch_draft(self.draft, self.reviewer, first.revision)
        self.save(branch)
        asset = Blob.objects.create(digest="a" * 64, media_type="image/png", size=10)
        RenditionAsset.objects.create(rendition=self.rendition, blob=asset)
        site = CrawlSite.objects.create(
            profile=get_profile().key, host="www.marxists.org",
        )
        entry = CatalogueEntry.objects.create(
            site=site, url=self.work.url, title="Catalogue ownership fixture",
        )
        organization = ContentOrganization.objects.create(
            entry=entry, specification={"title": "Catalogue owner"},
            rendition=self.rendition,
        )
        annotation = Annotation.objects.create(
            owner=self.reviewer, rendition=self.rendition,
            start=0, end=6, quote="Source", kind=Annotation.Kind.HIGHLIGHT,
            color=Annotation.Color.YELLOW,
        )
        rendition_count = Rendition.objects.count()
        publication_count = publication.rendition.document.renditions.count()
        latest_before = self.work.latest().pk
        reader_url = reverse("reader", args=[publication.rendition_id])
        pdf_url = reverse("reader-pdf", args=[publication.rendition_id])
        self.assertEqual(latest_before, self.rendition.pk)

        lineage = build_lineage(self.rendition.document)
        branch_id = f"history:{branch.pk}"
        branch_preview = archive_impact(lineage, branch_id)
        self.assertIn(f"revision:{branch.pk}:1", branch_preview["scope_ids"])
        self.assertEqual(branch_preview["preserved_publications"], [])
        branch_archive = archive_lineage(
            self.rendition.document, branch_id, self.reviewer,
            branch_preview["digest"], "Obsolete experimental branch",
        )

        lineage = build_lineage(self.rendition.document)
        generation_preview = archive_impact(lineage, f"edition:{self.rendition.pk}")
        self.assertIn(branch_id, generation_preview["scope_ids"])
        self.assertEqual(
            generation_preview["preserved_publications"][0]["id"],
            f"edition:{publication.rendition_id}",
        )
        generation_archive = archive_lineage(
            self.rendition.document, f"edition:{self.rendition.pk}", self.reviewer,
            generation_preview["digest"], "Retire this generation and its corrections",
        )
        self.assertEqual(self.work.latest().pk, latest_before)
        current_organization = ContentOrganization.objects.get(pk=organization.pk)
        self.assertEqual(current_organization.entry_id, entry.pk)
        self.assertEqual(current_organization.rendition_id, self.rendition.pk)
        self.assertEqual(annotation.rendition_id, self.rendition.pk)
        self.assertTrue(Annotation.objects.filter(pk=annotation.pk).exists())
        self.assertEqual(Client().get(reader_url).status_code, 200)
        self.assertEqual(Client().get(pdf_url).status_code, 200)
        restore_archive(
            self.rendition.document, branch_archive.pk, self.reviewer, "Overlap remains",
        )
        self.assertTrue(node_is_archived(self.rendition.document, branch_id))
        self.assertIn(str(branch.pk), archived_draft_ids(self.rendition.document))
        restore_archive(self.rendition.document, generation_archive.pk, self.reviewer)
        self.assertFalse(node_is_archived(self.rendition.document, branch_id))
        self.assertEqual(DocumentLineageArchive.objects.count(), 2)
        self.assertEqual(DocumentLineageRestore.objects.count(), 2)
        self.assertEqual(Rendition.objects.count(), rendition_count)
        self.assertEqual(publication.rendition.document.renditions.count(), publication_count)
        self.assertTrue(
            RenditionAsset.objects.filter(rendition=self.rendition, blob=asset).exists()
        )
        self.assertTrue(DocumentLineageArchive.objects.get(pk=branch_archive.pk).scope["node_ids"])
        self.assertEqual(self.work.latest().pk, latest_before)
        self.assertEqual(Client().get(reader_url).status_code, 200)
        self.assertEqual(Client().get(pdf_url).status_code, 200)

    def test_stale_preview_and_archived_open_editor_are_recoverable(self):
        self.save()
        lineage = build_lineage(self.rendition.document)
        target = f"history:{self.draft.pk}"
        preview = archive_impact(lineage, target)
        archive_lineage(
            self.rendition.document, target, self.reviewer,
            preview["digest"], "Test archived editor",
        )
        with self.assertRaisesMessage(DocumentEditConflict, "archived"):
            self.save(revision=1)
        with self.assertRaisesMessage(DocumentEditConflict, "archived"):
            branch_draft(self.draft, self.reviewer, 1)

        pending = {**self.draft.revisions.first().document, "title": "Unsaved pending title"}
        self.client = Client()
        self.client.force_login(self.reviewer)
        with patch("library.document_editor_views.finders.find", return_value="built-asset"):
            opened = self.client.get(
                reverse("document-editor", args=[self.rendition.pk]),
                {"draft": self.draft.pk},
            )
        self.assertEqual(opened.status_code, 200)
        self.assertContains(opened, "pending editor content is still here")
        before = self.draft.revisions.count()
        response = self.client.post(
            reverse("document-editor", args=[self.rendition.pk]),
            json.dumps({
                "draft": str(self.draft.pk), "revision": 1, "document": pending,
                "conversion_approval": None, "review": "partial",
                "verified_sections": [], "editorial": False,
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("Restore it before saving", response.json()["error"])
        self.assertEqual(self.draft.revisions.count(), before)

    def test_reader_target_selection_is_confirmed_audited_and_uses_fallback(self):
        newer = self.create_rendition(
            self.work, self.snapshot, "Newer source edition",
            '<section id="c1"><p>Newer source.</p></section>', book=False,
        )
        self.assertEqual(self.work.reader_target().pk, newer.pk)
        url = reverse("document-lineage", args=[self.work.pk])
        client = Client()
        client.force_login(self.reviewer)

        unconfirmed = client.post(url, {
            "action": "select-reader-target", "rendition_id": self.rendition.pk,
            "expected_rendition": newer.pk, "reason": "Prefer reviewed text.",
        })
        self.assertEqual(unconfirmed.status_code, 422)
        self.assertEqual(DocumentReaderSelection.objects.count(), 0)

        selected = client.post(url, {
            "action": "select-reader-target", "rendition_id": self.rendition.pk,
            "expected_rendition": newer.pk, "reason": "Prefer reviewed text.",
            "confirm": "yes",
        })
        self.assertEqual(selected.status_code, 302)
        self.work.refresh_from_db()
        self.assertEqual(self.work.reader_target().pk, self.rendition.pk)
        self.assertTrue(self.work.reader_selection_explicit)
        audit = DocumentReaderSelection.objects.get()
        self.assertEqual(audit.previous_rendition_id, newer.pk)
        self.assertEqual(audit.rendition_id, self.rendition.pk)
        self.assertEqual(audit.reviewer_id, self.reviewer.pk)
        self.assertEqual(audit.reason, "Prefer reviewed text.")
        self.assertTrue(audit.explicit)
        latest = client.get(reverse("latest", args=[self.work.pk]))
        self.assertEqual(latest.url, reverse("reader", args=[self.rendition.pk]))

        stale = client.post(url, {
            "action": "select-reader-target", "rendition_id": newer.pk,
            "expected_rendition": newer.pk, "reason": "Stale expectation.",
            "confirm": "yes",
        })
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(DocumentReaderSelection.objects.count(), 1)

        reset = client.post(url, {
            "action": "restore-reader-fallback", "expected_rendition": self.rendition.pk,
            "reason": "Return to generated fallback.", "confirm": "yes",
        })
        self.assertEqual(reset.status_code, 302)
        self.work.refresh_from_db()
        self.assertEqual(self.work.reader_target().pk, newer.pk)
        self.assertFalse(self.work.reader_selection_explicit)
        fallback_audit = DocumentReaderSelection.objects.order_by("-pk").first()
        self.assertEqual(fallback_audit.previous_rendition_id, self.rendition.pk)
        self.assertEqual(fallback_audit.rendition_id, newer.pk)
        self.assertFalse(fallback_audit.explicit)
        latest = client.get(reverse("latest", args=[self.work.pk]))
        self.assertEqual(latest.url, reverse("reader", args=[newer.pk]))

        outsider = get_user_model().objects.create_user("reader-target-outsider")
        unauthorized = Client()
        unauthorized.force_login(outsider)
        forbidden = unauthorized.post(url, {
            "action": "select-reader-target", "rendition_id": self.rendition.pk,
            "expected_rendition": newer.pk, "reason": "No reviewer role.",
            "confirm": "yes",
        })
        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(DocumentReaderSelection.objects.count(), 2)

    def test_permission_csrf_stale_preview_and_active_filter(self):
        self.save()
        url = reverse("document-lineage", args=[self.rendition.document_id])
        anonymous = Client().get(url)
        self.assertEqual(anonymous.status_code, 200)
        outsider = get_user_model().objects.create_user("outsider")
        client = Client()
        client.force_login(outsider)
        self.assertEqual(client.get(url).status_code, 200)
        self.assertEqual(client.post(url, {"action": "archive"}).status_code, 403)

        client = Client(enforce_csrf_checks=True)
        client.force_login(self.reviewer)
        response = client.get(url, {"filter": "corrections"})
        self.assertContains(response, "Active corrections")
        self.assertContains(response, str(self.draft.pk)[:8])
        blocked = client.post(url, {
            "action": "archive", "node_id": f"history:{self.draft.pk}",
            "preview_digest": "stale", "reason": "reason", "confirm": "yes",
        })
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(DocumentLineageArchive.objects.count(), 0)

        preview = client.get(url, {"archive": f"history:{self.draft.pk}"})
        self.assertEqual(preview.status_code, 200)
        token = preview.cookies["csrftoken"].value
        digest = preview.context["archive_preview"]["digest"]
        self.save(revision=1)
        stale = client.post(url, {
            "action": "archive", "node_id": f"history:{self.draft.pk}",
            "preview_digest": digest, "reason": "reason", "confirm": "yes",
        }, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(stale.status_code, 409)
        self.assertContains(stale, "changed after preview", status_code=409)
        self.assertEqual(DocumentLineageArchive.objects.count(), 0)
        unconfirmed = client.post(url, {
            "action": "archive", "node_id": f"history:{self.draft.pk}",
            "preview_digest": digest, "reason": "reason",
        }, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(unconfirmed.status_code, 422)
        current = client.get(url, {"archive": f"history:{self.draft.pk}"})
        digest = current.context["archive_preview"]["digest"]
        success = client.post(f"{url}?embedded=1", {
            "action": "archive", "node_id": f"history:{self.draft.pk}",
            "preview_digest": digest, "reason": "obsolete branch", "confirm": "yes",
        }, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(success.status_code, 302)
        self.assertIn("embedded=1", success.url)
        archived = client.get(url, {"filter": "archived"})
        self.assertContains(archived, "Archived elements")
        self.assertContains(archived, "Correction history")
        self.assertEqual(DocumentLineageArchive.objects.count(), 1)
        active = client.get(url, {"filter": "corrections"})
        self.assertNotContains(active, str(self.draft.pk))
        archive = DocumentLineageArchive.objects.get()
        restore_preview = client.get(url, {
            "filter": "archived", "selected": f"history:{self.draft.pk}",
            "restore": str(archive.pk), "embedded": "1",
        })
        self.assertContains(restore_preview, "Restore this operation")
        restored = client.post(f"{url}?filter=archived&embedded=1", {
            "action": "restore", "archive_id": str(archive.pk),
            "node_id": f"history:{self.draft.pk}", "reason": "Required again",
            "confirm": "yes",
        }, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(restored.status_code, 302)
        self.assertIn("embedded=1", restored.url)
        self.assertEqual(archive.restore.reviewer, self.reviewer)
        self.assertEqual(archive.restore.reason, "Required again")
        self.assertFalse(node_is_archived(self.rendition.document, f"history:{self.draft.pk}"))
