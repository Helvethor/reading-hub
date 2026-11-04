import io
import signal
import socket
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from library.services.errors import ImportFailure, LimitExceeded
from library.services.fetch import (
    Fetcher,
    PinnedHTTPSConnection,
    Response,
    canonical_url,
    public_addresses,
    request_deadline,
    validate_url,
)
from library.tests.test_sources import ARTICLE


class FetchTests(SimpleTestCase):
    def test_subscription_redirect_is_exact_crawler_only_and_checks_robots(self):
        origin = "https://kommunismus.ch/abo"
        destination = "https://adv-verlag.ch/produkt/abonnement-der-kommunist"
        fetcher = Fetcher(source_host="kommunismus.ch")
        with (
            patch.object(fetcher, "_wait"),
            patch.object(
                fetcher,
                "_exchange",
                side_effect=[
                    Response(origin, b"", "", {"location": destination}, 301),
                    Response(
                        "https://adv-verlag.ch/robots.txt",
                        b"User-agent: *\nAllow: /\n",
                        "text/plain",
                        {},
                    ),
                    Response(destination, b"", "", {"location": destination + "/"}, 301),
                    Response(destination + "/", b"<html>Subscription</html>", "text/html", {}),
                ],
            ) as exchange,
            patch.object(fetcher, "_check_robots", wraps=fetcher._check_robots) as robots,
        ):
            # Source robots are already known; destination robots must still be fetched.
            from urllib.robotparser import RobotFileParser

            rules = RobotFileParser()
            rules.parse(["User-agent: *", "Allow: /"])
            fetcher.robot_rules["https://kommunismus.ch"] = rules
            self.assertEqual(fetcher.fetch(origin).url, destination + "/")
            self.assertEqual(exchange.call_count, 4)
            self.assertEqual(robots.call_count, 3)
        with self.assertRaises(ImportFailure):
            validate_url(destination)
        for location in [
            "https://adv-verlag.ch/other",
            destination + "?admin=1",
            "http://adv-verlag.ch/produkt/abonnement-der-kommunist",
        ]:
            with (
                self.subTest(location=location),
                patch.object(fetcher, "_check_robots"),
                patch.object(fetcher, "_wait"),
                patch.object(
                    fetcher,
                    "_exchange",
                    return_value=Response(origin, b"", "", {"location": location}, 301),
                ),
                self.assertRaises(ImportFailure),
            ):
                fetcher.fetch(origin)

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        settings = override_settings(DATA_DIR=Path(directory.name))
        settings.enable()
        self.addCleanup(settings.disable)

    def test_separate_fetchers_share_request_spacing_including_aliases(self):
        first, second = Fetcher(), Fetcher()
        first.last_request, second.last_request = {}, {}
        with patch("time.monotonic", return_value=10), patch("time.sleep"):
            first._wait("communistusa.org")
        with patch("time.monotonic", return_value=10.2), patch("time.sleep") as sleep:
            second._wait("www.communistusa.org")
            self.assertAlmostEqual(sleep.call_args.args[0], 0.8)

    def test_url_validation(self):
        invalid = [
            "http://127.0.0.1/",
            "https://evil.example/",
            "file:///etc/passwd",
            "https://communistusa.org:8080/",
            "https://user:pass@communistusa.org/",
            "https://communistusa.org\\@evil.example/",
            "https://communistusa.org/a b",
            "https://communistusa.org/example.PDF",
            "https://communistusa.org/a%2Epdf",
        ]
        for url in invalid:
            with self.subTest(url=url), self.assertRaises(ImportFailure):
                validate_url(url)
        self.assertEqual(canonical_url("http://www.communistusa.org/sample/#heading"), ARTICLE)
        with self.assertRaises(ImportFailure):
            validate_url("https://i0.wp.com/evil.example/test.jpg", asset=True)
        self.assertEqual(
            validate_url(
                "https://i0.wp.com/communistusa.org/wp-content/uploads/test.jpg", asset=True
            ),
            "https://i0.wp.com/communistusa.org/wp-content/uploads/test.jpg",
        )

    def test_dns_rejects_any_nonpublic_address(self):
        for ip in ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "fc00::1"]:
            with (
                self.subTest(ip=ip),
                patch(
                    "socket.getaddrinfo",
                    return_value=[
                        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
                        (socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443)),
                    ],
                ),
                self.assertRaises(ImportFailure),
            ):
                public_addresses("communistusa.org", 443)

    def test_legacy_swiss_images_follow_only_approved_redirect_paths(self):
        legacy = "https://www.derfunke.ch/htm/wp-content/uploads/2022/10/photo.jpg"
        moved = "https://kommunismus.ch/htm/wp-content/uploads/2022/10/photo.jpg"
        final = "https://kommunismus.ch/wp-content/uploads/2022/10/photo.jpg"
        fetcher = Fetcher()
        with (
            patch.object(fetcher, "_check_robots"),
            patch.object(fetcher, "_wait"),
            patch.object(
                fetcher,
                "_exchange",
                side_effect=[
                    Response(legacy, b"", "", {"location": moved}, 301),
                    Response(moved, b"", "", {"location": final}, 301),
                    Response(final, b"jpeg", "image/jpeg", {}),
                ],
            ) as exchange,
        ):
            self.assertEqual(fetcher.fetch(legacy, asset=True).url, final)
            self.assertEqual(exchange.call_count, 3)
        for host in ("derfunke.ch", "www.derfunke.ch"):
            for url in (f"https://{host}/private.jpg", f"https://{host}/wp-admin/test.jpg"):
                with self.assertRaises(ImportFailure):
                    validate_url(url, asset=True)
            with self.assertRaises(ImportFailure):
                validate_url(f"https://{host}/wp-content/uploads/test.jpg")
        with (
            patch.object(fetcher, "_check_robots"),
            patch.object(fetcher, "_wait"),
            patch.object(
                fetcher,
                "_exchange",
                return_value=Response(
                    legacy, b"", "", {"location": "https://derfunke.ch/private.jpg"}, 302
                ),
            ) as exchange,
        ):
            with self.assertRaises(ImportFailure):
                fetcher.fetch(legacy, asset=True)
            self.assertEqual(exchange.call_count, 1)

    def test_connection_uses_validated_ip_and_tls_hostname(self):
        address = (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))
        conn = PinnedHTTPSConnection("communistusa.org", 443, address, 30)
        with patch("socket.socket") as factory, patch.object(conn._context, "wrap_socket") as tls:
            conn.connect()
            factory.return_value.connect.assert_called_once_with(("8.8.8.8", 443))
            tls.assert_called_once_with(factory.return_value, server_hostname="communistusa.org")
        conn.close()

    def test_robots_disallow(self):
        fetcher = Fetcher()
        with patch.object(
            fetcher,
            "_request",
            return_value=Response(
                ARTICLE,
                b"User-agent: *\nDisallow: /sample/\n",
                "text/plain",
                {},
            ),
        ):
            with self.assertRaisesMessage(ImportFailure, "robots.txt"):
                fetcher._check_robots(ARTICLE, asset=False)

    def test_page_limit_counts_unique_not_fragments(self):
        fetcher = Fetcher()
        with (
            patch("library.services.fetch.MAX_PAGES", 1),
            patch.object(
                fetcher, "_request", return_value=Response(ARTICLE, b"HTML", "text/html", {})
            ),
        ):
            fetcher.fetch(ARTICLE)
            fetcher.fetch(ARTICLE + "#section")
            with self.assertRaises(LimitExceeded):
                fetcher.fetch(ARTICLE + "other/")

    def fake_response(self, data=b"123456", headers=None, status=200):
        response = MagicMock()
        response.status = status
        response.getheaders.return_value = list((headers or {"Content-Type": "text/html"}).items())
        buffer = io.BytesIO(data)
        response.read1.side_effect = buffer.read
        return response

    def request_with(self, response):
        conn = MagicMock()
        conn.getresponse.return_value = response
        return conn

    def test_streaming_byte_limit_does_not_trust_headers(self):
        conn = self.request_with(
            self.fake_response(
                headers={
                    "Content-Type": "text/html",
                    "Content-Length": "1",
                }
            )
        )
        fetcher = Fetcher()
        with (
            patch("library.services.fetch.MAX_BYTES", 4),
            patch("library.services.fetch.public_addresses", return_value=[None]),
            patch("library.services.fetch.PinnedHTTPSConnection", return_value=conn),
            patch.object(fetcher, "_check_robots"),
            patch.object(fetcher, "_wait"),
        ):
            with self.assertRaises(LimitExceeded):
                fetcher.fetch(ARTICLE)
        conn.close.assert_called()

    def test_redirect_target_revalidated(self):
        conn = self.request_with(
            self.fake_response(status=302, headers={"Location": "http://127.0.0.1/private"})
        )
        fetcher = Fetcher()
        with (
            patch("library.services.fetch.public_addresses", return_value=[None]),
            patch("library.services.fetch.PinnedHTTPSConnection", return_value=conn),
            patch.object(fetcher, "_check_robots"),
            patch.object(fetcher, "_wait"),
        ):
            with self.assertRaisesMessage(ImportFailure, "Unsupported source"):
                fetcher.fetch(ARTICLE)

    def test_compressed_response_is_explicitly_rejected(self):
        conn = self.request_with(self.fake_response(headers={"Content-Encoding": "gzip"}))
        fetcher = Fetcher()
        with (
            patch("library.services.fetch.public_addresses", return_value=[None]),
            patch("library.services.fetch.PinnedHTTPSConnection", return_value=conn),
            patch.object(fetcher, "_check_robots"),
            patch.object(fetcher, "_wait"),
        ):
            with self.assertRaisesMessage(ImportFailure, "uncompressed"):
                fetcher.fetch(ARTICLE)

    def test_transient_network_retry_and_unsupported_type(self):
        fetcher = Fetcher()
        result = Response(ARTICLE, b"HTML", "text/html", {})
        with (
            patch.object(fetcher, "_request", side_effect=[OSError("Disconnected"), result]),
            patch("time.sleep"),
        ):
            self.assertEqual(fetcher.fetch(ARTICLE), result)
        with (
            patch.object(
                fetcher,
                "_request",
                return_value=Response(
                    ARTICLE,
                    b"%PDF",
                    "application/pdf",
                    {},
                ),
            ),
            self.assertRaisesMessage(ImportFailure, "Expected HTML"),
        ):
            fetcher.fetch(ARTICLE)

    def test_rate_limit_is_reported_without_immediate_retries(self):
        conn = self.request_with(self.fake_response(status=429, headers={"Retry-After": "120"}))
        fetcher = Fetcher()
        with (
            patch("library.services.fetch.public_addresses", return_value=[None]),
            patch("library.services.fetch.PinnedHTTPSConnection", return_value=conn),
            patch.object(fetcher, "_check_robots"),
            patch.object(fetcher, "_wait"),
        ):
            with self.assertRaisesMessage(ImportFailure, "Retry-After: 120"):
                fetcher.fetch(ARTICLE)
        self.assertEqual(conn.request.call_count, 1)

    def test_default_resource_thresholds(self):
        from library.services.fetch import MAX_BYTES, MAX_PAGES, TIMEOUT

        self.assertEqual(MAX_PAGES, 100)
        self.assertEqual(MAX_BYTES, 104857600)
        self.assertEqual(TIMEOUT, 30)

    def test_request_deadline_interrupts_blocking_work_and_restores_handler(self):
        import time

        previous = signal.getsignal(signal.SIGALRM)
        with patch("library.services.fetch.TIMEOUT", 0.01):
            with self.assertRaises(TimeoutError):
                with request_deadline():
                    time.sleep(0.1)
        self.assertEqual(signal.getsignal(signal.SIGALRM), previous)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL)[0], 0)

    def test_rate_spacing_and_excessive_crawl_delay(self):
        fetcher = Fetcher()
        fetcher.last_request = {"communistusa.org": 9.7}
        with patch("time.monotonic", return_value=10), patch("time.sleep") as sleep:
            fetcher._wait("communistusa.org")
            self.assertAlmostEqual(sleep.call_args.args[0], 0.7)
        with self.assertRaisesMessage(ImportFailure, "crawl delay"):
            fetcher._wait("communistusa.org", 3600)

    def test_all_public_addresses_are_attempted_without_second_dns_lookup(self):
        failed, connected = MagicMock(), self.request_with(self.fake_response())
        failed.connect.side_effect = ConnectionRefusedError()
        fetcher = Fetcher()
        with (
            patch("library.services.fetch.public_addresses", return_value=[None, None]) as dns,
            patch("library.services.fetch.PinnedHTTPSConnection", side_effect=[failed, connected]),
            patch.object(fetcher, "_check_robots"),
            patch.object(fetcher, "_wait"),
        ):
            self.assertEqual(fetcher.fetch(ARTICLE).body, b"123456")
        self.assertEqual(dns.call_count, 1)
        failed.close.assert_called_once()
