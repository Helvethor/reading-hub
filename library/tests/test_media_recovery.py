import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image

from library.models import Blob, Document, Job, Rendition, Snapshot
from library.services.errors import ImportFailure, LimitExceeded
from library.services.fetch import Fetcher, Response
from library.services.media import fetch_image, image_request_url
from library.services.pipeline import claim_job, enqueue, process_job, snapshot_digest
from library.services.storage import read_blob, store_blob
from library.tests.test_pipeline import png
from library.tests.test_sources import ARTICLE, article_html

FAILED = "https://communistusa.org/wp-content/uploads/article photo.png"
ENCODED = FAILED.replace(" ", "%20")
MISSING = "https://communistusa.org/missing.png"
MARXIST_MEDIA = "https://media.marxist.com/2026/09/Environment_Image_own_work-jpg.webp"


class ImageRequestTests(SimpleTestCase):
    def test_path_spaces_are_encoded_but_existing_escapes_and_query_are_preserved(self):
        self.assertEqual(image_request_url(FAILED), ENCODED)
        self.assertEqual(
            image_request_url(ENCODED + "?size=10%20px&name=a+b#ignored"),
            ENCODED + "?size=10%20px&name=a+b",
        )

    def test_encoding_does_not_relax_url_policy(self):
        for url in [
            " https://communistusa.org/a.png", "https://communistusa.org/\ta.png",
            "https://communi\nstusa.org/a.png", "https://communistusa.org/a\r.png",
            "https://evil.example/a b.png", "https://communistusa.org /a.png",
            "https://user@communistusa.org/a b.png", "https://communistusa.org:8080/a b.png",
            "https://communistusa.org/a b.png?key=has spaces",
            "https://communistusa.org\\@evil.example/a b.png",
        ]:
            with self.subTest(url=url), self.assertRaises(ImportFailure):
                image_request_url(url)

    def test_raster_type_bytes_and_decompression_limits_are_required(self):
        for body, media_type in [(b"broken", "image/png"), (png(), "image/jpeg")]:
            with (
                self.subTest(media_type=media_type),
                patch("library.services.fetch.Fetcher.fetch",
                      return_value=Response(ENCODED, body, media_type, {})),
                self.assertRaises(ImportFailure),
            ):
                fetch_image(Fetcher(), FAILED)
        with (
            patch("library.services.fetch.Fetcher.fetch",
                  return_value=Response(ENCODED, png(), "image/png", {})),
            patch("library.services.media.Image.open", side_effect=Image.DecompressionBombWarning),
            self.assertRaises(ImportFailure),
        ):
            fetch_image(Fetcher(), FAILED)

    def test_marxist_media_webp_is_verified_not_accepted_by_extension(self):
        buffer = io.BytesIO()
        Image.new("RGB", (4, 4), "green").save(buffer, format="WEBP")
        for body, media_type, valid in (
            (buffer.getvalue(), "image/webp", True),
            (buffer.getvalue(), "image/jpeg", False),
            (b"broken", "image/webp", False),
        ):
            with (
                self.subTest(media_type=media_type, valid=valid),
                patch("library.services.fetch.Fetcher.fetch",
                      return_value=Response(MARXIST_MEDIA, body, media_type, {})) as fetch,
            ):
                if valid:
                    self.assertEqual(fetch_image(Fetcher(), MARXIST_MEDIA).body, body)
                else:
                    with self.assertRaises(ImportFailure):
                        fetch_image(Fetcher(), MARXIST_MEDIA)
                fetch.assert_called_once_with(MARXIST_MEDIA, asset=True)


class MediaRecoveryTests(TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.data = Path(directory.name)
        settings = override_settings(DATA_DIR=self.data)
        settings.enable()
        self.addCleanup(settings.disable)
        self.document = Document.objects.create(url=ARTICLE)
        page = {
            "url": ARTICLE, "resolved_url": ARTICLE, "headers": {},
            "digest": store_blob(article_html(f'<p><img src="{FAILED}" alt="Article photo"></p>')),
            "retrieved_at": "2026-01-01T00:00:00+00:00",
        }
        self.manifest = {
            "pages": [page],
            "assets": {
                FAILED: {"error": "Invalid URL."},
                MISSING: {"error": "Old 404"},
                "https://communistusa.org/retained.png": {
                    "digest": store_blob(png("red")), "media_type": "image/png", "size": 73,
                },
            },
            "parts": [{"url": ARTICLE, "title": "Test article", "group": ""}],
        }
        self.warnings = [
            f"Missing image {FAILED}: Invalid URL.",
            f"Missing image {MISSING}: Old 404", "Unrelated retained warning",
        ]
        self.snapshot = Snapshot.objects.create(
            document=self.document, digest=snapshot_digest(self.manifest),
            manifest=self.manifest, warnings=self.warnings,
        )
        retained = self.manifest["assets"]["https://communistusa.org/retained.png"]
        Blob.objects.create(
            digest=retained["digest"], media_type=retained["media_type"],
            size=len(read_blob(retained["digest"])),
        )
        self.image = png()
        self.fetch = patch(
            "library.services.fetch.Fetcher.fetch", side_effect=self.response
        ).start()
        self.addCleanup(patch.stopall)

    def response(self, url, *, asset=False):
        self.assertTrue(asset)
        if url == ENCODED:
            return Response(url, self.image, "image/png", {})
        if url == MISSING:
            raise ImportFailure("Still HTTP 404", "http")
        self.fail(f"Unexpected fetch: {url}")

    def run_command(self, **kwargs):
        output = io.StringIO()
        call_command("recover_snapshot_media", self.snapshot.pk, stdout=output, **kwargs)
        return json.loads(output.getvalue())

    def test_preview_is_read_only_and_retries_only_recorded_failures(self):
        files = sorted(self.data.rglob("*"))
        report = self.run_command()
        self.assertFalse(report["applied"])
        self.assertEqual(len(report["preview_digest"]), 64)
        self.assertEqual(sum(item["recovered"] for item in report["results"]), 1)
        self.assertEqual(self.fetch.call_count, 2)
        self.assertEqual(Snapshot.objects.count(), 1)
        self.assertEqual(Blob.objects.count(), 1)
        self.assertEqual(Rendition.objects.count(), 0)
        self.assertEqual(Job.objects.count(), 0)
        self.assertEqual(files, sorted(self.data.rglob("*")))

    def test_apply_retains_provenance_and_history_and_reuses_identical_snapshot(self):
        report = self.run_command()
        applied = self.run_command(apply=report["preview_digest"])
        self.assertTrue(applied["applied"])
        self.assertTrue(applied["created"])
        new = Snapshot.objects.get(pk=applied["recovered_snapshot"])
        self.assertNotEqual(new.pk, self.snapshot.pk)
        self.assertEqual(new.manifest["pages"], self.manifest["pages"])
        self.assertEqual(new.manifest["parts"], self.manifest["parts"])
        info = new.manifest["assets"][FAILED]
        self.assertEqual(read_blob(info["digest"]), self.image)
        self.assertNotIn("error", info)
        self.assertEqual(new.manifest["assets"][MISSING], self.manifest["assets"][MISSING])
        self.assertEqual(new.warnings, self.warnings[1:])
        evidence = new.manifest["media_recovery"]
        self.assertEqual(evidence["source_snapshot"], self.snapshot.pk)
        recovered = next(item for item in evidence["results"] if item["recovered"])
        self.assertEqual(recovered["url"], FAILED)
        self.assertEqual(recovered["requested_url"], ENCODED)
        self.assertEqual(recovered["resolved_url"], ENCODED)
        self.assertIn("retrieved_at", evidence)
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.manifest, self.manifest)
        self.assertEqual(self.snapshot.warnings, self.warnings)
        repeated = self.run_command(apply=report["preview_digest"])
        self.assertFalse(repeated["created"])
        self.assertEqual(repeated["recovered_snapshot"], new.pk)
        self.assertEqual(Blob.objects.count(), 2)
        self.assertEqual(Rendition.objects.count(), 0)
        self.assertEqual(Job.objects.count(), 0)

    def test_changed_bytes_or_failed_outcome_refuses_confirmation_without_writes(self):
        report = self.run_command()
        self.image = png("blue")
        with self.assertRaisesMessage(CommandError, "changed since preview"):
            self.run_command(apply=report["preview_digest"])
        self.fetch.side_effect = ImportFailure("Robots disallows this request", "robots")
        with self.assertRaisesMessage(CommandError, "changed since preview"):
            self.run_command(apply=report["preview_digest"])
        self.assertEqual(Snapshot.objects.count(), 1)
        self.assertEqual(Blob.objects.count(), 1)

    def test_invalid_confirmation_is_rejected_before_network(self):
        with self.assertRaisesMessage(CommandError, "exact SHA-256"):
            self.run_command(apply="yes")
        self.fetch.assert_not_called()

    def test_changed_redirect_destination_requires_another_preview(self):
        report = self.run_command()
        self.fetch.side_effect = lambda url, **kwargs: (
            Response(ENCODED + "?redirected=1", self.image, "image/png", {})
            if url == ENCODED else self.response(url, **kwargs)
        )
        with self.assertRaisesMessage(CommandError, "changed since preview"):
            self.run_command(apply=report["preview_digest"])
        self.assertEqual(Snapshot.objects.count(), 1)

    def test_unavailable_snapshot_fails_before_network(self):
        with self.assertRaisesMessage(CommandError, "Snapshot not found"):
            call_command("recover_snapshot_media", 999999, stdout=io.StringIO())
        self.fetch.assert_not_called()

    def test_failed_only_preview_cannot_be_applied(self):
        self.fetch.side_effect = ImportFailure("Robots disallows this request", "robots")
        report = self.run_command()
        self.assertFalse(any(item["recovered"] for item in report["results"]))
        with self.assertRaisesMessage(CommandError, "No images recovered"):
            self.run_command(apply=report["preview_digest"])
        self.assertEqual(Snapshot.objects.count(), 1)
        self.assertEqual(Blob.objects.count(), 1)

    def test_limits_abort_instead_of_becoming_missing_image_success(self):
        self.fetch.side_effect = LimitExceeded("Source byte limit")
        with self.assertRaisesMessage(CommandError, "Source byte limit"):
            self.run_command()
        self.assertEqual(Snapshot.objects.count(), 1)
        self.assertEqual(Blob.objects.count(), 1)

    def test_storage_failure_leaves_original_snapshot_and_database_intact(self):
        report = self.run_command()
        with (
            patch("library.management.commands.recover_snapshot_media.store_blob",
                  side_effect=OSError("Disk full")),
            self.assertRaisesMessage(CommandError, "Disk full"),
        ):
            self.run_command(apply=report["preview_digest"])
        self.assertEqual(Snapshot.objects.count(), 1)
        self.assertEqual(Blob.objects.count(), 1)
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.manifest, self.manifest)

    def test_failed_asset_limit_is_checked_before_network(self):
        self.snapshot.manifest["assets"] = {
            f"https://communistusa.org/{index}.png": {"error": "Missing"}
            for index in range(51)
        }
        self.snapshot.save()
        with self.assertRaisesMessage(CommandError, "limited to 50"):
            self.run_command()
        self.fetch.assert_not_called()

    def test_empty_preview_does_not_fetch_or_create_a_snapshot(self):
        self.snapshot.manifest["assets"] = {}
        self.snapshot.save()
        report = self.run_command()
        self.assertEqual(report["results"], [])
        self.fetch.assert_not_called()
        with self.assertRaisesMessage(CommandError, "No images recovered"):
            self.run_command(apply=report["preview_digest"])

    def test_new_import_encodes_path_spaces_without_changing_source_asset_key(self):
        markup = article_html(f'<p><img src="{FAILED}" alt="Article photo"></p>')

        def response(url, *, asset=False):
            if asset:
                return self.response(url, asset=True)
            self.assertEqual(url, ARTICLE)
            return Response(url, markup, "text/html", {})

        self.fetch.side_effect = response
        enqueue(ARTICLE)
        result = process_job(claim_job())
        self.assertIsNotNone(result)
        self.assertIn(FAILED, result.snapshot.manifest["assets"])
        self.assertNotIn(ENCODED, result.snapshot.manifest["assets"])
        self.assertNotIn("Image unavailable", result.html)
        self.assertEqual(result.warnings, [])

    def test_new_import_retains_marxist_media_webp_for_local_reader(self):
        markup = article_html(f'<p><img src="{MARXIST_MEDIA}" alt="Environment"></p>')
        buffer = io.BytesIO()
        Image.new("RGB", (4, 4), "green").save(buffer, format="WEBP")
        image = buffer.getvalue()

        def response(url, *, asset=False):
            if asset:
                self.assertEqual(url, MARXIST_MEDIA)
                return Response(url, image, "image/webp", {})
            return Response(url, markup, "text/html", {})

        self.fetch.side_effect = response
        enqueue(ARTICLE)
        result = process_job(claim_job())
        self.assertIsNotNone(result)
        info = result.snapshot.manifest["assets"][MARXIST_MEDIA]
        self.assertEqual(info["media_type"], "image/webp")
        self.assertEqual(read_blob(info["digest"]), image)
        self.assertEqual(result.warnings, [])
        reader = self.client.get(f"/versions/{result.pk}/")
        self.assertContains(reader, f'/assets/{info["digest"]}/')
        self.assertNotContains(reader, "Image unavailable")
        asset = self.client.get(f'/assets/{info["digest"]}/')
        self.assertEqual(asset.status_code, 200)
        self.assertEqual(asset.headers["Content-Type"], "image/webp")
        self.assertEqual(b"".join(asset.streaming_content), image)

    def test_recovered_snapshot_can_be_reformatted_offline(self):
        report = self.run_command()
        applied = self.run_command(apply=report["preview_digest"])
        recovered = Snapshot.objects.get(pk=applied["recovered_snapshot"])
        self.fetch.reset_mock()
        enqueue(ARTICLE, Job.Mode.REFORMAT, recovered)
        result = process_job(claim_job())
        self.assertIsNotNone(result)
        self.fetch.assert_not_called()
        self.assertIn(f"/assets/{recovered.manifest['assets'][FAILED]['digest']}/", result.html)
        self.assertNotIn("Image unavailable", result.html)
        self.assertEqual(result.snapshot_id, recovered.pk)
        self.assertEqual(Snapshot.objects.count(), 2)

    def test_marxist_media_recovery_preserves_old_edition_and_generates_local_images(self):
        markup = article_html(f'<p><img src="{MARXIST_MEDIA}" alt="Environment"></p>')
        self.snapshot.manifest["pages"][0]["digest"] = store_blob(markup)
        self.snapshot.manifest["assets"] = {
            MARXIST_MEDIA: {"error": "Unsupported source or asset host: media.marxist.com."},
        }
        self.snapshot.warnings = [
            f"Missing image {MARXIST_MEDIA}: Unsupported source or asset host: media.marxist.com.",
        ]
        self.snapshot.digest = snapshot_digest(self.snapshot.manifest)
        self.snapshot.save()
        enqueue(ARTICLE, Job.Mode.REFORMAT, self.snapshot)
        original = process_job(claim_job())
        self.assertIn("Image unavailable", original.html)
        old_html = original.html
        buffer = io.BytesIO()
        Image.new("RGB", (4, 4), "green").save(buffer, format="WEBP")
        self.fetch.side_effect = None
        self.fetch.return_value = Response(MARXIST_MEDIA, buffer.getvalue(), "image/webp", {})
        preview = self.run_command()
        self.assertEqual(preview["recovered_images"], 1)
        self.assertEqual(preview["remaining_failed_images"], 0)
        recovered = Snapshot.objects.get(
            pk=self.run_command(apply=preview["preview_digest"])["recovered_snapshot"],
        )
        self.fetch.reset_mock()
        enqueue(ARTICLE, Job.Mode.REFORMAT, recovered)
        result = process_job(claim_job())
        self.assertIsNotNone(result)
        self.fetch.assert_not_called()
        self.assertIn(f'/assets/{recovered.manifest["assets"][MARXIST_MEDIA]["digest"]}/',
                      result.html)
        self.assertNotIn("Image unavailable", result.html)
        self.assertEqual(result.warnings, [])
        original.refresh_from_db()
        self.snapshot.refresh_from_db()
        self.assertEqual(original.html, old_html)
        self.assertIn("error", self.snapshot.manifest["assets"][MARXIST_MEDIA])

    def test_media_recovery_does_not_override_current_source_language_gate(self):
        legacy = "https://kommunismus.ch/fr/example/"
        self.document.url = legacy
        self.document.save()
        self.snapshot.manifest["pages"][0].update(url=legacy, resolved_url=legacy)
        self.snapshot.save()
        report = self.run_command()
        applied = self.run_command(apply=report["preview_digest"])
        recovered = Snapshot.objects.get(pk=applied["recovered_snapshot"])
        enqueue(legacy, Job.Mode.REFORMAT, recovered)
        self.assertIsNone(process_job(claim_job()))
        job = Job.objects.get()
        self.assertEqual(job.error_code, "unsupported_language")
        self.assertEqual(Rendition.objects.count(), 0)
