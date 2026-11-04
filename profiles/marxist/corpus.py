import json
import sqlite3
from dataclasses import asdict
from urllib.parse import urljoin, urlsplit

from django.conf import settings
from django.utils import timezone

from library.models import CatalogueWorker, CrawlCapture, Job
from library.profile import get_profile
from library.services.catalogue import configured_sites, save_entry
from library.services.errors import ImportFailure, LimitExceeded
from library.services.fetch import Fetcher, canonical_url
from library.services.storage import read_blob, save_response
from library.sources.adapters import discover, extract
from library.sources.base import parse_html
from library.sources.normalize import normalize
from profiles.marxist import archive
from profiles.marxist.catalogue import MarxistCatalogue

HOST = "www.marxists.org"
SEEDS = (
    "https://www.marxists.org/xlang/index.htm",
    "https://www.marxists.org/archive/",
    "https://www.marxists.org/francais/",
    "https://www.marxists.org/francais/lafargue/works/1891/00/pl18910000.htm",
    "https://www.marxists.org/archive/marx/works/1848/communist-manifesto/index.htm",
    "https://www.marxists.org/archive/lenin/works/1917/staterev/index.htm",
    "https://www.marxists.org/deutsch/archiv/marx-engels/1848/manifest/index.htm",
    "https://www.marxists.org/espanol/m-e/1840s/48-manif.htm",
    "https://www.marxists.org/portugues/marx/1848/ManifestoDoPartidoComunista/index.htm",
)


class ArchiveCorpus:
    def __init__(self):
        self.db = sqlite3.connect(settings.DATA_DIR / "archive-corpus.sqlite3", timeout=20)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS config (id INTEGER PRIMARY KEY, enabled INTEGER,
                target INTEGER, max_requests INTEGER, max_bytes INTEGER, error TEXT);
            INSERT OR IGNORE INTO config VALUES (1, 0, 1000, 30000, 2147483648, '');
            CREATE TABLE IF NOT EXISTS queue (url TEXT PRIMARY KEY, language TEXT,
                status TEXT DEFAULT 'pending', error TEXT DEFAULT '', depth INTEGER DEFAULT 0);
            CREATE INDEX IF NOT EXISTS queue_status_language ON queue(status,language,depth);
            CREATE TABLE IF NOT EXISTS pages (url TEXT PRIMARY KEY, response TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS works (url TEXT PRIMARY KEY, title TEXT, language TEXT,
                status TEXT, manifest TEXT, metrics TEXT, error TEXT, checked_at TEXT);
            CREATE TABLE IF NOT EXISTS members (url TEXT PRIMARY KEY, work_url TEXT);
            CREATE TABLE IF NOT EXISTS counters (
                id INTEGER PRIMARY KEY, requests INTEGER, bytes INTEGER);
            INSERT OR IGNORE INTO counters VALUES (1, 0, 0);
        """)
        self.db.commit()
        self.fetcher = Fetcher(source_host=HOST, request_interval=2, progress=self.heartbeat)
        self.site = None
        self.progress = lambda stage: None

    def close(self):
        self.db.close()

    def heartbeat(self, stage):
        if not self.db.execute("SELECT enabled FROM config").fetchone()[0]:
            raise ImportFailure("Archive sampling paused by the user.", "paused")
        if Job.objects.filter(status=Job.Status.QUEUED).exists():
            raise ImportFailure("Yielding archive sampling to a requested import.", "yield")
        CatalogueWorker.objects.update_or_create(
            profile=get_profile().key, defaults={"heartbeat": timezone.now()}
        )
        self.progress(stage)

    def add(self, url, depth=0):
        try:
            url = canonical_url(url)
        except ImportFailure as exc:
            if exc.code == "unsupported":
                return
            raise
        parts = urlsplit(url)
        if parts.hostname != HOST or parts.query:
            return
        path = parts.path.lower()
        if any(
            segment in path.split("/")
            for segment in (
                "admin",
                "glossary",
                "ebooks",
                "audiobooks",
                "images",
                "img",
                "audio",
                "video",
                "reference",
                "encyclopedia",
            )
        ):
            return
        filename = path.rsplit("/", 1)[-1]
        if "." in filename and not filename.endswith((".htm", ".html")):
            return
        if self.db.execute("SELECT COUNT(*) FROM queue").fetchone()[0] >= 100000:
            raise LimitExceeded("Archive sampling reached its 100,000 discovered URL limit.")
        self.db.execute(
            "INSERT OR IGNORE INTO queue(url, language, depth) VALUES (?, ?, ?)",
            (url, archive.language(url), depth),
        )

    def start(self, target, retry_failed=False, recheck=False):
        for url in SEEDS:
            self.add(url)
        if retry_failed:
            self.db.execute(
                "UPDATE queue SET status='pending', error='' WHERE url IN "
                "(SELECT url FROM works WHERE status='failed') OR status='failed'"
            )
        if recheck:
            self.db.execute(
                "UPDATE queue SET status='pending', error='' WHERE url IN (SELECT url FROM works)"
            )
            self.db.execute("UPDATE works SET status='pending'")
        self.db.execute("UPDATE config SET enabled=1,target=?,error='' WHERE id=1", (target,))
        self.db.commit()

    def pause(self, error=""):
        self.db.execute("UPDATE config SET enabled=0,error=? WHERE id=1", (error,))
        self.db.commit()

    def report(self):
        config = dict(self.db.execute("SELECT * FROM config").fetchone())
        config.update(dict(self.db.execute("SELECT requests,bytes FROM counters").fetchone()))
        config["queue"] = {
            row["status"]: row["n"]
            for row in self.db.execute("SELECT status,COUNT(*) n FROM queue GROUP BY status")
        }
        config["works"] = {
            row["status"]: row["n"]
            for row in self.db.execute("SELECT status,COUNT(*) n FROM works GROUP BY status")
        }
        config["languages"] = [
            dict(row)
            for row in self.db.execute(
                "SELECT language,status,COUNT(*) count FROM works GROUP BY language,status "
                "ORDER BY language,status"
            )
        ]
        config["recent_failures"] = [
            dict(row)
            for row in self.db.execute(
                "SELECT url,error FROM works WHERE status='failed' "
                "ORDER BY checked_at DESC LIMIT 10"
            )
        ]
        config["page_failures"] = [
            dict(row)
            for row in self.db.execute(
                "SELECT url,error FROM queue WHERE status='failed' ORDER BY rowid DESC LIMIT 10"
            )
        ]
        return config

    def page(self, url):
        self.heartbeat(f"Reading {urlsplit(url).path[:180]}")
        cached = self.db.execute("SELECT response FROM pages WHERE url=?", (url,)).fetchone()
        if cached:
            response = json.loads(cached[0])
        else:
            capture = (
                CrawlCapture.objects.filter(site=self.site, url=url)
                .order_by("-captured_at", "-pk")
                .first()
            )
            if capture:
                response = capture.response
            else:
                config = self.db.execute("SELECT * FROM config").fetchone()
                counters = self.db.execute("SELECT * FROM counters").fetchone()
                if counters["requests"] >= config["max_requests"]:
                    raise LimitExceeded("Archive sampling request safety limit reached.")
                remaining = config["max_bytes"] - counters["bytes"]
                if remaining <= 0:
                    raise LimitExceeded("Archive sampling byte safety limit reached.")
                self.fetcher.pages.clear()
                self.fetcher.downloaded = 0
                self.fetcher.byte_limit = min(remaining, get_profile().max_bytes)
                self.db.execute("UPDATE counters SET requests=requests+1")
                self.db.commit()
                try:
                    fetched = self.fetcher.fetch(url)
                finally:
                    self.db.execute("UPDATE counters SET bytes=bytes+?", (self.fetcher.downloaded,))
                    self.db.commit()
                response = save_response(fetched, url)
                CrawlCapture.objects.create(site=self.site, url=url, response=response)
            self.db.execute(
                "INSERT OR REPLACE INTO pages VALUES (?,?)", (url, json.dumps(response))
            )
            self.db.commit()
        body = read_blob(response["digest"])
        return response, parse_html(body, response["headers"])

    def expand(self, soup, url, depth):
        if depth >= 12:
            return
        for anchor in soup.select("a[href], area[href]"):
            self.add(urljoin(url, anchor["href"]), depth + 1)

    def parent_work(self, soup, url):
        directory = url.rsplit("/", 1)[0] + "/"
        for anchor in soup.select("a[href]"):
            candidate = urljoin(url, anchor["href"])
            if candidate.split("#")[0] not in {directory + "index.htm", directory + "index.html"}:
                continue
            candidate = canonical_url(candidate)
            if candidate == url:
                continue
            _, parent_soup = self.page(candidate)
            try:
                parent = discover(parent_soup, candidate)
            except ImportFailure as exc:
                if exc.code == "layout":
                    continue
                raise
            if parent.book and any(part.url == url for part in parent.parts):
                self.add(candidate)
                self.db.execute("INSERT OR REPLACE INTO members VALUES (?,?)", (url, candidate))
                self.db.execute("UPDATE works SET status='chapter' WHERE url=?", (url,))
                return candidate
        return None

    def audit(self, url, source, initial):
        manifest = {"pages": [initial], "parts": [asdict(part) for part in source.parts]}
        try:
            urls = list(dict.fromkeys([url] + [part.url for part in source.parts]))
            if len(urls) > get_profile().max_pages:
                raise LimitExceeded("Work exceeds the configured complete-work HTML page limit.")
            pages = []
            byte_count = len(read_blob(initial["digest"]))
            for part in source.parts:
                response, soup = self.page(part.url)
                if part.url != url:
                    manifest["pages"].append(response)
                    byte_count += len(read_blob(response["digest"]))
                if byte_count > get_profile().max_bytes:
                    raise LimitExceeded("Complete work exceeds the configured source byte limit.")
                body = extract(
                    soup,
                    part.url,
                    index=source.book and part.url == url,
                    book=source.book and not part.use_source_headings,
                    group=part.group,
                    chapter_title=part.title,
                    section=part.section,
                )
                pages.append((part, body))
                if source.book and part.url != url:
                    self.db.execute("INSERT OR REPLACE INTO members VALUES (?,?)", (part.url, url))
                    self.db.execute("UPDATE works SET status='chapter' WHERE url=?", (part.url,))
            characters = sum(len(body.get_text()) for _, body in pages)
            _, structure = normalize(pages, source, {})
            metrics = {
                "html_pages": len(urls),
                "chapters": sum(part.url != url for part in source.parts) if source.book else 1,
                "characters": characters,
                "source_bytes": byte_count,
                "toc_entries": len(structure["toc"]),
                "book": source.book,
                "adapter_version": get_profile().adapter_version,
            }
            status, error = "passed", ""
        except ImportFailure as exc:
            if exc.code in {"paused", "yield"}:
                raise
            metrics, status, error = {}, "failed", f"{exc.code}: {exc}"
            if exc.code in {"network", "rate_limited", "unsafe_url", "limit"}:
                self.pause(error)
        self.db.execute(
            "INSERT OR REPLACE INTO works VALUES (?,?,?,?,?,?,?,?)",
            (
                url,
                source.title,
                source.metadata["language"],
                status,
                json.dumps(manifest),
                json.dumps(metrics),
                error,
                timezone.now().isoformat(),
            ),
        )
        return status

    def step(self):
        config = self.db.execute("SELECT * FROM config").fetchone()
        if not config["enabled"]:
            return False
        count = self.db.execute("SELECT COUNT(*) FROM works WHERE status='passed'").fetchone()[0]
        if count >= config["target"]:
            self.pause()
            return False
        row = self.db.execute("""
            SELECT q.* FROM queue q
            LEFT JOIN (
                SELECT language,COUNT(*) visited FROM queue
                WHERE status!='pending' GROUP BY language
            ) stats ON stats.language=q.language
            LEFT JOIN works w ON w.url=q.url
            WHERE q.status='pending'
            ORDER BY
                CASE WHEN w.status='pending' THEN 0 ELSE 1 END,
                COALESCE(stats.visited,0),
                q.depth, q.rowid
            LIMIT 1
        """).fetchone()
        if not row:
            self.pause("Discovery exhausted before the requested complete-work target.")
            return False
        if self.site is None:
            self.site = configured_sites().get(host=HOST)
        url = row["url"]
        try:
            initial, soup = self.page(url)
            try:
                source = discover(soup, url)
            except ImportFailure as exc:
                if exc.code == "archive_structure":
                    self.expand(soup, url, row["depth"])
                if exc.code != "layout":
                    raise
                self.db.execute("UPDATE works SET status='directory' WHERE url=?", (url,))
                self.expand(soup, url, row["depth"])
            else:
                member = self.db.execute(
                    "SELECT work_url FROM members WHERE url=?", (url,)
                ).fetchone()
                if member:
                    self.db.execute("UPDATE works SET status='chapter' WHERE url=?", (url,))
                elif not (not source.book and self.parent_work(soup, url)):
                    details = MarxistCatalogue.metadata(soup, url)
                    if details:
                        save_entry(
                            self.site, details, language=source.metadata["language"], checked=True
                        )
                    if self.audit(url, source, initial) == "failed":
                        self.expand(soup, url, row["depth"])
            self.db.execute("UPDATE queue SET status='done',error='' WHERE url=?", (url,))
        except ImportFailure as exc:
            status = "pending" if exc.code in {"paused", "limit", "yield"} else "failed"
            self.db.execute(
                "UPDATE queue SET status=?,error=? WHERE url=?", (status, str(exc), url)
            )
            if exc.code in {"network", "rate_limited", "unsafe_url", "limit"} or isinstance(
                exc, LimitExceeded
            ):
                self.pause(str(exc))
        except MemoryError:
            from library.services.workers import release_memory_limit

            release_memory_limit()
            error = (
                f"Memory allocation failed while sampling {url}. "
                "Adjust worker resources before resuming."
            )
            self.db.execute("UPDATE queue SET status='pending',error=? WHERE url=?", (error, url))
            self.pause(error)
            raise
        except OSError:
            self.pause(f"Storage failure while sampling {url}; inspect worker log.")
            raise
        self.db.commit()
        return True
