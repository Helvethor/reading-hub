import json
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from library.models import (
    Annotation,
    Blob,
    BookMembershipGeneration,
    CatalogueEntry,
    ContentOrganization,
    ContentOrganizationDecision,
    CrawlCapture,
    Document,
    DocumentDraftBase,
    DocumentEditRevision,
    DocumentPublication,
    DocumentVersion,
    Job,
    PageTypeDecision,
    Rendition,
    RenditionAsset,
    Snapshot,
    SourceCorrection,
)
from library.services.book_generation import (
    generate_from_membership,
    preview_membership_generation,
)
from library.services.catalogue import configured_sites, register_book
from library.services.document_lineage import build_lineage
from library.services.errors import ImportFailure
from library.services.fetch import Fetcher, Response
from library.services.organizations import (
    change_plan,
    commit_change,
    current_spec,
    preview_change,
    undo_plan,
)
from library.services.pipeline import claim_job, enqueue, process_job, snapshot_digest
from library.services.storage import save_response, store_blob
from library.tests.test_sources import ARTICLE, BOOK, article_html, book_index, chapter


@override_settings(ALLOWED_HOSTS=["testserver"])
class OrganizationTests(TestCase):
    @override_settings(READING_HUB_EDITOR_PILOT=True)
    def test_standalone_organization_redirects_or_refuses_without_mutating(self):
        legacy = reverse("content-organization")
        destination = reverse("document-editor-membership", args=[self.book.pk])
        self.assertRedirects(
            self.client.get(legacy, {"review_version": self.book.pk}),
            destination,
            fetch_redirect_response=False,
        )
        self.assertRedirects(
            self.client.get(legacy),
            reverse("work-review"),
            fetch_redirect_response=False,
        )
        retired = self.client.post(
            legacy,
            {
                "action": "preview",
                "reason": "Should not mutate",
                "specification": json.dumps(self.spec),
            },
        )
        self.assertEqual(retired.status_code, 410)
        self.assertFalse(ContentOrganizationDecision.objects.exists())

        regular = get_user_model().objects.create_user("not-an-organizer")
        self.client.force_login(regular)
        self.assertEqual(self.client.get(destination).status_code, 403)

    @override_settings(READING_HUB_EDITOR_PILOT=False)
    def test_membership_remains_available_when_document_editor_is_disabled(self):
        response = self.client.get(
            reverse("content-organization"),
            {"review_version": self.book.pk},
        )
        self.assertRedirects(
            response,
            reverse("document-editor-membership", args=[self.book.pk]),
            fetch_redirect_response=False,
        )
        self.assertContains(
            self.client.get(response.url), "Catalogue book membership",
        )

    @override_settings(READING_HUB_EDITOR_PILOT=True)
    def test_retired_correction_editors_redirect_and_all_legacy_mutations_refuse(self):
        from library.services.corrections import save_correction
        from library.services.document_edits import create_draft

        draft = create_draft(self.book, self.reviewer)
        capture = CrawlCapture.objects.create(
            site=self.sites["www.marxists.org"],
            url=BOOK,
            response=save_response(self.response(BOOK), BOOK),
        )
        correction = save_correction(
            capture, self.reviewer, {"metadata": {"title": "Historical correction"}},
            0, "Historical evidence",
        )
        draft_count = DocumentDraftBase.objects.count()
        capture_count = CrawlCapture.objects.count()
        classification = PageTypeDecision.objects.create(
            site=capture.site,
            url=capture.url,
            discovery_only=True,
            previous_flags={"captures": {}, "entries": {}},
            reviewer=self.reviewer,
            reason="Global discovery-only evidence",
        )
        editor = reverse("document-editor", args=[self.book.pk])
        response = self.client.get(reverse("correction-workspace", args=[capture.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url.split("?", 1)[0], editor)
        self.assertNotIn("start=source", response.url)
        self.assertIn(f"review_capture={capture.pk}", response.url)
        self.assertIn(f"review_version={self.book.pk}", response.url)
        with patch("library.document_editor_views.finders.find", return_value="built-asset"):
            opened = self.client.get(response.url)
        self.assertEqual(opened.status_code, 200)
        self.assertEqual(opened.context["draft"].pk, draft.pk)
        self.assertEqual(DocumentDraftBase.objects.count(), draft_count)
        self.assertEqual(CrawlCapture.objects.count(), capture_count)
        legacy_writes = [
            self.client.post(reverse("correction-workspace", args=[capture.pk]), {}),
            self.client.post(
                reverse("correction-update", args=[capture.pk]),
                "{}",
                content_type="application/json",
            ),
            self.client.post(reverse("correction-page-type", args=[capture.pk]), {}),
            self.client.post(
                reverse("source-excerpts", args=[capture.pk]),
                "{}",
                content_type="application/json",
            ),
        ]
        self.assertEqual([response.status_code for response in legacy_writes], [410] * 4)
        self.assertContains(
            self.client.get(reverse("correction-dataset-import")),
            "Dataset JSON",
        )
        self.assertEqual(SourceCorrection.objects.get().pk, correction.pk)
        self.assertEqual(PageTypeDecision.objects.get().pk, classification.pk)
        history = self.client.get(reverse("correction-revisions", args=[capture.pk]))
        self.assertEqual(history.status_code, 200)
        self.assertContains(history, "Global discovery-only evidence")
        self.assertContains(history, "Page classification evidence (read-only)")
        self.assertNotContains(history, "correction-page-type")
        self.assertEqual(
            self.client.get(reverse("correction-export", args=[capture.pk])).json()[
                "corrections"
            ][0]["expected"],
            correction.expected,
        )
        self.assertContains(
            self.client.get(reverse("correction-dataset-import")),
            "Dataset JSON",
        )

    def test_reviewed_metadata_title_overrides_stale_organization_title_on_reformat(self):
        from library.services.corrections import save_correction
        from library.services.pipeline import format_rendition

        self.publish(self.spec)
        capture = CrawlCapture.objects.create(
            site=self.sites["www.marxists.org"],
            url=BOOK,
            response=save_response(self.response(BOOK), BOOK),
        )
        save_correction(
            capture, self.reviewer,
            {"metadata": {"title": "Corrected work title", "subtitle": "Exact mixed CASE"}},
            0, "Verified metadata",
        )
        source, *_ = format_rendition(self.book.snapshot.manifest, [])
        self.assertEqual(source.title, "Corrected work title")
        self.assertEqual(source.metadata["subtitle"], "Exact mixed CASE")
        self.book.refresh_from_db()
        self.assertNotEqual(self.book.title, source.title)
        self.assertEqual(
            ContentOrganization.objects.get().specification["title"], self.spec["title"]
        )

    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        settings = override_settings(DATA_DIR=Path(temporary.name))
        settings.enable()
        self.addCleanup(settings.disable)
        self.sites = {site.host: site for site in configured_sites()}
        self.reviewer = get_user_model().objects.create_user("organizer")
        self.reviewer.groups.add(Group.objects.get(name="Metadata reviewers"))
        self.client.force_login(self.reviewer)
        self.fetch = patch.object(Fetcher, "fetch", side_effect=self.response).start()
        self.addCleanup(patch.stopall)
        enqueue(BOOK)
        self.book = process_job(claim_job())
        self.assertIsNotNone(self.book)
        self.spec = current_spec(BOOK)

    def response(self, url, *, asset=False):
        if url == BOOK:
            body = book_index()
        elif url.endswith("chapter1.htm"):
            body = chapter(1)
        elif url.endswith("chapter2.htm"):
            body = chapter(2)
        else:
            body = article_html()
        return Response(url, body, "text/html", {"content-type": "text/html"})

    def prepare(self, spec):
        before, after = change_plan(spec)
        result = preview_change(before, after)
        result["digests"] = [work["digest"] for work in result["works"]]
        return result

    def publish(self, spec):
        return commit_change(self.prepare(spec), self.reviewer, "Verified source organization")

    @override_settings(READING_HUB_EDITOR_PILOT=True)
    def test_editor_structure_workflow_reorders_book_then_corrects_article_and_book(self):
        editor_path = reverse("document-editor", args=[self.book.pk])
        with patch("library.document_editor_views.finders.find", return_value="built-asset"):
            initial_editor = self.client.get(editor_path)
        self.assertEqual(initial_editor.status_code, 200)
        self.assertContains(initial_editor, "Book structure")
        self.assertEqual(len(initial_editor.context["initial"]["structure"]["parts"]), 3)
        self.assertContains(
            initial_editor,
            reverse("document-editor-membership", args=[self.book.pk]),
        )

        changed = deepcopy(self.spec)
        changed["parts"].reverse()
        changed["parts"][0].update(title="Reviewed appendix", role="appendix")
        self.publish(changed)
        new_book = Document.objects.get(url=BOOK).latest()

        def edit_and_publish(version):
            path = reverse("document-editor", args=[version.pk])
            with patch("library.document_editor_views.finders.find", return_value="built-asset"):
                page = self.client.get(path)
            self.assertEqual(page.status_code, 200)
            initial = page.context["initial"]
            payload = {
                "draft": None,
                "revision": 0,
                "document": initial["document"],
                "conversion_approval": initial["approval_digest"],
                "review": "partial",
                "verified_sections": [],
                "editorial": False,
            }
            saved = self.client.post(
                path, json.dumps(payload), content_type="application/json",
            )
            self.assertEqual(saved.status_code, 200, saved.content.decode())
            draft = saved.json()["draft"]
            publication_path = (
                reverse("document-publication", args=[version.pk])
                + f"?draft={draft}&revision=1"
            )
            preview = self.client.get(publication_path)
            self.assertEqual(preview.status_code, 200)
            published = self.client.post(
                publication_path,
                {
                    "confirm": "yes", "revision": 1,
                    "preview_digest": preview.context["candidate"]["digest"],
                },
            )
            self.assertEqual(published.status_code, 302)
            return DocumentPublication.objects.get(
                revision__draft__pk=draft, revision__revision=1,
            ).rendition

        new_book.refresh_from_db()
        new_book_publication = edit_and_publish(new_book)
        self.assertTrue(new_book_publication.structure["book"])
        self.assertEqual(new_book_publication.structure["pages"], 3)
        self.assertEqual(new_book_publication.structure["parts"][0]["role"], "appendix")
        self.assertEqual(
            new_book_publication.structure["parts"][0]["title"], "Reviewed appendix"
        )
        book_html = new_book_publication.html
        self.assertIn("Reviewed appendix", book_html)
        self.assertIn("First chapter", book_html)
        self.assertIn("This is a sufficiently long original test paragraph", book_html)
        self.assertEqual(
            self.client.get(reverse("reader", args=[new_book_publication.pk])).status_code,
            200,
        )

        enqueue(ARTICLE)
        article = process_job(claim_job())
        self.assertIsNotNone(article)
        article_publication = edit_and_publish(article)
        self.assertFalse(article_publication.structure["book"])
        self.assertEqual(article_publication.structure["pages"], 1)
        self.assertEqual(
            self.client.get(reverse("reader", args=[article_publication.pk])).status_code,
            200,
        )
        self.assertEqual(DocumentDraftBase.objects.count(), 2)
        self.assertEqual(DocumentEditRevision.objects.count(), 2)
        self.assertEqual(DocumentPublication.objects.count(), 2)

    @override_settings(READING_HUB_EDITOR_PILOT=True)
    def test_organization_mutation_is_refused_even_when_editor_conversion_would_fail(self):
        with patch(
            "library.organization_views.adapter_for",
            side_effect=ImportFailure("Legacy structure needs manual conversion.", "organization"),
        ):
            response = self.client.post(
                reverse("content-organization"),
                {
                    "action": "preview",
                    "reason": "Should not run in the retired workspace",
                    "specification": json.dumps(self.spec),
                },
            )
        self.assertEqual(response.status_code, 410)
        self.assertFalse(ContentOrganizationDecision.objects.exists())

    def test_preview_then_reorder_rename_roles_redirect_every_old_surface(self):
        first_url = self.spec["parts"][1]["url"]
        document = Document.objects.create(url=first_url)
        from library.models import Snapshot

        snapshot = Snapshot.objects.create(document=document, digest="a" * 64, manifest={})
        old = Rendition.objects.create(
            document=document,
            snapshot=snapshot,
            identity="a" * 64,
            title="Old chapter",
            structure={"toc": []},
            html="<p>Private quote</p>",
        )
        annotation = Annotation.objects.create(
            owner=self.reviewer,
            rendition=old,
            start=0,
            end=13,
            quote="Private quote",
            kind="highlight",
            color="yellow",
        )
        changed = deepcopy(self.spec)
        changed["title"] = "Reviewed exact BOOK title"
        changed["parts"].reverse()
        changed["parts"][0].update(title="Afterword", role="postscript")
        preview = self.prepare(changed)
        self.assertEqual(preview["annotations"], 1)
        self.assertEqual(self.book.document.latest(), self.book)
        self.assertFalse(ContentOrganizationDecision.objects.exists())
        decision = commit_change(preview, self.reviewer, "Reviewed order")
        current = self.book.document.latest()
        self.assertEqual(current.title, changed["title"])
        self.assertEqual(current.structure["parts"][0]["role"], "postscript")
        self.assertEqual(decision.before[0], self.spec)
        self.assertEqual(decision.after[0], changed)
        for url in (
            reverse("reader", args=[old.pk]),
            reverse("latest", args=[document.pk]),
            reverse("history", args=[document.pk]),
            reverse("reader-pdf", args=[old.pk]),
        ):
            response = self.client.get(url)
            destination = (
                reverse("reader-pdf", args=[current.pk])
                if url.endswith("download.pdf")
                else reverse("reader", args=[current.pk])
            )
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, destination + "#c2")
        self.assertRedirects(
            self.client.get(reverse("reader-css", args=[old.pk])),
            reverse("reader-css", args=[current.pk]),
        )
        old.refresh_from_db()
        annotation.refresh_from_db()
        self.assertEqual(old.html, "<p>Private quote</p>")
        self.assertEqual(annotation.rendition_id, old.pk)
        self.assertContains(self.client.get(reverse("preserved-annotations")), "Private quote")
        other = get_user_model().objects.create_user("another")
        self.client.force_login(other)
        self.assertNotContains(self.client.get(reverse("preserved-annotations")), "Private quote")
        self.assertEqual(
            self.client.get(reverse("annotations", args=[old.pk])).json()["annotations"], []
        )

    def test_detach_rebuilds_both_works_and_audited_undo(self):
        changed = deepcopy(self.spec)
        removed = changed["parts"].pop()
        decision = self.publish(changed)
        member = CatalogueEntry.objects.get(url=removed["url"])
        self.assertIsNone(member.book_id)
        separate = Document.objects.get(url=removed["url"]).latest()
        self.assertFalse(separate.structure["book"])
        self.assertEqual(self.book.document.latest().structure["pages"], 2)
        before, after = undo_plan(decision)
        preview = preview_change(before, after)
        preview["digests"] = [work["digest"] for work in preview["works"]]
        undo = commit_change(preview, self.reviewer, "Restore complete book", undo_of=decision)
        member.refresh_from_db()
        self.assertEqual(member.book.url, BOOK)
        self.assertEqual(undo.undo_of_id, decision.pk)
        self.assertEqual(self.book.document.latest().structure["pages"], 3)
        self.assertEqual(ContentOrganizationDecision.objects.count(), 2)

    def test_attach_separate_url_and_combine_book_survives_crawl_and_reformat(self):
        enqueue(ARTICLE)
        article = process_job(claim_job())
        changed = deepcopy(self.spec)
        changed["parts"].append(
            {
                "url": ARTICLE,
                "title": "Supplement",
                "role": "appendix",
                "group": "",
                "use_source_headings": False,
            }
        )
        self.publish(changed)
        self.assertEqual(CatalogueEntry.objects.get(url=ARTICLE).book.url, BOOK)
        with patch.object(Fetcher, "fetch") as fetch:
            result = enqueue(ARTICLE, Job.Mode.REFORMAT, article.snapshot)
            self.assertEqual(result.document.url, BOOK)
            reformatted = process_job(claim_job())
            self.assertEqual(reformatted.structure["pages"], 4)
            self.assertEqual(reformatted.structure["parts"][-1]["role"], "appendix")
            fetch.assert_not_called()
        from library.sources.adapters import discover, parse_html

        register_book(
            self.sites["www.marxists.org"], BOOK, discover(parse_html(book_index()), BOOK)
        )
        self.assertEqual(CatalogueEntry.objects.get(url=ARTICLE).book.url, BOOK)
        self.assertEqual(current_spec(BOOK), changed)

    def test_membership_generation_binds_sources_and_reuses_unchanged_version(self):
        book_entry = CatalogueEntry.objects.get(url=BOOK)
        preview = preview_membership_generation(book_entry)
        self.assertEqual(preview["url"], BOOK)
        self.assertEqual(
            set(preview["members"]),
            {entry.url for entry in book_entry.chapters.all()},
        )
        self.assertEqual(
            len(preview["binding"]["membership"]),
            book_entry.chapters.count(),
        )
        self.assertEqual(
            set(preview["binding"]["sources"]),
            {BOOK, *preview["members"]},
        )
        self.assertIn("assets", preview["binding"])

        before = (Rendition.objects.count(), DocumentVersion.objects.count())
        first = generate_from_membership(
            book_entry, self.reviewer, "Generate from current membership.",
            preview["revision"], preview["digest"],
        )
        after_first = (Rendition.objects.count(), DocumentVersion.objects.count())
        self.assertEqual(after_first, before)
        first_version = first.document_version
        generation = BookMembershipGeneration.objects.get()
        self.assertEqual(generation.rendition_id, first.pk)
        self.assertEqual(generation.binding, preview["binding"])
        self.assertEqual(generation.reviewer_id, self.reviewer.pk)
        self.assertEqual(generation.reason, "Generate from current membership.")
        self.assertEqual(first_version.evidence.get("book_membership_binding"), None)
        generation.reason = "Changed evidence"
        with self.assertRaisesMessage(ValueError, "immutable"):
            generation.save()
        lineage_node = build_lineage(first.document)["nodes"][f"edition:{first.pk}"]
        self.assertIn(
            ("Membership binding digest", generation.binding_digest),
            lineage_node["details"],
        )
        self.assertEqual(lineage_node["integrity_errors"], [])
        self.assertEqual(first.document.latest().pk, first.pk)

        next_preview = preview_membership_generation(book_entry)
        self.assertEqual(next_preview["existing_rendition"], first.pk)
        second = generate_from_membership(
            book_entry, self.reviewer, "Confirm unchanged generated source.",
            next_preview["revision"], next_preview["digest"],
        )
        self.assertEqual(second.pk, first.pk)
        self.assertEqual(
            (Rendition.objects.count(), DocumentVersion.objects.count()), after_first,
        )
        self.assertEqual(BookMembershipGeneration.objects.count(), 1)

        Document.objects.filter(pk=first.document_id).update(
            reader_rendition=self.book, reader_selection_explicit=True,
        )
        current_preview = preview_membership_generation(book_entry)
        generate_from_membership(
            book_entry, self.reviewer, "Keep explicit reader choice.",
            current_preview["revision"], current_preview["digest"],
        )
        first.document.refresh_from_db()
        self.assertEqual(first.document.reader_target().pk, self.book.pk)
        self.assertTrue(first.document.reader_selection_explicit)

    def test_membership_generation_warns_for_unordered_member_and_refuses_missing_source(self):
        book_entry = CatalogueEntry.objects.get(url=BOOK)
        enqueue(ARTICLE)
        process_job(claim_job())
        article_entry, _ = CatalogueEntry.objects.get_or_create(
            site=self.sites["communistusa.org"], url=ARTICLE, defaults={"title": "Standalone"},
        )
        response = Response(ARTICLE, article_html(), "text/html", {})
        CrawlCapture.objects.create(
            site=self.sites["communistusa.org"],
            url=ARTICLE,
            response=save_response(response, ARTICLE),
        )
        article_entry.book = book_entry
        article_entry.save(update_fields=["book"])

        preview = preview_membership_generation(book_entry)
        self.assertEqual(preview["specification"]["parts"][-1]["url"], ARTICLE)
        self.assertTrue(any(ARTICLE in warning for warning in preview["warnings"]))
        self.assertEqual(
            preview["binding"]["sources"][ARTICLE]["kind"],
            "capture",
        )
        generated = generate_from_membership(
            book_entry, self.reviewer, "Include the retained member.",
            preview["revision"], preview["digest"],
        )
        self.assertEqual(
            generated.document_version.evidence["book_membership_binding"],
            preview["binding"],
        )
        self.assertEqual(
            build_lineage(generated.document)["nodes"][f"edition:{generated.pk}"][
                "integrity_errors"
            ],
            [],
        )
        generated.document.refresh_from_db()
        self.assertEqual(generated.document.reader_target().pk, generated.pk)
        self.assertFalse(generated.document.reader_selection_explicit)

        missing_url = "https://www.marxists.org/francais/test/unretained.htm"
        CatalogueEntry.objects.create(
            site=self.sites["www.marxists.org"],
            url=missing_url,
            title="Unretained member",
            book=book_entry,
        )
        with self.assertRaisesMessage(ValueError, "Missing retained pages"):
            preview_membership_generation(book_entry)

    def test_membership_generation_refuses_a_stale_preview(self):
        book_entry = CatalogueEntry.objects.get(url=BOOK)
        preview = preview_membership_generation(book_entry)
        member = book_entry.chapters.first()
        member.membership_reviewed = True
        member.save(update_fields=["membership_reviewed"])
        count = Rendition.objects.count()

        with self.assertRaisesMessage(ValueError, "changed since preview"):
            generate_from_membership(
                book_entry, self.reviewer, "Stale membership preview.",
                preview["revision"], preview["digest"],
            )
        self.assertEqual(Rendition.objects.count(), count)

    def test_membership_generation_binds_retained_assets_to_new_version(self):
        body = b"retained generation asset"
        digest = store_blob(body)
        Blob.objects.create(digest=digest, media_type="image/png", size=len(body))
        manifest = {
            "pages": self.book.snapshot.manifest["pages"],
            "assets": {
                "https://www.marxists.org/test/generation-asset.png": {
                    "digest": digest,
                    "media_type": "image/png",
                    "size": len(body),
                },
            },
        }
        Snapshot.objects.create(
            document=self.book.document,
            digest=snapshot_digest(manifest),
            manifest=manifest,
            warnings=[],
        )
        book_entry = CatalogueEntry.objects.get(url=BOOK)
        preview = preview_membership_generation(book_entry)
        asset_url = "https://www.marxists.org/test/generation-asset.png"
        self.assertEqual(preview["binding"]["assets"][asset_url]["digest"], digest)
        self.assertIn(asset_url, preview["binding"]["asset_sources"])

        generated = generate_from_membership(
            book_entry, self.reviewer, "Bind retained asset evidence.",
            preview["revision"], preview["digest"],
        )
        self.assertEqual(
            generated.document_version.evidence["book_membership_binding"],
            preview["binding"],
        )
        self.assertTrue(
            RenditionAsset.objects.filter(rendition=generated, blob_id=digest).exists()
        )

    def test_membership_generation_view_requires_confirmation_and_fresh_preview(self):
        book_entry = CatalogueEntry.objects.get(url=BOOK)
        url = reverse("document-editor-membership", args=[self.book.pk])
        before = Rendition.objects.count()
        preview = self.client.post(url, {
            "action": "generation-preview",
            "reason": "Build from current catalogue membership.",
        })
        self.assertEqual(preview.status_code, 200)
        self.assertContains(preview, "Review membership-seeded edition")
        token = preview.context["generation_token"]

        unconfirmed = self.client.post(url, {
            "action": "generation-apply", "generation_token": token,
        })
        self.assertEqual(unconfirmed.status_code, 422)
        self.assertEqual(BookMembershipGeneration.objects.count(), 0)

        member = book_entry.chapters.first()
        member.membership_reviewed = True
        member.save(update_fields=["membership_reviewed"])
        stale = self.client.post(url, {
            "action": "generation-apply", "generation_token": token, "confirm": "yes",
        })
        self.assertEqual(stale.status_code, 422)
        self.assertContains(stale, "changed since preview", status_code=422)
        self.assertEqual(Rendition.objects.count(), before)
        self.assertEqual(BookMembershipGeneration.objects.count(), 0)

        fresh = self.client.post(url, {
            "action": "generation-preview",
            "reason": "Build from current catalogue membership.",
        })
        generated = self.client.post(url, {
            "action": "generation-apply",
            "generation_token": fresh.context["generation_token"],
            "confirm": "yes",
        })
        self.assertEqual(generated.status_code, 200)
        self.assertContains(generated, "Source edition saved")
        self.assertEqual(BookMembershipGeneration.objects.count(), 1)

    def test_take_member_from_another_book_rebuilds_donor(self):
        second_url = BOOK.replace("/test/", "/second/")
        with patch.object(
            Fetcher,
            "fetch",
            side_effect=lambda url, **kw: Response(
                url, book_index() if url == second_url else chapter(1), "text/html", {}
            ),
        ):
            enqueue(second_url)
            second = process_job(claim_job())
        self.assertIsNotNone(second)
        donor_spec = current_spec(second_url)
        changed = deepcopy(self.spec)
        changed["parts"].append(donor_spec["parts"][1])
        decision = self.publish(changed)
        self.assertEqual(len(decision.after), 2)
        self.assertEqual(second.document.latest().structure["pages"], 2)
        self.assertEqual(self.book.document.latest().structure["pages"], 4)

    def test_combining_using_an_existing_article_as_root_retires_its_old_reader(self):
        enqueue(ARTICLE)
        original = process_job(claim_job())
        combined = current_spec(ARTICLE)
        combined["book"] = True
        combined["parts"].append(self.spec["parts"][1])
        self.publish(combined)
        current = original.document.latest()
        self.assertTrue(current.structure["book"])
        self.assertEqual(current.structure["pages"], 2)
        self.assertEqual(
            self.client.get(reverse("reader", args=[original.pk])).url,
            reverse("reader", args=[current.pk]) + "#c1",
        )
        self.assertEqual(
            self.client.get(reverse("reader-css", args=[original.pk])).url,
            reverse("reader-css", args=[current.pk]),
        )
        self.assertEqual(
            self.client.get(reverse("reader-pdf", args=[original.pk])).url,
            reverse("reader-pdf", args=[current.pk]) + "#c1",
        )

    def test_failed_build_rolls_back_all_versions_membership_and_decision(self):
        changed = deepcopy(self.spec)
        changed["parts"].pop()
        preview = self.prepare(changed)
        counts = (Rendition.objects.count(), Job.objects.count())
        from library.services.pipeline import publish

        calls = 0

        def failing(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise ValueError("Second work failed")
            return publish(*args, **kwargs)

        with patch("library.services.pipeline.publish", side_effect=failing):
            with self.assertRaisesMessage(ValueError, "Second work failed"):
                commit_change(preview, self.reviewer, "Detach")
        self.assertEqual((Rendition.objects.count(), Job.objects.count()), counts)
        self.assertEqual(CatalogueEntry.objects.get(url=BOOK).chapters.count(), 2)
        self.assertFalse(ContentOrganization.objects.exists())
        self.assertFalse(ContentOrganizationDecision.objects.exists())

    def test_stale_preview_rejects_another_review_or_new_capture(self):
        preview = self.prepare(self.spec)
        capture = CrawlCapture.objects.create(
            site=self.sites["www.marxists.org"],
            url=BOOK,
            response=save_response(self.response(BOOK), BOOK),
        )
        with self.assertRaisesMessage(ValueError, "changed since preview"):
            commit_change(preview, self.reviewer, "Old preview")
        self.assertFalse(ContentOrganizationDecision.objects.exists())
        capture.delete()
        self.publish(self.spec)
        with self.assertRaisesMessage(ValueError, "changed since preview"):
            commit_change(preview, self.reviewer, "Concurrent review")

    def test_source_change_during_preview_cannot_be_signed_as_current(self):
        from library.services.pipeline import format_rendition

        def change_during_format(*args, **kwargs):
            result = format_rendition(*args, **kwargs)
            CrawlCapture.objects.create(
                site=self.sites["www.marxists.org"],
                url=BOOK,
                response=save_response(self.response(BOOK), BOOK),
            )
            return result

        with patch("library.services.pipeline.format_rendition", side_effect=change_during_format):
            with self.assertRaisesMessage(ValueError, "changed while building"):
                self.prepare(self.spec)
        self.assertFalse(ContentOrganizationDecision.objects.exists())

    def test_validation_missing_duplicate_reason_empty_and_active_work(self):
        changed = deepcopy(self.spec)
        changed["parts"][0]["url"] = BOOK.replace("index.htm", "missing.htm")
        with self.assertRaisesMessage(ValueError, "Missing retained page"):
            self.prepare(changed)
        changed = deepcopy(self.spec)
        changed["parts"].append(changed["parts"][0])
        with self.assertRaisesMessage(ValueError, "Duplicate page"):
            self.prepare(changed)
        changed["parts"] = []
        with self.assertRaisesMessage(ValueError, "must contain"):
            self.prepare(changed)
        preview = self.prepare(self.spec)
        with self.assertRaisesMessage(ValueError, "1-2000"):
            commit_change(preview, self.reviewer, " ")
        enqueue(BOOK, Job.Mode.REFRESH)
        with self.assertRaisesMessage(ValueError, "active import"):
            self.prepare(self.spec)

    def test_audit_is_append_only_and_conflicting_undo_is_blocked(self):
        decision = self.publish(self.spec)
        for action in (
            lambda: ContentOrganizationDecision.objects.filter(pk=decision.pk).update(reason="x"),
            lambda: ContentOrganizationDecision.objects.filter(pk=decision.pk).delete(),
        ):
            with self.assertRaisesMessage(IntegrityError, "append-only"), transaction.atomic():
                action()
        changed = deepcopy(self.spec)
        changed["parts"].reverse()
        self.publish(changed)
        with self.assertRaisesMessage(ValueError, "changed after"):
            undo_plan(decision)
