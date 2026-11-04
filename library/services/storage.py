import hashlib
import os
import tempfile
from pathlib import Path

from django.conf import settings
from django.utils import timezone


def save_response(response, requested):
    return {
        "url": requested,
        "resolved_url": response.url,
        "digest": store_blob(response.body),
        "headers": {
            key: value
            for key, value in response.headers.items()
            if key in {"content-type", "etag", "last-modified"}
        },
        "retrieved_at": timezone.now().isoformat(),
    }


def blob_path(digest):
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("Invalid content digest")
    return Path(settings.DATA_DIR) / "blobs" / digest[:2] / digest


def store_blob(data):
    digest = hashlib.sha256(data).hexdigest()
    path = blob_path(digest)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise OSError(f"Cached blob checksum mismatch: {digest}")
        return digest
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".staging-", delete=False) as file:
            name = file.name
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)
    return digest


def read_blob(digest):
    data = blob_path(digest).read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise OSError(f"Cached blob checksum mismatch: {digest}")
    return data
