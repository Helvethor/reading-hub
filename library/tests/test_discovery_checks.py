from dataclasses import replace
from unittest.mock import patch

from django.db import connection
from django.test import TestCase

from library.models import CatalogueEntry, CrawlCapture, PageTypeDecision
from library.profile import get_profile
from library.services.corrections import block_rows, extraction, save_correction
from library.services.errors import ImportFailure
from library.services.pipeline import prepare_pages, reject_reviewed_indexes
from library.tests import test_organizations


class DiscoveryCheckTests(TestCase):
    setUp = test_organizations.OrganizationTests.setUp
    response = test_organizations.OrganizationTests.response

    def test_batch_uses_three_queries_regardless_of_number_of_urls(self):
        urls = [part["url"] for part in self.spec["parts"]]
        with self.assertNumQueries(3):
            reject_reviewed_indexes(urls * 10)
        with self.assertNumQueries(0):
            reject_reviewed_indexes([])

    def test_latest_decision_per_url_wins_but_other_urls_still_block(self):
        first, second = [part["url"] for part in self.spec["parts"][1:]]
        site = self.sites["www.marxists.org"]
        for flag in (True, False):
            PageTypeDecision.objects.create(
                site=site,
                url=first,
                discovery_only=flag,
                reviewer=self.reviewer,
                reason="Classify",
            )
        reject_reviewed_indexes([first, second])
        PageTypeDecision.objects.create(
            site=site,
            url=second,
            discovery_only=True,
            reviewer=self.reviewer,
            reason="Not readable",
        )
        with self.assertRaises(ImportFailure):
            reject_reviewed_indexes([first, second])

    def test_catalogue_or_capture_discovery_flags_block_complete_book(self):
        url = self.spec["parts"][-1]["url"]
        site = self.sites["www.marxists.org"]
        CatalogueEntry.objects.filter(site=site, url=url).update(discovery_only=True)
        with self.assertRaisesMessage(ImportFailure, "discovery index"):
            prepare_pages(self.book.snapshot.manifest)
        CatalogueEntry.objects.filter(site=site, url=url).update(discovery_only=False)
        CrawlCapture.objects.create(
            site=site,
            url=url,
            response=self.book.snapshot.manifest["pages"][-1],
            discovery_only=True,
        )
        with self.assertRaisesMessage(ImportFailure, "discovery index"):
            prepare_pages(self.book.snapshot.manifest)

    def test_unrelated_discovery_decision_does_not_block(self):
        PageTypeDecision.objects.create(
            site=self.sites["www.marxists.org"],
            url=self.spec["url"] + "?listing",
            discovery_only=True,
            reviewer=self.reviewer,
            reason="Unrelated",
        )
        source, pages = prepare_pages(self.book.snapshot.manifest)
        self.assertTrue(source.book)
        self.assertEqual(len(pages), 3)

    def test_checks_are_profile_scoped(self):
        url = self.spec["parts"][0]["url"]
        CatalogueEntry.objects.filter(url=url).update(discovery_only=True)
        PageTypeDecision.objects.create(
            site=self.sites["www.marxists.org"],
            url=url,
            discovery_only=True,
            reviewer=self.reviewer,
            reason="This profile only",
        )
        with patch(
            "library.services.pipeline.get_profile",
            return_value=replace(get_profile(), key="another-profile"),
        ):
            reject_reviewed_indexes([url])

    def test_book_preparation_batches_latest_matching_corrections(self):
        chapter_url = self.spec["parts"][0]["url"]
        entry = next(
            page for page in self.book.snapshot.manifest["pages"] if page["url"] == chapter_url
        )
        capture = CrawlCapture.objects.create(
            site=self.sites["www.marxists.org"], url=chapter_url, response=entry
        )
        source, _, body, _ = extraction(capture)
        rows = block_rows(body)
        target = rows[0]
        save_correction(
            capture,
            self.reviewer,
            {"blocks": [{"index": target["index"], "action": "exclude"}]},
            0,
            "Initial review",
        )
        duplicate = CrawlCapture.objects.create(
            site=capture.site, url=capture.url, response=capture.response
        )
        reset = save_correction(duplicate, self.reviewer, {}, 0, "Reset")
        statements = []
        with connection.execute_wrapper(
            lambda execute, sql, params, many, context: (
                statements.append(sql),
                execute(sql, params, many, context),
            )[1]
        ):
            _, pages = prepare_pages(self.book.snapshot.manifest)
        correction_queries = [sql for sql in statements if "sourcecorrection" in sql.lower()]
        self.assertEqual(len(correction_queries), 1)
        self.assertIn("ROW_NUMBER", correction_queries[0].upper())
        prepared_body = next(page for part, page in pages if part.url == chapter_url)
        self.assertIn(target["text"], prepared_body.get_text(" ", strip=True))
        self.assertEqual(reset.revision, 1)
