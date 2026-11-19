#!/usr/bin/env python3
import argparse
import http.cookiejar
import json
import os
import ssl
import stat
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import (
    HTTPCookieProcessor,
    HTTPSHandler,
    Request,
    build_opener,
)


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.csrf_token = None
        self.initial_data = []
        self.reading_initial = False
        self.stylesheets = []

    def handle_starttag(self, tag, attributes):
        values = dict(attributes)
        if tag == "input" and values.get("name") == "csrfmiddlewaretoken":
            self.csrf_token = values.get("value")
        if tag == "link" and "stylesheet" in values.get("rel", "").split():
            href = values.get("href", "")
            if href.startswith("/static/"):
                self.stylesheets.append(href)
        if tag == "script" and values.get("id") == "document-editor-initial":
            self.reading_initial = True

    def handle_endtag(self, tag):
        if tag == "script" and self.reading_initial:
            self.reading_initial = False

    def handle_data(self, data):
        if self.reading_initial:
            self.initial_data.append(data)


def fail(message):
    raise SystemExit(message)


def main():
    state_home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    simulation_dir = state_home / "reading-hub" / "production-simulation"
    parser = argparse.ArgumentParser(
        description="Exercise the isolated local production simulation over HTTPS."
    )
    parser.add_argument("--port", type=int, default=8444)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    if not 1 <= args.port <= 65535:
        fail("The HTTPS port must be between 1 and 65535.")
    data_dir = simulation_dir / "data"
    credentials_path = data_dir / "development-credentials.json"
    manifest_path = data_dir / "development-fixtures.json"
    certificate_path = simulation_dir / "tls" / "server.crt"
    for path in (credentials_path, manifest_path, certificate_path):
        if path.is_symlink() or not path.is_file():
            fail(f"Required local simulation file is missing or unsafe: {path.name}")
    if stat.S_IMODE(credentials_path.stat().st_mode) != 0o600:
        fail("Synthetic fixture credentials must have mode 0600.")

    credentials = json.loads(credentials_path.read_text(encoding="utf-8"))["reviewer"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("synthetic") is not True:
        fail("The fixture manifest is not marked synthetic.")

    base_url = f"https://localhost:{args.port}"
    context = ssl.create_default_context(cafile=str(certificate_path))
    opener = build_opener(
        HTTPCookieProcessor(http.cookiejar.CookieJar()),
        HTTPSHandler(context=context),
    )

    def request(path, *, data=None, headers=None, method=None, timeout=30):
        url = base_url + path
        outgoing = Request(url, data=data, headers=headers or {}, method=method)
        try:
            with opener.open(outgoing, timeout=timeout) as response:
                return response.status, response.headers, response.read()
        except (HTTPError, URLError) as exc:
            fail(f"Local HTTPS request failed for {path}: {exc}")

    fixtures = manifest["fixtures"]
    for kind in ("article", "book"):
        fixture = fixtures[kind]
        status, _, page = request(fixture["reader_url"])
        if status != 200 or b"Synthetic" not in page:
            fail(f"The public synthetic {kind} reader did not load.")
        if kind == "article":
            reader_parser = PageParser()
            reader_parser.feed(page.decode("utf-8"))
            if not reader_parser.stylesheets:
                fail("The synthetic article reader did not reference a static stylesheet.")
            status, headers, stylesheet = request(reader_parser.stylesheets[0])
            if status != 200 or headers.get_content_type() != "text/css" or not stylesheet:
                fail("The production static stylesheet did not load.")
        status, headers, pdf = request(fixture["pdf_url"], timeout=120)
        if status != 200 or headers.get_content_type() != "application/pdf":
            fail(f"The synthetic {kind} PDF did not load.")
        if not pdf.startswith(b"%PDF-"):
            fail(f"The synthetic {kind} PDF response is invalid.")

    login_path = "/accounts/login/"
    status, _, login_page = request(login_path)
    if status != 200:
        fail("The reviewer sign-in page did not load.")
    login_parser = PageParser()
    login_parser.feed(login_page.decode("utf-8"))
    if not login_parser.csrf_token:
        fail("The sign-in page did not provide a CSRF token.")
    login_body = urlencode(
        {
            "username": credentials["username"],
            "password": credentials["password"],
            "csrfmiddlewaretoken": login_parser.csrf_token,
            "next": "/",
        }
    ).encode()
    status, _, page = request(
        login_path,
        data=login_body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": base_url,
            "Referer": base_url + login_path,
        },
        method="POST",
    )
    if status != 200 or b"Sign out" not in page:
        fail("The synthetic reviewer could not sign in.")

    for kind in ("article", "book"):
        fixture = fixtures[kind]
        workspace_path = fixture["workspace_url"]
        status, _, workspace_page = request(workspace_path)
        if status != 200:
            fail(f"The authenticated {kind} workspace did not load.")
        workspace_parser = PageParser()
        workspace_parser.feed(workspace_page.decode("utf-8"))
        if not workspace_parser.csrf_token or not workspace_parser.initial_data:
            fail(f"The {kind} workspace did not expose its saved draft state.")
        initial = json.loads("".join(workspace_parser.initial_data))
        marker = f"Synthetic HTTPS smoke edit ({kind})"
        document = initial["document"]

        if marker not in document["html"]:
            if args.verify_only or initial["revision"] != 1:
                fail(f"The saved {kind} smoke edit did not survive container recreation.")
            if "Synthetic edited text" not in document["html"]:
                fail(f"The {kind} source fixture no longer matches the smoke-test baseline.")
            edited = {
                **document,
                "title": f"{document['title']} - {marker}",
                "html": document["html"].replace(
                    "Synthetic edited text",
                    marker,
                    1,
                ),
            }
            payload = json.dumps(
                {
                    "draft": initial["draft"],
                    "revision": initial["revision"],
                    "document": edited,
                    "conversion_approval": None,
                    "review": "partial",
                    "verified_sections": [],
                    "editorial": True,
                    "source_tickets": [],
                }
            ).encode()
            status, _, saved_body = request(
                workspace_path,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Origin": base_url,
                    "Referer": base_url + workspace_path,
                    "X-CSRFToken": workspace_parser.csrf_token,
                },
                method="POST",
            )
            if status != 200:
                fail(f"The {kind} smoke edit did not save.")
            saved = json.loads(saved_body)
            if saved["revision"] != 2 or marker not in saved["document"]["html"]:
                fail(f"The {kind} smoke edit returned an unexpected saved revision.")
            status, _, reopened_page = request(workspace_path)
            if status != 200:
                fail(f"The saved {kind} workspace did not reopen.")
            reopened_parser = PageParser()
            reopened_parser.feed(reopened_page.decode("utf-8"))
            reopened = json.loads("".join(reopened_parser.initial_data))
            if reopened["document"] != saved["document"]:
                fail(f"The saved {kind} workspace did not reopen with the new revision.")
        elif initial["revision"] < 2:
            fail(f"The saved {kind} smoke edit has an invalid revision.")

    print("Synthetic article and book readers/PDFs passed; authenticated edits reopened.")


if __name__ == "__main__":
    main()
