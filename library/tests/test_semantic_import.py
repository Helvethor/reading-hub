import io
import json
from copy import deepcopy

from bs4 import BeautifulSoup
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from library.models import DocumentDraftBase
from library.services.document_edits import (
    DocumentEditConflict,
    create_draft,
    preview_rendition_import,
    save_revision,
)
from library.services.semantic_documents import canonical_document, document_issues
from library.services.semantic_import import preview_import
from library.tests import test_document_edits as foundation
from library.tests.test_document_edits import DIGEST, document


class SemanticImportTests(SimpleTestCase):
    def test_valid_documents_need_no_repair_or_approval(self):
        value = document()
        original = deepcopy(value)
        proposal = preview_import(value)
        self.assertEqual(proposal["document"], canonical_document(value))
        self.assertFalse(proposal["requires_approval"])
        self.assertEqual(proposal["conversion"]["repairs"], [])
        self.assertEqual(value, original)
        self.assertEqual(preview_import(value), proposal)

    def test_block_wrapper_conversion_preserves_text_attributes_and_targets(self):
        value = document(
            '<section id="c1"><span id="wrapper" class="text-italic-on">'
            '\n<div><p>Original 😀 <em>words</em>.</p>'
            '<img alt="An image" src="/assets/' + DIGEST + '/"/></div>'
            '<p id="note">Endnote <a href="#wrapper">Back</a></p></span></section>'
        )
        original = deepcopy(value)
        proposal = preview_import(value)
        self.assertTrue(proposal["requires_approval"])
        self.assertEqual(proposal["conversion"]["repairs"], [{
            "element": 1, "id": "wrapper", "operation": "block-wrapper",
            "before": "span", "after": "div",
        }])
        result = BeautifulSoup(proposal["document"]["html"], "html.parser")
        self.assertEqual(result.select_one("#wrapper").name, "div")
        self.assertEqual(result.select_one("#wrapper")["class"], ["text-italic-on"])
        self.assertEqual(result.get_text(), BeautifulSoup(value["html"], "html.parser").get_text())
        self.assertEqual(document_issues(proposal["document"], {DIGEST}), [])
        self.assertEqual(value, original)

    def test_nested_wrappers_are_repaired_bottom_up_with_original_indices(self):
        proposal = preview_import(document(
            '<section><span id="outer"><span id="inner"><div><p>Text.</p>'
            '</div></span></span></section>'
        ))
        self.assertEqual([item["id"] for item in proposal["conversion"]["repairs"]],
                         ["outer", "inner"])
        self.assertEqual([item["element"] for item in proposal["conversion"]["repairs"]],
                         [1, 2])
        self.assertIn('<div id="outer"><div id="inner">', proposal["document"]["html"])

    def test_unsupported_ambiguity_is_not_automatically_reinterpreted(self):
        for html in (
            '<section><figcaption>Orphan caption</figcaption></section>',
            '<section><a href="https://example.org/"><h2>Linked heading</h2></a></section>',
            '<section><p><div>Nested block</div></p></section>',
            '<section><span><div><figcaption>Still orphan</figcaption></div></span></section>',
            '<section><strong><div>Styled block</div></strong></section>',
        ):
            with self.subTest(html=html), self.assertRaises(ValueError):
                preview_import(document(html))

    def test_conversion_never_uses_parser_cleanup_to_hide_unsafe_or_malformed_input(self):
        for tail in (
            '<script>bad()</script>', '<p onclick="bad()">Text.</p>',
            '<p><a href="javascript:bad()">Link</a></p>',
            '<img src="https://example.org/tracker.png"/>',
            '<p class="unsupported">Text.</p>', '<!-- hidden -->',
            '<p id="same">One</p><p id="same">Two</p>',
            '<p><strong>Unbalanced</p></strong>', '<p>Unclosed',
        ):
            value = document('<section><span><div>Legacy wrapper.</div></span>' + tail +
                             '</section>')
            with self.subTest(tail=tail), self.assertRaises(ValueError):
                preview_import(value)

    def test_approval_identity_covers_source_and_actual_conversion(self):
        value = document('<section><span><div>Text.</div></span></section>')
        base = preview_import(value)
        for changed in (
            {**value, "title": "Another title"},
            {**value, "metadata": {"language": "fr"}},
            {**value, "html": value["html"].replace("Text.", "Changed.")},
        ):
            self.assertNotEqual(preview_import(changed)["approval_digest"],
                                base["approval_digest"])


class SemanticImportPersistenceTests(TestCase):
    def setUp(self):
        foundation.DocumentEditTests.setUp(self)
        self.rendition.html = (
            '<section id="c1"><span id="legacy"><div><p>Original text.</p></div>'
            '</span></section>'
        )
        self.rendition.save(update_fields=["html"])

    def test_conversion_is_explicit_and_preserves_historical_edition(self):
        preview = preview_rendition_import(self.rendition)
        initial_count = DocumentDraftBase.objects.count()
        for approval in (None, "0" * 64):
            with self.subTest(approval=approval), self.assertRaises(DocumentEditConflict):
                create_draft(self.rendition, self.reviewer, conversion_approval=approval)
        self.assertEqual(DocumentDraftBase.objects.count(), initial_count)
        draft = create_draft(
            self.rendition, self.reviewer, conversion_approval=preview["approval_digest"]
        )
        self.assertEqual(draft.document, preview["document"])
        self.assertEqual(draft.evidence["generated_html"], self.rendition.html)
        self.assertEqual(draft.evidence["import"]["repairs"], preview["conversion"]["repairs"])
        self.assertTrue(draft.evidence["import"]["explicitly_approved"])
        row = save_revision(draft, self.reviewer, draft.document, 0)
        self.assertEqual(row.review, "partial")
        self.rendition.refresh_from_db()
        self.assertIn('<span id="legacy">', self.rendition.html)

    def test_changed_edition_invalidates_old_approval(self):
        preview = preview_rendition_import(self.rendition)
        self.rendition.html = self.rendition.html.replace("Original text.", "Another text.")
        self.rendition.save(update_fields=["html"])
        with self.assertRaises(DocumentEditConflict):
            create_draft(self.rendition, self.reviewer,
                         conversion_approval=preview["approval_digest"])

    def test_changed_snapshot_or_version_invalidates_approval_even_with_same_document(self):
        preview = preview_rendition_import(self.rendition)
        self.rendition.snapshot.manifest = {"pages": [], "changed": True}
        self.rendition.snapshot.save(update_fields=["manifest"])
        with self.assertRaises(DocumentEditConflict):
            create_draft(self.rendition, self.reviewer,
                         conversion_approval=preview["approval_digest"])
        refreshed = preview_rendition_import(self.rendition)
        self.rendition.format_version = "20"
        self.rendition.save(update_fields=["format_version"])
        with self.assertRaises(DocumentEditConflict):
            create_draft(self.rendition, self.reviewer,
                         conversion_approval=refreshed["approval_digest"])

    def test_readonly_command_previews_repairs_without_creating_records(self):
        initial_count = DocumentDraftBase.objects.count()
        output = io.StringIO()
        call_command("semantic_document_check", self.rendition.pk,
                     preview_conversion=True, stdout=output)
        result = json.loads(output.getvalue())["results"][0]
        self.assertTrue(result["compatible"])
        self.assertTrue(result["requires_approval"])
        self.assertEqual(result["conversion"]["repairs"][0]["id"], "legacy")
        self.assertEqual(DocumentDraftBase.objects.count(), initial_count)
        output = io.StringIO()
        call_command("semantic_document_check", self.rendition.pk,
                     preview_conversion=True, include_document=True, stdout=output)
        result = json.loads(output.getvalue())["results"][0]
        self.assertIn('<div id="legacy">', result["document"]["html"])
        self.assertEqual(DocumentDraftBase.objects.count(), initial_count)
