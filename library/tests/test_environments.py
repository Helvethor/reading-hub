import io
import json
import os
import socket
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import RequestFactory, SimpleTestCase, override_settings

import workflow
from config.environments import validate_environment
from library.management.commands.runserver import UncachedDevelopmentHandler
from library.middleware import ReaderPolicyMiddleware
from library.services.workers import WorkerControlError, _start


class EnvironmentContractTests(SimpleTestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="reading-hub-environments-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.checkout = self.root / "checkout"
        self.checkout.mkdir()
        self.state = self.root / "state"
        self.state.mkdir()
        self.override = patch.dict(os.environ, {"READING_HUB_STATE": str(self.state)})
        self.override.start()
        self.addCleanup(self.override.stop)

    def registration(self, data):
        workflow.write_json(
            self.state / "live.json",
            {
                "data": str(data),
                "database": str(data / "library.sqlite3"),
                "checkout": str(self.checkout),
                "python": "/usr/bin/python",
                "profile": "profiles.marxist.site",
            },
        )

    def test_live_storage_is_rejected_before_any_runtime_file_is_created(self):
        live = self.checkout / "data"
        for role in ("development", "test", "staging"):
            with self.subTest(role=role), self.assertRaisesRegex(ValueError, "protected live"):
                validate_environment(role, self.checkout, live, live / "library.sqlite3")
        self.assertFalse(live.exists())

    def test_registered_live_and_database_override_are_protected(self):
        live = self.root / "private-live"
        self.registration(live)
        isolated = self.root / "dev"
        with self.assertRaisesRegex(ValueError, "protected live"):
            validate_environment("staging", self.checkout, live, live / "library.sqlite3")
        with self.assertRaisesRegex(ValueError, "inside their isolated"):
            validate_environment("development", self.checkout, isolated, live / "library.sqlite3")
        self.assertFalse(isolated.exists())

    def test_symlinked_root_and_runtime_files_cannot_escape_isolation(self):
        live = self.checkout / "data"
        live.mkdir()
        link = self.root / "alias"
        link.symlink_to(live, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "protected live"):
            validate_environment("development", self.checkout, link, link / "library.sqlite3")
        isolated = self.root / "dev"
        isolated.mkdir()
        for name in ("blobs", "secret-key", "workers", "development-credentials.json"):
            target = isolated / name
            target.symlink_to(live / name)
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "protected live"):
                validate_environment(
                    "development",
                    self.checkout,
                    isolated,
                    isolated / "library.sqlite3",
                )
            target.unlink()
        (isolated / "pdf").symlink_to(self.root / "another-environment")
        with self.assertRaisesRegex(ValueError, "inside isolated"):
            validate_environment(
                "development",
                self.checkout,
                isolated,
                isolated / "library.sqlite3",
            )

    def test_worktrees_and_test_runs_resolve_to_distinct_storage(self):
        second = self.root / "second"
        second.mkdir()
        self.assertNotEqual(
            workflow.instance_directory(self.checkout),
            workflow.instance_directory(second),
        )
        spec = workflow.new_spec(self.checkout, self.root / "dev", "development", "abc", 8766)
        with (
            patch.dict(
                os.environ,
                {
                    "READING_HUB_DATABASE_PATH": str(self.checkout / "data" / "library.sqlite3"),
                },
            ),
            self.assertRaisesRegex(workflow.WorkflowError, "conflicts"),
        ):
            workflow.check_overrides(spec)

    def test_development_checkouts_have_distinct_keys_and_browser_cookie_names(self):
        results = []
        for name in ("first", "second"):
            data = self.root / name
            result = subprocess.run(
                [
                    str(Path(workflow.ROOT, ".venv", "bin", "python")),
                    "-c",
                    "import json, hashlib; from config import settings as s; "
                    "print(json.dumps([s.DEBUG, s.SESSION_COOKIE_NAME, s.CSRF_COOKIE_NAME, "
                    "hashlib.sha256(s.SECRET_KEY.encode()).hexdigest(), str(s.DATABASE_PATH)]))",
                ],
                cwd=workflow.ROOT,
                env={
                    **os.environ,
                    "READING_HUB_ENVIRONMENT": "development",
                    "READING_HUB_DATA": str(data),
                    "READING_HUB_DATABASE_PATH": str(data / "library.sqlite3"),
                },
                capture_output=True,
                text=True,
                check=True,
            )
            results.append(json.loads(result.stdout))
        self.assertTrue(all(result[0] for result in results))
        for index in (1, 2, 3, 4):
            self.assertNotEqual(results[0][index], results[1][index])

    def test_occupied_port_never_stops_its_owner(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            with patch("workflow.os.kill") as kill:
                with self.assertRaisesRegex(workflow.WorkflowError, "occupied"):
                    workflow.port_free(listener.getsockname()[1])
                kill.assert_not_called()

    def test_stop_refuses_reused_pid_and_different_supervisor_token(self):
        record = {"pid": os.getpid(), "start": "not-this-process", "token": "wrong"}
        with patch("workflow.os.kill") as kill:
            with self.assertRaisesRegex(workflow.WorkflowError, "identity"):
                workflow.stop_owned(record)
            record["start"] = workflow.process_identity(os.getpid())
            with self.assertRaisesRegex(workflow.WorkflowError, "identity"):
                workflow.stop_owned(record)
            kill.assert_not_called()

    def test_candidate_source_and_assets_must_match_rehearsed_bytes(self):
        source = self.root / "source"
        source.mkdir()
        path = source / "manage.py"
        path.write_text("original", encoding="ascii")
        spec = {
            "checkout": str(source),
            "source_hashes": {"manage.py": workflow.hashlib.sha256(b"original").hexdigest()},
            "asset_hashes": {"bundle": "rehearsed"},
        }
        with patch("workflow.build_hashes", return_value={"bundle": "rehearsed"}):
            workflow.verify_candidate(spec)
        path.write_text("changed", encoding="ascii")
        with self.assertRaisesRegex(workflow.WorkflowError, "source changed"):
            workflow.verify_candidate(spec)
        path.write_text("original", encoding="ascii")
        with patch("workflow.build_hashes", return_value={"bundle": "changed"}):
            with self.assertRaisesRegex(workflow.WorkflowError, "assets changed"):
                workflow.verify_candidate(spec)

    def test_development_static_responses_ignore_old_conditional_requests(self):
        captured = {}

        def handler(environ, start_response):
            self.assertNotIn("HTTP_IF_MODIFIED_SINCE", environ)
            self.assertNotIn("HTTP_IF_NONE_MATCH", environ)
            start_response(
                "200 OK",
                [
                    ("Content-Type", "text/javascript"),
                    ("Cache-Control", "max-age=3600"),
                    ("ETag", "old"),
                    ("Last-Modified", "old"),
                ],
            )
            return [b"new source"]

        def response(status, headers, exc_info=None):
            captured.update(status=status, headers=dict(headers))

        output = UncachedDevelopmentHandler(handler)(
            {
                "HTTP_IF_MODIFIED_SINCE": "old",
                "HTTP_IF_NONE_MATCH": "old",
            },
            response,
        )
        self.assertEqual(output, [b"new source"])
        self.assertEqual(
            captured["headers"],
            {
                "Content-Type": "text/javascript",
                "Cache-Control": "no-store",
            },
        )

    @override_settings(
        READING_HUB_INSTANCE="owned-token",
        READING_HUB_ENVIRONMENT="development",
        READING_HUB_REVISION="abc working tree",
    )
    def test_health_identifies_exact_environment_without_database_access(self):
        request = RequestFactory().get("/__environment__/")
        response = ReaderPolicyMiddleware(lambda request: self.fail("Routed"))(request)
        self.assertEqual(
            json.loads(response.content),
            {
                "instance": "owned-token",
                "environment": "development",
                "revision": "abc working tree",
            },
        )
        self.assertEqual(response["Cache-Control"], "no-store")

    @override_settings(READING_HUB_ALLOW_WORKERS=False)
    def test_worker_starts_require_explicit_isolated_processing_permission(self):
        with self.assertRaisesRegex(WorkerControlError, "disabled"):
            _start(None)
        with self.assertRaisesRegex(CommandError, "disabled"):
            call_command("run_import_worker", once=True, stdout=io.StringIO())

    def test_promotion_requires_explicit_live_confirmation(self):
        with patch("sys.argv", ["workflow.py", "live", "promote", "HEAD"]):
            with patch("sys.stderr", new_callable=io.StringIO):
                with self.assertRaises(SystemExit) as failure:
                    workflow.main()
        self.assertEqual(failure.exception.code, 2)

    def test_failed_replacement_restores_previous_source_without_migration(self):
        current = workflow.new_spec(
            self.checkout,
            self.root / "live",
            "live",
            "old",
            8765,
        )
        current["process"] = {"pid": 123, "start": "old-process", "token": "old-token"}
        candidate = {
            **current,
            "role": "staging",
            "revision": "new",
            "data": str(self.root / "stage"),
            "database": str(self.root / "stage" / "db"),
        }
        self.registration(self.root / "live")
        restored = {"pid": 456, "start": "restored", "token": "restored-token"}
        with (
            patch("workflow.live_registration", return_value=current),
            patch("workflow.candidate_directory", return_value=self.root),
            patch("workflow.read_json", return_value=candidate),
            patch("workflow.verify_candidate"),
            patch("workflow.check_overrides"),
            patch("workflow.live_preflight") as preflight,
            patch("workflow.owned", side_effect=[True, False]),
            patch(
                "workflow.start", side_effect=[workflow.WorkflowError("startup"), restored]
            ) as start,
        ):
            with self.assertRaisesRegex(workflow.WorkflowError, "previous source restored"):
                workflow.promote(self.checkout, "new")
        preflight.assert_called_once()
        self.assertEqual(start.call_args_list[1].args[0]["revision"], "old")
        saved = json.loads((self.state / "live.json").read_text())
        self.assertEqual(saved["process"], restored)
