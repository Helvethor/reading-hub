import json
from pathlib import Path

from bs4 import BeautifulSoup
from django.conf import settings
from django.test import SimpleTestCase

from library.services.book_views import marker_text, publication_toc, publication_view


class BookViewTests(SimpleTestCase):
    def test_shared_editor_publication_hierarchy_and_numbering_examples(self):
        path = Path(settings.BASE_DIR) / "frontend/fixtures/book-views.json"
        cases = json.loads(path.read_text())
        for fixture in cases:
            with self.subTest(html=fixture["html"]):
                soup = BeautifulSoup(fixture["html"], "html.parser")
                entries = publication_toc(soup)
                self.assertEqual([
                    [entry[key] for key in ("title", "level", "style", "number", "marker")]
                    for entry in entries
                ], fixture["entries"])
                self.assertTrue(all(soup.find(id=entry["id"]) is not None for entry in entries))

    def test_heading_ids_are_collision_free_and_projection_does_not_change_prose(self):
        html = '<h2 data-toc-style="decimal">First</h2><p id="heading-1">Body</p>'
        projection = publication_view(html)
        soup = BeautifulSoup(projection["content_html"], "html.parser")
        self.assertEqual(projection["entries"][0]["id"], "heading-1-h")
        self.assertEqual(soup.h2["data-reading-marker"], "1. ")
        self.assertEqual(soup.get_text(), BeautifulSoup(html, "html.parser").get_text())
        self.assertNotIn("data-reading-marker", html)

    def test_series_follow_reorder_and_none_and_restart_under_each_parent(self):
        markup = '<section id="a" data-toc-style="decimal"><h2>A</h2>' \
            '<h3 data-toc-style="lower-alpha">Nested A</h3><p>Body</p></section>' \
            '<section id="b" data-toc-style="decimal"><h2>B</h2>' \
            '<h3 data-toc-style="lower-alpha">Nested B</h3><p>Body</p></section>'
        soup = BeautifulSoup(markup, "html.parser")
        soup.select_one("#a").insert_before(soup.select_one("#b").extract())
        entries = publication_toc(soup)
        self.assertEqual([(entry["title"], entry["marker"]) for entry in entries],
                         [("B", "1."), ("Nested B", "a."), ("A", "2."), ("Nested A", "a.")])
        del soup.select_one("#b")["data-toc-style"]
        entries = publication_toc(soup)
        self.assertEqual([entry["marker"] for entry in entries], ["", "a.", "1.", "a."])

    def test_all_marker_styles_and_rollover(self):
        for style, number, expected in (
            ("none", 1, ""), ("disc", 1, "\u2022"), ("decimal", 12, "12."),
            ("upper-alpha", 26, "Z."), ("upper-alpha", 27, "AA."),
            ("lower-alpha", 703, "aaa."), ("upper-roman", 49, "XLIX."),
            ("lower-roman", 1999, "mcmxcix."), ("upper-roman", 4000, "4000."),
        ):
            self.assertEqual(marker_text(style, number), expected)
        with self.assertRaisesMessage(ValueError, "Unsupported ToC"):
            publication_view('<h2 data-toc-style="invalid">Title</h2>')
