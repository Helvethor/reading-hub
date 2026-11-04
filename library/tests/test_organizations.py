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
    Job,
    Rendition,
)
from library.profile import get_profile
from library.services.catalogue import configured_sites, register_book
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

    def test_review_ui_permission_confirmation_csrf_and_tamper_checks(self):
        url = reverse("content-organization")
        self.assertContains(self.client.get(url, {"url": BOOK}), "Correct content organization")
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
        self.assertContains(response, "Content organization published")
        self.assertEqual(ContentOrganizationDecision.objects.get().profile, get_profile().key)

    def test_save_controls_precede_advanced_json_and_preview_details(self):
        from bs4 import BeautifulSoup

        url = reverse("content-organization")
        response = self.client.get(url, {"url": BOOK})
        soup = BeautifulSoup(response.content, "html.parser")
        editor = soup.select_one("#organization-editor")
        self.assertEqual(editor["action"], "#organization-preview")
        self.assertEqual(
            soup.select_one('a[href="#organization-save"]').text, "Review and save changes"
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
            confirm.select_one("button").text, "Save organization and publish editions"
        )
        self.assertEqual(confirm.find_next_sibling("h3").text, "Before")
        self.assertFalse(ContentOrganizationDecision.objects.exists())
