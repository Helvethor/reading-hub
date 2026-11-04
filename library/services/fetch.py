import fcntl
import hashlib
import http.client
import ipaddress
import signal
import socket
import ssl
import time
from contextlib import contextmanager
from dataclasses import dataclass
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

from django.conf import settings

from library.profile import get_profile
from library.services.errors import ImportFailure, LimitExceeded

USER_AGENT = "ReadingHub/0.1 (+local personal reader)"
MAX_PAGES = get_profile().max_pages
MAX_BYTES = get_profile().max_bytes
TIMEOUT = get_profile().request_timeout
REQUEST_TIMES = {}


@contextmanager
def request_deadline():
    def timed_out(signum, frame):
        raise TimeoutError(f"Request exceeded {TIMEOUT} seconds")

    previous = signal.signal(signal.SIGALRM, timed_out)
    timer = signal.setitimer(signal.ITIMER_REAL, TIMEOUT)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
        signal.setitimer(signal.ITIMER_REAL, *timer)


def validate_url(url, *, asset=False, robots=False, redirect_urls=()):
    if len(url) > 2048 or any(ord(c) < 33 for c in url) or "\\" in url:
        raise ImportFailure("Invalid URL.", "unsupported")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as exc:
        raise ImportFailure("Invalid URL.", "unsupported") from exc
    host = (parts.hostname or "").lower()
    profile = get_profile()
    hosts = {source.host for source in profile.sources} | set(profile.aliases)
    if parts.scheme not in {"http", "https"} or parts.username or parts.password:
        raise ImportFailure(
            "Only public HTTP(S) source URLs without credentials are supported.", "unsupported"
        )
    if port not in {None, 80 if parts.scheme == "http" else 443}:
        raise ImportFailure("Custom ports are not supported.", "unsupported")
    approved_redirect = url in redirect_urls
    if host not in hosts and not approved_redirect:
        asset_path = any(
            unquote(parts.path).startswith(prefix) for prefix in profile.asset_paths.get(host, ())
        )
        if not (
            asset
            and host in profile.asset_paths
            and (asset_path or (robots and parts.path == "/robots.txt"))
        ):
            raise ImportFailure(f"Unsupported source or asset host: {host}.", "unsupported")
    if not asset and not robots:
        path = unquote(parts.path).lower()
        if path.endswith((".pdf", ".epub", ".odt", ".zip")):
            raise ImportFailure(
                "PDFs and downloadable books are deferred. Submit an HTML URL.", "unsupported"
            )
    path = quote(unquote(parts.path or "/"), safe="/:@!$&'()*+,;=-._~")
    return urlunsplit((parts.scheme, host, path, parts.query, ""))


def canonical_url(url):
    parts = urlsplit(validate_url(url))
    return urlunsplit(
        (
            "https",
            get_profile().aliases.get(parts.hostname, parts.hostname),
            parts.path,
            parts.query,
            "",
        )
    )


def public_addresses(host, port):
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if not addresses:
        raise ImportFailure("Source DNS returned no addresses.", "network")
    for _, _, _, _, addr in addresses:
        if not ipaddress.ip_address(addr[0]).is_global:
            raise ImportFailure("Source resolves to a non-public network address.", "unsafe_url")
    return addresses


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, port, address, timeout, secure=True):
        super().__init__(host, port=port, timeout=timeout, context=ssl.create_default_context())
        self.address = address
        self.secure = secure

    def connect(self):
        family, socktype, proto, _, sockaddr = self.address
        sock = socket.socket(family, socktype, proto)
        try:
            sock.settimeout(self.timeout)
            sock.connect(sockaddr)
            self.sock = (
                self._context.wrap_socket(sock, server_hostname=self.host) if self.secure else sock
            )
        except BaseException:
            sock.close()
            raise


@dataclass
class Response:
    url: str
    body: bytes
    media_type: str
    headers: dict
    status: int = 200


class Fetcher:
    def __init__(
        self,
        progress=lambda stage: None,
        *,
        byte_limit=None,
        request_interval=None,
        source_host=None,
    ):
        self.downloaded = 0
        self.pages = set()
        self.last_request = REQUEST_TIMES
        self.robot_rules = {}
        self.progress = progress
        self.byte_limit = byte_limit
        self.request_interval = request_interval
        self.source_host = source_host

    def _wait(self, host, interval=1):
        if interval > TIMEOUT:
            raise ImportFailure(
                f"Source crawl delay is {interval}s; retry with a slower dedicated import.",
                "rate_limited",
            )
        directory = settings.DATA_DIR / "request-times"
        directory.mkdir(mode=0o700, exist_ok=True)
        key = get_profile().aliases.get(host, host)
        path = directory / hashlib.sha256(key.encode()).hexdigest()
        with path.open("a+") as clock:
            fcntl.flock(clock, fcntl.LOCK_EX)
            clock.seek(0)
            stored = clock.read().split()
            now = time.monotonic()
            previous, previous_interval = map(float, stored) if stored else (0, 0)
            if previous > now:
                previous = previous_interval = 0
            spacing = max(get_profile().request_interval, self.request_interval or 1, interval)
            delay = (
                max(previous, self.last_request.get(host, 0))
                + max(spacing, previous_interval)
                - now
            )
            if delay > 0:
                if self.source_host:
                    deadline = now + delay
                    while delay > 0:
                        self.progress("Waiting for the source request interval")
                        time.sleep(min(delay, 0.5))
                        delay = deadline - time.monotonic()
                else:
                    time.sleep(delay)
            self.last_request[host] = time.monotonic()
            clock.seek(0)
            clock.truncate()
            clock.write(f"{self.last_request[host]} {spacing}")
            clock.flush()

    def _request(self, url, *, asset=False, robots=False, redirect_urls=()):
        for _redirect in range(6):
            url = validate_url(url, asset=asset, robots=robots, redirect_urls=redirect_urls)
            parts = urlsplit(url)
            if (
                self.source_host
                and get_profile().aliases.get(parts.hostname, parts.hostname) != self.source_host
                and url not in redirect_urls
            ):
                raise ImportFailure("Catalogue redirect left its source site.", "unsupported")
            if not robots:
                if url in redirect_urls:
                    self._check_robots(url, asset=asset, redirect_urls=redirect_urls)
                else:
                    self._check_robots(url, asset=asset)
            host, port = parts.hostname, parts.port or (443 if parts.scheme == "https" else 80)
            rules = self.robot_rules.get(f"{parts.scheme}://{parts.netloc}")
            interval = rules.crawl_delay("ReadingHub") if rules else None
            self._wait(host, interval or 1)
            self.progress(f"Fetching {parts.path[:180]}")
            with request_deadline():
                result = self._exchange(url, host, port, parts)
            headers, status = result.headers, result.status
            if status in {301, 302, 303, 307, 308}:
                if "location" not in headers:
                    raise ImportFailure("Source redirect has no destination.", "network")
                destination = urljoin(url, headers["location"])
                approved = get_profile().catalogue_redirects.get(url)
                if self.source_host and approved == destination:
                    redirect_urls = (destination, destination.rstrip("/") + "/")
                url = destination
                continue
            if status >= 400:
                if robots and status == 404:
                    return Response(url, b"", "text/plain", headers)
                code = "rate_limited" if status == 429 else "http"
                raise ImportFailure(
                    f"Source returned HTTP {status} for {url}. "
                    f"Retry-After: {headers.get('retry-after', 'not specified')}",
                    code,
                )
            if status != 200:
                raise ImportFailure(f"Unexpected source status: {status}.", "http")
            return result
        raise ImportFailure("Too many source redirects.", "redirect")

    def _exchange(self, url, host, port, parts):
        addresses = public_addresses(host, port)
        for index, address in enumerate(addresses):
            conn = PinnedHTTPSConnection(
                host, port, address, TIMEOUT, secure=parts.scheme == "https"
            )
            try:
                try:
                    conn.connect()
                except TimeoutError:
                    raise
                except OSError:
                    if index + 1 == len(addresses):
                        raise
                    continue
                conn.request(
                    "GET",
                    urlunsplit(("", "", parts.path, parts.query, "")),
                    headers={
                        "User-Agent": USER_AGENT,
                        "Accept-Encoding": "identity",
                        "Connection": "close",
                    },
                )
                response = conn.getresponse()
                headers = {k.lower(): v for k, v in response.getheaders()}
                status = response.status
                if status != 200:
                    return Response(url, b"", "", headers, status)
                if headers.get("content-encoding", "identity").lower() != "identity":
                    raise ImportFailure("Source ignored uncompressed-transfer request.", "encoding")
                chunks = []
                while True:
                    chunk = response.read1(65536)
                    if not chunk:
                        break
                    self.downloaded += len(chunk)
                    limit = MAX_BYTES if self.byte_limit is None else self.byte_limit
                    if self.downloaded > limit:
                        raise LimitExceeded(f"Download exceeds the {limit}-byte limit.")
                    chunks.append(chunk)
                return Response(
                    url,
                    b"".join(chunks),
                    headers.get("content-type", "").split(";")[0].strip().lower(),
                    headers,
                )
            finally:
                conn.close()
        raise AssertionError("DNS returned no connection candidates")

    def _check_robots(self, url, *, asset, redirect_urls=()):
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self.robot_rules:
            response = self._request(
                origin + "/robots.txt",
                asset=asset,
                robots=True,
                redirect_urls=(origin + "/robots.txt",) if url in redirect_urls else (),
            )
            rules = RobotFileParser()
            rules.parse(response.body.decode("utf-8", errors="replace").splitlines())
            self.robot_rules[origin] = rules
        if not self.robot_rules[origin].can_fetch("ReadingHub", url):
            raise ImportFailure(f"Source robots.txt disallows this request: {url}", "robots")

    def fetch(self, url, *, asset=False, media_types=None):
        url = validate_url(url, asset=asset)
        if not asset:
            self.pages.add(url)
            if len(self.pages) > MAX_PAGES:
                raise LimitExceeded(f"Import exceeds the {MAX_PAGES} unique HTML page limit.")
        for attempt in range(2):
            try:
                result = self._request(url, asset=asset)
                if not asset and result.media_type not in (
                    media_types or {"text/html", "application/xhtml+xml"}
                ):
                    raise ImportFailure(
                        f"Expected HTML; received {result.media_type}.", "unsupported"
                    )
                return result
            except (OSError, http.client.HTTPException) as exc:
                if attempt:
                    raise ImportFailure(f"Unable to fetch {url}: {exc}", "network") from exc
                self.progress(f"Transient network error; retrying {url[:160]}")
                time.sleep(1)
        raise AssertionError("Unreachable")
