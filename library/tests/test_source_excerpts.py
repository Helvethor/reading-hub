from copy import deepcopy
from uuid import uuid4

from bs4 import BeautifulSoup
from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from library.models import (
    CatalogueEntry,
    ContentOrganizationDecision,
    CrawlCapture,
    SourceCorrection,
    SourceExcerptRevision,
)
from library.services.corrections import retain_rendition_capture
from library.services.errors import ImportFailure
from library.services.fetch import Response
from library.services.organizations import (
    change_plan,
    commit_change,
    current_spec,
    graph_membership,
    preview_change,
    retained_manifest,
    undo_plan,
    validate_spec,
)
from library.services.pipeline import format_rendition
from library.services.source_excerpts import (
    definitions_for_capture,
    descriptor,
    evidence,
    normalized_preview,
    revision_data,
    save_definition,
    select_excerpt,
)
from library.services.storage import save_response
from library.sources.base import parse_html
from library.sources.index_sections import sections
from library.tests import test_organizations
from library.tests.test_index_sections import mixed_index
from library.tests.test_sources import BOOK, PARAGRAPH, book_index, chapter


def editorial_index():
    html = book_index().decode("windows-1252")
    return html.replace(
        "</body>",
        '<p id="history-one">History before contents. <em>Original emphasis.</em></p>'
        '<p id="history-two">Second history paragraph.</p>'
        '<hr><h3 id="endnotes">Endnotes</h3>'
        '<p id="note-one">Editorial endnote, without an automatic section.</p>'
        "<p>Another note paragraph.</p></body>",
    ).encode("windows-1252")


class SourceExcerptTests(TestCase):
    def setUp(self):
        test_organizations.OrganizationTests.setUp(self)
        # These drafts explicitly replace the default whole index with selected excerpts.
        self.spec["parts"] = [part for part in self.spec["parts"] if part["url"] != BOOK]

    def response(self, url, *, asset=False):
        if url == BOOK:
            return Response(url, editorial_index(), "text/html", {})
        return test_organizations.OrganizationTests.response(self, url, asset=asset)

    def entry(self, url=BOOK):
        return retained_manifest({"url": url, "parts": []})[0]["pages"][0]

    def test_retained_normalized_preview_exposes_omitted_prose_with_exact_block_markers(self):
        entry = self.entry()
        rows = evidence(entry)["blocks"]
        html = normalized_preview(entry)
        parsed = BeautifulSoup(html, "html.parser")
        index = next(row["index"] for row in rows if row["text"].startswith("History before"))
        paragraph = parsed.select_one(f'[data-excerpt-block="{index}"]')
        self.assertIn("History before", paragraph.get_text())
        self.assertEqual(paragraph.select_one("em").get_text(), "Original emphasis.")
        self.assertFalse(parsed.select("a[href], img[src^='http'], script, style, iframe"))
        self.assertNotIn("data-preview-block", html)

    def test_retained_preview_disables_links_without_changing_source_or_publication(self):
        raw = b"""<body><p data-excerpt-block="999" onclick="alert(1)">One
        <a href="#not-retained">note</a><script>alert(2)</script></p>
        <p>Two <img src="https://www.marxists.org/image.jpg" alt="Figure"></p></body>"""
        entry = save_response(Response(BOOK, raw, "text/html", {}), BOOK)
        html = normalized_preview(entry)
        parsed = BeautifulSoup(html, "html.parser")
        self.assertEqual(
            [int(node["data-excerpt-block"]) for node in parsed.select("[data-excerpt-block]")],
            [0, 1],
        )
        self.assertFalse(parsed.select("[onclick], script, a[href], img[src]"))
        self.assertIn("Image unavailable", parsed.get_text())
        selected = select_excerpt(entry, {
            "version": 1, "source_digest": entry["digest"], "start": 0, "end": 0,
        })
        self.assertEqual(selected.select_one("a")["href"], "#not-retained")

    def selection(self, entry, start_text, end_text=None):
        rows = evidence(entry)["blocks"]
        start = next(row["index"] for row in rows if row["text"].startswith(start_text))
        end = next(row["index"] for row in rows if row["text"].startswith(end_text or start_text))
        return {"version": 1, "source_digest": entry["digest"], "start": start, "end": end}

    def part(self, entry, start_text, end_text=None, title="Editorial history", role="preface"):
        return {
            "url": entry["url"],
            "title": title,
            "role": role,
            "group": "",
            "use_source_headings": False,
            "excerpt": self.selection(entry, start_text, end_text),
        }

    def test_manual_unheaded_index_prose_and_endnotes_can_be_placed_independently(self):
        entry = self.entry()
        history = self.part(entry, "History before", "Second history")
        notes = self.part(entry, "Editorial endnote", "Another note", "Endnotes", "appendix")
        spec = deepcopy(self.spec)
        spec["parts"] = [history, *spec["parts"], notes]
        before, after = change_plan(spec)
        report = preview_change(before, after)
        html = report["works"][0]["html"]
        parsed = BeautifulSoup(html, "html.parser")
        assembled = parsed.select("section")
        self.assertIn("History before", assembled[0].get_text())
        self.assertIn("Editorial endnote", assembled[-1].get_text())
        self.assertNotIn("Editorial endnote", assembled[1].get_text())
        self.assertIn("<em>Original emphasis.</em>", html)
        parts = report["works"][0]["structure"]["parts"]
        self.assertEqual(parts[0]["origin"], "reviewed-source-excerpt")
        self.assertEqual(parts[0]["authorship"], "unspecified")
        self.assertEqual(parts[0]["excerpt"], history["excerpt"])
        self.assertEqual(SourceCorrection.objects.count(), 0)
        self.assertEqual(ContentOrganizationDecision.objects.count(), 0)

    def test_subwork_can_use_only_a_selected_range_and_publication_is_undoable(self):
        chapter = self.spec["parts"][0]["url"]
        entry = self.entry(chapter)
        rows = evidence(entry)["blocks"]
        paragraph = next(row for row in rows if row["text"].startswith(PARAGRAPH[:30]))
        spec = deepcopy(self.spec)
        spec["parts"][0] = {
            "url": chapter,
            "title": "Selected chapter passage",
            "role": "chapter",
            "excerpt": {
                "version": 1,
                "source_digest": entry["digest"],
                "start": paragraph["index"],
                "end": paragraph["index"],
            },
        }
        before, after = change_plan(spec)
        preview = preview_change(before, after)
        preview["digests"] = [work["digest"] for work in preview["works"]]
        before_count = CatalogueEntry.objects.count()
        decision = commit_change(preview, self.reviewer, "Use only the selected chapter passage")
        self.assertEqual(CatalogueEntry.objects.count(), before_count)
        member = CatalogueEntry.objects.get(url=chapter)
        self.assertEqual(member.book.url, BOOK)
        self.assertEqual(current_spec(BOOK)["parts"][0]["excerpt"], spec["parts"][0]["excerpt"])
        undo_before, undo_after = undo_plan(decision)
        undo = preview_change(undo_before, undo_after)
        undo["digests"] = [work["digest"] for work in undo["works"]]
        commit_change(undo, self.reviewer, "Restore the complete chapter", undo_of=decision)
        self.assertFalse(current_spec(BOOK)["parts"][0].get("excerpt"))

    def test_whole_page_overlap_duplicate_ranges_and_automatic_section_overlap_rejected(self):
        entry = self.entry(self.spec["parts"][0]["url"])
        part = self.part(entry, PARAGRAPH[:30])
        for parts in (
            [self.spec["parts"][0], part],
            [part, self.spec["parts"][0]],
            [part, deepcopy(part)],
        ):
            with self.subTest(parts=parts), self.assertRaises(ValueError):
                validate_spec({**self.spec, "parts": parts})

    def test_changed_source_and_broken_reference_block_preview_explicitly(self):
        entry = self.entry()
        spec = deepcopy(self.spec)
        part = self.part(entry, "History before")
        part["excerpt"]["source_digest"] = "0" * 64
        spec["parts"].insert(0, part)
        with self.assertRaisesMessage(ImportFailure, "Excerpt source changed"):
            manifest, warnings = retained_manifest(spec)
            format_rendition(manifest, warnings, spec)

        updated = (
            editorial_index()
            .decode("windows-1252")
            .replace(
                "History before contents.", 'History before contents. <a href="#omitted">Jump</a>'
            )
            .replace("</body>", '<p id="omitted">Omitted target</p></body>')
            .encode("windows-1252")
        )
        capture = CrawlCapture.objects.create(
            site=self.sites["www.marxists.org"],
            url=BOOK,
            response=save_response(Response(BOOK, updated, "text/html", {}), BOOK),
        )
        entry = {**capture.response, "url": BOOK}
        spec["parts"][0] = self.part(entry, "History before")
        with self.assertRaisesMessage(ImportFailure, "Unresolved internal link"):
            manifest, warnings = retained_manifest(spec)
            format_rendition(manifest, warnings, spec)

    def test_evidence_endpoint_is_reviewer_only_read_only_and_validates_ranges(self):
        capture = retain_rendition_capture(self.book, 0)
        url = reverse("source-excerpts", args=[capture.pk])
        params = {}
        before = ContentOrganizationDecision.objects.count()
        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertTrue(any(row["text"].startswith("History before") for row in result["blocks"]))
        selection = self.selection(self.entry(), "History before", "Second history")
        selected = select_excerpt(self.entry(), selection).get_text(" ", strip=True)
        self.assertIn("Second history", selected)
        self.assertNotIn("Endnotes", selected)
        with self.assertRaises((ValueError, ImportFailure)):
            select_excerpt(self.entry(), {**selection, "start": "bad", "end": 0})
        self.assertEqual(ContentOrganizationDecision.objects.count(), before)
        self.assertEqual(Client().get(url, params).status_code, 302)
        regular = get_user_model().objects.create_user("ordinary-reader")
        self.client.force_login(regular)
        self.assertEqual(self.client.get(url, params).status_code, 403)

    def test_borrowed_excerpt_does_not_claim_catalogue_membership(self):
        entry = self.entry(self.spec["parts"][0]["url"])
        other = {
            "url": "https://www.marxists.org/archive/example/index.htm",
            "title": "Other work",
            "book": True,
            "parts": [self.part(entry, PARAGRAPH[:30])],
        }
        self.assertEqual(graph_membership([other]), {})

    def publish(self, spec):
        before, after = change_plan(spec)
        preview = preview_change(before, after)
        preview["digests"] = [work["digest"] for work in preview["works"]]
        return commit_change(preview, self.reviewer, "Verified source excerpt organization")

    def other_book(self, parts):
        url = "https://www.marxists.org/archive/example/selection.htm"
        CrawlCapture.objects.create(
            site=self.sites["www.marxists.org"],
            url=url,
            response=save_response(Response(url, chapter(3), "text/html", {}), url),
        )
        return {"url": url, "title": "Other book", "book": True, "parts": parts}

    def test_omitting_borrowed_excerpt_does_not_detach_or_publish_its_source(self):
        entry = self.entry(self.spec["parts"][0]["url"])
        other = self.other_book(
            [
                self.part(entry, PARAGRAPH[:30]),
                deepcopy(self.spec["parts"][1]),
            ]
        )
        self.publish(other)
        changed = current_spec(other["url"])
        changed["parts"] = changed["parts"][1:]
        before, after = change_plan(changed)
        self.assertEqual([spec["url"] for spec in after], [other["url"]])
        preview = preview_change(before, after)
        preview["digests"] = [work["digest"] for work in preview["works"]]
        self.assertEqual(len(preview["works"]), 1)
        commit_change(preview, self.reviewer, "Omit only the borrowed excerpt")
        self.assertEqual(CatalogueEntry.objects.get(url=entry["url"]).book.url, BOOK)

    def test_detaching_last_owned_excerpt_restores_whole_source_and_undo_membership(self):
        entry = self.entry(self.spec["parts"][0]["url"])
        selected = deepcopy(self.spec)
        selected["parts"][0] = self.part(entry, PARAGRAPH[:30])
        self.publish(selected)
        changed = current_spec(BOOK)
        changed["parts"] = changed["parts"][1:]
        decision = self.publish(changed)
        self.assertIsNone(CatalogueEntry.objects.get(url=entry["url"]).book_id)
        self.assertFalse(current_spec(entry["url"])["parts"][0].get("excerpt"))
        before, after = undo_plan(decision)
        preview = preview_change(before, after, undo_of=decision)
        preview["digests"] = [work["digest"] for work in preview["works"]]
        self.assertEqual(len(preview["works"]), 1)
        commit_change(preview, self.reviewer, "Restore the excerpt membership", undo_of=decision)
        self.assertEqual(CatalogueEntry.objects.get(url=entry["url"]).book.url, BOOK)
        self.assertEqual(current_spec(BOOK)["parts"][0]["excerpt"], selected["parts"][0]["excerpt"])

    def test_borrowing_excerpt_while_moving_other_chapter_keeps_donor_source(self):
        entry = self.entry(self.spec["parts"][0]["url"])
        other = self.other_book(
            [
                self.part(entry, PARAGRAPH[:30]),
                deepcopy(self.spec["parts"][1]),
            ]
        )
        self.publish(other)
        self.assertEqual(CatalogueEntry.objects.get(url=entry["url"]).book.url, BOOK)
        self.assertEqual(len(current_spec(BOOK)["parts"]), 2)
        self.assertEqual(current_spec(BOOK)["parts"][1]["url"], entry["url"])

    def test_raw_boundaries_are_inclusive_safe_and_must_share_a_container(self):
        markup = (
            "<html><body><p>First paragraph</p><script>unsafe()</script>"
            '<p>Last <a id="kept">paragraph</a></p>'
            "<div><p>Different container</p></div></body></html>"
        ).encode()
        entry = save_response(Response(BOOK, markup, "text/html", {}), BOOK)
        selection = self.selection(entry, "First paragraph", "Last paragraph")
        body = select_excerpt(entry, selection)
        self.assertEqual(len(body.select("p")), 2)
        self.assertIsNotNone(body.find(id="kept"))
        self.assertNotIn("unsafe", str(body))
        selection = self.selection(entry, "First paragraph", "Different container")
        with self.assertRaisesMessage(ValueError, "same container"):
            select_excerpt(entry, selection)

    def test_nonoverlapping_manual_excerpt_can_coexist_with_legacy_endnotes(self):
        raw = (
            mixed_index()
            .decode("windows-1252")
            .replace("<body>", "<body><p>Additional introductory material.</p>")
            .encode("windows-1252")
        )
        capture = CrawlCapture.objects.create(
            site=self.sites["www.marxists.org"],
            url=BOOK,
            response=save_response(Response(BOOK, raw, "text/html", {}), BOOK),
        )
        entry = {**capture.response, "url": BOOK}
        spec = deepcopy(self.spec)
        for part, _ in sections(parse_html(raw), BOOK):
            spec["parts"].append(
                {
                    "url": part.url,
                    "title": part.title,
                    "role": part.role,
                    "section": part.section,
                }
            )
        spec["parts"].insert(0, self.part(entry, "Additional introductory"))
        before, after = change_plan(spec)
        preview = preview_change(before, after)
        self.assertIn("Additional introductory material.", preview["works"][0]["html"])
        self.assertIn("Editorial publication history.", preview["works"][0]["html"])
        spec["parts"][0] = self.part(entry, "Editorial publication history.")
        with self.assertRaisesMessage(ValueError, "overlap"):
            manifest, warnings = retained_manifest(spec)
            format_rendition(manifest, warnings, spec)

    def named(self, *, indices=None, capture=None, **changes):
        capture = capture or retain_rendition_capture(self.book, 0)
        selection = self.selection(
            {**capture.response, "url": capture.url}, "History before", "Second history"
        )
        return save_definition(
            capture,
            self.reviewer,
            {
                "name": "Editorial history",
                "reason": "Verified original source grouping",
                "source_digest": capture.response["digest"],
                "blocks": indices
                if indices is not None
                else list(range(selection["start"], selection["end"] + 1)),
                **changes,
            },
        )

    def test_named_noncontiguous_selection_preserves_order_markup_and_omits_gaps(self):
        entry = self.entry()
        first = self.selection(entry, "History before")["start"]
        last = self.selection(entry, "Editorial endnote")["start"]
        row = self.named(indices=[first, last])
        value = revision_data(row)["excerpt"]
        body = select_excerpt(entry, value)
        self.assertIn("<em>Original emphasis.</em>", str(body))
        self.assertNotIn("Second history", body.get_text())
        self.assertLess(
            body.get_text().index("History before"), body.get_text().index("Editorial endnote")
        )
        spec = deepcopy(self.spec)
        spec["parts"].insert(
            0,
            {
                "url": BOOK,
                "title": "Independent displayed title",
                "role": "preface",
                "excerpt": value,
            },
        )
        before, after = change_plan(spec)
        preview = preview_change(before, after)
        self.assertEqual(preview["works"][0]["structure"]["parts"][0]["excerpt"], value)
        self.assertEqual(ContentOrganizationDecision.objects.count(), 0)
        self.assertEqual(SourceCorrection.objects.count(), 0)

    def test_named_selection_can_cross_containers_and_preserves_preceding_targets(self):
        entry = save_response(
            Response(
                BOOK,
                b"<body><div><p>First selected paragraph</p></div>"
                b'<p>Omitted paragraph</p><div><a name="note"></a> \n'
                b"<p>Selected note</p></div></body>",
                "text/html",
                {},
            ),
            BOOK,
        )
        value = {
            "version": 2,
            "definition": str(uuid4()),
            "revision": 1,
            "source_digest": entry["digest"],
            "blocks": [0, 2],
        }
        body = select_excerpt(entry, value)
        self.assertEqual(len(body.find_all("p")), 2)
        self.assertNotIn("Omitted paragraph", str(body))
        self.assertIsNotNone(body.find("a", attrs={"name": "note"}))

    def test_disjoint_named_parts_same_source_publish_independently(self):
        entry = self.entry()
        first_index = self.selection(entry, "History before")["start"]
        second_index = self.selection(entry, "Second history")["start"]
        first = self.named(indices=[first_index])
        second = self.named(indices=[second_index], name="Second excerpt")
        spec = deepcopy(self.spec)
        spec["parts"].insert(
            0,
            {
                "url": BOOK,
                "title": "Opening",
                "role": "preface",
                "excerpt": revision_data(first)["excerpt"],
            },
        )
        spec["parts"].append(
            {
                "url": BOOK,
                "title": "Closing",
                "role": "postscript",
                "excerpt": revision_data(second)["excerpt"],
            }
        )
        self.publish(spec)
        parts = self.book.document.latest().structure["parts"]
        self.assertEqual(parts[0]["title"], "Opening")
        self.assertEqual(parts[-1]["title"], "Closing")
        self.assertEqual(len(parts), len(self.spec["parts"]) + 2)
        self.assertEqual(CatalogueEntry.objects.filter(url=BOOK).count(), 1)

    def test_named_selection_does_not_silently_drop_a_link_to_omitted_block(self):
        raw = editorial_index().replace(
            b"History before contents.", b'History before contents. <a href="#history-two">Next</a>'
        )
        capture = CrawlCapture.objects.create(
            site=self.sites["www.marxists.org"],
            url=BOOK,
            response=save_response(Response(BOOK, raw, "text/html", {}), BOOK),
        )
        row = self.named(
            capture=capture,
            indices=[self.selection({**capture.response, "url": BOOK}, "History before")["start"]],
        )
        spec = deepcopy(self.spec)
        spec["parts"].insert(
            0,
            {
                "url": BOOK,
                "title": row.name,
                "role": "preface",
                "excerpt": revision_data(row)["excerpt"],
            },
        )
        before, after = change_plan(spec)
        with self.assertRaisesMessage(ImportFailure, "Unresolved internal link"):
            preview_change(before, after)

    def test_definition_rename_revision_delete_do_not_change_published_use(self):
        first = self.named()
        value = revision_data(first)["excerpt"]
        spec = deepcopy(self.spec)
        spec["parts"].insert(
            0,
            {
                "url": BOOK,
                "title": "Independent part title",
                "role": "preface",
                "excerpt": value,
            },
        )
        self.publish(spec)
        published = self.book.document.latest()
        original_html = published.html
        revised = self.named(
            definition=str(first.definition),
            revision=1,
            name="Renamed history",
            indices=[first.blocks[0]],
        )
        self.assertEqual(revised.revision, 2)
        self.assertEqual(current_spec(BOOK)["parts"][0]["excerpt"], value)
        published.refresh_from_db()
        self.assertEqual(published.html, original_html)
        workspace = self.client.get(reverse("source-excerpts", args=[first.capture.pk]))
        self.assertEqual(workspace.json()["definitions"][0]["name"], "Renamed history")
        deleted = self.named(
            definition=str(first.definition),
            revision=2,
            deleted=True,
        )
        self.assertEqual(deleted.revision, 3)
        self.assertTrue(definitions_for_capture(first.capture)[0]["deleted"])
        before, after = change_plan(current_spec(BOOK))
        preview = preview_change(before, after)
        self.assertIn("Second history", preview["works"][0]["html"])
        self.assertEqual(current_spec(BOOK)["parts"][0]["title"], "Independent part title")
        self.assertEqual(SourceExcerptRevision.objects.count(), 3)

    def test_adoption_is_explicit_and_organization_publication_is_undoable(self):
        first = self.named()
        spec = deepcopy(self.spec)
        spec["parts"].insert(
            0,
            {
                "url": BOOK,
                "title": "Kept display title",
                "role": "preface",
                "excerpt": revision_data(first)["excerpt"],
            },
        )
        self.publish(spec)
        second = self.named(definition=str(first.definition), revision=1, indices=[first.blocks[0]])
        adopted = current_spec(BOOK)
        adopted["parts"][0]["excerpt"] = revision_data(second)["excerpt"]
        decision = self.publish(adopted)
        self.assertEqual(current_spec(BOOK)["parts"][0]["excerpt"]["revision"], 2)
        before, after = undo_plan(decision)
        preview = preview_change(before, after, undo_of=decision)
        preview["digests"] = [work["digest"] for work in preview["works"]]
        commit_change(preview, self.reviewer, "Undo excerpt revision adoption", undo_of=decision)
        self.assertEqual(current_spec(BOOK)["parts"][0]["excerpt"]["revision"], 1)
        self.assertEqual(current_spec(BOOK)["parts"][0]["title"], "Kept display title")

    def test_overlapping_definitions_allowed_but_overlapping_inclusions_blocked(self):
        first, second = self.named(), self.named()
        self.assertNotEqual(first.definition, second.definition)
        spec = deepcopy(self.spec)
        for row in (first, second):
            spec["parts"].append(
                {
                    "url": BOOK,
                    "title": row.name,
                    "role": "appendix",
                    "excerpt": revision_data(row)["excerpt"],
                }
            )
        with self.assertRaisesMessage(ValueError, "Overlapping"):
            validate_spec(spec)
        spec["parts"].pop()
        spec["parts"][-1]["excerpt"]["blocks"] = [first.blocks[0]]
        with self.assertRaisesMessage(ValueError, "saved definition"):
            validate_spec(spec)

    def test_named_and_legacy_overlap_is_rejected_in_either_order(self):
        row = self.named()
        named = {
            "url": BOOK,
            "title": row.name,
            "role": "preface",
            "excerpt": revision_data(row)["excerpt"],
        }
        legacy = self.part(self.entry(), "Second history")
        for parts in ([named, legacy], [legacy, named]):
            with self.subTest(parts=parts), self.assertRaisesMessage(ValueError, "Overlapping"):
                validate_spec({**self.spec, "parts": parts})

    def test_definition_conflicts_source_binding_and_immutability(self):
        first = self.named()
        spec = deepcopy(self.spec)
        spec["parts"].insert(
            0,
            {
                "url": BOOK,
                "title": first.name,
                "role": "preface",
                "excerpt": revision_data(first)["excerpt"],
            },
        )
        manifest, warnings = retained_manifest(spec)
        manifest["pages"][0] = {
            **manifest["pages"][0],
            "headers": {"content-type": "text/html; charset=utf-8"},
        }
        with self.assertRaisesMessage(ImportFailure, "encoding evidence changed"):
            format_rendition(manifest, warnings, spec)
        with self.assertRaisesMessage(ValueError, "changed"):
            self.named(definition=str(first.definition), revision=0)
        with self.assertRaisesMessage(ImportFailure, "source changed"):
            self.named(source_digest="0" * 64)
        with self.assertRaisesMessage(ValueError, "ordered"):
            self.named(indices=list(reversed(first.blocks)))
        with self.assertRaisesMessage(ValueError, "ordered"):
            self.named(indices=[first.blocks[0], first.blocks[0]])
        other = CrawlCapture.objects.create(
            site=first.capture.site,
            url=BOOK,
            response=first.capture.response,
        )
        with self.assertRaisesMessage(ValueError, "does not belong"):
            self.named(capture=other, definition=str(first.definition), revision=1)
        self.assertEqual(definitions_for_capture(other), [])
        with self.assertRaisesMessage(ValueError, "immutable"):
            first.save()
        with self.assertRaisesMessage(ValueError, "immutable"):
            first.delete()
        with self.assertRaisesMessage(ValueError, "immutable"):
            SourceExcerptRevision.objects.filter(pk=first.pk).update(name="Changed")

    def test_excerpt_reasons_are_optional_for_create_rename_and_delete(self):
        capture = retain_rendition_capture(self.book, 0)
        selection = self.selection(self.entry(), "History before")
        endpoint = reverse("source-excerpts", args=[capture.pk])
        payload = {
            "name": "Editorial grouping",
            "source_digest": selection["source_digest"],
            "blocks": [selection["start"]],
        }
        response = self.client.post(endpoint, payload, content_type="application/json")
        self.assertEqual(response.status_code, 410)
        self.assertFalse(SourceExcerptRevision.objects.exists())
        first = revision_data(save_definition(capture, self.reviewer, payload))
        self.assertEqual(first["reason"], "")
        payload.update(
            definition=first["definition"], revision=1, name="Renamed grouping", reason=""
        )
        saved = save_definition(capture, self.reviewer, payload)
        self.assertEqual(saved.name, "Renamed grouping")
        payload.update(revision=2, deleted=True)
        payload.pop("reason")
        self.assertTrue(save_definition(capture, self.reviewer, payload).deleted)
        self.assertEqual(SourceExcerptRevision.objects.count(), 3)
        for invalid in (None, 3, "a" * 2001):
            with self.subTest(reason=type(invalid)):
                payload.update(reason=invalid)
                with self.assertRaises(ValueError):
                    save_definition(capture, self.reviewer, payload)

    def test_named_endpoint_permissions_csrf_errors_history_and_read_only_get(self):
        capture = retain_rendition_capture(self.book, 0)
        endpoint = reverse("source-excerpts", args=[capture.pk])
        response = self.client.get(endpoint)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["definitions"], [])
        self.assertEqual(SourceExcerptRevision.objects.count(), 0)
        self.assertEqual(Client().get(endpoint).status_code, 302)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.reviewer)
        self.assertEqual(
            csrf.post(endpoint, "{}", content_type="application/json").status_code, 403
        )
        selection = self.selection(self.entry(), "History before")
        payload = {
            "name": "Named history",
            "reason": "Reviewed selection",
            "source_digest": selection["source_digest"],
            "blocks": [selection["start"]],
        }
        response = self.client.post(endpoint, payload, content_type="application/json")
        self.assertEqual(response.status_code, 410)
        self.assertEqual(save_definition(capture, self.reviewer, payload).revision, 1)
        history = self.client.get(endpoint).json()["history"]
        self.assertEqual(history[0]["name"], "Named history")
        evidence_response = self.client.get(endpoint).json()
        self.assertEqual(evidence_response["definitions"][0]["name"], "Named history")
        self.assertEqual(
            self.client.post(endpoint, "[]", content_type="application/json").status_code, 410
        )
        self.assertEqual(
            self.client.post(endpoint, "{", content_type="application/json").status_code, 410
        )
        regular = get_user_model().objects.create_user("excerpt-reader")
        self.client.force_login(regular)
        self.assertEqual(self.client.get(endpoint).status_code, 403)
        self.assertEqual(
            self.client.post(endpoint, payload, content_type="application/json").status_code, 403
        )


class ExcerptDescriptorTests(SimpleTestCase):
    def test_bad_descriptor_is_rejected(self):
        for value in (
            {},
            [],
            None,
            {"version": 1, "source_digest": "a" * 64, "start": True, "end": 1},
            {"version": 1, "source_digest": "a" * 64, "start": 2, "end": 1},
            {"version": 1, "source_digest": "x" * 64, "start": 0, "end": 1},
            {"version": 2, "source_digest": "a" * 64, "start": 0, "end": 1},
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                descriptor(value)
