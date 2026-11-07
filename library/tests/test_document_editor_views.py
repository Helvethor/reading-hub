import json
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from library.models import DocumentDraftBase, DocumentEditRevision
from library.services.semantic_documents import canonical_document
from library.tests import test_document_edits as foundation
from library.versions import APP_VERSION


@override_settings(READING_HUB_EDITOR_PILOT=True)
class DocumentEditorViewTests(TestCase):
    def setUp(self):
        assets = patch("library.document_editor_views.finders.find", return_value="built-asset")
        assets.start()
        self.addCleanup(assets.stop)
        foundation.DocumentEditTests.setUp(self)
        self.reviewer.is_staff = True
        self.reviewer.save(update_fields=["is_staff"])
        self.client.force_login(self.reviewer)
        self.url = reverse("document-editor", args=[self.rendition.pk])

    def post(self, **values):
        payload = {
            "draft": None, "revision": 0, "document": self.draft.document,
            "conversion_approval": None, "review": "partial",
            "verified_sections": [], "editorial": False, **values,
        }
        return self.client.post(self.url, json.dumps(payload), content_type="application/json")

    def test_get_does_not_create_evidence_or_publish(self):
        before = DocumentDraftBase.objects.count()
        response = self.client.get(self.url)
        for asset in (
            "library/reader.css", "library/reading-style-controls.css",
            "library/generated/editor-pilot.css",
            "library/editor-pilot.css", "library/generated/editor-pilot.js",
        ):
            self.assertContains(response, f'/static/{asset}?v={APP_VERSION}')
        self.assertContains(response, "Document editor pilot")
        self.assertContains(response, "immutable saved revisions")
        self.assertContains(response, 'data-comparison-url="'
                            + reverse("document-comparison", args=[self.rendition.pk]) + '"')
        self.assertContains(response, 'id="editor-comparison"')
        for panel in ("Lineage &amp; versions", "Regenerate a separate draft",
                      "Original retained source", "Saved comparison", "Publication preview"):
            self.assertContains(response, f'data-workflow-panel="{panel}"')
        self.assertContains(response, "excludes unsaved edits")
        self.assertContains(response, "document-editor-initial")
        self.assertContains(response, "Review clipboard paste")
        self.assertContains(response, "Insert formatted text")
        self.assertContains(response, "Insert plain text")
        self.assertContains(response, "Cancel paste")
        self.assertContains(response, "editor-metadata-sheet")
        self.assertContains(response, "Verify selected sections")
        self.assertContains(response, "Verify the whole document")
        self.assertContains(response, "Move paragraph up")
        self.assertContains(response, "Move paragraph down")
        self.assertContains(response, 'id="editor-context-menu" role="menu"')
        self.assertContains(response, "Shift+F10")
        self.assertContains(response, 'aria-label="Book parts"')
        self.assertContains(response, "Whole book")
        self.assertContains(response, "bottom-right resize handle")
        for value, label in (("book", "Whole book"), ("title", "Title"),
                             ("toc", "ToC"), ("sections", "Sections")):
            self.assertContains(response, f'<option value="{value}">{label}</option>')
        self.assertContains(response, 'id="editor-section-filter"')
        self.assertContains(response, '<option value="">All sections</option>')
        self.assertContains(response, "Book structure")
        self.assertContains(response, "Add / restore section")
        self.assertContains(response, "Section title, URL and role")
        self.assertContains(response, "Catalogue book membership (separate page)")
        self.assertNotContains(response, 'data-workflow-panel="Retained-page membership"')
        self.assertContains(response, "Separate as excerpt section")
        self.assertContains(response, "Excerpt title")
        self.assertContains(response, "Remove section")
        self.assertContains(response, "Publish this corrected document as a book")
        self.assertContains(response, reverse("document-editor-membership",
                                              args=[self.rendition.pk]))
        self.assertEqual(response.context["initial"]["structure"], self.rendition.structure)
        presentation = response.context["initial"]["presentation"]
        self.assertEqual(presentation["sourceUrl"], self.rendition.document.url)
        self.assertEqual(presentation["languages"]["en"], "English")
        self.assertEqual(presentation["languages"]["fr"], "French")
        self.assertContains(response, "Block labels")
        self.assertContains(response, 'id="editor-selection-path"')
        self.assertContains(response, 'aria-label="Paragraph alignment"')
        self.assertContains(response, "click again to inherit")
        self.assertNotContains(response, 'data-align=""')
        self.assertContains(response, 'aria-label="Italic"')
        self.assertContains(response, 'aria-label="Align center"')
        self.assertContains(response, "Edit image alternative text")
        self.assertContains(response, "Figure &amp; caption")
        self.assertContains(response, 'id="editor-figure-caption"')
        self.assertContains(response, 'id="editor-figure-preview"')
        self.assertContains(response, 'id="editor-figure-title"')
        self.assertNotContains(response, "Move final quotation paragraph to caption")
        self.assertContains(response, 'id="editor-quotation"')
        self.assertContains(response, 'id="editor-image"')
        self.assertContains(response, "Edit link destination")
        self.assertContains(response, "Create link from selection")
        self.assertContains(response, "Remove link (keep text and targets)")
        self.assertContains(response, "Choose an existing document target")
        self.assertContains(response, 'id="editor-link-search"')
        self.assertContains(response, 'aria-label="Matching document targets"')
        self.assertContains(response, 'id="editor-link"')
        self.assertEqual(DocumentDraftBase.objects.count(), before)
        self.assertEqual(DocumentEditRevision.objects.count(), 0)

    def test_style_defaults_are_in_a_separate_tab_without_editor_stylesheet(self):
        from bs4 import BeautifulSoup

        from library.services.reading_styles import DEFAULTS, style_token

        response = self.client.get(self.url, {"style": style_token({**DEFAULTS, "font_size": 28})})
        self.assertEqual(response.status_code, 200)
        page = BeautifulSoup(response.content, "html.parser")
        self.assertIsNone(page.select_one("link[data-reading-style]"))
        self.assertIsNone(page.select_one(".editor-canvas.publication-content"))
        self.assertIsNone(page.select_one('link[href*="print.css"]'))
        panel = page.select_one("#editor-panel-style")
        self.assertTrue(panel.has_attr("hidden"))
        self.assertEqual(panel["aria-labelledby"], "editor-tab-style")
        self.assertEqual(page.select_one("#editor-tab-style")["aria-controls"], panel["id"])
        self.assertTrue(panel.select_one(".reading-style-controls").has_attr("data-defaults-only"))
        for form in panel.select("form"):
            self.assertIsNone(form.find_parent("form"))
        self.assertEqual(len(panel.select("form")), 3)
        self.assertEqual(response.context["reading_style"]["font_size"], 28)
        self.assertContains(response, "The editor always follows the site theme.")
        self.assertEqual(DocumentEditRevision.objects.count(), 0)

    def test_link_repairs_save_and_reopen_preserving_note_targets_and_original(self):
        initial = self.client.get(self.url).context["initial"]
        original = self.rendition.html
        value = canonical_document({
            **initial["document"],
            "html": '<section id="c1"><p><a id="ref" class="text-bold-on" href="#note" '
            'title="Corrected note"><em>1</em></a> Source text.</p>'
            '<p id="note">Note <a class="note-backlink" href="#ref">Back</a></p></section>',
        })
        response = self.post(document=value)
        self.assertEqual(response.status_code, 200)
        saved = response.json()
        self.assertEqual(saved["issues"], [])
        self.assertEqual(saved["review"], "partial")
        reopened = self.client.get(self.url + "?draft=" + saved["draft"])
        self.assertEqual(reopened.context["initial"]["document"], value)
        self.rendition.refresh_from_db()
        self.assertEqual(self.rendition.html, original)

    def test_toc_styles_save_and_reopen_without_changing_titles_or_original(self):
        original = self.rendition.html
        markup = (
            '<section id="a" data-toc-style="upper-roman"><h2>First</h2>'
            '<h3 data-toc-style="lower-alpha">Nested</h3><p>Body</p></section>'
            '<section id="b" data-toc-style="upper-roman"><h2>Second</h2><p>End</p></section>'
        )
        value = canonical_document({**self.draft.document, "html": markup})
        response = self.post(document=value)
        self.assertEqual(response.status_code, 200)
        saved = response.json()
        reopened = self.client.get(self.url, {"draft": saved["draft"]})
        self.assertEqual(reopened.context["initial"]["document"], value)
        self.rendition.refresh_from_db()
        self.assertEqual(self.rendition.html, original)

    def test_created_link_saves_and_reopens_preserving_nested_and_inline_targets(self):
        initial = self.client.get(self.url).context["initial"]
        original = self.rendition.html
        value = canonical_document({
            **initial["document"],
            "html": '<section id="c1"><p id="paragraph">Before '
            '<a href="#inline" title="Note" rel="noopener noreferrer">One '
            '<em id="em">two <strong>three</strong></em></a> after</p>'
            '<p><span id="inline">Note target</span></p></section>',
        })
        response = self.post(document=value)
        self.assertEqual(response.status_code, 200)
        saved = response.json()
        self.assertEqual(saved["issues"], [])
        self.assertEqual(saved["review"], "partial")
        reopened = self.client.get(self.url + "?draft=" + saved["draft"])
        self.assertEqual(reopened.context["initial"]["document"], value)
        self.rendition.refresh_from_db()
        self.assertEqual(self.rendition.html, original)

    def test_removed_link_retains_nonnavigable_anchor_and_resolvable_backlink_on_reopen(self):
        initial = self.client.get(self.url).context["initial"]
        original = self.rendition.html
        value = canonical_document({
            **initial["document"],
            "html": '<section id="c1"><p><a id="ref" class="text-bold-on" title="Reference" '
            'aria-label="Reference"><sup>1</sup></a> Source <em>text</em>.</p>'
            '<p id="note">Note <a class="note-backlink" href="#ref">Back</a></p></section>',
        })
        response = self.post(document=value)
        self.assertEqual(response.status_code, 200)
        saved = response.json()
        self.assertEqual(saved["issues"], [])
        self.assertEqual(saved["review"], "partial")
        reopened = self.client.get(self.url + "?draft=" + saved["draft"])
        self.assertEqual(reopened.context["initial"]["document"], value)
        self.rendition.refresh_from_db()
        self.assertEqual(self.rendition.html, original)

    def test_alignment_classes_save_and_reopen_without_changing_original(self):
        initial = self.client.get(self.url).context["initial"]
        original = self.rendition.html
        aligned = canonical_document({
            **initial["document"],
            "html": '<section id="c1"><p id="paragraph" class="text-align-center text-bold-off">'
            'Source <em>text</em>.</p></section>',
        })
        response = self.post(document=aligned)
        self.assertEqual(response.status_code, 200)
        saved = response.json()
        self.assertEqual(saved["issues"], [])
        reopened = self.client.get(self.url + "?draft=" + saved["draft"])
        self.assertEqual(reopened.context["initial"]["document"], aligned)
        self.rendition.refresh_from_db()
        self.assertEqual(self.rendition.html, original)

    def test_formatted_paste_result_saves_and_reopens_with_absolute_links(self):
        initial = self.client.get(self.url).context["initial"]
        value = canonical_document({
            **initial["document"],
            "html": '<section id="c1"><p id="paragraph">Source '
            '<strong>bold <em>nested</em></strong>'
            ' <a href="https://example.org/source" title="Source">link</a><br>'
            '<u>underlined</u> <sup>2</sup></p></section>',
        })
        response = self.post(document=value)
        self.assertEqual(response.status_code, 200)
        saved = response.json()
        self.assertEqual(saved["review"], "partial")
        self.assertEqual(saved["issues"], [])
        reopened = self.client.get(self.url + "?draft=" + saved["draft"])
        self.assertEqual(reopened.context["initial"]["document"], value)

    def test_quotation_figure_and_cited_source_save_and_reopen_without_changing_original(self):
        initial = self.client.get(self.url).context["initial"]
        original = self.rendition.html
        value = canonical_document({
            **initial["document"],
            "html": '<section id="c1"><h2>Preface</h2><figure class="quotation">'
            '<blockquote id="epigraph"><p>Party struggles lend strength.<br>More text.</p>'
            '</blockquote><figcaption><p id="source"><em>From a '
            '<cite><a href="https://example.org/letter">letter to Marx</a></cite>, '
            'June 24, 1852.</em></p></figcaption></figure></section>',
        })
        response = self.post(document=value)
        self.assertEqual(response.status_code, 200)
        saved = response.json()
        self.assertEqual(saved["issues"], [])
        self.assertEqual(saved["review"], "partial")
        reopened = self.client.get(self.url + "?draft=" + saved["draft"])
        self.assertEqual(reopened.context["initial"]["document"], value)
        self.rendition.refresh_from_db()
        self.assertEqual(self.rendition.html, original)

    def test_multi_paragraph_paste_result_retains_empty_targets_and_reopens(self):
        initial = self.client.get(self.url).context["initial"]
        original = self.rendition.html
        value = canonical_document({
            **initial["document"],
            "html": '<section id="c1"><p id="original"></p><p><strong>First</strong></p>'
            '<p>Second</p><p>Remaining text.</p></section>',
        })
        saved = self.post(document=value)
        self.assertEqual(saved.status_code, 200)
        data = saved.json()
        self.assertEqual(data["issues"], [])
        reopened = self.client.get(self.url + "?draft=" + data["draft"])
        self.assertEqual(reopened.context["initial"]["document"], value)
        self.rendition.refresh_from_db()
        self.assertEqual(self.rendition.html, original)

    def test_image_alternative_text_save_and_reopen_preserves_asset_caption_and_original(self):
        source = "/assets/" + "a" * 64 + "/"
        self.rendition.html = (
            f'<section id="c1"><figure><img id="plate" src="{source}" alt="Old">'
            '<figcaption>Caption <span class="media-credit">Credit</span></figcaption>'
            '</figure></section>'
        )
        self.rendition.save(update_fields=["html"])
        original = self.rendition.html
        initial = self.client.get(self.url).context["initial"]
        for alt in ("Descriptive text", ""):
            value = canonical_document({
                **initial["document"], "html": original.replace('alt="Old"', f'alt="{alt}"'),
            })
            response = self.post(document=value)
            self.assertEqual(response.status_code, 200)
            saved = response.json()
            self.assertEqual(saved["review"], "partial")
            reopened = self.client.get(self.url + "?draft=" + saved["draft"])
            self.assertEqual(reopened.context["initial"]["document"], value)
        self.rendition.refresh_from_db()
        self.assertEqual(self.rendition.html, original)

    def test_image_figure_caption_and_source_title_save_and_reopen_together(self):
        initial = self.client.get(self.url).context["initial"]
        original = self.rendition.html
        value = canonical_document({
            **initial["document"],
            "html": '<section id="c1"><figure id="plate"><img src="/assets/' + "a" * 64 +
            '/" alt="Descriptive image"><figcaption><p id="caption">From '
            '<cite><a href="https://example.org/work">Collected works</a></cite>. '
            '<span class="media-credit">Original credit</span></p></figcaption></figure>'
            '</section><section id="hidden"><h2>Later</h2><p>Unchanged text.</p></section>',
        })
        response = self.post(document=value)
        self.assertEqual(response.status_code, 200)
        saved = response.json()
        self.assertEqual(saved["review"], "partial")
        reopened = self.client.get(self.url + "?draft=" + saved["draft"])
        self.assertEqual(reopened.context["initial"]["document"], value)
        self.rendition.refresh_from_db()
        self.assertEqual(self.rendition.html, original)

    def test_disabled_pilot_is_not_exposed(self):
        with override_settings(READING_HUB_EDITOR_PILOT=False):
            self.assertEqual(self.client.get(self.url).status_code, 404)
            self.assertEqual(self.post().status_code, 404)

    def test_missing_build_is_an_explicit_unavailable_page(self):
        with patch("library.document_editor_views.finders.find", return_value=None):
            response = self.client.get(self.url)
        self.assertContains(response, "pilot assets are not built", status_code=503)
        self.assertNotContains(response, 'id="editor-surface"', status_code=503)

    def test_access_requires_reviewer_and_csrf(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        reader = get_user_model().objects.create_user("reader")
        self.client.force_login(reader)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.post().status_code, 403)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.reviewer)
        response = protected.post(self.url, "{}", content_type="application/json")
        self.assertEqual(response.status_code, 403)

    def test_save_and_reopen_append_revisions_without_publication(self):
        value = {**self.draft.document, "html": '<section id="c1"><p>Edited.</p></section>'}
        response = self.post(document=value)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["review"], "partial")
        self.assertEqual(data["revision"], 1)
        self.assertContains(self.client.get(self.url + "?draft=" + data["draft"]), "Edited.")
        self.assertEqual(self.post(draft=data["draft"], revision=1).status_code, 200)
        self.assertEqual(DocumentEditRevision.objects.count(), 2)
        self.rendition.refresh_from_db()
        self.assertIn("Source text.", self.rendition.html)

    def test_explicit_scope_editorial_and_validated_metadata_are_saved(self):
        response = self.post(
            review="full", editorial=True,
            document={
                **self.draft.document, "title": "Corrected title",
                "metadata": {
                    **self.draft.document["metadata"], "author": "A. Writer",
                    "subtitle": "A new subtitle", "language": "fr-CA",
                },
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["review"], "full")
        self.assertEqual(data["verified_sections"], [])
        self.assertTrue(data["editorial"])
        self.assertEqual(data["document"]["metadata"]["author"], "A. Writer")
        self.assertFalse(data["document"]["metadata"]["author_is_fallback"])
        self.assertEqual(data["document"]["metadata"]["language"], "fr-CA")
        self.assertContains(
            self.client.get(self.url + "?draft=" + data["draft"]),
            "Verify the whole document",
        )

    def test_reordered_paragraphs_save_and_reopen_with_links_and_targets(self):
        first = '<p id="first"><a href="#note"><em>First</em></a></p>'
        second = '<h3 id="note">Second</h3>'
        self.rendition.html = f'<section id="c1">{first}{second}</section>'
        self.rendition.save(update_fields=["html"])
        original = self.rendition.html
        initial = self.client.get(self.url).context["initial"]
        moved = canonical_document({
            **initial["document"], "html": f'<section id="c1">{second}{first}</section>',
        })
        response = self.post(document=moved)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["issues"], [])
        self.assertEqual(data["review"], "partial")
        reopened = self.client.get(self.url + "?draft=" + data["draft"])
        self.assertEqual(reopened.context["initial"]["document"], moved)
        self.rendition.refresh_from_db()
        self.assertEqual(self.rendition.html, original)

    def test_section_scope_requires_existing_selected_sections(self):
        for sections, expected in (([], 422), (["missing"], 422), (["c1"], 200)):
            response = self.post(review="sections", verified_sections=sections)
            self.assertEqual(response.status_code, expected)
            if expected == 200:
                self.assertEqual(response.json()["verified_sections"], ["c1"])

    def test_metadata_input_rejects_unknown_fields_types_controls_and_languages(self):
        for metadata in (
            {**self.draft.document["metadata"], "unapproved_field": ["forged"]},
            {**self.draft.document["metadata"], "author": ["not text"]},
            {**self.draft.document["metadata"], "subtitle": "invalid\nvalue"},
            {**self.draft.document["metadata"], "language": "not-a-language"},
        ):
            with self.subTest(metadata=metadata):
                response = self.post(document={**self.draft.document, "metadata": metadata})
                self.assertEqual(response.status_code, 422)
        self.assertFalse(DocumentEditRevision.objects.exists())

    def test_stale_save_keeps_server_history(self):
        response = self.post()
        identifier = response.json()["draft"]
        self.assertEqual(self.post(draft=identifier, revision=0).status_code, 409)
        self.assertEqual(DocumentEditRevision.objects.count(), 1)

    def test_article_and_book_fixtures_save_and_reopen_without_rewriting_editions(self):
        for name in ("article", "book", "mixed-flow"):
            with self.subTest(fixture=name):
                html = (settings.BASE_DIR / "frontend" / "fixtures" / f"{name}.html").read_text()
                self.rendition.html = html
                self.rendition.save(update_fields=["html"])
                initial = self.client.get(self.url + "?start=source").context["initial"]
                corrected = canonical_document({
                    **initial["document"],
                    "html": html.replace("Original wording", "Corrected wording"),
                })
                response = self.post(document=corrected)
                self.assertEqual(response.status_code, 200)
                data = response.json()
                reopened = self.client.get(self.url + "?draft=" + data["draft"])
                self.assertEqual(reopened.context["initial"]["document"], corrected)
                self.assertEqual(data["review"], "partial")
                self.rendition.refresh_from_db()
                self.assertEqual(self.rendition.html, html)

    def test_invalid_first_save_does_not_leave_orphan_draft(self):
        before = DocumentDraftBase.objects.count()
        invalid = {**self.draft.document, "html": "<script>bad()</script>"}
        self.assertEqual(self.post(document=invalid).status_code, 422)
        self.assertEqual(DocumentDraftBase.objects.count(), before)
        self.assertEqual(DocumentEditRevision.objects.count(), 0)

    def test_new_pilot_saves_may_explicitly_verify_a_valid_scope(self):
        response = self.client.post(self.url, json.dumps({
            "draft": None, "revision": 0, "document": self.draft.document,
            "conversion_approval": None, "review": "full",
            "verified_sections": [], "editorial": False,
        }), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["review"], "full")
        self.assertTrue(DocumentEditRevision.objects.exists())
        invalid = self.post(review="sections", verified_sections=["missing"])
        self.assertEqual(invalid.status_code, 422)

    def test_conversion_requires_explicit_exact_approval(self):
        self.rendition.html = '<section><span><div><p>Legacy.</p></div></span></section>'
        self.rendition.save(update_fields=["html"])
        response = self.client.get(self.url + "?start=source")
        initial = response.context["initial"]
        self.assertTrue(initial["requires_approval"])
        self.assertEqual(self.post(document=initial["document"]).status_code, 409)
        response = self.post(document=initial["document"],
                             conversion_approval=initial["approval_digest"])
        self.assertEqual(response.status_code, 200)

    def test_malformed_requests_are_explicit(self):
        self.assertEqual(self.client.post(self.url, {}).status_code, 400)
        response = self.client.post(self.url, "{", content_type="application/json")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.post(revision=True).status_code, 422)
        self.assertEqual(self.client.get(self.url + "?draft=invalid").status_code, 422)

    def test_unsupported_structure_shows_error_not_an_empty_editor(self):
        self.rendition.html = "<section><figcaption>Orphan.</figcaption></section>"
        self.rendition.save(update_fields=["html"])
        response = self.client.get(self.url + "?start=source")
        self.assertEqual(response.status_code, 422)
        self.assertContains(response, "no safe repair", status_code=422)
        self.assertNotContains(response, 'id="editor-surface"', status_code=422)
