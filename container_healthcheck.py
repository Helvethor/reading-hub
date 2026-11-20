import os
import subprocess
import sys
from urllib.error import URLError
from urllib.request import Request, urlopen

request = Request(
    "http://127.0.0.1:8000/healthz/",
    headers={"Host": "read.shabang.ch", "X-Forwarded-Proto": "https"},
)
try:
    with urlopen(request, timeout=4) as response:
        ready = response.status == 200 and response.read() == b"ok"
except URLError:
    ready = False

if os.environ.get("READING_HUB_ALLOW_WORKERS") != "0":
    workers = subprocess.run(
        [sys.executable, "manage.py", "check_environment_workers"],
        capture_output=True,
        check=False,
    )
    ready = ready and workers.returncode == 0

raise SystemExit(0 if ready else 1)
