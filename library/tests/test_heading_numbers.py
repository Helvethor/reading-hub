import json
from copy import deepcopy

from bs4 import BeautifulSoup
from django.test import TestCase
from weasyprint import HTML

from library.correction_views import preview
from library.models import CorrectionFeedback
from library.services.correction_datasets import (
    commit_import,
    dataset,
    parse_dataset,
    prepare_import,
)
from library.services.correction_patterns import correction_patterns
from library.services.corrections import (
    SCHEMA_VERSION,
    apply_expected,
    apply_retained_correction,
    block_rows,
    digest,
    extraction,
    save_correction,
    validate_expected,
)
from library.services.fetch import Response
from library.services.storage import save_response
from library.sources.base import Part, Source
from library.sources.normalize import normalize
from library.tests import test_corrections
from library.tests.test_sources import article_html


class HeadingNumberTests(TestCase):
    def setUp(self):
        test_corrections.CorrectionTests.setUp(self)
        self.capture.response = save_response(
            Response(
                self.capture.url,
                article_html(
                    '<h4 id="num"><a name="roman">I</a></h4>'
                    '<a name="between"></a>'
                    '<h4 id="chapter"><em>Dogmatism</em> And Freedom</h4>'
                    '<p>Opening prose <a href="#num">number</a>, '
                    '<a href="#roman">old number</a>, <a href="#chapter">title</a>, '
                    '<a href="#between">between</a>.</p>'
                ),
                "text/html",
                {},
            ),
            self.capture.url,
        )
        self.capture.save(update_fields=["response"])
        self.source, self.part, self.body, _ = extraction(self.capture)
        rows = block_rows(self.body)
        self.number = next(row["index"] for row in rows if row["text"] == "I")
        self.heading = next(row["index"] for row in rows if row["text"] == "Dogmatism And Freedom")

    def expected(self, separator=". "):
        return {
            "heading_numbers": [
                {"number": self.number, "heading": self.heading, "separator": separator}
            ]
        }

    def test_preview_has_one_combined_heading_and_preserves_source_indices(self):
        before = str(self.body)
        result = preview(self.source, self.part, self.body, self.expected())
        parsed = BeautifulSoup(result["html"], "html.parser")
        combined = parsed.select_one(f'[data-preview-block="{self.heading}"]')
        self.assertIsNotNone(combined)
        self.assertEqual(combined.get_text("", strip=False), "I. Dogmatism And Freedom")
        self.assertIsNotNone(combined.find("em"))
        self.assertEqual(combined["data-preview-block"], str(self.heading))
        self.assertIsNotNone(combined.select_one(f'[data-preview-block="{self.number}"]'))
        self.assertFalse(any(row["title"] == "I" for row in result["structure"]["toc"]))
        self.assertEqual(str(self.body), before)
        self.assertEqual(len(result["blocks"]), len(block_rows(self.body)))

    def test_normalized_book_uses_reviewed_title_once_and_keeps_links(self):
        body = deepcopy(self.body)
        apply_expected(self.source, body, self.expected())
        part = Part(self.capture.url, "Dogmatism And Freedom")
        source = Source("Book", self.source.metadata, [part], True)
        html, structure = normalize([(part, body)], source, {})
        parsed = BeautifulSoup(html, "html.parser")
        headings = [
            node for node in parsed.select("h2,h3,h4,h5,h6") if "Dogmatism" in node.get_text()
        ]
        self.assertEqual(len(headings), 1)
        self.assertEqual(headings[0].name, "h2")
        self.assertEqual(headings[0].get_text(), "I. Dogmatism And Freedom")
        self.assertEqual(
            [row["title"] for row in structure["toc"] if "Dogmatism" in row["title"]],
            ["I. Dogmatism And Freedom"],
        )
        for anchor in parsed.select("a[href^='#']"):
            self.assertIsNotNone(parsed.find(id=anchor["href"][1:]))
        self.assertNotIn("data-preview-block", html)

    def test_subsection_relationship_does_not_remove_unrelated_chapter_heading(self):
        body = deepcopy(self.body)
        apply_expected(self.source, body, self.expected())
        part = Part(self.capture.url, "Different chapter")
        source = Source("Book", self.source.metadata, [part], True)
        html, _ = normalize([(part, body)], source, {})
        self.assertIn("Different chapter", html)

    def test_pdf_bookmark_uses_combined_title_once(self):
        body = deepcopy(self.body)
        apply_expected(self.source, body, self.expected())
        part = Part(self.capture.url, "Dogmatism And Freedom")
        source = Source("Book", self.source.metadata, [part], True)
        html, _ = normalize([(part, body)], source, {})
        document = HTML(string=html).render()

        def labels(bookmarks):
            return [
                text
                for bookmark in bookmarks
                for text in [bookmark[0], *labels(bookmark[2])]
            ]

        titles = labels(document.make_bookmark_tree())
        self.assertEqual(
            [title for title in titles if "Dogmatism" in title], ["I. Dogmatism And Freedom"]
        )
        self.assertNotIn("I", titles)

    def test_save_transfer_application_feedback_and_reset(self):
        correction = save_correction(
            self.capture, self.reviewer, self.expected(), 0, "Attach source number"
        )
        self.assertEqual(correction.schema_version, SCHEMA_VERSION)
        value = parse_dataset(json.dumps(dataset([correction])).encode())
        self.assertEqual(prepare_import(value)[0]["record"]["expected"], self.expected())
        commit_import(value, self.reviewer, {str(self.capture.pk): 1})
        self.assertEqual(
            CorrectionFeedback.objects.filter(operation=f"heading-number:{self.heading}").count(), 1
        )
        source, _, body, _ = extraction(self.capture)
        original_digest = digest(str(body))
        apply_retained_correction(
            source, body, self.capture.response, metadata=False, book_part=True
        )
        self.assertIn("I. Dogmatism", body.get_text())
        self.assertEqual(correction.original["body_digest"], original_digest)
        report = correction_patterns(correction.profile)
        self.assertTrue(any(group["operation"] == "heading:number" for group in report["groups"]))
        save_correction(self.capture, self.reviewer, {}, 2, "Detach source number")
        source, _, body, _ = extraction(self.capture)
        apply_retained_correction(
            source, body, self.capture.response, metadata=False, book_part=True
        )
        self.assertEqual(digest(str(body)), original_digest)

    def test_transfer_rejects_older_schema_and_missing_block_evidence(self):
        correction = save_correction(self.capture, self.reviewer, self.expected(), 0, "Attach")
        value = dataset([correction])
        value["dataset_schema"] = 7
        value["corrections"][0]["schema_version"] = 7
        with self.assertRaisesMessage(ValueError, "require correction schema 8"):
            prepare_import(value)
        value = dataset([correction])
        value["corrections"][0]["original"]["blocks"] = correction.original["blocks"][
            : self.heading
        ]
        with self.assertRaisesMessage(ValueError, "source block evidence"):
            prepare_import(value)

    def test_book_variant_reloads_exact_workspace_and_respects_explicit_heading_level(self):
        expected = self.expected()
        expected["blocks"] = [{"index": self.heading, "action": "h3"}]
        save_correction(self.capture, self.reviewer, expected, 0, "Attach and set heading level")
        source, _, body, _ = extraction(self.capture)
        body.find(["h2", "h3", "h4"]).decompose()
        apply_retained_correction(
            source, body, self.capture.response, metadata=False, book_part=True
        )
        part = Part(self.capture.url, "Dogmatism And Freedom")
        book = Source("Book", source.metadata, [part], True)
        html, structure = normalize([(part, body)], book, {})
        parsed = BeautifulSoup(html, "html.parser")
        joined = [h for h in parsed.select("h2,h3,h4") if "Dogmatism" in h.get_text()]
        self.assertEqual(len(joined), 1)
        self.assertEqual(joined[0].name, "h3")
        self.assertEqual(
            next(row["title"] for row in structure["toc"] if "Dogmatism" in row["title"]),
            "I. Dogmatism And Freedom",
        )

    def test_invalid_number_pairs_and_conflicting_exclusions_are_rejected(self):
        invalid = [
            [{"number": True, "heading": self.heading, "separator": ". "}],
            [{"number": 9999, "heading": self.heading, "separator": ". "}],
            [{"number": self.heading, "heading": self.heading, "separator": ". "}],
            [{"number": self.number, "heading": self.heading, "separator": "<script>"}],
            self.expected()["heading_numbers"] * 2,
        ]
        for pairs in invalid:
            with self.subTest(pairs=pairs), self.assertRaises(ValueError):
                validate_expected({"heading_numbers": pairs}, self.body, self.source)
        for index in (self.number, self.heading):
            expected = self.expected()
            expected["blocks"] = [{"index": index, "action": "exclude"}]
            with self.assertRaisesMessage(ValueError, "conflicting block edits"):
                validate_expected(expected, self.body, self.source)
        expected = self.expected()
        expected["blocks"] = [{"index": self.heading, "action": "h2"}]
        validate_expected(expected, self.body, self.source)

    def test_number_cannot_cross_prose_or_container_and_separator_does_not_double_punctuation(self):
        for markup in (
            "<div><h3>I</h3><p>Keep this prose</p><h3>Title</h3></div>",
            "<div><div><h3>I</h3></div><h3>Title</h3></div>",
            "<div><h3>I</h3><hr><h3>Title</h3></div>",
        ):
            body = BeautifulSoup(markup, "html.parser").div
            rows = block_rows(body)
            expected = {
                "heading_numbers": [
                    {"number": rows[0]["index"], "heading": rows[-1]["index"], "separator": ". "}
                ]
            }
            with self.assertRaises(ValueError):
                validate_expected(expected, body)
        for separator, output in ((". ", "I. Title"), (" ", "I Title"), (") ", "I) Title")):
            body = BeautifulSoup("<div><h3>I</h3><h3>Title</h3></div>", "html.parser").div
            expected = {"heading_numbers": [{"number": 0, "heading": 1, "separator": separator}]}
            validate_expected(expected, body)
            apply_expected(self.source, body, expected)
            self.assertEqual(body.h3.get_text(), output)
        body = BeautifulSoup("<div><h3>I.</h3><h3>Title</h3></div>", "html.parser").div
        apply_expected(
            self.source, body, {"heading_numbers": [{"number": 0, "heading": 1, "separator": ". "}]}
        )
        self.assertEqual(body.h3.get_text(), "I. Title")
        body = BeautifulSoup(
            "<div><h3>\n<a id='number'>I</a>\n</h3><h3>Title</h3></div>", "html.parser"
        ).div
        apply_expected(
            self.source, body, {"heading_numbers": [{"number": 0, "heading": 1, "separator": ". "}]}
        )
        self.assertEqual(body.h3.get_text(), "I. Title")
        self.assertIsNotNone(body.find(id="number"))
