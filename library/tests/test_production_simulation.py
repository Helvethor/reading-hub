import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from library.models import Document


class ProductionSimulationSeedTests(TestCase):
    @override_settings(READING_HUB_ENVIRONMENT="production", DEBUG=False)
    def test_seed_requires_simulation_marker_and_explicit_confirmation(self):
        with patch.dict(os.environ, {"READING_HUB_LOCAL_SIMULATION": "0"}):
            with self.assertRaisesMessage(CommandError, "isolated local simulation"):
                call_command("seed_production_simulation", confirm_synthetic_data=True)

        with patch.dict(os.environ, {"READING_HUB_LOCAL_SIMULATION": "1"}):
            with self.assertRaisesMessage(CommandError, "--confirm-synthetic-data"):
                call_command("seed_production_simulation")

        self.assertFalse(get_user_model().objects.exists())
        self.assertFalse(Document.objects.exists())
