from copy import deepcopy

from bs4 import BeautifulSoup
from django.test import SimpleTestCase

from library.services.editor_structure import legacy_article_root, section_structure
from library.services.semantic_documents import canonical_document


class ArticleStructureTests(SimpleTestCase):
    def test_article_role_and_local_title_survive_semantic_validation(self):
        value = canonical_document(
            {
                "version": 1,
                "title": "Anthology",
                "metadata": {},
                "html": '<section id="story" data-section-role="article" '
                'data-section-label="Retained title"><p>Opening.</p></section>',
            }
        )
        self.assertIn('data-section-label="Retained title"', value["html"])
        for attribute in (
            'data-section-role="unknown"',
            'data-section-role="chapter" data-section-label="Section title"',
            'data-section-role="article" data-section-label=""',
            'data-section-role="article" data-section-label="x&#10;y"',
        ):
            with self.subTest(attribute=attribute), self.assertRaises(ValueError):
                canonical_document(
                    {
                        "version": 1,
                        "title": "Anthology",
                        "metadata": {},
                        "html": f'<section id="story" {attribute}><p>Opening.</p></section>',
                    }
                )

    def test_legacy_article_compatibility_is_bounded_and_preserves_explicit_roles(self):
        original = {
            "book": False,
            "parts": [{"id": "article", "title": "Retained identity", "role": "chapter"}],
        }
        html = '<section id="article"><p>Opening.</p><h2>First section</h2></section>'
        soup = BeautifulSoup(html, "html.parser")
        role = legacy_article_root(soup, original, {"work_type": "article"})
        self.assertIsNotNone(role)
        structure = section_structure(
            soup,
            original,
            document_title="Current article title",
            metadata={"work_type": "article"},
        )
        self.assertEqual(structure["parts"][0]["role"], "article")
        self.assertEqual(structure["parts"][0]["title"], "Current article title")
        self.assertEqual(soup.section["data-section-role"], "article")
        self.assertEqual(original["parts"][0]["role"], "chapter")

        for markup, metadata, book in (
            (
                '<section id="article" data-section-role="chapter"><h2>Explicit</h2></section>',
                {"work_type": "article"},
                False,
            ),
            (html, {"work_type": "essay"}, False),
            (html, {"work_type": "article"}, True),
        ):
            with self.subTest(markup=markup, metadata=metadata, book=book):
                source = deepcopy(original)
                source["book"] = book
                source_soup = BeautifulSoup(markup, "html.parser")
                self.assertIsNone(legacy_article_root(source_soup, source, metadata))

    def test_article_local_title_is_not_replaced_by_its_first_heading(self):
        soup = BeautifulSoup(
            '<section id="anthology"><h2>Book title</h2>'
            '<section id="article" data-section-role="article" '
            'data-section-label="Retained local title">'
            "<p>Opening.</p><h2>First subsection</h2></section></section>",
            "html.parser",
        )
        original = {
            "book": True,
            "parts": [{"id": "anthology", "title": "Book title", "role": "chapter"}],
        }
        structure = section_structure(
            soup,
            original,
            {"book": True},
            document_title="Enclosing book title",
            metadata={"work_type": "book"},
        )
        article = next(part for part in structure["parts"] if part["id"] == "article")
        self.assertEqual(article["title"], "Retained local title")
        self.assertEqual(article["role"], "article")
        self.assertEqual(article["parent"], "anthology")

    def test_article_without_owned_title_evidence_fails_instead_of_falling_back_to_heading(self):
        soup = BeautifulSoup(
            '<section id="anthology"><h2>Book title</h2>'
            '<section id="article" data-section-role="article">'
            "<h2>First subsection</h2></section></section>",
            "html.parser",
        )
        with self.assertRaisesMessage(ValueError, "needs its own retained title"):
            section_structure(
                soup,
                {"book": True, "parts": []},
                {"book": True},
                document_title="Enclosing book title",
                metadata={"work_type": "book"},
            )
