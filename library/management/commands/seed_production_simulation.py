import json
import os
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor

from config.environments import validate_environment
from library.management.commands.seed_development import (
    FIXTURE_VERSION,
    ROLES,
    fixture_users,
    retained_plate,
    seed_work,
    write_private_json,
)
from library.models import Document, Job
from library.profile import get_profile


class Command(BaseCommand):
    help = "Seed offline synthetic works into an explicitly marked local production simulation."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm-synthetic-data",
            action="store_true",
            help="Confirm that this database is a disposable local production simulation.",
        )

    def handle(self, *args, **options):
        if (
            settings.READING_HUB_ENVIRONMENT != "production"
            or settings.DEBUG
            or os.environ.get("READING_HUB_LOCAL_SIMULATION") != "1"
        ):
            raise CommandError(
                "Synthetic production fixtures require the isolated local simulation setting."
            )
        if not options["confirm_synthetic_data"]:
            raise CommandError("Pass --confirm-synthetic-data to seed this simulation.")
        if settings.READING_HUB_ALLOW_WORKERS:
            raise CommandError("Disable workers before seeding the local production simulation.")

        data = Path(settings.DATA_DIR).resolve()
        database = settings.DATABASES["default"]["NAME"]
        try:
            validate_environment("production", settings.BASE_DIR, data, database)
        except (OSError, ValueError) as exc:
            raise CommandError(
                f"The simulation data path is not isolated from live storage: {exc}"
            ) from exc
        executor = MigrationExecutor(connection)
        if executor.migration_plan(executor.loader.graph.leaf_nodes()):
            raise CommandError("Apply migrations explicitly before seeding synthetic fixtures.")

        profile = get_profile()
        expected_urls = {
            f"https://{profile.sources[0].host}/reading-hub-synthetic/{kind}/index.htm"
            for kind in ("article", "book")
        }
        expected_users = {username for username, _, _ in ROLES.values()}
        if get_user_model().objects.exclude(username__in=expected_users).exists():
            raise CommandError("Refusing to seed a simulation with non-fixture accounts.")
        if Document.objects.exclude(url__in=expected_urls).exists() or Job.objects.exists():
            raise CommandError("Refusing to seed a simulation with unrelated or queued records.")

        data.mkdir(parents=True, exist_ok=True, mode=0o700)
        credentials_path = data / "development-credentials.json"
        manifest_path = data / "development-fixtures.json"
        if manifest_path.is_symlink():
            raise CommandError("The fixture manifest must not be a symlink.")
        with transaction.atomic():
            users = fixture_users(credentials_path)
            blob = retained_plate()
            fixtures = {
                kind: seed_work(kind, users["reviewer"], blob) for kind in ("article", "book")
            }
            manifest = {
                "version": FIXTURE_VERSION,
                "synthetic": True,
                "profile": profile.key,
                "fixtures": fixtures,
            }
            if manifest_path.exists():
                try:
                    previous = json.loads(manifest_path.read_text(encoding="utf-8"))
                except ValueError as exc:
                    raise CommandError(
                        "Invalid fixture manifest; no simulation state was reset."
                    ) from exc
                if previous != manifest:
                    raise CommandError(
                        "Existing fixture manifest differs; no simulation state was reset."
                    )
            else:
                write_private_json(manifest_path, manifest)

        self.stdout.write(str(credentials_path))
        self.stdout.write(str(manifest_path))
        for fixture in fixtures.values():
            self.stdout.write(fixture["reader_url"])
            self.stdout.write(fixture["workspace_url"])
