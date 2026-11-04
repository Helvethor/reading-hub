from bs4 import BeautifulSoup
from django.test import SimpleTestCase

from library.services.errors import ImportFailure
from library.sources.adapters import discover, extract, parse_html
from library.sources.normalize import normalize

ARTICLE = "https://communistusa.org/sample/"
BOOK = "https://www.marxists.org/francais/test/index.htm"
PARAGRAPH = (
    "This is a sufficiently long original test paragraph about reading and preserving "
    "documents. Its wording must remain unchanged after importing and formatting."
)


def article_html(extra="", host="communistusa.org", title="Test article"):
    selector = {
        "communistusa.org": "et_pb_post_content",
        "marxist.com": "article-content",
        "communisme.ch": "post-text",
    }[host]
    return (
        f'<html><head><meta charset="utf-8"><meta property="og:title" content="{title}">'
        f'<meta name="author" content="Test Author"></head><body><nav>Exclude navigation</nav>'
        f'<div class="{selector}"><h4>Section one</h4><p>{PARAGRAPH}</p>{extra}</div>'
        "<footer>Exclude footer</footer></body></html>"
    ).encode()


def book_index():
    return (
        '<html><head><meta charset="windows-1252"></head><body>'
        '<p class="titre">Un livre illustré</p><h1>Test Author</h1>'
        '<ul><li><a href="chapter1.htm">First chapter</a></li>'
        '<li><a href="chapter1.htm#section">Same page subsection</a></li>'
        '<li>Part two<ul><li><a href="chapter2.htm">Second chapter</a></li></ul></li></ul>'
        "</body></html>"
    ).encode("windows-1252")


def chapter(number, extra=""):
    return (
        '<html><head><meta charset="utf-8"></head><body><p class="an">Header date</p>'
        '<p class="titre">Un livre illustré</p><h1>Test Author</h1>'
        f'<h2>Chapter {number}</h2><a name="preface"></a>'
        f'<p class="ss-titre" id="section">Subsection {number}</p><p>{PARAGRAPH}</p>{extra}'
        '<hr><a href="../index.htm"><img src="/img/haut.gif" alt="Site navigation"></a>'
        "</body></html>"
    ).encode()


class SourceTests(SimpleTestCase):
    def test_cited_work_remains_inline_in_quotation_caption(self):
        extra = '<figure class="quotation"><blockquote><p>Quoted passage.</p></blockquote>' \
            '<figcaption>From <cite id="work"><a href="https://example.org/work">' \
            'A source document</a></cite>, 1852.</figcaption></figure>'
        soup = parse_html(article_html(extra))
        source = discover(soup, ARTICLE)
        html, _ = normalize([(source.parts[0], extract(soup, ARTICLE))], source, {})
        result = BeautifulSoup(html, "html.parser")
        self.assertEqual(result.select_one("figure figcaption cite").get_text(),
                         "A source document")
        self.assertEqual(result.select_one("cite a")["href"], "https://example.org/work")

    def test_empty_and_break_only_containers_are_removed_without_losing_targets(self):
        extra = (
            "<div> \n<br></div><div><span><br><br></span></div>"
            "<p> &nbsp; <br></p><div><!-- decoration --></div>"
            '<a href="#target">Jump</a><div><a id="target"></a></div>'
            "<div><hr></div><table><tr><td></td><td>Value</td></tr></table>"
            "<p>Line one<br>Line two</p>"
            '<div><img src="/picture.png" alt="Picture"></div>'
        )
        soup = parse_html(article_html(extra))
        source = discover(soup, ARTICLE)
        html, _ = normalize([(source.parts[0], extract(soup, ARTICLE))], source, {})
        result = BeautifulSoup(html, "html.parser")
        for node in result.select("div,p,span"):
            self.assertTrue(node.get_text(strip=True) or node.find(["a", "hr", "img"]))
        link = result.find("a", string="Jump")
        self.assertIsNotNone(result.find(id=link["href"][1:]))
        self.assertEqual(len(result.select("td")), 2)
        self.assertIsNotNone(result.select_one("hr"))
        paragraph = next(p for p in result.select("p") if "Line one" in p.get_text())
        self.assertIsNotNone(paragraph.find("br"))
        self.assertIn("Image unavailable: Picture", result.get_text())

    def test_standalone_quote_and_credit_get_semantic_blocks_without_text_changes(self):
        extra = (
            '<p id="quote">\u201cThere is no royal road to science, and only those '
            "who climb can reach its summits.\u201d</p>\n"
            '<p id="credit">\u2013 Karl Marx, Preface to <em>Capital.</em>'
            '<a href="#note" id="reference"><sup>[1]</sup></a></p>'
            '<p id="note">A source note. <a href="#reference">Return</a></p>'
        )
        soup = parse_html(article_html(extra))
        source = discover(soup, ARTICLE)
        body = extract(soup, ARTICLE)
        before = body.get_text()
        html, structure = normalize([(source.parts[0], body)], source, {})
        output = BeautifulSoup(html, "html.parser")
        figure = output.select_one("figure.quotation")
        self.assertIsNotNone(figure)
        self.assertTrue(figure.select_one("blockquote > p[id]"))
        self.assertTrue(figure.select_one("figcaption > p[id] > em"))
        self.assertFalse(figure.blockquote.select("figcaption"))
        self.assertEqual(
            output.get_text().replace(" [back]", ""),
            before.replace("\u201c", "").replace("\u201d", ""),
        )
        self.assertEqual(len(structure["toc"]), 1)
        ids = {node["id"] for node in output.select("[id]")}
        for link in output.select('a[href^="#"]'):
            self.assertIn(link["href"][1:], ids)

    def test_quotation_inference_leaves_ambiguous_and_existing_markup_alone(self):
        quote = "\u201cA sufficiently long quotation about science and its difficult paths.\u201d"
        for extra in [
            f"<p>{quote}</p><p>Normal following prose.</p>",
            f"<p>{quote} Marx wrote, followed by more prose.</p><p>\u2013 Marx</p>",
            f"<p>{quote}</p><h2>Intervening heading</h2><p>\u2013 Marx</p>",
            f"<p>{quote}</p>Intervening prose<p>\u2013 Marx</p>",
            f"<blockquote><p>{quote}</p><p>\u2013 Marx</p></blockquote>",
            f"<p>{quote}</p><p>- ordinary list-like text</p>",
        ]:
            with self.subTest(extra=extra):
                soup = parse_html(article_html(extra))
                source = discover(soup, ARTICLE)
                html, _ = normalize([(source.parts[0], extract(soup, ARTICLE))], source, {})
                self.assertNotIn('class="quotation"', html)

    def test_social_widgets_become_compact_links_without_placeholder_whitespace(self):
        widgets = (
            '<blockquote class="instagram-media" id="social" data-instgrm-permalink="https://www.instagram.com/p/ABC/">'
            '<div><div>&nbsp;</div><a href="https://www.instagram.com/p/ABC/">'
            "<div>&nbsp;</div>View this post</a></div>"
            '<p><a href="https://www.instagram.com/p/ABC/">'
            "A post shared by Example</a></p></blockquote>"
            '<iframe src="https://www.facebook.com/plugins/video.php?href=https%3A%2F%2Fwww.facebook.com%2Fexample%2Fvideos%2F123"></iframe>'
            '<div class="fb-post" data-href="https://www.facebook.com/example/posts/456"><div>&nbsp;</div></div>'
            '<p><a href="#social">Reference to embed</a></p>'
            '<p><a href="https://www.instagram.com/ordinary/">Ordinary editorial link</a></p>'
        )
        soup = parse_html(article_html(widgets))
        source = discover(soup, ARTICLE)
        body = extract(soup, ARTICLE)
        html, _ = normalize([(source.parts[0], body)], source, {})
        self.assertNotIn("\xa0", html)
        self.assertNotIn("iframe", html)
        self.assertNotIn("View this post", html)
        self.assertIn("View on Instagram: A post shared by Example", html)
        self.assertIn('href="https://www.facebook.com/example/videos/123"', html)
        self.assertIn("Ordinary editorial link", html)
        self.assertIn("Reference to embed", html)

    def test_normalized_legacy_asian_labels_keep_compatible_codec_supersets(self):
        for labels, codec, text in [
            (["ks_c_5601-1987", "euc-kr", "euc_kr"], "cp949", "\ubdc1"),
            (["shift_jis", "shift-jis", "x-sjis"], "cp932", "\u9ad9"),
            (["gb2312", "gbk"], "gb18030", "\U00020000"),
        ]:
            for label in labels:
                with self.subTest(label=label):
                    data = f'<meta charset="{label}"><p>{text}</p>'.encode(codec)
                    self.assertEqual(parse_html(data).p.get_text(), text)

    def test_html_ascii_and_latin1_labels_use_browser_windows1252_semantics(self):
        for label in ["us-ascii", "ascii", "iso-8859-1", "latin1"]:
            soup = parse_html(
                f'<meta charset="{label}"><p>Espa\xf1a \u20ac</p>'.encode("windows-1252")
            )
            self.assertEqual(soup.p.get_text(), "Espa\xf1a \u20ac")

    def test_wrong_legacy_label_can_recover_strict_utf8_but_not_damaged_bytes(self):
        data = '<meta charset="windows-1250"><p>\u0141\xf3d\u017a</p>'.encode()
        with self.assertLogs("library", level="WARNING"):
            self.assertEqual(parse_html(data).p.get_text(), "\u0141\xf3d\u017a")
        with self.assertRaises(ImportFailure):
            parse_html(b'<meta charset="windows-1250"><p>\x81</p>')
        with self.assertRaises(ImportFailure):
            parse_html(b'<meta charset="not-an-encoding"><p>text</p>')

    def test_article_adapters_preserve_body_not_site_chrome(self):
        for host in ["communistusa.org", "marxist.com", "communisme.ch"]:
            with self.subTest(host=host):
                soup = parse_html(article_html(host=host))
                source = discover(soup, f"https://{host}/sample/")
                body = extract(soup, source.parts[0].url)
                html, structure = normalize([(source.parts[0], body)], source, {})
                self.assertEqual(source.title, "Test article")
                self.assertIn(PARAGRAPH, html)
                self.assertNotIn("Exclude navigation", html)
                self.assertNotIn("Exclude footer", html)
                self.assertEqual(structure["toc"][0]["level"], 2)

    def test_declared_legacy_encoding_and_title_author(self):
        soup = parse_html(book_index(), {"content-type": "text/html"})
        source = discover(soup, BOOK)
        self.assertEqual(source.title, "Un livre illustré")
        self.assertEqual(source.metadata["author"], "Test Author")
        self.assertEqual(len(source.parts), 3)
        self.assertEqual(source.parts[0].url, BOOK)
        self.assertEqual(source.parts[2].group, "Part two")

    def test_invalid_encoding_and_replacement_character_fail(self):
        for data in [b'<meta charset="utf-8">\xff', "<p>\ufffd</p>".encode()]:
            with self.subTest(data=data), self.assertRaises(ImportFailure):
                parse_html(data)

    def test_empty_or_unknown_layout_fails(self):
        for data in [b"<html>hello</html>", b'<div class="et_pb_post_content"></div>']:
            with self.subTest(data=data), self.assertRaises(ImportFailure):
                discover(parse_html(data), ARTICLE)

    def test_empty_book_index_fails(self):
        soup = parse_html(b'<p class="titre">Empty book</p><h1>Author</h1>')
        with self.assertRaises(ImportFailure):
            discover(soup, BOOK)

    def test_book_parts_anchors_notes_and_duplicate_ids(self):
        source = discover(parse_html(book_index()), BOOK)
        pages = []
        for i, part in enumerate(source.parts, 1):
            if part.url == BOOK:
                pages.append((part, extract(parse_html(book_index()), BOOK, index=True)))
                continue
            extra = (
                '<p><a href="#ftn1" name="ftnref1">[1]</a></p>'
                '<p id="ftn1">An original test note.</p>'
                '<p id="repeat">First duplicate</p><p id="repeat">Second duplicate</p>'
            )
            if i == 2:
                extra += '<p><a href="chapter2.htm#section">Next section</a></p>'
            body = extract(parse_html(chapter(i - 1, extra)), part.url, book=True, group=part.group)
            pages.append((part, body))
        html, structure = normalize(pages, source, {})
        soup = BeautifulSoup(html, "html.parser")
        ids = [node["id"] for node in soup.select("[id]")]
        self.assertEqual(len(ids), len(set(ids)))
        for node in soup.select("a[href^='#']"):
            self.assertIn(node["href"][1:], ids)
        for entry in structure["toc"]:
            self.assertIn(entry["id"], ids)
        self.assertEqual(structure["pages"], 3)
        self.assertIn("Part two", html)
        self.assertNotIn("Site navigation", html)
        self.assertNotIn("Header date", html)
        self.assertEqual(len(soup.select(".note-backlink")), 2)

    def test_unresolved_internal_link_fails(self):
        soup = parse_html(article_html('<a href="#missing">Missing</a>'))
        source = discover(soup, ARTICLE)
        with self.assertRaisesMessage(ImportFailure, "Unresolved internal"):
            normalize([(source.parts[0], extract(soup, ARTICLE))], source, {})

    def test_unsafe_markup_removed_and_images_local(self):
        extra = (
            '<script>alert(1)</script><iframe src="https://evil.example"></iframe>'
            '<p onclick="alert(1)" style="color:red"><a href="javascript:alert(1)">Unsafe</a></p>'
            '<img src="/test.png" onerror="alert(1)" alt="Original alt">'
            '<p class="wp-caption-text">Original credit</p><table><tr><td>A cell</td></tr></table>'
        )
        soup = parse_html(article_html(extra))
        source = discover(soup, ARTICLE)
        digest = "a" * 64
        html, _ = normalize(
            [(source.parts[0], extract(soup, ARTICLE))],
            source,
            {
                "https://communistusa.org/test.png": {"digest": digest},
            },
        )
        for unsafe in ["<script", "<iframe", "onclick", "onerror", "javascript:", "style="]:
            self.assertNotIn(unsafe, html)
        self.assertIn(f"/assets/{digest}/", html)
        self.assertIn("<figcaption>Original credit</figcaption>", html)
        self.assertIn("<td>A cell</td>", html)

    def test_missing_image_has_local_placeholder(self):
        soup = parse_html(article_html('<img src="/missing.jpg" alt="A description">'))
        source = discover(soup, ARTICLE)
        html, _ = normalize([(source.parts[0], extract(soup, ARTICLE))], source, {})
        self.assertNotIn("<img", html)
        self.assertIn("Image unavailable: A description", html)

    def test_swiss_newspaper_appendices_are_not_part_of_the_requested_article(self):
        data = article_html(
            "<hr><h1>A different article</h1><p>Unrelated newspaper material.</p>",
            host="communisme.ch",
        )
        soup = parse_html(data)
        body = extract(soup, "https://communisme.ch/sample/")
        self.assertIn(PARAGRAPH, body.get_text())
        self.assertNotIn("A different article", body.get_text())

    def test_joomla_nested_captions_become_semantic_figures(self):
        soup = parse_html(
            article_html(
                '<span class="wf_caption"><img src="/test.png"><span>Original credit</span></span>',
                host="marxist.com",
            )
        )
        source = discover(soup, "https://marxist.com/sample/")
        body = extract(soup, "https://marxist.com/sample/")
        html, _ = normalize([(source.parts[0], body)], source, {})
        self.assertIn("<figure>", html)
        self.assertIn("<figcaption>Original credit</figcaption>", html)

    def test_legacy_link_aliases_and_image_anchor_survive(self):
        soup = parse_html(
            article_html(
                '<a href="#image">Illustration</a><img id="image" src="/test.png">'
                '<a id="primary" name="secondary"></a><a href="#secondary">Alias</a>'
                '<font id="legacy">Legacy anchor</font><a href="#legacy">Legacy link</a>'
            )
        )
        source = discover(soup, ARTICLE)
        html, _ = normalize([(source.parts[0], extract(soup, ARTICLE))], source, {})
        parsed = BeautifulSoup(html, "html.parser")
        for anchor in parsed.select("a[href^='#']"):
            self.assertIsNotNone(parsed.find(id=anchor["href"][1:]))

    def test_prefaces_in_one_file_are_siblings_not_nested_duplicate_titles(self):
        index = book_index().replace(b'href="chapter1.htm"', b'href="chapter1.htm#preface"')
        source = discover(parse_html(index), BOOK)
        part = source.parts[0]
        self.assertTrue(part.use_source_headings)
        content = chapter(1).replace(
            b"<h2>Chapter 1</h2>",
            b'<h2 id="first">First preface</h2><p>Text.</p><h2>Second preface</h2>',
        )
        body = extract(parse_html(content), part.url, book=False)
        _, structure = normalize([(part, body)], source, {})
        self.assertEqual(
            [(h["title"], h["level"]) for h in structure["toc"][:2]],
            [("First preface", 2), ("Second preface", 2)],
        )
