from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from library.profile import get_profile
from library.services.errors import ImportFailure
from library.services.fetch import canonical_url, validate_url
from library.sources.adapters import discover, extract, parse_html
from library.tests import test_pipeline
from profiles.marxist.catalogue import MarxistCatalogue

URL = "https://marxiste.org/article-exemple"
ARTICLE = b"""<!doctype html><html lang="fr-fr"><head>
<meta name="og:title" content="Article exemple">
<meta name="author" content="Jean Exemple">
<meta name="og:image" content="https://marxiste.org/images/example.webp">
</head><body><nav>Navigation</nav><h1 class="tck-article-title">Article exemple</h1>
<dl><dd class="createdby">Jean Exemple</dd>
<dd class="published"><time datetime="2026-10-25T09:13:58+01:00">25 octobre</time></dd></dl>
<div class="com-content-article__body tck-article-body" itemprop="articleBody">
<div id="data_4215" itemprop="articleBody"><p>This synthetic French-site article
has enough body text to pass the supported layout gate without relying on remote
content. Its exact paragraphs, formatting and images must be preserved.</p>
<h2>Section</h2><p>Text with <em>emphasis</em> and <a href="#note">a note</a>.</p>
<p id="note">Note text.</p><figure><img src="/images/example.webp" alt="Example">
<figcaption>Caption</figcaption></figure></div></div><footer>Footer</footer>
</body></html>"""


class MarxisteOrgTests(SimpleTestCase):
    def test_host_alias_assets_and_profile_registration(self):
        source = next(s for s in get_profile().sources if s.host == "marxiste.org")
        self.assertEqual(source.label, "PCR · France")
        self.assertEqual(source.catalogue_seeds, ("https://marxiste.org/",))
        self.assertEqual(canonical_url("http://www.marxiste.org/article-exemple"), URL)
        self.assertEqual(
            validate_url("https://marxiste.org/images/example.webp", asset=True),
            "https://marxiste.org/images/example.webp",
        )
        with self.assertRaises(ImportFailure):
            validate_url("https://marcherouge.marxiste.org/3-le-journal")

    def test_article_metadata_and_exact_body_extraction(self):
        soup = parse_html(ARTICLE)
        source = discover(soup, URL)
        self.assertEqual(source.title, "Article exemple")
        self.assertEqual(source.metadata["language"], "fr")
        self.assertEqual(source.metadata["author"], "Jean Exemple")
        self.assertEqual(source.metadata["published"], "2026-10-25T09:13:58+01:00")
        body = extract(soup, URL)
        self.assertEqual(len(body.select("img")), 1, "Hero must not duplicate an existing image.")
        self.assertEqual(body.select_one("figcaption").get_text(), "Caption")
        self.assertEqual(body.select_one('a[href="#note"]').get_text(), "a note")
        self.assertNotIn("Navigation", body.get_text())
        self.assertNotIn("Footer", body.get_text())

    def test_homepage_and_unsupported_layout_are_not_articles(self):
        soup = parse_html(b"<html><h1>Accueil</h1><nav>Menu</nav></html>")
        self.assertIsNone(MarxistCatalogue.metadata(soup, "https://marxiste.org/"))
        with self.assertRaises(ImportFailure):
            discover(soup, "https://marxiste.org/")

    def test_catalogue_discovers_heading_links_and_rejects_component_endpoints(self):
        soup = parse_html(b"""<html lang="fr"><article><h2>
        <a href="/article-exemple">Article exemple</a></h2>
        <time datetime="2026-10-25">Date</time></article>
        <nav><a href="/actualite-francaise">Category</a></nav>
        <div class="articles_actualite"><a href="/other-article"><img src="/images/other.webp"></a>
        <div class="jt-title"><a href="/other-article">Another article</a></div></div>
        <a href="/component/route66/sitemapindex/1?format=xml">Sitemap</a></html>""")
        links = list(MarxistCatalogue.links(soup, "https://marxiste.org/"))
        article = next(link for link in links if link.url == URL)
        self.assertTrue(article.is_article)
        self.assertEqual(article.language, "fr")
        self.assertEqual(article.published, "2026-10-25")
        other = [
            link
            for link in links
            if link.url == "https://marxiste.org/other-article" and link.is_article
        ]
        self.assertEqual(len(other), 1)
        self.assertTrue(other[0].is_article)
        self.assertFalse(next(link for link in links if "actualite" in link.url).is_article)
        self.assertFalse(any("/component/" in link.url for link in links))


class MarxisteOrgPipelineTests(TestCase):
    setUp = test_pipeline.PipelineTests.setUp
    fetch = test_pipeline.PipelineTests.fetch

    def test_import_reader_cache_and_source_filter(self):
        from library.services.pipeline import enqueue, process_job

        self.content = ARTICLE
        job = enqueue(URL)
        result = process_job(job)
        self.assertIsNotNone(result)
        self.assertEqual(result.metadata["language"], "fr")
        self.assertEqual(result.metadata["author"], "Jean Exemple")
        self.assertEqual(result.assets.count(), 1)
        self.assertContains(self.client.get(reverse("reader", args=[result.pk])), "Article exemple")
        self.assertContains(self.client.get("/?source=marxiste.org"), "PCR · France")
        self.mock.reset_mock()
        self.assertEqual(enqueue(URL).pk, result.pk)
        self.mock.assert_not_called()
