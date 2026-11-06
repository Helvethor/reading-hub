from copy import deepcopy
from unittest.mock import patch

from bs4 import BeautifulSoup
from django.test import TestCase
from django.urls import reverse

from library.correction_views import preview
from library.services.corrections import (
    apply_expected,
    baseline,
    block_rows,
    editable_nodes,
    extraction,
    save_correction,
)
from library.services.errors import ImportFailure
from library.services.fetch import Response
from library.services.preview_blocks import mark_blocks
from library.services.source_excerpts import evidence
from library.services.storage import save_response
from library.sources.normalize import normalize
from library.tests import test_corrections
from library.tests.test_sources import article_html


class PreviewBlockTests(TestCase):
    setUp = test_corrections.CorrectionTests.setUp

    def source(self, markup):
        self.capture.response = save_response(
            Response(self.capture.url, article_html(markup), "text/html", {}),
            self.capture.url,
        )
        self.capture.save(update_fields=["response"])
        self.s, self.p, self.b, _ = extraction(self.capture)
        self.rows = block_rows(self.b)

    def index(self, text, tag="p"):
        return next(row["index"] for row in self.rows if row["tag"] == tag and row["text"] == text)

    def test_mapping_is_preview_only_preserves_baseline_and_source_indices(self):
        self.source('<p id="source">First <em>word</em>.</p><p>Second.</p><hr>')
        original = baseline(self.s, self.b)
        first = self.index("First word .")
        result = preview(self.s, self.p, self.b, {})
        parsed = BeautifulSoup(result["html"], "html.parser")
        self.assertEqual(parsed.select_one(f'[data-preview-block="{first}"]').name, "p")
        self.assertEqual(baseline(self.s, self.b), original)
        self.assertEqual(
            [{key: row[key] for key in ("index", "tag", "text")} for row in result["blocks"]],
            self.rows,
        )
        html, _ = normalize([(self.p, deepcopy(self.b))], self.s, {})
        self.assertNotIn("data-preview-block", html)
        self.assertNotIn("tabindex", html)

    def test_excerpt_mapping_uses_original_indices_without_changing_correction_baseline(self):
        self.source("<p>Keep <em>emphasis</em></p><blockquote><p>Quoted</p></blockquote>")
        original = baseline(self.s, self.b)
        source, part, body, soup = extraction(self.capture, excerpt_mapping=True)
        self.assertEqual(baseline(source, body), original)
        self.assertNotIn("data-internal-excerpt", str(soup))
        self.assertNotIn("data-internal-excerpt", str(body))
        entry = {**self.capture.response, "url": self.capture.url}
        rows = evidence(entry)["blocks"]
        quote = next(row["index"] for row in rows if row["tag"] == "blockquote")
        result = preview(source, part, body, {})
        parsed = BeautifulSoup(result["html"], "html.parser")
        self.assertEqual(
            parsed.select_one("blockquote")["data-excerpt-block"], str(quote)
        )
        self.assertEqual(
            parsed.select_one("blockquote p")["data-excerpt-block"], str(quote)
        )
        html, _ = normalize([(part, deepcopy(body))], source, {})
        self.assertNotIn("data-excerpt-block", html)

    def test_excerpt_mapping_survives_draft_preview_but_not_exclusions_or_source_spoofing(self):
        self.source(
            '<p data-excerpt-block="999" data-internal-excerpt-block="999">Keep</p>'
            "<p>Remove</p>"
        )
        source, part, body, _ = extraction(self.capture, excerpt_mapping=True)
        expected = {"blocks": [
            {"index": self.index("Keep"), "action": "h3"},
            {"index": self.index("Remove"), "action": "exclude"},
        ]}
        result = preview(source, part, body, expected)
        parsed = BeautifulSoup(result["html"], "html.parser")
        self.assertIsNotNone(parsed.select_one("h2[data-excerpt-block]"))
        self.assertNotIn("999", result["html"])
        self.assertNotIn("Remove", parsed.get_text())

    def test_integrated_excerpt_controls_share_preview_and_do_not_nest_forms_or_csrf_tokens(self):
        response = self.client.get(reverse("correction-workspace", args=[self.capture.pk]))
        self.assertRedirects(response, reverse("work-review"), fetch_redirect_response=False)
        self.assertFalse(self.capture.corrections.exists())
        response = self.client.post(
            reverse("source-excerpts", args=[self.capture.pk]),
            {"name": "Obsolete controls"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 410)

    def test_exclusion_uses_existing_saved_block_semantics(self):
        self.source("<p>Keep</p><p>Remove</p>")
        index = self.index("Remove")
        expected = {"blocks": [{"index": index, "action": "exclude"}]}
        result = preview(self.s, self.p, self.b, expected)
        parsed = BeautifulSoup(result["html"], "html.parser")
        self.assertIsNone(parsed.select_one(f'[data-preview-block="{index}"]'))
        self.assertNotIn("Remove", parsed.get_text())
        self.assertEqual(result["blocks"][index]["text"], "Remove")
        correction = save_correction(self.capture, self.reviewer, expected, 0, "Exclude")
        self.assertEqual(correction.expected, expected)
        self.assertNotIn("data-preview-block", str(correction.original))
        body = deepcopy(self.b)
        apply_expected(self.s, body, expected)
        html, _ = normalize([(self.p, body)], self.s, {})
        self.assertNotIn("Remove", html)
        self.assertNotIn("data-preview-block", html)

    def test_nested_source_scope_reports_container_without_merging_blocks(self):
        self.source("<blockquote><p>Quoted</p></blockquote><p>After</p>")
        child = self.index("Quoted")
        parent = self.index("Quoted", "blockquote")
        result = preview(self.s, self.p, self.b, {})
        self.assertIn(parent, result["blocks"][child]["parents"])
        parsed = BeautifulSoup(result["html"], "html.parser")
        self.assertIsNotNone(
            parsed.select_one(
                f'blockquote[data-preview-block="{parent}"] p[data-preview-block="{child}"]'
            )
        )
        removed = preview(
            self.s,
            self.p,
            self.b,
            {
                "blocks": [{"index": parent, "action": "exclude"}],
            },
        )
        self.assertNotIn("Quoted", BeautifulSoup(removed["html"], "html.parser").get_text())

    def test_mapping_cannot_be_supplied_by_source_attributes(self):
        self.source('<p data-preview-block="999" tabindex="0" onclick="alert(1)">Text</p>')
        result = preview(self.s, self.p, self.b, {})
        self.assertNotIn('data-preview-block="999"', result["html"])
        self.assertNotIn("onclick", result["html"])
        self.assertNotIn("tabindex", result["html"])

    def test_image_placeholder_divider_and_heading_keep_source_scope(self):
        self.source('<h3>Title</h3><img src="/image.png" alt="Illustration"><hr><p>Text</p>')
        result = preview(self.s, self.p, self.b, {})
        parsed = BeautifulSoup(result["html"], "html.parser")
        for row in self.rows:
            if row["tag"] in {"img", "hr", "h3"}:
                self.assertIsNotNone(parsed.select_one(f'[data-preview-block="{row["index"]}"]'))
        self.assertIsNotNone(parsed.select_one(".missing-image[data-preview-block]"))

    def test_unwrapped_text_is_selectable_without_changing_original_rows(self):
        self.source('<p>Prose</p><a href="https://example.org">Unwrapped</a>')
        original = str(self.b)
        row = next(row for row in self.rows if row["tag"] == "unwrapped text")
        result = preview(self.s, self.p, self.b, {})
        self.assertIn(f'data-preview-block="{row["index"]}"', result["html"])
        removed = preview(
            self.s,
            self.p,
            self.b,
            {
                "blocks": [{"index": row["index"], "action": "exclude"}],
            },
        )
        self.assertNotIn("Unwrapped", BeautifulSoup(removed["html"], "html.parser").get_text())
        self.assertEqual(str(self.b), original)

    def test_mapping_unchanged_by_heading_operations_and_identical_paragraphs(self):
        self.source("<p>Same</p><p>Same</p>")
        matches = [row["index"] for row in self.rows if row["text"] == "Same"]
        result = preview(
            self.s,
            self.p,
            self.b,
            {
                "blocks": [{"index": matches[1], "action": "h4"}],
            },
        )
        parsed = BeautifulSoup(result["html"], "html.parser")
        self.assertEqual(parsed.select_one(f'[data-preview-block="{matches[0]}"]').name, "p")
        self.assertEqual(parsed.select_one(f'[data-preview-block="{matches[1]}"]').name, "h4")

    def test_workspace_and_preview_api_expose_mapping_without_writes(self):
        self.source("<p>Selectable</p>")
        response = self.client.get(reverse("correction-workspace", args=[self.capture.pk]))
        self.assertRedirects(response, reverse("work-review"), fetch_redirect_response=False)
        result = preview(self.s, self.p, self.b, {})
        self.assertIn("parents", result["blocks"][0])
        response = self.client.post(
            self.url, {"action": "preview", "expected": {}}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 410)
        self.assertFalse(self.capture.corrections.exists())

    def test_private_mapping_never_survives_normal_reading_normalization(self):
        self.source("<p>Text</p>")
        body = deepcopy(self.b)
        mark_blocks(body)
        self.assertTrue(
            any("_reviewed_source_block" in node.__dict__ for node in editable_nodes(body))
        )
        html, _ = normalize([(self.p, body)], self.s, {})
        self.assertNotIn("data-preview-block", html)

    def test_source_selection_available_when_initial_preview_fails(self):
        self.source("<p>Repairable source</p>")
        with patch("library.correction_views.preview", side_effect=ImportFailure("Broken link")):
            response = self.client.get(reverse("correction-workspace", args=[self.capture.pk]))
        self.assertRedirects(response, reverse("work-review"), fetch_redirect_response=False)
        self.assertTrue(block_rows(self.b))
        self.assertEqual(block_rows(self.b)[0]["index"], self.rows[0]["index"])
        self.assertFalse(self.capture.corrections.exists())

    def test_form_guidance_uses_named_help_popovers_without_hiding_status(self):
        self.source("<p>Selectable</p>")
        response = self.client.get(reverse("correction-workspace", args=[self.capture.pk]))
        self.assertRedirects(response, reverse("work-review"), fetch_redirect_response=False)
        result = preview(self.s, self.p, self.b, {})
        self.assertIn("Selectable", result["html"])
        self.assertFalse(self.capture.corrections.exists())
