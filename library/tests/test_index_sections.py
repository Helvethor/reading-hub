import json
from copy import deepcopy
from dataclasses import asdict

from bs4 import BeautifulSoup
from django.test import TestCase
from django.urls import reverse

from library.correction_views import preview
from library.models import ContentOrganization, CrawlCapture
from library.services.corrections import (
    baseline,
    block_rows,
    digest,
    extraction,
    save_correction,
)
from library.services.errors import ImportFailure
from library.services.fetch import Response
from library.services.organizations import (
    change_plan,
    commit_change,
    current_spec,
    preview_change,
    retained_manifest,
    validate_spec,
)
from library.services.pipeline import format_rendition
from library.services.storage import save_response
from library.sources.adapters import discover, parse_html
from library.sources.index_sections import content, sections, selected
from library.sources.normalize import make_id, normalize
from library.tests import test_organizations
from library.tests.test_sources import BOOK, PARAGRAPH, book_index


def mixed_index():
    html = book_index().decode("windows-1252")
    extra = (
        '<blockquote><table><tr><td><a href="chapter1.htm">First</a>'
        '<a href="chapter2.htm">Second</a></td></tr></table></blockquote>'
        '<p class="footer">Download navigation</p><hr>'
        '<h3 id="editorial">Endnotes</h3>'
        f'<p id="history">Editorial publication history. {PARAGRAPH}</p>'
        '<p>Read <a href="chapter2.htm#section">the second chapter</a>.</p>'
        '<hr><p class="footer">NEXT</p>'
    )
    return html.replace("</body>", extra + "</body>").encode("windows-1252")


class IndexSectionTests(TestCase):
    def setUp(self):
        test_organizations.OrganizationTests.setUp(self)
        # Exercise older explicit section-only organizations alongside the new default.
        self.spec["parts"] = [part for part in self.spec["parts"] if part["url"] != BOOK]
        self.spec["parts"].extend(
            asdict(part) for part, _ in sections(parse_html(mixed_index()), BOOK)
        )

    def response(self, url, *, asset=False):
        if url == BOOK:
            return Response(url, mixed_index(), "text/html", {"content-type": "text/html"})
        return test_organizations.OrganizationTests.response(self, url, asset=asset)

    def capture(self):
        return CrawlCapture.objects.create(
            site=self.sites["www.marxists.org"],
            url=BOOK,
            response=save_response(self.response(BOOK), BOOK),
        )

    def test_discovery_and_book_format_include_bounded_editorial_material(self):
        self.assertIn("Editorial publication history.", self.book.html)
        self.assertNotIn("Download navigation", self.book.html)
        self.assertNotIn(">NEXT<", self.book.html)
        self.assertEqual(len(self.book.structure["parts"]), 3)
        part = self.book.structure["parts"][0]
        self.assertEqual(part["url"], BOOK)
        self.assertEqual(part["title"], "Contents")
        self.assertEqual(part["role"], "preface")
        self.assertNotIn("section", part)
        self.assertEqual(part["origin"], "contents-page")
        self.assertEqual(part["authorship"], "unspecified")
        self.assertNotIn("Contents-page material; authorship not inferred.", self.book.html)
        self.assertNotIn("source-provenance", self.book.html)
        soup = BeautifulSoup(self.book.html, "html.parser")
        self.assertEqual(len([h for h in soup.select("h2,h3") if h.get_text() == "Endnotes"]), 1)
        link = soup.find("a", string="the second chapter")
        self.assertIsNotNone(soup.find(id=link["href"][1:]))
        self.assertEqual(len(self.book.snapshot.manifest["pages"]), 3)

    def test_index_editor_exposes_section_and_corrections_apply_in_assembly(self):
        capture = self.capture()
        source, _, body, _ = extraction(capture)
        rows = block_rows(body)
        index = next(row["index"] for row in rows if row["text"].startswith("Editorial"))
        save_correction(
            capture, self.reviewer, {"blocks": [{"index": index, "action": "exclude"}]}, 0, "Remove"
        )
        manifest, warnings = retained_manifest(self.spec)
        _, html, _, _, _ = format_rendition(manifest, warnings)
        self.assertNotIn("Editorial publication history.", html)
        self.assertIn("the second chapter", html)
        response = self.client.get(reverse("correction-workspace", args=[capture.pk]))
        self.assertRedirects(
            response,
            reverse("document-editor", args=[self.book.pk])
            + f"?review_capture={capture.pk}&review_version={self.book.pk}",
            fetch_redirect_response=False,
        )
        self.assertTrue(rows)
        self.assertEqual(baseline(source, body)["blocks"], rows)

    def test_default_index_is_first_editable_part_in_import_reformat_and_organization(self):
        spec = current_spec(BOOK)
        self.assertEqual(spec["parts"][0]["url"], BOOK)
        self.assertEqual(spec["parts"][0]["role"], "preface")
        capture = self.capture()
        response = self.client.get(reverse("correction-workspace", args=[capture.pk]))
        self.assertEqual(response.status_code, 302)
        source, part, body, _ = extraction(capture, excerpt_mapping=True)
        result = preview(source, part, body, {})
        self.assertIn("Editorial publication history.", result["html"])
        self.assertIn("First chapter", result["html"])
        self.assertIn("data-excerpt-block", result["html"])
        manifest = deepcopy(self.book.snapshot.manifest)
        manifest["parts"] = [part for part in manifest["parts"] if part["url"] != BOOK]
        old_html = self.book.html
        _, html, structure, _, _ = format_rendition(manifest, [])
        self.assertEqual(structure["parts"][0]["url"], BOOK)
        self.assertIn("Editorial publication history.", html)
        self.assertNotIn("data-excerpt-block", html)
        self.book.refresh_from_db()
        self.assertEqual(self.book.html, old_html)

    def test_omitting_section_publishes_only_book_and_keeps_source_available(self):
        changed = deepcopy(self.spec)
        changed["parts"] = [part for part in changed["parts"] if not part.get("section")]
        before, after = change_plan(changed)
        self.assertEqual(len(after), 1)
        result = preview_change(before, after)
        result["digests"] = [work["digest"] for work in result["works"]]
        decision = commit_change(result, self.reviewer, "Omit editorial appendix")
        self.assertEqual(len(decision.after), 1)
        self.assertEqual(len(current_spec(BOOK)["parts"]), 2)
        self.assertEqual(len(ContentOrganization.objects.get().rendition.structure["parts"]), 2)
        response = self.client.get(reverse("content-organization"), {"url": BOOK})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(sections(parse_html(mixed_index()), BOOK)[0][0].title, "Endnotes")

    def test_legacy_metadata_only_index_correction_remains_applicable(self):
        capture = self.capture()
        correction = save_correction(
            capture, self.reviewer, {"metadata": {"topics": ["Editorial"]}}, 0, "Metadata"
        )
        correction.original["blocks"] = []
        correction.original["body_digest"] = digest("<div></div>")
        correction.save(update_fields=["original"])
        manifest, warnings = retained_manifest(self.spec)
        source, html, _, _, _ = format_rendition(manifest, warnings)
        self.assertEqual(source.metadata["topics"], ["Editorial"])
        self.assertIn("Editorial publication history.", html)
        response = self.client.get(reverse("correction-workspace", args=[capture.pk]))
        self.assertEqual(response.status_code, 302)
        from library.services.correction_patterns import current_compatibility

        result = current_compatibility(correction.profile)["results"][0]
        self.assertEqual(result["status"], "compatible")
        self.assertTrue(result["legacy_index_metadata"])

    def test_reviewed_membership_is_not_overwritten_and_candidates_are_exposed(self):
        old = deepcopy(self.spec)
        old["parts"] = [part for part in old["parts"] if not part.get("section")]
        entry = self.sites["www.marxists.org"].entries.get(url=BOOK)
        ContentOrganization.objects.create(entry=entry, specification=old, rendition=self.book)
        self.assertEqual(current_spec(BOOK), old)
        manifest, warnings = retained_manifest(old)
        _, html, _, _, _ = format_rendition(manifest, warnings)
        self.assertNotIn("Editorial publication history.", html)
        response = self.client.get(reverse("content-organization"), {"url": BOOK})
        self.assertEqual(response.status_code, 302)
        panel = self.client.get(reverse("document-editor-membership", args=[self.book.pk]))
        self.assertEqual(panel.status_code, 200)
        self.assertEqual(json.loads(panel.context["specification"]), old)
        self.assertEqual(sections(parse_html(mixed_index()), BOOK)[0][0].title, "Endnotes")

    def test_section_identity_validation_and_missing_evidence_fail_explicitly(self):
        spec = deepcopy(self.spec)
        spec["parts"].append(deepcopy(spec["parts"][-1]))
        with self.assertRaisesMessage(ValueError, "Duplicate page"):
            validate_spec(spec)
        spec = deepcopy(self.spec)
        spec["parts"].append({"url": BOOK, "title": "Full contents page", "role": "chapter"})
        with self.assertRaisesMessage(ValueError, "Duplicate page"):
            validate_spec(spec)
        spec = deepcopy(self.spec)
        spec["parts"][-1]["url"] = BOOK.replace("index.htm", "chapter1.htm")
        with self.assertRaisesMessage(ValueError, "own contents"):
            validate_spec(spec)
        spec = deepcopy(self.spec)
        spec["parts"][-1]["section"] = "missing-section"
        manifest, warnings = retained_manifest(spec)
        with self.assertRaisesMessage(ImportFailure, "absent or excluded"):
            format_rendition(manifest, warnings, spec)

    def test_multiple_sections_same_url_preserve_links_and_omit_without_detaching_root(self):
        soup = parse_html(mixed_index())
        heading = soup.new_tag("h3")
        heading.string = "Editorial appendix"
        paragraph = soup.new_tag("p")
        paragraph.string = PARAGRAPH
        soup.body.append(heading)
        soup.body.append(paragraph)
        parts = sections(soup, BOOK)
        self.assertEqual(len(parts), 2)
        proposed = deepcopy(self.spec)
        proposed["parts"] = [part for part in proposed["parts"] if not part.get("section")]
        proposed["parts"].extend(asdict(part) for part, _ in parts)
        self.assertEqual(len(validate_spec(proposed)["parts"]), 4)
        extracted = content(soup, BOOK)
        self.assertNotIn("Download navigation", extracted.get_text())
        self.assertIn("Editorial appendix", selected(extracted, parts[-1][0].section).get_text())
        first = selected(extracted, parts[0][0].section, use_source_headings=False)
        link = soup.new_tag("a", href=BOOK)
        link.string = "Source contents"
        first.append(link)
        target_link = soup.new_tag("a", href=BOOK + "#editorial")
        target_link.string = "Editorial heading"
        second = selected(extracted, parts[-1][0].section, use_source_headings=False)
        second.append(target_link)
        source = discover(soup, BOOK)
        html, structure = normalize([(parts[0][0], first), (parts[1][0], second)], source, {})
        output = BeautifulSoup(html, "html.parser")
        self.assertEqual(output.find("a", string="Source contents")["href"], BOOK)
        target = make_id("c1", "editorial")
        self.assertEqual(output.find("a", string="Editorial heading")["href"], "#" + target)
        self.assertIsNotNone(output.find(id=target))
        self.assertEqual(len({part["section"] for part in structure["parts"]}), 2)

    def test_navigation_only_index_does_not_create_readable_sections(self):
        soup = parse_html(book_index())
        self.assertEqual(sections(soup, BOOK), [])
        self.assertEqual(len(discover(soup, BOOK).parts), 3)
