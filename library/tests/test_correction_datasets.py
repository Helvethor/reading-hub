import json
from copy import deepcopy
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from library.models import (
    Annotation,
    CanonicalAuthor,
    CorrectionFeedback,
    Document,
    Rendition,
    Snapshot,
    SourceCorrection,
)
from library.services.correction_datasets import (
    MAX_BYTES,
    commit_import,
    dataset,
    parse_dataset,
    prepare_import,
)
from library.services.corrections import (
    SCHEMA_VERSION,
    CorrectionConflict,
    export_correction,
    save_correction,
)
from library.tests import test_corrections


class DatasetTests(TestCase):
    setUp = test_corrections.CorrectionTests.setUp
    edits = test_corrections.CorrectionTests.edits

    def test_subtitle_metadata_round_trips_only_with_schema_nine(self):
        value = self.bundle()
        value["corrections"][0]["expected"]["metadata"]["subtitle"] = "Reviewed subtitle"
        plan = prepare_import(value)
        self.assertEqual(
            plan[0]["record"]["expected"]["metadata"]["subtitle"], "Reviewed subtitle"
        )
        value["corrections"][0]["schema_version"] = 8
        with self.assertRaisesMessage(ValueError, "Subtitle metadata requires correction schema 9"):
            prepare_import(value)

    def bundle(self):
        correction = save_correction(
            self.capture, self.reviewer, self.edits(), 0, "Original decision"
        )
        return dataset([correction])

    def upload(self, value):
        return self.client.post(
            reverse("correction-dataset-import"),
            {
                "action": "preview",
                "dataset": SimpleUploadedFile(
                    "corrections.json", json.dumps(value).encode(), "application/json"
                ),
            },
        )

    def confirm(self, response):
        return self.client.post(
            reverse("correction-dataset-import"),
            {"action": "confirm", "token": response.context["token"]},
        )

    def test_preview_does_not_write_and_confirmation_appends_with_local_authority(self):
        value = self.bundle()
        value["corrections"][0]["expected"]["metadata"]["title"] = "Imported title"
        before = SourceCorrection.objects.get()
        feedback_count = CorrectionFeedback.objects.count()
        response = self.upload(value)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertContains(response, "Imported title")
        self.assertContains(response, "Reviewed title")
        self.assertEqual(SourceCorrection.objects.count(), 1)
        result = self.confirm(response)
        self.assertContains(result, "Imported 1 new revisions")
        correction = SourceCorrection.objects.latest("pk")
        self.assertEqual(correction.revision, 2)
        self.assertEqual(correction.reviewer, self.reviewer)
        self.assertEqual(correction.expected, value["corrections"][0]["expected"])
        self.assertEqual(CorrectionFeedback.objects.count(), feedback_count)
        self.assertEqual(
            correction.imported_from["record"], json.loads(json.dumps(value["corrections"][0]))
        )
        before.refresh_from_db()
        self.assertEqual(before.expected["metadata"]["title"], "Reviewed title")
        history = self.client.get(reverse("correction-revisions", args=[self.capture.pk]))
        self.assertContains(history, "Imported source revision evidence")

    def test_import_is_idempotent_and_signed_confirmation_cannot_be_replayed(self):
        value = self.bundle()
        response = self.upload(value)
        self.assertEqual(self.confirm(response).status_code, 200)
        self.assertEqual(self.confirm(response).status_code, 409)
        again = self.upload(value)
        self.assertContains(again, "Already imported; will be skipped.")
        self.assertContains(self.confirm(again), "Imported 0 new revisions; skipped 1")
        self.assertEqual(SourceCorrection.objects.count(), 2)

    def test_preview_is_bound_to_user_and_expires_and_detects_tampering(self):
        response = self.upload(self.bundle())
        token = response.context["token"]
        target = reverse("correction-dataset-import")
        self.assertEqual(
            self.client.post(target, {"action": "confirm", "token": token + "x"}).status_code,
            400,
        )
        with patch("django.core.signing.time.time", return_value=10**11):
            self.assertContains(
                self.client.post(target, {"action": "confirm", "token": token}),
                "invalid or expired",
                status_code=400,
            )
        second = get_user_model().objects.create_superuser("second")
        self.client.force_login(second)
        self.assertContains(
            self.client.post(target, {"action": "confirm", "token": token}),
            "another reviewer or profile",
            status_code=400,
        )
        self.assertEqual(SourceCorrection.objects.count(), 1)

    def test_concurrent_correction_requires_fresh_preview(self):
        response = self.upload(self.bundle())
        save_correction(self.capture, self.reviewer, {}, 1, "Newer local decision")
        self.assertContains(self.confirm(response), "changed after preview", status_code=409)
        self.assertEqual(SourceCorrection.objects.count(), 2)

    def test_changed_capture_after_preview_rejects_without_any_writes(self):
        response = self.upload(self.bundle())
        self.capture.response["digest"] = "e" * 64
        self.capture.save(update_fields=["response"])
        self.assertContains(self.confirm(response), "No exact retained", status_code=400)
        self.assertEqual(SourceCorrection.objects.count(), 1)

    def test_history_import_orders_source_revisions_and_preserves_reset(self):
        self.bundle()
        save_correction(self.capture, self.reviewer, {}, 1, "Reset decision")
        value = dataset(self.capture.corrections.all())
        self.assertEqual([record["revision"] for record in value["corrections"]], [2, 1])
        rows = prepare_import(value)
        self.assertEqual([row["record"]["revision"] for row in rows], [1, 2])
        created, skipped = commit_import(value, self.reviewer, {str(self.capture.pk): 2})
        self.assertEqual((created, skipped), (2, 0))
        self.assertEqual(SourceCorrection.objects.latest("pk").expected, {})
        self.assertEqual(SourceCorrection.objects.latest("pk").revision, 4)

    def test_invalid_records_reject_entire_dataset(self):
        value = self.bundle()
        cases = [
            ("schema_version", 99),
            ("schema_version", True),
            ("revision", False),
            ("adapter_version", "stale"),
            ("capture", {"url": "https://example.com/"}),
            ("original", None),
            ("created_at", "not a date"),
            ("reason", ["not text"]),
            ("expected", {"metadata": {"dates": [{"value": "1848-99", "type": "written"}]}}),
            ("imported_from", {"unexpected": "value"}),
        ]
        for field, invalid in cases:
            with self.subTest(field=field, invalid=invalid):
                broken = deepcopy(value)
                broken["corrections"][0][field] = invalid
                self.assertEqual(self.upload(broken).status_code, 400)
        self.assertEqual(SourceCorrection.objects.count(), 1)

    def test_missing_older_history_does_not_activate_older_override(self):
        self.bundle()
        reset = save_correction(self.capture, self.reviewer, {}, 1, "Reset decision")
        full_history = dataset(self.capture.corrections.all())
        commit_import(dataset([reset]), self.reviewer, {str(self.capture.pk): 2})
        preview = prepare_import(full_history)
        self.assertTrue(preview[-1]["reapply"])
        created, _ = commit_import(full_history, self.reviewer, {str(self.capture.pk): 3})
        self.assertEqual(created, 2)
        self.assertEqual(SourceCorrection.objects.latest("pk").expected, {})
        self.assertEqual(
            commit_import(full_history, self.reviewer, {str(self.capture.pk): 5}), (0, 2)
        )

    def test_wrong_profile_digest_blocks_and_baseline_are_rejected(self):
        value = self.bundle()
        for field, invalid in [
            ("capture.profile", "another-profile"),
            ("capture.digest", "a" * 64),
            ("original.body_digest", "0" * 64),
            ("original.blocks", []),
            ("original.metadata", {}),
            ("original.provenance", []),
        ]:
            broken = deepcopy(value)
            parent, key = field.split(".")
            broken["corrections"][0][parent][key] = invalid
            with self.subTest(field=field):
                self.assertEqual(self.upload(broken).status_code, 400)
        self.assertEqual(SourceCorrection.objects.count(), 1)

    def test_duplicates_and_ambiguous_captures_are_explicit_errors(self):
        value = self.bundle()
        value["corrections"] *= 2
        self.assertContains(self.upload(value), "Duplicate source revision", status_code=400)
        self.capture.pk = None
        self.capture.save()
        self.assertContains(
            self.upload(
                {"dataset_schema": SCHEMA_VERSION, "corrections": value["corrections"][:1]}
            ),
            "Ambiguous local capture",
            status_code=400,
        )

    def test_atomic_import_rolls_back_if_a_later_write_fails(self):
        self.bundle()
        save_correction(self.capture, self.reviewer, {}, 1, "Reset")
        value = dataset(self.capture.corrections.all())
        count = 0

        def fail_second(*args, **kwargs):
            nonlocal count
            count += 1
            if count == 2:
                raise CorrectionConflict("Concurrent update")
            return save_correction(*args, **kwargs)

        with patch("library.services.correction_datasets.save_correction", side_effect=fail_second):
            with self.assertRaises(CorrectionConflict):
                commit_import(value, self.reviewer, {str(self.capture.pk): 2})
        self.assertEqual(SourceCorrection.objects.count(), 2)

    def test_roundtrip_preserves_import_provenance_without_account_identifiers(self):
        value = self.bundle()
        value["corrections"][0]["reviewer_id"] = 999999
        self.assertEqual(self.confirm(self.upload(value)).status_code, 200)
        exported = export_correction(SourceCorrection.objects.latest("pk"))
        self.assertNotIn("reviewer_id", json.dumps(exported))
        self.assertTrue(prepare_import(dataset([SourceCorrection.objects.latest("pk")])))

    def test_legacy_envelopes_and_schemas_remain_supported(self):
        value = self.bundle()
        for version in (1, 2, 3):
            record = deepcopy(value["corrections"][0])
            record.pop("imported_from")
            record["schema_version"] = version
            record["reviewer_id"] = 5
            self.assertEqual(
                self.upload({"dataset_schema": version, "corrections": [record]}).status_code,
                200,
            )
        value["dataset_schema"] = 1
        self.assertContains(self.upload(value), "exceeds the dataset", status_code=400)

    def test_schema_four_canonical_snapshot_roundtrip_and_legacy_rejection(self):
        author = CanonicalAuthor.objects.create(name="Friedrich Engels")
        expected = self.edits()
        expected["metadata"]["people"][0]["canonical"] = {
            "name": author.name,
            "authority_uri": author.authority_uri,
        }
        correction = save_correction(self.capture, self.reviewer, expected, 0, "")
        value = dataset([correction])
        self.assertEqual(self.upload(value).status_code, 200)
        self.assertEqual(self.confirm(self.upload(value)).status_code, 200)
        self.assertEqual(SourceCorrection.objects.latest("pk").expected, expected)
        value["corrections"][0]["schema_version"] = 3
        self.assertContains(self.upload(value), "require correction schema 4", status_code=400)

    def test_filtered_export_uses_latest_revision_and_no_accounts(self):
        self.bundle()
        save_correction(self.capture, self.reviewer, {"metadata": {"language": "da"}}, 1, "Danish")
        document = Document.objects.create(url=self.capture.url)
        snapshot = Snapshot.objects.create(document=document, digest="a" * 64, manifest={})
        rendition = Rendition.objects.create(
            document=document,
            snapshot=snapshot,
            identity="b" * 64,
            title="Retained article",
            structure={"toc": []},
            html="<p>Retained article.</p>",
        )
        Annotation.objects.create(
            owner=self.reviewer,
            rendition=rendition,
            start=0,
            end=len("PRIVATE_MARK_78F31"),
            quote="PRIVATE_MARK_78F31",
            kind=Annotation.Kind.HIGHLIGHT,
            color=Annotation.Color.YELLOW,
        )
        target = reverse("correction-dataset-export")
        self.assertEqual(self.client.get(target).json()["corrections"], [])
        response = self.client.get(target, {"language": "all"})
        self.assertEqual(len(response.json()["corrections"]), 1)
        self.assertEqual(response.json()["corrections"][0]["revision"], 2)
        self.assertNotIn("reviewer_id", response.content.decode())
        self.assertNotIn("PRIVATE_MARK_78F31", response.content.decode())
        self.assertEqual(response.json()["semantics"], "explicit_verified_overrides")
        self.assertEqual(
            self.client.get(target, {"source": "another.org", "language": "all"}).json()[
                "corrections"
            ],
            [],
        )

    def test_permissions_csrf_and_upload_limits(self):
        value = self.bundle()
        regular = get_user_model().objects.create_user("ordinary")
        self.client.force_login(regular)
        for name in ("correction-dataset-import", "correction-dataset-export"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403)
        self.assertEqual(self.upload(value).status_code, 403)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.reviewer)
        self.assertEqual(
            csrf.post(reverse("correction-dataset-import"), {"action": "confirm"}).status_code,
            403,
        )
        with self.assertRaisesMessage(ValueError, "1 MiB"):
            parse_dataset(b"x" * (MAX_BYTES + 1))
        for raw in (b"not json", b"\xff", b"[]", b'{"dataset_schema":true,"corrections":[]}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_dataset(raw)
        too_many = {"dataset_schema": 3, "corrections": value["corrections"] * 51}
        with self.assertRaisesMessage(ValueError, "50"):
            parse_dataset(json.dumps(too_many).encode())
        with self.assertRaisesMessage(ValueError, "50"):
            dataset([SourceCorrection.objects.get()] * 51)
        with self.assertRaises(ValueError):
            parse_dataset(b"{}")
