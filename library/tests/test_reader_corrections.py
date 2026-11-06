from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from library.models import CrawlCapture, Job, SourceCorrection
from library.services.catalogue import configured_sites
from library.services.corrections import rendition_correction_sources
from library.services.fetch import Fetcher, Response
from library.services.pipeline import claim_job, enqueue, process_job
from library.services.storage import save_response
from library.tests.test_sources import ARTICLE, BOOK, PARAGRAPH, article_html, book_index, chapter


@override_settings(ALLOWED_HOSTS=["testserver"])
class ReaderCorrectionTests(TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        settings = override_settings(DATA_DIR=Path(temporary.name))
        settings.enable()
        self.addCleanup(settings.disable)
        self.sites = {site.host: site for site in configured_sites()}
        self.reviewer = get_user_model().objects.create_user("reviewer")
        self.reviewer.groups.add(Group.objects.get(name="Metadata reviewers"))
        self.reader = get_user_model().objects.create_user("reader")
        self.client.force_login(self.reviewer)
        self.content = article_html()
        self.fetch = patch.object(Fetcher, "fetch", side_effect=self.response).start()
        self.addCleanup(patch.stopall)

    def response(self, url, *, asset=False):
        body = self.content
        if url == BOOK:
            body = book_index()
        elif url.endswith("chapter1.htm"):
            body = chapter(1)
        elif url.endswith("chapter2.htm"):
            body = chapter(2)
        return Response(url, body, "text/html", {"content-type": "text/html"})

    def import_version(self, url):
        enqueue(url)
        result = process_job(claim_job())
        self.assertIsNotNone(result)
        return result

    def reformat(self, version):
        enqueue(version.document.url, Job.Mode.REFORMAT, version.snapshot)
        with patch("library.versions.FORMAT_VERSION", "reader-correction-test"):
            result = process_job(claim_job())
        self.assertIsNotNone(result)
        return result

    def test_cached_import_only_source_created_on_post_once_without_network_or_get_writes(self):
        original = self.import_version(ARTICLE)
        version = self.reformat(original)
        original_state = (
            version.html,
            version.metadata,
            version.structure,
            version.snapshot.manifest,
        )
        self.assertFalse(CrawlCapture.objects.exists())
        self.fetch.reset_mock()
        response = self.client.get(reverse("reader", args=[version.pk]))
        self.assertContains(response, "Review this work")
        self.assertNotContains(response, "Correct this retained source")
        response = self.client.get(reverse("rendition-corrections", args=[version.pk]))
        self.assertContains(
            response, "this historical rendition and its annotations remain unchanged"
        )
        self.assertFalse(CrawlCapture.objects.exists())
        endpoint = reverse("rendition-correction-source", args=[version.pk])
        self.assertEqual(self.client.get(endpoint).status_code, 405)
        response = self.client.post(endpoint, {"page": "0"})
        capture = CrawlCapture.objects.get()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url.split("?", 1)[0], reverse("document-editor", args=[version.pk])
        )
        self.assertIn("start=source", response.url)
        self.assertIn(f"review_capture={capture.pk}", response.url)
        self.assertIn(f"review_version={version.pk}", response.url)
        self.assertEqual(capture.response, version.snapshot.manifest["pages"][0])
        self.assertEqual(capture.url, ARTICLE)
        self.client.post(endpoint, {"page": "0"})
        self.assertEqual(CrawlCapture.objects.count(), 1)
        self.assertContains(
            self.client.get(reverse("rendition-corrections", args=[version.pk])),
            "Source editor — selected content",
        )
        self.fetch.assert_not_called()
        version.refresh_from_db()
        self.assertEqual(
            (version.html, version.metadata, version.structure, version.snapshot.manifest),
            original_state,
        )
        self.assertFalse(SourceCorrection.objects.exists())

    def test_old_reformatted_snapshot_maps_exact_capture_not_newest(self):
        old_capture = CrawlCapture.objects.create(
            site=self.sites["communistusa.org"],
            url=ARTICLE,
            response=save_response(self.response(ARTICLE), ARTICLE),
        )
        version = self.reformat(self.import_version(ARTICLE))
        self.content = article_html("<p>New source evidence</p>")
        latest = CrawlCapture.objects.create(
            site=old_capture.site,
            url=ARTICLE,
            response=save_response(self.response(ARTICLE), ARTICLE),
        )
        wrong_url = CrawlCapture.objects.create(
            site=old_capture.site,
            url=ARTICLE + "another/",
            response=old_capture.response,
        )
        sources = rendition_correction_sources(version)
        self.assertEqual(sources[0]["capture"], old_capture)
        response = self.client.get(reverse("rendition-corrections", args=[version.pk]))
        self.assertContains(response, "Source editor")
        for capture in (old_capture, latest, wrong_url):
            legacy_url = reverse("correction-workspace", args=[capture.pk])
            self.assertNotContains(response, f'href="{legacy_url}"')
        response = self.client.post(
            reverse("rendition-correction-source", args=[version.pk]), {"page": "0"}
        )
        editor_url = urlsplit(response.url)
        query = parse_qs(editor_url.query)
        self.assertEqual(editor_url.path, reverse("document-editor", args=[version.pk]))
        self.assertEqual(query["start"], ["source"])
        self.assertEqual(query["review_capture"], [str(old_capture.pk)])
        self.assertEqual(query["review_version"], [str(version.pk)])
        self.assertEqual(CrawlCapture.objects.count(), 3)

    def test_book_offers_exact_contents_and_each_retained_chapter(self):
        version = self.reformat(self.import_version(BOOK))
        sources = rendition_correction_sources(version)
        self.assertEqual(len(sources), 3)
        self.assertEqual(sources[0]["label"], "Book metadata / contents / cover images")
        self.assertEqual(sources[1]["label"], "First chapter")
        self.assertEqual(sources[2]["label"], "Second chapter")
        response = self.client.get(reverse("rendition-corrections", args=[version.pk]))
        for source in sources:
            self.assertContains(response, source["url"])
            self.assertContains(response, source["label"])
            response = self.client.post(
                reverse("rendition-correction-source", args=[version.pk]),
                {"page": str(source["index"])},
            )
            capture = CrawlCapture.objects.get(url=source["url"])
            self.assertEqual(capture.response["digest"], source["page"]["digest"])
            self.assertEqual(response.status_code, 302)
            self.assertEqual(
                response.url.split("?", 1)[0],
                reverse("document-editor", args=[version.pk]),
            )
            self.assertIn(f"review_capture={capture.pk}", response.url)
            self.assertIn("start=source", response.url)
            response = self.client.get(reverse("rendition-corrections", args=[version.pk]))
        self.assertEqual(CrawlCapture.objects.count(), 3)

    def test_permission_csrf_invalid_selection_and_staff_access(self):
        version = self.import_version(ARTICLE)
        endpoint = reverse("rendition-correction-source", args=[version.pk])
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.reviewer)
        self.assertEqual(strict.post(endpoint, {"page": "0"}).status_code, 403)
        self.client.force_login(self.reader)
        self.assertNotContains(
            self.client.get(reverse("reader", args=[version.pk])),
            "Correct content parsing",
        )
        self.assertEqual(
            self.client.get(reverse("rendition-corrections", args=[version.pk])).status_code,
            403,
        )
        self.assertEqual(self.client.post(endpoint, {"page": "0"}).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.post(endpoint, {"page": "0"}).status_code, 302)
        self.assertFalse(CrawlCapture.objects.exists())
        self.client.force_login(self.reviewer)
        for value in ("-1", "1", "garbage", ""):
            self.assertEqual(self.client.post(endpoint, {"page": value}).status_code, 302)
        self.assertFalse(CrawlCapture.objects.exists())
        staff = get_user_model().objects.create_user("staff", is_staff=True)
        self.client.force_login(staff)
        self.assertContains(
            self.client.get(reverse("reader", args=[version.pk])),
            "Review this work",
        )
        self.client.post(endpoint, {"page": "0"})
        self.assertEqual(CrawlCapture.objects.count(), 1)

    def test_retired_chapter_post_redirects_without_creating_capture(self):
        chapter_url = BOOK.replace("index.htm", "chapter1.htm")
        old = self.import_version(chapter_url)
        complete = self.import_version(BOOK)
        self.assertFalse(CrawlCapture.objects.exists())
        endpoint = reverse("rendition-correction-source", args=[old.pk])
        response = self.client.post(endpoint, {"page": "0"})
        self.assertEqual(response.url, reverse("reader", args=[complete.pk]) + "#c2")
        self.assertEqual(
            self.client.get(reverse("rendition-corrections", args=[old.pk])).url,
            reverse("reader", args=[complete.pk]) + "#c2",
        )
        self.assertFalse(CrawlCapture.objects.exists())

    def test_reader_keeps_entire_book_and_toc_with_one_separate_reviewer_link(self):
        version = self.reformat(self.import_version(BOOK))
        with patch("library.services.corrections.rendition_correction_sources") as sources:
            response = self.client.get(reverse("reader", args=[version.pk]))
            sources.assert_not_called()
        page = BeautifulSoup(response.content, "html.parser")
        article = page.select_one("article.reader-content")
        retained = BeautifulSoup(version.html, "html.parser")
        self.assertEqual(article.get_text(), retained.get_text())
        self.assertEqual(len(article.select(":scope > section")), 3)
        self.assertEqual(article.get_text().count(PARAGRAPH), 2)
        self.assertEqual(len(page.select(".toc-panel a")), len(version.structure["toc"]) + 1,
                         "Navigation adds the generated metadata page.")
        self.assertEqual(page.select(".toc-panel a")[-1]["href"], "#document-metadata")
        links = [
            link
            for link in page.select(".reader-review-entry a")
            if link.get_text(strip=True) == "Review this work"
        ]
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["href"], reverse("work-review") + f"?review_version={version.pk}")
        self.assertIsNone(page.select_one("#parsing-corrections"))
        self.assertIsNone(page.select_one(".reader-toolbar + .page-container"))
        self.assertNotContains(response, "Correct this retained source")
        self.assertNotContains(response, reverse("rendition-correction-source", args=[version.pk]))
        self.assertNotContains(response, "Correct content organization")
        self.assertFalse(CrawlCapture.objects.exists())
        overview = BeautifulSoup(self.client.get(links[0]["href"]).content, "html.parser")
        landing_url = overview.find("a", string="Document editor")["href"]
        with patch("library.document_editor_views.finders.find", return_value="built-asset"):
            landing = self.client.get(landing_url)
        self.assertContains(landing, "Book metadata / contents")
        self.assertContains(landing, "First chapter")
        self.assertContains(landing, "Second chapter")
        self.assertFalse(CrawlCapture.objects.exists())
