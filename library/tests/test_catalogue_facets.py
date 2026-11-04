import io
from dataclasses import replace
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings

from library.models import CatalogueEntry, CrawlCapture
from library.services.catalogue import configured_sites, save_entry
from library.services.fetch import Response
from library.services.storage import save_response
from library.sources.base import parse_html
from library.sources.catalogue import CatalogueLink
from library.sources.classification import (
    clean_attribution,
    clean_authors,
    infer_topics,
    is_date,
    normalize_language,
    split_authors,
)
from library.tests import test_pipeline
from library.tests.test_sources import ARTICLE, article_html
from profiles.marxist.adapters import source_language
from profiles.marxist.catalogue import MarxistCatalogue
from profiles.marxist.site import PROFILE


class ClassificationTests(SimpleTestCase):
    def test_additional_language_evidence_and_archive_sections(self):
        base = "https://www.marxists.org"
        for path, expected in (
            ("/reference/subject/philosophy/works/fr/derrida.htm", "en"),
            ("/glossary/people/t/r.htm", "en"),
            ("/thai/archive/work.htm", "th"),
            ("/mongolian/nomyn-san.htm", "mn"),
            ("/kurdi/lenin/lenin.htm", "ku"),
            ("/makedonski/biblioteka.htm", "mk"),
            ("/nepali/nekapa/1949/09/ghoshanapatr.htm", "ne"),
            ("/xlang/selected-marxists.htm", "und"),
        ):
            self.assertEqual(source_language(None, base + path), expected)
        for html, expected in (
            (b'<html lang="und"><meta name="DC.Language" content="French">', "fr"),
            (b'<html xml:lang="de">', "de"),
            (b'<meta http-equiv="Content-Language" content="es">', "es"),
            (
                b'<script type="application/ld+json">{"@type":"https://schema.org/Article",'
                b'"inLanguage":{"name":"Portuguese"}}</script>',
                "pt",
            ),
        ):
            self.assertEqual(
                source_language(parse_html(html), base + "/xlang/example.htm"), expected
            )
        self.assertEqual(
            source_language(parse_html(b'<html lang="fr">'), base + "/reference/test.htm"), "fr"
        )

    def test_other_explicit_metadata_fallbacks_do_not_guess_authors_or_dates(self):
        html = article_html().replace(
            b'<meta name="author" content="Test Author">',
            b'<meta name="citation_author" content="Marx, Karl">'
            b'<meta name="citation_author" content="Engels, Friedrich">'
            b'<meta itemprop="datePublished" content="1848-02-21">'
            b'<script type="application/ld+json">{"@type":"ScholarlyArticle",'
            b'"about":{"name":"Labour movement"}}</script>',
        )
        link = MarxistCatalogue.metadata(parse_html(html), ARTICLE)
        self.assertEqual(link.authors, ("Marx, Karl", "Engels, Friedrich"))
        self.assertEqual(link.published, "1848-02-21")
        self.assertIn("Labour movement", link.topics)
        html = article_html().replace(b'name="author"', b'name="DC.Creator"')
        self.assertEqual(MarxistCatalogue.metadata(parse_html(html), ARTICLE).author, "Test Author")

    def test_archive_first_publication_is_not_written_or_online_edition_date(self):
        from profiles.marxist.archive import date_facts, publication_date

        for text, expected in (
            ("Written: 1847. First published: In London, 1848. Online edition: 2004.", "1848"),
            ("Written: 1847. Online edition: 2004.", ""),
            ("First published: 1848; revised 1850. Source: Archive.", ""),
            (
                "First Publication: Albania, 7-VII-1977. Digitalization: Anonymous. "
                "Online Edition: April 2004.",
                "1977",
            ),
        ):
            soup = parse_html(f'<p class="information">{text}</p>'.encode())
            self.assertEqual(publication_date(soup), expected)
        facts = date_facts(
            parse_html(
                b'<p class="information">Written: 1847. First published: London, 1848. '
                b"Online edition: 2004.</p>"
            )
        )
        self.assertEqual(
            [(fact["type"], fact["value"]) for fact in facts],
            [("written", "1847"), ("publication", "1848"), ("online_edition", "2004")],
        )
        self.assertIn("First published: London, 1848", facts[1]["evidence"])

    def test_byline_dates_navigation_and_related_authors_do_not_override_real_metadata(self):
        soup = parse_html(
            article_html()
            .replace(
                b'<meta name="author" content="Test Author">',
                b'<meta name="Author" content="12.02.2025">',
            )
            .replace(
                b"<body>",
                b'<body><nav><span class="author">Menu Author</span></nav>'
                b'<div class="related-posts"><span class="author">Related Author</span>'
                b'<time datetime="1999-01-01"></time></div>'
                b'<span class="author">12.02.2025</span>'
                b'<span class="byline">By Genuine Author, Berne, 12.02.2025</span>'
                b'<time itemprop="datePublished" datetime="2025-02-12"></time>',
            )
        )
        link = MarxistCatalogue.metadata(soup, ARTICLE)
        self.assertEqual(link.author, "Genuine Author")
        self.assertEqual(link.authors, ("Genuine Author",))
        self.assertEqual(link.published, "2025-02-12")

    def test_language_evidence_is_normalized_and_listing_page_does_not_leak_language(self):
        self.assertEqual(source_language(parse_html(b'<html lang="pt_BR">'), ARTICLE), "pt")
        self.assertEqual(
            source_language(parse_html(b'<meta property="og:locale" content="fr_FR">'), ARTICLE),
            "fr",
        )
        self.assertEqual(source_language(None, "https://communisme.ch/de/test/"), "fr")
        self.assertEqual(source_language(None, "https://www.marxists.org/russkij/test.htm"), "ru")
        soup = parse_html(b'<html lang="fr"><h2><a href="/de/test/">German text</a></h2></html>')
        self.assertEqual(list(MarxistCatalogue.links(soup, "https://communisme.ch/fr/")), [])

    def test_dates_and_source_affiliations_are_not_coauthors(self):
        for value in (
            "Noël Jaquet, Berne, 12.02.2025",
            "Noël Jaquet, 2025-02-12",
            "Noël Jaquet, 12 février 2025",
            "Noël Jaquet, February 12, 2025",
        ):
            self.assertEqual(split_authors(value), ["Noël Jaquet"])
        self.assertEqual(
            clean_authors(["Jorge Martín", "marxist.com (04.06.2025)"]),
            ["Jorge Martín"],
        )
        self.assertEqual(split_authors("ICR Canada, 29.11.2024"), ["ICR Canada"])
        self.assertEqual(split_authors("12.02.2025"), [])
        self.assertEqual(clean_attribution("October 15, 2025"), "")
        self.assertFalse(is_date("Karl May"))
        self.assertFalse(is_date("31.02.2025"))
        self.assertEqual(split_authors("Karl May, Rosa Luxemburg"), ["Karl May", "Rosa Luxemburg"])
        self.assertEqual(normalize_language("pt_BR"), "pt")
        for variant in ("en-US", "en-gb", "fr-CA", "fr-FR", "de-CH", "zh-Hans"):
            self.assertEqual(normalize_language(variant), variant.split("-", 1)[0])
        self.assertEqual(normalize_language("Not a language"), "")

    def test_multiple_author_separators_and_editorial_roles(self):
        self.assertEqual(
            split_authors("Karl Marx et Friedrich Engels; Rosa Luxemburg & Karl Marx"),
            ["Karl Marx", "Friedrich Engels", "Rosa Luxemburg"],
        )
        self.assertEqual(split_authors("Caspar Oertli, rédaction"), ["Caspar Oertli"])
        self.assertEqual(split_authors("Caspar Oertli (JS Zurich)"), ["Caspar Oertli"])
        self.assertEqual(clean_attribution("Caspar Oertli, Zürich"), "Caspar Oertli")
        self.assertEqual(
            split_authors("Jane Smith (RCI, London); Alex Doe (Marxist.com, Zürich)"),
            ["Jane Smith", "Alex Doe"],
        )
        self.assertEqual(split_authors("Marx, Engels"), ["Marx", "Engels"])

    def test_known_places_are_affiliations_not_coauthors(self):
        for place in ("Berne", "Bern", "BERNE", "Genève", "GENEVE", "Zürich", "Paris"):
            with self.subTest(place=place):
                self.assertEqual(split_authors(f"Dario Dietsch, {place}"), ["Dario Dietsch"])
        self.assertEqual(
            split_authors("Dario Dietsch, Berne; Jane Smith, Genève"),
            ["Dario Dietsch", "Jane Smith"],
        )
        self.assertEqual(
            split_authors("Jack London, George Orwell"), ["Jack London", "George Orwell"]
        )
        self.assertEqual(
            split_authors("Dario Dietsch, Unlistedtown"), ["Dario Dietsch", "Unlistedtown"]
        )
        self.assertEqual(
            clean_authors(["Doe, Jane", "John Smith, Berne"]), ["Doe, Jane", "John Smith"]
        )
        self.assertEqual(clean_authors(["Dario Dietsch", "Berne"]), ["Dario Dietsch"])
        self.assertEqual(clean_authors(["Berne"]), ["Berne"])

    def test_location_vocabulary_is_validated_and_configurable(self):
        for places in ("Berne", ("",), (1,)):
            with self.subTest(places=places), self.assertRaises(ImproperlyConfigured):
                replace(PROFILE, author_locations=places).validate()
        with patch(
            "library.profile.get_profile",
            return_value=replace(PROFILE, author_locations=("Testville",)),
        ):
            self.assertEqual(split_authors("Jane Smith, Testville"), ["Jane Smith"])
            self.assertEqual(split_authors("Jane Smith, Berne"), ["Jane Smith", "Berne"])

    def test_literal_accent_insensitive_topic_rules_and_exact_threshold(self):
        rules = {"Labour": ("grève", "union"), "War": ("war",)}
        self.assertEqual(infer_topics("GREVE: union", rules), ["Labour"])
        self.assertEqual(infer_topics("A union", rules), [])
        self.assertEqual(infer_topics("war war", rules), ["War"])
        self.assertEqual(infer_topics("award warlike", rules), [])
        self.assertEqual(infer_topics("war", {"War": ("war", "WAR")}), [])
        self.assertEqual(infer_topics("war war", {}), [])

    def test_invalid_topic_rules_are_rejected(self):
        for rules in ([], {"": ("test",)}, {"Topic": ()}, {"Topic": "word"}, {"Topic": (1,)}):
            with self.subTest(rules=rules), self.assertRaises(ImproperlyConfigured):
                replace(PROFILE, topic_rules=rules).validate()

    def test_topics_use_body_not_navigation_and_related_content(self):
        profile = replace(PROFILE, topic_rules={"War": ("war",), "Labour": ("union",)})
        soup = parse_html(
            article_html(
                "<p>union union</p><nav>war war</nav>"
                '<div class="related-posts">war war</div><script>war war</script>'
            )
        )
        with patch("profiles.marxist.catalogue.get_profile", return_value=profile):
            link = MarxistCatalogue.metadata(soup, ARTICLE)
        self.assertEqual(link.topics, ("Labour",))

    def test_swiss_appended_articles_are_not_classified(self):
        profile = replace(PROFILE, topic_rules={"War": ("war",)})
        soup = parse_html(
            article_html(
                "<p>Unrelated text.</p><hr><h1>Another article</h1><p>war war</p>",
                host="communisme.ch",
            )
        )
        with patch("profiles.marxist.catalogue.get_profile", return_value=profile):
            link = MarxistCatalogue.metadata(soup, "https://communisme.ch/fr/test/")
        self.assertEqual(link.topics, ())

    def test_multiple_source_categories_and_inferred_topics_are_combined(self):
        soup = parse_html(
            article_html("<p>war war</p>").replace(
                b"</head>",
                b'<meta property="article:section" content="History">'
                b'<meta property="article:section" content="Theory"></head>',
            )
        )
        profile = replace(PROFILE, topic_rules={"War": ("war",)})
        with patch("profiles.marxist.catalogue.get_profile", return_value=profile):
            link = MarxistCatalogue.metadata(soup, ARTICLE)
        self.assertEqual(link.topics, ("History", "Theory", "War"))

    def test_structured_coauthors_preserve_surname_comma(self):
        soup = parse_html(
            article_html().replace(
                b'<meta name="author" content="Test Author">',
                b'<script type="application/ld+json">{"@type":"Article",'
                b'"author":[{"name":"Doe, Jane"},{"name":"John Smith"}]}</script>',
            )
        )
        link = MarxistCatalogue.metadata(soup, ARTICLE)
        self.assertEqual(link.authors, ("Doe, Jane", "John Smith"))

    def test_archive_body_is_classified(self):
        soup = parse_html(
            b'<html><body><h1>Author</h1><p class="titre">Book</p><p>union union</p></body></html>'
        )
        profile = replace(PROFILE, topic_rules={"Labour": ("union",)})
        with patch("profiles.marxist.catalogue.get_profile", return_value=profile):
            link = MarxistCatalogue.metadata(
                soup, "https://www.marxists.org/francais/test/book.htm"
            )
        self.assertEqual(link.topics, ("Labour",))


@override_settings(ALLOWED_HOSTS=["testserver"])
class FacetViewTests(TestCase):
    def test_website_authors_are_grouped_case_insensitively(self):
        save_entry(
            self.site,
            CatalogueLink(ARTICLE + "site-a", "First", True, author="defunke.de"),
        )
        save_entry(
            self.site,
            CatalogueLink(ARTICLE + "site-b", "Second", True, author="DerFunke.de"),
        )
        response = self.client.get("/catalogue/?group=author&then=")
        website_groups = [
            node for node in response.context["tree"]["children"] if "funke.de" in node["label"]
        ]
        self.assertEqual(
            [(node["label"], node["count"]) for node in website_groups],
            [("defunke.de", 1), ("derfunke.de", 1)],
        )

    def test_language_aliases_resolve_fallbacks_without_crashing_catalogue(self):
        from django.conf.locale import LANG_INFO

        from library.catalogue_views import language_label

        for code in LANG_INFO:
            with self.subTest(code=code):
                self.assertEqual(language_label(code), language_label(code.split("-", 1)[0]))
        entry = CatalogueEntry.objects.get()
        entry.language = "zh-cn"
        entry.save()
        self.assertContains(self.client.get("/catalogue/?group=language"), language_label("zh-cn"))

    def test_coherence_command_reports_dates_without_modifying_metadata(self):
        call_command("check_catalogue_metadata", stdout=io.StringIO())
        entry = CatalogueEntry.objects.get()
        entry.authors = ["12.02.2025"]
        entry.save()
        with self.assertRaises(CommandError):
            call_command("check_catalogue_metadata", stdout=io.StringIO(), stderr=io.StringIO())
        entry.refresh_from_db()
        self.assertEqual(entry.authors, ["12.02.2025"])

    def setUp(self):
        self.site = configured_sites().get(host="communistusa.org")
        save_entry(
            self.site,
            CatalogueLink(
                ARTICLE,
                "Joint article",
                True,
                author="Karl Marx and Friedrich Engels",
                published="2026-10-16T10:00:00Z",
                topic="History, Theory",
                authors=("Karl Marx", "Friedrich Engels"),
                topics=("History", "Theory"),
            ),
        )

    def test_article_occurs_under_each_author_and_topic_without_duplicate_records(self):
        response = self.client.get("/catalogue/?group=author&then=topic")
        self.assertNotContains(response, "Joint article")
        self.assertEqual(response.context["page"].paginator.count, 1)
        self.assertEqual(CatalogueEntry.objects.count(), 1)
        tree = response.context["tree"]
        self.assertEqual(
            [node["label"] for node in tree["children"]], ["Friedrich Engels", "Karl Marx"]
        )
        for node in tree["children"]:
            self.assertEqual(node["count"], 1)
            branch = self.client.get(node["url"])
            self.assertEqual(
                [child["label"] for child in branch.context["tree"]["children"]],
                ["History", "Theory"],
            )
            for topic in branch.context["tree"]["children"]:
                leaf = self.client.get(topic["url"] + "&partial=1")
                self.assertContains(leaf, "Joint article", count=1)

    def test_year_and_month_filter_independently_and_together(self):
        for index, date in enumerate(("2025-10-01", "2026-09-01", "", "2026", "20261")):
            save_entry(
                self.site,
                CatalogueLink(ARTICLE + str(index), f"Other {index}", True, published=date),
            )
        for query, count in (
            ("year=2026", 3),
            ("month=10", 2),
            ("year=2026&month=10", 1),
            ("year=2024&month=10", 0),
        ):
            response = self.client.get("/catalogue/?" + query)
            self.assertEqual(response.context["page"].paginator.count, count, query)
        response = self.client.get("/catalogue/?year=2024&month=10")
        self.assertContains(response, '<option value="2024" selected>')
        self.assertContains(response, '<option value="10" selected>October')

    def test_year_month_hierarchy_and_descending(self):
        save_entry(
            self.site, CatalogueLink(ARTICLE + "second", "Earlier", True, published="2025-09-01")
        )
        save_entry(self.site, CatalogueLink(ARTICLE + "unknown", "Unknown", True))
        response = self.client.get("/catalogue/?group=year&then=month")
        children = response.context["tree"]["children"]
        self.assertEqual([node["label"] for node in children], ["2025", "2026", "Unknown year"])
        branch = self.client.get(children[1]["url"])
        self.assertEqual(branch.context["tree"]["children"][0]["label"], "2026-10")
        self.assertContains(self.client.get(children[2]["url"]), "Unknown month")
        response = self.client.get("/catalogue/?group=month&then=&direction=desc")
        self.assertEqual(response.context["tree"]["children"][1]["label"], "2026-10")

    def test_date_filters_survive_pagination_and_invalid_input_is_explicit(self):
        save_entry(
            self.site, CatalogueLink(ARTICLE + "second", "Other", True, published="2026-10-02")
        )
        with patch(
            "library.catalogue_views.get_profile", return_value=replace(PROFILE, page_size=1)
        ):
            response = self.client.get("/catalogue/?year=2026&month=10&group=author&then=topic")
            self.assertContains(response, "year=2026&amp;month=10")
            self.assertEqual(response.context["page"].paginator.count, 2)
        for query in ("year=bad", "month=13", "month=1", "year=2026%27"):
            response = self.client.get("/catalogue/?" + query)
            self.assertContains(response, "Unknown catalogue display option")

    def test_global_counts_and_branch_pagination_do_not_hide_articles(self):
        for index in range(25):
            save_entry(
                self.site,
                CatalogueLink(
                    ARTICLE + str(index),
                    f"Extra article {index:02}",
                    True,
                    author="Other Author",
                    published="2026-10-01",
                ),
            )
        response = self.client.get("/catalogue/?group=source&then=")
        node = response.context["tree"]["children"][0]
        self.assertEqual(node["count"], 26)
        self.assertNotContains(response, "Joint article")
        branch = self.client.get(node["url"] + "&partial=1")
        self.assertEqual(branch.context["page"].paginator.count, 26)
        self.assertEqual(len(branch.context["page"]), 20)
        self.assertContains(branch, "Page 1 of 2")
        next_page = self.client.get(node["url"] + "&partial=1&page=2")
        self.assertEqual(len(next_page.context["page"]), 6)
        self.assertContains(next_page, "Joint article")
        self.assertNotContains(next_page, "<html")
        self.assertContains(next_page, 'name="csrfmiddlewaretoken"')

    def test_invalid_branch_is_reported_and_filters_apply_to_global_totals(self):
        for path in ('"author"', '{"bad":1}', "[1]", '["a","b","c"]'):
            response = self.client.get("/catalogue/", {"branch": path, "partial": "1"})
            self.assertContains(response, "Invalid catalogue branch")
        response = self.client.get("/catalogue/?year=2025&group=author")
        self.assertEqual(response.context["total_count"], 0)
        self.assertEqual(response.context["tree"]["children"], [])

    def test_language_grouping_sorting_filtering_and_pagination(self):
        entry = CatalogueEntry.objects.get()
        entry.language = "fr"
        entry.save()
        save_entry(self.site, CatalogueLink(ARTICLE + "en", "English text", True, language="en"))
        save_entry(self.site, CatalogueLink(ARTICLE + "unknown", "Unknown text", True))
        response = self.client.get("/catalogue/?group=language&then=&order=language")
        self.assertEqual(
            [node["label"] for node in response.context["tree"]["children"]],
            ["English (en)", "French (fr)", "Unknown language"],
        )
        self.assertEqual([e.language for e in response.context["page"]], ["", "en", "fr"])
        response = self.client.get("/catalogue/?language=fr&group=language&then=&order=language")
        self.assertEqual(response.context["total_count"], 1)
        leaf = self.client.get(response.context["tree"]["children"][0]["url"])
        self.assertContains(leaf, "Joint article")
        self.assertContains(leaf, "language=fr")
        response = self.client.get("/catalogue/?language=und")
        self.assertEqual(response.context["total_count"], 1)
        self.assertContains(
            self.client.get("/catalogue/?language=bad%20value"), "Unknown catalogue"
        )

    def test_language_variants_share_group_and_filter_including_legacy_entries(self):
        entry = CatalogueEntry.objects.get()
        entry.language = "en-us"
        entry.save()
        save_entry(
            self.site,
            CatalogueLink(ARTICLE + "uk", "English text UK", True, language="en-gb"),
        )
        save_entry(
            self.site,
            CatalogueLink(ARTICLE + "french", "French text", True, language="fr-ca"),
        )

        response = self.client.get("/catalogue/?group=language&then=&order=language")
        labels = [node["label"] for node in response.context["tree"]["children"]]
        self.assertEqual(labels, ["English (en)", "French (fr)"])

        response = self.client.get("/catalogue/?language=en-US&group=language&then=")
        self.assertEqual(response.context["total_count"], 2)
        self.assertEqual({entry.language for entry in response.context["page"]}, {"en"})

    def test_checked_metadata_clears_invalid_author_but_listing_hints_do_not(self):
        save_entry(
            self.site,
            CatalogueLink(ARTICLE, "Joint article", True, author="12.02.2025"),
            checked=True,
        )
        entry = CatalogueEntry.objects.get()
        self.assertEqual(entry.author, "")
        self.assertEqual(entry.authors, [])
        self.assertContains(self.client.get("/catalogue/?group=author&then="), "RCA")

    def test_sparse_listing_cannot_erase_multiple_topics(self):
        save_entry(self.site, CatalogueLink(ARTICLE, "Joint article", True))
        self.assertEqual(CatalogueEntry.objects.get().topics, ["History", "Theory"])

    def test_existing_city_author_does_not_create_branch_and_rebuild_repairs_it(self):
        entry = CatalogueEntry.objects.get()
        entry.author = "Dario Dietsch, Berne"
        entry.authors = ["Dario Dietsch", "Berne"]
        entry.save()
        response = self.client.get("/catalogue/?group=author&then=")
        self.assertEqual(
            [node["label"] for node in response.context["tree"]["children"]], ["Dario Dietsch"]
        )
        call_command("rebuild_catalogue_metadata", stdout=io.StringIO())
        entry.refresh_from_db()
        self.assertEqual(entry.authors, ["Dario Dietsch"])
        self.assertEqual(entry.author, "Dario Dietsch")

    def test_checked_article_can_remove_outdated_topics(self):
        save_entry(self.site, CatalogueLink(ARTICLE, "Joint article", True), checked=True)
        entry = CatalogueEntry.objects.get()
        self.assertEqual(entry.topics, [])
        self.assertEqual(entry.topic, "")
        response = self.client.get("/catalogue/?group=topic&then=")
        self.assertEqual(response.context["tree"]["children"][0]["label"], "Unknown topic")


class CachedClassificationTests(TestCase):
    setUp = test_pipeline.PipelineTests.setUp
    fetch = test_pipeline.PipelineTests.fetch
    import_article = test_pipeline.PipelineTests.import_article

    def test_rebuild_replaces_und_and_uses_language_on_nonwork_captures(self):
        site = configured_sites().get(host="www.marxists.org")
        directory = "https://www.marxists.org/xlang/index.htm"
        url = "https://www.marxists.org/reference/archive/hegel/works/hp/plato.htm"
        entry = CatalogueEntry.objects.create(site=site, url=url, title="Plato", language="und")
        index = CatalogueEntry.objects.create(
            site=site, url=directory, title="Index", language="und"
        )
        html = b'<html lang="fr"><body><h1>Library index</h1></body></html>'
        CrawlCapture.objects.create(
            site=site,
            url=directory,
            response=save_response(Response(directory, html, "text/html", {}), directory),
        )
        call_command("rebuild_catalogue_metadata", stdout=io.StringIO())
        entry.refresh_from_db()
        index.refresh_from_db()
        self.assertEqual(entry.language, "en")
        self.assertEqual(index.language, "fr")
        self.assertEqual(entry.author, "")
        self.assertEqual(entry.published, "")
        self.mock.assert_not_called()

    def test_bad_source_encoding_is_reported_without_blocking_other_metadata(self):
        site = configured_sites().get(host="communistusa.org")
        bad = b'<meta charset="utf-8">\xff'
        for url, html in ((ARTICLE + "bad", bad), (ARTICLE, article_html())):
            CrawlCapture.objects.create(
                site=site,
                url=url,
                response=save_response(Response(url, html, "text/html", {}), url),
            )
        output, errors = io.StringIO(), io.StringIO()
        call_command("rebuild_catalogue_metadata", stdout=output, stderr=errors)
        self.assertIn("encoding", errors.getvalue())
        self.assertIn("Skipped 1 unsupported cached sources", output.getvalue())
        self.assertEqual(CatalogueEntry.objects.get(url=ARTICLE).language, "en")
        self.mock.assert_not_called()

    def test_rebuild_infers_topics_offline_and_fills_multiple_authors(self):
        site = configured_sites().get(host="communistusa.org")
        html = article_html("<p>war war and union union</p>").replace(
            b"Test Author", b"Karl Marx and Friedrich Engels"
        )
        CrawlCapture.objects.create(
            site=site,
            url=ARTICLE,
            response=save_response(Response(ARTICLE, html, "text/html", {}), ARTICLE),
        )
        entry = CatalogueEntry.objects.create(site=site, url=ARTICLE, title="Title")
        call_command("rebuild_catalogue_metadata", stdout=io.StringIO())
        entry.refresh_from_db()
        self.assertEqual(entry.authors, ["Karl Marx", "Friedrich Engels"])
        self.assertIn("Imperialism and war", entry.topics)
        call_command("rebuild_catalogue_metadata", stdout=io.StringIO())
        entry.refresh_from_db()
        self.assertEqual(len(entry.topics), len(set(entry.topics)))
        with patch(
            "profiles.marxist.catalogue.get_profile",
            return_value=replace(PROFILE, topic_rules={}),
        ):
            call_command("rebuild_catalogue_metadata", stdout=io.StringIO())
        entry.refresh_from_db()
        self.assertEqual(entry.topics, [])
        self.mock.assert_not_called()

    def test_imported_metadata_contains_coauthors_and_multiple_inferred_topics(self):
        self.content = article_html("<p>war war, workers workers</p>").replace(
            b"Test Author", b"Karl Marx and Friedrich Engels"
        )
        site = configured_sites().get(host="communistusa.org")
        entry = CatalogueEntry.objects.create(site=site, url=ARTICLE, title="Title")
        version = self.import_article()
        self.assertEqual(version.metadata["authors"], ["Karl Marx", "Friedrich Engels"])
        self.assertIn("Imperialism and war", version.metadata["topics"])
        self.assertIn("Labour and trade unions", version.metadata["topics"])
        entry.refresh_from_db()
        self.assertEqual(entry.topics, version.metadata["topics"])

    def test_import_and_cached_rebuild_exclude_city_from_authors(self):
        self.content = article_html().replace(b"Test Author", b"Dario Dietsch, Berne")
        site = configured_sites().get(host="communistusa.org")
        entry = CatalogueEntry.objects.create(site=site, url=ARTICLE, title="Title")
        version = self.import_article()
        self.assertEqual(version.metadata["authors"], ["Dario Dietsch"])
        self.assertEqual(version.metadata["author"], "Dario Dietsch")
        call_command("rebuild_catalogue_metadata", stdout=io.StringIO())
        entry.refresh_from_db()
        self.assertEqual(entry.authors, ["Dario Dietsch"])
        self.mock.assert_called()
