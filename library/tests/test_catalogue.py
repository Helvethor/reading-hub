import io
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from library.models import (
    Blob,
    CatalogueEntry,
    CrawlCapture,
    CrawlPage,
    CrawlSite,
    Document,
    Job,
    MetadataSuggestion,
    Rendition,
    Snapshot,
)
from library.services.catalogue import (
    FETCHERS,
    CrawlPaused,
    change_site,
    configured_sites,
    crawl_step,
    recover_crawls,
    register_book,
    save_entry,
)
from library.services.errors import ImportFailure, LimitExceeded
from library.services.fetch import Fetcher, Response
from library.services.pipeline import claim_job, enqueue, process_job
from library.services.storage import blob_path, read_blob, save_response
from library.sources.base import parse_html
from library.sources.catalogue import CatalogueLink
from library.tests import test_pipeline
from library.tests.test_sources import ARTICLE, BOOK, article_html, book_index, chapter
from profiles.marxist.catalogue import MarxistCatalogue
from profiles.marxist.site import PROFILE

ROOT = "https://communistusa.org/"
INDEX = b"""<html lang="en"><body>
<article><h2><a href="/sample/">SAMPLE ARTICLE</a></h2>
<span class="author">ALAN WOODS</span><time datetime="2026-10-16"></time></article>
<a href="/sample/#notes">Duplicate</a><a href="/category/theory/">Theory</a>
<a href="https://evil.example/private">External</a><a href="/book.pdf">PDF</a>
</body></html>"""


@override_settings(ALLOWED_HOSTS=["testserver"])
class CatalogueTests(TestCase):
    def test_book_registration_routes_chapters_to_one_book_and_preserves_old_versions(self):
        from library.sources.adapters import discover

        site = CrawlSite.objects.get(host="www.marxists.org")
        source = discover(parse_html(book_index()), BOOK)
        book_document = Document.objects.create(url=BOOK, title=source.title)
        book_snapshot = Snapshot.objects.create(
            document=book_document, digest="e" * 64, manifest={"parts": []}
        )
        complete = Rendition.objects.create(
            document=book_document,
            snapshot=book_snapshot,
            identity="f" * 64,
            title=source.title,
            structure={
                "book": True,
                "toc": [],
                "pages": 2,
                "parts": [
                    {"url": part.url, "id": f"c{index + 1}"}
                    for index, part in enumerate(source.parts)
                ],
            },
            html="<section id='c1'>First</section><section id='c2'>Second</section>",
        )
        book = register_book(site, BOOK, source)
        self.assertEqual(book.chapters.count(), 2)
        chapter_url = source.parts[1].url
        old_document = Document.objects.create(url=chapter_url, title="Historical chapter")
        snapshot = Snapshot.objects.create(document=old_document, digest="c" * 64, manifest={})
        old = Rendition.objects.create(
            document=old_document,
            snapshot=snapshot,
            identity="d" * 64,
            title=old_document.title,
            structure={"toc": []},
            html="<p>Original chapter text</p>",
        )
        self.assertEqual(enqueue(chapter_url), complete)
        job = enqueue(chapter_url, Job.Mode.REFRESH)
        self.assertEqual(job.document.url, BOOK)
        self.assertEqual(enqueue(source.parts[1].url).pk, job.pk)
        self.assertEqual(enqueue(chapter_url, Job.Mode.REFRESH).pk, job.pk)
        self.assertEqual(
            enqueue(chapter_url, Job.Mode.REFORMAT, snapshot).document_id, book_document.pk
        )
        self.assertEqual(self.client.get(reverse("home")).context["page"].paginator.count, 1)
        self.assertEqual(
            self.client.get(reverse("reader", args=[old.pk])).url,
            reverse("reader", args=[complete.pk]) + "#c2",
        )
        response = self.client.get(reverse("catalogue"), {"q": source.title})
        self.assertContains(response, source.title)
        self.assertNotContains(response, "First chapter")
        register_book(site, BOOK, source)
        self.assertEqual(book.chapters.count(), 2)
        old.refresh_from_db()
        self.assertEqual(old.html, "<p>Original chapter text</p>")

    def test_retained_book_registration_is_offline_and_dry_run_by_default(self):
        site = CrawlSite.objects.get(host="www.marxists.org")
        CrawlCapture.objects.create(
            site=site,
            url=BOOK,
            response=save_response(Response(BOOK, book_index(), "text/html", {}), BOOK),
        )
        with patch.object(Fetcher, "fetch") as fetch:
            call_command("register_catalogue_book", BOOK, stdout=io.StringIO())
            self.assertFalse(CatalogueEntry.objects.filter(url=BOOK).exists())
            call_command("register_catalogue_book", BOOK, apply=True, stdout=io.StringIO())
        fetch.assert_not_called()
        self.assertEqual(CatalogueEntry.objects.get(url=BOOK).chapters.count(), 0)

    def test_crawl_book_registers_chapters_without_hiding_contents_as_an_index(self):
        site = CrawlSite.objects.get(host="www.marxists.org")
        change_site(site, "resume")
        site.frontier.all().delete()
        CrawlPage.objects.create(site=site, url=BOOK, is_article=False)
        with patch.object(
            Fetcher, "fetch", return_value=Response(BOOK, book_index(), "text/html", {})
        ):
            self.assertTrue(crawl_step(site_id=site.pk))
        book = CatalogueEntry.objects.get(site=site, url=BOOK)
        self.assertEqual(book.chapters.count(), 0)
        self.assertFalse(book.discovery_only)
        self.assertIsNone(book.book_id)

    def test_manual_page_type_survives_later_crawl_and_undo_restores_new_capture(self):
        from library.services.page_types import classify

        self.site.frontier.all().delete()
        capture = CrawlCapture.objects.create(
            site=self.site,
            url=ARTICLE,
            response=save_response(Response(ARTICLE, INDEX, "text/html", {}), ARTICLE),
        )
        entry = CatalogueEntry.objects.create(site=self.site, url=ARTICLE, title="Listing")
        page = CrawlPage.objects.create(site=self.site, url=ARTICLE, is_article=True)
        decision = classify(
            capture,
            get_user_model().objects.get(username="administrator"),
            "discovery",
            "This is a source listing",
            "0",
        )
        # A stale article frontier hint must not override the reviewer's decision.
        page.is_article = True
        page.save(update_fields=["is_article"])
        self.site.fetch_articles = True
        self.site.save(update_fields=["fetch_articles"])
        with patch.object(Fetcher, "fetch", return_value=Response(ARTICLE, INDEX, "text/html", {})):
            self.assertTrue(crawl_step(site_id=self.site.pk))
        self.assertEqual(self.site.captures.filter(url=ARTICLE).count(), 2)
        self.assertFalse(self.site.captures.filter(url=ARTICLE, discovery_only=False).exists())
        self.assertEqual(entry.metadata_suggestions.count(), 0)
        self.assertTrue(self.site.frontier.exclude(pk=page.pk).exists())
        classify(
            capture, decision.reviewer, "undo", "Restore automatic detection", str(decision.pk)
        )
        self.assertFalse(self.site.captures.filter(url=ARTICLE, discovery_only=True).exists())

    def test_discovery_errors_are_visible_on_all_import_actions_and_history_survives(self):
        url = "https://www.marxists.org/deutsch/referenz/goldman/index.htm"
        site = CrawlSite.objects.get(host="www.marxists.org")
        CrawlCapture.objects.create(site=site, url=url, response={}, discovery_only=True)
        entry = CatalogueEntry.objects.create(site=site, url=url, title="Index")
        document = Document.objects.create(url=url, title="Historical index")
        snapshot = Snapshot.objects.create(document=document, digest="a" * 64, manifest={})
        rendition = Rendition.objects.create(
            document=document,
            snapshot=snapshot,
            identity="b" * 64,
            title=document.title,
            structure={"toc": []},
            html="<p>Original cached index</p>",
        )
        job = Job.objects.create(document=document, snapshot=snapshot, status=Job.Status.FAILED)
        for name, pk in [
            ("catalogue-open", entry.pk),
            ("refresh", document.pk),
            ("reformat", rendition.pk),
            ("retry", job.pk),
        ]:
            with self.subTest(action=name):
                self.assertContains(
                    self.client.post(reverse(name, args=[pk])),
                    "This URL is a discovery index, not an article or a book.",
                    status_code=400,
                )
        self.assertEqual(Job.objects.filter(document=document).count(), 1)
        self.assertEqual(self.client.get(reverse("home")).context["page"].paginator.count, 0)
        self.assertContains(
            self.client.get(reverse("reader", args=[rendition.pk])), "Original cached index"
        )

    def test_author_index_is_discovery_only_but_book_contents_remain_readable(self):
        index_url = "https://www.marxists.org/deutsch/referenz/goldman/index.htm"
        markup = (
            "<html><body><h1>Emma Goldman</h1>"
            "<p>Zur Zeit sind folgende Texte in Deutsch verfügbar:</p>"
            '<p><a href="1911/patriotismus.htm">Patriotismus</a></p></body></html>'
        ).encode()
        soup = parse_html(markup)
        self.assertTrue(MarxistCatalogue.is_discovery_page(soup, index_url))
        self.assertIsNone(MarxistCatalogue.metadata(soup, index_url))
        from library.sources.adapters import discover

        with self.assertRaisesMessage(ImportFailure, "discovery index"):
            discover(soup, index_url)
        self.assertFalse(MarxistCatalogue.is_discovery_page(parse_html(book_index()), BOOK))
        self.assertTrue(discover(parse_html(book_index()), BOOK).book)

    def test_reclassify_retained_index_hides_work_and_reviews_without_deleting_evidence(self):
        url = "https://www.marxists.org/deutsch/referenz/goldman/index.htm"
        site = CrawlSite.objects.get(host="www.marxists.org")
        broken_url = "https://www.marxists.org/deutsch/referenz/goldman/invalid.htm"
        broken = CrawlCapture.objects.create(
            site=site,
            url=broken_url,
            response=save_response(
                Response(
                    broken_url,
                    b'<html><meta charset="windows-1252"><body>\x9d</body></html>',
                    "text/html",
                    {},
                ),
                broken_url,
            ),
        )
        capture = CrawlCapture.objects.create(
            site=site,
            url=url,
            response=save_response(
                Response(url, b"<html><body><h1>Emma Goldman</h1></body></html>", "text/html", {}),
                url,
            ),
        )
        entry = CatalogueEntry.objects.create(
            site=site, url=url, title="Emma Goldman index", language="de"
        )
        page = CrawlPage.objects.create(site=site, url=url, is_article=True, status="done")
        suggestion = MetadataSuggestion.objects.create(
            capture=capture,
            entry=entry,
            field="author",
            value="Navigation text",
            method="test",
            fingerprint="9" * 64,
        )
        output = io.StringIO()
        errors = io.StringIO()
        call_command("classify_discovery_pages", stdout=output, stderr=errors)
        self.assertIn(f"Skipped unclassifiable capture {broken.pk}", errors.getvalue())
        capture.refresh_from_db()
        self.assertFalse(capture.discovery_only)
        call_command("classify_discovery_pages", apply=True, stdout=output, stderr=errors)
        broken.refresh_from_db()
        self.assertFalse(broken.discovery_only)
        capture.refresh_from_db()
        entry.refresh_from_db()
        self.assertTrue(capture.discovery_only)
        self.assertTrue(entry.discovery_only)
        page.refresh_from_db()
        self.assertFalse(page.is_article)
        self.assertEqual(page.status, "pending")
        self.assertEqual(read_blob(capture.response["digest"])[:6], b"<html>")
        self.assertNotContains(self.client.get(reverse("catalogue")), "Emma Goldman index")
        self.assertNotContains(self.client.get(reverse("metadata-review")), "Navigation text")
        self.assertRedirects(
            self.client.get(reverse("correction-workspace", args=[capture.pk])),
            reverse("work-review"),
            fetch_redirect_response=False,
        )
        response = self.client.post(
            reverse("metadata-review-decision", args=[suggestion.pk]),
            {"action": "approve"},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            self.client.post(reverse("catalogue-open", args=[entry.pk])).status_code, 404
        )
        with self.assertRaisesMessage(ImportFailure, "discovery index"):
            enqueue(url)
        self.assertContains(
            self.client.post(reverse("request"), {"url": url}),
            "This URL is a discovery index, not an article or a book.",
            status_code=400,
        )
        self.assertFalse(Job.objects.filter(document__url=url).exists())
        suggestion.refresh_from_db()
        self.assertEqual(suggestion.status, "pending")
        self.assertEqual(CrawlCapture.objects.filter(pk=capture.pk).count(), 1)

    def test_index_primary_evidence_does_not_hide_author_proposal_from_a_real_work(self):
        site = CrawlSite.objects.get(host="www.marxists.org")
        url = "https://www.marxists.org/deutsch/referenz/goldman/index.htm"
        index = CrawlCapture.objects.create(
            site=site,
            url=url,
            response=save_response(
                Response(url, b"<html><body><h1>Emma Goldman</h1></body></html>", "text/html", {}),
                url,
            ),
        )
        work_url = "https://www.marxists.org/deutsch/referenz/goldman/1911/test.htm"
        markup = (
            '<html><body><p class="author">Emma Goldman</p><h1>A readable work</h1>'
            "<p>" + "A sufficiently long prose paragraph about reading. " * 6 + "</p></body></html>"
        ).encode()
        work = CrawlCapture.objects.create(
            site=site,
            url=work_url,
            response=save_response(Response(work_url, markup, "text/html", {}), work_url),
        )
        evidence = [{"url": url}, {"url": work_url}]
        suggestion = MetadataSuggestion.objects.create(
            capture=index,
            field="author",
            value="Emma Goldman",
            method="test",
            fingerprint="8" * 64,
            evidence=evidence,
        )
        call_command("classify_discovery_pages", apply=True, stdout=io.StringIO())
        suggestion.refresh_from_db()
        self.assertEqual(suggestion.capture_id, work.pk)
        self.assertEqual(suggestion.evidence, evidence)
        self.assertEqual(suggestion.status, "pending")
        self.assertContains(self.client.get(reverse("metadata-review")), "Emma Goldman")

    def test_mislabelled_index_crawl_still_discovers_works(self):
        site = CrawlSite.objects.get(host="www.marxists.org")
        change_site(site, "resume")
        site.fetch_articles = True
        site.save(update_fields=["fetch_articles"])
        site.frontier.all().delete()
        url = "https://www.marxists.org/deutsch/referenz/goldman/index.htm"
        entry = CatalogueEntry.objects.create(site=site, url=url, title="Index")
        page = CrawlPage.objects.create(site=site, url=url, is_article=True)
        markup = (
            "<html><body><h1>Emma Goldman</h1>"
            '<p><a href="1911/patriotismus.htm">Patriotismus</a></p></body></html>'
        ).encode()
        with patch.object(Fetcher, "fetch", return_value=Response(url, markup, "text/html", {})):
            self.assertTrue(crawl_step(site_id=site.pk))
        page.refresh_from_db()
        entry.refresh_from_db()
        self.assertEqual(page.status, "done")
        self.assertFalse(page.is_article)
        self.assertTrue(entry.discovery_only)
        self.assertTrue(site.frontier.filter(url__endswith="1911/patriotismus.htm").exists())
        self.assertTrue(site.captures.get(url=url).discovery_only)

    def test_memory_failure_pauses_only_its_source_before_another_worker_can_retry(self):
        other = CrawlSite.objects.exclude(pk=self.site.pk).first()
        other.enabled = True
        other.save()
        with (
            patch.object(Fetcher, "fetch", side_effect=MemoryError),
            patch("library.services.workers.release_memory_limit") as release,
            self.assertRaises(MemoryError),
        ):
            crawl_step(site_id=self.site.pk)
        release.assert_called_once()
        self.site.refresh_from_db()
        other.refresh_from_db()
        self.assertFalse(self.site.enabled)
        self.assertEqual(self.site.status, "failed")
        self.assertIn("Memory allocation failed", self.site.error)
        self.assertTrue(other.enabled)
        self.assertFalse(crawl_step(site_id=self.site.pk))

    def setUp(self):
        self.client.force_login(
            get_user_model().objects.create_user("administrator", is_staff=True)
        )
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        settings = override_settings(DATA_DIR=Path(temp.name))
        settings.enable()
        self.addCleanup(settings.disable)
        FETCHERS.clear()
        configured_sites()
        self.site = CrawlSite.objects.get(host="communistusa.org")
        change_site(self.site, "resume")
        self.settings_data = {
            "max_pages": 100,
            "max_bytes": 1000000,
            "max_urls": 100,
            "request_interval": 2,
            "action": "resume",
        }

    def fetch(self, fetcher, url, **options):
        body = article_html() if url == ARTICLE else INDEX if url == ROOT else b"<html></html>"
        fetcher.downloaded += len(body)
        return Response(url, body, "text/html", {})

    def step(self):
        with patch.object(Fetcher, "fetch", autospec=True, side_effect=self.fetch):
            return crawl_step()

    def test_all_sources_initialized_paused_without_fetching(self):
        self.assertEqual(CrawlSite.objects.count(), len(PROFILE.sources))
        self.assertEqual(CrawlSite.objects.filter(enabled=False).count(), len(PROFILE.sources) - 1)
        self.assertEqual(CatalogueEntry.objects.count(), 0)

    def test_allowed_external_redirect_is_not_catalogued_or_followed(self):
        with patch.object(
            Fetcher,
            "fetch",
            return_value=Response(
                "https://adv-verlag.ch/produkt/abonnement-der-kommunist",
                b'<html><a href="https://adv-verlag.ch/other">Other</a></html>',
                "text/html",
                {},
            ),
        ):
            crawl_step(site_id=self.site.pk)
        self.assertFalse(CatalogueEntry.objects.exists())
        self.assertFalse(CrawlCapture.objects.exists())
        self.assertFalse(self.site.frontier.filter(url__contains="adv-verlag").exists())
        self.assertEqual(self.site.frontier.get().status, "done")

    def test_index_catalogue_deduplicates_and_does_not_publish_content(self):
        self.step()
        entry = CatalogueEntry.objects.get(url=ARTICLE)
        self.assertEqual(entry.title, "Sample article")
        self.assertEqual(entry.author, "Alan Woods")
        self.assertEqual(entry.published, "2026-10-16")
        self.assertEqual(CatalogueEntry.objects.count(), 1)
        self.assertFalse(self.site.frontier.filter(url__contains="evil").exists())
        self.assertFalse(self.site.frontier.filter(url__endswith=".pdf").exists())
        for model in (Document, Job, Blob, Snapshot):
            self.assertEqual(model.objects.count(), 0)
        self.assertFalse(CrawlCapture.objects.exists())

    def test_article_fetch_is_per_site_and_can_be_enabled_after_skipping(self):
        seen = []

        def fetch(fetcher, url, **options):
            seen.append(url)
            return self.fetch(fetcher, url, **options)

        with patch.object(Fetcher, "fetch", autospec=True, side_effect=fetch):
            for _ in range(4):
                crawl_step()
            self.assertNotIn(ARTICLE, seen)
            self.site.refresh_from_db()
            self.assertEqual(self.site.status, "complete")
            change_site(self.site, "resume", {"fetch_articles": True})
            crawl_step()
            self.assertIn(ARTICLE, seen)
        self.assertIsNotNone(CatalogueEntry.objects.get(url=ARTICLE).checked_at)
        self.assertEqual(Snapshot.objects.count(), 0)
        capture = CrawlCapture.objects.get(url=ARTICLE)
        self.assertEqual(read_blob(capture.response["digest"]), article_html())
        self.assertEqual(capture.response["resolved_url"], ARTICLE)
        self.assertIn("retrieved_at", capture.response)
        other = CrawlSite.objects.get(host="marxist.com")
        self.assertFalse(other.fetch_articles)

    def test_page_and_byte_limits_pause_without_losing_queue(self):
        change_site(self.site, "save", {"max_pages": 1})
        self.step()
        self.step()
        self.site.refresh_from_db()
        self.assertEqual(
            (self.site.enabled, self.site.status, self.site.pages), (False, "limited", 1)
        )
        self.assertGreater(self.site.frontier.filter(status="pending").count(), 0)
        change_site(self.site, "resume", {"max_pages": 5})
        self.step()
        self.site.refresh_from_db()
        self.assertEqual(self.site.pages, 2)
        change_site(self.site, "save", {"max_bytes": self.site.downloaded})
        self.step()
        self.site.refresh_from_db()
        self.assertEqual(self.site.status, "limited")

    def test_url_limit_is_enforced_and_resume_revisits_unfinished_index(self):
        change_site(self.site, "save", {"max_urls": 1})
        self.step()
        self.site.refresh_from_db()
        self.assertEqual(self.site.status, "limited")
        self.assertEqual(self.site.frontier.count(), 1)
        self.assertEqual(self.site.frontier.get().status, "pending")
        change_site(self.site, "resume", {"max_urls": 10})
        self.step()
        self.assertTrue(CatalogueEntry.objects.filter(url=ARTICLE).exists())

    def test_pause_and_restart_retain_catalogue_and_reset_counters(self):
        self.step()
        change_site(self.site, "pause")
        with patch.object(Fetcher, "fetch") as fetch:
            self.assertFalse(crawl_step())
            fetch.assert_not_called()
        change_site(self.site, "restart")
        self.site.refresh_from_db()
        self.assertEqual((self.site.pages, self.site.downloaded), (0, 0))
        self.assertEqual(CatalogueEntry.objects.count(), 1)
        self.assertFalse(self.site.frontier.exclude(status="pending").exists())
        with self.assertRaises(ValueError):
            change_site(self.site, "restart")

    def test_interrupted_request_is_recovered(self):
        self.site.frontier.update(status="fetching")
        recover_crawls()
        self.assertTrue(self.site.frontier.filter(status="pending").exists())
        self.step()
        self.assertTrue(CatalogueEntry.objects.exists())

    def test_network_errors_are_visible_and_retryable(self):
        with patch.object(
            Fetcher, "fetch", side_effect=ImportFailure("Too many requests", "rate_limited")
        ):
            crawl_step()
        self.site.refresh_from_db()
        self.assertEqual(self.site.status, "failed")
        self.assertFalse(self.site.enabled)
        self.assertIn("Too many", self.site.error)
        self.assertEqual(self.site.frontier.get().status, "failed")
        change_site(self.site, "resume")
        self.assertEqual(self.site.frontier.get().status, "pending")

    def test_byte_failure_records_usage_and_keeps_request_pending(self):
        def failure(fetcher, url, **options):
            fetcher.downloaded = 1025
            raise LimitExceeded("Download exceeds limit")

        with patch.object(Fetcher, "fetch", autospec=True, side_effect=failure):
            crawl_step()
        self.site.refresh_from_db()
        self.assertEqual(self.site.downloaded, 1025)
        self.assertEqual(self.site.status, "limited")
        self.assertEqual(self.site.frontier.get().status, "pending")

    def test_sparse_index_does_not_erase_richer_article_metadata(self):
        link = CatalogueLink(ARTICLE, "Title", True, "Author", "1917", "Theory", "1910s")
        save_entry(self.site, link, checked=True)
        save_entry(self.site, CatalogueLink(ARTICLE, "Inferior hint", True))
        entry = CatalogueEntry.objects.get()
        self.assertEqual((entry.title, entry.era, entry.topic), ("Title", "1910s", "Theory"))

    def test_controls_validate_settings_and_show_progress(self):
        response = self.client.get(reverse("crawl-controls"))
        self.assertContains(response, "Catalogue crawling")
        self.assertContains(response, "Start / resume", count=len(PROFILE.sources))
        url = reverse("crawl-control", args=[self.site.pk])
        response = self.client.post(url, {**self.settings_data, "request_interval": 0})
        self.assertEqual(response.status_code, 400)
        response = self.client.post(url, {**self.settings_data, "fetch_articles": "on"})
        self.assertEqual(response.status_code, 302)
        self.site.refresh_from_db()
        self.assertTrue(self.site.fetch_articles)
        response = self.client.post(url, {"action": "pause"})
        self.assertEqual(response.status_code, 302)
        self.site.refresh_from_db()
        self.assertFalse(self.site.enabled)
        self.assertEqual(self.client.post(url, {"action": "bad"}).status_code, 400)

    def test_catalogue_hierarchy_search_sort_and_unknown_metadata(self):
        self.step()
        save_entry(self.site, CatalogueLink(ROOT + "z/", "Zebra", True))
        response = self.client.get(reverse("catalogue"), {"group": "era", "then": "topic"})
        self.assertContains(response, "Unknown era")
        branch = self.client.get(response.context["tree"]["children"][0]["url"])
        self.assertContains(branch, "Unknown topic")
        response = self.client.get(reverse("catalogue"), {"order": "title", "direction": "desc"})
        self.assertEqual(response.context["page"][0].title, "Zebra")
        response = self.client.get(reverse("catalogue"), {"q": "woods"})
        self.assertEqual(response.context["page"].paginator.count, 1)
        self.assertContains(self.client.get("/catalogue/?group=invalid"), "Unknown catalogue")
        with patch(
            "library.catalogue_views.get_profile", return_value=replace(PROFILE, page_size=1)
        ):
            response = self.client.get("/catalogue/?group=era&then=topic")
            self.assertContains(response, "group=era&amp;then=topic")

    def test_open_is_post_only_csrf_protected_and_enqueues_once(self):
        self.step()
        entry = CatalogueEntry.objects.get()
        url = reverse("catalogue-open", args=[entry.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(Client(enforce_csrf_checks=True).post(url).status_code, 403)
        with patch(
            "library.services.pipeline.Fetcher.fetch", side_effect=AssertionError("Network")
        ):
            self.assertEqual(self.client.post(url).status_code, 302)
            self.assertEqual(self.client.post(url).status_code, 302)
        self.assertEqual(Job.objects.count(), 1)

    def test_profile_can_disable_catalogue_without_touching_cache(self):
        disabled = replace(PROFILE, catalogue_enabled=False)
        with patch("library.catalogue_views.get_profile", return_value=disabled):
            for url in ("/catalogue/", "/crawlers/"):
                self.assertEqual(self.client.get(url).status_code, 404)
        with patch("library.services.catalogue.get_profile", return_value=disabled):
            self.assertFalse(crawl_step())

    def test_profile_requires_catalogue_contract_and_seeds(self):
        source = replace(PROFILE.sources[0], catalogue_adapter="")
        with self.assertRaises(ImproperlyConfigured):
            replace(PROFILE, sources=(source,), aliases={}).validate()
        source = replace(PROFILE.sources[0], catalogue_seeds=("https://evil.example/",))
        with self.assertRaises(ImproperlyConfigured):
            replace(PROFILE, sources=(source,), aliases={}).validate()

    def test_source_adapters_produce_metadata_without_body_storage(self):
        fixtures = {
            "https://www.marxists.org/archive/test/works/book.htm": (
                b"<h1>LENIN</h1><p class='titre'>THE STATE</p>"
            ),
            "https://marxist.com/test.htm": (
                b"<h1>Title</h1><div class='article-content'>Body</div>"
            ),
            "https://communisme.ch/fr/a/b/test/": (
                b"<h1>Title</h1><div class='post-text'>Body</div>"
            ),
            ARTICLE: article_html(),
        }
        for url, html in fixtures.items():
            with self.subTest(url=url):
                self.assertTrue(MarxistCatalogue.metadata(parse_html(html), url).title)

    def test_crawl_fetcher_does_not_follow_other_source_redirects(self):
        fetcher = Fetcher(source_host="communistusa.org")
        with (
            patch.object(fetcher, "_check_robots"),
            patch.object(fetcher, "_wait"),
            patch.object(
                fetcher,
                "_exchange",
                return_value=Response(
                    ROOT, b"", "", {"location": "https://marxist.com/test.htm"}, 302
                ),
            ) as exchange,
        ):
            with self.assertRaisesMessage(ImportFailure, "left its source"):
                fetcher.fetch(ROOT)
            self.assertEqual(exchange.call_count, 1)

    def test_per_site_rate_reaches_fetcher(self):
        change_site(self.site, "save", {"request_interval": 7})
        self.step()
        self.assertEqual(FETCHERS[self.site.pk].request_interval, 7)
        self.assertEqual(FETCHERS[self.site.pk].byte_limit, self.site.max_bytes)

    def test_archive_image_maps_and_navigation_are_index_links(self):
        soup = parse_html(b"""<map><area href="lenin/index.htm" alt="Lenin">
        <area href="authors.htm" alt="Authors"></map>
        <a href="lenin/works/1917/book.htm">A book</a>""")
        links = list(MarxistCatalogue.links(soup, "https://www.marxists.org/francais/"))
        self.assertEqual([link.is_article for link in links], [False, False, True])
        self.assertEqual(links[0].title, "Lenin")

    def test_listing_navigation_is_not_catalogued_as_articles(self):
        soup = parse_html(b"""<nav><a href="/about/">About</a>
        <a href="/category/theory/">Theory</a></nav>
        <h2><a href="/story/">A story</a></h2>""")
        links = list(MarxistCatalogue.links(soup, ROOT))
        self.assertEqual([link.title for link in links if link.is_article], ["A story"])

    def test_wordpress_category_menu_slug_remains_crawlable_without_becoming_an_article(self):
        soup = parse_html(b"""<li class="menu-item menu-item-object-category">
        <a href="/us-politics/">US politics</a></li>""")
        links = list(MarxistCatalogue.links(soup, ROOT))
        self.assertEqual(len(links), 1)
        self.assertFalse(links[0].is_article)

    def test_legacy_mobile_language_index_is_not_a_document(self):
        soup = parse_html(b'<a href="/english-mobiles.htm">English</a>')
        links = list(MarxistCatalogue.links(soup, "https://www.marxists.org/"))
        self.assertFalse(links[0].is_article)

    def test_pause_during_wait_returns_request_to_persistent_queue(self):
        def fetch(fetcher, url, **options):
            change_site(self.site, "pause")
            fetcher.progress("Waiting")

        with patch.object(Fetcher, "fetch", autospec=True, side_effect=fetch):
            crawl_step()
        self.site.refresh_from_db()
        self.assertEqual((self.site.enabled, self.site.status), (False, "paused"))
        self.assertEqual(self.site.frontier.get().status, "pending")

    def test_rate_wait_can_be_interrupted_without_sending_a_request(self):
        def paused(stage):
            raise CrawlPaused()

        fetcher = Fetcher(source_host=self.site.host, request_interval=7, progress=paused)
        fetcher.last_request = {self.site.host: 10}
        with patch("library.services.fetch.time.monotonic", return_value=11):
            with self.assertRaises(CrawlPaused):
                fetcher._wait(self.site.host)

    def test_worker_rotates_between_enabled_sources(self):
        other = CrawlSite.objects.get(host="marxist.com")
        change_site(other, "resume")
        self.step()
        self.step()
        other.refresh_from_db()
        self.assertEqual(other.pages, 1)

    def test_metadata_requests_are_not_starved_by_index_frontier(self):
        self.step()
        self.site.frontier.create(url=ROOT + "category/second/")
        change_site(self.site, "save", {"fetch_articles": True})
        self.step()
        self.assertTrue(CrawlCapture.objects.filter(url=ARTICLE).exists())

    def test_joomla_listing_author_and_date(self):
        soup = parse_html(b"""<article><h2><a href="/theory.htm">Theory</a></h2>
        <dd class="createdby"><span itemprop="name">Alan Woods</span></dd>
        <time datetime="2026-10-16"></time></article>""")
        link = next(MarxistCatalogue.links(soup, "https://marxist.com/"))
        self.assertEqual((link.author, link.published), ("Alan Woods", "2026-10-16"))

    def test_listing_category_metadata_is_kept(self):
        soup = parse_html(b"""<div class="dipi-blog-post category-theory category-highlights">
        <h2><a href="/story/">Story</a></h2></div>""")
        link = next(MarxistCatalogue.links(soup, ROOT))
        self.assertEqual(link.topic, "theory")

    def test_swiss_byline_uses_visible_author_not_wordpress_account(self):
        soup = parse_html(
            article_html(host="communisme.ch")
            .replace(b"<body>", b'<body><span class="author">de Caspar Oertli, redaction</span>')
            .replace(b'<meta name="author" content="Test Author">', b"")
        )
        link = MarxistCatalogue.metadata(soup, "https://communisme.ch/fr/theorie/story/")
        self.assertEqual(link.author, "Caspar Oertli, redaction")

    def test_structured_article_metadata_and_time_fallback(self):
        soup = parse_html(
            article_html().replace(
                b'<meta name="author" content="Test Author">',
                b"""<script type="application/ld+json">{"@graph":[{"@type":"Article",
            "author":{"name":"Source Author"},"datePublished":"1917-08-01",
            "articleSection":["Theory","History"]}]}</script>""",
            )
        )
        link = MarxistCatalogue.metadata(soup, ARTICLE)
        self.assertEqual(
            (link.author, link.published, link.topic),
            ("Source Author", "1917-08-01", "Theory, History"),
        )
        soup = parse_html(article_html(host="marxist.com") + b'<time datetime="2026-10-16"></time>')
        self.assertEqual(
            MarxistCatalogue.metadata(soup, "https://marxist.com/test.htm").published, "2026-10-16"
        )

    def test_source_absent_era_is_not_guessed_from_publication_date(self):
        soup = parse_html(article_html() + b'<time datetime="1917-08-01"></time>')
        self.assertEqual(MarxistCatalogue.metadata(soup, ARTICLE).era, "")

    def test_website_author_fallback_is_grouped_sorted_and_searchable(self):
        save_entry(self.site, CatalogueLink(ARTICLE, "No byline", True))
        save_entry(self.site, CatalogueLink(ROOT + "named/", "Named", True, author="Zelda Writer"))
        response = self.client.get("/catalogue/?group=author&then=&order=author")
        entries = list(response.context["page"])
        self.assertEqual(
            [entry.display_author for entry in entries], ["RCA · United States", "Zelda Writer"]
        )
        self.assertContains(response, "RCA · United States")
        self.assertNotContains(response, "Unknown author")
        response = self.client.get("/catalogue/", {"q": "RCA"})
        self.assertEqual(response.context["page"].paginator.count, 1)
        save_entry(
            self.site,
            CatalogueLink(ARTICLE, "No byline", True, author="Actual Writer"),
            checked=True,
        )
        response = self.client.get("/catalogue/", {"q": "Actual Writer"})
        self.assertEqual(response.context["page"][0].display_author, "Actual Writer")

    def test_article_capture_versions_are_retained_across_recrawls(self):
        self.site.frontier.all().delete()
        self.site.frontier.create(url=ARTICLE, is_article=True)
        change_site(self.site, "save", {"fetch_articles": True})
        self.step()
        first = CrawlCapture.objects.get()
        change_site(self.site, "pause")
        change_site(self.site, "restart")
        newer = article_html(title="New title")
        with patch.object(Fetcher, "fetch", return_value=Response(ARTICLE, newer, "text/html", {})):
            crawl_step()
        self.assertEqual(CrawlCapture.objects.count(), 2)
        self.assertEqual(read_blob(first.response["digest"]), article_html())
        self.assertEqual(read_blob(CrawlCapture.objects.latest("pk").response["digest"]), newer)

    def test_storage_errors_stop_the_crawl_and_remain_visible(self):
        self.site.frontier.all().delete()
        self.site.frontier.create(url=ARTICLE, is_article=True)
        change_site(self.site, "save", {"fetch_articles": True})
        with patch("library.services.catalogue.save_response", side_effect=OSError("Disk full")):
            with self.assertRaisesMessage(OSError, "Disk full"):
                self.step()
        self.site.refresh_from_db()
        self.assertEqual((self.site.enabled, self.site.status), (False, "failed"))
        self.assertIn("Disk full", self.site.error)
        self.assertFalse(CrawlCapture.objects.exists())


class CachedCatalogueTests(TestCase):
    setUp = test_pipeline.PipelineTests.setUp
    fetch = test_pipeline.PipelineTests.fetch
    import_article = test_pipeline.PipelineTests.import_article

    def capture(self, url=ARTICLE, body=None, resolved_url=None, headers=None):
        site = configured_sites().get(
            host="www.marxists.org"
            if url.startswith("https://www.marxists.org/")
            else "communistusa.org"
        )
        return CrawlCapture.objects.create(
            site=site,
            url=url,
            response=save_response(
                Response(resolved_url or url, body or article_html(), "text/html", headers or {}),
                url,
            ),
        )

    def test_crawler_cached_article_is_formatted_without_html_network_request(self):
        capture = self.capture(headers={"content-type": "text/html; charset=utf-8", "etag": "v1"})
        self.mock.side_effect = AssertionError("HTML fetched again")
        version = self.import_article()
        self.mock.assert_not_called()
        page = version.snapshot.manifest["pages"][0]
        self.assertEqual(page, capture.response)
        # Subsequent reformatting also works entirely offline.
        enqueue(ARTICLE, Job.Mode.REFORMAT, version.snapshot)
        self.assertIsNotNone(process_job(claim_job()))
        self.mock.assert_not_called()

    def test_latest_capture_is_used_and_refresh_bypasses_crawler_cache(self):
        self.capture(body=article_html(title="Older title"))
        newest = self.capture(body=article_html(title="Newer title"))
        version = self.import_article()
        self.assertEqual(version.title, "Newer title")
        self.assertEqual(version.snapshot.manifest["pages"][0]["digest"], newest.response["digest"])
        self.mock.assert_not_called()
        enqueue(ARTICLE, Job.Mode.REFRESH)
        refreshed = process_job(claim_job())
        self.assertEqual(refreshed.title, "Test article")
        self.mock.assert_called_once_with(ARTICLE)

    def test_cached_book_index_and_chapter_reuse_with_missing_chapter_fetched(self):
        self.capture(
            BOOK, book_index(), headers={"content-type": "text/html; charset=windows-1252"}
        )
        self.capture(BOOK.replace("index.htm", "chapter1.htm"), chapter(1))
        enqueue(BOOK)
        version = process_job(claim_job())
        self.assertIsNotNone(version)
        self.assertEqual(version.title, "Un livre illustré")
        self.mock.assert_called_once_with(BOOK.replace("index.htm", "chapter2.htm"))

    def test_cached_article_still_downloads_images_on_demand(self):
        self.capture(body=article_html('<img src="/picture.png" alt="Picture">'))
        version = self.import_article()
        self.mock.assert_called_once_with("https://communistusa.org/picture.png", asset=True)
        self.assertEqual(version.assets.count(), 1)

    def test_cached_corruption_is_an_explicit_import_failure_not_a_silent_refetch(self):
        capture = self.capture()
        blob_path(capture.response["digest"]).write_bytes(b"corrupt")
        enqueue(ARTICLE)
        self.assertIsNone(process_job(claim_job()))
        job = Job.objects.get()
        self.assertEqual(job.status, Job.Status.FAILED)
        self.assertIn("checksum mismatch", job.error)
        self.mock.assert_not_called()

    def test_cached_html_counts_towards_import_byte_limit(self):
        self.capture()
        enqueue(ARTICLE)
        with patch("library.services.pipeline.MAX_BYTES", 1):
            self.assertIsNone(process_job(claim_job()))
        self.assertEqual(Job.objects.get().error_code, "limit")
        self.mock.assert_not_called()

    def test_capture_redirect_can_be_reused_via_resolved_url(self):
        self.capture(url=ARTICLE + "old/", resolved_url=ARTICLE)
        self.import_article()
        self.mock.assert_not_called()

    def test_metadata_rebuild_uses_raw_captures_without_network_or_formatting(self):
        self.capture()
        site = configured_sites().get(host="communistusa.org")
        entry = CatalogueEntry.objects.create(site=site, url=ARTICLE, title="Hint")
        output = io.StringIO()
        call_command("rebuild_catalogue_metadata", stdout=output)
        entry.refresh_from_db()
        self.assertEqual(entry.author, "Test Author")
        self.assertEqual(Snapshot.objects.count(), 0)
        self.mock.assert_not_called()
        self.assertIn("no network used", output.getvalue())

    def test_catalogue_import_enriches_metadata_and_cache_hit_does_not_fetch(self):
        site = configured_sites().get(host="communistusa.org")
        entry = CatalogueEntry.objects.create(site=site, url=ARTICLE, title="Hint")
        version = self.import_article()
        entry.refresh_from_db()
        self.assertEqual(entry.title, version.title)
        self.assertEqual(entry.author, version.metadata["author"])
        self.assertIsNotNone(entry.checked_at)
        self.mock.reset_mock()
        response = self.client.post(reverse("catalogue-open", args=[entry.pk]))
        self.assertRedirects(response, reverse("reader", args=[version.pk]))
        self.mock.assert_not_called()
        self.assertEqual(Job.objects.count(), 1)

    def test_missing_source_author_defaults_to_website_and_preserves_real_author(self):
        self.content = article_html().replace(b'<meta name="author" content="Test Author">', b"")
        site = configured_sites().get(host="communistusa.org")
        entry = CatalogueEntry.objects.create(site=site, url=ARTICLE, title="Title")
        version = self.import_article()
        self.assertEqual(version.metadata["author"], "RCA · United States")
        self.assertTrue(version.metadata["author_is_fallback"])
        self.assertContains(
            self.client.get(reverse("reader", args=[version.pk])), "RCA · United States"
        )
        entry.refresh_from_db()
        self.assertEqual(entry.author, "")
        self.content = article_html()
        enqueue(ARTICLE, Job.Mode.REFRESH)
        named = process_job(claim_job())
        self.assertEqual(named.metadata["author"], "Test Author")
        self.assertFalse(named.metadata.get("author_is_fallback", False))

    def test_visible_byline_prevents_website_fallback(self):
        self.content = (
            article_html()
            .replace(b'<meta name="author" content="Test Author">', b"")
            .replace(b"<body>", b'<body><span class="author">By Actual Writer</span>')
        )
        version = self.import_article()
        self.assertEqual(version.metadata["author"], "Actual Writer")
        self.assertFalse(version.metadata.get("author_is_fallback", False))

    def test_old_reader_with_missing_author_has_display_fallback_without_changing_version(self):
        version = self.import_article()
        metadata = {**version.metadata, "author": ""}
        type(version).objects.filter(pk=version.pk).update(metadata=metadata)
        self.assertContains(
            self.client.get(reverse("reader", args=[version.pk])), "RCA · United States"
        )
        version.refresh_from_db()
        self.assertEqual(version.metadata["author"], "")
