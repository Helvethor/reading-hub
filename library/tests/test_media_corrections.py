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
    apply_expected,
    apply_retained_correction,
    block_rows,
    extraction,
    save_correction,
    validate_expected,
)
from library.services.fetch import Response
from library.services.storage import save_response
from library.tests import test_corrections
from library.tests.test_sources import article_html


class MediaCorrectionTests(TestCase):
    setUp = test_corrections.CorrectionTests.setUp

    def source(self, extra=None):
        extra = extra or (
            '<p><a href="/image"><img src="/picture.png" alt="Picture"></a></p>'
            '<p id="caption">Original <em>caption</em> <a href="#note">[1]</a></p>'
            '<p id="credit">Photo: <a href="https://example.org/artist">Artist</a></p>'
            '<p id="note">Note text.</p>'
        )
        self.capture.response = save_response(
            Response(
                self.capture.url,
                article_html(extra),
                "text/html",
                {},
            ),
            self.capture.url,
        )
        self.capture.save()
        self.s, self.p, self.b, _ = extraction(self.capture)
        self.rows = block_rows(self.b)
        self.image = next(r["index"] for r in self.rows if r["tag"] == "img")
        self.caption = next(
            r["index"]
            for r in self.rows
            if r["tag"] in {"p", "figcaption"} and r["text"].startswith("Original")
        )
        self.credit = next((r["index"] for r in self.rows if r["text"].startswith("Photo:")), None)
        return {"media": [{"image": self.image, "caption": self.caption, "credit": self.credit}]}

    def test_preview_preserves_text_links_targets_and_original_body(self):
        expected = self.source()
        original = str(self.b)
        validate_expected(expected, self.b, self.s)
        html = preview(self.s, self.p, self.b, expected)["html"]
        result = BeautifulSoup(html, "html.parser")
        figure = result.select_one("figure")
        self.assertIsNotNone(figure)
        self.assertEqual(len(figure.select("figcaption")), 1)
        self.assertEqual(len(figure.select("figcaption em")), 1)
        self.assertEqual(len(figure.select("figcaption a")), 2)
        self.assertEqual(len(figure.select("p.media-credit")), 1)
        self.assertEqual(result.get_text().count("Original"), 1)
        self.assertEqual(result.get_text().count("Photo:"), 1)
        self.assertEqual(str(self.b), original)
        self.assertEqual(block_rows(self.b), self.rows)

    def test_save_dataset_roundtrip_and_reset(self):
        expected = self.source()
        correction = save_correction(self.capture, self.reviewer, expected, 0, "Associate caption")
        value = dataset([correction])
        self.assertEqual(value["dataset_schema"], SCHEMA_VERSION)
        plan = prepare_import(parse_dataset(json.dumps(value).encode()))
        self.assertEqual(plan[0]["record"]["expected"], expected)
        commit_import(value, self.reviewer, {str(self.capture.pk): 1})
        self.assertEqual(self.capture.corrections.first().expected, expected)
        legacy = deepcopy(value)
        legacy["dataset_schema"] = 5
        legacy["corrections"][0]["schema_version"] = 5
        with self.assertRaisesMessage(ValueError, "require correction schema 6"):
            prepare_import(parse_dataset(json.dumps(legacy).encode()))
        shortened = deepcopy(value)
        shortened["corrections"][0]["original"]["blocks"] = self.rows[: self.image]
        with self.assertRaisesMessage(ValueError, "lacks corresponding"):
            prepare_import(parse_dataset(json.dumps(shortened).encode()))
        response = self.client.get(reverse("correction-workspace", args=[self.capture.pk]))
        self.assertContains(response, "Images, captions and credits")
        self.assertContains(response, "Associate image with caption")
        save_correction(self.capture, self.reviewer, {}, 2, "Restore source layout")
        s, _, b, _ = extraction(self.capture)
        apply_retained_correction(s, b, self.capture.response, metadata=True)
        self.assertFalse(b.select("figure"))

    def test_media_applies_to_book_parts_when_metadata_is_not_applied(self):
        expected = self.source()
        save_correction(self.capture, self.reviewer, expected, 0, "Caption")
        s, _, b, _ = extraction(self.capture)
        apply_retained_correction(s, b, self.capture.response, metadata=False, book_part=True)
        self.assertEqual(len(b.select("figure")), 1)
        self.assertIn("Original", b.select_one("figcaption").get_text())

    def test_rejects_invalid_duplicate_or_conflicting_indices_and_blocks(self):
        expected = self.source()
        variants = [
            {"image": True, "caption": self.caption, "credit": None},
            {"image": self.image, "caption": None, "credit": None},
            {"image": self.caption, "caption": self.image, "credit": None},
            {"image": self.image, "caption": self.caption, "credit": self.caption},
            {"image": self.image, "caption": 99999, "credit": None},
            {"image": self.image, "caption": self.image, "credit": None},
        ]
        for association in variants:
            with self.subTest(association=association), self.assertRaises(ValueError):
                validate_expected({"media": [association]}, self.b, self.s)
        with self.assertRaisesMessage(ValueError, "used once"):
            validate_expected({"media": expected["media"] * 2}, self.b, self.s)
        for index in (self.image, self.caption, self.credit):
            with self.subTest(index=index), self.assertRaisesMessage(ValueError, "combine"):
                validate_expected(
                    {**expected, "blocks": [{"index": index, "action": "exclude"}]}, self.b, self.s
                )

    def test_rejects_cross_container_and_cross_heading_image_divider(self):
        for middle in ("<hr>", "<h3>Boundary</h3>", '<img src="/other.png">'):
            expected = self.source(
                '<p><img src="/picture.png"></p>' + middle + "<p>Original caption</p>"
            )
            with self.subTest(middle=middle), self.assertRaisesMessage(ValueError, "cross"):
                validate_expected(expected, self.b, self.s)
        expected = self.source(
            '<div><img src="/picture.png"><p>Inside</p></div><p>Original caption</p>'
        )
        with self.assertRaisesMessage(ValueError, "container"):
            validate_expected(expected, self.b, self.s)

    def test_existing_single_image_figure_and_caption_are_preserved(self):
        expected = self.source(
            '<figure><img src="/picture.png"><figcaption id="caption">Original caption</figcaption>'
            "</figure><p>Photo: Artist</p>"
        )
        validate_expected(expected, self.b, self.s)
        apply_expected(self.s, self.b, expected)
        self.assertEqual(len(self.b.select("figure")), 1)
        self.assertEqual(len(self.b.select("figcaption")), 1)
        self.assertEqual(len(self.b.select("#caption")), 1)

    def test_credit_only_leaves_unselected_caption_in_place(self):
        expected = self.source()
        expected["media"][0]["caption"] = None
        validate_expected(expected, self.b, self.s)
        apply_expected(self.s, self.b, expected)
        self.assertNotIn("Original", self.b.select_one("figcaption").get_text())
        self.assertIn("Photo:", self.b.select_one("figcaption").get_text())

    def test_identical_images_cannot_hide_a_crossing_boundary(self):
        expected = self.source('<img src="/same.png"><img src="/same.png"><p>Original caption</p>')
        with self.assertRaisesMessage(ValueError, "another image"):
            validate_expected(expected, self.b, self.s)

    def test_identical_caption_siblings_use_the_selected_node(self):
        expected = self.source(
            '<p>Original caption</p><hr><img src="/picture.png"><p>Original caption</p>'
        )
        expected["media"][0]["caption"] = next(
            row["index"] for row in reversed(self.rows) if row["text"] == "Original caption"
        )
        validate_expected(expected, self.b, self.s)
        apply_expected(self.s, self.b, expected)
        self.assertEqual(self.b.select_one("figcaption").get_text(), "Original caption")
        self.assertEqual(self.b.get_text().count("Original caption"), 2)

    def test_existing_caption_with_paragraphs_preserves_target_and_markup(self):
        expected = self.source(
            '<figure><img src="/picture.png"><figcaption id="original-caption">'
            "<p>Original <em>caption</em></p></figcaption></figure>"
        )
        expected["media"][0]["caption"] = next(
            row["index"] for row in self.rows if row["tag"] == "figcaption"
        )
        validate_expected(expected, self.b, self.s)
        apply_expected(self.s, self.b, expected)
        self.assertEqual(len(self.b.select("figcaption")), 1)
        self.assertIsNotNone(self.b.select_one("figcaption #original-caption p em"))

    def test_separate_images_and_saved_assets_keep_order_and_count(self):
        from library.sources.normalize import normalize

        expected = self.source(
            '<img src="/one.png"><p>Original first caption</p>'
            '<img src="/two.png"><p>Second caption</p>'
        )
        second_image = next(
            row["index"] for row in self.rows if row["tag"] == "img" and row["index"] != self.image
        )
        second_caption = next(row["index"] for row in self.rows if row["text"] == "Second caption")
        expected["media"].append(
            {
                "image": second_image,
                "caption": second_caption,
                "credit": None,
            }
        )
        validate_expected(expected, self.b, self.s)
        apply_expected(self.s, self.b, expected)
        from urllib.parse import urljoin

        assets = {
            urljoin(self.capture.url, path): {"digest": digest}
            for path, digest in [("/one.png", "a" * 64), ("/two.png", "b" * 64)]
        }
        html, _ = normalize([(self.p, self.b)], self.s, assets)
        result = BeautifulSoup(html, "html.parser")
        self.assertEqual(len(result.select("figure")), 2)
        self.assertEqual(
            [image["src"] for image in result.select("img")],
            [f"/assets/{'a' * 64}/", f"/assets/{'b' * 64}/"],
        )
        self.assertEqual(
            [node.get_text() for node in result.select("figcaption")],
            ["Original first caption", "Second caption"],
        )

    def test_preview_endpoint_is_read_only_and_save_requires_valid_associations(self):
        expected = self.source()
        endpoint = reverse("correction-update", args=[self.capture.pk])
        response = self.client.post(
            endpoint,
            json.dumps(
                {
                    "action": "preview",
                    "expected": expected,
                    "revision": 0,
                    "reason": "Caption",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("<figcaption>", response.json()["html"])
        self.assertFalse(self.capture.corrections.exists())
        expected["media"][0]["caption"] = self.image
        response = self.client.post(
            endpoint,
            json.dumps(
                {
                    "action": "save",
                    "expected": expected,
                    "revision": 0,
                    "reason": "Caption",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.capture.corrections.exists())
