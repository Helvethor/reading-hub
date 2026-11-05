import io
import tempfile
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image
from pypdf import PdfReader

from library.models import Blob, DocumentPublication, Rendition, RenditionAsset
from library.profile import get_profile
from library.services.document_edits import DocumentEditConflict, save_revision
from library.services.document_publication import (
    PUBLICATION_VERSION,
    prepare_publication,
    publish_revision,
)
from library.services.pdf import STYLES, render_pdf
from library.services.storage import blob_path, store_blob
from library.tests import test_document_edits as foundation


@override_settings(READING_HUB_EDITOR_PILOT=True)
class DocumentPublicationTests(TestCase):
    def setUp(self):
        foundation.DocumentEditTests.setUp(self)
        self.reviewer.is_staff = True
        self.reviewer.save(update_fields=["is_staff"])
        self.client.force_login(self.reviewer)
        self.revision = save_revision(
            self.draft, self.reviewer, {
                **self.draft.document, "title": "Edited title",
                "html": '<section id="c1"><h2>New heading</h2>'
                '<p id="heading-1">Edited text. <a href="#c1">Return</a></p></section>',
            }, 0,
        )
        self.url = reverse("document-publication", args=[self.rendition.pk])
        self.query = f"?draft={self.draft.pk}&revision=1"

    def publish(self, revision=None):
        revision = revision or self.draft.revisions.first().revision
        candidate = prepare_publication(self.draft, revision)
        return publish_revision(self.draft, self.reviewer, revision, candidate["digest"])

    def test_corrected_section_order_title_url_role_survive_publication_and_reopen(self):
        source_html = self.rendition.html
        markup = (
            '<section id="appendix" data-section-role="appendix" '
            'data-section-url="https://example.org/appendix" data-section-title="actual">'
            '<h2>Running title</h2><h3 id="actual">Reviewed Appendix</h3>'
            '<p id="note">Retained note <a href="#chapter">Return</a></p></section>'
            '<section id="chapter"><h2>Chapter</h2><p>Corrected text.</p></section>'
        )
        revision = save_revision(self.draft, self.reviewer, {
            **self.revision.document, "html": markup,
        }, 1)
        publication = self.publish(2)
        rendition = publication.rendition
        self.assertEqual([part["id"] for part in rendition.structure["parts"]],
                         ["appendix", "chapter"])
        appendix = rendition.structure["parts"][0]
        self.assertEqual(appendix["title"], "Reviewed Appendix")
        self.assertEqual(appendix["url"], "https://example.org/appendix")
        self.assertEqual(appendix["role"], "appendix")
        self.assertEqual(revision.review, "partial")
        self.rendition.refresh_from_db()
        self.assertEqual(self.rendition.html, source_html)
        reopened = self.client.get(reverse("document-editor", args=[self.rendition.pk]),
                                   {"draft": self.draft.pk})
        self.assertEqual(reopened.context["initial"]["document"]["html"],
                         revision.document["html"])
        self.assertContains(self.client.get(reverse("reader", args=[rendition.pk])),
                            "Reviewed Appendix")

    def test_toc_numbering_preferences_survive_publication_without_title_prefixes(self):
        source = self.rendition.html
        markup = (
            '<section id="a" data-toc-style="upper-roman"><h2>First</h2>'
            '<h3 data-toc-style="lower-alpha">Nested</h3><p>Body</p></section>'
            '<section id="b" data-toc-style="upper-roman"><h2>Second</h2><p>End</p></section>'
        )
        save_revision(self.draft, self.reviewer, {**self.revision.document, "html": markup}, 1)
        published = self.publish(2).rendition
        soup = BeautifulSoup(published.html, "html.parser")
        self.assertEqual(soup.select_one("#a")["data-toc-style"], "upper-roman")
        self.assertEqual(soup.h3["data-toc-style"], "lower-alpha")
        self.assertEqual(soup.h2.get_text(), "First")
        self.assertEqual(
            [part["title"] for part in published.structure["parts"]], ["First", "Second"],
        )
        self.rendition.refresh_from_db()
        self.assertEqual(self.rendition.html, source)

    def test_preview_reader_and_pdf_mirror_editor_numbering_title_and_metadata(self):
        from library.services.document_metadata import metadata_rows

        markup = (
            '<section id="a" data-toc-style="upper-roman"><h2 id="first">First</h2>'
            '<h3 data-toc-style="lower-alpha">Nested</h3><p>Body</p></section>'
            '<section id="b" data-toc-style="upper-roman"><h2>Second</h2><p>End</p></section>'
        )
        metadata = {
            **self.revision.document["metadata"], "author": "Reviewed writer",
            "subtitle": "Reviewed subtitle", "language": "fr",
            "contributors": [{"name": "Reviewed translator", "role": "translator",
                              "source_name": "Reviewed translator"}],
            "date_facts": [{"type": "written", "value": "1900", "end_value": "1902"}],
            "topics": ["History", "Books"],
        }
        # Structured author rows derive the author field in the save contract.
        metadata["contributors"].insert(0, {
            "name": "Reviewed writer", "role": "author", "source_name": "Reviewed writer",
        })
        revision = save_revision(self.draft, self.reviewer, {
            **self.revision.document, "title": "Reviewed book",
            "metadata": metadata, "html": markup,
        }, 1)
        preview = self.client.get(self.url + f"?draft={self.draft.pk}&revision=2")
        self.assertContains(preview, "Reviewed book")
        self.assertContains(preview, 'data-reading-marker="I. "')
        preview_soup = BeautifulSoup(preview.content, "html.parser")
        publication = self.publish(2)
        published = publication.rendition
        response = self.client.get(reverse("reader", args=[published.pk]))
        soup = BeautifulSoup(response.content, "html.parser")
        for page in (preview_soup, soup):
            entries = page.select(".document-contents a")
            self.assertEqual([entry.get_text() for entry in entries],
                             ["I. First", "a. Nested", "II. Second"])
            self.assertEqual(page.select_one("#first")["data-reading-marker"], "I. ")
            self.assertEqual(page.select_one(".document-header h1").get_text(), "Reviewed book")
            header = page.select_one(".document-header")
            rows = list(zip([node.get_text() for node in header.select("dt")],
                            [node.get_text() for node in header.select("dd")], strict=True))
            self.assertEqual(rows, metadata_rows(revision.document["metadata"]) + [
                ("Source", published.document.url),
            ])
            self.assertIn("Reviewed subtitle", header.get_text())
        stored = published.html
        self.assertNotIn("data-reading-marker", stored)
        self.assertEqual(BeautifulSoup(stored, "html.parser").h2.get_text(), "First")
        output = io.BytesIO()
        render_pdf(published, output)
        pdf = PdfReader(output)
        self.assertEqual(pdf.metadata.title, "Reviewed book")
        self.assertEqual(pdf.metadata.author, "Reviewed writer")
        cover = pdf.pages[0].extract_text()
        for text in ("Reviewed subtitle", "Reviewed translator", "1900 / 1902",
                     "French", "History, Books"):
            self.assertIn(text, cover)
        contents = pdf.pages[1].extract_text()
        for text in ("Table of contents", "I. First", "a. Nested", "II. Second"):
            self.assertIn(text, contents)
        body = "\n".join(page.extract_text() for page in pdf.pages[2:])
        for text in ("I. First", "a. Nested", "II. Second"):
            self.assertIn(text, body)
        def bookmarks(items):
            return [title for item in items for title in (
                bookmarks(item) if isinstance(item, list) else [item.title]
            )]
        self.assertIn("I. First", bookmarks(pdf.outline))
        self.assertIn("a. Nested", bookmarks(pdf.outline))
        self.assertNotIn("Table of contents", bookmarks(pdf.outline))
        self.assertTrue(any(annotation.get_object().get("/Dest")
                            for annotation in pdf.pages[1].get("/Annots", [])))
        published.refresh_from_db()
        self.assertEqual(published.html, stored)

    def test_existing_publication_gets_read_only_projection_without_republication(self):
        from library.sources.normalize import heading_toc

        markup = '<section id="a" data-toc-style="upper-roman"><h2>First</h2>' \
            '<p>Body</p></section>'
        save_revision(self.draft, self.reviewer, {**self.revision.document, "html": markup}, 1)
        with patch("library.services.document_publication.PUBLICATION_VERSION", 3), patch(
            "library.services.document_publication.publication_toc", side_effect=heading_toc,
        ):
            publication = self.publish(2)
        published = publication.rendition
        stored = published.html
        toc = deepcopy(published.structure["toc"])
        self.assertEqual(publication.publication_version, 3)
        response = self.client.get(reverse("reader", args=[published.pk]))
        self.assertContains(response, 'data-reading-marker="I. "')
        self.assertContains(response, 'href="#a"')
        published.refresh_from_db()
        self.assertEqual(published.html, stored)
        self.assertEqual(published.structure["toc"], toc)
        self.assertEqual(DocumentPublication.objects.count(), 1)

    def test_invalid_section_title_binding_is_partial_issue_and_blocks_publication(self):
        markup = '<section id="s" data-section-title="nested"><h2>Title</h2>' \
            '<section id="child"><h3 id="nested">Child</h3></section></section>'
        revision = save_revision(self.draft, self.reviewer, {
            **self.revision.document, "html": markup,
        }, 1)
        self.assertTrue(any("Section title" in issue for issue in revision.issues))
        with self.assertRaisesMessage(ValueError, "Section title"):
            self.publish(2)
        for attribute in (
            'data-section-url="javascript:alert(1)"',
            'data-section-url="#local"', 'data-section-role="unknown"',
        ):
            with self.subTest(attribute=attribute), self.assertRaises(ValueError):
                save_revision(self.draft, self.reviewer, {
                    **revision.document, "html": f"<section {attribute}><h2>Title</h2></section>",
                }, 2)

    def test_article_subsections_do_not_change_article_classification_or_source_page_count(self):
        from library.services.document_edits import create_draft

        self.rendition.structure.update(book=False, pages=1)
        self.rendition.save(update_fields=["structure"])
        draft = create_draft(self.rendition, self.reviewer)
        save_revision(draft, self.reviewer, {
            **draft.document,
            "html": '<section id="article"><h2>Article</h2>'
            '<section id="notes"><h3>Notes</h3><p>Note.</p></section></section>',
        }, 0)
        candidate = prepare_publication(draft, 1)
        self.assertFalse(candidate["output"]["structure"]["book"])
        self.assertEqual(candidate["output"]["structure"]["pages"], 1)
        self.assertEqual(candidate["output"]["structure"]["parts"][1]["parent"], "article")

    def test_new_empty_section_persists_and_publishes_with_heading_toc_and_pdf(self):
        markup = '<section id="c1"><h2>Chapter</h2><p id="main">Main text.</p>' \
            '<section id="edited-section"><h3>Endnotes</h3><p></p></section></section>'
        revision = save_revision(self.draft, self.reviewer, {
            **self.revision.document, "html": markup,
        }, 1)
        self.assertEqual(revision.document["html"], markup)
        result = self.publish(2)
        soup = BeautifulSoup(result.rendition.html, "html.parser")
        section = soup.find("section", id="edited-section")
        self.assertEqual(section.h3.get_text(), "Endnotes")
        self.assertIsNotNone(section.p)
        self.assertEqual(section.p.get_text(), "")
        self.assertIn("Endnotes", [item["title"] for item in result.rendition.structure["toc"]])
        self.assertEqual(result.rendition.structure["book"],
                         bool(self.draft.evidence["structure"].get("book")))
        nested = next(part for part in result.rendition.structure["parts"]
                      if part["id"] == "edited-section")
        self.assertEqual(nested["parent"], "c1")
        response = self.client.get(reverse("reader", args=[result.rendition.pk]))
        self.assertContains(response, "Endnotes")
        output = io.BytesIO()
        render_pdf(result.rendition, output)
        pdf = PdfReader(output)
        self.assertIn("Endnotes", "\n".join(page.extract_text() for page in pdf.pages))

    def test_restored_section_boundary_preserves_chapter_targets_and_saved_ancestry(self):
        prefix = '<h2 id="iv">Chapter IV</h2><p id="earlier">Earlier prose.</p>'
        tail = '<h2 id="v">Chapter V</h2><p id="later">Later prose. ' \
            '<a href="#earlier" rel="noopener noreferrer">Return</a></p><pre>Exact\n  space</pre>'
        original = '<section id="c6">' + prefix + tail + '</section>'
        merged = save_revision(self.draft, self.reviewer, {
            **self.revision.document, "html": original,
        }, 1)
        restored = ('<section id="c6">' + prefix + '</section><section id="c7">'
                    + tail + '</section>')
        revision = save_revision(self.draft, self.reviewer, {
            **merged.document, "html": restored,
        }, 2)
        self.assertEqual(revision.document["html"], restored)
        self.assertEqual(revision.review, "partial")
        merged.refresh_from_db()
        self.assertEqual(merged.document["html"], original)
        self.assertFalse(DocumentPublication.objects.exists())
        publication = self.publish(3)
        soup = BeautifulSoup(publication.rendition.html, "html.parser")
        self.assertEqual([n["id"] for n in soup.find_all("section", recursive=False)], ["c6", "c7"])
        self.assertEqual(str(soup.select_one("#c7")), '<section id="c7">' + tail + '</section>')
        self.assertEqual([n["title"] for n in publication.rendition.structure["toc"]],
                         ["Chapter IV", "Chapter V"])
        self.assertContains(self.client.get(reverse("reader", args=[publication.rendition.pk])),
                            'href="#earlier"')
        output = io.BytesIO()
        render_pdf(publication.rendition, output)
        text = "\n".join(page.extract_text() for page in PdfReader(output).pages)
        for expected in ["Chapter IV", "Chapter V", "Earlier prose.", "Later prose."]:
            self.assertIn(expected, text)

    def test_created_and_renamed_note_targets_preserve_reciprocal_links_on_publication(self):
        markup = (
            '<section id="chapter"><h2>Chapter</h2><p id="reference">'
            '<a href="#renamed-note" rel="noopener noreferrer"><sup>1</sup></a> Main prose.'
            '</p><section id="notes"><h3>Notes</h3><p id="renamed-note">Note text. '
            '<a href="#reference" rel="noopener noreferrer">Return</a></p></section></section>'
        )
        revision = save_revision(self.draft, self.reviewer, {
            **self.revision.document, "html": markup,
        }, 1)
        self.assertEqual(revision.document["html"], markup)
        self.assertEqual(revision.review, "partial")
        publication = self.publish(2)
        soup = BeautifulSoup(publication.rendition.html, "html.parser")
        self.assertEqual(soup.select_one("#reference a")["href"], "#renamed-note")
        self.assertEqual(soup.select_one("#renamed-note a")["href"], "#reference")
        self.assertEqual(soup.select_one("#reference sup").get_text(), "1")
        self.assertEqual(soup.select_one("#renamed-note").find_parent("section")["id"], "notes")
        response = self.client.get(reverse("reader", args=[publication.rendition.pk]))
        self.assertContains(response, 'href="#renamed-note"')
        self.assertContains(response, 'href="#reference"')
        output = io.BytesIO()
        render_pdf(publication.rendition, output)
        text = "\n".join(page.extract_text() for page in PdfReader(output).pages)
        for expected in ["Main prose.", "Note text.", "Return"]:
            self.assertIn(expected, text)
        self.revision.refresh_from_db()
        self.assertNotIn("renamed-note", self.revision.document["html"])

    def test_renamed_inline_target_preserves_nested_content_and_reference_on_publication(self):
        markup = (
            '<section id="chapter"><h2>Chapter</h2><p>Before '
            '<span id="renamed-inline"><em>Nested</em> note '
            '<a href="#reference" rel="noopener noreferrer">Return</a></span> after.</p>'
            '<p id="reference"><a href="#renamed-inline" rel="noopener noreferrer">'
            'Reference</a></p></section>'
        )
        revision = save_revision(self.draft, self.reviewer, {
            **self.revision.document, "html": markup,
        }, 1)
        self.assertEqual(revision.document["html"], markup)
        result = self.publish(2)
        soup = BeautifulSoup(result.rendition.html, "html.parser")
        self.assertEqual(soup.select_one("#renamed-inline em").get_text(), "Nested")
        self.assertEqual(soup.select_one("#renamed-inline a")["href"], "#reference")
        self.assertEqual(soup.select_one("#reference a")["href"], "#renamed-inline")
        self.assertContains(self.client.get(reverse("reader", args=[result.rendition.pk])),
                            'id="renamed-inline"')
        output = io.BytesIO()
        render_pdf(result.rendition, output)
        text = "\n".join(page.extract_text() for page in PdfReader(output).pages)
        for expected in ["Before", "Nested", "note", "after.", "Reference"]:
            self.assertIn(expected, text)

    def test_preview_is_read_only_and_generates_collision_free_current_toc(self):
        candidate = prepare_publication(self.draft, 1)
        self.assertEqual(candidate["output"]["structure"]["toc"], [
            {"id": "c1", "level": 2, "title": "New heading", "style": "none",
             "number": 1, "marker": "", "editor_entry": True},
        ])
        self.assertIn('<h2>New heading</h2>', candidate["output"]["html"])
        self.assertEqual(Rendition.objects.count(), 1)
        self.assertFalse(DocumentPublication.objects.exists())
        self.assertNotIn("heading-1-h", self.revision.document["html"])
        response = self.client.get(self.url + self.query)
        self.assertContains(response, "Edited title")
        self.assertContains(response, "Not verified as a whole document")
        self.assertContains(response, 'href="#c1"')
        self.assertContains(response, reverse("document-comparison", args=[self.rendition.pk])
                            + f"?draft={self.draft.pk}&amp;to=1")
        self.assertEqual(Rendition.objects.count(), 1)
        css = self.client.get(self.url + self.query + "&stylesheet=1")
        self.assertEqual(css.content.decode(), self.rendition.stylesheet)
        self.assertEqual(css["Content-Type"], "text/css; charset=utf-8")

    def test_publish_is_idempotent_preserves_evidence_and_does_not_verify(self):
        result = self.publish()
        self.assertEqual(self.publish().pk, result.pk)
        self.assertEqual(Rendition.objects.count(), 2)
        self.assertEqual(result.revision_id, self.revision.pk)
        self.assertEqual(result.reviewer, self.reviewer)
        self.assertEqual(result.rendition.snapshot_id, self.rendition.snapshot_id)
        self.assertEqual(result.rendition.title, "Edited title")
        self.assertEqual(result.rendition.adapter_version, self.rendition.adapter_version)
        self.revision.refresh_from_db()
        self.assertEqual(self.revision.review, "partial")
        self.rendition.refresh_from_db()
        self.assertIn("Source text.", self.rendition.html)
        with self.assertRaisesMessage(ValueError, "immutable"):
            result.save()
        with self.assertRaisesMessage(ValueError, "immutable"):
            DocumentPublication.objects.filter(pk=result.pk).delete()

    def test_quotation_and_cited_attribution_survive_publication_reader_and_pdf(self):
        original = self.rendition.html
        markup = (
            '<section id="c1"><h2>Preface</h2><figure class="quotation">'
            '<blockquote id="quote"><p>Party struggles lend strength and vitality.</p>'
            '</blockquote><figcaption id="source"><p>From <cite>'
            '<a href="https://example.org/letter">A letter to Marx</a></cite>, 1852.'
            '</p></figcaption></figure><p>Following prose.</p></section>'
        )
        revision = save_revision(
            self.draft, self.reviewer, {**self.revision.document, "html": markup}, 1,
        )
        publication = self.publish(revision.revision)
        result = BeautifulSoup(publication.rendition.html, "html.parser")
        self.assertEqual(result.select_one("figure.quotation blockquote#quote p").get_text(),
                         "Party struggles lend strength and vitality.")
        self.assertEqual(
            result.select_one("figcaption#source cite a").get_text(), "A letter to Marx"
        )
        response = self.client.get(reverse("reader", args=[publication.rendition_id]))
        self.assertContains(response, '<cite><a href="https://example.org/letter"')
        self.assertContains(response, 'figcaption id="source"')
        with (
            tempfile.TemporaryDirectory() as directory,
            override_settings(DATA_DIR=Path(directory)),
        ):
            output = io.BytesIO()
            render_pdf(publication.rendition, output)
            document = PdfReader(output)
            text = " ".join(page.extract_text() for page in document.pages)
        for expected in ("Party struggles", "A letter to Marx", "1852", "Following prose"):
            self.assertIn(expected, text)
        self.rendition.refresh_from_db()
        self.assertEqual(self.rendition.html, original)
        self.assertEqual(revision.review, "partial")

    def test_stale_revision_or_wrong_preview_never_publishes(self):
        with self.assertRaises(DocumentEditConflict):
            publish_revision(self.draft, self.reviewer, 1, "wrong")
        candidate = prepare_publication(self.draft, 1)
        save_revision(self.draft, self.reviewer, self.revision.document, 1)
        with self.assertRaises(DocumentEditConflict):
            publish_revision(self.draft, self.reviewer, 1, candidate["digest"])
        self.assertEqual(Rendition.objects.count(), 1)
        self.assertFalse(DocumentPublication.objects.exists())

    def test_reordered_endnotes_preserve_targets_current_toc_reader_and_pdf_order(self):
        markup = (
            '<section id="c1"><h2>Opening</h2><p><a id="ref" href="#note">1</a></p></section>'
            '<section id="chapter"><h2>Main chapter</h2><p>Main chapter text.</p></section>'
            '<section id="notes"><h2>Endnotes</h2><p id="note">Final note text. '
            '<a href="#ref">Back</a></p></section>'
        )
        revision = save_revision(
            self.draft, self.reviewer, {**self.revision.document, "html": markup}, 1,
        )
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.revisions.get(revision=2).document, revision.document)
        publication = self.publish(2)
        self.assertEqual(
            [item["title"] for item in publication.rendition.structure["toc"]],
            ["Opening", "Main chapter", "Endnotes"],
        )
        result = BeautifulSoup(publication.rendition.html, "html.parser")
        self.assertEqual(result.find_all("section")[-1]["id"], "notes")
        self.assertEqual(result.select_one("#ref")["href"], "#note")
        self.assertEqual(result.select_one("#note a")["href"], "#ref")
        reader = self.client.get(reverse("reader", args=[publication.rendition_id]))
        self.assertContains(reader, 'id="notes"')
        output = io.BytesIO()
        render_pdf(publication.rendition, output)
        text = "\n".join(page.extract_text() for page in PdfReader(output).pages)
        self.assertLess(text.rindex("Main chapter text."), text.rindex("Final note text."))

    def test_manually_relocated_inline_content_keeps_note_links_and_saved_evidence(self):
        markup = (
            '<section id="c1"><h2>Chapter</h2><p id="main">Before '
            '<sup><a id="ref" href="#note">1</a></sup> after.</p>'
            '<p id="other">Another note.</p><section id="edited-section"><h2>Endnotes</h2>'
            '<p><span><sup><a id="note" href="#ref">1</a></sup> Relocated note '
            '<a href="#other">2</a> — Author.</span></p></section></section>'
        )
        value = {**self.revision.document, "html": markup}
        row = save_revision(self.draft, self.reviewer, value, 1)
        original_base = deepcopy(self.draft.document)
        publication = self.publish(row.revision)
        soup = BeautifulSoup(publication.rendition.html, "html.parser")
        self.assertEqual(soup.select_one("#note").find_parent("section")["id"], "edited-section")
        self.assertEqual(soup.select_one("#main").get_text(), "Before 1 after.")
        self.assertEqual(soup.select_one("#ref")["href"], "#note")
        self.assertEqual(soup.select_one("#note")["href"], "#ref")
        self.assertEqual(len(soup.select("#note")), 1)
        self.assertEqual(soup.select_one('#edited-section a[href="#other"]').get_text(), "2")
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.document, original_base)
        reader = self.client.get(reverse("reader", args=[publication.rendition_id]))
        self.assertContains(reader, "Relocated note")
        output = io.BytesIO()
        render_pdf(publication.rendition, output)
        text = "\n".join(page.extract_text() for page in PdfReader(output).pages)
        self.assertLess(text.rindex("Before"), text.rindex("Relocated note"))

    def test_invalid_relationships_metadata_and_empty_content_block_publication(self):
        cases = [
            {**self.revision.document, "html": '<p><a href="#absent">Missing</a></p>'},
            {**self.revision.document, "html": '<p class="missing-image">Missing</p>'},
            {**self.revision.document, "html": "<p></p>"},
        ]
        for number, document in enumerate(cases, 2):
            save_revision(self.draft, self.reviewer, document, number - 1)
            with self.subTest(document=document), self.assertRaises(ValueError):
                prepare_publication(self.draft, number)
        self.assertEqual(Rendition.objects.count(), 1)
        invalid_metadata = {
            **self.revision.document,
            "metadata": {**self.revision.document["metadata"], "author": ["invalid"]},
        }
        with self.assertRaisesMessage(ValueError, "Author must be text"):
            save_revision(
                self.draft, self.reviewer, invalid_metadata,
                self.draft.revisions.first().revision,
            )

    def test_tampered_revision_base_or_source_evidence_is_refused(self):
        self.draft.document_digest = "bad"
        with self.assertRaisesMessage(ValueError, "integrity"):
            prepare_publication(self.draft, 1)
        self.draft.refresh_from_db()
        self.rendition.html = "<p>Changed original evidence</p>"
        self.rendition.save(update_fields=["html"])
        self.draft.refresh_from_db()
        with self.assertRaises(DocumentEditConflict):
            prepare_publication(self.draft, 1)

    def test_profile_and_revision_bounds_are_explicit(self):
        for revision in (0, -1, True, "1"):
            with self.subTest(revision=revision), self.assertRaises(ValueError):
                prepare_publication(self.draft, revision)
        with patch(
            "library.services.document_publication.get_profile",
            return_value=replace(get_profile(), key="another-profile"),
        ), self.assertRaises(ValueError):
            prepare_publication(self.draft, 1)

    def test_referenced_assets_are_checked_again_and_bound_to_new_edition(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            override_settings(DATA_DIR=Path(directory)),
        ):
            output = io.BytesIO()
            Image.new("RGB", (2, 2), "white").save(output, format="PNG")
            data = output.getvalue()
            digest = store_blob(data)
            blob = Blob.objects.create(digest=digest, media_type="image/png", size=len(data))
            RenditionAsset.objects.create(rendition=self.rendition, blob=blob)
            # Asset evidence is pinned at creation, not silently expanded later.
            value = {
                **self.revision.document, "html": f'<p>Image</p><img src="/assets/{digest}/"/>',
            }
            save_revision(self.draft, self.reviewer, value, 1)
            with self.assertRaisesMessage(ValueError, "not bound"):
                prepare_publication(self.draft, 2)
            from library.services.document_edits import create_draft

            self.draft = create_draft(self.rendition, self.reviewer)
            save_revision(self.draft, self.reviewer, value, 0)
            candidate = prepare_publication(self.draft, 1)
            with patch("library.services.document_publication.read_blob", side_effect=OSError):
                with self.assertRaisesMessage(ValueError, "unavailable or corrupt"):
                    publish_revision(self.draft, self.reviewer, 1, candidate["digest"])
            self.assertEqual(Rendition.objects.count(), 1)
            blob_path(digest).write_bytes(b"corrupt bytes")
            with self.assertRaisesMessage(ValueError, "unavailable or corrupt"):
                publish_revision(self.draft, self.reviewer, 1, candidate["digest"])
            blob_path(digest).write_bytes(data)
            result = self.publish()
            self.assertEqual(
                list(result.rendition.assets.values_list("blob_id", flat=True)), [digest],
            )

    def test_publication_requires_permission_csrf_confirmation_and_exact_preview(self):
        self.assertEqual(self.client.post(self.url + self.query, {}).status_code, 422)
        candidate = prepare_publication(self.draft, 1)
        payload = {"confirm": "yes", "revision": "1", "preview_digest": candidate["digest"]}
        self.assertEqual(self.client.post(
            self.url + self.query, {**payload, "preview_digest": "wrong"},
        ).status_code, 409)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.reviewer)
        self.assertEqual(protected.post(self.url + self.query, payload).status_code, 403)
        self.reviewer.is_staff = False
        self.reviewer.save(update_fields=["is_staff"])
        self.assertEqual(self.client.get(self.url + self.query).status_code, 403)
        self.assertEqual(self.client.post(self.url + self.query, payload).status_code, 403)
        self.reviewer.is_staff = True
        self.reviewer.save(update_fields=["is_staff"])
        with override_settings(READING_HUB_EDITOR_PILOT=False):
            self.assertEqual(self.client.get(self.url + self.query).status_code, 404)
            self.assertEqual(self.client.post(self.url + self.query, payload).status_code, 404)
        response = self.client.post(self.url + self.query, payload)
        result = DocumentPublication.objects.get()
        self.assertRedirects(response, reverse("reader", args=[result.rendition_id]))

    def test_edited_reader_stylesheet_and_pdf_do_not_redirect_to_another_book(self):
        result = self.publish()
        with patch("library.organization_views.member_destination") as destination:
            response = self.client.get(reverse("reader", args=[result.rendition_id]))
            self.assertContains(response, "Edited text.")
            self.assertContains(response, "Not verified as a whole document")
            self.assertContains(response, 'href="#c1"')
            self.assertContains(response, "Original edition")
            css = self.client.get(reverse("reader-css", args=[result.rendition_id]))
            self.assertEqual(css.content.decode(), self.rendition.stylesheet)
            destination.assert_not_called()

    def test_pdf_contains_edited_text_review_status_and_separate_opening_page(self):
        self.rendition.stylesheet = (STYLES / "reader.css").read_text()
        self.rendition.save(update_fields=["stylesheet"])
        from library.services.document_edits import create_draft

        self.draft = create_draft(self.rendition, self.reviewer)
        save_revision(self.draft, self.reviewer, self.revision.document, 0)
        result = self.publish()
        output = io.BytesIO()
        render_pdf(result.rendition, output)
        pdf = PdfReader(output)
        self.assertGreaterEqual(len(pdf.pages), 2)
        self.assertIn("Edited title", pdf.pages[0].extract_text())
        self.assertIn("Not verified as a whole document", pdf.pages[0].extract_text())
        self.assertNotIn("Edited text.", pdf.pages[0].extract_text())
        self.assertIn("Edited text.", "\n".join(page.extract_text() for page in pdf.pages[1:]))

    def test_preview_output_does_not_mutate_pinned_structure(self):
        before = deepcopy(self.draft.evidence)
        prepare_publication(self.draft, 1)
        self.assertEqual(self.draft.evidence, before)

    def test_direct_metadata_changes_are_validated_and_used_in_published_reader(self):
        value = {
            **self.revision.document,
            "metadata": {
                **self.revision.document["metadata"], "author": "Corrected Author",
                "subtitle": "Corrected Subtitle", "language": "fr",
            },
        }
        revision = save_revision(self.draft, self.reviewer, value, 1)
        self.assertEqual(revision.document["metadata"]["author"], "Corrected Author")
        self.revision = revision
        result = self.publish()
        self.assertEqual(result.rendition.metadata["subtitle"], "Corrected Subtitle")
        self.assertContains(
            self.client.get(reverse("reader", args=[result.rendition_id])),
            "Corrected Author",
        )
        self.assertContains(
            self.client.get(reverse("reader", args=[result.rendition_id])),
            'lang="fr"',
        )

    def test_failed_provenance_write_rolls_back_entire_publication(self):
        candidate = prepare_publication(self.draft, 1)
        with patch(
            "library.services.document_publication.DocumentPublication.objects.create",
            side_effect=ValueError("failed evidence write"),
        ), self.assertRaisesMessage(ValueError, "failed evidence"):
            publish_revision(self.draft, self.reviewer, 1, candidate["digest"])
        self.assertEqual(Rendition.objects.count(), 1)
        self.assertFalse(DocumentPublication.objects.exists())

    def test_saved_document_is_authoritative_when_original_section_is_removed(self):
        from library.services.document_edits import create_draft

        self.rendition.structure["parts"] = [
            {"url": self.rendition.document.url, "id": "c1", "title": "Opening"},
        ]
        self.rendition.save(update_fields=["structure"])
        draft = create_draft(self.rendition, self.reviewer)
        save_revision(
            draft, self.reviewer, {**draft.document, "html": "<p>Removed chapter target.</p>"}, 0,
        )
        candidate = prepare_publication(draft, 1)
        self.assertEqual(candidate["output"]["structure"]["parts"], [])
        self.assertEqual(draft.evidence["structure"]["parts"][0]["id"], "c1")

    def test_unwrapped_target_and_cleared_properties_do_not_restore_source_organization(self):
        from library.services.document_edits import create_draft

        self.rendition.structure["parts"] = [{
            "id": "c1", "url": "https://example.org/source", "title": "Original",
            "group": "Old group", "use_source_headings": True,
            "section": "raw-source-section", "excerpt": {"historical": "selector"},
        }]
        self.rendition.save(update_fields=["structure"])
        draft = create_draft(self.rendition, self.reviewer)
        save_revision(draft, self.reviewer, {
            **draft.document,
            "html": '<section id="c1" data-section-url="" data-section-group="">'
            '<h2>Corrected</h2><p>Content.</p></section>',
        }, 0)
        part = prepare_publication(draft, 1)["output"]["structure"]["parts"][0]
        self.assertEqual(part, {"id": "c1", "title": "Corrected", "role": "chapter"})
        save_revision(draft, self.reviewer, {
            **draft.document,
            "html": '<span id="c1"></span><h2>Corrected</h2>'
            '<p>Content. <a href="#c1">Return</a></p>',
        }, 1)
        candidate = prepare_publication(draft, 2)
        self.assertEqual(candidate["output"]["structure"]["parts"], [])

    def test_excerpt_origin_survives_move_save_reopen_publication_and_pdf(self):
        markup = (
            '<section id="origin"><h2>Parent</h2><p>Remaining.</p></section>'
            '<section id="destination"><h2>Destination</h2>'
            '<section id="excerpt" data-section-title="excerpt-title" '
            'data-section-group="Editorial" data-excerpt-parent="origin" '
            'data-excerpt-url="https://example.org/source">'
            '<h3 id="excerpt-title">Selected paragraphs</h3>'
            '<p id="note">Exact <em>note</em>. <a href="#origin">Return</a></p>'
            '</section></section>'
        )
        revision = save_revision(self.draft, self.reviewer, {
            **self.revision.document, "html": markup,
            "metadata": {
                **self.revision.document["metadata"], "content_organization": {"book": True},
            },
        }, 1)
        self.assertEqual(revision.issues, [])
        result = self.publish(2)
        part = result.rendition.structure["parts"][2]
        self.assertEqual(part["parent"], "destination")
        self.assertEqual(part["excerpt_origin"], {
            "section": "origin", "url": "https://example.org/source",
        })
        self.assertEqual(part["group"], "Editorial")
        self.assertTrue(result.rendition.structure["book"])
        reopened = self.client.get(reverse("document-editor", args=[self.rendition.pk]),
                                   {"draft": self.draft.pk})
        self.assertEqual(reopened.context["initial"]["document"]["html"], revision.document["html"])
        reader = self.client.get(reverse("reader", args=[result.rendition.pk]))
        self.assertContains(reader, 'data-excerpt-parent="origin"')
        output = io.BytesIO()
        render_pdf(result.rendition, output)
        self.assertIn("Selected paragraphs", " ".join(
            page.extract_text() for page in PdfReader(output).pages
        ))

    def test_excerpt_missing_or_cyclic_origins_block_publication_not_partial_save(self):
        for markup in (
            '<section id="e" data-excerpt-parent="missing"><p>Text.</p></section>',
            '<section id="a" data-excerpt-parent="b"><p>A.</p></section>'
            '<section id="b" data-excerpt-parent="a"><p>B.</p></section>',
            '<section id="a" data-excerpt-url="https://example.org/"><p>A.</p></section>',
        ):
            with self.subTest(markup=markup):
                current = self.draft.revisions.first().revision
                revision = save_revision(self.draft, self.reviewer, {
                    **self.revision.document, "html": markup,
                }, current)
                self.assertTrue(any("Excerpt origin" in issue for issue in revision.issues))
                with self.assertRaisesMessage(ValueError, "Excerpt origin"):
                    self.publish(revision.revision)

    def test_mixed_whole_block_excerpt_save_reopen_and_publication_keep_every_container(self):
        blocks = (
            '<p id="p">Text <a href="#parent">Back</a></p><h4 id="h">Heading</h4>'
            '<table id="table"><tbody><tr><td>Cell</td></tr></tbody></table>'
            '<ul id="list"><li>Item</li></ul>'
            '<figure id="figure"><blockquote><p>Quote</p></blockquote>'
            '<figcaption>Credit</figcaption></figure>'
            '<pre id="pre">  exact\n spacing</pre><hr id="rule"/>'
        )
        markup = (
            '<section id="parent"><h2>Parent</h2><p>Remaining</p></section>'
            '<section id="excerpt" data-excerpt-parent="parent">'
            '<h3>Mixed excerpt</h3>' + blocks + '</section>'
        )
        revision = save_revision(self.draft, self.reviewer, {
            **self.revision.document, "html": markup,
        }, 1)
        self.assertEqual(revision.issues, [])
        result = self.publish(2)
        soup = BeautifulSoup(result.rendition.html, "html.parser")
        self.assertEqual(
            [node.name for node in soup.select_one("#excerpt").find_all(recursive=False)],
            ["h3", "p", "h4", "table", "ul", "figure", "pre", "hr"],
        )
        expected = BeautifulSoup(revision.document["html"], "html.parser").select_one("#excerpt")
        for node in expected.select("[id]"):
            self.assertEqual(str(soup.find(id=node["id"])), str(node))
        reopened = self.client.get(reverse("document-editor", args=[self.rendition.pk]),
                                   {"draft": self.draft.pk})
        self.assertEqual(reopened.context["initial"]["document"]["html"],
                         revision.document["html"])

    def test_organization_metadata_and_excerpt_attributes_are_strict(self):
        for value in ({"book": "true"}, {"book": True, "parts": []}, [], None):
            with self.subTest(value=value), self.assertRaisesMessage(ValueError, "organization"):
                save_revision(self.draft, self.reviewer, {
                    **self.revision.document,
                    "metadata": {
                        **self.revision.document["metadata"], "content_organization": value,
                    },
                }, 1)
        for attribute in (
            'data-excerpt-parent=""', 'data-excerpt-parent="two targets"',
            'data-excerpt-url="javascript:alert(1)"', 'data-section-group="&#10;"',
        ):
            with self.subTest(attribute=attribute), self.assertRaises(ValueError):
                save_revision(self.draft, self.reviewer, {
                    **self.revision.document,
                    "html": f"<section {attribute}><p>Text.</p></section>",
                }, 1)

    def test_changed_publication_rules_cannot_reuse_a_different_preview(self):
        self.publish()
        with patch(
            "library.services.document_publication.PUBLICATION_VERSION", PUBLICATION_VERSION + 1,
        ):
            candidate = prepare_publication(self.draft, 1)
            with self.assertRaisesMessage(DocumentEditConflict, "another preview"):
                publish_revision(self.draft, self.reviewer, 1, candidate["digest"])
        self.assertEqual(Rendition.objects.count(), 2)
