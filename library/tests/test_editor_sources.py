from unittest.mock import patch

from bs4 import BeautifulSoup
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from library.models import SourceExcerptRevision
from library.services.editor_sources import source_page
from library.services.errors import ImportFailure
from library.services.pipeline import snapshot_digest
from library.services.storage import store_blob
from library.tests import test_fresh_document_drafts as foundation
from library.tests.test_sources import ARTICLE


@override_settings(READING_HUB_EDITOR_PILOT=True)
class EditorSourceTests(TestCase):
    def setUp(self):
        foundation.FreshDraftTests.setUp(self)
        self.url = reverse("document-editor-source", args=[self.rendition.pk])

    def source(self, body):
        page = self.rendition.snapshot.manifest["pages"][0]
        page["digest"] = store_blob(
            ('<html><body>' + body + '</body></html>').encode(),
        )
        self.rendition.snapshot.digest = snapshot_digest(self.rendition.snapshot.manifest)

    def test_read_only_listing_contains_omitted_material_and_no_excerpts(self):
        self.source('<p>Original omitted Endnotes.</p><script>alert("x")</script>'
                    '<p id="n1">The first note.</p>')
        before = SourceExcerptRevision.objects.count()
        result = source_page(self.rendition, 0)
        self.assertEqual([block["text"] for block in result["blocks"]], [
            "Original omitted Endnotes.", "The first note.",
        ])
        self.assertEqual(
            result["source_digest"], self.rendition.snapshot.manifest["pages"][0]["digest"],
        )
        self.assertEqual(SourceExcerptRevision.objects.count(), before)

    def test_structured_selection_preserves_note_links_targets_and_retained_image(self):
        self.source(
            '<h2>Endnotes</h2><p><a id="ref" href="#note">1</a></p>'
            '<p id="note">Note text <a href="#ref">Return</a></p>'
            '<figure><img src="https://www.marxists.org/image.jpg" alt="Plate">'
            '<figcaption>Credit</figcaption></figure>',
        )
        result = source_page(self.rendition, 0, [0, 1, 2, 3])
        soup = BeautifulSoup(result["html"], "html.parser")
        ids = {node["id"] for node in soup.select("[id]")}
        for link in soup.select('a[href^="#"]'):
            self.assertIn(link["href"][1:], ids)
        self.assertEqual(soup.img["src"], f"/assets/{self.blob.pk}/")
        self.assertEqual(soup.figcaption.get_text(), "Credit")
        self.assertNotIn("data-excerpt", result["html"])
        self.assertEqual(result["binding"]["blocks"], [0, 1, 2, 3])

    def test_unselected_note_targets_remain_exact_external_source_links(self):
        self.source('<p><a href="#note">Reference</a></p><p id="note">A note.</p>')
        result = source_page(self.rendition, 0, [0])
        soup = BeautifulSoup(result["html"], "html.parser")
        self.assertEqual(soup.a["href"], ARTICLE + "#note")
        self.assertEqual(result["external_links"], 1)

    def test_selection_rejects_unbound_or_corrupt_retained_images(self):
        self.source('<figure><img src="https://www.marxists.org/image.jpg" alt="Plate">'
                    '<figcaption>Caption</figcaption></figure>')
        with self.assertRaisesMessage(ValueError, "not bound"):
            source_page(self.rendition, 0, [0], allowed_assets=[])
        result = source_page(self.rendition, 0, [0], allowed_assets=[self.blob.pk])
        self.assertIn(self.blob.pk, result["html"])
        from library.services.storage import blob_path

        blob_path(self.blob.pk).write_bytes(b"broken image")
        with self.assertRaises(OSError):
            source_page(self.rendition, 0, [0], allowed_assets=[self.blob.pk])

    def test_standalone_anchors_before_notes_survive_selection(self):
        self.source('<p><a href="#endnote">1</a></p>'
                    '<a name="endnote"></a><p>Endnote text.</p>')
        result = source_page(self.rendition, 0, [0, 1])
        soup = BeautifulSoup(result["html"], "html.parser")
        href = soup.select_one("a[href^='#']")["href"]
        self.assertIsNotNone(soup.find(id=href[1:]))
        self.assertIn("Endnote text.", soup.get_text())

    def test_note_only_selection_does_not_invent_backlinks_to_unselected_references(self):
        self.source('<p>Text <a href="#note1">1</a></p><p id="note1">An endnote.</p>')
        result = source_page(self.rendition, 0, [1])
        self.assertIn("An endnote.", result["html"])
        self.assertNotIn("[back]", result["html"])
        self.assertEqual(result["omitted_generated_backlinks"], 1)

    def test_invalid_ranges_missing_bytes_and_manifest_tampering_are_explicit(self):
        for page, selection in ((-1, None), (100, None), (True, None), (0, []),
                                (0, [1, 0]), (0, [0, 0]), (0, [9999])):
            with self.subTest(page=page, selection=selection), self.assertRaises(ValueError):
                source_page(self.rendition, page, selection)
        self.rendition.snapshot.manifest["pages"][0]["digest"] = "0" * 64
        with self.assertRaisesMessage(ValueError, "integrity"):
            source_page(self.rendition, 0)

    def test_routes_enforce_profile_flag_permission_and_do_not_accept_mutation(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(self.client.post(self.url, {}).status_code, 405)
        self.assertEqual(self.client.get(self.url, {"page": "no"}).status_code, 422)
        self.assertEqual(self.client.get(self.url, {"blocks": "99999"}).status_code, 422)
        with override_settings(READING_HUB_EDITOR_PILOT=False):
            self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(Client().get(self.url).status_code, 302)
        with patch("library.document_editor_views.adapter_for",
                   side_effect=ImportFailure("Unavailable", "source")):
            self.assertEqual(self.client.get(self.url).status_code, 404)
