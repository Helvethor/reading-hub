import io
import json
import shutil
import uuid
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image
from pypdf import PdfReader

from library.models import (
    Document,
    DocumentDraftBase,
    DocumentEditRevision,
    DocumentPublication,
    DocumentVersion,
    Job,
    Rendition,
    Snapshot,
)
from library.profile import get_profile
from library.services.document_edits import save_revision
from library.services.document_versions import version_for_saved_state
from library.services.editor_sources import source_page
from library.services.semantic_documents import document_issues
from library.services.storage import read_blob


@override_settings(READING_HUB_ENVIRONMENT="test", READING_HUB_EDITOR_PILOT=True)
class DevelopmentFixtureTests(TestCase):
    def setUp(self):
        self.data = Path(settings.DATA_DIR) / f"fixture-test-{uuid.uuid4().hex}"
        self.data.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.data)
        databases = deepcopy(settings.DATABASES)
        databases["default"]["NAME"] = self.data / "library.sqlite3"
        overrides = override_settings(DATA_DIR=self.data, DATABASES=databases)
        overrides.enable()
        self.addCleanup(overrides.disable)
        network = patch(
            "library.services.fetch.Fetcher.fetch",
            side_effect=AssertionError("Development fixtures must not fetch a source"),
        )
        network.start()
        self.addCleanup(network.stop)
        self.output = io.StringIO()

    def seed(self):
        call_command("seed_development", stdout=self.output)
        return json.loads((self.data / "development-fixtures.json").read_text())

    def reviewer(self):
        return get_user_model().objects.get(username="development-reviewer")

    def test_live_legacy_and_unknown_environments_refuse_before_mutation(self):
        for environment in ("live", "legacy", "", "production"):
            with (
                self.subTest(environment=environment),
                override_settings(
                    READING_HUB_ENVIRONMENT=environment,
                ),
                self.assertRaisesMessage(CommandError, "live is refused"),
            ):
                self.seed()
        with override_settings():
            del settings.READING_HUB_ENVIRONMENT
            with self.assertRaisesMessage(CommandError, "live is refused"):
                self.seed()
        self.assertFalse(Document.objects.exists())
        self.assertFalse(get_user_model().objects.exists())
        self.assertEqual(list(self.data.iterdir()), [])

    def test_live_or_external_data_paths_are_refused(self):
        with (
            override_settings(
                DATA_DIR=Path(settings.BASE_DIR) / "data",
            ),
            self.assertRaisesMessage(CommandError, "isolated"),
        ):
            self.seed()
        databases = deepcopy(settings.DATABASES)
        databases["default"]["NAME"] = self.data.parent / "unrelated.sqlite3"
        with (
            override_settings(DATABASES=databases),
            self.assertRaisesMessage(
                CommandError,
                "database must be inside",
            ),
        ):
            self.seed()
        self.assertFalse(Document.objects.exists())
        self.assertEqual(list(self.data.iterdir()), [])

    def test_allowed_environments_seed_offline(self):
        for environment in ("development", "staging", "test"):
            with (
                self.subTest(environment=environment),
                override_settings(
                    READING_HUB_ENVIRONMENT=environment,
                ),
            ):
                manifest = self.seed()
                self.assertEqual(set(manifest["fixtures"]), {"article", "book"})
        self.assertEqual(Document.objects.count(), 2)
        self.assertEqual(Rendition.objects.count(), 4)
        self.assertFalse(Job.objects.exists())
        credential_path = self.data / "development-credentials.json"
        self.assertEqual(credential_path.stat().st_mode & 0o777, 0o600)
        credentials = json.loads(credential_path.read_text())
        for account in credentials.values():
            self.assertNotIn(account["username"], self.output.getvalue())
            self.assertNotIn(account["password"], self.output.getvalue())
            self.assertTrue(
                get_user_model()
                .objects.get(
                    username=account["username"],
                )
                .check_password(account["password"])
            )
        self.assertTrue(self.reviewer().is_staff)
        self.assertFalse(get_user_model().objects.get(username="development-reader").is_staff)

    def test_escaping_blob_symlink_is_refused_before_seeding(self):
        (self.data / "blobs").symlink_to(self.data.parent / "outside-fixture-blobs")
        with self.assertRaisesMessage(CommandError, "isolated non-live storage"):
            self.seed()
        self.assertFalse(Document.objects.exists())
        self.assertFalse((self.data / "development-credentials.json").exists())

    def test_second_seed_preserves_developer_edits_credentials_and_unrelated_records(self):
        manifest = self.seed()
        credential_path = self.data / "development-credentials.json"
        manifest_path = self.data / "development-fixtures.json"
        credentials = credential_path.read_bytes()
        retained_manifest = manifest_path.read_bytes()
        credential_mtime = credential_path.stat().st_mtime_ns
        draft = DocumentDraftBase.objects.get(pk=manifest["fixtures"]["article"]["draft_id"])
        current = draft.revisions.first()
        saved = save_revision(
            draft,
            self.reviewer(),
            {
                **current.document,
                "title": "Developer's unseeded title",
            },
            current.revision,
        )
        reader = get_user_model().objects.get(username="development-reader")
        reader.set_password("A locally changed synthetic password")
        reader.save(update_fields=["password"])
        password = reader.password
        reviewer = self.reviewer()
        reviewer.is_staff = False
        reviewer.save(update_fields=["is_staff"])
        unrelated = Document.objects.create(url="https://example.invalid/developer-work")
        counts = (DocumentEditRevision.objects.count(), DocumentVersion.objects.count())
        self.assertEqual(self.seed(), manifest)
        self.assertEqual(credential_path.read_bytes(), credentials)
        self.assertEqual(credential_path.stat().st_mtime_ns, credential_mtime)
        self.assertEqual(manifest_path.read_bytes(), retained_manifest)
        self.assertEqual(draft.revisions.first().pk, saved.pk)
        self.assertEqual(draft.revisions.first().document["title"], "Developer's unseeded title")
        reader.refresh_from_db()
        self.assertEqual(reader.password, password)
        self.assertFalse(self.reviewer().is_staff)
        self.assertTrue(Document.objects.filter(pk=unrelated.pk).exists())
        self.assertEqual(
            counts,
            (
                DocumentEditRevision.objects.count(),
                DocumentVersion.objects.count(),
            ),
        )

    def test_retained_assets_notes_and_version_lineage_are_intact(self):
        fixtures = self.seed()["fixtures"]
        for kind, fixture in fixtures.items():
            with self.subTest(kind=kind):
                source = Rendition.objects.get(pk=fixture["source_rendition_id"])
                publication = Rendition.objects.get(pk=fixture["published_rendition_id"])
                draft = DocumentDraftBase.objects.get(pk=fixture["draft_id"])
                revision = draft.revisions.first()
                self.assertEqual(
                    urlsplit(fixture["source_url"]).hostname, get_profile().sources[0].host
                )
                self.assertEqual(
                    len(source.snapshot.manifest["pages"]),
                    1 if kind == "article" else 3,
                )
                for number, entry in enumerate(source.snapshot.manifest["pages"]):
                    self.assertIn(b"<!doctype html>", read_blob(entry["digest"]))
                    listing = source_page(source, number)
                    self.assertTrue(listing["blocks"])
                self.assertEqual(source.structure["book"], kind == "book")
                self.assertEqual(len(source.structure["parts"]), 1 if kind == "article" else 2)
                for rendition in (source, publication):
                    soup = BeautifulSoup(rendition.html, "html.parser")
                    image = soup.find("img")
                    digest = image["src"].split("/")[2]
                    self.assertTrue(rendition.assets.filter(blob_id=digest).exists())
                    with Image.open(io.BytesIO(read_blob(digest))) as plate:
                        self.assertEqual(plate.format, "PNG")
                        plate.verify()
                    links = soup.select('a[href^="#"]')
                    self.assertGreaterEqual(len(links), 2)
                    for link in links:
                        self.assertIsNotNone(soup.find(id=link["href"][1:]))
                    reference = soup.select_one('sup a[href^="#"]')
                    note = soup.find(id=reference["href"][1:])
                    self.assertIsNotNone(note.find("a", href="#" + reference["id"]))
                self.assertEqual(
                    document_issues(
                        revision.document,
                        set(source.assets.values_list("blob_id", flat=True)),
                    ),
                    [],
                )
                self.assertEqual(revision.review, "partial")
                self.assertEqual(
                    version_for_saved_state(draft, 1).pk, publication.document_version_id
                )
                self.assertEqual(draft.branch.starting_version_id, source.document_version_id)
                self.assertEqual(revision.document_version.parent_id, draft.document_version_id)
        self.assertEqual(Snapshot.objects.count(), 2)

    def test_real_editor_save_reopen_compare_publish_reader_and_pdf(self):
        fixtures = self.seed()["fixtures"]
        self.client.force_login(self.reviewer())
        for kind, fixture in fixtures.items():
            with self.subTest(kind=kind):
                workspace = fixture["workspace_url"]
                response = self.client.get(workspace)
                self.assertEqual(response.status_code, 200)
                initial = response.context["initial"]
                self.assertEqual(initial["revision"], 1)
                edited = {
                    **initial["document"],
                    "title": f"Saved synthetic {kind}",
                    "html": initial["document"]["html"].replace(
                        "Synthetic edited text",
                        "Browser endpoint edited text",
                        1,
                    ),
                }
                response = self.client.post(
                    workspace,
                    json.dumps(
                        {
                            "draft": fixture["draft_id"],
                            "revision": 1,
                            "document": edited,
                            "conversion_approval": None,
                            "review": "partial",
                            "verified_sections": [],
                            "editorial": True,
                        }
                    ),
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 200, response.content[:300])
                saved = response.json()
                self.assertEqual(saved["revision"], 2)
                reopened = self.client.get(workspace)
                self.assertEqual(reopened.context["initial"]["document"], saved["document"])
                comparison = self.client.get(
                    fixture["comparison_url"] + "&from=1&to=2&download=1",
                )
                self.assertEqual(comparison.status_code, 200)
                self.assertEqual(comparison.json()["later"]["document"], saved["document"])
                preview_url = fixture["publication_url"].replace("revision=1", "revision=2")
                preview = self.client.get(preview_url)
                self.assertEqual(preview.status_code, 200)
                published = self.client.post(
                    preview_url,
                    {
                        "confirm": "yes",
                        "revision": "2",
                        "preview_digest": preview.context["candidate"]["digest"],
                    },
                )
                self.assertEqual(published.status_code, 200, published.content[:300])
                publication = DocumentPublication.objects.get(
                    revision__draft_id=fixture["draft_id"],
                    revision__revision=2,
                )
                reader = Client().get(reverse("reader", args=[publication.rendition_id]))
                self.assertContains(reader, edited["title"])
                self.assertContains(reader, "Browser endpoint edited text")
                pdf = Client().get(reverse("reader-pdf", args=[publication.rendition_id]))
                self.assertEqual(pdf.status_code, 200)
                pdf_bytes = b"".join(pdf.streaming_content)
                pdf.close()
                text = "\n".join(
                    page.extract_text() for page in PdfReader(io.BytesIO(pdf_bytes)).pages
                )
                self.assertIn(edited["title"], text)
                self.assertIn("Browser endpoint edited text", text)
                self.assertIn("Publication does not add verification", text)
                source = Rendition.objects.get(pk=fixture["source_rendition_id"])
                self.assertIn("Synthetic source text", source.html)
