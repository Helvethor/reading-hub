from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup
from django.test import TestCase, override_settings
from django.urls import reverse

from library.models import CrawlCapture, MetadataSuggestion, SourceCorrection
from library.services.storage import save_response
from library.tests import test_reader_corrections
from library.tests.test_sources import ARTICLE, BOOK, PARAGRAPH


class ReviewNavigationTests(TestCase):
    setUp = test_reader_corrections.ReaderCorrectionTests.setUp
    response = test_reader_corrections.ReaderCorrectionTests.response
    import_version = test_reader_corrections.ReaderCorrectionTests.import_version
    reformat = test_reader_corrections.ReaderCorrectionTests.reformat

    def menu(self, response):
        return BeautifulSoup(response.content, "html.parser").find(
            "nav", attrs={"aria-label": "Work reviewer tools"}
        )

    def test_work_page_uses_one_role_aware_workspace_and_redirects_legacy_editor(self):
        version = self.import_version(ARTICLE)
        self.client.logout()
        response = self.client.get(reverse("reader", args=[version.pk]))
        soup = BeautifulSoup(response.content, "html.parser")
        self.assertIsNone(self.menu(response))
        self.assertEqual(
            [tab.get_text(strip=True) for tab in soup.select(".workspace-tabs [role=tab]")],
            ["Read", "Versions", "Sources"],
        )
        self.assertIsNone(soup.select_one("#workspace-tab-edit"))
        self.assertIn("generated/public-workspace.js", " ".join(
            script.get("src", "") for script in soup.select("script[src]")
        ))
        self.assertNotIn("generated/editor-pilot.js", " ".join(
            script.get("src", "") for script in soup.select("script[src]")
        ))
        self.assertNotIn("data-read-url", response.content.decode())
        self.assertNotIn("data-pdf-url", response.content.decode())
        self.assertContains(response, PARAGRAPH)
        self.assertContains(response, 'aria-label="Work views"')
        self.assertContains(response, "data-reading-pdf>PDF</a>")
        requested_edit = self.client.get(
            reverse("reader", args=[version.pk]), {"tab": "edit"},
        )
        self.assertContains(requested_edit, 'data-initial-tab="read"')
        self.assertNotContains(requested_edit, "data-read-url")

        legacy = self.client.get(
            reverse("document-editor-legacy", args=[version.pk]),
            {"draft": "draft-id", "start": "source", "other": "kept"},
        )
        self.assertEqual(legacy.status_code, 301)
        self.assertEqual(urlsplit(legacy["Location"]).path, reverse("reader", args=[version.pk]))
        self.assertEqual(parse_qs(urlsplit(legacy["Location"]).query), {
            "draft": ["draft-id"], "start": ["source"], "other": ["kept"], "tab": ["edit"],
        })

        self.client.force_login(self.reader)
        response = self.client.get(reverse("reader", args=[version.pk]))
        soup = BeautifulSoup(response.content, "html.parser")
        self.assertIsNone(soup.select_one("#workspace-tab-edit"))
        self.assertContains(response, PARAGRAPH)
        self.assertNotContains(response, "data-read-url")
        self.assertEqual(self.client.get(reverse("work-review")).status_code, 403)

        self.client.force_login(self.reviewer)
        response = self.client.get(reverse("reader", args=[version.pk]))
        soup = BeautifulSoup(response.content, "html.parser")
        self.assertEqual([heading.get_text(strip=True) for heading in soup.find_all("h1")],
                         [version.title])
        self.assertEqual(
            [tab.get_text(strip=True) for tab in soup.select(".workspace-tabs [role=tab]")],
            ["Read", "Edit", "Versions", "Sources"],
        )
        self.assertNotIn("generated/public-workspace.js", " ".join(
            script.get("src", "") for script in soup.select("script[src]")
        ))
        self.assertContains(response, 'aria-label="Work views"')
        self.assertNotIn(">Editor</h1>", response.content.decode())
        self.assertNotIn("WORKSPACE", response.content.decode())
        self.assertNotIn('class="work-navigation"', response.content.decode())

        review_link = soup.select_one('.primary-navigation a[href*="review_version"]')
        self.assertEqual(
            review_link["href"], reverse("work-review") + f"?review_version={version.pk}"
        )
        response = self.client.get(
            reverse("reader", args=[version.pk]), {"tab": "versions"},
        )
        self.assertContains(response, 'data-initial-tab="versions"')

    @override_settings(READING_HUB_EDITOR_PILOT=True)
    @patch("library.document_editor_views.finders.find", return_value="built-asset")
    def test_round_trip_book_source_and_tools_preserves_exact_version(self, _find_asset):
        version = self.import_version(BOOK)
        # Retaining a source is still an explicit POST; navigating must not write.
        before = CrawlCapture.objects.count()
        url = reverse("work-review") + f"?review_version={version.pk}"
        response = self.client.get(url)
        self.assertEqual(CrawlCapture.objects.count(), before)
        menu = self.menu(response)
        parsing = menu.find("a", string="Document editor")["href"]
        response = self.client.get(parsing)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            reverse("rendition-correction-source", args=[version.pk]),
            {"page": "1", "review_version": str(version.pk)},
        )
        self.assertIn(f"review_version={version.pk}", response.url)
        response = self.client.get(response.url, follow=True)
        self.assertIsNone(self.menu(response))
        self.assertContains(response, 'aria-label="Work views"')
        self.assertNotContains(response, 'aria-label="Work destinations"', html=False)
        self.assertContains(response, 'id="editor-source-open"')
        capture = CrawlCapture.objects.get()
        response = self.client.get(
            reverse("work-review"),
            {"review_version": version.pk, "review_capture": capture.pk},
        )
        menu = self.menu(response)
        self.assertIn(f"capture {capture.pk}", menu.get_text())
        self.assertEqual(
            menu.find("a", string="Document editor")["href"].split("?")[0],
            reverse("document-editor", args=[version.pk]),
        )
        selector = menu.select_one("[data-source-switcher]")
        self.assertEqual(len(selector.select("option")), 3)
        self.assertEqual(selector.select_one("option[selected]")["value"], "1")
        self.assertNotIn("Parsing & source metadata", menu.get_text())
        self.assertNotIn("Selected source editor", menu.get_text())
        reading = menu.find("a", string=f"Back to reading — version {version.pk}")
        self.assertEqual(reading["href"], reverse("reader", args=[version.pk]))
        for label in (
            "Review overview",
            "Catalogue metadata",
            "Source revision history",
            "Metadata review",
            "Page membership",
        ):
            href = menu.find("a", string=label)["href"]
            self.assertEqual(parse_qs(urlsplit(href).query)["review_version"], [str(version.pk)])
            result = self.client.get(href)
            self.assertIn(result.status_code, (200, 422))
            self.assertIsNotNone(self.menu(result))
            self.assertContains(
                result, f"Back to reading — version {version.pk}", status_code=result.status_code
            )
        self.assertFalse(SourceCorrection.objects.exists())

    def test_metadata_queue_is_scoped_and_filter_form_retains_context(self):
        version = self.import_version(ARTICLE)
        capture = CrawlCapture.objects.create(
            site=self.sites["communistusa.org"],
            url=ARTICLE,
            response=save_response(self.response(ARTICLE), ARTICLE),
        )
        other = CrawlCapture.objects.create(
            site=capture.site,
            url=ARTICLE + "other",
            response=capture.response,
        )
        for index, source in enumerate((capture, other)):
            MetadataSuggestion.objects.create(
                capture=source,
                field="author",
                value=f"Person {index}",
                method="test",
                fingerprint=str(index) * 64,
            )
        url = reverse("metadata-review")
        response = self.client.get(
            url,
            {
                "review_capture": capture.pk,
                "review_version": version.pk,
                "language": "all",
            },
        )
        self.assertContains(response, "Person 0")
        self.assertNotContains(response, "Person 1")
        self.assertEqual(response.context["page"].paginator.count, 1)
        soup = BeautifulSoup(response.content, "html.parser")
        self.assertEqual(soup.select_one('input[name="review_capture"]')["value"], str(capture.pk))
        self.assertIsNotNone(soup.select_one('a[aria-current="page"]'))
        self.assertEqual(self.client.get(url, {"review_capture": "invalid"}).status_code, 404)

    @override_settings(READING_HUB_EDITOR_PILOT=True)
    def test_direct_capture_navigation_and_bad_context(self):
        version = self.import_version(ARTICLE)
        capture = CrawlCapture.objects.create(
            site=self.sites["communistusa.org"],
            url=ARTICLE,
            response=save_response(self.response(ARTICLE), ARTICLE),
        )
        response = self.client.get(reverse("correction-workspace", args=[capture.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            urlsplit(response.url).path,
            reverse("document-editor", args=[version.pk]),
        )
        self.assertEqual(
            self.client.get(
                reverse("work-review"),
                {
                    "review_version": "bad",
                },
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse("work-review"),
                {
                    "review_capture": 999999,
                },
            ).status_code,
            404,
        )
