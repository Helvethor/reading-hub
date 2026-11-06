import json
from copy import deepcopy

from bs4 import BeautifulSoup
from django.test import TestCase
from django.urls import reverse

from library.correction_views import preview
from library.services.correction_datasets import (
    commit_import,
    dataset,
    parse_dataset,
    prepare_import,
)
from library.services.corrections import (
    SCHEMA_VERSION,
    CorrectionConflict,
    apply_expected,
    apply_retained_correction,
    block_rows,
    editable_nodes,
    extraction,
    save_correction,
    validate_expected,
)
from library.services.fetch import Response
from library.services.note_corrections import reference_rows
from library.services.storage import save_response
from library.sources.normalize import make_id, normalize
from library.tests import test_corrections
from library.tests.test_sources import article_html


class NoteCorrectionTests(TestCase):
    setUp = test_corrections.CorrectionTests.setUp

    def source(self, markup=None):
        markup = markup or (
            '<p>Prose <a id="citation" href="#missing">[1]</a> and '
            '<a href="https://example.org/wrong">[1 again]</a></p>'
            '<p id="explanation">Note <em>text</em> '
            '<a href="#also-missing">return</a></p>'
        )
        self.capture.response = save_response(
            Response(self.capture.url, article_html(markup), "text/html", {}),
            self.capture.url,
        )
        self.capture.save(update_fields=["response"])
        self.s, self.p, self.b, _ = extraction(self.capture)
        nodes = editable_nodes(self.b)
        self.links = reference_rows(self.b, nodes)
        self.target = next(
            row["index"] for row in block_rows(self.b) if row["text"].startswith("Note")
        )
        self.expected = {
            "notes": [
                {
                    "reference": self.selection(0),
                    "target": self.target,
                    "backlink": self.selection(2) if len(self.links) > 2 else None,
                }
            ]
        }
        return self.expected

    def selection(self, index):
        return {key: self.links[index][key] for key in ("block", "link")}

    def formatted(self, expected):
        validate_expected(expected, self.b, self.s)
        apply_expected(self.s, self.b, expected)
        html, structure = normalize([(self.p, self.b)], self.s, {})
        return BeautifulSoup(html, "html.parser"), structure

    def test_explicit_pair_repairs_arbitrary_names_and_existing_backlink(self):
        expected = self.source()
        original = str(self.b)
        result = preview(self.s, self.p, self.b, expected)
        self.assertIn("<em>text</em>", result["html"])
        self.assertEqual(str(self.b), original)
        parsed, _ = self.formatted(expected)
        reference = next(a for a in parsed.select("a") if a.get_text() == "[1]")
        target = parsed.find(id=reference["href"][1:])
        self.assertIn("Note text", target.get_text(" ", strip=True))
        backlink = next(a for a in target.select("a") if a.get_text() == "return")
        self.assertEqual(backlink["href"], "#" + reference["id"])
        self.assertEqual(backlink["aria-label"], "Back to reference")
        self.assertEqual(len(target.select("a")), 1)
        self.assertIn('href="https://example.org/wrong"', str(parsed))
        self.assertEqual(parsed.get_text().count("Note"), 1)

    def test_multiple_references_get_distinct_return_links_without_losing_ids(self):
        expected = self.source(
            '<p><a href="#old">[1]</a> and <a href="#old">[2]</a></p>'
            '<p id="old">Note <a name="legacy"></a>text.</p>'
            '<p id="reviewed-reference-0">Retained collision.</p>'
        )
        expected["notes"].append(
            {
                "reference": self.selection(1),
                "target": self.target,
                "backlink": None,
            }
        )
        parsed, _ = self.formatted(expected)
        refs = [a for a in parsed.select("a") if a.get_text() in {"[1]", "[2]"}]
        self.assertNotEqual(refs[0]["id"], refs[1]["id"])
        self.assertEqual(refs[0]["href"], refs[1]["href"])
        target = parsed.find(id=refs[0]["href"][1:])
        self.assertEqual(len(target.select(".note-backlink")), 2)
        ids = [node["id"] for node in parsed.select("[id]")]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIsNotNone(parsed.find(id=make_id("c1", "legacy")))

    def test_target_without_id_gets_safe_fragment_and_list_item_is_supported(self):
        expected = self.source('<p><a href="#bad">[1]</a></p><ul><li>Note text</li></ul>')
        parsed, _ = self.formatted(expected)
        reference = parsed.select_one("p a")
        self.assertEqual(parsed.find(id=reference["href"][1:]).name, "li")
        self.assertEqual(len(parsed.select("li .note-backlink")), 1)

    def test_validation_rejects_bad_indices_types_duplicate_links_and_self_reference(self):
        expected = self.source()
        variants = [
            {"reference": {"block": True, "link": 0}},
            {"reference": {"block": 9999, "link": 0}},
            {"reference": {"block": self.links[0]["block"], "link": 9999}},
            {"target": True},
            {"target": 9999},
            {"target": self.links[0]["block"]},
            {"backlink": self.selection(1)},
            {"backlink": self.selection(0)},
        ]
        for patch in variants:
            value = deepcopy(expected)
            value["notes"][0].update(patch)
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                validate_expected(value, self.b, self.s)
        with self.assertRaisesMessage(ValueError, "distinct"):
            validate_expected({"notes": expected["notes"] * 2}, self.b, self.s)
        for invalid in ({}, [None], expected["notes"] * 201):
            with self.subTest(invalid=str(invalid)[:100]), self.assertRaises(ValueError):
                validate_expected({"notes": invalid}, self.b, self.s)

    def test_excluding_reference_target_or_container_conflicts(self):
        expected = self.source()
        for index in (self.links[0]["block"], self.target):
            with self.subTest(index=index), self.assertRaisesMessage(ValueError, "combine"):
                validate_expected(
                    {
                        **expected,
                        "blocks": [{"index": index, "action": "exclude"}],
                    },
                    self.b,
                    self.s,
                )

    def test_duplicate_source_ids_are_explicit_errors(self):
        expected = self.source(
            '<p><a href="#old">[1]</a></p><p id="duplicate">Note text</p>'
            '<p id="duplicate">Other text</p>'
        )
        with self.assertRaisesMessage(ValueError, "duplicate source ID"):
            validate_expected(expected, self.b, self.s)

    def test_workspace_stays_available_when_baseline_links_are_broken(self):
        expected = self.source()
        response = self.client.get(reverse("correction-workspace", args=[self.capture.pk]))
        self.assertRedirects(response, reverse("work-review"), fetch_redirect_response=False)
        result = preview(self.s, self.p, self.b, expected)
        self.assertIn("Back to reference", result["html"])
        self.assertFalse(self.capture.corrections.exists())

    def test_save_api_restores_saved_controls_and_reports_conflicts(self):
        expected = self.source()
        saved = save_correction(self.capture, self.reviewer, expected, 0, "Repair references")
        self.assertEqual(saved.revision, 1)
        self.assertEqual(saved.expected["notes"], expected["notes"])
        with self.assertRaises(CorrectionConflict):
            save_correction(self.capture, self.reviewer, expected, 0, "Stale")
        history = self.client.get(reverse("correction-revisions", args=[self.capture.pk]))
        self.assertContains(history, "Repair references")
        invalid = deepcopy(expected)
        invalid["notes"][0]["target"] = -1
        with self.assertRaises(ValueError):
            validate_expected(invalid, self.b, self.s)
        self.assertEqual(
            self.client.post(self.url, invalid, content_type="application/json").status_code, 410
        )
        self.assertEqual(self.capture.corrections.count(), 1)

    def test_note_repairs_combine_with_media_without_losing_reference(self):
        expected = self.source(
            '<img src="/image.png"><p>Caption <a href="#bad">[1]</a></p><p>Note text</p>'
        )
        rows = block_rows(self.b)
        expected["media"] = [
            {
                "image": next(row["index"] for row in rows if row["tag"] == "img"),
                "caption": self.links[0]["block"],
                "credit": None,
            }
        ]
        parsed, _ = self.formatted(expected)
        reference = parsed.select_one("figcaption a")
        self.assertIsNotNone(parsed.find(id=reference["href"][1:]))
        self.assertEqual(len(parsed.select(".note-backlink")), 1)

    def test_save_transfer_book_part_application_and_reset(self):
        expected = self.source()
        correction = save_correction(self.capture, self.reviewer, expected, 0, "Repair references")
        value = dataset([correction])
        self.assertEqual(value["dataset_schema"], SCHEMA_VERSION)
        self.assertEqual(
            prepare_import(parse_dataset(json.dumps(value).encode()))[0]["record"]["expected"],
            expected,
        )
        commit_import(value, self.reviewer, {str(self.capture.pk): 1})
        s, _, b, _ = extraction(self.capture)
        apply_retained_correction(s, b, self.capture.response, metadata=False, book_part=True)
        self.assertEqual(b.select_one('a[id="citation"]')["href"], "#explanation")
        with self.assertRaises(CorrectionConflict):
            save_correction(self.capture, self.reviewer, expected, 0, "Stale save")
        save_correction(self.capture, self.reviewer, {}, 2, "Restore original")
        s, _, b, _ = extraction(self.capture)
        apply_retained_correction(s, b, self.capture.response, metadata=False, book_part=True)
        self.assertEqual(b.select_one('a[id="citation"]')["href"], "#missing")

    def test_transfer_requires_schema_and_original_block_evidence(self):
        expected = self.source()
        correction = save_correction(self.capture, self.reviewer, expected, 0, "Repair")
        value = dataset([correction])
        value["dataset_schema"] = 6
        value["corrections"][0]["schema_version"] = 6
        with self.assertRaisesMessage(ValueError, "require correction schema 7"):
            prepare_import(value)
        value = dataset([correction])
        value["corrections"][0]["original"]["blocks"] = value["corrections"][0]["original"][
            "blocks"
        ][: self.target]
        with self.assertRaisesMessage(ValueError, "source block evidence"):
            prepare_import(value)
