import io
import json
from unittest.mock import patch

from bs4 import BeautifulSoup
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from pypdf import PdfReader

from library.models import DocumentDraftBase, DocumentEditRevision, Rendition, Snapshot
from library.services.document_edits import create_draft
from library.services.pdf import STYLES, PDFExportError
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

    def workspace_payload(self, document, *, draft=None, revision=0, source_tickets=None):
        return {
            "draft": str(draft.pk) if draft else None,
            "revision": revision,
            "document": document,
            "source_tickets": source_tickets or [],
        }

    def test_workspace_read_preview_projects_unsaved_semantic_content_without_mutation(self):
        initial = self.client.get(self.url).context["initial"]
        document = canonical_document({
            **initial["document"],
            "title": "Unsaved preview title",
            "html": '<section id="c1"><h2 id="heading">Preview heading</h2>'
            '<p id="prose">Unsaved reader text.</p>'
            '<p><a href="#prose">Internal link</a></p></section>',
        })
        before = (
            DocumentDraftBase.objects.count(), DocumentEditRevision.objects.count(),
            self.rendition.html, self.rendition.document.reader_rendition_id,
        )
        response = self.client.post(
            reverse("document-editor-read-preview", args=[self.rendition.pk]),
            json.dumps(self.workspace_payload(document)),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        markup = response.json()["html"]
        self.assertIn("Unsaved preview title", markup)
        self.assertIn("Unsaved reader text.", markup)
        self.assertIn("Unsaved editor changes are shown", markup)
        self.assertRegex(
            markup,
            r'href="#workspace-preview-[0-9a-f]{32}-prose"',
        )
        self.assertNotIn('id="prose"', markup)
        self.assertEqual(before, (
            DocumentDraftBase.objects.count(), DocumentEditRevision.objects.count(),
            self.rendition.html, self.rendition.document.reader_rendition_id,
        ))

    def test_workspace_unchanged_source_has_no_draft_preview_banner(self):
        self.rendition.metadata = {**self.rendition.metadata, "author": "Example author"}
        self.rendition.metadata.pop("author_is_fallback", None)
        self.rendition.save(update_fields=["metadata"])
        initial = self.client.get(self.url + "?start=source").context["initial"]
        response = self.client.post(
            reverse("document-editor-read-preview", args=[self.rendition.pk]),
            json.dumps(self.workspace_payload(initial["document"])),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("PRIVATE WORKSPACE PREVIEW", response.json()["html"])
        self.assertNotIn("Draft preview:", response.json()["html"])

    def test_catalogue_reviewer_opens_selected_source_not_existing_draft(self):
        response = self.client.get(reverse("latest", args=[self.rendition.document_id]))
        self.assertRedirects(response, self.url + "?start=edition&tab=read")
        workspace = self.client.get(response.url)
        self.assertIsNone(workspace.context["initial"]["draft"])
        self.assertEqual(workspace.context["version"].pk, self.rendition.pk)
        guest = Client().get(reverse("latest", args=[self.rendition.document_id]))
        self.assertRedirects(guest, reverse("reader", args=[self.rendition.pk]))

    def test_workspace_preview_rejects_stale_revision_and_other_reviewers_draft(self):
        document = canonical_document({
            **self.draft.document, "html": '<section id="c1"><p>Saved revision.</p></section>',
        })
        saved = foundation.DocumentEditTests.save(self, value=document)
        stale = self.client.post(
            reverse("document-editor-read-preview", args=[self.rendition.pk]),
            json.dumps(self.workspace_payload(document, draft=self.draft, revision=0)),
            content_type="application/json",
        )
        stale_pdf = self.client.post(
            reverse("document-editor-draft-pdf", args=[self.rendition.pk]),
            json.dumps(self.workspace_payload(document, draft=self.draft, revision=0)),
            content_type="application/json",
        )
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale_pdf.status_code, 409)

        other = get_user_model().objects.create_user("other-editor")
        other_draft = create_draft(self.rendition, other)
        private_document = canonical_document({
            **other_draft.document, "html": "<p>Other reviewer private text.</p>",
        })
        denied = self.client.post(
            reverse("document-editor-read-preview", args=[self.rendition.pk]),
            json.dumps(self.workspace_payload(private_document, draft=other_draft)),
            content_type="application/json",
        )
        denied_pdf = self.client.post(
            reverse("document-editor-draft-pdf", args=[self.rendition.pk]),
            json.dumps(self.workspace_payload(private_document, draft=other_draft)),
            content_type="application/json",
        )
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied_pdf.status_code, 403)
        self.assertNotIn("Other reviewer private text", denied.content.decode())
        self.assertNotIn("Other reviewer private text", denied_pdf.content.decode())
        self.assertEqual(saved.revision, 1)

    def test_workspace_preview_rejects_invalid_semantics_and_forged_asset_evidence(self):
        baseline = self.client.get(self.url).context["initial"]["document"]
        invalid = {
            **baseline,
            "html": '<section id="c1"><p id="reused">First.</p>'
            '<p id="reused">Second.</p></section>',
        }
        forged_ticket = self.client.post(
            reverse("document-editor-read-preview", args=[self.rendition.pk]),
            json.dumps(self.workspace_payload(baseline, source_tickets=["forged-ticket"])),
            content_type="application/json",
        )
        unsafe_document = self.client.post(
            reverse("document-editor-read-preview", args=[self.rendition.pk]),
            json.dumps(self.workspace_payload(invalid)),
            content_type="application/json",
        )
        digest = "a" * 64
        unbound_asset = canonical_document({
            **baseline, "html": f'<p><img src="/assets/{digest}/" alt="Unbound"></p>',
        })
        unbound = self.client.post(
            reverse("document-editor-read-preview", args=[self.rendition.pk]),
            json.dumps(self.workspace_payload(unbound_asset)),
            content_type="application/json",
        )
        self.assertEqual(forged_ticket.status_code, 422)
        self.assertEqual(unsafe_document.status_code, 422)
        self.assertEqual(unbound.status_code, 422)
        self.assertEqual(DocumentDraftBase.objects.count(), 1)
        self.assertEqual(DocumentEditRevision.objects.count(), 0)

    def test_workspace_pdf_exports_captured_unsaved_document_without_mutation(self):
        initial = self.client.get(self.url).context["initial"]
        document = canonical_document({
            **initial["document"],
            "title": "Unsaved PDF title",
            "html": '<section id="c1"><p>Captured PDF text.</p></section>',
        })
        before = (
            DocumentDraftBase.objects.count(), DocumentEditRevision.objects.count(),
            self.rendition.html, self.rendition.document.reader_rendition_id,
        )

        def render(version, destination, reading_style, *, theme, approved_assets):
            self.assertEqual(version.title, "Unsaved PDF title")
            self.assertIn("Captured PDF text.", version.html)
            self.assertEqual(approved_assets, {})
            destination.write(b"%PDF-1.7\\nworkspace")

        with patch("library.services.pdf.render_pdf", side_effect=render) as renderer:
            response = self.client.post(
                reverse("document-editor-draft-pdf", args=[self.rendition.pk]),
                json.dumps(self.workspace_payload(document)),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertIn("Draft preview - Unsaved PDF title.pdf", response["Content-Disposition"])
        self.assertEqual(b"".join(response.streaming_content), b"%PDF-1.7\\nworkspace")
        renderer.assert_called_once()
        self.rendition.refresh_from_db()
        self.assertEqual(before, (
            DocumentDraftBase.objects.count(), DocumentEditRevision.objects.count(),
            self.rendition.html, self.rendition.document.reader_rendition_id,
        ))

    def test_workspace_pdf_returns_a_real_private_pdf_without_persisting_the_draft(self):
        initial = self.client.get(self.url).context["initial"]
        document = canonical_document({
            **initial["document"],
            "title": "Captured workspace edition",
            "html": '<section id="c1"><p>Real workspace PDF content.</p></section>',
        })
        self.rendition.stylesheet = (STYLES / "reader.css").read_text()
        self.rendition.save(update_fields=["stylesheet"])
        before = (
            DocumentDraftBase.objects.count(), DocumentEditRevision.objects.count(),
            self.rendition.html, self.rendition.document.reader_rendition_id,
        )

        response = self.client.post(
            reverse("document-editor-draft-pdf", args=[self.rendition.pk]),
            json.dumps(self.workspace_payload(document)),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertIn("Draft preview - Captured workspace edition.pdf",
                      response["Content-Disposition"])
        content = b"".join(response.streaming_content)
        self.assertTrue(content.startswith(b"%PDF-"))
        extracted = "\n".join(
            page.extract_text() for page in PdfReader(io.BytesIO(content)).pages
        )
        self.assertIn("Captured workspace edition", extracted)
        self.assertIn("Real workspace PDF content", extracted)
        self.assertNotIn("Back to top", extracted)
        self.assertNotIn("Download current draft PDF", extracted)
        self.rendition.refresh_from_db()
        self.assertEqual(before, (
            DocumentDraftBase.objects.count(), DocumentEditRevision.objects.count(),
            self.rendition.html, self.rendition.document.reader_rendition_id,
        ))

    def test_workspace_pdf_render_failure_is_explicit_and_does_not_fall_back(self):
        changed = canonical_document({
            **self.draft.document,
            "html": '<section id="c1"><p>Changed before failed export.</p></section>',
        })
        with (
            patch(
                "library.services.pdf.render_pdf",
                side_effect=PDFExportError("synthetic renderer failure"),
            ),
            patch("library.services.pdf.cached_pdf") as exact,
        ):
            response = self.client.post(
                reverse("document-editor-draft-pdf", args=[self.rendition.pk]),
                json.dumps(self.workspace_payload(changed)),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertIn("Draft PDF generation failed", response.json()["error"])
        exact.assert_not_called()

    def test_workspace_pdf_state_unchanged_source_exports_exact_retained_output(self):
        initial = self.client.get(self.url + "?start=source").context["initial"]
        exact = self.rendition
        exported = io.BytesIO(b"%PDF-1.7\\nexact")

        class ExactPath:
            def open(self, mode):
                return exported

        payload = json.dumps(self.workspace_payload(initial["document"]))
        read = self.client.post(
            reverse("document-editor-read-preview", args=[exact.pk]),
            payload, content_type="application/json",
        )
        self.assertEqual(read.json()["state"], "exact")
        with (
            patch("library.services.pdf.cached_pdf", return_value=ExactPath()) as cached,
            patch("library.services.pdf.render_pdf") as renderer,
        ):
            response = self.client.post(
                reverse("document-editor-draft-pdf", args=[exact.pk]),
                payload, content_type="application/json",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Reading-Hub-PDF-State"], "exact")
        self.assertIn(f"{exact.title}.pdf", response["Content-Disposition"])
        self.assertNotIn("Draft preview", response["Content-Disposition"])
        self.assertEqual(b"".join(response.streaming_content), b"%PDF-1.7\\nexact")
        self.assertEqual(cached.call_args.args[0].pk, exact.pk)
        renderer.assert_not_called()
        self.assertEqual(DocumentDraftBase.objects.count(), 1)
        self.assertEqual(DocumentEditRevision.objects.count(), 0)

    def test_workspace_pdf_exact_failure_is_explicit_without_fallback(self):
        initial = self.client.get(self.url + "?start=source").context["initial"]
        with (
            patch(
                "library.services.pdf.cached_pdf",
                side_effect=PDFExportError("synthetic exact failure"),
            ),
            patch("library.services.pdf.render_pdf") as renderer,
        ):
            response = self.client.post(
                reverse("document-editor-draft-pdf", args=[self.rendition.pk]),
                json.dumps(self.workspace_payload(initial["document"])),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 503)
        self.assertIn("No other version was substituted", response.json()["error"])
        renderer.assert_not_called()

    def test_workspace_pdf_state_distinguishes_saved_copy_from_unsaved_draft(self):
        document = canonical_document({
            **self.draft.document, "title": "Saved copy title",
            "html": '<section id="c1"><p>Saved revision text.</p></section>',
        })
        foundation.DocumentEditTests.save(self, value=document)
        saved = self.client.get(self.url + f"?draft={self.draft.pk}").context["initial"]
        self.assertEqual(saved["revision"], 1)
        rendered = []

        def render(version, destination, reading_style, *, theme, approved_assets):
            rendered.append(version.html)
            destination.write(b"%PDF-1.7\\nworkspace")

        def export(value):
            with patch("library.services.pdf.render_pdf", side_effect=render):
                return self.client.post(
                    reverse("document-editor-draft-pdf", args=[self.rendition.pk]),
                    json.dumps(self.workspace_payload(value, draft=self.draft, revision=1)),
                    content_type="application/json",
                )

        unchanged = export(saved["document"])
        self.assertEqual(unchanged.status_code, 200)
        self.assertEqual(unchanged["X-Reading-Hub-PDF-State"], "saved")
        self.assertEqual(unchanged["X-Reading-Hub-PDF-Revision"], "1")
        self.assertIn("Saved revision 1 - Saved copy title.pdf", unchanged["Content-Disposition"])
        self.assertIn("Saved revision text.", rendered[-1])
        read = self.client.post(
            reverse("document-editor-read-preview", args=[self.rendition.pk]),
            json.dumps(self.workspace_payload(saved["document"], draft=self.draft, revision=1)),
            content_type="application/json",
        )
        self.assertEqual(read.json()["state"], "saved")

        changed = export({
            **saved["document"],
            "html": '<section id="c1"><p>Unsaved later text.</p></section>',
        })
        self.assertEqual(changed["X-Reading-Hub-PDF-State"], "draft")
        self.assertIn("Draft preview - Saved copy title.pdf", changed["Content-Disposition"])
        self.assertIn("Unsaved later text.", rendered[-1])
        self.assertEqual(DocumentEditRevision.objects.count(), 1)

    def test_get_does_not_create_evidence_or_publish(self):
        before = DocumentDraftBase.objects.count()
        response = self.client.get(self.url)
        document = BeautifulSoup(response.content, "html.parser")
        workspace = document.select_one("#unified-workspace")
        self.assertIsNotNone(workspace)
        for panel in ("read", "edit", "versions", "sources"):
            self.assertIsNotNone(workspace.select_one(f"#workspace-panel-{panel}"), panel)
        for panel in ("read", "versions", "sources"):
            self.assertIsNotNone(
                workspace.select_one(f"#workspace-panel-{panel} #workspace-{panel}-content"),
                panel,
            )
        self.assertIsNotNone(workspace.select_one("#workspace-back-to-top"))
        for asset in (
            "library/reader.css", "library/reading-style-controls.css",
            "library/generated/editor-pilot.css",
            "library/editor-pilot.css", "library/generated/editor-pilot.js",
        ):
            self.assertContains(response, f'/static/{asset}?v={APP_VERSION}')
        self.assertContains(response, "Work editor")
        self.assertContains(response, "immutable saved versions")
        self.assertContains(response, 'aria-label="Work workspace"')
        self.assertContains(response, 'id="workspace-tab-read"')
        self.assertContains(response, 'id="workspace-tab-edit"')
        self.assertContains(response, 'id="workspace-tab-versions"')
        self.assertContains(response, 'id="workspace-tab-sources"')
        self.assertContains(response, "Reader default:")
        self.assertContains(response, "Download current draft PDF")
        self.assertNotContains(response, 'aria-label="Work destinations"', html=False)
        self.assertNotContains(response, 'aria-label="Work reviewer tools"')
        self.assertContains(
            response,
            f'data-versions-url="{reverse("document-lineage", args=[self.rendition.document_id])}'
            f'?filter=all&amp;selected=edition%3A{self.rendition.pk}&amp;embedded=1"',
        )
        self.assertContains(
            response,
            f'data-sources-url="{reverse("document-lineage", args=[self.rendition.document_id])}'
            f'?filter=sources&amp;selected=snapshot%3A{self.rendition.snapshot_id}&amp;embedded=1"',
        )
        self.assertNotContains(response, 'data-workflow-panel="Versions"')
        self.assertNotContains(response, 'data-workflow-panel="Sources"')
        self.assertContains(response, 'data-comparison-url="'
                            + reverse("document-comparison", args=[self.rendition.pk]) + '"')
        self.assertContains(response, 'id="editor-comparison"')
        for panel in ("Saved comparison", "Publication preview"):
            self.assertContains(response, f'data-workflow-panel="{panel}"')
        self.assertNotContains(response, 'data-workflow-panel="Regenerate a separate draft"')
        self.assertContains(response, "Unsaved editor changes are not included.")
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
        self.assertContains(response, "lower-right handle")
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

    def test_guest_reader_keeps_the_immutable_route_and_adds_scroll_controls(self):
        response = Client().get(reverse("reader", args=[self.rendition.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "reader-back-to-top")
        self.assertContains(response, "reader-workspace.js")
        self.assertContains(response, "Download PDF")
        self.assertContains(response, 'aria-label="Work status and destinations"')

    def test_unowned_working_copy_requires_explicit_choice(self):
        source = self.rendition
        snapshot = Snapshot.objects.create(
            document=source.document,
            digest="f" * 64,
            manifest=source.snapshot.manifest,
        )
        version = Rendition.objects.create(
            document=source.document, snapshot=snapshot, identity="9" * 64,
            title=source.title, metadata=source.metadata, structure=source.structure,
            html=source.html, stylesheet=source.stylesheet, warnings=source.warnings,
            app_version=source.app_version, adapter_version=source.adapter_version,
            format_version=source.format_version, output_digest="8" * 64,
        )
        owner = get_user_model().objects.create_user("other-reviewer")
        create_draft(version, owner)

        response = self.client.get(reverse("document-editor", args=[version.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["choose_history"])
        self.assertIsNone(response.context["draft"])
        self.assertContains(response, "Choose a working copy")
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
