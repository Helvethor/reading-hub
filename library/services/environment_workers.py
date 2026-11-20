import json
import os
import time
import uuid

from django.conf import settings

from library.services.workers import process_identity, worker_directory


def supervisor_status_path():
    return worker_directory() / "supervisor.json"


def write_supervisor_status(*, expected, live):
    path = supervisor_status_path()
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}")
    record = {
        "pid": os.getpid(),
        "process_start": process_identity(os.getpid()),
        "role": settings.READING_HUB_ENVIRONMENT,
        "instance": settings.READING_HUB_INSTANCE,
        "heartbeat": time.time(),
        "expected_workers": expected,
        "live_workers": live,
    }
    with temporary.open("x", encoding="utf-8") as file:
        os.chmod(temporary, 0o600)
        json.dump(record, file)
        file.write("\n")
    temporary.replace(path)
    return record


def read_supervisor_status():
    try:
        record = json.loads(supervisor_status_path().read_text(encoding="utf-8"))
        if (
            process_identity(record["pid"]) != record["process_start"]
            or time.time() - record["heartbeat"] >= 90
        ):
            return None
        return record
    except OSError, ValueError, KeyError, TypeError:
        return None


def clear_supervisor_status(record):
    path = supervisor_status_path()
    try:
        current = json.loads(path.read_text(encoding="utf-8"))
        if (
            current.get("pid") == record["pid"]
            and current.get("process_start") == record["process_start"]
        ):
            path.unlink()
    except OSError, ValueError:
        return
