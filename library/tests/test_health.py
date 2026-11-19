from unittest.mock import patch

from django.test import TestCase


class HealthTests(TestCase):
    def test_health_reports_ready_after_database_migrations(self):
        response = self.client.get("/healthz/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")

    def test_health_reports_unavailable_when_migrations_are_pending(self):
        with patch("library.views.MigrationExecutor") as migration_executor:
            migration_executor.return_value.loader.graph.leaf_nodes.return_value = [
                ("library", "0001_initial")
            ]
            migration_executor.return_value.migration_plan.return_value = [object()]
            response = self.client.get("/healthz/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.content, b"unavailable")

    def test_health_is_get_only(self):
        self.assertEqual(self.client.post("/healthz/").status_code, 405)
