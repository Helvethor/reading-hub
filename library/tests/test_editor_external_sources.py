import json
from copy import deepcopy

from bs4 import BeautifulSoup
from django.core import signing
from django.test import TestCase, override_settings
from django.urls import reverse

from library.models import CatalogueEntry, CrawlCapture, CrawlSite, Document, Rendition, Snapshot
from library.profile import get_profile
from library.services.book_membership import commit_membership, preview_membership
from library.services.document_edits import branch_draft, saved_state
from library.services.document_publication import prepare_publication, publish_revision
from library.services.editor_sources import TICKET_SALT
from library.services.pipeline import snapshot_digest
from library.services.storage import blob_path, store_blob
from library.tests import test_fresh_document_drafts as foundation


@override_settings(READING_HUB_EDITOR_PILOT=True)
class ExternalEditorSourceTests(TestCase):
    def setUp(self):
        foundation.FreshDraftTests.setUp(self)
        self.source_url = "https://www.marxists.org/archive/example/external.htm"
        self.site = CrawlSite.objects.create(profile=get_profile().key, host="www.marxists.org")
        self.book = CatalogueEntry.objects.create(
            site=self.site, url=self.rendition.document.url, title="Book",
        )
        self.member = CatalogueEntry.objects.create(
            site=self.site, url=self.source_url, title="Member", book=self.book,
        )
        page = {
            "url": self.source_url, "resolved_url": self.source_url,
            "digest": store_blob(
                b'<html><body><h1>External</h1><p>' + b'Text. ' * 25 + b'</p>'
                b'<figure><img src="https://www.marxists.org/image.jpg" alt="Plate">'
                b'<figcaption>Caption</figcaption></figure></body></html>'
            ),
            "headers": {"content-type": "text/html"},
        }
        manifest = {"pages": [page], "assets": deepcopy(self.rendition.snapshot.manifest["assets"])}
        self.external = Snapshot.objects.create(
            document=Document.objects.create(url=self.source_url),
            manifest=manifest, digest=snapshot_digest(manifest),
        )
        self.rendition.structure = {**self.rendition.structure, "book": True}
        self.rendition.save(update_fields=["structure"])
        Rendition.objects.create(
            document=self.external.document, snapshot=self.external, identity="external",
            output_digest="external-output", title="External", html="<p>External.</p>",
            metadata={}, structure={"book": False, "parts": [], "toc": []},
            stylesheet="", warnings=[], app_version="test", adapter_version="test",
            format_version="test",
        )
        self.endpoint = reverse("document-editor-source", args=[self.rendition.pk])
        self.save_url = reverse("document-editor", args=[self.rendition.pk])

    def inspect(self, **params):
        return self.client.get(self.endpoint, {"url": self.source_url, **params})

    def payload(self, html, token):
        return {
            "draft": None, "revision": 0, "conversion_approval": None,
            "document": {
                "version": 1, "title": "Historical title", "metadata": {"language": "en"},
                "html": html,
            },
            "review": "partial", "verified_sections": [], "editorial": False,
            "source_tickets": [token],
        }

    def post(self, payload):
        return self.client.post(self.save_url, json.dumps(payload), content_type="application/json")

    def test_external_image_survives_save_reopen_branch_and_publication_after_detach(self):
        listing = self.client.get(self.endpoint).json()
        self.assertEqual(listing["members"], [{"url": self.source_url, "title": "Member"}])
        preview = self.inspect(blocks="0,1,2").json()
        self.assertIn(self.blob.pk, preview["html"])
        evidence = signing.loads(preview["source_ticket"], salt=TICKET_SALT)
        self.assertEqual(
            evidence["asset_sources"]["https://www.marxists.org/image.jpg"]["digest"],
            self.blob.pk,
        )
        self.assertEqual(evidence["page"], self.external.manifest["pages"][0])
        self.assertEqual(preview["binding"]["source_digest"],
                         self.external.manifest["pages"][0]["digest"])
        html = '<section id="main"><p>Historical output.</p></section>' + (
            '<section id="added">' + preview["html"] + '</section>'
        )
        # Recovery stores this same JSON payload in the tab before submission.
        recovered = json.loads(json.dumps(self.payload(html, preview["source_ticket"])))
        response = self.post(recovered)
        self.assertEqual(response.status_code, 200, response.content)
        from library.models import DocumentDraftBase

        draft = DocumentDraftBase.objects.get(pk=response.json()["draft"])
        self.assertNotIn(self.blob.pk, draft.evidence["assets"])
        saved_html = response.json()["document"]["html"]
        decision = commit_membership(
            preview_membership(self.book, self.source_url, "detach"),
            self.reviewer, "Remove catalogue membership without changing the saved draft.",
        )
        self.assertEqual(decision.before["book"], self.book.pk)
        self.assertIsNone(decision.after["book"])
        self.member.refresh_from_db()
        self.assertIsNone(self.member.book_id)
        self.assertEqual(self.client.get(self.endpoint).json()["members"], [])
        reopened = self.client.get(self.save_url, {"draft": str(draft.pk)})
        self.assertEqual(reopened.status_code, 200)
        self.assertEqual(reopened.context["initial"]["document"]["html"], saved_html)
        row = saved_state(draft, 1)
        self.assertEqual(row.document["html"], saved_html)
        self.assertEqual(len(row.lineage["source_tickets"]), 1)
        self.assertEqual(row.issues, [])
        branch = branch_draft(draft, self.reviewer, 1)
        self.assertEqual(saved_state(branch, 0).document["html"], saved_html)
        from library.services.document_edits import save_revision

        branched = save_revision(branch, self.reviewer, branch.document, 0)
        candidate = prepare_publication(branch, branched.revision)
        publication = publish_revision(branch, self.reviewer, 1, candidate["digest"])
        self.assertTrue(publication.rendition.assets.filter(blob=self.blob).exists())
        self.assertEqual(publication.rendition.html, candidate["output"]["html"])
        self.assertEqual(
            str(BeautifulSoup(publication.rendition.html, "html.parser").select_one("#added")),
            str(BeautifulSoup(saved_html, "html.parser").select_one("#added")),
        )
        self.assertIn(self.blob.pk, publication.rendition.html)
        self.external.refresh_from_db()
        self.assertEqual(self.external.manifest["pages"][0]["url"], self.source_url)

    def test_missing_unsupported_corrupt_and_permissions_are_explicit(self):
        missing = self.client.get(self.endpoint, {
            "url": "https://www.marxists.org/archive/example/missing.htm",
        })
        self.assertEqual(missing.status_code, 422)
        self.assertIn("no retained source", missing.json()["error"])
        self.assertEqual(missing.json()["capture_url"], reverse("request"))
        unsupported = self.client.get(self.endpoint, {"url": "https://example.com/"})
        self.assertEqual(unsupported.status_code, 422)
        self.assertEqual(self.client.post(self.endpoint).status_code, 405)
        self.client.logout()
        self.assertEqual(self.inspect().status_code, 302)
        self.client.force_login(self.reviewer)
        blob_path(self.external.manifest["pages"][0]["digest"]).write_bytes(b"corrupt")
        self.assertEqual(self.inspect().status_code, 422)

    def test_missing_external_source_blob_is_refused_at_inspection_and_save(self):
        preview = self.inspect(blocks="0,1,2").json()
        blob_path(self.external.manifest["pages"][0]["digest"]).unlink()
        self.assertEqual(self.inspect().status_code, 422)
        payload = self.payload(
            '<section id="external">' + preview["html"] + '</section>',
            preview["source_ticket"],
        )
        response = self.post(payload)
        self.assertEqual(response.status_code, 422)
        self.assertIn("unavailable or corrupt", response.json()["error"])

    def test_ticket_forgery_staleness_scope_and_unbound_assets(self):
        preview = self.inspect(blocks="0,1,2").json()
        html = '<section id="external">' + preview["html"] + '</section>'
        payload = self.payload(html, preview["source_ticket"] + "x")
        self.assertEqual(self.post(payload).status_code, 422)
        payload["source_tickets"] = []
        payload["review"] = "full"
        self.assertEqual(self.post(payload).status_code, 422)
        payload = self.payload(html, preview["source_ticket"])
        saved = self.post(payload)
        self.assertEqual(saved.status_code, 200, saved.content)
        payload.update(draft=saved.json()["draft"], revision=1, conversion_approval=None)
        self.assertEqual(self.post(payload).status_code, 422)
        self.assertEqual(self.inspect(draft=payload["draft"], revision=0).status_code, 409)

    def test_capture_without_snapshot_is_available_read_only(self):
        url = "https://www.marxists.org/archive/example/capture.htm"
        response = {
            "resolved_url": url, "digest": store_blob(b"<p>Retained capture.</p>"),
            "headers": {"content-type": "text/html"},
        }
        CrawlCapture.objects.create(site=self.site, url=url, response=response)
        result = self.client.get(self.endpoint, {"url": url, "blocks": "0"})
        self.assertEqual(result.status_code, 200, result.content)
        self.assertIn("Retained capture.", result.json()["html"])
        self.assertIsNone(result.json()["snapshot"])
        image_url = "https://www.marxists.org/archive/example/capture-image.htm"
        image_response = {
            "resolved_url": image_url,
            "digest": store_blob(b'<p><img src="https://www.marxists.org/missing.jpg"></p>'),
            "headers": {"content-type": "text/html"},
        }
        CrawlCapture.objects.create(site=self.site, url=image_url, response=image_response)
        missing = self.client.get(self.endpoint, {"url": image_url, "blocks": "0"})
        self.assertEqual(missing.status_code, 422)
        self.assertIn("Selected image is not retained", missing.json()["error"])

    def test_corrupt_manifest_asset_and_changed_reviewer_are_refused(self):
        preview = self.inspect(blocks="0,1,2").json()
        html = '<section id="external">' + preview["html"] + '</section>'
        from django.contrib.auth import get_user_model

        other = get_user_model().objects.create_user("other", is_staff=True)
        self.client.force_login(other)
        self.assertEqual(self.post(self.payload(html, preview["source_ticket"])).status_code, 422)
        self.client.force_login(self.reviewer)
        blob_path(self.blob.pk).write_bytes(b"corrupt")
        self.assertEqual(self.post(self.payload(html, preview["source_ticket"])).status_code, 422)
        self.assertEqual(self.inspect(blocks="0,1,2").status_code, 422)
        self.external.manifest["pages"][0].pop("resolved_url")
        self.external.save(update_fields=["manifest"])
        self.assertEqual(self.inspect().status_code, 422)
