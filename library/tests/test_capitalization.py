from bs4 import BeautifulSoup
from django.test import SimpleTestCase

from library.sources.adapters import Part, Source
from library.sources.capitalization import (
    author_names,
    normalize_capitalization,
    normalize_heading,
    normalize_subtitle,
)
from library.sources.normalize import normalize


class CapitalizationTests(SimpleTestCase):
    def test_subtitle_normalizes_mixed_capitals_without_rewriting_words(self):
        for text, expected in (
            ("BURNING QUESTIONS of our MOVEMENT", "Burning questions of our movement"),
            ("MARX and the USSR", "Marx and the USSR"),
            ("Burning Questions of Our Movement", "Burning Questions of Our Movement"),
            ("A normal subtitle", "A normal subtitle"),
            ("", ""),
        ):
            with self.subTest(text=text):
                self.assertEqual(normalize_subtitle(text), expected)

    def test_french_accents_are_restored_when_changing_case(self):
        examples = {
            "L'ETAT ET LA REVOLUTION": "L'état et la révolution",
            "L’ETAT ET LA REVOLUTION": "L’état et la révolution",
            "PREFACE A LA PREMIERE EDITION": "Préface a la première édition",
            "CHAPITRE II. LA SOCIETE ET L'ETAT": "Chapitre II. La société et l'état",
            "DETACHEMENTS SPECIAUX D'HOMMES ARMES": "Détachements spéciaux d'hommes armés",
            "LES BASES ECONOMIQUES DE LA DEMOCRATIE": "Les bases économiques de la démocratie",
            "LA CIA ET L'URSS": "La CIA et l'URSS",
            "L'ÉTAT ET LA RÉVOLUTION": "L'état et la révolution",
        }
        for language in ["fr", "fr-FR", "fr-CH", "FR"]:
            for text, expected in examples.items():
                with self.subTest(text=text, language=language):
                    self.assertEqual(normalize_capitalization(text, language=language), expected)

    def test_french_names_are_verified_but_other_languages_are_not_accented(self):
        self.assertEqual(
            normalize_capitalization("V. LENINE", author=True, language="fr"), "V. Lénine"
        )
        self.assertEqual(
            normalize_capitalization("LENINE ET PLEKHANOV", language="fr"),
            "Lénine et Plékhanov",
        )
        self.assertEqual(
            normalize_capitalization("REVOLUTION AND DEMOCRATIE", language="en"),
            "Revolution and democratie",
        )
        self.assertEqual(
            normalize_capitalization("V. LENINE", author=True, language="en"), "V. Lenine"
        )

    def test_ambiguous_spellings_and_existing_mixed_case_are_not_guessed(self):
        self.assertEqual(
            normalize_capitalization("A OU COTE DU SUR", language="fr"), "A ou cote du sur"
        )
        self.assertEqual(
            normalize_capitalization("L'etat et la revolution", language="fr"),
            "L'etat et la revolution",
        )

    def test_accents_preserve_inline_word_boundaries_and_links(self):
        soup = BeautifulSoup(
            '<h2 id="heading">L\'<em>ET</em>AT ET LA '
            '<a href="#note">REVOLU<strong>TION</strong></a></h2>',
            "html.parser",
        )
        normalize_heading(soup.h2, {}, language="fr")
        self.assertEqual(soup.h2.get_text(), "L'état et la révolution")
        self.assertEqual(soup.em.string, "ét")
        self.assertEqual(soup.a.strong.string, "tion")
        self.assertEqual(soup.a["href"], "#note")
        self.assertEqual(soup.h2["id"], "heading")
        original = str(soup)
        normalize_heading(soup.h2, {}, language="fr")
        self.assertEqual(str(soup), original)

    def test_sentence_case_preserves_known_acronyms_names_and_roman_numerals(self):
        examples = {
            "L'ETAT ET LA REVOLUTION": "L'etat et la revolution",
            "CHAPITRE IV. EXPLICATIONS D'ENGELS": "Chapitre IV. Explications d'Engels",
            "LA CIA, L'URSS ET L'OTAN": "La CIA, l'URSS et l'OTAN",
            "LÉNINE ET MARX EN EUROPE": "Lénine et Marx en Europe",
            "1917 : L'ÉTAT ET LA RÉVOLUTION": "1917 : L'état et la révolution",
            "INTRODUCTION: LA THÉORIE": "Introduction: La théorie",
            "II. LA COMMUNE DE PARIS": "II. La commune de Paris",
            "UE": "UE",
            "": "",
            "123": "123",
        }
        for source, expected in examples.items():
            with self.subTest(source=source):
                self.assertEqual(normalize_capitalization(source), expected)

    def test_author_names_initials_hyphens_apostrophes_and_particles(self):
        examples = {
            "V. LENINE": "V. Lenine",
            "K. MARX - F. ENGELS": "K. Marx - F. Engels",
            "ALAN WOODS": "Alan Woods",
            "JEAN-PAUL D'ALBERT": "Jean-Paul D'Albert",
            "SIMONE DE BEAUVOIR": "Simone de Beauvoir",
            "LUDWIG VAN BEETHOVEN": "Ludwig van Beethoven",
            "ÉMILE ZOLA": "Émile Zola",
        }
        for source, expected in examples.items():
            with self.subTest(source=source):
                self.assertEqual(normalize_capitalization(source, author=True), expected)

    def test_website_authors_are_normalized_to_lowercase(self):
        for source, expected in (
            ("defunke.de", "defunke.de"),
            ("DerFunke.de", "derfunke.de"),
            ("DERFUNKE.DE", "derfunke.de"),
            ("WWW.DerFunke.de", "www.derfunke.de"),
            ("Example.Co.UK", "example.co.uk"),
            ("Example.Technology", "example.technology"),
            ("M.Sivalingam", "M.Sivalingam"),
            ("V.I.Lenin", "V.I.Lenin"),
        ):
            with self.subTest(source=source):
                self.assertEqual(normalize_capitalization(source, author=True), expected)

    def test_mixed_case_is_unchanged(self):
        for text in ["eBook and iPhone", "Marx et l'UE", "Alan Woods", "de Gaulle", "McDonald"]:
            with self.subTest(text=text):
                self.assertEqual(normalize_capitalization(text), text)
                self.assertEqual(normalize_capitalization(text, author=True), text)

    def test_author_evidence_preserves_names_in_titles(self):
        names = author_names("Jon Lange")
        self.assertEqual(
            normalize_capitalization("INTRODUCTION BY JON LANGE", names=names),
            "Introduction by Jon Lange",
        )

    def test_heading_inline_markup_and_anchors_are_preserved(self):
        soup = BeautifulSoup(
            '<h2 id="section">LA <em>THÉORIE</em> DE <a href="#note">MARX</a>'
            "<sup>[1]</sup><!-- unchanged --></h2>",
            "html.parser",
        )
        normalize_heading(soup.h2, {})
        self.assertEqual(soup.h2.get_text(), "La théorie de Marx[1]")
        self.assertEqual(soup.em.string, "théorie")
        self.assertEqual(soup.a["href"], "#note")
        self.assertEqual(soup.h2["id"], "section")
        self.assertIn("<!-- unchanged -->", str(soup))

    def test_words_split_across_inline_elements_use_whole_heading_context(self):
        soup = BeautifulSoup("<h2><em>IN</em>TRODUCTION À LA THÉORIE</h2>", "html.parser")
        normalize_heading(soup.h2, {})
        self.assertEqual(soup.h2.get_text(), "Introduction à la théorie")
        self.assertEqual(soup.em.string, "In")

    def test_normalization_is_idempotent(self):
        for text in ["V. LENINE", "CHAPITRE II. LA CIA ET L'URSS"]:
            for author in [False, True]:
                first = normalize_capitalization(text, author=author)
                self.assertEqual(normalize_capitalization(first, author=author), first)

    def test_book_parts_chapters_and_toc_share_the_same_case_and_ids(self):
        part = Part(
            "https://www.marxists.org/test/chapter.htm",
            "CHAPITRE II. LA THÉORIE DE MARX",
            "LA THÉORIE",
        )
        source = Source("Book", {"author": "Karl Marx"}, [part], True)
        body = BeautifulSoup(
            '<div><h3 id="original"><em>MARX ET ENGELS</em></h3>'
            '<p>UNCHANGED PARAGRAPH.</p><a href="#original">Section link</a></div>',
            "html.parser",
        ).div
        html, structure = normalize([(part, body)], source, {})
        parsed = BeautifulSoup(html, "html.parser")
        self.assertEqual(
            [entry["title"] for entry in structure["toc"]],
            ["La théorie", "Chapitre II. La théorie de Marx", "Marx et Engels"],
        )
        for entry in structure["toc"]:
            self.assertEqual(parsed.find(id=entry["id"]).get_text(), entry["title"])
        self.assertIsNotNone(parsed.find(id=parsed.a["href"][1:]))
        self.assertIn("UNCHANGED PARAGRAPH.", html)
