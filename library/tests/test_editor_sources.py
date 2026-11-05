from unittest.mock import patch

from bs4 import BeautifulSoup
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from library.models import CrawlCapture, CrawlSite, SourceExcerptRevision
from library.profile import get_profile
from library.services.editor_sources import original_section, source_page
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

    def test_section_candidates_include_exact_heading_ranges_and_current_saved_excerpts(self):
        self.source('<h2>Appendix</h2><p>Note</p><h3>Detail</h3><p>More</p>'
                    '<h2>Next</h2><p>Other</p>')
        result = source_page(self.rendition, 0)
        candidates = result["candidates"]
        self.assertEqual(candidates[0], {
            "title": "Appendix", "kind": "Parsed heading range", "blocks": [0, 1, 2, 3],
        })
        self.assertEqual(candidates[1]["blocks"], [2, 3])
        self.assertEqual(candidates[2]["blocks"], [4, 5])
        self.assertEqual(len(result["pages"]), 1)
        entry = self.rendition.snapshot.manifest["pages"][0]
        site = CrawlSite.objects.create(profile=get_profile().key, host="www.marxists.org")
        capture = CrawlCapture.objects.create(site=site, url=ARTICLE, response=entry)
        excerpt = SourceExcerptRevision.objects.create(
            capture=capture, revision=1, name="Selected appendix note",
            source_digest=entry["digest"], blocks=[1, 3], reviewer=self.reviewer,
        )
        self.assertIn({
            "title": excerpt.name, "kind": "Saved excerpt", "blocks": [1, 3],
        }, source_page(self.rendition, 0)["candidates"])
        SourceExcerptRevision.objects.create(
            definition=excerpt.definition, capture=capture, revision=2, name=excerpt.name,
            source_digest=entry["digest"], blocks=[1, 3], reviewer=self.reviewer, deleted=True,
        )
        self.assertFalse(any(item["kind"] == "Saved excerpt"
                             for item in source_page(self.rendition, 0)["candidates"]))

    def test_original_section_preview_is_read_only_and_refuses_missing_or_unbound_content(self):
        original = self.rendition.html
        section = original_section(self.rendition, "c1")
        self.assertIn('<section id="c1"', section["html"])
        self.assertEqual(self.rendition.html, original)
        with self.assertRaisesMessage(ValueError, "Choose a section"):
            original_section(self.rendition, "absent")
        response = self.client.get(self.url, {"original_section": "c1"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["binding"]["rendition"], self.rendition.pk)
        self.assertEqual(self.client.get(self.url, {"original_section": "absent"}).status_code, 422)
        self.rendition.html = (
            '<section id="c1"><h2>Appendix</h2>'
            f'<p><img src="/assets/{self.blob.pk}/" alt="Plate"></p></section>'
        )
        with self.assertRaisesMessage(ValueError, "not bound"):
            original_section(self.rendition, "c1", allowed_assets=[])
        self.assertIn(self.blob.pk, original_section(
            self.rendition, "c1", allowed_assets=[self.blob.pk],
        )["html"])

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

    def test_heading_range_preserves_trailing_empty_selected_paragraph(self):
        self.source('<h3>Notes</h3><p id="note">Note text.</p><p> </p>')
        listing = source_page(self.rendition, 0)
        candidate = listing["candidates"][0]
        self.assertEqual(candidate["blocks"], [0, 1, 2])
        selected = source_page(self.rendition, 0, candidate["blocks"])
        soup = BeautifulSoup(selected["html"], "html.parser")
        self.assertEqual(soup.find_all("p")[-1].get_text(), " ")
        self.assertIn("Note text.", soup.get_text())
        self.assertNotIn("data-excerpt-block", selected["html"])

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
