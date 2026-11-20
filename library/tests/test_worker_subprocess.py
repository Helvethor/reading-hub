import time
import unittest

from django.conf import settings
from django.test import TransactionTestCase

from library.models import Blob, Document, Job, Snapshot, URLAlias
from library.services.pipeline import enqueue, snapshot_digest
from library.services.storage import read_blob, store_blob
from library.services.workers import configured_pool, operate, process_info
from library.tests.test_sources import ARTICLE, article_html


@unittest.skipUnless(
    settings.READING_HUB_ALLOW_WORKERS, "Run with workflow.py test --with-workers."
)
class WorkerSubprocessTests(TransactionTestCase):
    def test_worker_processes_offline_job_and_stops_cleanly(self):
        source_bytes = article_html()
        digest = store_blob(source_bytes)
        Blob.objects.create(digest=digest, media_type="text/html", size=len(source_bytes))
        document = Document.objects.create(url=ARTICLE, title="Synthetic worker test")
        URLAlias.objects.create(url=ARTICLE, document=document)
        manifest = {
            "pages": [
                {
                    "url": ARTICLE,
                    "resolved_url": ARTICLE,
                    "digest": digest,
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "retrieved_at": "2026-01-01T00:00:00+00:00",
                }
            ],
            "assets": {},
            "synthetic": True,
        }
        source = Snapshot.objects.create(
            document=document,
            digest=snapshot_digest(manifest),
            manifest=manifest,
        )
        job = enqueue(ARTICLE, Job.Mode.REFORMAT, source)
        worker = configured_pool().workers.get(number=1)

        operate("start", worker.pk)
        try:
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                job.refresh_from_db()
                if job.status in {Job.Status.READY, Job.Status.FAILED}:
                    break
                time.sleep(0.25)
            self.assertEqual(job.status, Job.Status.READY, job.error)
            self.assertEqual(job.rendition.snapshot_id, source.pk)
            for page in job.rendition.snapshot.manifest["pages"]:
                self.assertTrue(read_blob(page["digest"]))
        finally:
            operate("stop", worker.pk)

        worker.refresh_from_db()
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and process_info(worker):
            time.sleep(0.25)
            worker.refresh_from_db()
        self.assertIsNone(process_info(worker))
        self.assertEqual(worker.status, "stopped")
