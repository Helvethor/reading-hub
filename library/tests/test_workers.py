import io
import os
import tempfile
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import call, patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from library.models import Job, WorkerInstance
from library.services.pipeline import claim_job, enqueue, process_job, recover_interrupted
from library.services.workers import (
    WorkerControlError,
    configured_pool,
    operate,
    process_identity,
    process_info,
    save_pool,
    save_worker,
    worker_rows,
)
from library.tests.test_sources import ARTICLE


@override_settings(READING_HUB_ALLOW_WORKERS=True)
class WorkerControlsTests(TestCase):
    def scheduler(self):
        from library.management.commands.run_import_worker import Command

        command = Command()
        command.cursor, command.corpus, command.recovered_sites = 0, None, set()
        return command

    def test_busy_source_does_not_block_other_sources_or_recover_their_pages(self):
        import fcntl

        from library.services.catalogue import configured_sites

        sites = list(configured_sites().order_by("pk")[:2])
        for site in sites:
            site.enabled = True
            site.save()
        first, second = sites
        first.frontier.update(status="fetching")
        with (
            Path(self.temp.name, f"crawl-{first.pk}.lock").open("a") as lock,
            patch(
                "library.management.commands.run_import_worker.crawl_step", return_value=True
            ) as step,
        ):
            fcntl.flock(lock, fcntl.LOCK_EX)
            self.assertEqual(self.scheduler().background_step(None), (True, False))
            self.assertEqual(step.call_args.kwargs["site_id"], second.pk)
        self.assertTrue(first.frontier.filter(status="fetching").exists())

    def test_single_worker_rotates_sources_and_sampling_without_starvation(self):
        from unittest.mock import Mock

        from library.services.catalogue import configured_sites

        sites = list(configured_sites().order_by("pk")[:2])
        for site in sites:
            site.enabled = True
            site.save()
        corpus = SimpleNamespace(step=Mock(return_value=True), progress=None)
        command = self.scheduler()
        with (
            patch(
                "library.management.commands.run_import_worker.crawl_step", return_value=True
            ) as step,
            patch(
                "library.management.commands.run_import_worker.import_string",
                return_value=lambda: corpus,
            ),
        ):
            for _ in range(3):
                self.assertEqual(command.background_step(None), (True, False))
        self.assertEqual([c.kwargs["site_id"] for c in step.call_args_list], [s.pk for s in sites])
        corpus.step.assert_called_once()

    def test_background_recovery_can_keep_existing_robots_cache(self):
        from library.services.catalogue import FETCHERS, configured_sites, recover_crawls

        site = configured_sites().first()
        site.enabled, site.status = True, "running"
        site.save()
        site.frontier.update(status="fetching")
        sentinel = object()
        with patch.dict(FETCHERS, {site.pk: sentinel}, clear=True):
            recover_crawls(clear_fetchers=False)
            self.assertIs(FETCHERS[site.pk], sentinel)
        site.refresh_from_db()
        self.assertEqual(site.status, "ready")
        self.assertFalse(site.frontier.filter(status="fetching").exists())

    def test_memory_exhaustion_is_a_visible_job_failure_not_a_success(self):
        worker = configured_pool().workers.get()
        enqueue(ARTICLE)
        job = claim_job(worker)
        with (
            patch("library.services.pipeline.fetch_snapshot", side_effect=MemoryError),
            patch("library.services.workers.release_memory_limit") as release,
            self.assertRaises(MemoryError),
        ):
            process_job(job)
        release.assert_called_once()
        job.refresh_from_db()
        self.assertEqual(job.status, "failed")
        self.assertEqual(job.error_code, "memory_limit")

    def setUp(self):
        self.client.force_login(
            get_user_model().objects.create_user("administrator", is_staff=True)
        )
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        settings = override_settings(DATA_DIR=Path(self.temp.name), ALLOWED_HOSTS=["testserver"])
        settings.enable()
        self.addCleanup(settings.disable)
        from library.services import workers

        self.addCleanup(workers._children.clear)

    def test_defaults_and_no_processes_started_on_get(self):
        with patch("library.services.workers.subprocess.Popen") as spawn:
            response = self.client.get("/workers/")
            self.assertContains(response, "Worker administration")
            self.assertContains(response, "1024 MiB")
            self.assertContains(response, 'name="worker_count"')
            spawn.assert_not_called()
        pool = configured_pool()
        self.assertEqual(pool.worker_count, 1)
        worker = pool.workers.get()
        self.assertEqual(worker.memory_mib, 1024)
        self.assertFalse(worker.desired_running)
        self.assertEqual(
            self.client.get("/workers/status/").json()["workers"][0]["status"], "stopped"
        )
        self.assertEqual(self.client.get("/workers/control/").status_code, 405)

    def test_environment_supervisor_stops_workers_outside_configured_pool(self):
        from library.management.commands.manage_environment_workers import Command

        save_pool(3, 1024)
        save_pool(1, 1024)
        pool = configured_pool()
        workers = list(pool.workers.order_by("number"))
        with (
            patch("library.management.commands.manage_environment_workers.operate") as operate,
            patch(
                "library.management.commands.manage_environment_workers.process_info",
                return_value={"rss": 1},
            ),
            patch(
                "library.management.commands.manage_environment_workers.worker_rows",
                return_value=(pool, [{"worker": workers[0], "live": True}]),
            ),
            patch(
                "library.management.commands.manage_environment_workers.write_supervisor_status",
                return_value={"healthy": True},
            ),
        ):
            self.assertEqual(Command().start_pool(), {"healthy": True})

        self.assertEqual(
            operate.call_args_list,
            [
                call("start", workers[0].pk),
                call("stop", workers[1].pk),
                call("stop", workers[2].pk),
            ],
        )

    def test_pool_and_individual_settings_and_bounds(self):
        response = self.client.post(
            "/workers/control/",
            {
                "action": "save",
                "worker_count": 2,
                "memory_mib": 768,
            },
        )
        self.assertEqual(response.status_code, 302)
        pool = configured_pool()
        self.assertEqual(pool.workers.count(), 2)
        worker = pool.workers.first()
        response = self.client.post(
            f"/workers/{worker.pk}/",
            {
                "action": "save",
                f"worker-{worker.pk}-memory_mib": 512,
            },
        )
        self.assertEqual(response.status_code, 302)
        worker.refresh_from_db()
        self.assertEqual(worker.memory_mib, 512)
        for count, memory in [(0, 1024), (9, 1024), (2, 128), (2, 8193)]:
            self.assertEqual(
                self.client.post(
                    "/workers/control/",
                    {
                        "action": "save",
                        "worker_count": count,
                        "memory_mib": memory,
                    },
                ).status_code,
                400,
            )
        self.assertEqual(
            self.client.post(
                f"/workers/{worker.pk}/",
                {
                    "action": "save",
                    f"worker-{worker.pk}-memory_mib": 255,
                },
            ).status_code,
            400,
        )
        with self.assertRaises(WorkerControlError):
            save_pool(100, 1024)
        with self.assertRaises(WorkerControlError):
            save_worker(worker.pk, 1)

    def test_start_idempotency_global_and_individual_lifecycle(self):
        save_pool(2, 1024)

        def live(worker):
            return {"rss": 100, "virtual": 1000} if worker.pid else None

        with (
            patch(
                "library.services.workers.subprocess.Popen",
                return_value=SimpleNamespace(pid=99999, poll=lambda: None),
            ) as spawn,
            patch("library.services.workers.process_identity", return_value="start"),
            patch("library.services.workers.process_info", side_effect=live),
        ):
            operate("start")
            operate("start")
            self.assertEqual(spawn.call_count, 2)
            worker = configured_pool().workers.first()
            operate("restart", worker.pk)
            worker.refresh_from_db()
            self.assertTrue(worker.restart_requested)
            operate("stop", worker.pk)
            worker.refresh_from_db()
            self.assertFalse(worker.desired_running)
            self.assertFalse(worker.restart_requested)
            self.assertEqual(worker.status, "stopping")
            with self.assertRaises(WorkerControlError):
                operate("start", worker.pk)
            save_pool(1, 768)
            second = WorkerInstance.objects.get(number=2)
            self.assertFalse(second.desired_running)
            self.assertTrue(worker_rows()[1][0]["pending_memory"])
            operate("stop")
            self.assertFalse(WorkerInstance.objects.filter(desired_running=True).exists())

    def test_spawn_failure_is_visible_and_invalid_actions_do_not_spawn(self):
        with patch(
            "library.services.workers.subprocess.Popen", side_effect=OSError("not executable")
        ):
            response = self.client.post("/workers/control/", {"action": "start"})
        self.assertContains(response, "not executable", status_code=400)
        self.assertEqual(configured_pool().workers.get().status, "failed")
        self.assertEqual(
            self.client.post("/workers/control/", {"action": "destroy"}).status_code, 400
        )
        self.assertEqual(self.client.post("/workers/99999/", {"action": "start"}).status_code, 404)

    def test_csrf_and_profile_isolation(self):
        client = Client(enforce_csrf_checks=True)
        client.get("/workers/")
        self.assertEqual(client.post("/workers/control/", {"action": "start"}).status_code, 403)
        from library.models import WorkerPool

        other = WorkerPool.objects.create(profile="another")
        worker = other.workers.create(number=1)
        self.assertEqual(
            self.client.post(f"/workers/{worker.pk}/", {"action": "start"}).status_code, 404
        )
        self.assertEqual(self.client.get(f"/workers/{worker.pk}/log/").status_code, 404)

    def test_logs_are_bounded_and_missing_logs_are_explicit(self):
        worker = configured_pool().workers.get()
        self.assertContains(self.client.get(f"/workers/{worker.pk}/log/"), "No process log yet")
        path = Path(self.temp.name, "workers", f"{worker.pk}.log")
        path.write_bytes(b"a" * 20000 + b"\nlast line")
        response = self.client.get(f"/workers/{worker.pk}/log/")
        self.assertEqual(len(response.content), 16384)
        self.assertTrue(response.content.endswith(b"last line"))

    def test_job_ownership_and_recovery_do_not_fail_other_live_workers(self):
        save_pool(2, 1024)
        first, second = list(configured_pool().workers.order_by("number"))
        enqueue(ARTICLE)
        enqueue(ARTICLE + "other/")
        a, b = claim_job(first), claim_job(second)
        self.assertNotEqual(a.pk, b.pk)
        self.assertEqual(a.worker_id, first.pk)
        self.assertIsNone(claim_job(first))
        Job.objects.update(heartbeat=timezone.now() - timedelta(hours=1))
        with patch(
            "library.services.workers.process_info",
            side_effect=lambda w: {"rss": 1} if w.pk == second.pk else None,
        ):
            recover_interrupted()
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual(a.status, "failed")
        self.assertEqual(b.status, "running")

    def test_exited_worker_status_recovers_its_owned_job(self):
        worker = configured_pool().workers.get()
        worker.status = "running"
        worker.desired_running = True
        worker.save()
        enqueue(ARTICLE)
        job = claim_job(worker)
        _, rows = worker_rows()
        self.assertEqual(rows[0]["worker"].status, "failed")
        job.refresh_from_db()
        self.assertEqual(job.error_code, "interrupted")

    def test_pid_identity_must_match_before_reporting_memory(self):
        worker = configured_pool().workers.get()
        worker.pid = os.getpid()
        worker.process_start = "different-generation"
        self.assertIsNone(process_info(worker))
        self.assertIsNotNone(process_identity(os.getpid()))

    def test_background_steps_are_exclusive(self):
        import fcntl

        with (
            Path(self.temp.name, "background.lock").open("a") as lock,
            patch("library.management.commands.run_import_worker.crawl_step") as crawl,
        ):
            fcntl.flock(lock, fcntl.LOCK_EX)
            call_command("run_import_worker", once=True, stdout=io.StringIO())
            crawl.assert_not_called()
