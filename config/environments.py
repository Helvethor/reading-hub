"""Shared, side-effect-free environment validation for Django and the launcher."""

import json
import os
import subprocess
from pathlib import Path

ROLES = {"development", "test", "staging", "production", "live"}
RUNTIME_PATHS = (
    "secret-key",
    "blobs",
    "pdf",
    "static",
    "workers",
    "request-times",
    "worker.lock",
    "background.lock",
    "archive-corpus.sqlite3",
    "development-credentials.json",
    "development-fixtures.json",
)


def state_directory():
    return (
        Path(
            os.environ.get(
                "READING_HUB_STATE",
                Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
                / "reading-hub",
            )
        )
        .expanduser()
        .resolve()
    )


def live_registration():
    path = state_directory() / "live.json"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as file:
        value = json.load(file)
    if not isinstance(value, dict) or not all(
        isinstance(value.get(key), str) and value[key]
        for key in ("checkout", "data", "database", "python", "profile")
    ):
        raise ValueError(f"Invalid live registration: {path}")
    return value


def protected_paths(checkout):
    checkout = Path(checkout).resolve()
    paths = {checkout / "data"}
    if (checkout / ".git").exists():
        common = subprocess.run(
            ["git", "-C", str(checkout), "rev-parse", "--git-common-dir"],
            capture_output=True,
            text=True,
            check=False,
        )
        if common.returncode == 0:
            directory = (checkout / common.stdout.strip()).resolve()
            if directory.name == ".git":
                paths.add(directory.parent / "data")
    registered = live_registration()
    if registered:
        paths.update((Path(registered["data"]).resolve(), Path(registered["database"]).resolve()))
    return paths


def validate_environment(role, checkout, data, database):
    if role not in ROLES:
        raise ValueError(f"Unknown Reading Hub environment: {role}")
    data, database = Path(data).expanduser().resolve(), Path(database).expanduser().resolve()
    if role == "live":
        return data, database
    if database == data or not database.is_relative_to(data):
        raise ValueError("Non-live databases must be files inside their isolated data directory.")
    protected = protected_paths(checkout)
    for candidate in (data, database, *(data / name for name in RUNTIME_PATHS)):
        resolved = candidate.resolve()
        if any(
            resolved == path or resolved.is_relative_to(path) or path.is_relative_to(resolved)
            for path in protected
        ):
            raise ValueError(f"{role} cannot use protected live storage: {candidate}")
        if not resolved.is_relative_to(data):
            raise ValueError(f"Runtime paths must remain inside isolated storage: {candidate}")
    if data.is_relative_to(Path(checkout).resolve()):
        raise ValueError("Non-live runtime data must be outside the source checkout.")
    for path in protected:
        live_database = path if path.is_file() else path / "library.sqlite3"
        if database.exists() and live_database.exists() and database.samefile(live_database):
            raise ValueError("An isolated database cannot be a hardlink to live storage.")
    return data, database
