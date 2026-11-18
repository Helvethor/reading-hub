import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from pypdf import PdfReader

from library.models import UserSettings
from library.services.pdf import cached_pdf, render_pdf
from library.services.reading_styles import DEFAULTS, style_token
from library.tests import test_printing
from library.themes import COOKIE


class ThemeTests(TestCase):
    def choose(self, theme, **extra):
        return self.client.post(reverse("change-theme"), {"theme": theme, **extra},
                                HTTP_ACCEPT="application/json")

    def test_square_ui_is_included_for_marxist_themes(self):
        for theme in ("", "dark"):
            if theme:
                self.choose(theme)
            for url in ("/", reverse("login")):
                with self.subTest(theme=theme, url=url):
                    response = self.client.get(url)
                    self.assertContains(response, "/static/marxist/square-ui.css")
                    self.assertContains(response, 'media="screen"')
                    self.assertContains(response, 'class="site-navigation-group"')
                    stylesheet = "dark.css" if theme else "theme.css"
                    self.assertContains(response, f"/static/marxist/{stylesheet}")

    def test_guest_default_cookie_and_reset_without_accounts(self):
        self.assertContains(self.client.get("/"), "/static/marxist/theme.css")
        self.assertContains(self.client.get("/"), 'data-theme-form')
        response = self.choose("dark")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["stylesheet"], "/static/marxist/dark.css")
        self.assertEqual(response.cookies[COOKIE]["max-age"], 365 * 24 * 60 * 60)
        self.assertTrue(response.cookies[COOKIE]["httponly"])
        self.assertContains(self.client.get("/"), "/static/marxist/dark.css")
        self.assertFalse(UserSettings.objects.exists())
        self.choose("")
        self.assertContains(self.client.get("/"), "/static/marxist/theme.css")
        self.client.cookies[COOKIE] = "../../invalid.css"
        self.assertContains(self.client.get("/"), "/static/marxist/theme.css")

    def test_preview_theme_cookies_ignore_other_environments(self):
        self.client.cookies["reading_hub_theme"] = "dark"
        with override_settings(READING_HUB_THEME_COOKIE_NAME="isolated-preview-theme"):
            self.assertContains(self.client.get("/"), "/static/marxist/theme.css")
            response = self.choose("dark")
            self.assertIn("isolated-preview-theme", response.cookies)
            self.assertNotIn("reading_hub_theme", response.cookies)
            self.assertContains(self.client.get("/"), "/static/marxist/dark.css")
            self.choose("")
            self.assertContains(self.client.get("/"), "/static/marxist/theme.css")

    @override_settings(READING_HUB_PROFILE="profiles.marxist.dark")
    def test_configured_default_is_overridable(self):
        self.assertContains(self.client.get("/"), "/static/marxist/dark.css")
        self.choose("paper")
        self.assertContains(self.client.get("/"), "/static/marxist/theme.css")
        self.choose("")
        self.assertContains(self.client.get("/"), "/static/marxist/dark.css")

    def test_account_settings_persist_across_sessions_and_isolate_users(self):
        user = get_user_model().objects.create_user("theme-owner")
        other = get_user_model().objects.create_user("another-theme-owner")
        self.client.force_login(user)
        self.choose("dark")
        self.assertEqual(UserSettings.objects.get(user=user).theme, "dark")
        fresh = Client()
        fresh.force_login(user)
        self.assertContains(fresh.get("/"), "/static/marxist/dark.css")
        settings_url = reverse("user-settings")
        response = fresh.get(settings_url)
        self.assertEqual(response.context["form"].initial["theme"], "dark")
        self.assertRedirects(fresh.post(settings_url, {"theme": "paper"}), settings_url)
        self.assertEqual(UserSettings.objects.get(user=user).theme, "paper")
        self.assertContains(self.client.get("/"), "/static/marxist/theme.css")
        fresh.force_login(other)
        self.assertContains(fresh.get("/"), "/static/marxist/theme.css")
        self.assertFalse(UserSettings.objects.filter(user=other).exists())
        self.assertEqual(fresh.get(settings_url).status_code, 200)
        fresh.post(settings_url, {"theme": ""})
        fresh.cookies[COOKIE] = "dark"
        self.assertContains(fresh.get("/"), "/static/marxist/theme.css")

    def test_validation_csrf_methods_redirect_and_read_only_settings(self):
        url = reverse("change-theme")
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.choose("unknown").status_code, 400)
        strict = Client(enforce_csrf_checks=True)
        self.assertEqual(strict.post(url, {"theme": "dark"}).status_code, 403)
        self.assertEqual(self.client.get(reverse("user-settings")).status_code, 302)
        response = self.client.post(url, {"theme": "dark", "next": "https://evil.example/"})
        self.assertEqual(response.url, "/")
        user = get_user_model().objects.create_user("settings-reader")
        self.client.force_login(user)
        self.client.get(reverse("user-settings"))
        self.assertFalse(UserSettings.objects.exists())
        response = self.client.post(reverse("user-settings"), {"theme": "invalid"})
        self.assertContains(response, "Select a valid choice", status_code=400)
        self.assertFalse(UserSettings.objects.exists())

    def test_follow_theme_css_uses_preference_without_changing_signed_style(self):
        settings = {**DEFAULTS, "palette": "theme"}
        token = style_token(settings)
        self.choose("dark")
        response = self.client.get(reverse("reading-style-css"), {"style": token})
        self.assertContains(response, "var(--ink, #e6e6e6)")
        self.assertContains(response, "background: #181818")
        self.choose("paper")
        response = self.client.get(reverse("reading-style-css"), {"style": token})
        self.assertContains(response, "var(--ink, #302221)")
        self.assertContains(response, "background: #faf5ef")


class ThemePDFTests(TestCase):
    setUp = test_printing.PrintingTests.setUp

    def test_rendered_follow_theme_pdf_contains_dark_paper_and_off_white_ink(self):
        path = Path(self.temp.name) / "dark-theme.pdf"
        render_pdf(self.version, path, {**DEFAULTS, "palette": "theme"}, theme="dark")
        stream = b"\n".join(page.get_contents().get_data() for page in PdfReader(path).pages)
        self.assertIn(b"0.094118 0.094118 0.094118 rg", stream)
        self.assertIn(b"0.901961 0.901961 0.901961 rg", stream)

    def test_rendered_dark_lenin_palette_pdf_uses_its_paper_ink_and_accent(self):
        path = Path(self.temp.name) / "lenin-dark.pdf"
        render_pdf(self.version, path, {**DEFAULTS, "palette": "lenin", "mode": "dark"})
        stream = b"\n".join(page.get_contents().get_data() for page in PdfReader(path).pages)
        self.assertIn(b"0.121569 0.039216 0.039216 rg", stream, "Dark red-black paper")
        self.assertIn(b"0.956863 0.894118 0.862745 rg", stream, "Warm off-white ink")
        self.assertIn(b"1 0.478431 0.419608 rg", stream, "Red accent for headings")

    def test_theme_pdf_cache_binds_palette_and_subprocess_selection(self):
        settings = {**DEFAULTS, "palette": "theme"}
        themes = []

        def build(command, **kwargs):
            self.assertEqual(json.loads(command[-2]), settings)
            themes.append(kwargs["env"]["READING_HUB_PDF_THEME"])
            Path(command[-1]).write_bytes(b"%PDF-test")
            return subprocess.CompletedProcess(command, 0)

        with patch("library.services.pdf.subprocess.run", side_effect=build):
            paper = cached_pdf(self.version, settings, theme="paper")
            dark = cached_pdf(self.version, settings, theme="dark")
            self.assertNotEqual(paper, dark)
            self.assertEqual(cached_pdf(self.version, settings, theme="dark"), dark)
            self.assertEqual(themes, ["paper", "dark"])

    def test_pdf_download_passes_request_theme(self):
        path = Path(self.temp.name) / "theme-download.pdf"
        path.write_bytes(b"%PDF-test")
        self.client.post(reverse("change-theme"), {"theme": "dark"})
        with patch("library.views.cached_pdf", return_value=path) as exporter:
            response = self.client.get(reverse("reader-pdf", args=[self.version.pk]))
            self.assertEqual(exporter.call_args.kwargs["theme"], "dark")
            response.close()
