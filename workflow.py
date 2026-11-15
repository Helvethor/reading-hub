#!/usr/bin/env python3
"""Local development, candidate rehearsal and explicitly authorized live promotion."""

import argparse
import fcntl
import hashlib
import io
import json
import os
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import tarfile
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from config.environments import (
    live_registration,
    state_directory,
    validate_environment,
)

ROOT = Path(__file__).resolve().parent


class WorkflowError(Exception):
    pass


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise WorkflowError(f"Cannot read {path}: {exc}") from exc


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}")
    with temporary.open("x", encoding="utf-8") as file:
        os.chmod(temporary, 0o600)
        json.dump(value, file, indent=2)
        file.write("\n")
    temporary.replace(path)


def run(arguments, *, cwd, env=None, capture=False):
    result = subprocess.run(
        [str(argument) for argument in arguments],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=capture,
        check=False,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout or "").strip() if capture else ""
        raise WorkflowError(f"Command failed ({result.returncode}): {arguments[0]} {detail}")
    return result.stdout.strip() if capture else None


def commit(checkout, revision="HEAD"):
    return run(
        ["git", "rev-parse", "--verify", f"{revision}^{{commit}}"],
        cwd=checkout,
        capture=True,
    )


def instance_directory(checkout):
    identity = hashlib.sha256(str(checkout).encode()).hexdigest()[:20]
    return state_directory() / "checkouts" / identity


def candidate_directory(checkout, revision):
    return instance_directory(checkout) / "candidates" / commit(checkout, revision)


def ensure_state(checkout):
    state = state_directory()
    validate_environment("development", checkout, state, state / "unused.sqlite3")
    state.mkdir(parents=True, exist_ok=True, mode=0o700)


@contextmanager
def live_operation():
    with (state_directory() / "live-operation.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise WorkflowError(
                "Another live operation is in progress; leave it untouched."
            ) from exc
        yield


def environment(spec, *, instance=""):
    role = spec["role"]
    data, database = validate_environment(
        role,
        spec["checkout"],
        spec["data"],
        spec["database"],
    )
    result = dict(os.environ)
    result.update(
        {
            "DJANGO_SETTINGS_MODULE": "config.settings",
            "READING_HUB_STATE": str(state_directory()),
            "READING_HUB_ENVIRONMENT": role,
            "READING_HUB_DATA": str(data),
            "READING_HUB_DATABASE_PATH": str(database),
            "READING_HUB_PROFILE": spec["profile"],
            "READING_HUB_REVISION": spec["revision"],
            "READING_HUB_INSTANCE": instance,
            "READING_HUB_ALLOW_WORKERS": "1" if spec.get("allow_workers") else "0",
            "READING_HUB_EDITOR_PILOT": spec.get("editor_pilot", "1"),
            "PYTHONUNBUFFERED": "1",
        }
    )
    return result


def check_overrides(spec):
    for name, expected in (
        ("READING_HUB_DATA", spec["data"]),
        ("READING_HUB_DATABASE_PATH", spec["database"]),
    ):
        value = os.environ.get(name)
        if value and Path(value).expanduser().resolve() != Path(expected).resolve():
            raise WorkflowError(f"{name} conflicts with this managed environment; unset it.")


def dependencies(checkout):
    if sys.version_info < (3, 14):
        raise WorkflowError("Run the launcher with Python >= 3.14.")
    python = checkout / ".venv" / "bin" / "python"
    if not python.exists():
        run([sys.executable, "-m", "venv", checkout / ".venv"], cwd=checkout)
    available = subprocess.run(
        [str(python), "-c", "import django, bs4, nh3, PIL, weasyprint, pypdf"],
        cwd=checkout,
        capture_output=True,
        check=False,
    )
    if available.returncode:
        run([python, "-m", "pip", "install", "-r", "requirements.lock"], cwd=checkout)
        run([python, "-m", "pip", "install", "--no-deps", "-e", "."], cwd=checkout)
    if not (checkout / "node_modules" / "esbuild").exists():
        run(["npm", "ci"], cwd=checkout)
    return str(python)


def django(spec, *arguments, capture=False):
    return run(
        [spec["python"], "manage.py", *arguments],
        cwd=spec["checkout"],
        env=environment(spec),
        capture=capture,
    )


def initialize(spec):
    check_overrides(spec)
    environment(spec)
    spec["python"] = dependencies(Path(spec["checkout"]))
    django(spec, "migrate", "--noinput")
    django(spec, "seed_development")
    run(["npm", "run", "build"], cwd=spec["checkout"])
    django(spec, "check")
    django(spec, "makemigrations", "--check", "--dry-run")


def new_spec(checkout, directory, role, revision, port):
    return {
        "role": role,
        "checkout": str(checkout),
        "data": str(directory / "data"),
        "database": str(directory / "data" / "library.sqlite3"),
        "python": str(checkout / ".venv" / "bin" / "python"),
        "profile": os.environ.get("READING_HUB_PROFILE", "profiles.marxist.site"),
        "revision": revision,
        "port": port,
        "allow_workers": False,
        "legacy": False,
    }


def dev_init(checkout, port):
    directory = instance_directory(checkout) / "development"
    spec_path = directory / "environment.json"
    if spec_path.exists():
        spec = read_json(spec_path)
        check_overrides(spec)
        print(f"Development already initialized: {directory}")
        return
    spec = new_spec(
        checkout,
        directory,
        "development",
        f"{commit(checkout)[:12]} working tree",
        port,
    )
    initialize(spec)
    write_json(spec_path, spec)
    print(f"Development initialized: {directory}")
    print(f"Private test identities: {directory / 'data' / 'development-credentials.json'}")
    print(f"Fixture URLs: {directory / 'data' / 'development-fixtures.json'}")


def build_hashes(checkout):
    generated = checkout / "library" / "static" / "library" / "generated"
    names = ("editor-pilot.js", "editor-pilot.css", "editor-licenses.txt", "public-workspace.js")
    return {name: hashlib.sha256((generated / name).read_bytes()).hexdigest() for name in names}


def stage_prepare(checkout, revision, port):
    directory = candidate_directory(checkout, revision)
    if (directory / "environment.json").exists():
        verify_candidate(read_json(directory / "environment.json"))
        print(f"Candidate already prepared: {directory}")
        return
    source = directory / "source"
    if source.exists():
        raise WorkflowError(
            f"Incomplete candidate at {directory}; inspect it and remove only that failed "
            "candidate before retrying."
        )
    archive = subprocess.run(
        ["git", "archive", commit(checkout, revision)],
        cwd=checkout,
        capture_output=True,
        check=True,
    ).stdout
    source.mkdir(parents=True, mode=0o700)
    with tarfile.open(fileobj=io.BytesIO(archive)) as files:
        if any(member.issym() or member.islnk() for member in files.getmembers()):
            raise WorkflowError("Candidate source archives must not contain symlinks.")
        source_names = [member.name for member in files.getmembers() if member.isfile()]
        files.extractall(source, filter="data")
    spec = new_spec(source, directory, "staging", commit(checkout, revision), port)
    spec["repository"] = str(checkout)
    spec["source_hashes"] = {
        name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in source_names
    }
    initialize(spec)
    spec["asset_hashes"] = build_hashes(source)
    write_json(directory / "environment.json", spec)
    print(f"Frozen candidate ready: {spec['revision']}")
    print(f"Private fixture identities and URLs: {directory / 'data'}")


def verify_candidate(spec):
    source = Path(spec["checkout"])
    observed = set()
    for directory, directories, files in source.walk():
        directories[:] = [
            name
            for name in directories
            if name not in {".venv", "node_modules", "__pycache__", ".ruff_cache"}
            and not name.endswith(".egg-info")
            and directory / name != source / "library/static/library/generated"
        ]
        for name in directories + files:
            path = directory / name
            if path.is_symlink():
                raise WorkflowError(f"Frozen candidate source became a symlink: {path}")
        observed.update(
            (directory / name).relative_to(source).as_posix()
            for name in files
            if not name.endswith((".pyc", ".pyo"))
        )
    if observed != set(spec["source_hashes"]):
        raise WorkflowError("Frozen candidate source inventory changed; prepare a new candidate.")
    for name, digest in spec["source_hashes"].items():
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != digest:
            raise WorkflowError(f"Frozen candidate source changed: {name}")
    if build_hashes(source) != spec["asset_hashes"]:
        raise WorkflowError("Frozen candidate assets changed; prepare a new committed candidate.")


def process_identity(pid):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(") ", 1)[1].split()
        return None if fields[0] == "Z" else fields[19]
    except FileNotFoundError, ProcessLookupError:
        return None


def process_record(pid, *, token="", checkout=""):
    return {
        "pid": pid,
        "start": process_identity(pid),
        "token": token,
        "checkout": str(checkout),
    }


def owned(record):
    pid = record["pid"]
    path = Path(f"/proc/{pid}")
    if process_identity(pid) != record["start"]:
        return False
    if path.stat().st_uid != os.getuid():
        raise WorkflowError("Process belongs to another user.")
    arguments = (path / "cmdline").read_bytes().split(b"\0")
    if record.get("token"):
        return record["token"].encode() in arguments and b"_serve" in arguments
    return (
        b"runserver" in arguments
        and b"--noreload" in arguments
        and (path / "cwd").resolve() == Path(record["checkout"]).resolve()
    )


def stop_owned(record):
    if not owned(record):
        raise WorkflowError("Recorded process identity no longer matches; no process was stopped.")
    os.kill(record["pid"], signal.SIGTERM)
    deadline = time.monotonic() + 15
    while process_identity(record["pid"]) == record["start"]:
        if time.monotonic() >= deadline:
            raise WorkflowError(
                "Owned process did not stop gracefully; inspect it before retrying."
            )
        time.sleep(0.1)


def port_free(port):
    if not 1024 <= port <= 65535:
        raise WorkflowError("Choose an unprivileged port between 1024 and 65535.")
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            listener.bind(("127.0.0.1", port))
        except OSError as exc:
            raise WorkflowError(
                f"Port {port} is occupied; no existing process was stopped."
            ) from exc


def health(spec, token, *, supervisor=None):
    path = "/" if spec.get("legacy") else "/__environment__/"
    try:
        with urlopen(f"http://127.0.0.1:{spec['port']}{path}", timeout=1) as response:
            if spec.get("legacy"):
                if response.status != 200:
                    return False
                if not token:
                    return True
                if supervisor is None:
                    return False
                listener = run(
                    ["ss", "-H", "-ltnp", f"sport = :{spec['port']}"],
                    cwd=spec["checkout"],
                    capture=True,
                )
                return any(
                    f"pid={child['pid']}," in listener
                    and process_identity(child["pid"]) == child["start"]
                    and Path(f"/proc/{child['pid']}/cwd").resolve()
                    == Path(spec["checkout"]).resolve()
                    for child in children(supervisor["pid"])
                )
            value = json.load(response)
            return (
                value.get("instance") == token
                and value.get("environment") == spec["role"]
                and value.get("revision") == spec["revision"]
            )
    except URLError, TimeoutError, ValueError:
        return False


def children(pid):
    result = []
    path = Path(f"/proc/{pid}/task/{pid}/children")
    try:
        direct = [int(value) for value in path.read_text().split()]
    except FileNotFoundError, ProcessLookupError:
        return result
    for child in direct:
        result.extend(children(child))
        result.append(process_record(child))
    return result


def serve(directory, token):
    spec = read_json(directory / "environment.json")
    environment(spec, instance=token)
    stopping = False

    def request_stop(signum, frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    processes = []
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (directory / "process.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise WorkflowError("An environment supervisor is already running.") from exc
        write_json(
            directory / "process.json",
            process_record(
                os.getpid(),
                token=token,
                checkout=spec["checkout"],
            ),
        )
        try:
            replacement = spec.get("replace")
            if replacement:
                stop_owned(replacement)
                spec.pop("replace")
                write_json(directory / "environment.json", spec)
                deadline = time.monotonic() + 10
                while True:
                    try:
                        port_free(spec["port"])
                        break
                    except WorkflowError:
                        if time.monotonic() >= deadline:
                            raise
                        time.sleep(0.1)
            else:
                port_free(spec["port"])
            env = environment(spec, instance=token)
            if spec["role"] == "development":
                processes.append(
                    subprocess.Popen(
                        ["node", "frontend/build.mjs", "--watch"],
                        cwd=spec["checkout"],
                        env=env,
                    )
                )
            command = [
                spec["python"],
                "manage.py",
                "runserver",
                f"127.0.0.1:{spec['port']}",
                "--insecure",
            ]
            if spec["role"] != "development":
                command.append("--noreload")
            processes.append(subprocess.Popen(command, cwd=spec["checkout"], env=env))
            print(f"{spec['role']} {spec['revision']} http://127.0.0.1:{spec['port']}/", flush=True)
            while not stopping:
                for process in processes:
                    if process.poll() is not None:
                        raise WorkflowError(
                            f"Preview child exited with status {process.returncode}."
                        )
                time.sleep(0.2)
        finally:
            descendants = children(os.getpid())
            for child in descendants:
                if process_identity(child["pid"]) == child["start"]:
                    try:
                        os.kill(child["pid"], signal.SIGTERM)
                    except ProcessLookupError:
                        pass
            for process in processes:
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired as exc:
                    raise WorkflowError(
                        f"Child {process.pid} did not stop; inspect the environment log."
                    ) from exc


def start(spec, directory, *, replacement=None):
    check_overrides(spec)
    environment(spec)
    record_path = directory / "process.json"
    if record_path.exists():
        record = read_json(record_path)
        if process_identity(record["pid"]) == record["start"]:
            if owned(record) and health(spec, record["token"], supervisor=record):
                print(f"Already running: http://127.0.0.1:{spec['port']}/")
                return record
            raise WorkflowError("An existing supervisor is unhealthy; inspect its log/status.")
    if not replacement:
        port_free(spec["port"])
    spec = {**spec}
    if replacement:
        spec["replace"] = replacement
    write_json(directory / "environment.json", spec)
    token = uuid.uuid4().hex
    with (directory / "server.log").open("ab", buffering=0) as log:
        os.chmod(directory / "server.log", 0o600)
        process = subprocess.Popen(
            [sys.executable, str(ROOT / "workflow.py"), "_serve", str(directory), token],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            cwd=spec["checkout"],
            env=environment(spec),
            start_new_session=True,
        )
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise WorkflowError(f"Startup failed; see {directory / 'server.log'}.")
        if record_path.exists():
            record = read_json(record_path)
            if (
                record["pid"] == process.pid
                and owned(record)
                and health(spec, token, supervisor=record)
            ):
                print(
                    f"Ready: http://127.0.0.1:{spec['port']}/ ({spec['role']}, {spec['revision']})"
                )
                print(f"Log: {directory / 'server.log'}")
                return record
        time.sleep(0.2)
    record = process_record(process.pid, token=token, checkout=spec["checkout"])
    if owned(record):
        stop_owned(record)
    raise WorkflowError(f"Startup health check timed out; see {directory / 'server.log'}.")


def status(directory):
    spec = read_json(directory / "environment.json")
    record_path = directory / "process.json"
    if not record_path.exists():
        print("Stopped.")
        return
    record = read_json(record_path)
    if process_identity(record["pid"]) != record["start"]:
        print(f"Stopped. Log: {directory / 'server.log'}")
        return
    if not owned(record) or not health(spec, record["token"], supervisor=record):
        raise WorkflowError(f"Environment is unhealthy or ownership changed: {directory}")
    print(f"Running {spec['role']} {spec['revision']} at http://127.0.0.1:{spec['port']}/")
    print(f"PID: {record['pid']}; isolated storage: {spec['data']}")


def test(checkout, selectors, *, revision=None):
    directory = instance_directory(checkout) / "tests" / uuid.uuid4().hex
    spec = new_spec(
        checkout,
        directory,
        "test",
        revision or f"{commit(checkout)[:12]} working tree",
        8766,
    )
    spec["python"] = str(checkout / ".venv" / "bin" / "python")
    if not Path(spec["python"]).exists():
        raise WorkflowError("Initialize development dependencies before running tests.")
    check_overrides(spec)
    environment(spec)
    print(f"Isolated test storage: {directory}", flush=True)
    passed = False
    try:
        django(spec, "test", *(selectors or ["library.tests"]), "--noinput")
        passed = True
    finally:
        if passed and directory.exists():
            validate_environment("test", checkout, directory, directory / "unused.sqlite3")
            shutil.rmtree(directory)
        elif not passed:
            print(f"Failed-run runtime retained at {directory}; inspect before exact-path cleanup.")


def register_live(checkout, pid):
    if live_registration():
        raise WorkflowError(
            "Live is already registered; inspect its registration before changing it."
        )
    record = process_record(pid)
    record["checkout"] = str(Path(f"/proc/{pid}/cwd").resolve())
    if not record["start"] or not owned(record):
        raise WorkflowError("Live registration requires an owned, no-autoreload Django runserver.")
    args = [
        value.decode() for value in Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0") if value
    ]
    script = Path(args[1]) if len(args) > 1 else Path("")
    if not script.is_absolute():
        script = Path(record["checkout"]) / script
    if script.resolve() != Path(record["checkout"]) / "manage.py":
        raise WorkflowError("The listener is not running this checkout's manage.py.")
    binding = next((value for value in args if value.startswith("127.0.0.1:")), "")
    if not binding or "--insecure" not in args:
        raise WorkflowError("Expected a localhost-only runserver with --noreload --insecure.")
    listener = run(
        ["ss", "-H", "-ltnp", f"sport = :{binding.split(':')[1]}"],
        cwd=checkout,
        capture=True,
    )
    if f"pid={pid}," not in listener:
        raise WorkflowError("The registered PID does not own that listener.")
    variables = dict(
        item.decode().split("=", 1)
        for item in Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
        if b"=" in item
    )
    if variables.get("DJANGO_SETTINGS_MODULE", "config.settings") != "config.settings":
        raise WorkflowError("Only the documented config.settings service can be registered.")
    serving = Path(record["checkout"])
    data = Path(variables.get("READING_HUB_DATA", serving / "data")).resolve()
    database = Path(variables.get("READING_HUB_DATABASE_PATH", data / "library.sqlite3")).resolve()
    python = Path(args[0])
    if not python.is_absolute():
        python = serving / python
    spec = {
        "role": "live",
        "checkout": str(serving),
        "data": str(data),
        "database": str(database),
        "python": str(python),
        "profile": variables.get("READING_HUB_PROFILE", "profiles.marxist.site"),
        "revision": variables.get("READING_HUB_REVISION", serving.name),
        "port": int(binding.split(":")[1]),
        "allow_workers": True,
        "legacy": True,
        "process": record,
        "editor_pilot": variables.get("READING_HUB_EDITOR_PILOT", "1"),
    }
    if not database.is_file() or not (data / "secret-key").is_file():
        raise WorkflowError("Existing live database and signing key must already exist.")
    if not health(spec, ""):
        raise WorkflowError("Live service is not responding; registration was not saved.")
    write_json(state_directory() / "live.json", spec)
    print(
        f"Registered existing live listener on port {spec['port']}; no service or data was changed."
    )


def live_preflight(spec):
    if not Path(spec["database"]).is_file() or not (Path(spec["data"]) / "secret-key").is_file():
        raise WorkflowError("Live database/key missing; refusing to create replacements.")
    django(spec, "check")
    django(spec, "migrate", "--check")
    with sqlite3.connect(Path(spec["database"]).as_uri() + "?mode=ro", uri=True) as database:
        active = database.execute(
            "SELECT id FROM library_workerinstance WHERE desired_running = 1 "
            "OR status IN ('starting', 'running', 'stopping')"
        ).fetchall()
    if active:
        raise WorkflowError(
            "Active import workers must first be stopped gracefully through Manage workers. "
            "Record which were active; restore only those after promotion. No worker was changed."
        )
    with (Path(spec["data"]) / "worker.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise WorkflowError("An import worker is still running; leave live unchanged.") from exc


def promote(checkout, revision, *, rollback=False):
    current = live_registration()
    if not current:
        raise WorkflowError("Register the exact existing live listener before promotion.")
    if rollback:
        if not current.get("previous"):
            raise WorkflowError("No previous live target has been recorded.")
        target = {**current["previous"]}
        if "source_hashes" in target:
            verify_candidate(target)
    else:
        target = read_json(candidate_directory(checkout, revision) / "environment.json")
        verify_candidate(target)
        target = {
            **target,
            "role": "live",
            "data": current["data"],
            "database": current["database"],
            "profile": current["profile"],
            "port": current["port"],
            "allow_workers": True,
            "editor_pilot": current.get("editor_pilot", "1"),
        }
        if (
            read_json(candidate_directory(checkout, revision) / "environment.json")["profile"]
            != (current["profile"])
        ):
            raise WorkflowError("Candidate profile differs from live; rehearse the live profile.")
    check_overrides(target)
    live_preflight(target)
    if not owned(current["process"]):
        raise WorkflowError("The current live process identity changed; no process was stopped.")
    directory = state_directory() / "live"
    previous = {key: value for key, value in current.items() if key != "previous"}
    target.pop("replace", None)
    target.pop("process", None)
    if directory.joinpath("process.json").exists():
        existing = read_json(directory / "process.json")
        if existing["pid"] == current["process"]["pid"]:
            # start() must not mistake the old supervisor for the replacement.
            directory = state_directory() / "live-runs" / uuid.uuid4().hex
    try:
        record = start(target, directory, replacement=current["process"])
    except WorkflowError as failure:
        if owned(current["process"]):
            raise
        recovery = {key: value for key, value in previous.items() if key != "process"}
        recovery_directory = state_directory() / "live-runs" / uuid.uuid4().hex
        try:
            restored = start(recovery, recovery_directory)
        except WorkflowError as recovery_failure:
            raise WorkflowError(
                f"Promotion failed: {failure}; recovery also failed: {recovery_failure}. "
                "Data was not migrated. Operator recovery is required."
            ) from recovery_failure
        write_json(state_directory() / "live.json", {**previous, "process": restored})
        raise WorkflowError(f"Promotion failed; previous source restored: {failure}") from failure
    write_json(
        state_directory() / "live.json",
        {
            **target,
            "process": record,
            "previous": previous,
        },
    )
    print("Live source promoted. No migration, crawl, publication or worker action was performed.")


def main():
    if len(sys.argv) == 4 and sys.argv[1] == "_serve":
        serve(Path(sys.argv[2]), sys.argv[3])
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, default=ROOT)
    commands = parser.add_subparsers(dest="group", required=True)
    for group in ("dev", "stage"):
        command = commands.add_parser(group)
        actions = command.add_subparsers(dest="action", required=True)
        initial = actions.add_parser("init" if group == "dev" else "prepare")
        initial.add_argument("--port", type=int, default=8766 if group == "dev" else 8767)
        if group == "stage":
            initial.add_argument("revision")
        for action in ("start", "status", "stop"):
            operation = actions.add_parser(action)
            if group == "stage":
                operation.add_argument("revision")
            if action == "start":
                operation.add_argument("--port", type=int)
                operation.add_argument("--allow-workers", action="store_true")
        management = actions.add_parser("manage")
        if group == "stage":
            management.add_argument("revision")
        management.add_argument("arguments", nargs=argparse.REMAINDER)
        if group == "stage":
            validation = actions.add_parser("test")
            validation.add_argument("revision")
            validation.add_argument("selectors", nargs="*")
    tests = commands.add_parser("test")
    tests.add_argument("selectors", nargs="*")
    live = commands.add_parser("live")
    actions = live.add_subparsers(dest="action", required=True)
    registration = actions.add_parser("register")
    registration.add_argument("--pid", type=int, required=True)
    actions.add_parser("status")
    for action in ("promote", "rollback"):
        operation = actions.add_parser(action)
        if action == "promote":
            operation.add_argument("revision")
        operation.add_argument("--confirm-live", action="store_true", required=True)
    args = parser.parse_args()
    checkout = args.checkout.expanduser().resolve()
    ensure_state(checkout)
    if args.group == "test":
        test(checkout, args.selectors)
    elif args.group == "live":
        if args.action == "status":
            spec = live_registration()
            if not spec or not owned(spec["process"]):
                raise WorkflowError("No owned live listener is registered.")
            print(f"Registered live {spec['revision']} at http://127.0.0.1:{spec['port']}/")
        else:
            with live_operation():
                if args.action == "register":
                    register_live(checkout, args.pid)
                else:
                    promote(
                        checkout,
                        getattr(args, "revision", None),
                        rollback=args.action == "rollback",
                    )
    elif args.action in {"init", "prepare"}:
        if not 1024 <= args.port <= 65535:
            raise WorkflowError("Choose an unprivileged port between 1024 and 65535.")
        if args.group == "dev":
            dev_init(checkout, args.port)
        else:
            stage_prepare(checkout, args.revision, args.port)
    else:
        directory = (
            instance_directory(checkout) / "development"
            if args.group == "dev"
            else candidate_directory(checkout, args.revision)
        )
        spec = read_json(directory / "environment.json")
        if args.action in {"manage", "test"}:
            check_overrides(spec)
            if args.group == "stage":
                verify_candidate(spec)
            if args.action == "test":
                test(Path(spec["checkout"]), args.selectors, revision=spec["revision"])
            else:
                if not args.arguments:
                    raise WorkflowError("Supply a Django management command.")
                django(spec, *args.arguments)
        elif args.action == "start":
            if args.group == "stage":
                verify_candidate(spec)
            else:
                spec["revision"] = f"{commit(checkout)[:12]} working tree"
            if args.port is not None:
                spec["port"] = args.port
            spec["allow_workers"] = args.allow_workers
            start(spec, directory)
        elif args.action == "status":
            status(directory)
        else:
            stop_owned(read_json(directory / "process.json"))
            print("Stopped owned environment processes; data retained.")


if __name__ == "__main__":
    try:
        main()
    except (WorkflowError, ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Workflow error: {exc}", file=sys.stderr)
        sys.exit(1)
