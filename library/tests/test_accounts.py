from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

User = get_user_model()
PASSWORD = "A-sturdy-example-passphrase-823"


@override_settings(ALLOWED_HOSTS=["testserver"])
class AccountTests(TestCase):
    def test_simultaneous_duplicate_signup_reports_error_without_promoting_existing_user(self):
        from unittest.mock import patch

        from django.contrib.auth.forms import UserCreationForm

        form = UserCreationForm(
            {
                "username": "racing-reader",
                "password1": PASSWORD,
                "password2": PASSWORD,
            }
        )
        self.assertTrue(form.is_valid())
        original = User.objects.create_user("racing-reader")
        with patch("library.account_views.UserCreationForm", return_value=form):
            response = self.signup("racing-reader")
        self.assertContains(response, "A user with that username already exists.", status_code=400)
        original.refresh_from_db()
        self.assertFalse(original.is_staff)
        self.assertNotIn("_auth_user_id", self.client.session)

    def signup(self, username):
        return self.client.post(
            reverse("signup"),
            {
                "username": username,
                "password1": PASSWORD,
                "password2": PASSWORD,
            },
        )

    def test_first_signup_is_admin_and_later_signup_is_reader(self):
        self.assertRedirects(
            self.signup("first-reader"), "/workers/", fetch_redirect_response=False
        )
        first = User.objects.get(username="first-reader")
        self.assertTrue(first.is_staff)
        self.assertTrue(first.is_superuser)
        admin = self.client.get("/admin/")
        self.assertEqual(admin.status_code, 200)
        self.assertContains(admin, "marxist/admin.css")
        self.assertContains(admin, "library/admin.css")
        self.assertContains(admin, "Reading Hub administration")
        self.client.post(reverse("logout"))
        self.assertRedirects(self.signup("second-reader"), "/")
        second = User.objects.get(username="second-reader")
        self.assertFalse(second.is_staff)
        self.assertFalse(second.is_superuser)

    def test_account_settings_groups_theme_preference_and_rejects_invalid_choice(self):
        user = User.objects.create_user("settings-reader", password=PASSWORD)
        self.client.force_login(user)
        response = self.client.get(reverse("user-settings"))
        self.assertContains(response, "<legend>Appearance preference</legend>", html=True)
        self.assertContains(response, 'name="theme"')
        response = self.client.post(reverse("user-settings"), {"theme": "not-a-theme"})
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Select a valid choice", status_code=400)

    def test_password_validation_and_signup_csrf(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "reader",
                "password1": "short",
                "password2": "short",
            },
        )
        self.assertContains(response, "at least 12 characters", status_code=400)
        self.assertFalse(User.objects.exists())
        strict = Client(enforce_csrf_checks=True)
        self.assertEqual(strict.post(reverse("signup"), {}).status_code, 403)

    def test_login_logout_password_change_and_safe_redirect(self):
        user = User.objects.create_user("reader", password=PASSWORD)
        self.assertEqual(
            self.client.post(
                reverse("login"),
                {
                    "username": "reader",
                    "password": PASSWORD,
                    "next": "https://evil.example/",
                },
            ).url,
            "/",
        )
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        changed = PASSWORD + "-changed"
        response = self.client.post(
            reverse("password_change"),
            {
                "old_password": PASSWORD,
                "new_password1": changed,
                "new_password2": changed,
            },
        )
        self.assertRedirects(response, reverse("password_change_done"))
        user.refresh_from_db()
        self.assertTrue(user.check_password(changed))
        self.assertIn("_auth_user_id", self.client.session)
        self.client.post(reverse("logout"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_worker_and_crawler_pages_and_actions_are_staff_only(self):
        paths = ["/workers/", "/workers/status/", "/workers/1/log/", "/crawlers/"]
        self.assertEqual(
            self.client.get("/workers/status/", HTTP_ACCEPT="application/json").status_code, 401
        )
        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/accounts/login/", response.url)
        user = User.objects.create_user("reader")
        self.client.force_login(user)
        self.assertEqual(
            self.client.get("/workers/status/", HTTP_ACCEPT="application/json").status_code, 403
        )
        for path in paths:
            self.assertEqual(self.client.get(path).status_code, 403, path)
        for path in ["/workers/control/", "/workers/1/", "/crawlers/1/"]:
            self.assertEqual(self.client.post(path, {"action": "start"}).status_code, 403, path)
        self.assertContains(self.client.get("/"), "Browse source catalogue")
        self.assertNotContains(self.client.get("/"), "Manage workers")
