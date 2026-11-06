import io
from copy import deepcopy
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from pypdf import PdfReader

from library.models import CanonicalAuthor
from library.services.document_edits import save_revision, validate_editor_metadata
from library.services.document_metadata import (
    book_pages, fact_spans, metadata_entries, metadata_rows, page_preset, title_facts,
)
from library.services.document_publication import prepare_publication, publish_revision
from library.services.pdf import render_pdf
from library.tests import test_document_edits as foundation


@override_settings(READING_HUB_EDITOR_PILOT=True)
class EditorMetadataTests(TestCase):
    def setUp(self):
        foundation.DocumentEditTests.setUp(self)
        self.reviewer.is_staff = True
        self.reviewer.save(update_fields=["is_staff"])
        self.client.force_login(self.reviewer)

    def values(self):
        return {
            **deepcopy(self.draft.document["metadata"]),
            "contributors": [
                {"name": "First Writer", "source_name": "F. Writer", "role": "author"},
                {"name": "Second Writer", "source_name": "S. Writer", "role": "author"},
                {"name": "A Translator", "source_name": "A Translator", "role": "translator"},
                {"name": "An Editor", "source_name": "An Editor", "role": "editor"},
                {"name": "Unconfirmed", "source_name": "Unconfirmed", "role": "unknown"},
                {"name": "Not an author", "source_name": "Not an author", "role": "exclude"},
            ],
            "date_facts": [
                {"value": "1891", "end_value": "1892", "type": "written"},
                {"value": "1902-03", "type": "publication"},
                {"value": "2026-10-25", "type": "online_edition"},
            ],
            "topics": ["History", "Philosophy"],
        }

    def test_structured_values_derive_consistent_reader_fields_and_are_idempotent(self):
        value = validate_editor_metadata(self.draft.document["metadata"], self.values())
        self.assertEqual(value["author"], "First Writer, Second Writer")
        self.assertEqual(value["authors"], ["First Writer", "Second Writer"])
        self.assertEqual(value["published"], "1902-03")
        self.assertEqual(value["topic"], "History, Philosophy")
        self.assertFalse(value["author_is_fallback"])
        self.assertEqual(validate_editor_metadata(self.draft.document["metadata"], value), value)
        rows = metadata_rows(value)
        self.assertEqual(rows, [
            ("Author", "First Writer, Second Writer"), ("Translator", "A Translator"),
            ("Written", "1891 / 1892"), ("Published", "1902-03"),
        ], "The title page is synthetic by default.")
        entries = [(label, text) for _, label, text in metadata_entries(value)]
        self.assertIn(("Editor", "An Editor"), entries)
        self.assertIn(("Online edition", "2026-10-25"), entries)
        self.assertNotIn(("Author", "Not an author"), entries)

    def test_bibliographic_text_fields_and_original_language_are_editable(self):
        original = self.draft.document["metadata"]
        value = validate_editor_metadata(original, {
            **original, "original_title": "  Das Kapital ", "publisher": "Verlag",
            "series": "Collected Works 35", "original_language": "DE_at",
        })
        self.assertEqual(value["original_title"], "Das Kapital")
        self.assertEqual(value["original_language"], "de-AT")
        self.assertEqual(validate_editor_metadata(original, value), value)
        entries = [(label, text) for _, label, text in metadata_entries(value)]
        for row in (("Original title", "Das Kapital"), ("Publisher", "Verlag"),
                    ("Series", "Collected Works 35"), ("Original language", "German")):
            self.assertIn(row, entries)
            self.assertNotIn(row, metadata_rows(value))
        cleared = validate_editor_metadata(value, {**value, "publisher": " ", "original_language": ""})
        self.assertNotIn("publisher", cleared)
        self.assertNotIn("original_language", cleared)
        for key, invalid in (
            ("original_title", "Bad\ntitle"), ("publisher", "x" * 2001), ("series", ["list"]),
            ("original_language", "zz-invalid-language"),
        ):
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_editor_metadata(original, {**original, key: invalid})

    def test_editorial_note_fields_delivered_dates_and_title_page_selection(self):
        original = self.draft.document["metadata"]
        value = validate_editor_metadata(original, {
            **original,
            "publication_note": "First published as a separate work in March 1902.",
            "source_edition": "Collected Works, Volume 5, pp. 347-530.",
            "translation_note": "Joe Fineberg and George Hanna.",
            "online_version": "Online Version: MIA 1999",
            "transcription": "Original Transcription & Markup: Tim Delaney (1999)",
            "proofreading": "Proofread by: K. Goins (2008)",
            "rights": "Public Domain: Lenin Internet Archive (1999).",
            "notes": "  Signed: N. Lenin \r\n\n Delivered: 12 May 1920  ",
            "date_facts": [{"value": "1920-05-12", "type": "delivered"}],
        })
        self.assertEqual(value["notes"], "Signed: N. Lenin\nDelivered: 12 May 1920")
        self.assertEqual(validate_editor_metadata(original, value), value)
        rows = metadata_rows(value)
        self.assertEqual(rows, [
            ("Delivered", "1920-05-12"), ("Rights", "Public Domain: Lenin Internet Archive (1999)."),
        ], "The synthetic title page keeps dates, rights and source only.")
        entries = [(label, text) for _, label, text in metadata_entries(value)]
        for row in (
            ("Publication history", "First published as a separate work in March 1902."),
            ("Source edition", "Collected Works, Volume 5, pp. 347-530."),
            ("Translation", "Joe Fineberg and George Hanna."),
        ):
            self.assertIn(row, entries)
        hidden = {"Online version", "Transcription/markup", "Proofreading", "Other notes"}
        self.assertFalse(hidden & {label for label, _ in rows}, "Credits are hidden by default.")
        self.assertTrue(hidden <= {label for label, _ in entries})
        chosen = validate_editor_metadata(original, {
            **value, "title_page_fields": ["notes", "delivered", "rights"],
        })
        self.assertEqual(chosen["title_page_fields"], ["delivered", "rights", "notes"])
        self.assertEqual(metadata_rows(chosen), [
            ("Delivered", "1920-05-12"),
            ("Rights", "Public Domain: Lenin Internet Archive (1999)."),
            ("Other notes", "Signed: N. Lenin; Delivered: 12 May 1920"),
        ])
        for key, invalid in (
            ("notes", "bad\x00control"), ("notes", "x" * 4001), ("source_edition", "x" * 2001),
            ("rights", "two\nlines"), ("title_page_fields", "author"),
            ("title_page_fields", ["author", "author"]), ("title_page_fields", ["unknown_field"]),
        ):
            with self.subTest(key=key, invalid=invalid[:20]), self.assertRaises(ValueError):
                validate_editor_metadata(original, {**original, key: invalid})

    def test_compact_title_facts_pack_rows_and_keep_order(self):
        self.assertEqual(fact_spans([14, 17, 7, 140, 66]), [2, 2, 2, 6, 6])
        self.assertEqual(fact_spans([14, 30, 10]), [3, 3, 6])
        metadata = {"author": "Vladimir Lenin", "language": "en",
                    "rights": "Lenin Internet Archive (1999). " * 4,
                    "date_facts": [{"type": "written", "value": "1901-09", "end_value": "1902-02"},
                                   {"type": "publication", "value": "1903-03"}]}
        url = "https://www.marxists.org/archive/lenin/works/1901/witbd/index.htm"
        facts = title_facts(metadata, "Vladimir Lenin", url)
        self.assertEqual([(fact["field"], fact["span"]) for fact in facts],
                         [("author", 2), ("written", 2), ("publication", 2), ("rights", 6),
                          ("source_url", 6)])
        self.assertEqual(facts[-1]["url"], url)

    def test_work_type_and_page_settings_validate_and_override_presets(self):
        original = self.draft.document["metadata"]
        self.assertEqual(page_preset(None, False),
                         {"title_layout": "compact", "contents_page": False, "metadata_page": True})
        self.assertEqual(page_preset(None, True)["title_layout"], "full")
        self.assertEqual(page_preset("letter", True)["title_layout"], "compact")
        self.assertTrue(page_preset("pamphlet", False)["contents_page"])
        value = validate_editor_metadata(original, {
            **original, "work_type": "speech", "title_layout": "full", "contents_page": True,
            "metadata_page": False,
        })
        self.assertEqual(book_pages(value), {"title_layout": "full", "contents_page": True, "metadata_page": False})
        self.assertEqual(metadata_entries(value)[0], ("work_type", "Type", "Speech"))
        self.assertEqual(validate_editor_metadata(original, value), value)
        for key, invalid in (
            ("work_type", "novel"), ("title_layout", "tiny"), ("contents_page", "yes"), ("metadata_page", 1),
        ):
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_editor_metadata(original, {**original, key: invalid})
        editor = self.client.get(reverse("document-editor", args=[self.rendition.pk]))
        self.assertContains(editor, '<option value="letter">Letter</option>', html=False)
        self.assertContains(editor, 'id="editor-tab-metadata"')

    def test_title_page_selection_controls_reader_rows_and_source_link(self):
        metadata = {**self.values(), "rights": "Public Domain", "title_page_fields": ["rights"]}
        row = save_revision(
            self.draft, self.reviewer, {**self.draft.document, "metadata": metadata}, 0,
        )
        candidate = prepare_publication(self.draft, row.revision)
        published = publish_revision(self.draft, self.reviewer, row.revision, candidate["digest"])
        reader = self.client.get(reverse("reader", args=[published.rendition_id]))
        self.assertContains(reader, "<dt>Rights</dt><dd>Public Domain</dd>", html=False)
        self.assertNotContains(reader, "<dt>Translator</dt>")
        html = reader.content.decode()
        header = html[html.index('<header class="document-header'):]
        header = header[:header.index("</header>")]
        self.assertNotIn('class="source-link"', header, "Unselected source stays off the title page.")
        page = html[html.index('id="document-metadata"'):]
        self.assertIn('class="source-link"', page, "The metadata page still records the source.")
        self.assertIn("<th scope=\"row\">Translator</th>", page)

    def test_register_person_creates_or_reuses_a_registered_author(self):
        url = reverse("document-editor-register-person")
        created = self.client.post(
            url, {"name": "  Joe   Fineberg ", "authority_uri": "https://www.wikidata.org/wiki/Q1"},
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json(), {
            "name": "Joe Fineberg", "authority_uri": "https://www.wikidata.org/wiki/Q1", "created": True,
        })
        again = self.client.post(
            url, {"name": "Joe Fineberg", "authority_uri": "https://www.wikidata.org/wiki/Q1"},
            content_type="application/json",
        )
        self.assertEqual(again.status_code, 200)
        self.assertEqual(CanonicalAuthor.objects.filter(name="Joe Fineberg").count(), 1)
        for payload in ({"name": ""}, {"name": "X", "authority_uri": "javascript:alert(1)"},
                        {"name": ["X"]}, []):
            with self.subTest(payload=payload):
                response = self.client.post(url, payload, content_type="application/json")
                self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get(url).status_code, 405)
        search = self.client.get(reverse("document-editor-people"), {"q": "Fineberg"}).json()
        self.assertIn(
            {"name": "Joe Fineberg", "authority_uri": "https://www.wikidata.org/wiki/Q1"},
            search["candidates"] + search["others"],
        )
        original = self.draft.document["metadata"]
        linked = validate_editor_metadata(original, {**original, "contributors": [{
            "name": "Joe Fineberg", "source_name": "J. Fineberg", "role": "translator",
            "canonical": {"name": "Joe Fineberg", "authority_uri": "https://www.wikidata.org/wiki/Q1"},
        }]})
        self.assertEqual(linked["contributors"][0]["canonical"]["authority_uri"],
                         "https://www.wikidata.org/wiki/Q1")
        self.client.logout()
        self.assertNotEqual(
            self.client.post(url, {"name": "Anonymous"}, content_type="application/json").status_code,
            201,
        )
        self.assertFalse(CanonicalAuthor.objects.filter(name="Anonymous").exists())

    def test_invalid_dates_people_subjects_and_derived_field_conflicts_refuse(self):
        for key, invalid in (
            ("contributors", [{"name": "", "source_name": "X", "role": "author"}]),
            ("contributors", [{"name": "X", "source_name": "X", "role": "owner"}]),
            ("contributors", [{"name": "X\nY", "source_name": "X", "role": "author"}]),
            ("date_facts", [{"value": "1900-02-29", "type": "written"}]),
            ("date_facts", [{"value": "1902", "end_value": "1901", "type": "written"}]),
            ("date_facts", [{"value": "1902", "end_value": "1903-02", "type": "written"}]),
            ("date_facts", [{"value": "1902", "type": "publication"}] * 2),
            ("topics", [""]),
            ("topics", "not a list"),
            ("topics", ["Bad\nsubject"]),
            ("published", "forged derived value"),
            ("authors", ["forged"]),
            ("topic", "forged"),
            ("unapproved", "field"),
        ):
            value = {**self.draft.document["metadata"], key: invalid}
            with self.subTest(key=key, invalid=invalid), self.assertRaises(ValueError):
                validate_editor_metadata(self.draft.document["metadata"], value)
        with self.assertRaisesMessage(ValueError, "conflicts"):
            validate_editor_metadata(
                self.draft.document["metadata"], {**self.values(), "author": "Conflicting author"},
            )

    def test_clear_is_explicit_and_does_not_restore_fallback_or_dates(self):
        original = validate_editor_metadata(self.draft.document["metadata"], self.values())
        value = validate_editor_metadata(original, {
            **original, "contributors": [], "date_facts": [], "topics": [],
        })
        self.assertNotIn("author", value)
        self.assertEqual(value["authors"], [])
        self.assertFalse(value["author_is_fallback"])
        self.assertEqual(value["published"], "")
        self.assertEqual(value["topic"], "")
        self.assertEqual(value["topics"], [])

    def test_unedited_historical_dates_remain_exact_when_other_metadata_changes(self):
        original = {
            **self.draft.document["metadata"],
            "published": "2024-04-04T09:57:34+01:00",
            "date_facts": [{
                "value": "1917", "type": "written", "method": "archive-labelled-date",
                "evidence": "Written: August - September, 1917",
            }],
        }
        result = validate_editor_metadata(original, {**original, "topics": ["History"]})
        self.assertEqual(result["date_facts"], original["date_facts"])
        self.assertEqual(result["published"], original["published"])
        self.assertEqual(validate_editor_metadata(original, result), result)

    def test_scalar_author_edit_keeps_author_list_and_roles_consistent(self):
        original = validate_editor_metadata(self.draft.document["metadata"], self.values())
        result = validate_editor_metadata(original, {**original, "author": "Changed writer"})
        self.assertEqual(result["authors"], ["Changed writer"])
        self.assertEqual([p["name"] for p in result["contributors"] if p["role"] == "author"],
                         ["Changed writer"])
        self.assertEqual([p for p in result["contributors"] if p["role"] == "translator"],
                         [original["contributors"][2]])

    def test_save_reopen_comparison_and_publication_share_metadata(self):
        original = deepcopy(self.rendition.metadata)
        value = {**self.draft.document, "metadata": self.values()}
        row = save_revision(self.draft, self.reviewer, value, 0)
        editor = reverse("document-editor", args=[self.rendition.pk])
        with patch("library.document_editor_views.finders.find", return_value="built"):
            response = self.client.get(editor, {"draft": self.draft.pk})
        self.assertEqual(
            response.context["initial"]["document"]["metadata"], row.document["metadata"],
        )
        self.assertContains(response, 'id="editor-contributors"')
        self.assertContains(response, 'id="editor-dates"')
        for name in ("original_title", "publisher", "series", "original_language", "source_edition",
                     "translation_note", "transcription", "rights", "notes"):
            self.assertContains(response, f'name="{name}"')
        self.assertContains(response, 'id="editor-metadata-import"')
        self.assertContains(response, 'id="editor-person-link"')
        page = response.content.decode()
        self.assertLess(page.index('class="editor-workspace"'), page.index('class="editor-metadata"'))
        comparison = reverse("document-comparison", args=[self.rendition.pk])
        result = self.client.get(
            comparison, {"draft": self.draft.pk, "to": 1, "download": 1},
        ).json()
        self.assertEqual(result["later"]["document"]["metadata"], row.document["metadata"])
        candidate = prepare_publication(self.draft, 1)
        self.assertEqual(candidate["output"]["metadata"], row.document["metadata"])
        published = publish_revision(self.draft, self.reviewer, 1, candidate["digest"])
        self.assertEqual(published.rendition.metadata, row.document["metadata"])
        reader = self.client.get(reverse("reader", args=[published.rendition_id]))
        self.assertContains(reader, "A Translator")
        self.assertContains(reader, "1891 / 1892")
        self.assertContains(reader, "History, Philosophy")
        output = io.BytesIO()
        render_pdf(published.rendition, output)
        pdf_text = "\n".join(page.extract_text() for page in PdfReader(output).pages)
        self.assertIn("A Translator", pdf_text)
        self.assertIn("1891 / 1892", pdf_text)
        self.assertIn("History, Philosophy", pdf_text)
        self.rendition.refresh_from_db()
        self.assertEqual(self.rendition.metadata, original)
