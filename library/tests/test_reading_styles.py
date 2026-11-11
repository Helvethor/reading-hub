import io
import json
import subprocess
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from xml.etree.ElementTree import SubElement

from bs4 import BeautifulSoup
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from pypdf import PdfReader
from weasyprint import HTML
from weasyprint.formatting_structure.boxes import MarginBox

from library.models import ReadingStyleProfile
from library.services.pdf import PDFExportError, cached_pdf, pdf_content_boxes, render_pdf
from library.services.reading_styles import (
    DEFAULTS,
    PALETTES,
    SALT,
    STYLE_VERSION,
    mix,
    style_css,
    style_digest,
    style_token,
    token_style,
    validate_style,
)
from library.tests import test_printing


class ReadingStyleTests(TestCase):
    def setUp(self):
        test_printing.PrintingTests.setUp(self)
        self.version.metadata.update(title_layout="full", metadata_page=False)
        self.version.save(update_fields=["metadata"])
        self.user = get_user_model().objects.create_user("style-owner", password="test-password")
        self.other = get_user_model().objects.create_user("other-reader", password="test-password")
        self.url = reverse("reader", args=[self.version.pk])
        self.save_url = reverse("reading-style-save", args=[self.version.pk])
        self.default_url = reverse("reading-style-default", args=[self.version.pk])
        self.custom = {**DEFAULTS, "font_mode": "dyslexic", "font_size": 18,
                       "paragraph_align": "justify", "title_align": "center",
                       "letter_spacing": .06, "word_spacing": .2, "line_height": 1.8,
                       "italic_to_bold": True, "underline_to_bold": True}

    def test_reset_resolves_account_default_without_changing_it(self):
        profile = ReadingStyleProfile.objects.create(
            owner=self.user, name="Comfort", settings=self.custom, is_default=True,
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("reading-style-preview"), {
            "style_action": "default", "style": style_token(DEFAULTS),
            "style_profile": "marxist",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["settings"], validate_style(self.custom))
        fallback = self.client.get(self.url, {
            "style_action": "load", "style_profile": "__default__",
        })
        self.assertEqual(fallback.status_code, 200)
        self.assertEqual(fallback.context["reading_style"], validate_style(self.custom))
        profile.refresh_from_db()
        self.assertTrue(profile.is_default)
        self.assertEqual(profile.settings, self.custom)

    def test_strict_settings_and_signed_snapshots_refuse_invalid_input(self):
        self.assertEqual(validate_style(self.custom), self.custom)
        self.assertEqual(token_style(style_token(self.custom)), self.custom)
        self.assertNotEqual(style_digest(DEFAULTS), style_digest(self.custom))
        for key, value in (
            ("font_size", 100), ("font_size", float("nan")), ("line_height", .1),
            ("letter_spacing", -1), ("word_spacing", 1), ("paragraph_align", "inherit"),
            ("body_font", 'url("https://example.org/font")'), ("contrast", "red"),
            ("contrast", "cream"), ("palette", "red"), ("mode", "sepia"),
            ("italic_to_bold", "false"), ("font_mode", "custom"),
        ):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_style({**DEFAULTS, key: value})
        with self.assertRaises(ValueError):
            validate_style({**DEFAULTS, "css": "body{}"})
        with self.assertRaises(ValueError):
            token_style("tampered")
        self.assertEqual(self.client.get(self.url, {"style": "tampered"}).status_code, 400)
        self.assertEqual(self.client.get(reverse("reading-style-css"),
                                         {"style": "tampered"}).status_code, 400)
        self.assertEqual(self.client.get(reverse("reader-pdf", args=[self.version.pk]),
                                         {"style": "tampered"}).status_code, 400)

    def test_every_palette_mode_and_contrast_meets_its_contrast_ratio(self):
        def luminance(color):
            channels = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
            channels = [value / 12.92 if value <= .03928 else ((value + .055) / 1.055) ** 2.4
                        for value in channels]
            return .2126 * channels[0] + .7152 * channels[1] + .0722 * channels[2]

        def ratio(first, second):
            high, low = sorted((luminance(first), luminance(second)), reverse=True)
            return (high + .05) / (low + .05)

        minimum = {"low": (4.5, 4.5), "standard": (7, 4.5), "high": (15, 7)}
        self.assertIn("lenin", PALETTES)
        for palette, (_label, modes) in PALETTES.items():
            self.assertEqual(set(modes), {"light", "dark"})
            for mode, levels in modes.items():
                self.assertEqual(set(levels), set(minimum))
                for level, (ink, paper, accent) in levels.items():
                    with self.subTest(palette=palette, mode=mode, level=level):
                        self.assertGreaterEqual(ratio(ink, paper), minimum[level][0])
                        self.assertGreaterEqual(ratio(accent or ink, paper), minimum[level][1])
                        self.assertEqual(luminance(paper) > luminance(ink), mode == "light")
                if mode == "light":
                    self.assertLess(ratio(*levels["low"][:2]), ratio(*levels["standard"][:2]))
                self.assertLessEqual(ratio(*levels["standard"][:2]), ratio(*levels["high"][:2]))
        css = style_css({**DEFAULTS, "palette": "lenin", "mode": "dark", "contrast": "high"})
        self.assertIn("color: #ffffff", css)
        self.assertIn("background: #0f0000", css)
        self.assertIn("color: #ffa59c", css)
        self.assertIn("color-scheme: dark", css)
        self.assertNotIn("#ffa59c", style_css({**DEFAULTS, "palette": "neutral"}))

    def test_palette_outranks_site_theme_for_contents_notice_and_metadata_section(self):
        from weasyprint import CSS

        static = Path(__file__).resolve().parents[2]
        site = [CSS(filename=str(static / "library/static/library/app.css")),
                CSS(filename=str(static / "library/static/library/reader.css")),
                CSS(filename=str(static / "profiles/static/marxist/dark.css"))]
        reading = CSS(string=style_css({**DEFAULTS, "palette": "lenin", "mode": "light"}))
        markup = """<div class="publication-content">
          <section class="notice document-review-status"><p>Review</p></section>
          <section class="document-contents"><h2 id="c">Contents</h2>
          <ul><li><a id="toc" href="#s">Section</a></li></ul></section>
          <article class="reader-content"><h2 id="s">Section</h2>
          <p><a id="link" href="#s">x</a></p></article>
          <section class="document-metadata-page"><h2 id="m">Metadata</h2></section></div>"""
        # The site theme loads after the reading style in the page head.
        document = HTML(string=markup).render(stylesheets=[*site[:2], reading, site[2]])
        boxes = {}

        def walk(box):
            element = getattr(box, "element", None)
            if element is not None:
                key = element.get("id") or element.get("class") or element.tag
                boxes.setdefault(key, box.style)
            for child in getattr(box, "children", []):
                walk(child)
        walk(document.pages[0]._page_box)

        def rgb(style, name="color"):
            return "#" + "".join(f"{round(channel * 255):02x}" for channel in style[name][:3])
        ink, paper, accent = PALETTES["lenin"][1]["light"]["standard"]
        self.assertEqual(rgb(boxes["toc"]), ink)
        self.assertEqual(rgb(boxes["link"]), accent)
        notice = boxes["notice document-review-status"]
        self.assertEqual(rgb(notice), ink)
        self.assertEqual(rgb(notice, "background_color"), mix(accent, paper, .08))
        self.assertEqual(rgb(boxes["s"]), accent)
        for heading in ("m", "c"):
            for name in ("font_family", "font_size", "font_weight", "margin_top", "color"):
                self.assertEqual(boxes[heading][name], boxes["s"][name], (heading, name))
        # `ch` widths follow each box's own font, so section boxes share the prose font.
        for box in ("document-metadata-page", "document-contents"):
            for name in ("max_width", "font_family", "font_size", "line_height", "margin_top"):
                self.assertEqual(boxes[box][name], boxes["reader-content"][name], (box, name))
        self.assertNotEqual(boxes["toc"]["font_family"], boxes["link"]["font_family"])
        for css in ("library/static/library/reader.css", "profiles/static/marxist/theme.css",
                    "profiles/static/marxist/dark.css"):
            self.assertNotIn(":target", (static / css).read_text())

    def test_version_four_contrast_settings_upgrade_on_read_without_rewriting_profiles(self):
        legacy = {key: value for key, value in DEFAULTS.items() if key not in ("palette", "mode")}
        for old, expected in (("theme", ("theme", "standard")),
                              ("standard", ("neutral", "standard")),
                              ("cream", ("sepia", "standard")), ("high", ("neutral", "high"))):
            with self.subTest(old=old):
                value = validate_style({**legacy, "contrast": old})
                self.assertEqual((value["palette"], value["mode"], value["contrast"]),
                                 (expected[0], "light", expected[1]))
        from django.core import signing
        token = signing.dumps({**legacy, "contrast": "cream"}, salt=SALT, compress=True)
        self.assertEqual(token_style(token)["palette"], "sepia")
        profile = ReadingStyleProfile.objects.create(
            owner=self.user, name="Old cream", settings={**legacy, "contrast": "cream"})
        self.client.force_login(self.user)
        response = self.client.get(self.url, {"style_profile": profile.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<option value="sepia" selected>')
        profile.refresh_from_db()
        self.assertEqual(profile.settings, {**legacy, "contrast": "cream"})
        response = self.client.get(self.url, {**{key: value for key, value in legacy.items()
                                                 if value is not False},
                                              "contrast": "high", "style_action": "apply"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["reading_style"]["contrast"], "high")

    def test_anonymous_preset_apply_and_pdf_share_exact_settings_without_mutating_prose(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Marxist")
        self.assertEqual(response.context["reading_style"], DEFAULTS)
        self.assertIn("font-src 'self'", response["Content-Security-Policy"])
        applied = self.client.get(self.url, {**self.custom, "style_action": "apply"})
        self.assertEqual(applied.status_code, 200)
        soup = BeautifulSoup(applied.content, "html.parser")
        self.assertEqual(soup.select_one("article").decode_contents(), self.version.html)
        self.assertEqual(applied.context["reading_style"], self.custom)
        self.assertNotIn("csrfmiddlewaretoken", [
            node.get("name") for node in soup.select("form[method=get] input")
        ])
        token = applied.context["reading_style_token"]
        stylesheet = self.client.get(applied.context["reading_style_url"])
        self.assertEqual(stylesheet.content.decode(), style_css(self.custom))
        pdf_link = soup.find("a", string="Download PDF")["href"]
        self.assertEqual(token_style(parse_qs(urlsplit(pdf_link).query)["style"][0]), self.custom)
        path = Path(self.temp.name) / "download.pdf"
        path.write_bytes(b"%PDF-test")
        with patch("library.views.cached_pdf", return_value=path) as exporter:
            response = self.client.get(pdf_link)
            self.assertEqual(response.status_code, 200)
            exporter.assert_called_once()
            self.assertEqual(exporter.call_args.args[1], self.custom)
            response.close()
        self.version.refresh_from_db()
        self.assertNotIn("OpenDyslexic", self.version.html)
        self.assertEqual(token_style(token), self.custom)
        self.assertFalse(ReadingStyleProfile.objects.exists())

    def test_personal_profile_creation_reuse_replacement_default_and_ownership(self):
        self.client.force_login(self.user)
        saved = self.client.post(self.save_url, {
            "profile_name": "Comfort", "style": style_token(self.custom), "make_default": "on",
        })
        self.assertEqual(saved.status_code, 302)
        profile = ReadingStyleProfile.objects.get(owner=self.user)
        self.assertTrue(profile.is_default)
        response = self.client.get(self.url)
        self.assertEqual(response.context["reading_style"], self.custom)
        second = deepcopy(self.version)
        second.pk = None
        second.identity = "d" * 64
        second.save()
        reused = self.client.get(reverse("reader", args=[second.pk]),
                                 {"style_profile": profile.pk})
        self.assertEqual(reused.context["reading_style"], self.custom)
        # Snapshot URLs remain exact even when the named profile is later replaced.
        old_token = reused.context["reading_style_token"]
        self.client.post(self.save_url, {"profile_name": "Comfort", "style": style_token(DEFAULTS)})
        profile.refresh_from_db()
        self.assertEqual(profile.settings, DEFAULTS)
        self.assertTrue(profile.is_default)
        self.assertEqual(token_style(old_token), self.custom)
        self.assertEqual(ReadingStyleProfile.objects.count(), 1)
        self.client.post(self.default_url, {"style_profile": "marxist"})
        profile.refresh_from_db()
        self.assertFalse(profile.is_default)
        self.assertEqual(self.client.get(self.url).context["reading_style"], DEFAULTS)
        self.client.post(self.default_url, {"style_profile": profile.pk})
        profile.refresh_from_db()
        self.assertTrue(profile.is_default)
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(self.url), "Comfort")
        self.assertEqual(self.client.get(self.url, {"style_profile": profile.pk}).status_code, 400)
        self.assertEqual(self.client.post(self.default_url,
                                          {"style_profile": profile.pk}).status_code, 404)
        for invalid in ("", "0", "9999999999999999999999", "Ⅳ"):
            self.assertEqual(self.client.post(self.default_url,
                                              {"style_profile": invalid}).status_code, 400)
        self.assertEqual(self.client.get(self.url, {"style_profile": "9" * 100}).status_code, 400)
        self.assertEqual(self.client.get(self.url, {"style_profile": "marxist"})
                         .context["reading_style"], DEFAULTS)
        self.assertEqual(self.client.post(self.save_url, {
            "profile_name": "marxist", "style": style_token(self.custom),
        }).status_code, 400)
        self.assertEqual(ReadingStyleProfile.objects.count(), 1)
        self.client.logout()
        self.assertEqual(self.client.post(self.save_url, {}).status_code, 302)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.user)
        with self.assertLogs("library", level="WARNING"):
            self.assertEqual(protected.post(self.save_url, {
                "profile_name": "Other", "style": style_token(DEFAULTS),
            }).status_code, 403)

    def test_style_digest_cache_binding_and_subprocess_transport(self):
        def build(command, **kwargs):
            self.assertEqual(json.loads(command[-2]), self.expected)
            Path(command[-1]).write_bytes(b"%PDF-test")
            return subprocess.CompletedProcess(command, 0)

        with patch("library.services.pdf.subprocess.run", side_effect=build) as process:
            self.expected = DEFAULTS
            standard = cached_pdf(self.version, DEFAULTS)
            self.expected = self.custom
            custom = cached_pdf(self.version, self.custom)
            self.assertNotEqual(standard, custom)
            self.assertEqual(cached_pdf(self.version, self.custom), custom)
            self.assertEqual(process.call_count, 2)

    def test_live_snapshot_endpoint_and_theme_following_styles_are_read_only(self):
        url = reverse("reading-style-preview")
        settings = {**self.custom, "palette": "theme"}
        response = self.client.get(url, {**settings, "style_action": "apply"})
        self.assertEqual(response.status_code, 200)
        snapshot = response.json()
        self.assertEqual(snapshot["settings"], settings)
        self.assertEqual(token_style(snapshot["token"]), settings)
        self.assertIn(f"&v={STYLE_VERSION}", snapshot["stylesheet"])
        self.assertEqual(response["Cache-Control"], "no-store")
        css = self.client.get(snapshot["stylesheet"])
        self.assertEqual(css["Cache-Control"], "no-store")
        self.assertEqual(css.content.decode(), style_css(settings))
        self.assertIn("background: transparent", css.content.decode())
        self.assertIn("var(--ink, #302221)", css.content.decode())
        self.assertIn("background: #faf5ef", css.content.decode())
        self.assertIn("[data-reading-marker]::before", css.content.decode())
        self.assertFalse(ReadingStyleProfile.objects.exists())
        self.assertEqual(self.client.get(url, {"style_action": "apply"}).status_code, 400)
        self.assertEqual(self.client.get(url, {"style_profile": 999}).status_code, 400)
        self.assertEqual(self.client.post(url).status_code, 405)

    def test_explicit_profile_update_create_conflicts_and_foreign_update_refusal(self):
        self.client.force_login(self.user)
        headers = {"HTTP_ACCEPT": "application/json"}
        response = self.client.post(self.save_url, {
            "operation": "create", "profile_name": "Comfort", "style": style_token(DEFAULTS),
        }, **headers)
        self.assertEqual(response.status_code, 200)
        profile = ReadingStyleProfile.objects.get(owner=self.user)
        self.assertEqual(response.json()["id"], profile.pk)
        self.assertEqual(response.json()["default"], "marxist")
        self.client.post(self.default_url, {"style_profile": profile.pk}, **headers)
        conflict = self.client.post(self.save_url, {
            "operation": "create", "profile_name": "Comfort", "style": style_token(self.custom),
            "make_default": "on",
        }, **headers)
        self.assertEqual(conflict.status_code, 409)
        profile.refresh_from_db()
        self.assertTrue(profile.is_default)
        self.assertEqual(profile.settings, DEFAULTS)
        changed = self.client.post(self.save_url, {
            "operation": "update", "profile_id": profile.pk, "style": style_token(self.custom),
        }, **headers)
        self.assertEqual(changed.json()["id"], profile.pk)
        profile.refresh_from_db()
        self.assertEqual(profile.settings, self.custom)
        self.assertEqual(profile.name, "Comfort")
        self.assertTrue(profile.is_default)
        self.assertEqual(ReadingStyleProfile.objects.count(), 1)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.save_url, {
            "operation": "update", "profile_id": profile.pk, "style": style_token(DEFAULTS),
        }, **headers).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.post(self.save_url, {
            "operation": "update", "profile_id": profile.pk, "style": style_token(DEFAULTS),
        }, **headers).status_code, 302)

    def test_contents_title_and_section_titles_use_identical_pdf_typography(self):
        self.version.html = '<section><h2>Section sentinel</h2><p>Body</p></section>'
        # A generated publication's contents and heading styles are tested in the same layout.
        original_render = HTML.render
        headings = {}

        def capture(renderer, *args, **kwargs):
            renderer_source = renderer.etree_element
            body = renderer_source.find("body")
            contents = SubElement(body, "section", {"class": "document-contents"})
            SubElement(contents, "h2").text = "Table of contents"
            document = original_render(renderer, *args, **kwargs)
            for page in document.pages:
                for box in pdf_content_boxes(page):
                    if box.element_tag == "h2" and hasattr(box, "text"):
                        headings[box.text] = (box.style["font_size"], box.style["font_weight"],
                                              box.style["font_family"], box.style["text_align_all"])
            return document

        with patch.object(HTML, "render", capture):
            render_pdf(self.version, io.BytesIO(), {**self.custom, "palette": "theme"})
        self.assertEqual(headings["Table of contents"], headings["Section sentinel"])

    def test_actual_pdf_headers_footers_selected_font_emphasis_and_unchanged_source(self):
        self.version.title = "Header Book Sentinel"
        self.version.html = (
            '<section><h2>First Section Sentinel</h2><p>'
            '<em>ItalicSentinel</em> <u>UnderlineSentinel</u> '
            '<a href="#second">LinkSentinel</a></p>'
            '<figure class="quotation"><blockquote><p>Quotation sentinel.</p></blockquote>'
            '<figcaption>Caption sentinel.</figcaption></figure>'
            '<p>Readable prose fills a page. ' +
            'Words in original order. ' * 60 + '</p>'
        ) + (
            '<p>More words. ' + 'Continued readable text. ' * 70 + '</p></section>'
            '<section><h2 id="second" style="break-before:page">Second Section Sentinel</h2>'
            '<p>Final body sentinel.</p></section>'
        )
        original = self.version.html
        output = io.BytesIO()
        render_pdf(self.version, output, self.custom)
        pdf = PdfReader(output)
        total = len(pdf.pages)
        self.assertGreaterEqual(total, 4)
        for index, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            self.assertIn("Header Book Sentinel", " ".join(text.split()))
            if index == 1:
                self.assertNotIn(f"{index} / {total}", text)
                self.assertNotIn("First Section Sentinel", text)
                continue
            self.assertIn(f"{index} / {total}", text)
            running = []
            page.extract_text(visitor_text=lambda text, cm, tm, font, size, running=running:
                              running.append((
                text.strip(), size * abs(cm[0]), cm[0] * tm[4] + cm[4],
                cm[3] * tm[5] + cm[5],
            )) if text.strip() else None)
            book = next(item for item in running if item[0] == self.version.title
                        and abs(item[1] - 9) < .1)
            self.assertLess(book[2], 60)
            self.assertGreater(book[3], float(page.mediabox.height) - 40)
            footer = next(item for item in running if item[0] == f"{index} / {total}")
            self.assertAlmostEqual(footer[1], book[1], delta=.1)
            self.assertLess(footer[3], 40)
            self.assertLess(abs(footer[2] - float(page.mediabox.width) / 2), 25)
            section = next(item for item in running if "Section Sentinel" in item[0]
                           and abs(item[1] - 9) < .1)
            self.assertGreater(section[2], float(page.mediabox.width) / 2)
            self.assertEqual(section[0], "Second Section Sentinel" if index == total
                             else "First Section Sentinel")
        last = pdf.pages[-1].extract_text()
        self.assertIn("Second Section Sentinel", last)
        self.assertIn("Final body sentinel.", " ".join(last.split()))
        fonts = {
            font.get_object().get("/BaseFont", "")
            for page in pdf.pages for font in page["/Resources"]["/Font"].get_object().values()
        }
        self.assertTrue(any("OpenDyslexic" in font for font in fonts), fonts)
        self.assertTrue(all("OpenDyslexic" in font for font in fonts), fonts)
        emphasis = []
        for page in pdf.pages:
            page.extract_text(visitor_text=lambda text, cm, tm, font, size: emphasis.append(
                (text, font.get("/BaseFont", "") if font else "", size),
            ) if "ItalicSentinel" in text or "UnderlineSentinel" in text else None)
        self.assertTrue(emphasis)
        self.assertTrue(all("Bold" in str(font) for _, font, _ in emphasis), emphasis)
        self.assertTrue(all(
            abs(size * .75 - self.custom["font_size"]) < .1 for _, _, size in emphasis
        ))
        self.assertEqual(self.version.html, original)

    def test_long_running_titles_have_separate_nonoverlapping_columns(self):
        self.version.title = "An unusually long book title " * 5
        self.version.html = (
            "<section><h2>" + "A long section title " * 6 +
            "</h2><p>Prose remains intact.</p></section>"
        )
        layouts = []
        original_render = HTML.render

        def capture(renderer, *args, **kwargs):
            document = original_render(renderer, *args, **kwargs)
            layouts.append(document)
            return document

        with patch.object(HTML, "render", capture):
            render_pdf(self.version, io.BytesIO())
        for index, page in enumerate(layouts[-1].pages):
            margins = {
                box.at_keyword: box for box in page._page_box.children
                if isinstance(box, MarginBox)
            }
            if index == 0:
                self.assertEqual(margins, {})
                continue
            left, right = margins["@top-left"], margins["@top-right"]
            self.assertLessEqual(left.position_x + left.width, right.position_x)
            self.assertLessEqual(left.height, 12 * 96 / 25.4 + 1)
            self.assertLessEqual(right.height, 12 * 96 / 25.4 + 1)

    def test_wrapped_running_headers_keep_a_fixed_top_inset_and_body_margin(self):
        layouts = []
        original_render = HTML.render

        def capture(renderer, *args, **kwargs):
            document = original_render(renderer, *args, **kwargs)
            layouts.append(document)
            return document

        for style in (DEFAULTS, self.custom):
            first_lines = []
            body_tops = []
            for book, section in (
                ("Short book", "Short section"),
                ("A longer book title " * 5, "A longer section title " * 5),
            ):
                self.version.title = book
                self.version.html = f"<section><h2>{section}</h2><p>Body sentinel.</p></section>"
                with patch.object(HTML, "render", capture):
                    render_pdf(self.version, io.BytesIO(), style)
                page = next(
                    page for page in layouts[-1].pages
                    if page._page_box.page_type.name == "reading-content"
                )
                body_tops.append(page._page_box.content_box_y())
                positions = []
                for box in page._page_box.children:
                    if not isinstance(box, MarginBox) or box.at_keyword == "@bottom-center":
                        continue
                    lines = [child for child in box.descendants()
                             if type(child).__name__ == "LineBox"]
                    self.assertGreater(len(lines), 1 if book != "Short book" else 0)
                    if book == "Short book":
                        self.assertEqual(len(lines), 1)
                    positions.append(lines[0].position_y)
                self.assertEqual(len(positions), 2)
                first_lines.append(positions)
            for short, wrapped in zip(first_lines[0], first_lines[1], strict=True):
                self.assertAlmostEqual(short, wrapped, delta=.1)
                self.assertAlmostEqual(short, 6 * 96 / 25.4, delta=.1)
            self.assertAlmostEqual(body_tops[0], body_tops[1], delta=.1)
            self.assertAlmostEqual(body_tops[0], 18 * 96 / 25.4, delta=.1)

    def test_multipage_title_and_contents_have_no_running_matter_but_all_prose_pages_do(self):
        markup = (
            '<html><body class="publication-content"><header class="document-header">'
            '<h1>Running Book Sentinel</h1>' +
            '<p>Title metadata sentinel. ' + 'Bibliographic details. ' * 700 +
            '</p></header><section class="document-contents"><h2>Table of contents</h2><ul>' +
            '<li>Contents entry sentinel.</li>' * 100 +
            '</ul></section><article class="reader-content"><section>'
            '<h2>Running Section Sentinel</h2><p>Prose sentinel. ' +
            'Continued prose text. ' * 800 + '</p></section></article></body></html>'
        )
        layouts = []
        original_render = HTML.render

        def capture(renderer, *args, **kwargs):
            document = original_render(renderer, *args, **kwargs)
            layouts.append(document)
            return document

        output = io.BytesIO()
        with (
            patch("django.template.loader.render_to_string", return_value=markup),
            patch.object(HTML, "render", capture),
        ):
            render_pdf(self.version, output, self.custom)
        pdf = PdfReader(output)
        title_pages, contents_pages, prose_pages = 0, 0, 0
        for index, (layout, page) in enumerate(zip(layouts[-1].pages, pdf.pages, strict=True), 1):
            text = " ".join(page.extract_text().split())
            margins = [
                box for box in layout._page_box.children if isinstance(box, MarginBox)
            ]
            if layout._page_box.page_type.name == "reading-content":
                prose_pages += 1
                self.assertEqual(len(margins), 3)
                self.assertIn("Running Book Sentinel", text)
                self.assertIn("Running Section Sentinel", text)
                self.assertIn(f"{index} / {len(pdf.pages)}", text)
                for box in margins:
                    self.assertAlmostEqual(box.style["font_size"] * .75, 9, delta=.1)
            else:
                title_pages += "Bibliographic details." in text
                contents_pages += "Contents entry sentinel." in text
                self.assertEqual(margins, [])
                self.assertNotIn("Running Section Sentinel", text)
                self.assertNotIn(f"{index} / {len(pdf.pages)}", text)
        self.assertGreaterEqual(title_pages, 2)
        self.assertGreaterEqual(contents_pages, 2)
        self.assertGreaterEqual(prose_pages, 2)

    def test_all_bundled_font_faces_embed_and_missing_fonts_refuse_partial_pdf(self):
        self.version.html = (
            "<p>RegularSentinel <strong>BoldSentinel</strong> <em>ItalicSentinel</em> "
            "<strong><em>BoldItalicSentinel</em></strong></p>"
        )
        style = {**DEFAULTS, "font_mode": "dyslexic"}
        output = io.BytesIO()
        render_pdf(self.version, output, style)
        pdf = PdfReader(output)
        fonts = {
            str(font.get_object().get("/BaseFont", ""))
            for page in pdf.pages for font in page["/Resources"]["/Font"].get_object().values()
        }
        self.assertEqual({font.split("+")[-1] for font in fonts}, {
            "OpenDyslexic", "OpenDyslexic-Bold", "OpenDyslexic-Italic", "OpenDyslexic-Bold-Italic",
        })
        for page in pdf.pages:
            for font in page["/Resources"]["/Font"].get_object().values():
                descendant = font.get_object()["/DescendantFonts"][0].get_object()
                descriptor = descendant["/FontDescriptor"]
                self.assertGreater(len(descriptor["/FontFile3"].get_object().get_data()), 1000)
        read_bytes = Path.read_bytes

        def missing(path):
            if path.name == "OpenDyslexic-Regular.otf":
                raise FileNotFoundError("test missing bundled font")
            return read_bytes(path)

        with patch.object(Path, "read_bytes", missing), self.assertRaises(PDFExportError):
            render_pdf(self.version, io.BytesIO(), style)
