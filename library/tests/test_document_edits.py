import io
import json
from copy import deepcopy
from dataclasses import replace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import SimpleTestCase, TestCase

from library.models import (
    Document,
    DocumentDraftBase,
    DocumentEditRevision,
    Rendition,
    Snapshot,
)
from library.profile import get_profile
from library.services.document_edits import (
    DocumentEditConflict,
    create_draft,
    save_revision,
)
from library.services.semantic_documents import (
    canonical_document,
    document_issues,
    fingerprint,
)

DIGEST = "a" * 64
HTML = (
    '<section id="c1"><h2 id="title">I. A heading</h2>'
    '<p>Original <em>words</em> and Unicode 😀.</p>'
    '<figure><img src="/assets/' + DIGEST + '/" alt="Cover" loading="lazy"/>'
    '<figcaption>Image caption <span class="media-credit">Credit</span></figcaption>'
    '</figure><p>A note <sup><a id="ref" href="#note">1</a></sup>.</p>'
    '<p id="note">Note text <a class="note-backlink" href="#ref">Back</a></p>'
    '<table><tbody><tr><th colspan="2">Heading</th></tr>'
    '<tr><td>First</td><td>Second</td></tr></tbody></table>'
    '<ul><li>A list <strong>item</strong></li></ul>'
    '<blockquote><p>Quoted text.</p></blockquote><hr/>'
    '<pre><code>  exact\n spacing</code></pre></section>'
)


def document(html=HTML):
    return {"version": 1, "title": "A work", "metadata": {"language": "en"}, "html": html}


class SemanticDocumentTests(SimpleTestCase):
    def test_round_trip_preserves_semantics_text_and_assets(self):
        result = canonical_document(document())
        self.assertEqual(canonical_document(result), result)
        self.assertIn("Unicode 😀", result["html"])
        self.assertIn("  exact\n spacing", result["html"])
        self.assertIn('href="#note"', result["html"])
        self.assertIn("<figcaption>", result["html"])
        self.assertEqual(document_issues(result, {DIGEST}), [])

    def test_serialization_noise_does_not_change_identity(self):
        a = document('<p id="x" class="text-bold-on text-align-left">Text &amp; more</p>')
        b = document('<p class="text-align-left text-bold-on" id="x">Text &#38; more</p>')
        self.assertEqual(fingerprint(canonical_document(a)), fingerprint(canonical_document(b)))

    def test_unsafe_unsupported_or_malformed_input_is_rejected_not_stripped(self):
        for html in (
            '<p onclick="alert(1)">Text</p>', '<script>alert(1)</script>',
            '<p style="color:red">Text</p>', '<p class="unknown">Text</p>',
            '<p><strong>Unbalanced</p></strong>', '<p>Unclosed',
            '<p><div>Invalid block</div></p>', '<p id="x" id="y">Duplicate</p>',
            '<p id="x">First</p><p id="x">Second</p>',
            '<p><a href="javascript:alert(1)">Unsafe</a></p>',
            '<p><a href="//tracker.invalid/">Remote</a></p>',
            '<p><a href="https://example.org/"><a>Nested</a></a></p>',
            '<img src="https://example.org/tracker.png"/>', '<img alt="No source"/>',
            '<p>Text<!-- hidden --></p>', '<!DOCTYPE html><p>Text</p>',
            '<table><p>Not a row</p></table>', '<li>Orphan</li>',
            '<p/>', 'Bare text', '<p data-preview-block="1">Review ID</p>',
        ):
            with self.subTest(html=html), self.assertRaises(ValueError):
                canonical_document(document(html))

    def test_schema_and_complexity_bounds_are_explicit(self):
        for value in (
            {**document(), "version": True}, {**document(), "extra": 1},
            {**document(), "metadata": []}, {**document(), "title": ""},
            {**document(), "metadata": {"number": float("nan")}},
            {**document(), "metadata": {1: "Coerced key"}},
            {**document(), "metadata": {"tuple": ("not", "JSON")}},
            document("<div>" * 101 + "<p>Text</p>" + "</div>" * 101),
            document("<p>" + "x" * (2 * 1024 * 1024) + "</p>"),
        ):
            with self.subTest(value=str(value)[:100]), self.assertRaises(ValueError):
                canonical_document(value)

    def test_incomplete_targets_are_diagnostics_not_silent_fixes(self):
        result = canonical_document(document('<p><a href="#absent">Note</a></p>' + HTML))
        issues = document_issues(result, set())
        self.assertEqual(len(issues), 2)
        self.assertIn("Unresolved internal target: #absent", issues)
        self.assertIn(DIGEST, issues[1])
        self.assertIn('href="#absent"', result["html"])

    def test_missing_image_placeholders_are_not_a_complete_target(self):
        result = canonical_document(document('<p><span class="missing-image">Missing</span></p>'))
        self.assertIn("unavailable-image", document_issues(result, set())[0])

    def test_direct_split_merge_and_move_need_no_operation_vocabulary(self):
        initial = canonical_document(document(
            '<section id="c1"><p>I</p><h2 id="heading">A title</h2>'
            '<p>First sentence. Second sentence.</p><p id="note">Endnote.</p></section>'
        ))
        corrected = canonical_document({**initial, "html":
            '<section id="c1"><h2 id="heading">I. A title</h2>'
            '<p id="note">Endnote.</p><p>First sentence.</p><p>Second sentence.</p></section>'
        })
        self.assertEqual(set(corrected), {"version", "title", "metadata", "html"})
        self.assertEqual(document_issues(corrected, set()), [])
        self.assertNotEqual(fingerprint(initial), fingerprint(corrected))


class DocumentEditTests(TestCase):
    def setUp(self):
        self.reviewer = get_user_model().objects.create_user("editor")
        work = Document.objects.create(url="https://www.marxists.org/test/index.htm")
        snapshot = Snapshot.objects.create(
            document=work, digest="b" * 64,
            manifest={"pages": [{"url": work.url, "digest": "c" * 64}]},
        )
        self.rendition = Rendition.objects.create(
            document=work, snapshot=snapshot, identity="d" * 64, title="A work",
            metadata={"language": "en"}, html='<section id="c1"><p>Source text.</p></section>',
            structure={"toc": [], "book": True}, stylesheet="retained stylesheet",
            app_version="0.30.0", adapter_version="19", format_version="19",
            output_digest="e" * 64,
        )
        self.draft = create_draft(self.rendition, self.reviewer)

    def save(self, value=None, revision=0, **kwargs):
        return save_revision(
            self.draft, self.reviewer, value or self.draft.document, revision, **kwargs
        )

    def test_base_pins_exact_edition_and_cannot_certify_historical_output(self):
        self.assertEqual(self.draft.evidence["generated_html"], self.rendition.html)
        self.assertEqual(self.draft.evidence["output_digest"], self.rendition.output_digest)
        self.assertEqual(self.draft.evidence["manifest"], self.rendition.snapshot.manifest)
        self.assertEqual(self.draft.evidence["versions"]["app"], "0.30.0")
        self.assertEqual(self.draft.evidence["kind"], "retained-rendition")
        self.assertEqual(self.draft.evidence_digest, fingerprint(self.draft.evidence))
        self.assertEqual(self.draft.revisions.count(), 0)
        self.assertEqual(self.rendition.html, self.draft.document["html"])

    def test_unchanged_full_verification_is_explicit_and_not_inherited(self):
        verified = self.save(review="full")
        self.assertEqual(verified.review, "full")
        partial = self.save(revision=1)
        self.assertEqual(partial.review, "partial")
        changed = {**partial.document, "html": '<section id="c1"><p>Repaired text.</p></section>'}
        edited = self.save(changed, revision=2)
        self.assertEqual(edited.review, "partial")
        self.assertEqual(edited.verified_sections, [])
        self.rendition.refresh_from_db()
        self.assertIn("Source text.", self.rendition.html)
        self.assertEqual(Rendition.objects.count(), 1)
        verified.refresh_from_db()
        self.assertEqual(verified.review, "full")

    def test_section_review_requires_exact_existing_scope(self):
        row = self.save(review="sections", verified_sections=["c1"])
        self.assertEqual(row.verified_sections, ["c1"])
        for scope, sections in (
            ("sections", []), ("sections", ["missing"]), ("full", ["c1"]),
            ("partial", ["c1"]), ("sections", ["c1", "c1"]), ("sections", [1]),
        ):
            with self.subTest(scope=scope, sections=sections), self.assertRaises(ValueError):
                self.save(revision=1, review=scope, verified_sections=sections)
        self.assertEqual(self.draft.revisions.count(), 1)

    def test_incomplete_edits_save_but_cannot_be_verified(self):
        value = document('<section id="c1"><p><a href="#missing">Note</a></p></section>')
        row = self.save(value)
        self.assertEqual(row.issues, ["Unresolved internal target: #missing"])
        for review, sections in (("full", None), ("sections", ["c1"])):
            with self.subTest(review=review), self.assertRaisesMessage(ValueError, "Resolve"):
                self.save(value, revision=1, review=review, verified_sections=sections)

    def test_stale_save_and_invalid_input_never_append(self):
        self.save()
        with self.assertRaises(DocumentEditConflict):
            self.save()
        for revision in (True, -1, "1"):
            with self.subTest(revision=revision), self.assertRaises(ValueError):
                self.save(revision=revision)
        with self.assertRaises(ValueError):
            self.save(document('<script>unsafe</script>'), revision=1)
        self.assertEqual(self.draft.revisions.count(), 1)

    def test_explicit_editorial_flag_is_not_inferred_from_diff(self):
        row = self.save(review="full", editorial=True)
        self.assertTrue(row.editorial)
        self.assertTrue(self.save(revision=1).editorial)
        self.assertFalse(self.save(revision=2, editorial=False).editorial)

    def test_immutable_models_and_querysets(self):
        row = self.save()
        for value in (self.draft, row):
            with self.subTest(model=type(value).__name__):
                with self.assertRaisesMessage(ValueError, "immutable"):
                    value.save()
                with self.assertRaisesMessage(ValueError, "immutable"):
                    value.delete()
                with self.assertRaisesMessage(ValueError, "immutable"):
                    type(value).objects.filter(pk=value.pk).update(document={})
                with self.assertRaisesMessage(ValueError, "immutable"):
                    type(value).objects.filter(pk=value.pk).delete()
        self.assertEqual(DocumentDraftBase.objects.count(), 1)
        self.assertEqual(DocumentEditRevision.objects.count(), 1)

    def test_caller_mutation_does_not_modify_saved_evidence(self):
        value = deepcopy(self.draft.document)
        row = self.save(value)
        value["metadata"]["language"] = "fr"
        row.refresh_from_db()
        self.assertEqual(row.document["metadata"]["language"], "en")

    def test_profile_and_evidence_mismatch_do_not_save(self):
        profile = replace(get_profile(), key="another-profile")
        with patch("library.services.document_edits.get_profile", return_value=profile):
            with self.assertRaisesMessage(ValueError, "profile"):
                self.save()
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE library_documentdraftbase SET evidence_digest = %s WHERE id = %s",
                ["0" * 64, self.draft.pk.hex],
            )
        with self.assertRaisesMessage(ValueError, "integrity"):
            self.save()
        self.assertEqual(self.draft.revisions.count(), 0)

    def test_readonly_command_reports_compatibility_without_creating_review(self):
        output = io.StringIO()
        call_command("semantic_document_check", self.rendition.pk, stdout=output)
        report = json.loads(output.getvalue())
        self.assertEqual(report["semantics"], "contract_check_not_review_certification")
        self.assertTrue(report["results"][0]["compatible"])
        self.assertEqual(self.draft.revisions.count(), 0)
        output = io.StringIO()
        with self.assertRaises(CommandError):
            call_command("semantic_document_check", self.rendition.pk + 1, stdout=output)
        self.assertFalse(json.loads(output.getvalue())["results"][0]["compatible"])
        self.rendition.html = '<section><p><a href="#missing">Note</a></p></section>'
        self.rendition.save(update_fields=["html"])
        output = io.StringIO()
        with self.assertRaises(CommandError):
            call_command("semantic_document_check", self.rendition.pk, stdout=output)
        self.assertEqual(json.loads(output.getvalue())["results"][0]["issues"],
                         ["Unresolved internal target: #missing"])
