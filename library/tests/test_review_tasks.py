import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup
from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image
from pypdf import PdfReader

from library.models import Blob, DocumentPublication, Rendition, RenditionAsset
from library.services.document_edits import create_draft
from library.services.pdf import STYLES, render_pdf
from library.services.semantic_documents import canonical_document, fingerprint
from library.services.storage import store_blob
from library.tests import test_document_edits as foundation


@override_settings(READING_HUB_EDITOR_PILOT=True)
class ReviewTaskTests(TestCase):
    def setUp(self):
        foundation.DocumentEditTests.setUp(self)
        self.reviewer.is_staff = True
        self.reviewer.save(update_fields=["is_staff"])
        self.client.force_login(self.reviewer)
        assets = patch("library.document_editor_views.finders.find", return_value="built-asset")
        assets.start()
        self.addCleanup(assets.stop)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        data_dir = override_settings(DATA_DIR=Path(directory.name))
        data_dir.enable()
        self.addCleanup(data_dir.disable)
        image = io.BytesIO()
        Image.new("RGB", (8, 8), "white").save(image, format="PNG")
        data = image.getvalue()
        digest = store_blob(data)
        self.blob = Blob.objects.create(digest=digest, media_type="image/png", size=len(data))
        self.tasks = json.loads(
            (settings.BASE_DIR / "frontend" / "fixtures" / "review-tasks.json").read_text()
        )["tasks"]

    def run_task(self, task):
        initial = task["initial"].replace("a" * 64, self.blob.pk)
        expected = task["expected"].replace("a" * 64, self.blob.pk)
        source = Rendition.objects.create(
            document=self.rendition.document, snapshot=self.rendition.snapshot,
            identity=fingerprint(task["id"]), output_digest=fingerprint(initial),
            title=task["title"], metadata={"language": "en"}, html=initial,
            structure={"book": task["id"].startswith("book"), "toc": []},
            stylesheet=(STYLES / "reader.css").read_text(),
            app_version="review-task-v1", adapter_version="19", format_version="19",
        )
        if "<img " in initial:
            RenditionAsset.objects.create(rendition=source, blob=self.blob)
        draft = create_draft(source, self.reviewer)
        evidence = fingerprint(draft.evidence)
        editor_url = reverse("document-editor", args=[source.pk])
        publication_url = reverse("document-publication", args=[source.pk]) + f"?draft={draft.pk}"

        def save(document, revision, review="partial"):
            return self.client.post(editor_url, json.dumps({
                "draft": str(draft.pk), "revision": revision, "document": document,
                "conversion_approval": None, "review": review,
                "verified_sections": [], "editorial": False,
            }), content_type="application/json")

        before = Rendition.objects.count()
        incomplete = save(draft.document, 0)
        self.assertEqual(incomplete.status_code, 200)
        self.assertIn("Unresolved internal target: #missing", incomplete.json()["issues"])
        self.assertEqual(
            self.client.get(publication_url + "&revision=1").status_code, 422,
        )
        self.assertEqual(save(draft.document, 1, review="full").status_code, 422)
        self.assertEqual(draft.revisions.count(), 1)
        self.assertEqual(Rendition.objects.count(), before)
        corrected = canonical_document({**draft.document, "html": expected})
        response = save(corrected, 1)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["issues"], [])
        self.assertEqual(response.json()["review"], "partial")
        reopened = self.client.get(editor_url + f"?draft={draft.pk}")
        self.assertEqual(reopened.context["initial"]["document"], corrected)
        self.assertEqual(save(corrected, 1).status_code, 409)
        rejected = save({**corrected, "html": "<p><script>invalid</script></p>"}, 2)
        self.assertEqual(rejected.status_code, 422)
        self.assertEqual(draft.revisions.count(), 2)
        self.assertEqual(
            self.client.get(editor_url + f"?draft={draft.pk}").context["initial"]["document"],
            corrected,
        )

        preview = self.client.get(publication_url + "&revision=2")
        self.assertEqual(preview.status_code, 200)
        candidate = preview.context["candidate"]
        self.assertEqual(
            [entry["title"] for entry in candidate["output"]["structure"]["toc"]], task["toc"],
        )
        self.assertEqual(Rendition.objects.count(), before)
        result = self.client.post(publication_url, {
            "confirm": "yes", "revision": "2", "preview_digest": candidate["digest"],
        })
        publication = DocumentPublication.objects.get(revision__draft=draft)
        self.assertRedirects(result, reverse("reader", args=[publication.rendition_id]))
        published = publication.rendition
        reader = self.client.get(reverse("reader", args=[published.pk]))
        self.assertContains(reader, "Not verified as a whole document")
        soup = BeautifulSoup(published.html, "html.parser")
        ids = [node["id"] for node in soup.select("[id]")]
        self.assertEqual(len(ids), len(set(ids)))
        for entry in published.structure["toc"]:
            self.assertContains(reader, f'href="#{entry["id"]}"')
            self.assertIn(entry["id"], ids)
        for anchor in soup.select("a[href^='#']"):
            self.assertIn(anchor["href"][1:], ids)
        self.assertEqual(
            published.assets.count(), 1 if "<img " in expected else 0,
        )
        if task["id"].startswith("book"):
            self.assertLess(published.html.index('id="first"'), published.html.index('id="second"'))
            self.assertIn(task["source_excerpt"], soup.get_text())
            self.assertIn("  exact\n spacing", soup.get_text())
            self.assertEqual(len(soup.select("table td")), 2)
        else:
            self.assertContains(reader, "Unicode 😀 and café.")
            self.assertEqual(soup.select_one("img")["alt"], "A retained diagram")
            self.assertEqual(soup.select_one(".media-credit").get_text(), "Diagram credit")

        output = io.BytesIO()
        render_pdf(published, output)
        pdf = PdfReader(output)
        self.assertGreaterEqual(len(pdf.pages), 2)
        # pypdf can expose NUL separators with the Unicode fixture's font subset.
        # This checks content coverage, not visual/Unicode PDF acceptance.
        opening_text = pdf.pages[0].extract_text().replace("\x00", "")
        self.assertIn(task["title"], opening_text)
        self.assertIn("Not verified as a whole document", opening_text)
        body_text = "\n".join(page.extract_text() for page in pdf.pages[1:]).replace("\x00", "")
        for text in task["pdf_text"]:
            self.assertIn(text, body_text)
        if "<img " in expected:
            self.assertTrue(any(page.images for page in pdf.pages))

        verified = save(corrected, 2, review="full")
        self.assertEqual(verified.status_code, 200)
        self.assertEqual(verified.json()["review"], "full")
        self.assertEqual(draft.revisions.get(revision=2).review, "partial")
        stale = self.client.post(publication_url, {
            "confirm": "yes", "revision": "2", "preview_digest": candidate["digest"],
        })
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(Rendition.objects.count(), before + 1)
        source.refresh_from_db()
        draft.refresh_from_db()
        self.assertEqual(source.html, initial)
        self.assertEqual(fingerprint(draft.evidence), evidence)
        self.assertEqual(draft.evidence["generated_html"], initial)
        self.assertEqual(draft.revisions.get(revision=1).document, draft.document)
        self.assertContains(
            self.client.get(reverse("reader", args=[published.pk])),
            "Not verified as a whole document",
        )

    def test_article_correction_save_reopen_publication_reader_and_pdf(self):
        self.run_task(self.tasks[0])

    def test_book_correction_save_reopen_publication_reader_and_pdf(self):
        self.run_task(self.tasks[1])
