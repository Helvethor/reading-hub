from copy import deepcopy

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from library.models import DocumentDraftBase, DocumentEditRevision, DocumentPublication, Rendition
from library.services.document_comparison import compare_documents
from library.services.document_edits import save_revision
from library.services.semantic_documents import fingerprint
from library.tests import test_document_edits as foundation


class ComparisonTests(SimpleTestCase):
    def value(self, html):
        return {"version": 1, "title": "Title", "metadata": {}, "html": html}

    def test_structural_changes_are_visible_even_when_words_are_identical(self):
        before = self.value("<blockquote><p>Quote</p><p>Work</p></blockquote>")
        after = self.value("<figure><blockquote><p>Quote</p></blockquote>"
                           "<figcaption><cite>Work</cite></figcaption></figure>")
        result = compare_documents(before, after)
        self.assertEqual(result["changed_fields"], ["html"])
        self.assertTrue(any("<cite>" in line["text"] for line in result["lines"]))
        self.assertEqual(result["after_digest"], fingerprint(after))
        self.assertFalse(result["limited"])

    def test_inline_quotation_and_source_title_changes_are_visible(self):
        before = self.value("<p>A <q>brief quote</q> from <cite>Work</cite>.</p>")
        after = self.value("<p>A <q>brief quoted phrase</q> from <cite>Work</cite>.</p>")
        result = compare_documents(before, after)
        self.assertTrue(result["html_changed"])
        self.assertTrue(any("brief quoted phrase" in line["text"] for line in result["lines"]))
        self.assertTrue(any("<q>" in line["text"] for line in result["lines"]))

    def test_unicode_entities_and_html_looking_text_are_preserved_in_inert_tokens(self):
        before = self.value("<p>&amp; &#233; Élément</p>")
        after = self.value("<p>&lt;script&gt;different&lt;/script&gt; Élément</p>")
        result = compare_documents(before, after)
        self.assertTrue(any("&#233;" in row["text"] for row in result["lines"]))
        self.assertTrue(any("script" in row["text"] for row in result["lines"]))

    def test_large_documents_have_an_explicit_limit_and_no_partial_diff(self):
        result = compare_documents(self.value("<p>One</p>" * 2100), self.value("<p>Two</p>"))
        self.assertTrue(result["limited"])
        self.assertEqual(result["lines"], [])

    def test_long_lines_and_large_change_sets_are_explicitly_truncated(self):
        result = compare_documents(self.value("<p>Old</p>"),
                                   self.value("<p>" + "x" * 3000 + "</p>" + "<p>New</p>" * 200))
        self.assertTrue(result["truncated"])
        self.assertLessEqual(len(result["lines"]), 400)
        self.assertTrue(all(len(row["text"]) <= 2000 for row in result["lines"]))
        self.assertTrue(any("[line clipped]" in line["text"] for line in result["lines"]))

    def test_unchanged_documents_and_metadata_only_changes(self):
        before = self.value("<p>Unchanged</p>")
        self.assertEqual(compare_documents(before, before)["changed_fields"], [])
        after = {**before, "metadata": {"author": "Reviewer"}}
        result = compare_documents(before, after)
        self.assertEqual(result["changed_fields"], ["metadata"])
        self.assertEqual(result["lines"], [])
        self.assertEqual(result["metadata_changes"], [{
            "field": "author", "before": "Not present", "after": "Reviewer",
        }])

    def test_visual_comparison_groups_sections_sanitizes_markup_and_aligns_words(self):
        before = self.value(
            "<p>Outside old.</p>"
            '<section id="c1"><h2>Chapter</h2><p>A brief <em>old</em> phrase.</p>'
            '<script>alert(1)</script></section>'
            '<section id="c2"><p>Unchanged.</p></section>',
        )
        after = self.value(
            "<p>Outside new.</p>"
            '<section id="c1"><h2>Chapter</h2><p>A very brief <em>new</em> phrase.</p>'
            '<img src="javascript:alert(1)" alt="diagram"></section>'
            '<section id="c2"><p>Unchanged.</p></section>',
        )
        result = compare_documents(before, after)
        self.assertEqual(
            [item["id"] for item in result["visual_sections"]], ["c1", "c2", None],
        )
        changed = next(item for item in result["visual_sections"] if item["id"] == "c1")
        pair = next(group for group in changed["groups"] if not group["unchanged"])
        self.assertEqual(pair["word_changes"], {"before": "old", "after": "very new"})
        self.assertIn("<em>", str(pair["before_html"]))
        self.assertNotIn("<script", str(pair["before_html"]))
        differences = [group for group in changed["groups"] if not group["unchanged"]]
        self.assertEqual(len(differences), 2)
        self.assertEqual(differences[0]["next_anchor"], differences[1]["anchor"])
        self.assertEqual(differences[1]["previous_anchor"], differences[0]["anchor"])
        self.assertTrue(any(group["unchanged"] for group in changed["groups"]))
        image = next(
            group for group in changed["groups"]
            if not group["unchanged"] and "Image: diagram" in str(group["after_html"])
        )
        self.assertNotIn("javascript:", str(image["after_html"]))
        unchanged = next(item for item in result["visual_sections"] if item["id"] == "c2")
        self.assertTrue(all(group["unchanged"] for group in unchanged["groups"]))
        unsectioned = next(
            item for item in result["visual_sections"] if item["id"] is None
        )
        self.assertEqual(unsectioned["label"], "Unsectioned content")
        self.assertTrue(unsectioned["changed"])

    def test_localized_change_in_large_book_remains_visible_without_quadratic_full_diff(self):
        prefix, suffix = "<p>Earlier chapter.</p>" * 3000, "<p>Later chapter.</p>" * 3000
        before = self.value(prefix + "<p>Original</p>" + suffix)
        after = self.value(prefix + "<p>Corrected</p>" + suffix)
        result = compare_documents(before, after)
        self.assertFalse(result["limited"])
        self.assertFalse(result["truncated"])
        self.assertGreater(result["omitted_prefix_tokens"], 8000)
        self.assertTrue(any("Corrected" in row["text"] for row in result["lines"]))

    def test_section_scope_matches_ids_handles_absence_and_keeps_full_digests(self):
        before = self.value('<section id="c1"><h2>One</h2><p>Old</p></section>')
        after = self.value('<section id="c2"><h2>Two</h2><p>New</p></section>')
        result = compare_documents(before, after, "c1")
        self.assertEqual(result["after_digest"], fingerprint(after))
        self.assertTrue(any(row["kind"] == "removed" for row in result["lines"]))
        self.assertFalse(any(row["kind"] == "added" for row in result["lines"]))
        self.assertEqual([row["id"] for row in result["sections"]], ["c1", "c2"])
        self.assertTrue(compare_documents(before, after, "c2")["html_changed"])
        with self.assertRaisesMessage(ValueError, "identified section"):
            compare_documents(before, after, "missing")

    def test_ambiguous_section_ids_are_explicitly_refused(self):
        value = self.value('<section id="same"><p>A</p></section>'
                           '<section id="same"><p>B</p></section>')
        with self.assertRaisesMessage(ValueError, "ambiguous"):
            compare_documents(value, value, "same")


@override_settings(READING_HUB_EDITOR_PILOT=True)
class ComparisonViewTests(TestCase):
    def setUp(self):
        foundation.DocumentEditTests.setUp(self)
        self.reviewer.is_staff = True
        self.reviewer.save(update_fields=["is_staff"])
        self.client.force_login(self.reviewer)
        self.url = reverse("document-comparison", args=[self.rendition.pk])
        self.revision = save_revision(
            self.draft, self.reviewer, {**self.draft.document, "html":
                '<section id="c1"><figure class="quotation"><blockquote><p>Quoted.</p>'
                '</blockquote><figcaption><cite>Work</cite></figcaption></figure></section>'}, 0,
        )
        self.params = {"draft": self.draft.pk, "to": 1}

    def counts(self):
        return [model.objects.count() for model in (
            DocumentDraftBase, DocumentEditRevision, Rendition, DocumentPublication,
        )]

    def test_comparison_is_read_only_inert_and_displays_exact_bindings(self):
        before = self.counts()
        response = self.client.get(self.url, self.params)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "&lt;cite&gt;")
        self.assertNotContains(response, "<cite>")
        self.assertContains(response, self.draft.evidence_digest)
        self.assertContains(response, self.revision.document_digest)
        self.assertContains(response, "not a newly regenerated source draft")
        self.assertContains(response, "Partial edits")
        self.assertContains(response, "Pinned starting version")
        self.assertContains(response, "Saved version 1")
        self.assertContains(response, 'name="from"')
        self.assertContains(response, 'name="to"')
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(self.counts(), before)

    def test_scoped_html_and_download_preserve_complete_documents(self):
        response = self.client.get(self.url, {**self.params, "section": "c1"})
        self.assertContains(response, "matched by its exact ID")
        response = self.client.get(self.url, {**self.params, "section": "c1", "download": 1})
        self.assertEqual(response.json()["later"]["document"], self.revision.document)
        self.assertEqual(response.json()["selected_html_section"], "c1")
        response = self.client.get(self.url, {**self.params, "section": "absent"})
        self.assertEqual(response.status_code, 422)

    def test_download_is_exact_pinned_pair_and_not_a_verified_dataset(self):
        before = self.counts()
        response = self.client.get(self.url, {**self.params, "download": 1})
        data = response.json()
        self.assertEqual(data["earlier"]["document"], self.draft.document)
        self.assertEqual(data["later"]["document"], self.revision.document)
        self.assertEqual(data["evidence"], self.draft.evidence)
        self.assertEqual(data["semantics"], "saved_comparison_not_verified_training_pair")
        self.assertEqual(data["later"]["review"], "partial")
        self.assertEqual(data["later"]["reviewer"], self.reviewer.pk)
        self.assertEqual(data["later"]["verified_sections"], [])
        self.assertEqual(data["later"]["created_at"], self.revision.created_at.isoformat())
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertEqual(self.counts(), before)

    def test_compare_previous_revision_and_same_document_review_states(self):
        value = deepcopy(self.revision.document)
        value["title"] = "Changed title"
        save_revision(self.draft, self.reviewer, value, 1)
        response = self.client.get(self.url, {**self.params, "from": 1, "to": 2})
        self.assertContains(response, "Changed title")
        self.assertEqual(response.context["comparison"]["changed_fields"], ["title"])
        response = self.client.get(self.url, {**self.params, "from": 1})
        self.assertContains(response, "No document changes")

    def test_invalid_ranges_missing_revisions_and_foreign_drafts_are_refused(self):
        for values, status in [
            ({"from": -1}, 422), ({"from": 2}, 422), ({"to": "invalid"}, 422),
            ({"to": 99}, 404), ({"draft": "invalid"}, 422),
        ]:
            with self.subTest(values=values):
                self.assertEqual(self.client.get(self.url, {**self.params, **values}).status_code,
                                 status)
        other = Rendition.objects.create(
            document=self.rendition.document, snapshot=self.rendition.snapshot,
            identity="different-edition", title="Other", metadata={}, structure={}, html="<p>X</p>",
            stylesheet="", warnings=[], app_version="test", adapter_version="test",
            format_version="test", output_digest="different-output",
        )
        other_url = reverse("document-comparison", args=[other.pk])
        self.assertEqual(self.client.get(other_url, self.params).status_code, 404)

    def test_reviewer_permission_feature_flag_and_get_only(self):
        self.assertEqual(self.client.post(self.url, self.params).status_code, 405)
        with override_settings(READING_HUB_EDITOR_PILOT=False):
            self.assertEqual(self.client.get(self.url, self.params).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(self.url, self.params).status_code, 302)
        self.client.force_login(get_user_model().objects.create_user("ordinary-reader"))
        self.assertEqual(self.client.get(self.url, self.params).status_code, 403)
