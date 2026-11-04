from bs4 import BeautifulSoup
from django.test import SimpleTestCase

from library.services.errors import ImportFailure
from library.services.fetch import Response, canonical_url, validate_url
from library.sources.adapters import discover, extract, parse_html
from library.sources.normalize import normalize
from library.tests.test_sources import PARAGRAPH
from profiles.marxist.adapters import clean_site_author, source_language
from profiles.marxist.catalogue import MarxistCatalogue
from profiles.marxist.site import PROFILE


class NationalSourceTests(SimpleTestCase):
    def test_french_swiss_promotional_icon_component_does_not_become_article_headings(self):
        url = "https://communisme.ch/fr/mouvement-ouvrier/example/"
        markup = (
            '<html lang="fr"><head><meta property="og:title" content="Article"></head>'
            '<body><div class="post-text">'
            f'<p id="opening">{PARAGRAPH}</p>'
            '<div class="icon-add-block"><a href="https://example.org/join">'
            '<svg><title>Join label</title><path d="M0 0"></path></svg>'
            '<h4>Join label</h4></a><a href="https://example.org/donate">'
            '<h4>Donate label</h4></a></div>'
            '<h3 id="real-heading">Actual section</h3>'
            '<p id="ending">Article conclusion with '
            '<a href="https://example.org/donate">ordinary donation discussion</a>.</p>'
            '</div></body></html>'
        ).encode()
        soup = parse_html(markup)
        source = discover(soup, url)
        body = extract(soup, url)
        self.assertIsNone(body.select_one(".icon-add-block"))
        self.assertEqual(body.select_one("#opening").get_text(), PARAGRAPH)
        self.assertEqual(body.select_one("#real-heading").get_text(), "Actual section")
        self.assertIn("ordinary donation discussion", body.get_text())
        html, structure = normalize([(source.parts[0], body)], source, {})
        self.assertNotIn("Join label", html)
        self.assertNotIn("Donate label", html)
        self.assertIn("Article conclusion", html)
        self.assertTrue(any(item["title"] == "Actual section" for item in structure["toc"]))
        from library.services.semantic_documents import canonical_document

        canonical_document({
            "version": 1, "title": source.title, "metadata": source.metadata, "html": html,
        })

    def test_french_swiss_component_rule_does_not_remove_other_sites_content(self):
        markup = (
            '<html><body><div class="article-content">'
            f'<p>{PARAGRAPH}</p><div class="icon-add-block">'
            '<p>Article content using a coincidental class.</p></div></div></body></html>'
        ).encode()
        body = extract(parse_html(markup), "https://marxist.com/example.htm")
        self.assertIn("Article content using a coincidental class.", body.get_text())

    def test_french_swiss_promotional_component_alone_is_not_an_article(self):
        markup = (
            '<html><body><div class="post-text"><div class="icon-add-block">'
            '<p>Promotional component text ' + "Join now. " * 20 +
            '</p></div></div></body></html>'
        ).encode()
        with self.assertRaisesMessage(ImportFailure, "empty or unexpectedly short"):
            extract(parse_html(markup), "https://communisme.ch/fr/example/")

    def test_quebec_hero_already_present_as_resized_mirrored_image(self):
        url = "https://www.marxiste.qc.ca/article/example"
        data = (
            '<html><head><meta property="og:title" content="Example">'
            '<meta property="og:image" content="https://admin.marxiste.qc.ca/'
            'wp-content/uploads/2025/12/photo.jpg"></head><body>'
            '<div id="article-content"><figure><img '
            'src="/wordpress/wp-content/uploads/2025/12/photo-1024x682.jpg" '
            'srcset="/wordpress/wp-content/uploads/2025/12/photo-1024x682.jpg 1024w, '
            '/wordpress/wp-content/uploads/2025/12/photo.jpg 1082w">'
            f"<figcaption>Original caption</figcaption></figure><p>{PARAGRAPH}</p></div>"
            "</body></html>"
        ).encode()
        body = extract(parse_html(data), url)
        self.assertEqual(len(body.select("img")), 1)
        self.assertEqual(body.figcaption.get_text(), "Original caption")
        # A different image with the same filename on an unrelated host is not equivalent.
        modified = data.replace(
            b"https://admin.marxiste.qc.ca/wp-content",
            b"https://example.org/wp-content",
        )
        self.assertEqual(len(extract(parse_html(modified), url).select("img")), 2)

    def test_registered_aliases_and_asset_only_quebec_cms(self):
        for alias, host in [
            ("marxiste.qc.ca", "www.marxiste.qc.ca"),
            ("www.kommunismus.ch", "kommunismus.ch"),
            ("www.communist.red", "communist.red"),
            ("www.comunismo.ch", "comunismo.ch"),
        ]:
            self.assertEqual(canonical_url(f"https://{alias}/sample"), f"https://{host}/sample")
        self.assertEqual(
            validate_url("https://admin.marxiste.qc.ca/wp-content/uploads/test.jpg", asset=True),
            "https://admin.marxiste.qc.ca/wp-content/uploads/test.jpg",
        )
        for asset, path in [(False, "/wp-content/uploads/test.jpg"), (True, "/wp-admin/")]:
            with self.assertRaises(ImportFailure):
                validate_url("https://admin.marxiste.qc.ca" + path, asset=asset)

    def test_quebec_body_title_author_and_french_date(self):
        url = "https://www.marxiste.qc.ca/article/sample"
        markup = (
            '<html lang="fr-CA"><head><meta property="og:title" '
            'content="Title | Révolution communiste"></head><body>'
            '<article id="article-main"><h2 id="article-title">Title</h2>'
            '<ul><li id="article-byline-author">Example Author</li>'
            '<li id="article-byline-date">jeu. 15 oct. 2026</li></ul>'
            f'<div id="article-content"><p>{PARAGRAPH}</p></div></article>'
            "<aside>Exclude footer</aside></body></html>"
        ).encode()
        soup = parse_html(markup)
        source = discover(soup, url)
        self.assertEqual(source.title, "Title")
        self.assertEqual(source.metadata["author"], "Example Author")
        self.assertEqual(source.metadata["published"], "2026-10-15")
        self.assertEqual(source.metadata["language"], "fr")
        html, _ = normalize([(source.parts[0], extract(soup, url))], source, {})
        self.assertIn(PARAGRAPH, html)
        self.assertNotIn("Exclude footer", html)

    def test_german_swiss_layout_metadata_and_default_language(self):
        url = "https://kommunismus.ch/deutsch/sample/"
        data = (
            '<html><head><meta property="og:title" content="German article">'
            '<meta property="article:published_time" content="2026-10-08"></head>'
            '<body><span class="author">von Example Author, Bern</span>'
            f'<div class="post-text"><p>{PARAGRAPH}</p></div></body></html>'
        ).encode()
        source = discover(parse_html(data), url)
        self.assertEqual(source.metadata["language"], "de")
        self.assertEqual(source.metadata["authors"], ["Example Author"])
        self.assertEqual(source.metadata["published"], "2026-10-08")

    def test_swiss_sources_enforce_their_assigned_languages(self):
        for url, language in (
            ("https://communisme.ch/fr/story/", "fr"),
            ("https://communisme.ch/de/story/", "fr"),
            ("https://kommunismus.ch/de/story/", "de"),
            ("https://kommunismus.ch/fr/story/", "de"),
            ("https://comunismo.ch/it/story/", "it"),
            ("https://comunismo.ch/es/story/", "it"),
        ):
            self.assertEqual(
                source_language(parse_html(b'<html lang="en-US"></html>'), url), language
            )
        for url in (
            "https://communisme.ch/de/story/",
            "https://kommunismus.ch/fr/story/",
            "https://comunismo.ch/es/story/",
        ):
            with self.assertRaises(ImportFailure):
                discover(parse_html(b"<html></html>"), url)

    def test_italian_site_article_body_and_language_sitemap(self):
        url = "https://comunismo.ch/it/tema/example/"
        markup = (
            '<html lang="it-IT"><head><meta property="og:title" content="Italian article">'
            '<meta name="author" content="✏  Alan Woods">'
            '</head><body><div class="container-wide article"><div class="post-content">'
            '<h1>Italian article</h1><div class="post-text">'
            f"<p>{PARAGRAPH}</p></div></div></div></body></html>"
        ).encode()
        soup = parse_html(markup)
        source = discover(soup, url)
        self.assertEqual(source.metadata["language"], "it")
        self.assertEqual(source.metadata["author"], "Alan Woods")
        self.assertIn(PARAGRAPH, extract(soup, url).get_text(" ", strip=True))
        sitemap = Response(
            "https://comunismo.ch/wp-sitemap-posts-post-1.xml",
            b"<urlset><url><loc>https://comunismo.ch/it/a/</loc></url>"
            b"<url><loc>https://comunismo.ch/es/b/</loc></url></urlset>",
            "application/xml",
            {},
        )
        links = list(MarxistCatalogue.links(MarxistCatalogue.parse_response(sitemap), sitemap.url))
        self.assertEqual([link.url for link in links], ["https://comunismo.ch/it/a/"])

    def test_rivoluzione_sitemap_is_supported_and_source_location_is_italy(self):
        source = next(site for site in PROFILE.sources if site.host == "rivoluzione.red")
        self.assertEqual(source.label, "PCR · Italia")
        sitemap_url = "https://rivoluzione.red/wp-sitemap-posts-post-2.xml"
        self.assertIn("application/xml", MarxistCatalogue.media_types(sitemap_url))
        response = Response(
            sitemap_url,
            b"<urlset><url><loc>https://rivoluzione.red/sample/</loc></url></urlset>",
            "application/xml",
            {},
        )
        links = list(MarxistCatalogue.links(MarxistCatalogue.parse_response(response), sitemap_url))
        self.assertEqual([link.url for link in links], ["https://rivoluzione.red/sample/"])
        self.assertEqual(links[0].language, "it")

    def test_comunismo_label_and_author_artifact_cleanup(self):
        source = next(site for site in PROFILE.sources if site.host == "comunismo.ch")
        self.assertEqual(source.label, "PCR · Svizzera")
        self.assertEqual(clean_site_author("✏  redazione", "comunismo.ch"), "redazione")
        self.assertEqual(clean_site_author("✏  Alan Woods", "comunismo.ch"), "Alan Woods")
        self.assertEqual(clean_site_author("✏  Alan Woods", "rivoluzione.red"), "✏  Alan Woods")

    def test_rivoluzione_red_article_body_title_byline_and_date(self):
        url = "https://rivoluzione.red/sample/"
        markup = (
            '<html lang="it-IT"><head><meta property="og:title" content="Italian article">'
            '<meta property="article:published_time" content="2026-10-16"></head><body>'
            '<article id="post-1"><header><h1 class="entry-title">Italian article</h1>'
            '</header><div class="post-wrapper-content"><p><em>di Francesco Giliani</em></p>'
            f'<section class="the_content"><p>{PARAGRAPH}</p></section></div></article>'
            "</body></html>"
        ).encode()
        soup = parse_html(markup)
        source = discover(soup, url)
        self.assertEqual(source.title, "Italian article")
        self.assertEqual(source.metadata["author"], "Francesco Giliani")
        self.assertEqual(source.metadata["language"], "it")
        self.assertEqual(source.metadata["published"], "2026-10-16")
        metadata = MarxistCatalogue.metadata(soup, url)
        self.assertEqual(metadata.author, "Francesco Giliani")
        self.assertEqual(metadata.language, "it")
        body = extract(soup, url)
        self.assertIn(PARAGRAPH, body.get_text(" ", strip=True))
        self.assertNotIn("Francesco Giliani", body.get_text(" ", strip=True))

    def test_british_split_intro_and_full_body_exclude_related_posts(self):
        url = "https://communist.red/sample/"
        data = (
            '<html lang="en-GB"><head><meta name="author" content="The Communist">'
            '<meta property="og:title" content="Title | The Communist"></head><body>'
            '<h1 class="entry-title">Title</h1><span class="author">Actual Author</span>'
            '<div class="meta_intro"><div class="entry-content"><p>Intro sentinel.</p></div></div>'
            '<main id="content"><article id="post-123"><div class="entry-content">'
            f'<p>{PARAGRAPH}</p><div class="code-block">Exclude advert</div>'
            '<div class="simplesocialbuttons">Exclude sharing controls</div>'
            '</div></article></main><div class="related-posts"><article>'
            '<div class="entry-content"><p>Exclude related prose.</p></div>'
            "</article></div></body></html>"
        ).encode()
        soup = parse_html(data)
        source = discover(soup, url)
        self.assertEqual(source.title, "Title")
        self.assertEqual(source.metadata["author"], "Actual Author")
        html, _ = normalize([(source.parts[0], extract(soup, url))], source, {})
        self.assertIn("Intro sentinel.", html)
        self.assertIn(PARAGRAPH, html)
        self.assertNotIn("Exclude", html)

    def test_sitemap_discovery_is_source_scoped_and_article_marked(self):
        url = "https://communist.red/post-sitemap.xml"
        response = Response(
            url,
            b"<urlset><url><loc>https://communist.red/sample/</loc></url></urlset>",
            "application/xml",
            {},
        )
        self.assertIn("application/xml", MarxistCatalogue.media_types(url))
        soup = MarxistCatalogue.parse_response(response)
        links = list(MarxistCatalogue.links(soup, url))
        self.assertEqual(len(links), 1)
        self.assertTrue(links[0].is_article)
        self.assertEqual(links[0].url, "https://communist.red/sample/")
        self.assertIsNone(MarxistCatalogue.media_types("https://communist.red/sample/"))

    def test_quebec_json_cursor_and_listing_links(self):
        url = "https://www.marxiste.qc.ca/archive?type=ajax&cursor=test"
        import json

        response = Response(
            url,
            json.dumps(
                {
                    "content": '<a href="/article/sample">Sample title</a>',
                    "nextPage": "?type=ajax&cursor=next",
                }
            ).encode(),
            "application/json",
            {},
        )
        soup = MarxistCatalogue.parse_response(response)
        links = list(MarxistCatalogue.links(soup, url))
        self.assertTrue(any(link.is_article and link.title == "Sample title" for link in links))
        self.assertTrue(any(not link.is_article and "cursor=next" in link.url for link in links))
        for raw in [b"invalid", b'{"content": 5}', b'{"content":"x","nextPage":5}']:
            with self.subTest(raw=raw), self.assertRaises(ImportFailure):
                MarxistCatalogue.parse_response(Response(url, raw, "application/json", {}))

    def test_blockquotes_remove_only_matched_outer_marks(self):
        from library.sources.base import Part, Source

        for markup, expected in [
            (
                "<blockquote><p>“A quote with an <em>inner “quotation”</em>.”</p></blockquote>",
                "A quote with an inner “quotation”.",
            ),
            ("<blockquote><p>« Une citation. »</p></blockquote>", " Une citation. "),
            ("<blockquote><p>“Unmatched quotation.</p></blockquote>", "“Unmatched quotation."),
            ("<blockquote><p>Unquoted prose.</p></blockquote>", "Unquoted prose."),
        ]:
            with self.subTest(markup=markup):
                body = BeautifulSoup(markup, "html.parser")
                part = Part("https://communist.red/sample/", "Example")
                source = Source("Example", {"language": "en"}, [part], False)
                html, _ = normalize([(part, body)], source, {})
                self.assertEqual(BeautifulSoup(html, "html.parser").blockquote.get_text(), expected)
