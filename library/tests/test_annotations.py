from bs4 import BeautifulSoup
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from library.annotation_views import matching_selection, reader_text
from library.models import Annotation, Document, Rendition, Snapshot


@override_settings(ALLOWED_HOSTS=["testserver"])
class AnnotationTests(TestCase):
    def test_canonical_text_preserves_browser_whitespace_and_preformatted_text(self):
        html = "\n\n<p>One &amp; two</p>\n\n  <p>Three</p><!-- comment -->\r\n<pre>\n A\r\n B</pre>"
        expected = "\n\nOne & two\n\n  Three\n A\n B"
        self.assertEqual(reader_text(html), expected)
        start = expected.index("Three")
        self.assertTrue(matching_selection(html, start, start + 5, "Three"))

    def setUp(self):
        self.owner = get_user_model().objects.create_user("owner")
        self.other = get_user_model().objects.create_user("other", is_staff=True, is_superuser=True)
        doc = Document.objects.create(url="https://communistusa.org/example/")
        snapshot = Snapshot.objects.create(document=doc, digest="a" * 64, manifest={})
        self.html = (
            "<p>Hello \U0001f412 <em>brave</em> world &amp; friends.</p>\n<p>Second paragraph.</p>"
        )
        fields = {
            "document": doc,
            "snapshot": snapshot,
            "title": "Example",
            "structure": {"toc": []},
            "html": self.html,
            "stylesheet": "",
            "app_version": "test",
            "adapter_version": "1",
            "format_version": "1",
            "output_digest": "b" * 64,
        }
        self.version = Rendition.objects.create(identity="a" * 64, **fields)
        self.next_version = Rendition.objects.create(identity="b" * 64, **fields)
        self.url = f"/versions/{self.version.pk}/annotations/"
        self.data = {
            "start": 6,
            "end": 20,
            "quote": "\U0001f412 brave world",
            "kind": "highlight",
            "color": "yellow",
        }
        self.client.force_login(self.owner)

    def create(self):
        response = self.client.post(self.url, self.data, content_type="application/json")
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()["annotation"]

    def test_utf16_selection_matches_inline_markup_entities_and_unicode(self):
        self.create()
        self.assertTrue(matching_selection(self.html, 6, 8, "\U0001f412"))
        self.assertFalse(matching_selection(self.html, 6, 7, "\U0001f412"))
        self.assertFalse(matching_selection(self.html, 7, 8, "\U0001f412"))
        self.assertFalse(matching_selection(self.html, 0, 2**31, "Hello"))
        self.assertFalse(matching_selection(self.html, 10, 1, "Hello"))
        self.assertFalse(matching_selection(self.html, 0, 5, "Wrong"))

    def test_owner_only_even_for_staff_and_bound_to_exact_version(self):
        item = self.create()
        detail = f"{self.url}{item['id']}/"
        newer = f"/versions/{self.next_version.pk}/annotations/"
        self.assertEqual(self.client.get(newer).json(), {"annotations": []})
        self.assertEqual(self.client.delete(f"{newer}{item['id']}/").status_code, 404)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url).json(), {"annotations": []})
        self.assertEqual(
            self.client.patch(
                detail, {"kind": "underline", "color": "blue"}, content_type="application/json"
            ).status_code,
            404,
        )
        self.assertEqual(self.client.delete(detail).status_code, 404)
        self.assertTrue(Annotation.objects.filter(pk=item["id"]).exists())

    def test_edit_delete_and_overlaps_do_not_modify_cached_html(self):
        one = self.create()
        self.data.update(start=9, end=14, quote="brave", kind="underline", color="blue")
        self.create()
        url = f"{self.url}{one['id']}/"
        response = self.client.patch(
            url, {"kind": "underline", "color": "pink"}, content_type="application/json"
        )
        self.assertEqual(response.json()["annotation"]["color"], "pink")
        self.assertEqual(len(self.client.get(self.url).json()["annotations"]), 2)
        self.assertEqual(self.client.delete(url).status_code, 200)
        self.assertEqual(Annotation.objects.count(), 1)
        self.version.refresh_from_db()
        self.assertEqual(self.version.html, self.html)
        self.assertEqual(self.client.delete(url).status_code, 404)

    def test_invalid_fields_anchors_types_styles_and_json_are_rejected(self):
        for change in [
            {"owner": self.other.pk},
            {"rendition": self.next_version.pk},
            {"quote": "not the selected text"},
            {"end": 1},
            {"start": -1},
            {"end": 99999},
            {"color": "url(javascript:bad)"},
            {"kind": "script"},
            {"quote": "x" * 20001},
        ]:
            with self.subTest(change=change):
                response = self.client.post(
                    self.url, {**self.data, **change}, content_type="application/json"
                )
                self.assertEqual(response.status_code, 400)
        self.assertEqual(
            self.client.post(self.url, "[]", content_type="application/json").status_code, 400
        )
        self.assertEqual(
            self.client.post(self.url, "{", content_type="application/json").status_code, 400
        )
        self.assertEqual(self.client.post(self.url, self.data).status_code, 415)
        self.assertEqual(Annotation.objects.count(), 0)

    def test_anonymous_session_expiration_csrf_and_method_restrictions(self):
        anonymous = Client()
        self.assertEqual(anonymous.get(self.url).status_code, 401)
        self.assertEqual(
            anonymous.post(self.url, self.data, content_type="application/json").status_code, 401
        )
        self.assertEqual(self.client.put(self.url).status_code, 405)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.owner)
        page = strict.get(f"/versions/{self.version.pk}/")
        self.assertTrue(strict.cookies["csrftoken"]["httponly"])
        self.assertEqual(
            strict.post(self.url, self.data, content_type="application/json").status_code, 403
        )
        token = BeautifulSoup(page.content, "html.parser").select_one("[name=csrfmiddlewaretoken]")[
            "value"
        ]
        response = strict.post(
            self.url, self.data, content_type="application/json", HTTP_X_CSRFTOKEN=token
        )
        self.assertEqual(response.status_code, 201)
        detail = f"{self.url}{response.json()['annotation']['id']}/"
        self.assertEqual(strict.delete(detail).status_code, 403)
        self.assertEqual(
            strict.patch(
                detail, {"kind": "underline", "color": "pink"}, content_type="application/json"
            ).status_code,
            403,
        )
        self.assertEqual(strict.delete(detail, HTTP_X_CSRFTOKEN=token).status_code, 200)

    def test_per_version_limit_is_explicit_and_does_not_limit_other_versions(self):
        from unittest.mock import patch

        self.create()
        with patch("library.annotation_views.MAX_ANNOTATIONS", 1):
            self.assertEqual(
                self.client.post(self.url, self.data, content_type="application/json").status_code,
                409,
            )
            self.assertEqual(
                self.client.post(
                    f"/versions/{self.next_version.pk}/annotations/",
                    self.data,
                    content_type="application/json",
                ).status_code,
                201,
            )
