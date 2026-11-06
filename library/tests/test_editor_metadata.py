import io
from copy import deepcopy
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from pypdf import PdfReader

from library.services.document_edits import save_revision, validate_editor_metadata
from library.services.document_metadata import metadata_rows
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
        self.assertIn(("Translator", "A Translator"), rows)
        self.assertIn(("Editor", "An Editor"), rows)
        self.assertIn(("Written", "1891 / 1892"), rows)
        self.assertNotIn(("Author", "Not an author"), rows)

    def test_bibliographic_text_fields_and_original_language_are_editable(self):
        original = self.draft.document["metadata"]
        value = validate_editor_metadata(original, {
            **original, "original_title": "  Das Kapital ", "publisher": "Verlag",
            "series": "Collected Works 35", "original_language": "DE_at",
        })
        self.assertEqual(value["original_title"], "Das Kapital")
        self.assertEqual(value["original_language"], "de-AT")
        self.assertEqual(validate_editor_metadata(original, value), value)
        rows = metadata_rows(value)
        for row in (("Original title", "Das Kapital"), ("Publisher", "Verlag"),
                    ("Series", "Collected Works 35"), ("Original language", "German")):
            self.assertIn(row, rows)
        cleared = validate_editor_metadata(value, {**value, "publisher": " ", "original_language": ""})
        self.assertNotIn("publisher", cleared)
        self.assertNotIn("original_language", cleared)
        for key, invalid in (
            ("original_title", "Bad\ntitle"), ("publisher", "x" * 1001), ("series", ["list"]),
            ("original_language", "zz-invalid-language"),
        ):
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_editor_metadata(original, {**original, key: invalid})

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
        for name in ("original_title", "publisher", "series", "original_language"):
            self.assertContains(response, f'name="{name}"')
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
