import json
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from library.models import (
    Annotation,
    CatalogueEntry,
    ContentOrganization,
    ContentOrganizationDecision,
    CrawlCapture,
    Document,
    DocumentDraftBase,
    DocumentEditRevision,
    DocumentPublication,
    Job,
    PageTypeDecision,
    Rendition,
    SourceCorrection,
)
from library.profile import get_profile
from library.services.catalogue import configured_sites, register_book
from library.services.errors import ImportFailure
from library.services.fetch import Fetcher, Response
from library.services.organizations import (
    change_plan,
    commit_change,
    current_spec,
    preview_change,
    undo_plan,
)
from library.services.pipeline import claim_job, enqueue, process_job
from library.services.storage import save_response
from library.tests.test_sources import ARTICLE, BOOK, article_html, book_index, chapter


@override_settings(ALLOWED_HOSTS=["testserver"])
class OrganizationTests(TestCase):
    @override_settings(READING_HUB_EDITOR_PILOT=True)
    def test_editor_membership_panel_previews_publishes_and_undoes_without_replacing_drafts(self):
        from bs4 import BeautifulSoup

        from library.services.document_edits import create_draft

        draft = create_draft(self.book, self.reviewer)
        draft_state = (draft.rendition_id, draft.document, draft.evidence)
        path = reverse("document-editor-membership", args=[self.book.pk])
        embedded_path = path + "?embedded=1"
        initial = self.client.get(path)
        self.assertEqual(initial.status_code, 200)
        self.assertContains(initial, "Retained page membership")
        self.assertContains(initial, "Attach URL")
        self.assertEqual(initial.context["version"], self.book)
        embedded = self.client.get(path, {"embedded": "1"})
        self.assertEqual(embedded.status_code, 200)
        self.assertTrue(embedded.editor_panel)
        self.assertEqual(embedded["X-Frame-Options"], "SAMEORIGIN")
        self.assertIn("frame-ancestors 'self'", embedded["Content-Security-Policy"])
        embedded_soup = BeautifulSoup(embedded.content, "html.parser")
        self.assertIn("?embedded=1", embedded_soup.select_one("#organization-editor")["action"])
        self.assertIn(
            "?embedded=1",
            embedded_soup.select_one("form[action*='membership']")["action"],
        )

        changed = deepcopy(self.spec)
        changed["parts"].reverse()
        preview = self.client.post(
            embedded_path,
            {
                "action": "preview",
                "reason": "Reorder retained chapters",
                "specification": json.dumps(changed),
            },
        )
        self.assertEqual(preview.status_code, 200)
        self.assertContains(preview, "Preview: all affected works")
        self.assertEqual(preview.context["preview"]["before"], [self.spec])
        self.assertFalse(ContentOrganizationDecision.objects.exists())

        token = preview.context["token"]
        missing_acknowledgement = self.client.post(
            embedded_path, {"action": "apply", "token": token}
        )
        self.assertEqual(missing_acknowledgement.status_code, 422)
        self.assertFalse(ContentOrganizationDecision.objects.exists())

        saved = self.client.post(
            embedded_path,
            {
                "action": "apply",
                "token": token,
                "preserve_annotations": "yes",
            },
        )
        self.assertEqual(saved.status_code, 200)
        self.assertContains(saved, "Membership published")
        self.assertContains(saved, "Switch to a newly published source edition")
        self.assertEqual(saved.context["saved_decision"].after[0]["parts"], changed["parts"])
        self.assertEqual(saved.context["decisions"][0], saved.context["saved_decision"])
        self.assertContains(saved, "Preview audited undo")
        self.assertEqual(saved["Cache-Control"], "no-store")
        self.assertTrue(saved.editor_panel)
        self.assertTrue(DocumentDraftBase.objects.filter(pk=draft.pk).exists())
        draft.refresh_from_db()
        self.assertEqual(
            (draft.rendition_id, draft.document, draft.evidence),
            draft_state,
        )
        self.assertEqual(ContentOrganizationDecision.objects.count(), 1)

        undo_preview = self.client.post(
            embedded_path,
            {
                "action": "undo-preview",
                "decision": saved.context["saved_decision"].pk,
                "reason": "Restore the prior retained order",
            },
        )
        self.assertEqual(undo_preview.status_code, 200)
        self.assertEqual(undo_preview.context["preview"]["after"], [self.spec])
        undone = self.client.post(
            embedded_path,
            {
                "action": "apply",
                "token": undo_preview.context["token"],
                "preserve_annotations": "yes",
            },
        )
        self.assertEqual(undone.status_code, 200)
        self.assertEqual(undone.context["decisions"][0], undone.context["saved_decision"])
        self.assertEqual(ContentOrganizationDecision.objects.count(), 2)
        self.assertEqual(ContentOrganizationDecision.objects.latest("pk").undo_of_id,
                         saved.context["saved_decision"].pk)
        self.assertTrue(DocumentDraftBase.objects.filter(pk=draft.pk).exists())
        draft.refresh_from_db()
        self.assertEqual(
            (draft.rendition_id, draft.document, draft.evidence),
            draft_state,
        )

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
    def test_retired_organization_reports_disabled_editor_for_selected_edition(self):
        response = self.client.get(
            reverse("content-organization"),
            {"review_version": self.book.pk},
        )
        self.assertEqual(response.status_code, 503)
        self.assertContains(
            response,
            "document editor is currently disabled",
            status_code=503,
        )

    @override_settings(READING_HUB_EDITOR_PILOT=True)
    def test_membership_panel_blocks_missing_sources_and_stale_previews(self):
        path = reverse("document-editor-membership", args=[self.book.pk])
        missing = deepcopy(self.spec)
        missing["parts"][0]["url"] = BOOK.replace("index.htm", "missing.htm")
        response = self.client.post(
            path,
            {
                "action": "preview",
                "reason": "Attach a source that is not retained",
                "specification": json.dumps(missing),
            },
        )
        self.assertEqual(response.status_code, 422)
        self.assertContains(response, "Missing retained page", status_code=422)
        self.assertFalse(ContentOrganizationDecision.objects.exists())

        changed = deepcopy(self.spec)
        changed["parts"].reverse()
        preview = self.client.post(
            path,
            {
                "action": "preview",
                "reason": "Reorder retained chapters",
                "specification": json.dumps(changed),
            },
        )
        self.assertEqual(preview.status_code, 200)
        CrawlCapture.objects.create(
            site=self.sites["www.marxists.org"],
            url=BOOK,
            response=save_response(self.response(BOOK), BOOK),
        )
        stale = self.client.post(
            path,
            {
                "action": "apply",
                "token": preview.context["token"],
                "preserve_annotations": "yes",
            },
        )
        self.assertEqual(stale.status_code, 422)
        self.assertContains(stale, "changed since preview", status_code=422)
        self.assertFalse(ContentOrganizationDecision.objects.exists())

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
        membership_path = reverse("document-editor-membership", args=[self.book.pk])
        response = self.client.post(
            membership_path,
            {
                "action": "preview",
                "reason": "Set the reviewed book hierarchy",
                "specification": json.dumps(changed),
            },
        )
        self.assertEqual(response.status_code, 200)
        token = response.context["token"]
        response = self.client.post(
            membership_path,
            {"action": "apply", "token": token, "preserve_annotations": "yes"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Membership published")
        new_book = Document.objects.get(url=BOOK).latest()
        self.assertIn(
            (BOOK, new_book.pk), response.context["saved_renditions"]
        )

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

    @override_settings(READING_HUB_EDITOR_PILOT=True)
    def test_review_ui_permission_confirmation_csrf_and_tamper_checks(self):
        url = reverse("document-editor-membership", args=[self.book.pk])
        self.assertContains(self.client.get(url), "Retained page membership")
        response = self.client.post(
            url,
            {
                "action": "preview",
                "specification": json.dumps(self.spec),
                "reason": "Verified",
            },
        )
        self.assertContains(response, "Before")
        token = response.context["token"]
        self.assertFalse(ContentOrganizationDecision.objects.exists())
        self.assertEqual(
            self.client.post(
                url,
                {
                    "action": "apply",
                    "token": token,
                },
            ).status_code,
            422,
        )
        self.assertEqual(
            self.client.post(
                url,
                {
                    "action": "apply",
                    "token": token + "bad",
                    "preserve_annotations": "yes",
                },
            ).status_code,
            422,
        )
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.reviewer)
        self.assertEqual(
            strict.post(
                url,
                {
                    "action": "apply",
                    "token": token,
                    "preserve_annotations": "yes",
                },
            ).status_code,
            403,
        )
        other = get_user_model().objects.create_user("unauthorized")
        self.client.force_login(other)
        self.assertEqual(self.client.get(url, {"url": BOOK}).status_code, 403)
        self.client.force_login(self.reviewer)
        response = self.client.post(
            url,
            {
                "action": "apply",
                "token": token,
                "preserve_annotations": "yes",
            },
        )
        self.assertContains(response, "Membership published")
        self.assertEqual(ContentOrganizationDecision.objects.get().profile, get_profile().key)

    @override_settings(READING_HUB_EDITOR_PILOT=True)
    def test_save_controls_precede_advanced_json_and_preview_details(self):
        from bs4 import BeautifulSoup

        url = reverse("document-editor-membership", args=[self.book.pk])
        response = self.client.get(url)
        soup = BeautifulSoup(response.content, "html.parser")
        editor = soup.select_one("#organization-editor")
        self.assertEqual(editor["action"], url + "#organization-preview")
        self.assertEqual(
            soup.select_one('a[href="#organization-save"]').text,
            "Review and save membership changes",
        )
        actions = editor.select_one("#organization-save")
        self.assertEqual(actions.find_next_sibling("details")["id"], "organization-advanced")
        self.assertTrue(actions.select_one('textarea[name="reason"]').has_attr("required"))
        self.assertEqual(actions.select_one("button")["value"], "preview")
        self.assertFalse(soup.select("#organization-confirm"))
        response = self.client.post(
            url,
            {
                "action": "preview",
                "specification": json.dumps(self.spec),
                "reason": "Review",
            },
        )
        soup = BeautifulSoup(response.content, "html.parser")
        preview = soup.select_one("#organization-preview")
        confirm = preview.select_one("#organization-confirm")
        self.assertEqual(confirm.select_one('input[name="action"]')["value"], "apply")
        self.assertTrue(
            confirm.select_one('input[name="preserve_annotations"]').has_attr("required")
        )
        self.assertEqual(
            confirm.select_one("button").text, "Save membership and publish affected editions"
        )
        self.assertEqual(confirm.find_next_sibling("h3").text, "Before")
        self.assertFalse(ContentOrganizationDecision.objects.exists())
