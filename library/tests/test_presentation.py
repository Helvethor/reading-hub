import io
from copy import deepcopy

from bs4 import BeautifulSoup
from django.test import SimpleTestCase, TestCase
from pypdf import PdfReader

from library.correction_views import preview
from library.services.correction_datasets import dataset, prepare_import
from library.services.corrections import (
    apply_expected,
    apply_retained_correction,
    editable_nodes,
    extraction,
    save_correction,
    validate_expected,
)
from library.services.document_metadata import metadata_rows
from library.services.presentation import inline_alignment, source_text
from library.sources.base import Part, Source
from library.sources.normalize import normalize
from library.tests import test_corrections


class PresentationTests(SimpleTestCase):
    def setUp(self):
        self.body = BeautifulSoup(
            '<div><p style="color:red;text-align:center">Before <em>linked '
            '<a href="https://example.org/">words</a></em> after.</p>'
            '<h3 style="text-align:right">UPPER HEADING</h3>'
            '<blockquote><p>Nested text.</p></blockquote><hr></div>', "html.parser"
        ).div
        self.part = Part("https://www.marxists.org/archive/test.htm", "Test")
        self.source = Source("Test", {"language": "en"}, [self.part], False)

    def test_source_alignment_is_safe_normalized_and_populates_preview(self):
        original = str(self.body)
        result = preview(self.source, self.part, self.body, {})
        self.assertEqual(result["blocks"][0]["align"], "center")
        self.assertEqual(result["blocks"][1]["align"], "right")
        parsed = BeautifulSoup(result["html"], "html.parser")
        self.assertIn("text-align-center", parsed.p["class"])
        self.assertNotIn("style=", result["html"])
        self.assertNotIn("color:red", result["html"])
        self.assertEqual(str(self.body), original)
        for css, expected in (
            ("text-align:left;text-align:right!important;text-align:center", "right"),
            ("text-align:url(javascript:alert(1))", ""),
            ("text-align: CENTER", "center"),
            ("text-align:center; background:url(https://tracker.invalid)", "center"),
        ):
            node = BeautifulSoup(f'<p style="{css}">Text</p>', "html.parser").p
            self.assertEqual(inline_alignment(node), expected)

    def test_block_alignment_styles_and_text_ranges_preserve_markup_and_evidence(self):
        text = source_text(self.body.p)
        expected = {"presentation": [
            {"index": 0, "align": "justify", "styles": {"bold": True},
             "ranges": [{"start": 7, "end": 18, "text": text[7:18],
                         "styles": {"underline": True, "italic": False}}]},
            {"index": 1, "align": "left", "styles": {"strikethrough": True}},
        ]}
        validate_expected(expected, self.body, self.source)
        result = preview(self.source, self.part, self.body, expected)
        parsed = BeautifulSoup(result["html"], "html.parser")
        self.assertIn("text-align-justify", parsed.p["class"])
        self.assertIn("text-bold-on", parsed.p["class"])
        self.assertEqual("".join(node.get_text() for node in parsed.select(".text-underline-on")),
                         text[7:18])
        self.assertIn("text-italic-off", parsed.select_one(".text-underline-on")["class"])
        self.assertIsNotNone(parsed.p.em.a)
        self.assertNotIn("data-preview-block", normalize(
            [(self.part, deepcopy(self.body))], self.source, {}
        )[0])
        self.assertNotIn("text-bold-on", str(self.body))
        body = deepcopy(self.body)
        apply_expected(self.source, body, expected)
        html, _ = normalize([(self.part, body)], self.source, {})
        self.assertIn("text-bold-on", html)
        self.assertIn('href="https://example.org/"', html)
        self.assertNotIn("data-preview", html)

    def test_overlapping_ranges_apply_last_explicit_style_without_text_loss(self):
        text = source_text(self.body.p)
        expected = {"presentation": [{"index": 0, "ranges": [
            {"start": 0, "end": 12, "text": text[:12], "styles": {"bold": True}},
            {"start": 5, "end": 15, "text": text[5:15],
             "styles": {"bold": False, "superscript": True, "subscript": False}},
        ]}]}
        result = preview(self.source, self.part, self.body, expected)
        parsed = BeautifulSoup(result["html"], "html.parser")
        self.assertEqual(parsed.p.get_text(), text)
        self.assertIn("text-bold-off", parsed.select_one(".text-superscript-on")["class"])

    def test_off_overrides_semantic_decorations_without_losing_unselected_styles(self):
        body = BeautifulSoup(
            '<div><p><u>Underline <strong>bold</strong> text</u> and '
            '<sup>raised text</sup>.</p></div>', "html.parser"
        ).div
        text = source_text(body.p)
        expected = {"presentation": [{"index": 0, "styles": {"bold": False}, "ranges": [
            {"start": 10, "end": 14, "text": text[10:14], "styles": {"underline": False}},
            {"start": 24, "end": 30, "text": text[24:30], "styles": {"superscript": False}},
        ]}]}
        validate_expected(expected, body, self.source)
        parsed = BeautifulSoup(
            preview(self.source, self.part, body, expected)["html"], "html.parser"
        )
        self.assertEqual(parsed.p.get_text(), text)
        self.assertIsNone(parsed.u)
        self.assertIsNone(parsed.sup)
        self.assertTrue(all("text-bold-off" in node["class"]
                            for node in parsed.strong.select("span")))
        self.assertIn("bold", "".join(n.get_text() for n in parsed.select(".text-underline-off")))
        self.assertIn(
            "Underline", "".join(n.get_text() for n in parsed.select(".text-underline-on"))
        )

    def test_preview_mapping_tracks_original_characters_after_heading_case_changes(self):
        result = preview(self.source, self.part, self.body, {})
        heading = result["blocks"][1]
        self.assertEqual(heading["source_text"], "UPPER HEADING")
        self.assertEqual(heading["text_map"], list(range(len("UPPER HEADING"))))
        self.assertEqual(
            BeautifulSoup(result["html"], "html.parser").h2.get_text(), "Upper heading"
        )

    def test_invalid_evidence_and_unsupported_styles_are_rejected(self):
        bad = [
            [{"index": True, "align": "left"}],
            [{"index": 0, "align": "start"}],
            [{"index": 0, "styles": {"color": "red"}}],
            [{"index": 0, "styles": {"bold": "true"}}],
            [{"index": 0, "styles": {"superscript": True, "subscript": True}}],
            [{"index": 0, "ranges": [{"start": 0, "end": 3, "text": "bad",
                                     "styles": {"bold": True}}]}],
            [{"index": 0, "ranges": [{"start": -1, "end": 3, "text": "bad",
                                     "styles": {"bold": True}}]}],
            [{"index": 0, "align": "left"}, {"index": 0, "align": "right"}],
        ]
        nodes = editable_nodes(self.body)
        bad.append([{"index": next(i for i, n in enumerate(nodes) if n.name == "hr"),
                     "align": "left"}])
        for value in bad:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_expected({"presentation": value}, self.body, self.source)
        with self.assertRaisesMessage(ValueError, "excluded"):
            validate_expected({"blocks": [{"index": 0, "action": "exclude"}],
                               "presentation": [{"index": 0, "align": "left"}]},
                              self.body, self.source)

    def test_complete_language_names_for_reader_and_pdf(self):
        for code, label in (("en", "English"), ("fr", "French"), ("de", "German"),
                            ("pt-br", "Brazilian Portuguese"), ("und", "Unknown language")):
            self.assertIn(("Language", label), metadata_rows({"language": code}))


class RetainedPresentationTests(TestCase):
    setUp = test_corrections.CorrectionTests.setUp

    def test_source_bound_presentation_saves_transfers_and_applies_offline(self):
        from library.models import CorrectionFeedback

        source, part, body, _ = extraction(self.capture)
        node = next((i, n) for i, n in enumerate(editable_nodes(body)) if n.name == "p")
        index, paragraph = node
        text = source_text(paragraph)
        expected = {"presentation": [{"index": index, "align": "right",
                     "styles": {"bold": True}, "ranges": [
                         {"start": 0, "end": 4, "text": text[:4], "styles": {"italic": True}}
                     ]}]}
        row = save_correction(self.capture, self.reviewer, expected, 0, "Reviewed styling")
        self.assertEqual(row.schema_version, 10)
        self.assertTrue(CorrectionFeedback.objects.filter(
            correction=row, operation=f"presentation:{index}", decision="correction"
        ).exists())
        bundle = dataset([row])
        self.assertEqual(prepare_import(bundle)[0]["record"]["expected"], expected)
        bundle["corrections"][0]["schema_version"] = 9
        with self.assertRaisesMessage(ValueError, "schema 10"):
            prepare_import(bundle)
        apply_retained_correction(source, body, self.capture.response, metadata=True)
        html, _ = normalize([(part, body)], source, {})
        self.assertIn("text-align-right", html)
        self.assertIn("text-bold-on", html)
        self.assertIn("text-italic-on", html)
        source, part, body, _ = extraction(self.capture)
        apply_retained_correction(source, body, self.capture.response, metadata=False)
        chapter_html, _ = normalize([(part, body)], source, {})
        self.assertIn("text-align-right", chapter_html)
        self.assertIn("text-italic-on", chapter_html)

    def test_presentation_is_shared_by_pdf_and_normalized_reader(self):
        from library.models import Document, Rendition, Snapshot
        from library.services.pdf import STYLES, render_pdf

        document = Document.objects.create(url="https://marxist.com/style-test/")
        snapshot = Snapshot.objects.create(document=document, digest="a" * 64, manifest={})
        version = Rendition.objects.create(
            document=document, snapshot=snapshot, title="Styled document", identity="b"*64,
            metadata={"language": "en"}, structure={"toc": []},
            html='<p class="text-align-center text-bold-on">Centered styled text</p>',
            stylesheet=(STYLES / "reader.css").read_text(), output_digest="c"*64,
        )
        output = io.BytesIO()
        render_pdf(version, output)
        pdf = PdfReader(output)
        self.assertIn("English", pdf.pages[0].extract_text())
        self.assertNotIn("Centered styled text", pdf.pages[0].extract_text())
        self.assertIn("Centered styled text", pdf.pages[1].extract_text())
