import fcntl
import io
import subprocess
import tempfile
import xml.etree.ElementTree as ET
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
        self.assertNotIn("review status", header.get_text().lower())
        self.assertNotIn("Cached", header.get_text())
        self.assertEqual(
            len(BeautifulSoup(response.content, "html.parser").select("#document-edition-status")),
            1,
        )
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
                     "Unconfirmed Person", "History", self.version.document.url,
                     "Edition and review status", "Source-generated edition"):
            self.assertIn(text, final)
        all_text = "\n".join(page.extract_text() for page in pdf.pages)
        self.assertEqual(all_text.count("Edition and review status"), 1)
        outline_titles = []

        def collect_titles(items):
            for item in items:
                if isinstance(item, list):
                    collect_titles(item)
                else:
                    outline_titles.append(item.title)

        collect_titles(pdf.outline)
        self.assertIn("Edition and review status", outline_titles)
        for internal in (
            "Cached ", "Source adapter", "Formatting rules", "Document publication rules",
        ):
            self.assertNotIn(internal, all_text)
        self.assertNotIn("Hidden Person", final)
        self.assertNotIn("Original prose", final)

    def test_pdf_metadata_round_trips_bounded_unicode_dates_and_review_evidence(self):
        self.version.metadata = {
            "author": "Zoë 雪",
            "contributors": [
                {"name": "Éditrice", "role": "editor"},
                {"name": "مترجم", "role": "translator"},
                {"name": "Rôle inconnu", "role": "unknown"},
                {"name": "PRIVATE_EXCLUDED_SENTINEL", "role": "exclude"},
            ],
            "language": "fr-CA",
            "topics": ["Histoire", "雪"],
            "work_type": "book",
            "original_title": "L'œuvre",
            "publisher": "出版社",
            "date_facts": [
                {"type": "written", "value": "1901-09", "end_value": "1902-02"},
                {"type": "publication", "value": "1903-04"},
                {"type": "online_edition", "value": "2001"},
                {"type": "unknown", "value": "c. 1920"},
            ],
            "published": "1903-04",
            "reviewer_account": "PRIVATE_ACCOUNT_SENTINEL",
            "private_annotation": "PRIVATE_ANNOTATION_SENTINEL",
            "workspace_path": "/PRIVATE_PATH_SENTINEL",
            "credential": "PRIVATE_CREDENTIAL_SENTINEL",
        }
        self.version.snapshot.manifest = {
            "account": "PRIVATE_MANIFEST_SENTINEL",
            "path": "/PRIVATE_MANIFEST_PATH_SENTINEL",
        }
        self.version.snapshot.save(update_fields=["manifest"])
        self.version.save(update_fields=["metadata"])

        reader = self.pdf()
        info = reader.metadata
        self.assertEqual(info.title, self.version.title)
        self.assertEqual(info.author, "Zoë 雪")
        self.assertEqual(reader.trailer["/Root"]["/Lang"], "fr-CA")
        self.assertIn("Histoire", info.keywords)
        self.assertEqual(info.subject, info.keywords)
        self.assertIsNotNone(info.creation_date)
        packet = reader.trailer["/Root"]["/Metadata"].get_object().get_data()
        root = ET.fromstring(packet)
        namespace = "{urn:reading-hub:pdf:1.0}"
        xmp_namespace = "{http://ns.adobe.com/xap/1.0/}"
        joined = "\n".join(root.itertext())
        xmp_tags = {node.tag for node in root.iter()}
        self.assertIn(namespace + "dateFact", xmp_tags)
        for role in ("editor", "translator", "unknown"):
            self.assertIn(namespace + role, xmp_tags)
        for expected in (
            "Éditrice", "مترجم", "Rôle inconnu", "1901-09", "1902-02",
            "1903-04", "2001", "c. 1920", "source-generated",
        ):
            self.assertIn(expected, joined)
        pdf_created = root.find(f".//{xmp_namespace}CreateDate")
        self.assertIsNotNone(pdf_created)
        self.assertNotEqual(pdf_created.text, "1903-04")
        self.assertIn("+00:00", pdf_created.text)
        for private in (
            "PRIVATE_EXCLUDED_SENTINEL", "PRIVATE_ACCOUNT_SENTINEL",
            "PRIVATE_ANNOTATION_SENTINEL", "PRIVATE_PATH_SENTINEL",
            "PRIVATE_CREDENTIAL_SENTINEL", "PRIVATE_MANIFEST_SENTINEL",
            "PRIVATE_MANIFEST_PATH_SENTINEL",
        ):
            self.assertNotIn(private, packet.decode("utf-8"))

    def test_article_preset_uses_compact_title_and_page_settings_override_it(self):
        self.version.metadata.update(contributors=[{"name": "Translation Person", "role": "translator"}])
        self.version.save(update_fields=["metadata"])
        response = self.client.get(f"/versions/{self.version.pk}/")
        soup = BeautifulSoup(response.content, "html.parser")
        self.assertIn("document-header-compact", soup.select_one(".document-header")["class"])
        facts = soup.select(".document-header .document-facts .document-fact")
        self.assertEqual(facts[-1].select_one(".document-fact-label").get_text(), "Source")
        self.assertTrue(all(fact.select_one(".document-fact-value") for fact in facts))
        self.assertIn("document-fact-span-6", facts[-1]["class"],
                      "A long source URL takes its own row.")
        self.assertFalse(soup.select_one(".document-contents"), "Articles omit the contents page by preset.")
        self.assertTrue(soup.select_one("#document-metadata table.document-metadata-table"))
        pdf = self.pdf()
        self.assertEqual(len(pdf.pages), 2, "Compact title and body share the first page.")
        self.assertIn("Original prose", pdf.pages[0].extract_text())
        self.assertEqual(pdf.pages[0].extract_text().count("Print test"), 1,
                         "The first page shows the title once, without a running header.")
        self.assertIn("Metadata", pdf.pages[1].extract_text())
        self.assertIn("Print test", pdf.pages[1].extract_text(), "Later pages keep running headers.")
        self.assertEqual(
            "\n".join(page.extract_text() for page in pdf.pages).count("Edition and review status"),
            1,
        )
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
        self.assertIn("Edition and review status", pdf.pages[1].extract_text())

    def test_pdf_renders_modern_title_size_and_body_separation_independently(self):
        self.version.structure = {"book": True, "toc": []}
        self.version.html = (
            '<section id="first" data-section-role="chapter">'
            '<h2>First chapter</h2><p>Body sentinel.</p></section>'
        )
        for title_size, separation, expected_body_page in (
            ("full", "continuous", 0),
            ("compact", "new-page", 1),
        ):
            with self.subTest(title=title_size, separation=separation):
                self.version.metadata.update({
                    "work_type": "book",
                    "title_layout": title_size,
                    "contents_page": False,
                    "metadata_page": False,
                    "layout": {
                        "version": 1,
                        "overrides": {"body": separation, "edition": "continuous"},
                    },
                })
                self.version.save(update_fields=["html", "metadata", "structure"])
                pdf = self.pdf()
                pages = [page.extract_text() for page in pdf.pages]
                title_page = next(i for i, text in enumerate(pages) if "Print test" in text)
                body_page = next(i for i, text in enumerate(pages) if "Body sentinel" in text)
                self.assertEqual(title_page, 0)
                self.assertEqual(body_page, expected_body_page, pages)
                self.assertEqual(len(pdf.pages), expected_body_page + 1, pages)

    def test_two_line_widow_orphan_policy_allows_controlled_paragraph_and_list_splits(self):
        examples = (
            (
                "paragraph",
                '<p style="margin:0">P1 first line<br>P2 second line<br>'
                'P3 third line<br>P4 fourth line</p>',
                ("P1 first line", "P2 second line", "P3 third line", "P4 fourth line"),
            ),
            (
                "list item",
                '<ul style="margin:0;padding:0"><li style="margin:0">L1 first line<br>'
                'L2 second line<br>L3 third line<br>L4 fourth line</li></ul>',
                ("L1 first line", "L2 second line", "L3 third line", "L4 fourth line"),
            ),
        )
        original_stylesheet = self.version.stylesheet
        for label, content, lines in examples:
            with self.subTest(kind=label):
                self.version.html = (
                    '<div style="height:517pt"></div>' + content
                )
                self.version.metadata.update(
                    work_type="article", title_layout="compact", metadata_page=False,
                )
                self.version.save(update_fields=["html", "metadata"])
                pages = [page.extract_text() for page in self.pdf().pages]
                split = [
                    sum(line in page for line in lines)
                    for page in pages
                ]
                self.assertGreaterEqual(split[0], 2)
                self.assertTrue(any(count >= 2 for count in split[1:]))
                locations = [
                    next(index for index, page in enumerate(pages) if line in page)
                    for line in lines
                ]
                self.assertEqual(locations, sorted(locations))
                self.version.stylesheet = (
                    original_stylesheet
                    + "\n@media print {.reader-content p, .reader-content li "
                    "{orphans:3 !important; widows:3 !important;}}"
                )
                old_pages = [page.extract_text() for page in self.pdf().pages]
                old_locations = [
                    next(index for index, page in enumerate(old_pages) if line in page)
                    for line in lines
                ]
                self.assertEqual(len(set(old_locations)), 1)
                self.version.stylesheet = original_stylesheet

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

    def test_endmatter_navigation_uses_unique_targets_when_source_ids_collide(self):
        self.version.metadata.update(metadata_page=False)
        self.version.structure["toc"] = []
        self.version.html = (
            '<p id="document-metadata">Retained metadata anchor.</p>'
            '<p id="document-edition-status">Retained edition anchor.</p>'
            '<p id="document-edition-status-heading">Retained heading anchor.</p>'
            '<p id="document-edition-status-2-heading">Second retained heading anchor.</p>'
        )
        self.version.save(update_fields=["metadata", "structure", "html"])
        soup = BeautifulSoup(
            self.client.get(f"/versions/{self.version.pk}/").content, "html.parser",
        )
        identifiers = [node["id"] for node in soup.select("[id]")]
        self.assertEqual(
            len(identifiers), len(set(identifiers)),
            [identifier for identifier in set(identifiers) if identifiers.count(identifier) > 1],
        )
        self.assertIsNone(soup.select_one("#document-metadata-2"))
        edition = soup.select_one("#document-edition-status-3")
        self.assertIsNotNone(edition)
        self.assertIn("Source-generated edition", edition.get_text())
        self.assertTrue(
            soup.select_one('.toc-panel a[href="#document-edition-status-3"]')
        )
        self.assertEqual(len(soup.select("#document-edition-status-3")), 1)

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
        body_text = []
        for page in reader.pages:
            page.extract_text(visitor_text=lambda value, cm, tm, font, size:
                              body_text.append(value) if size * abs(cm[0]) > 9 else None)
        self.assertEqual("\n".join(body_text).count("A section"), 1)
        self.assertEqual(text.count("A subsection"), 1)

    def test_end_matter_shares_print_hierarchy_and_metadata_visibility_is_independent(self):
        self.version.metadata.update(
            title_layout="compact",
            metadata_page=True,
            work_type="article",
        )
        self.version.save(update_fields=["metadata"])
        layouts = []
        original_render = HTML.render

        def capture_layout(renderer, *args, **kwargs):
            document = original_render(renderer, *args, **kwargs)
            layouts.append(document)
            return document

        with patch.object(HTML, "render", capture_layout):
            pdf = self.pdf()
        text = "\n".join(page.extract_text() for page in pdf.pages)
        self.assertIn("Metadata", text)
        self.assertEqual(text.count("Edition and review status"), 1)

        styles = {}

        def collect(box):
            element = getattr(box, "element", None)
            if element is not None and element.get("id") in {
                "document-metadata", "document-edition-status",
            }:
                styles[element.get("id")] = box.style
            for child in getattr(box, "children", []):
                collect(child)

        for page in layouts[-1].pages:
            collect(page._page_box)
        metadata_style = styles["document-metadata"]
        edition_style = styles["document-edition-status"]
        for prop in ("font_family", "font_size", "line_height", "max_width"):
            self.assertEqual(metadata_style[prop], edition_style[prop], prop)
        self.assertEqual(metadata_style["border_top_style"], "solid")
        self.assertEqual(edition_style["border_top_style"], "none")

        self.version.metadata["metadata_page"] = False
        self.version.save(update_fields=["metadata"])
        reader = BeautifulSoup(
            self.client.get(f"/versions/{self.version.pk}/").content, "html.parser",
        )
        self.assertIsNone(reader.select_one(".document-metadata-page"))
        self.assertEqual(len(reader.select(".document-edition-status")), 1)
        pdf = self.pdf()
        text = "\n".join(page.extract_text() for page in pdf.pages)
        self.assertNotIn("Metadata", text)
        self.assertEqual(text.count("Edition and review status"), 1)

    def test_running_furniture_bounds_balance_with_body_frame_on_continuation_pages(self):
        self.version.metadata.update(
            work_type="article", title_layout="compact", metadata_page=False,
        )
        self.version.structure["toc"] = [
            {"id": "geometry-section", "level": 2, "title": "Geometry section"},
        ]
        self.version.html = (
            '<section id="geometry-section"><h2 data-pdf-section="Geometry section">'
            'Geometry section</h2>'
            + '<p style="text-indent:0">Geometry body sentence. '
            + "Readable continuation text. " * 800 + "</p>"
            + "</section>"
        )
        self.version.save(update_fields=["metadata", "structure", "html"])
        layouts = []
        original_render = HTML.render

        def capture_layout(renderer, *args, **kwargs):
            document = original_render(renderer, *args, **kwargs)
            layouts.append(document)
            return document

        with patch.object(HTML, "render", capture_layout):
            pdf = self.pdf()
        page = next(
            page for page in pdf.pages[1:]
            if "Print test" in page.extract_text()
            and "Readable continuation text" in page.extract_text()
        )
        page_width = float(page.mediabox.width)
        page_height = float(page.mediabox.height)
        runs = []

        def capture_text(text, cm, tm, font, size):
            if not text.strip():
                return
            x = cm[0] * tm[4] + cm[2] * tm[5] + cm[4]
            y = cm[1] * tm[4] + cm[3] * tm[5] + cm[5]
            descriptor = font.get("/FontDescriptor", {}) if font else {}
            if hasattr(descriptor, "get_object"):
                descriptor = descriptor.get_object()
            ascent = float(descriptor.get("/Ascent", 750)) * size / 1000
            descent = float(descriptor.get("/Descent", -250)) * size / 1000
            widths = font.get("/Widths") if font else None
            first = int(font.get("/FirstChar", 0)) if font else 0
            width = (
                sum(float(widths[ord(char) - first]) for char in text
                    if widths and first <= ord(char) < first + len(widths)) * size / 1000
                if widths else len(text) * size * 0.5
            )
            runs.append((text, x, y, x + width, y + ascent, y + descent))

        page.extract_text(visitor_text=capture_text)
        page_index = next(index for index, candidate in enumerate(pdf.pages) if candidate is page)
        rendered_page = layouts[-1].pages[page_index]._page_box
        margin_boxes = {
            box.at_keyword: box for box in rendered_page.children
            if hasattr(box, "at_keyword")
        }
        margin_lines = {
            key: next(box for box in margin_box.descendants()
                      if type(box).__name__ == "LineBox")
            for key, margin_box in margin_boxes.items()
        }
        top = margin_lines["@top-left"]
        right = margin_lines["@top-right"]
        footer = margin_lines["@bottom-center"]
        body = [run for run in runs if .2 * page_height < run[2] < .8 * page_height]
        body_frame = rendered_page
        body_left = body_frame.content_box_x()
        body_right = body_left + body_frame.width
        scale = 25.4 / 72
        css_scale = 25.4 / 96
        page_height_css = page_height * 96 / 72
        top_inset = top.position_y * css_scale
        bottom_inset = (page_height_css - footer.position_y - footer.height) * css_scale
        body_top = min((page_height - run[4]) * scale for run in body)
        body_bottom = max((page_height - run[5]) * scale for run in body)
        header_body_gap = body_top - (top.position_y + top.height) * css_scale
        body_footer_gap = footer.position_y * css_scale - body_bottom
        self.assertAlmostEqual(top.position_x * css_scale, 18, delta=1.5)
        self.assertAlmostEqual(min(run[1] for run in body) * scale, 18, delta=1.5)
        self.assertAlmostEqual(body_left * css_scale, 18, delta=1.5)
        self.assertAlmostEqual(body_right * css_scale,
                               page_width * scale - 18, delta=1.5)
        self.assertAlmostEqual((right.position_x + right.width) * css_scale,
                               page_width * scale - 18, delta=1.5)
        self.assertAlmostEqual((footer.position_x + footer.width / 2) * css_scale,
                               page_width * scale / 2, delta=1)
        self.assertAlmostEqual(top_inset, 18, delta=0.25)
        self.assertAlmostEqual(bottom_inset, 18, delta=0.25)
        self.assertAlmostEqual(top_inset, bottom_inset, delta=1.5)
        self.assertAlmostEqual(body_frame.content_box_y() * css_scale, 30, delta=0.25)
        self.assertGreater(
            (body_frame.content_box_y() - top.position_y - top.height) * css_scale, 4,
        )
        self.assertGreater(header_body_gap, 4)
        self.assertGreater(body_footer_gap, 4)
        stylesheet = self.version.stylesheet
        self.version.stylesheet += (
            "\n@media print {@page reading-content {"
            "@top-left {padding-top:6mm!important;}"
            "@top-right {padding-top:6mm!important;}"
            "@bottom-center {padding-bottom:6mm!important;}"
            "}}"
        )
        self.version.save(update_fields=["stylesheet"])
        try:
            with patch.object(HTML, "render", capture_layout):
                self.pdf()
        finally:
            self.version.stylesheet = stylesheet
            self.version.save(update_fields=["stylesheet"])
        centered_page = layouts[-1].pages[page_index]._page_box
        centered_boxes = {
            box.at_keyword: box for box in centered_page.children
            if hasattr(box, "at_keyword")
        }
        centered_top = next(
            box for box in centered_boxes["@top-left"].descendants()
            if type(box).__name__ == "LineBox"
        )
        centered_footer = next(
            box for box in centered_boxes["@bottom-center"].descendants()
            if type(box).__name__ == "LineBox"
        )
        centered_top_inset = centered_top.position_y * css_scale
        centered_bottom_inset = (
            page_height_css - centered_footer.position_y - centered_footer.height
        ) * css_scale
        self.assertAlmostEqual(centered_top_inset, 6, delta=0.25)
        self.assertAlmostEqual(centered_bottom_inset, 6, delta=0.25)
        self.assertLess(abs(top_inset - 18), abs(centered_top_inset - 18))
        self.assertLess(abs(bottom_inset - 18), abs(centered_bottom_inset - 18))

    def test_title_based_filename_preserves_unicode_and_is_filesystem_safe(self):
        for title, expected in [
            ("Print test", "Print test.pdf"),
            ("La homiĝo – étude", "La homiĝo – étude.pdf"),
            ("Why? Now", "Why - Now.pdf"),
            ("Title: Subtitle", "Title - Subtitle.pdf"),
            ("A/B", "A - B.pdf"),
            ('Why? A/B: "test"', "Why - A - B - test-.pdf"),
            ("A?? / : B", "A - B.pdf"),
            (" A ? B ", "A - B.pdf"),
            ("keep-this — and this", "keep-this — and this.pdf"),
            ("../CON", "-CON.pdf"),
            ("CON", "_CON.pdf"),
            ("NUL.txt", "_NUL.txt.pdf"),
            (" . ", "Untitled.pdf"),
            ("line\r\nbreak", "line - break.pdf"),
            ("?title?", "-title-.pdf"),
            ("title?.", "title-.pdf"),
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
        archived = directory / f"{self.version.pk}-{self.version.identity}-{APP_VERSION}.pdf"
        previous_policy = directory / (
            f"{self.version.pk}-{self.version.identity}-{APP_VERSION}-"
            f"p{PDF_PRESENTATION_VERSION - 1}.pdf"
        )
        archived.write_bytes(b"%PDF-archived")
        previous_policy.write_bytes(b"%PDF-old-presentation")
        with patch("library.services.pdf.subprocess.run", side_effect=build) as run:
            path = cached_pdf(self.version)
            self.assertTrue(path.name.endswith(f"-p{PDF_PRESENTATION_VERSION}.pdf"))
            self.assertEqual(path.read_bytes(), b"%PDF-test")
            self.assertEqual(cached_pdf(self.version), path)
            run.assert_called_once()
            self.assertEqual(run.call_args.kwargs["timeout"], 120)
        self.assertEqual(archived.read_bytes(), b"%PDF-archived")
        self.assertEqual(previous_policy.read_bytes(), b"%PDF-old-presentation")
        archived.unlink()
        previous_policy.unlink()
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

    def test_pdf_contents_list_aligns_with_its_heading_and_indents_children(self):
        document = HTML(string="""<body class="publication-content">
          <section class="document-contents"><h2 id="h">Table of contents</h2>
          <ul id="root" class="editor-document-toc"><li><a href="#a">A</a>
          <ul id="child" class="editor-document-toc"><li><a href="#b">B</a></li></ul></li></ul>
          </section></body>""").render(stylesheets=[CSS(filename=str(STYLES / "print.css"))])
        found = {}

        def walk(box):
            element = getattr(box, "element", None)
            if element is not None and element.get("id") and box.element_tag in ("h2", "ul"):
                found.setdefault(element.get("id"), box)
            for child in getattr(box, "children", []):
                walk(child)
        walk(document.pages[0]._page_box)
        self.assertEqual(found["root"].content_box_x(), found["h"].content_box_x())
        self.assertAlmostEqual(found["child"].content_box_x() - found["root"].content_box_x(), 24)
        self.assertEqual(found["root"].style["list_style_type"], "none")

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
                CSS(string="@page {size: 100mm 100mm; margin: 10mm} "
                           "@page reading-content {margin: 10mm}"),
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
            heading_page_index = next(
                index for index, text in enumerate(pages) if f"Chapter marker {i}" in text
            )
            heading_page = pages[heading_page_index]
            self.assertTrue(
                f"Caption {i}." in heading_page
                or any(f"Paragraph {i}-{j}." in heading_page for j in range(6))
            )
            self.assertEqual(complete.count(f"Caption {i}."), 1)
            for j in range(6):
                self.assertEqual(complete.count(f"Paragraph {i}-{j}."), 1)
                if j:
                    self.assertLess(
                        complete.index(f"Paragraph {i}-{j - 1}."),
                        complete.index(f"Paragraph {i}-{j}."),
                    )
            if i:
                self.assertLess(
                    complete.index(f"Paragraph {i - 1}-5."),
                    complete.index(f"Paragraph {i}-0."),
                )
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
