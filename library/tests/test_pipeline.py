import io
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from PIL import Image

from library.models import Blob, Document, FetchCheck, Job, Rendition, Snapshot
from library.services.errors import ImportFailure, LimitExceeded
from library.services.fetch import Response
from library.services.pipeline import claim_job, enqueue, process_job, recover_interrupted
from library.services.storage import blob_path, read_blob, store_blob
from library.tests.test_sources import ARTICLE, BOOK, PARAGRAPH, article_html, book_index, chapter
from library.views import toc_tree


def png(color="green"):
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), color).save(buffer, format="PNG")
    return buffer.getvalue()


class PipelineTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings_override = override_settings(
            DATA_DIR=Path(self.temp.name), ALLOWED_HOSTS=["testserver"]
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.content = article_html()
        self.image = png()
        self.mock = patch("library.services.pipeline.Fetcher.fetch", side_effect=self.fetch).start()
        self.addCleanup(patch.stopall)

    def fetch(self, url, *, asset=False):
        if asset:
            return Response(url, self.image, "image/png", {})
        if url == BOOK:
            content = book_index()
        elif url.endswith("chapter1.htm"):
            content = chapter(1)
        elif url.endswith("chapter2.htm"):
            content = chapter(2)
        else:
            content = self.content
        return Response(url, content, "text/html", {"content-type": "text/html"})

    def import_article(self):
        job = enqueue(ARTICLE)
        claimed = claim_job()
        self.assertEqual(claimed.pk, job.pk)
        result = process_job(claimed)
        job.refresh_from_db()
        self.assertEqual(job.status, Job.Status.READY, job.error)
        return result

    def test_form_worker_reader_and_pdf_rejection(self):
        client = Client()
        response = client.post("/request/", {"url": ARTICLE})
        self.assertEqual(response.status_code, 302)
        call_command("run_import_worker", once=True, stdout=io.StringIO())
        job = Job.objects.get()
        self.assertEqual(job.status, "ready", job.error)
        response = client.get(f"/versions/{job.rendition_id}/")
        self.assertContains(response, PARAGRAPH)
        self.assertContains(response, "Formatting rules")
        self.assertIn("img-src 'self'", response.headers["Content-Security-Policy"])
        self.assertEqual(client.get(f"/jobs/{job.pk}/status/").json()["status"], "ready")
        self.assertContains(
            client.get(f"/documents/{job.document_id}/versions/", follow=True),
            "Lineage &amp; versions",
        )
        response = client.post(
            "/request/",
            {
                "url": "https://www.marxists.org/francais/test/test.pdf",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "PDFs", status_code=400)

    def test_cache_hit_and_active_job_deduplication(self):
        first = enqueue(ARTICLE)
        self.assertEqual(enqueue(ARTICLE).pk, first.pk)
        version = process_job(claim_job())
        self.mock.reset_mock()
        self.assertEqual(enqueue(ARTICLE).pk, version.pk)
        self.mock.assert_not_called()
        self.assertEqual(Job.objects.count(), 1)

    def test_unchanged_refresh_records_check_not_duplicate(self):
        first = self.import_article()
        enqueue(ARTICLE, Job.Mode.REFRESH)
        second = process_job(claim_job())
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Snapshot.objects.count(), 1)
        self.assertEqual(FetchCheck.objects.count(), 2)
        self.assertEqual(FetchCheck.objects.order_by("-pk").first().outcome, "unchanged")

    def test_source_changes_preserve_old_versions(self):
        first = self.import_article()
        old_html = first.html
        self.content = article_html("<h2>New section</h2><p>New text</p>")
        enqueue(ARTICLE, Job.Mode.REFRESH)
        second = process_job(claim_job())
        first.refresh_from_db()
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(first.html, old_html)
        self.assertEqual(Rendition.objects.count(), 2)
        self.assertEqual(first.document.latest().pk, second.pk)

    def test_reformat_offline_and_pipeline_versioning(self):
        first = self.import_article()
        self.mock.reset_mock()
        enqueue(ARTICLE, Job.Mode.REFORMAT, first.snapshot)
        with patch("library.versions.FORMAT_VERSION", "future-test-version"):
            second = process_job(claim_job())
        self.mock.assert_not_called()
        self.assertEqual(Snapshot.objects.count(), 1)
        self.assertEqual(second.snapshot_id, first.snapshot_id)
        self.assertEqual(second.format_version, "future-test-version")
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(FetchCheck.objects.count(), 1)

    def test_original_stylesheet_preserved(self):
        first = self.import_article()
        with patch("pathlib.Path.read_text", return_value=".reader-content {color: blue}"):
            enqueue(ARTICLE, Job.Mode.REFORMAT, first.snapshot)
            second = process_job(claim_job())
        first.refresh_from_db()
        self.assertNotEqual(first.stylesheet, second.stylesheet)
        self.assertContains(Client().get(f"/versions/{first.pk}/reader.css"), first.stylesheet)

    def test_capitalization_is_consistent_across_reader_toc_metadata_and_library(self):
        self.content = article_html(
            "<h2><em>THE CIA</em> AND MARX</h2><p>KEEP THIS BODY PARAGRAPH UNCHANGED.</p>",
            title="THE THEORY OF MARX",
        ).replace(b"Test Author", b"ALAN WOODS")
        version = self.import_article()
        self.assertEqual(version.title, "The theory of Marx")
        self.assertEqual(version.metadata["author"], "Alan Woods")
        version.document.refresh_from_db()
        self.assertEqual(version.document.title, "The theory of Marx")
        self.assertEqual(version.structure["toc"][1]["title"], "The CIA and Marx")
        self.assertIn("<em>The CIA</em> and Marx", version.html)
        self.assertIn("KEEP THIS BODY PARAGRAPH UNCHANGED.", version.html)
        for path in ["/", f"/versions/{version.pk}/"]:
            self.assertContains(Client().get(path), "The theory of Marx")
        self.assertContains(Client().get(f"/versions/{version.pk}/"), "Alan Woods")

    def test_capitalization_reformat_keeps_original_snapshot_and_old_version(self):
        self.content = article_html(title="THE THEORY OF MARX")
        with patch(
            "library.services.pipeline.normalize_capitalization", side_effect=lambda s, **kw: s
        ):
            old = self.import_article()
        old_html = old.html
        self.mock.reset_mock()
        enqueue(ARTICLE, Job.Mode.REFORMAT, old.snapshot)
        new = process_job(claim_job())
        self.mock.assert_not_called()
        self.assertEqual(new.title, "The theory of Marx")
        self.assertEqual(new.snapshot_id, old.snapshot_id)
        old.refresh_from_db()
        self.assertEqual(old.title, "THE THEORY OF MARX")
        self.assertEqual(old.html, old_html)

    def test_image_changes_at_same_url_create_snapshot(self):
        self.content = article_html('<img src="/test.png" alt="Example">')
        first = self.import_article()
        first_digest = first.assets.get().blob_id
        self.image = png("red")
        enqueue(ARTICLE, Job.Mode.REFRESH)
        second = process_job(claim_job())
        self.assertNotEqual(first.snapshot_id, second.snapshot_id)
        self.assertNotEqual(first_digest, second.assets.get().blob_id)
        response = Client().get(f"/assets/{first_digest}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Type"], "image/png")
        response.close()

    def test_image_failure_is_visible_and_offline(self):
        self.content = article_html('<img src="/test.png" alt="Example">')
        original = self.fetch

        def missing(url, *, asset=False):
            if asset:
                raise ImportFailure("Image not found", "http")
            return original(url)

        self.mock.side_effect = missing
        version = self.import_article()
        self.assertEqual(len(version.warnings), 1)
        self.assertIn("Image unavailable", version.html)
        self.assertNotIn("<img", version.html)
        self.assertContains(Client().get(f"/versions/{version.pk}/"), "Some images")

    def test_limit_failure_does_not_publish_partial(self):
        old = self.import_article()
        enqueue(ARTICLE, Job.Mode.REFRESH)
        self.mock.side_effect = LimitExceeded("Resource limit reached")
        with self.assertLogs("library", level="ERROR"):
            self.assertIsNone(process_job(claim_job()))
        self.assertEqual(Rendition.objects.count(), 1)
        self.assertEqual(old.document.latest().pk, old.pk)
        self.assertEqual(Job.objects.order_by("-created_at").first().error_code, "limit")

    def test_failed_chapter_does_not_publish_book(self):
        original = self.fetch

        def failed(url, *, asset=False):
            if url.endswith("chapter2.htm"):
                raise ImportFailure("Required chapter failed", "incomplete")
            return original(url, asset=asset)

        self.mock.side_effect = failed
        enqueue(BOOK)
        with self.assertLogs("library", level="ERROR"):
            process_job(claim_job())
        self.assertFalse(Rendition.objects.exists())
        self.assertFalse(Snapshot.objects.exists())
        self.assertEqual(Job.objects.get().status, "failed")

    def test_book_unique_ordered_pages(self):
        enqueue(BOOK)
        version = process_job(claim_job())
        self.assertIsNotNone(version, Job.objects.get().error)
        self.assertEqual(version.structure["pages"], 3)
        self.assertEqual(self.mock.call_count, 3)
        self.assertEqual(len(version.snapshot.manifest["pages"]), 3)
        soup = BeautifulSoup(version.html, "html.parser")
        self.assertLess(
            soup.get_text().index("First chapter"), soup.get_text().index("Second chapter")
        )

    def test_french_accent_reformat_updates_all_surfaces_without_network_or_source_changes(self):
        from library.tests.test_sources import book_index

        french_url = BOOK.replace("/test/", "/francais/test/")

        def french_source(url, *, asset=False):
            if url == french_url:
                body = (
                    book_index()
                    .replace("Un livre illustré".encode("windows-1252"), b"L'ETAT ET LA REVOLUTION")
                    .replace(b"Test Author", b"V. LENINE")
                )
                body = body.replace(b"First chapter", b"LA SOCIETE ET L'ETAT")
                body = body.replace(b"Part two", b"LES BASES ECONOMIQUES")
            else:
                body = chapter(1).replace(b"Subsection 1", b"LA REVOLUTION")
                body = body.replace(PARAGRAPH.encode(), b"REVOLUTION. " + PARAGRAPH.encode())
            return Response(url, body, "text/html", {})

        self.mock.side_effect = french_source
        enqueue(french_url)
        with (
            patch("library.sources.capitalization.FRENCH_ACCENTS", {}),
            patch("library.sources.capitalization.FRENCH_NAMES", {}),
            patch("library.versions.FORMAT_VERSION", "2"),
        ):
            old = process_job(claim_job())
        self.assertEqual(old.title, "L'etat et la revolution")
        original_manifest = old.snapshot.manifest
        old_html = old.html
        self.mock.reset_mock()
        enqueue(french_url, Job.Mode.REFORMAT, old.snapshot)
        new = process_job(claim_job())
        self.mock.assert_not_called()
        self.assertEqual(new.title, "L'état et la révolution")
        self.assertEqual(new.metadata["author"], "V. Lénine")
        self.assertEqual(new.snapshot_id, old.snapshot_id)
        self.assertEqual(new.snapshot.manifest, original_manifest)
        new.document.refresh_from_db()
        self.assertEqual(new.document.title, new.title)
        self.assertIn("La société et l'état", [item["title"] for item in new.structure["toc"]])
        self.assertIn("Les bases économiques", [item["title"] for item in new.structure["toc"]])
        parsed = BeautifulSoup(new.html, "html.parser")
        for item in new.structure["toc"]:
            self.assertEqual(parsed.find(id=item["id"]).get_text(" ", strip=True), item["title"])
        self.assertIn("<p>REVOLUTION.", new.html)
        old.refresh_from_db()
        self.assertEqual(old.title, "L'etat et la revolution")
        self.assertEqual(old.html, old_html)
        self.assertContains(Client().get(f"/versions/{new.pk}/"), "L&#x27;état et la révolution")
        self.assertContains(Client().get("/"), "L&#x27;état et la révolution")

    def test_interrupted_job_recovery_and_retry(self):
        job = enqueue(ARTICLE)
        claim_job()
        Job.objects.filter(pk=job.pk).update(heartbeat=timezone.now() - timedelta(minutes=6))
        recover_interrupted()
        job.refresh_from_db()
        self.assertEqual(job.error_code, "interrupted")
        response = Client().post(f"/jobs/{job.pk}/retry/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Job.objects.filter(status="queued").count(), 1)

    def test_reformat_requires_own_snapshot(self):
        version = self.import_article()
        with self.assertRaises(ImportFailure):
            enqueue("https://communistusa.org/another/", Job.Mode.REFORMAT, version.snapshot)
        self.assertEqual(Document.objects.count(), 1)

    def test_asset_storage_integrity_and_unpublished_asset_not_served(self):
        digest = store_blob(b"original")
        self.assertEqual(read_blob(digest), b"original")
        Blob.objects.create(digest=digest, media_type="image/png", size=8)
        self.assertEqual(Client().get(f"/assets/{digest}/").status_code, 404)
        blob_path(digest).write_bytes(b"corrupted")
        with self.assertRaises(OSError):
            read_blob(digest)
        with self.assertRaises(ValueError):
            blob_path("../../escape")

    def test_missing_published_asset_reports_failure(self):
        self.content = article_html('<img src="/test.png">')
        version = self.import_article()
        digest = version.assets.get().blob_id
        blob_path(digest).unlink()
        with self.assertLogs("library", level="ERROR"):
            self.assertEqual(Client().get(f"/assets/{digest}/").status_code, 503)

    def test_csrf_and_post_only_actions(self):
        version = self.import_article()
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post("/request/", {"url": ARTICLE}).status_code, 403)
        self.assertEqual(client.get(f"/versions/{version.pk}/reformat/").status_code, 405)
        self.assertEqual(client.get(f"/documents/{version.document_id}/refresh/").status_code, 405)

    def test_valid_csrf_cookie_and_origin_work_but_null_origin_is_rejected(self):
        client = Client(enforce_csrf_checks=True)
        page = client.get("/")
        self.assertEqual(page.headers["Referrer-Policy"], "same-origin")
        parsed = BeautifulSoup(page.content, "html.parser")
        token = parsed.select_one("input[name=csrfmiddlewaretoken]")["value"]
        response = client.post(
            "/request/",
            {"url": ARTICLE, "csrfmiddlewaretoken": token},
            HTTP_ORIGIN="http://testserver",
        )
        self.assertEqual(response.status_code, 302)
        with self.assertLogs("library", level="WARNING"):
            response = client.post(
                "/request/", {"url": ARTICLE, "csrfmiddlewaretoken": token}, HTTP_ORIGIN="null"
            )
        self.assertContains(response, "security cookie or page token", status_code=403)
        self.assertEqual(Job.objects.count(), 1)

    def test_stored_source_disk_failure_is_reported(self):
        enqueue(ARTICLE)
        with patch("library.services.storage.store_blob", side_effect=OSError("Disk full")):
            with self.assertLogs("library", level="ERROR"):
                process_job(claim_job())
        self.assertEqual(Job.objects.get().error, "Disk full")
        self.assertFalse(Rendition.objects.exists())

    def test_toc_tree_handles_level_gaps(self):
        tree = toc_tree(
            [
                {"id": "a", "title": "First", "level": 2},
                {"id": "b", "title": "Nested", "level": 4},
                {"id": "c", "title": "Next", "level": 2},
            ]
        )
        self.assertEqual(len(tree), 2)
        self.assertEqual(tree[0]["children"][0]["id"], "b")

    def test_resolved_url_alias_opens_existing_cache(self):
        original = self.fetch
        resolved_url = "https://communistusa.org/resolved/"

        def redirect(url, *, asset=False):
            result = original(url, asset=asset)
            result.url = resolved_url
            return result

        self.mock.side_effect = redirect
        first = self.import_article()
        self.mock.reset_mock()
        self.assertEqual(enqueue(resolved_url).pk, first.pk)
        self.assertEqual(Document.objects.count(), 1)
        self.mock.assert_not_called()

    def test_corrupted_image_is_a_warning_not_a_successful_remote_image(self):
        self.content = article_html('<img src="/test.png" alt="Broken illustration">')
        self.image = b"not an image"
        with self.assertLogs("library", level="WARNING"):
            version = self.import_article()
        self.assertEqual(len(version.warnings), 1)
        self.assertIn("Image unavailable: Broken illustration", version.html)

    def test_second_worker_is_rejected(self):
        import fcntl

        with (Path(self.temp.name) / "worker.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesMessage(CommandError, "already running"):
                call_command("run_import_worker", once=True, stdout=io.StringIO())
