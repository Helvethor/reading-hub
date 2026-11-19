import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from library.services.errors import ImportFailure
from library.services.fetch import Response
from library.sources.adapters import discover, extract
from library.sources.base import parse_html
from library.sources.normalize import normalize
from library.tests.test_sources import PARAGRAPH
from profiles.marxist.corpus import ArchiveCorpus

ROOT = "https://www.marxists.org"
BOOK = ROOT + "/archive/example/works/1900/book/index.htm"
ARTICLE = ROOT + "/francais/example/works/1900/article.htm"
MANIFESTO = ROOT + "/francais/marx/works/1847/00/kmfe18470000.htm"


def page(content, metadata="", title="Example work"):
    return (
        f'<html><head><meta charset="utf-8"><title>{title}</title>{metadata}</head>'
        f"<body>{content}</body></html>"
    ).encode()


def index():
    return page(
        '<p class="title"><a href="../../index.htm">Library</a></p>'
        '<h1>Example book</h1><table><tr><td class="index">'
        '<a href="one.htm">Chapter one</a></td></tr><tr><td class="index">'
        '<a href="two.htm#section">Chapter two</a></td></tr></table>',
        '<meta name="author" content="Example Author">',
    )


def dated_contents():
    prefaces = [
        ("marx", "1872/06/kmfe18720624"),
        ("marx", "1882/01/kmfe18820121"),
        ("engels", "1883/06/fe18830628"),
        ("engels", "1888/01/fe18880130"),
        ("engels", "1890/05/fe18900501"),
        ("engels", "1892/02/fe18920210"),
        ("engels", "1893/02/fe18930201"),
    ]
    return page(
        '<p class="titre">Synthetic linked book</p><h1>Test Author</h1>'
        '<p class="ss-titre">Sommaire</p>'
        '<a href="download.epub">Download</a>'
        '<a href="https://example.org/help.htm">External help</a>'
        '<h5>'
        + "".join(
            f'<a href="../../../../{author}/works/{path}.htm">Preface {i}</a><br>'
            for i, (author, path) in enumerate(prefaces, 1)
        )
        + '</h5><h4><a href="kmfe18470000a.htm">Opening</a></h4><h5>'
        + "".join(
            f'<a href="kmfe18470000{letter}.htm#section">Section {i}</a><br>'
            for i, letter in enumerate("abcd", 1)
        )
        + '</h5><footer><a href="unrelated.htm">Navigation</a></footer>'
    )


class ArchiveLayoutTests(SimpleTestCase):
    def test_dated_contents_includes_cross_directory_prefaces_and_deduplicates_fragments(self):
        source = discover(parse_html(dated_contents()), MANIFESTO)
        self.assertTrue(source.book)
        self.assertEqual(len(source.parts), 12)
        self.assertEqual(source.parts[0].url, MANIFESTO)
        self.assertEqual(
            [part.url for part in source.parts[1:8]],
            [
                ROOT + "/francais/marx/works/1872/06/kmfe18720624.htm",
                ROOT + "/francais/marx/works/1882/01/kmfe18820121.htm",
                ROOT + "/francais/engels/works/1883/06/fe18830628.htm",
                ROOT + "/francais/engels/works/1888/01/fe18880130.htm",
                ROOT + "/francais/engels/works/1890/05/fe18900501.htm",
                ROOT + "/francais/engels/works/1892/02/fe18920210.htm",
                ROOT + "/francais/engels/works/1893/02/fe18930201.htm",
            ],
        )
        self.assertFalse(source.parts[8].use_source_headings)
        self.assertTrue(source.parts[9].use_source_headings)
        self.assertEqual(
            [part.url for part in source.parts[8:]],
            [MANIFESTO.replace(".htm", f"{letter}.htm") for letter in "abcd"],
        )

    def test_article_citations_and_navigation_do_not_trigger_book_detection(self):
        data = page(
            '<h1>Article</h1><h2>Contents</h2>'
            f'<p>{PARAGRAPH}<a href="one.htm">Citation one</a>'
            '<a href="two.htm">Citation two</a></p>'
            '<nav><a href="next.htm">Next</a><a href="previous.htm">Previous</a></nav>'
        )
        self.assertFalse(discover(parse_html(data), ARTICLE).book)

    def test_manual_book_discovery_bypasses_missing_contents_marker_not_discovery_policy(self):
        data = page(
            '<h1>Linked work</h1><ul><li><a href="one.htm">One</a></li>'
            '<li><a href="two.htm">Two</a></li></ul>' + f'<p>{PARAGRAPH}</p>'
        )
        self.assertFalse(discover(parse_html(data), ARTICLE).book)
        self.assertTrue(discover(parse_html(data), ARTICLE, force_book=True).book)
        with self.assertRaisesRegex(ImportFailure, "discovery index"):
            discover(parse_html(data), ROOT + "/francais/", force_book=True)

    def test_subtitle_inferred_from_legacy_title_group_or_explicit_metadata(self):
        source = discover(
            parse_html(page(
                '<h2>Example Author</h2><h3>Example book</h3>'
                '<h4>BURNING QUESTIONS of our MOVEMENT</h4><hr>'
                f'<p>{PARAGRAPH}</p>'
                '<p class="information">Written: 1901. First published: 1902.</p>'
            )), BOOK,
        )
        self.assertEqual(source.metadata["subtitle"], "Burning questions of our movement")
        self.assertEqual(
            [(date["type"], date["value"]) for date in source.metadata["date_facts"]],
            [("written", "1901"), ("publication", "1902")],
        )
        explicit = discover(
            parse_html(page(
                f'<h1>Title</h1><h2>Chapter opening</h2><p>{PARAGRAPH}</p>',
                '<meta name="subtitle" content="AN EXPLICIT SUBTITLE">',
            )), ARTICLE,
        )
        self.assertEqual(explicit.metadata["subtitle"], "An explicit subtitle")
        ordinary = discover(
            parse_html(page(f'<h1>Title</h1><h2>Chapter opening</h2><p>{PARAGRAPH}</p>')),
            ARTICLE,
        )
        self.assertEqual(ordinary.metadata["subtitle"], "")

    def test_french_numbered_heading_and_publication_layout(self):
        data = page(
            '<a name="top"></a><hr><table><tr><td><p class="an">1891-92</p></td>'
            '<td><p class="ref">Publié dans : "Die Neue Zeit" 1891-92, '
            "retraduit de l'allemand</p></td></tr></table>"
            '<h1>"L\'Argent" de Zola</h1><h3 class="author">Paul Lafargue</h3>'
            '<hr><table><tr><td><p class="download">Download files</p></td>'
            "<td><table><tr><td><br></td></tr></table></td></tr></table><hr>"
            '<p class="chapit">\n I<br>\n CE QUE LE ROMAN DOIT A ZOLA</p>'
            f'<p>{PARAGRAPH}<a href="#top">Top</a></p>'
            "<hr><table><tr><td>Actual data</td></tr></table>"
        )
        source = discover(parse_html(data), ARTICLE)
        html, structure = normalize(
            [(source.parts[0], extract(parse_html(data), ARTICLE))], source, {}
        )
        parsed = parse_html(html.encode())
        self.assertEqual(structure["toc"][0]["title"], "I. Ce que le roman doit à Zola")
        self.assertEqual(parsed.h2.get_text(), "I. Ce que le roman doit à Zola")
        self.assertEqual(len(parsed.select("table")), 1)
        self.assertIn("Actual data", parsed.table.get_text())
        self.assertEqual(len(parsed.select("hr")), 1)
        self.assertIn("1891-92", html)
        self.assertIn("retraduit de l'allemand", html)
        self.assertNotIn("Download files", html)
        self.assertIsNotNone(parsed.find(id=parsed.find("a", string="Top")["href"][1:]))

    def test_modern_french_containers_keep_prose_notes_and_chapter_context(self):
        data = page(
            '<div class="entete"><p class="an_pub">1978</p>Navigation chrome</div>'
            '<div class="titre"><a name="top"></a><p class="auteur">Example Author (1900-1980)</p>'
            '<p class="titre">Example book</p><p class="date-pub">Chapitre I : A beginning</p>'
            '<p class="date-pub">1978</p></div>'
            f'<div class="corps"><p>{PARAGRAPH}<a href="#note">[1]</a></p>'
            '<p id="note">An original footnote.<a href="#top">Top</a></p></div>'
            '<div class="final">Footer chrome</div>'
        )
        source = discover(parse_html(data), ARTICLE)
        self.assertEqual(source.title, "Example book - Chapitre I : A beginning")
        self.assertEqual(source.metadata["author"], "Example Author")
        self.assertEqual(source.metadata["published"], "1978")
        html, _ = normalize([(source.parts[0], extract(parse_html(data), ARTICLE))], source, {})
        self.assertIn(PARAGRAPH, html)
        self.assertIn("An original footnote.", html)
        self.assertNotIn("Navigation chrome", html)
        self.assertNotIn("Footer chrome", html)
        parsed = parse_html(html.encode())
        for anchor in parsed.select('a[href^="#"]'):
            self.assertIsNotNone(parsed.find(id=anchor["href"][1:]))

    def test_author_period_and_gallery_indexes_are_not_complete_works(self):
        data = page(
            f"<h1>Collection index</h1><p>{PARAGRAPH}</p><ul>"
            '<li><a href="one.htm">One</a></li><li><a href="two.htm">Two</a></li></ul>'
        )
        for path in [
            "/francais/lenin/works.htm",
            "/francais/lenin/works-2.htm",
            "/espanol/lenin/txtindex.htm",
            "/nihon/trotsky/1930-1/index.htm",
            "/nihon/trotsky/1930-2/index.htm",
            "/espanol/m-e/imagen/index.htm",
            "/espanol/lenin/obras/index.htm",
            "/srpshrva/subject/index2.htm",
        ]:
            with (
                self.subTest(path=path),
                self.assertRaisesRegex(ImportFailure, "discovery index") as error,
            ):
                discover(parse_html(data), ROOT + path)
            self.assertEqual(error.exception.code, "discovery")

    def test_opening_parenthesized_year_is_a_dateline_not_a_section(self):
        url = ROOT + "/esperanto/marx-engels/1870s/1876junio.htm"
        data = page(
            "<h2>Friedrich Engels</h2><h1>Example work</h1>"
            f'<h3 id="year">(1876)</h3><p>{PARAGRAPH}<a href="#end">End</a></p>'
            '<h5 id="end">&nbsp;</h5>',
        )
        source = discover(parse_html(data), url)
        html, structure = normalize([(source.parts[0], extract(parse_html(data), url))], source, {})
        self.assertEqual(structure["toc"], [])
        parsed = parse_html(html.encode())
        self.assertEqual(parsed.find("p").get_text(" ", strip=True), "(1876)")
        link = parsed.find("a", string="End")
        self.assertEqual(parsed.find(id=link["href"][1:]).name, "div")
        self.assertIn(PARAGRAPH, html)

    def test_real_year_sections_after_prose_are_preserved(self):
        data = page(
            f"<h1>Example work</h1><p>{PARAGRAPH}</p>"
            f"<h2>(1876)</h2><p>{PARAGRAPH}</p><h2>1917</h2><p>{PARAGRAPH}</p>"
        )
        source = discover(parse_html(data), ARTICLE)
        _, structure = normalize(
            [(source.parts[0], extract(parse_html(data), ARTICLE))], source, {}
        )
        self.assertEqual([entry["title"] for entry in structure["toc"]], ["(1876)", "1917"])

    def test_french_heading_title_and_author_class_with_notes(self):
        data = page(
            '<table><tr><td class="an">Source information</td></tr></table>'
            '<h1>Example work</h1><h3 class="author">Example Author</h3>'
            f'<p class="chapit">First section</p><p>{PARAGRAPH}<a href="#ftn1">[1]</a></p>'
            '<p class="note" id="ftn1">An original test note.</p>'
            '<p class="footer"><a href="../../index.htm">Archive navigation</a></p>'
        )
        source = discover(parse_html(data), ARTICLE)
        self.assertEqual(source.title, "Example work")
        self.assertEqual(source.metadata["author"], "Example Author")
        self.assertEqual(source.metadata["language"], "fr")
        html, structure = normalize(
            [(source.parts[0], extract(parse_html(data), ARTICLE))], source, {}
        )
        self.assertIn(PARAGRAPH, html)
        self.assertIn("An original test note", html)
        self.assertNotIn("Archive navigation", html)
        self.assertEqual(structure["toc"][0]["title"], "First section")

    def test_english_title_metadata_and_table_contents(self):
        source = discover(parse_html(index()), BOOK)
        self.assertTrue(source.book)
        self.assertEqual(source.metadata["author"], "Example Author")
        self.assertEqual(len(source.parts), 3)
        self.assertTrue(source.parts[2].use_source_headings)

    def test_head_title_without_h1_and_case_insensitive_metadata(self):
        data = page(f"<p>{PARAGRAPH}</p>", '<meta name="Author" content="Example Author">')
        source = discover(parse_html(data), ARTICLE)
        self.assertEqual(source.metadata["author"], "Example Author")
        self.assertEqual(source.title, "Example work")

    def test_german_and_spanish_author_heading_precedes_title(self):
        for language, code in (("deutsch", "de"), ("espanol", "es")):
            url = ROOT + f"/{language}/writer/work.htm"
            data = page(f"<h2>Example Author</h2><h1>Example work</h1><p>{PARAGRAPH}</p>")
            source = discover(parse_html(data), url)
            self.assertEqual(source.metadata["author"], "Example Author")
            self.assertEqual(source.metadata["language"], code)
            self.assertIn(PARAGRAPH, extract(parse_html(data), url).get_text())

    def test_portuguese_paragraph_toc_and_preface_fragments(self):
        data = page(
            "<h1>Example book</h1><h2>Example Author</h2>"
            '<p class="toc1"><a href="preface.htm#a">Preface A</a></p>'
            '<p class="toc1"><a href="preface.htm#b">Preface B</a></p>'
            '<p class="toc"><a href="one.htm">Chapter one</a></p>'
            '<p class="info"><a href="credits.htm">Credits</a></p>'
        )
        source = discover(parse_html(data), ROOT + "/portugues/writer/1900/book/index.htm")
        self.assertEqual(len(source.parts), 3)
        self.assertTrue(source.parts[1].use_source_headings)
        self.assertEqual(source.metadata["language"], "pt")
        self.assertEqual(source.metadata["author"], "Example Author")

    def test_nested_contents_are_not_silently_imported_as_a_partial_book(self):
        data = page(
            '<h1>Example book</h1><ul><li><a href="one.htm">One</a></li>'
            '<li><a href="volume/two.htm">Two</a></li></ul>'
        )
        with self.assertRaisesMessage(ImportFailure, "nested chapter directories"):
            discover(parse_html(data), BOOK)
        labelled = page(
            '<h1>Example book</h1><p>Sommaire</p><h5>'
            '<a href="one.htm">One</a><a href="volume/two.htm">Two</a></h5>'
        )
        with self.assertRaisesMessage(ImportFailure, "nested chapter directories"):
            discover(parse_html(labelled), ARTICLE)

    def test_language_and_author_directories_are_not_books(self):
        data = page(
            '<h1>Library</h1><p><a href="first.htm">First work</a>'
            '<a href="second.htm">Second work</a></p>'
        )
        for path in (
            "/francais/",
            "/archive/writer/index.htm",
            "/archive/writer/works/1900/index.htm",
        ):
            with self.subTest(path=path), self.assertRaises(ImportFailure):
                discover(parse_html(data), ROOT + path)

    def test_declared_chinese_legacy_encoding_accepts_superset_characters(self):
        text = "\u4e2d\u6587\u20ac"
        data = ('<meta charset="gb2312"><p>' + text + "</p>").encode("gb18030")
        self.assertEqual(parse_html(data).p.get_text(), text)

    def test_heading_targets_survive_removal(self):
        data = page(f'<h1 id="top">Example work</h1><p>{PARAGRAPH}<a href="#top">Top</a></p>')
        source = discover(parse_html(data), ARTICLE)
        html, _ = normalize([(source.parts[0], extract(parse_html(data), ARTICLE))], source, {})
        self.assertIn(PARAGRAPH, html)

    def test_malformed_metadata_paragraph_cannot_swallow_article(self):
        for css_class in ("information", "pagenote", "title"):
            data = page(
                f'<h1>Example work</h1><p class="{css_class}">Source information'
                f"<p>{PARAGRAPH}</p><h2>Section</h2><p>{PARAGRAPH}</p>"
            )
            source = discover(parse_html(data), ARTICLE)
            body = extract(parse_html(data), ARTICLE)
            html, _ = normalize([(source.parts[0], body)], source, {})
            self.assertIn(PARAGRAPH, html)

    def test_chapter_container_is_not_converted_into_one_enormous_heading(self):
        data = page(
            f'<h1>Example work</h1><div class="chapter"><h2>Section</h2><p>{PARAGRAPH}</p></div>'
        )
        source = discover(parse_html(data), ARTICLE)
        body = extract(parse_html(data), ARTICLE)
        html, structure = normalize([(source.parts[0], body)], source, {})
        self.assertEqual(structure["toc"][0]["title"], "Section")
        self.assertIn(PARAGRAPH, html)

    def test_legacy_east_asian_labels_use_browser_compatible_codecs(self):
        for declared, codec, text in (
            ("ks_c_5601-1987", "cp949", "\uac00\ub098\ub2e4"),
            ("x-sjis", "cp932", "\u65e5\u672c\u8a9e"),
        ):
            data = (f'<meta charset="{declared}"><p>' + text + "</p>").encode(codec)
            self.assertEqual(parse_html(data).p.get_text(), text)
        data = b'\xef\xbb\xbf<meta charset="windows-1252"><p>' + "\u65e5".encode() + b"</p>"
        self.assertEqual(parse_html(data).p.get_text(), "\u65e5")


class ArchiveCorpusTests(TestCase):
    def test_memory_failure_pauses_sampling_instead_of_exhausting_the_pool(self):
        self.queue(BOOK)
        self.fetch.side_effect = MemoryError
        with (
            patch("library.services.workers.release_memory_limit") as release,
            self.assertRaises(MemoryError),
        ):
            self.corpus.step()
        release.assert_called_once()
        report = self.corpus.report()
        self.assertEqual(report["enabled"], 0)
        self.assertIn("Memory allocation failed", report["error"])
        self.assertEqual(report["queue"], {"pending": 1})
        self.assertFalse(self.corpus.step())

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        settings = override_settings(DATA_DIR=Path(temp.name))
        settings.enable()
        self.addCleanup(settings.disable)
        self.corpus = ArchiveCorpus()
        self.addCleanup(self.corpus.close)
        self.data = {
            BOOK: index(),
            BOOK.replace("index.htm", "one.htm"): page(f"<h2>Chapter one</h2><p>{PARAGRAPH}</p>"),
            BOOK.replace("index.htm", "two.htm"): page(
                f'<h2 id="section">Chapter two</h2><p>{PARAGRAPH}</p>'
            ),
        }
        self.fetch = patch(
            "profiles.marxist.corpus.Fetcher.fetch",
            side_effect=lambda url: Response(url, self.data[url], "text/html", {}),
        ).start()
        self.addCleanup(patch.stopall)
        self.corpus.db.execute("UPDATE config SET enabled=1,target=1000")
        self.corpus.db.commit()

    def queue(self, url):
        self.corpus.add(url)
        self.corpus.db.commit()

    def test_whole_multichapter_book_counts_once_and_resumes_offline(self):
        self.queue(BOOK)
        self.assertTrue(self.corpus.step())
        report = self.corpus.report()
        self.assertEqual(report["works"], {"passed": 1})
        self.assertEqual(self.fetch.call_count, 3)
        for part in self.data:
            self.queue(part)
        while self.corpus.step():
            pass
        self.assertEqual(self.corpus.report()["works"], {"passed": 1})
        self.assertEqual(self.fetch.call_count, 3)
        metrics = self.corpus.db.execute("SELECT metrics FROM works").fetchone()[0]
        self.assertIn('"html_pages": 3', metrics)
        self.assertIn('"chapters": 2', metrics)
        self.corpus.db.execute("UPDATE queue SET status='pending' WHERE url=?", (BOOK,))
        self.corpus.db.execute("UPDATE config SET enabled=1")
        self.corpus.db.commit()
        self.corpus.step()
        self.assertEqual(self.fetch.call_count, 3)

    def test_missing_chapter_is_failed_not_a_complete_work(self):
        self.queue(BOOK)
        self.fetch.side_effect = [
            Response(BOOK, index(), "text/html", {}),
            ImportFailure("Missing chapter", "http"),
        ]
        self.corpus.step()
        self.assertEqual(self.corpus.report()["works"], {"failed": 1})

    def test_broken_note_is_failed_not_counted(self):
        self.data[ARTICLE] = page(
            f'<h1>Example work</h1><p>{PARAGRAPH}<a href="#missing">Note</a></p>'
        )
        self.queue(ARTICLE)
        self.corpus.step()
        self.assertEqual(self.corpus.report()["works"], {"failed": 1})
        self.assertIn(
            "Unresolved internal link", self.corpus.report()["recent_failures"][0]["error"]
        )

    def test_target_stops_at_work_count_not_page_count(self):
        self.queue(BOOK)
        self.corpus.db.execute("UPDATE config SET target=1")
        self.corpus.db.commit()
        self.corpus.step()
        self.assertFalse(self.corpus.step())
        self.assertEqual(self.corpus.report()["enabled"], 0)
        self.assertEqual(self.corpus.report()["works"], {"passed": 1})

    def test_network_error_pauses_instead_of_hammering_source(self):
        self.queue(BOOK)
        self.fetch.side_effect = ImportFailure("Too many requests", "rate_limited")
        self.corpus.step()
        self.assertEqual(self.corpus.report()["enabled"], 0)
        self.assertFalse(self.corpus.step())
        self.assertEqual(self.fetch.call_count, 1)

    def test_discovery_excludes_external_hosts_downloads_and_traps(self):
        for url in (
            "https://evil.example/book.htm",
            ROOT + "/book.pdf",
            ROOT + "/admin/search/index.htm",
            ROOT + "/book.htm?q=loop",
        ):
            self.queue(url)
        self.assertEqual(self.corpus.db.execute("SELECT COUNT(*) FROM queue").fetchone()[0], 0)

    def test_chapter_with_book_breadcrumb_schedules_whole_book(self):
        url = BOOK.replace("index.htm", "one.htm")
        self.data[url] = page(
            f'<p class="title"><a href="index.htm">Book</a></p><p>{PARAGRAPH}</p>'
        )
        self.queue(url)
        self.corpus.step()
        self.assertEqual(self.corpus.report()["works"], {})
        self.assertTrue(
            self.corpus.db.execute("SELECT 1 FROM queue WHERE url=?", (BOOK,)).fetchone()
        )
        self.corpus.step()
        self.assertEqual(self.corpus.report()["works"], {"passed": 1})

    def test_pause_and_recheck_preserve_cached_work_without_refetching(self):
        self.queue(BOOK)
        self.corpus.step()
        self.corpus.pause()
        self.assertFalse(self.corpus.step())
        self.assertEqual(self.fetch.call_count, 3)
        self.corpus.start(1000, recheck=True)
        self.corpus.db.execute("DELETE FROM queue WHERE url NOT IN (SELECT url FROM works)")
        self.corpus.db.commit()
        self.corpus.step()
        self.assertEqual(self.corpus.report()["works"], {"passed": 1})
        self.assertEqual(self.fetch.call_count, 3)
