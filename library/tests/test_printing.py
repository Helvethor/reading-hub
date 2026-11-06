import fcntl
import io
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup
from django.test import TestCase, override_settings
from pypdf import PdfReader
from weasyprint import CSS, HTML

from library.models import Blob, Document, Rendition, RenditionAsset, Snapshot
from library.services.pdf import (
    PDF_PRESENTATION_VERSION,
    STYLES,
    PDFExportError,
    cached_pdf,
    defer_pdf_figures,
    mark_pdf_flow,
    pdf_filename,
    render_pdf,
    split_pdf_paragraph,
)
from library.services.storage import store_blob
from library.tests.test_pipeline import png
from library.versions import APP_VERSION


class PrintingTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.override = override_settings(DATA_DIR=Path(self.temp.name))
        self.override.enable()
        self.addCleanup(self.override.disable)
        document = Document.objects.create(url="https://marxist.com/print-test.htm")
        snapshot = Snapshot.objects.create(document=document, digest="a" * 64, manifest={})
        self.version = Rendition.objects.create(
            document=document,
            snapshot=snapshot,
            title="Print test",
            identity="b" * 64,
            metadata={"author": "Test author", "language": "en"},
            structure={
                "toc": [
                    {"id": "section", "level": 2, "title": "A section"},
                    {"id": "subsection", "level": 3, "title": "A subsection"},
                ]
            },
            html='<section><h2 id="section">A section</h2><p>Original prose.</p>'
            '<h3 id="subsection">A subsection</h3>'
            '<p>A <a href="#section">return link</a>.</p></section>',
            stylesheet=(STYLES / "reader.css").read_text(),
            app_version="old",
            adapter_version="old",
            format_version="old",
            output_digest="c" * 64,
        )

    def pdf(self):
        output = io.BytesIO()
        render_pdf(self.version, output)
        return PdfReader(output)

    def test_title_page_contains_metadata_only_and_body_starts_on_second_page(self):
        self.version.metadata.update(
            subtitle="Burning questions of our movement",
            published="1902",
            date_facts=[
                {"type": "written", "value": "1901-09", "end_value": "1902-02"},
                {"type": "publication", "value": "1902"},
                {"type": "online_edition", "value": "1999"},
            ],
            contributors=[
                {"name": "Translation Person", "role": "translator"},
                {"name": "Unconfirmed Person", "role": "unknown"},
                {"name": "Hidden Person", "role": "exclude"},
            ],
            topics=["History"],
            title_layout="full",
        )
        self.version.save(update_fields=["metadata"])
        response = self.client.get(f"/versions/{self.version.pk}/")
        self.assertContains(response, "Burning questions of our movement")
        self.assertContains(response, "1901-09 / 1902-02")
        self.assertContains(response, "Translation Person")
        header = BeautifulSoup(response.content, "html.parser").select_one(".document-header")
        self.assertIn("Author", header.get_text())
        self.assertIn("Test author", header.get_text())
        self.assertNotIn("Hidden Person", header.get_text())
        pdf = self.pdf()
        self.assertEqual(len(pdf.pages), 3, "Full title page, body, then the metadata page.")
        cover = pdf.pages[0].extract_text()
        for text in (
            "Print test", "Burning questions of our movement", "Test author",
            "Written", "1901-09 / 1902-02", "Published", "1902",
            "Translator", "Translation Person", self.version.document.url,
        ):
            self.assertIn(text, cover)
        for text in ("Original prose", "Hidden Person", "Online edition", "Unconfirmed Person"):
            self.assertNotIn(text, cover)
        self.assertIn("Original prose", pdf.pages[1].extract_text())
        self.assertEqual(pdf.get_destination_page_number(pdf.outline[1][0]), 1)
        final = pdf.pages[2].extract_text()
        for text in ("Metadata", "Online edition", "1999", "Contributor (role unconfirmed)",
                     "Unconfirmed Person", "History", self.version.document.url):
            self.assertIn(text, final)
        self.assertNotIn("Hidden Person", final)
        self.assertNotIn("Original prose", final)

    def test_article_preset_uses_compact_title_and_page_settings_override_it(self):
        self.version.metadata.update(contributors=[{"name": "Translation Person", "role": "translator"}])
        self.version.save(update_fields=["metadata"])
        response = self.client.get(f"/versions/{self.version.pk}/")
        soup = BeautifulSoup(response.content, "html.parser")
        self.assertIn("document-header-compact", soup.select_one(".document-header")["class"])
        self.assertTrue(soup.select_one(".document-header .document-facts"))
        self.assertFalse(soup.select_one(".document-contents"), "Articles omit the contents page by preset.")
        self.assertTrue(soup.select_one("#document-metadata table.document-metadata-table"))
        pdf = self.pdf()
        self.assertEqual(len(pdf.pages), 2, "Compact title and body share the first page.")
        self.assertIn("Original prose", pdf.pages[0].extract_text())
        self.assertEqual(pdf.pages[0].extract_text().count("Print test"), 1,
                         "The first page shows the title once, without a running header.")
        self.assertIn("Metadata", pdf.pages[1].extract_text())
        self.assertIn("Print test", pdf.pages[1].extract_text(), "Later pages keep running headers.")
        self.version.metadata.update(work_type="book", metadata_page=False)
        self.version.save(update_fields=["metadata"])
        soup = BeautifulSoup(self.client.get(f"/versions/{self.version.pk}/").content, "html.parser")
        self.assertIn("document-header-full", soup.select_one(".document-header")["class"])
        self.assertFalse(soup.select_one("#document-metadata"))
        self.assertNotIn("Metadata", [link.get_text() for link in soup.select(".toc-panel a")])
        pdf = self.pdf()
        self.assertEqual(len(pdf.pages), 2, "Full title page then body; no metadata page.")
        self.assertNotIn("Original prose", pdf.pages[0].extract_text())
        self.assertNotIn("Metadata", pdf.pages[1].extract_text())

    def test_unconfirmed_attribution_is_not_silently_presented_as_author(self):
        self.version.metadata = {
            "author": "",
            "contributors": [{"role": "unknown", "name": "Unconfirmed Person"}],
        }
        self.version.save(update_fields=["metadata"])
        response = self.client.get(f"/versions/{self.version.pk}/")
        soup = BeautifulSoup(response.content, "html.parser")
        header = soup.select_one(".document-header")
        self.assertNotIn("Unconfirmed Person", header.get_text())
        self.assertNotIn("document-fact-author", str(header))
        page = soup.select_one("#document-metadata").get_text()
        self.assertIn("Contributor (role unconfirmed)", page)
        self.assertIn("Unconfirmed Person", page)
        self.assertNotIn("Author", [row.get_text() for row in soup.select("#document-metadata th")])

    def test_nested_outline_internal_links_and_metadata(self):
        reader = self.pdf()
        self.assertEqual(reader.metadata.title, "Print test")
        self.assertEqual(reader.metadata.author, "Test author")
        outline = reader.outline
        self.assertEqual(outline[0].title, "Print test")
        self.assertEqual(outline[1][0].title, "A section")
        self.assertEqual(outline[1][1][0].title, "A subsection")
        for destination in [outline[0], outline[1][0], outline[1][1][0]]:
            self.assertGreaterEqual(reader.get_destination_page_number(destination), 0)
        links = [
            annotation.get_object()
            for page in reader.pages
            for annotation in page.get("/Annots", [])
        ]
        self.assertTrue(any(link.get("/Dest") for link in links))
        self.assertNotIn("Contents", [item.title for item in outline if not isinstance(item, list)])
        text = "\n".join(page.extract_text() for page in reader.pages)
        self.assertNotIn("Contents", text)
        body_text = []
        for page in reader.pages:
            page.extract_text(visitor_text=lambda text, cm, tm, font, size:
                              body_text.append(text) if size * abs(cm[0]) > 9 else None)
        self.assertEqual("\n".join(body_text).count("A section"), 1)
        self.assertEqual(text.count("A subsection"), 1)

    def test_title_based_filename_preserves_unicode_and_is_filesystem_safe(self):
        for title, expected in [
            ("Print test", "Print test.pdf"),
            ("La homiĝo – étude", "La homiĝo – étude.pdf"),
            ('Why? A/B: "test"', "Why- A-B- -test-.pdf"),
            ("../CON", "-CON.pdf"),
            ("CON", "_CON.pdf"),
            ("NUL.txt", "_NUL.txt.pdf"),
            (" . ", "Untitled.pdf"),
            ("line\r\nbreak", "line--break.pdf"),
        ]:
            with self.subTest(title=title):
                self.assertEqual(pdf_filename(title), expected)
        self.assertLessEqual(len(pdf_filename("a" * 1000)), 154)

    def test_cached_image_and_no_source_network(self):
        data = png()
        digest = store_blob(data)
        blob = Blob.objects.create(digest=digest, media_type="image/png", size=len(data))
        RenditionAsset.objects.create(rendition=self.version, blob=blob)
        self.version.html += (
            f'<figure><img src="/assets/{digest}/"><figcaption>Caption</figcaption></figure>'
        )
        reader = self.pdf()
        self.assertTrue(any(list(page.images) for page in reader.pages))
        self.assertIn("Caption", "".join(page.extract_text() for page in reader.pages))
        for url in [
            "https://example.org/tracker.png",
            "file:///etc/passwd",
            "data:image/png;base64,AAAA",
        ]:
            with self.subTest(url=url):
                self.version.html = f'<img src="{url}">'
                with self.assertRaises(PDFExportError):
                    self.pdf()

    def test_reviewed_note_repairs_keep_pdf_destinations_and_return_links(self):
        from library.services.corrections import apply_expected, validate_expected
        from library.sources.base import Part, Source
        from library.sources.normalize import normalize

        body = BeautifulSoup(
            '<div><p>Text <a href="#broken">[1]</a></p>'
            '<p id="explanation">Note <em>text</em> <a href="#wrong">Return</a></p></div>',
            "html.parser",
        ).div
        part = Part(self.version.document.url, "Print test")
        source = Source("Print test", {"language": "en"}, [part], False)
        expected = {
            "notes": [
                {
                    "reference": {"block": 0, "link": 0},
                    "target": 1,
                    "backlink": {"block": 1, "link": 0},
                }
            ]
        }
        validate_expected(expected, body, source)
        apply_expected(source, body, expected)
        self.version.html, _ = normalize([(part, body)], source, {})
        reader = self.pdf()
        text = " ".join(page.extract_text() for page in reader.pages)
        self.assertEqual(text.count("Note text"), 1)
        self.assertEqual(text.count("Return"), 1)
        links = [
            annotation.get_object()
            for page in reader.pages
            for annotation in page.get("/Annots", [])
        ]
        self.assertGreaterEqual(sum(bool(link.get("/Dest")) for link in links), 2)

    def test_missing_cached_image_is_not_a_partial_pdf(self):
        digest = "d" * 64
        blob = Blob.objects.create(digest=digest, media_type="image/png", size=10)
        RenditionAsset.objects.create(rendition=self.version, blob=blob)
        self.version.html = f'<img src="/assets/{digest}/">'
        with self.assertRaises(PDFExportError):
            self.pdf()

    def test_invalid_cached_raster_is_not_silently_omitted(self):
        data = b"not an image"
        digest = store_blob(data)
        blob = Blob.objects.create(digest=digest, media_type="image/png", size=len(data))
        RenditionAsset.objects.create(rendition=self.version, blob=blob)
        self.version.html = f'<img src="/assets/{digest}/">'
        with self.assertRaises(PDFExportError):
            self.pdf()

    def test_download_cache_and_failure_ui(self):
        path = Path(self.temp.name) / "result.pdf"
        path.write_bytes(b"%PDF-test")
        with patch("library.views.cached_pdf", return_value=path):
            response = self.client.get(f"/versions/{self.version.pk}/download.pdf")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["Content-Type"], "application/pdf")
            self.assertIn("attachment", response.headers["Content-Disposition"])
            self.assertIn('filename="Print test.pdf"', response.headers["Content-Disposition"])
            response.close()
            self.version.title = "La homiĝo – étude"
            self.version.save(update_fields=["title"])
            response = self.client.get(f"/versions/{self.version.pk}/download.pdf")
            from urllib.parse import unquote

            self.assertIn("La homiĝo – étude.pdf", unquote(response.headers["Content-Disposition"]))
            response.close()
        with patch("library.views.cached_pdf", side_effect=PDFExportError("Please retry")):
            with self.assertLogs("library", level="ERROR"):
                response = self.client.get(f"/versions/{self.version.pk}/download.pdf")
            self.assertContains(response, "Please retry", status_code=503)
            self.assertEqual(response.headers["Retry-After"], "10")
        self.assertEqual(
            self.client.post(f"/versions/{self.version.pk}/download.pdf").status_code, 405
        )
        self.assertEqual(self.client.get("/versions/99999/download.pdf").status_code, 404)

    def test_export_subprocess_cache_timeout_failure_and_busy(self):
        def build(command, **kwargs):
            Path(command[-1]).write_bytes(b"%PDF-test")
            return subprocess.CompletedProcess(command, 0)

        directory = Path(self.temp.name) / "pdf"
        directory.mkdir()
        old = directory / f"{self.version.pk}-{self.version.identity}-{APP_VERSION}.pdf"
        old.write_bytes(b"%PDF-old-presentation")
        with patch("library.services.pdf.subprocess.run", side_effect=build) as run:
            path = cached_pdf(self.version)
            self.assertTrue(path.name.endswith(f"-p{PDF_PRESENTATION_VERSION}.pdf"))
            self.assertEqual(path.read_bytes(), b"%PDF-test")
            self.assertEqual(cached_pdf(self.version), path)
            run.assert_called_once()
            self.assertEqual(run.call_args.kwargs["timeout"], 120)
        self.assertEqual(old.read_bytes(), b"%PDF-old-presentation")
        old.unlink()
        path.unlink()
        for result in [
            subprocess.TimeoutExpired("pdf", 120),
            subprocess.CompletedProcess([], 1, stderr=b"failed"),
        ]:
            with patch("library.services.pdf.subprocess.run") as run:
                if isinstance(result, Exception):
                    run.side_effect = result
                else:
                    run.return_value = result
                with self.assertRaises(PDFExportError):
                    cached_pdf(self.version)
            self.assertEqual(list((Path(self.temp.name) / "pdf").glob("*.pdf")), [])
        with (Path(self.temp.name) / "pdf" / "render.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            with self.assertRaisesMessage(PDFExportError, "Another PDF"):
                cached_pdf(self.version)

    def test_reader_print_override_for_old_versions_and_optional_wrap(self):
        response = self.client.get(f"/versions/{self.version.pk}/")
        self.assertContains(response, "library/print.css")
        self.assertContains(response, ">Download PDF</a>")
        self.assertNotContains(response, "Download PDF with bookmarks")
        self.assertNotContains(response, 'class="print-toc"')
        self.assertContains(response, 'id="print-wrap-images"')
        soup = BeautifulSoup(response.content, "html.parser")
        self.assertEqual(soup.select_one(".reader-content").decode_contents(), self.version.html)

    def test_print_pagination_keeps_heading_chains_and_caption(self):
        markup = '<article class="reader-content"><div style="height:65mm"></div>'
        markup += "<h2>Heading sentinel</h2><h3>Subtitle sentinel</h3><p>Following sentinel.</p>"
        markup += (
            '<figure><img src="test:image"><figcaption>Caption sentinel.</figcaption>'
            "</figure></article>"
        )
        document = HTML(
            string=markup, url_fetcher=lambda url: {"string": png(), "mime_type": "image/png"}
        ).render(
            stylesheets=[
                CSS(filename=str(STYLES / "reader.css")),
                CSS(filename=str(STYLES / "print.css")),
                CSS(string="@page {size: 100mm 100mm; margin: 10mm}"),
            ]
        )
        locations = {}
        for number, page in enumerate(document.pages):
            for box in page._page_box.descendants():
                text = getattr(box, "text", "")
                for sentinel in [
                    "Heading sentinel",
                    "Subtitle sentinel",
                    "Following sentinel",
                    "Caption sentinel",
                ]:
                    if sentinel in text:
                        locations[sentinel] = number
                if box.element_tag == "img":
                    locations["image"] = number
        self.assertGreater(len(document.pages), 1)
        self.assertGreater(locations["Heading sentinel"], 0)
        self.assertEqual(locations["Heading sentinel"], locations["Subtitle sentinel"])
        self.assertEqual(locations["Subtitle sentinel"], locations["Following sentinel"])
        self.assertEqual(locations["image"], locations["Caption sentinel"])

    def test_tall_image_fits_a4_and_stays_with_caption(self):
        from PIL import Image

        image = io.BytesIO()
        Image.new("RGB", (500, 4000), "green").save(image, format="PNG")
        document = HTML(
            string='<article class="reader-content"><p>Before.</p><figure>'
            '<img src="test:tall"><figcaption>Caption sentinel.</figcaption></figure>'
            "<p>After.</p></article>",
            url_fetcher=lambda url: {"string": image.getvalue(), "mime_type": "image/png"},
        ).render(stylesheets=[CSS(filename=str(STYLES / "print.css"))])
        positions = {}
        for number, page in enumerate(document.pages):
            for box in page._page_box.descendants():
                if box.element_tag == "img":
                    positions["image"] = number
                    self.assertLessEqual(box.height, 210 * 96 / 25.4 + 1)
                if "Caption sentinel" in getattr(box, "text", ""):
                    positions["caption"] = number
        self.assertEqual(positions["image"], positions["caption"])

    def test_pdf_defers_large_figure_to_fill_gap_with_following_prose(self):
        from PIL import Image

        image = io.BytesIO()
        Image.new("RGB", (800, 900), "green").save(image, format="PNG")
        data = image.getvalue()
        digest = store_blob(data)
        blob = Blob.objects.create(digest=digest, media_type="image/png", size=len(data))
        RenditionAsset.objects.create(rendition=self.version, blob=blob)
        self.version.html = (
            '<section><div style="height:55mm"></div><h2 id="section">Gap heading</h2><p></p>'
            f'<figure id="portrait"><img src="/assets/{digest}/">'
            "<figcaption>Portrait caption sentinel.</figcaption></figure>"
            + "".join(
                f"<p>Prose marker {i}. "
                + "Following readable text fills the available space. " * 12
                + "</p>"
                for i in range(8)
            )
            + '<h2 id="subsection">Next section sentinel</h2><p>Final prose.</p></section>'
        )
        original = self.version.html
        with (
            patch("library.services.pdf.defer_pdf_figures", return_value=None),
            patch("library.services.pdf.mark_pdf_flow", side_effect=lambda markup: markup),
        ):
            baseline = self.pdf()
        updated = self.pdf()
        baseline_page = next(
            page for page in baseline.pages if "Gap heading" in page.extract_text()
        )
        updated_page = next(page for page in updated.pages if "Gap heading" in page.extract_text())
        self.assertNotIn("Prose marker 0", baseline_page.extract_text())
        self.assertIn("Prose marker 0", updated_page.extract_text())

        def bottom_text(page):
            positions = []

            def visit(text, cm, tm, font, size):
                if text.strip() and size * abs(cm[0]) > 9:
                    positions.append(cm[3] * tm[5] + cm[5])

            page.extract_text(visitor_text=visit)
            return min(positions)

        self.assertGreater(bottom_text(baseline_page) - bottom_text(updated_page), 72)
        texts = [page.extract_text() for page in updated.pages]
        complete = "\n".join(texts)
        for i in range(8):
            self.assertEqual(complete.count(f"Prose marker {i}."), 1)
        self.assertEqual(complete.count("Portrait caption sentinel."), 1)
        self.assertLess(complete.index("Prose marker 0."), complete.index("Prose marker 7."))
        caption_page = next(
            i for i, text in enumerate(texts) if "Portrait caption sentinel." in text
        )
        image_calls = []
        updated.pages[caption_page].extract_text(
            visitor_operand_before=lambda op, args, cm, tm: (
                image_calls.append(args) if op == b"Do" else None
            )
        )
        self.assertTrue(image_calls, "Image and caption must remain on the same page.")
        next_section = next(text for text in texts if "Next section sentinel" in text)
        self.assertIn("Final prose.", next_section)
        self.assertEqual(self.version.html, original)

    def test_adjacent_figures_can_move_past_subheading_with_opening_prose(self):
        markup = mark_pdf_flow(
            '<article class="reader-content"><section><div style="height:140mm"></div>'
            '<figure id="first"><img src="test:image" style="height:180mm"></figure>'
            '<figure id="second"><img src="test:image" style="height:180mm"></figure>'
            '<h2 id="opening">Opening <em>heading</em></h2><p></p>'
            "<p>Opening prose must stay with its heading.</p></section></article>"
        )
        document = HTML(
            string=markup, url_fetcher=lambda url: {"string": png(), "mime_type": "image/png"}
        ).render(stylesheets=[CSS(filename=str(STYLES / "print.css"))])
        updated = defer_pdf_figures(markup, document)
        self.assertIsNotNone(updated)
        self.assertLess(updated.index('id="opening"'), updated.index("Opening prose"))
        self.assertLess(updated.index("Opening prose"), updated.index('id="first"'))
        self.assertLess(updated.index('id="first"'), updated.index('id="second"'))

    def test_pdf_paragraph_split_preserves_inline_text_links_and_unique_anchors(self):
        soup = BeautifulSoup(
            '<p id="paragraph">Before <em id="emphasis">some emphasized '
            '<a id="link" href="#target">linked words and more linked words</a> '
            "after the link</em> and the end.</p>",
            "html.parser",
        )
        original = soup.get_text()
        prefix = split_pdf_paragraph(soup.p, 0.5)
        self.assertIsNotNone(prefix)
        self.assertEqual(soup.get_text(), original)
        self.assertEqual(len(soup.select("p")), 2)
        for target in ("paragraph", "emphasis", "link"):
            self.assertEqual(len(soup.select(f"#{target}")), 1)
        self.assertEqual(
            "".join(a.get_text() for a in soup.select('a[href="#target"]')),
            "linked words and more linked words",
        )

    def test_pdf_remeasures_multiple_images_and_keeps_headings_with_prose(self):
        from PIL import Image

        image = io.BytesIO()
        Image.new("RGB", (800, 900), "green").save(image, format="PNG")
        data = image.getvalue()
        digest = store_blob(data)
        blob = Blob.objects.create(digest=digest, media_type="image/png", size=len(data))
        RenditionAsset.objects.create(rendition=self.version, blob=blob)
        self.version.html = (
            "<section>"
            + "".join(
                f'<h2 id="heading-{i}">Chapter marker {i}</h2><p></p>'
                f'<figure><img src="/assets/{digest}/">'
                f"<figcaption>Caption {i}.</figcaption></figure>"
                + "".join(
                    f"<p>Paragraph {i}-{j}. "
                    + "Readable prose continues in its original order. " * 22
                    + "</p>"
                    for j in range(6)
                )
                for i in range(5)
            )
            + "</section>"
        )
        original = self.version.html
        with patch("library.services.pdf.defer_pdf_figures", wraps=defer_pdf_figures) as defer:
            result = self.pdf()
        self.assertGreater(defer.call_count, 3)
        pages = [page.extract_text() for page in result.pages]
        complete = "\n".join(pages)
        for i in range(5):
            heading_page = next(text for text in pages if f"Chapter marker {i}" in text)
            self.assertIn(f"Paragraph {i}-0.", heading_page)
            self.assertEqual(complete.count(f"Caption {i}."), 1)
            for j in range(6):
                self.assertEqual(complete.count(f"Paragraph {i}-{j}."), 1)
        image_calls = []
        for index, page in enumerate(result.pages):
            calls = []
            page.extract_text(
                visitor_operand_before=lambda op, args, cm, tm, calls=calls: (
                    calls.append(args) if op == b"Do" else None
                )
            )
            image_calls.extend(calls)
            # A final image has no remaining chapter prose to backfill with.
            if index and calls and (index < len(pages) - 1 or "Readable prose" in pages[index]):
                bottoms = []
                result.pages[index - 1].extract_text(
                    visitor_text=lambda text, cm, tm, font, size, bottoms=bottoms: (
                        bottoms.append((cm[3] * tm[5] + cm[5]) * 25.4 / 72)
                        if text.strip()
                        else None
                    )
                )
                self.assertLess(
                    min(bottoms), 70, f"Image page {index + 1}; layouts {defer.call_count}"
                )
        self.assertEqual(len(image_calls), 5)
        self.assertEqual(self.version.html, original)

    def test_pdf_deferral_stops_at_chapter_boundary_and_does_not_move_quotations(self):
        for figure in [
            '<figure><img src="test:image"><figcaption>Caption</figcaption></figure>',
            '<figure class="quotation"><blockquote><p>Quote</p></blockquote>'
            "<figcaption>Credit</figcaption></figure>",
        ]:
            markup = mark_pdf_flow(
                '<article class="reader-content"><section><div style="height:140mm"></div>'
                + figure
                + "</section><section><h2>New chapter</h2>"
                "<p>Do not move across this boundary.</p></section></article>"
            )
            doc = HTML(
                string=markup, url_fetcher=lambda url: {"string": png(), "mime_type": "image/png"}
            ).render(stylesheets=[CSS(filename=str(STYLES / "print.css"))])
            self.assertIsNone(defer_pdf_figures(markup, doc))
