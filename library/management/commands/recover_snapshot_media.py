import copy
import hashlib
import json
import logging

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from library import versions
from library.models import Blob, Snapshot
from library.profile import get_profile
from library.services.errors import ImportFailure, LimitExceeded
from library.services.fetch import Fetcher
from library.services.media import fetch_image, image_request_url
from library.services.pipeline import fingerprint, snapshot_digest
from library.services.storage import store_blob

logger = logging.getLogger("library")


class Command(BaseCommand):
    help = (
        "Preview retries of failed images recorded in a retained snapshot. "
        "Use --apply PREVIEW_DIGEST to save a separate snapshot, never an edition."
    )

    def add_arguments(self, parser):
        parser.add_argument("snapshot", type=int)
        parser.add_argument("--apply", metavar="PREVIEW_DIGEST")

    def handle(self, *args, **options):
        token = options["apply"]
        if token is not None and (
            len(token) != 64 or any(char not in "0123456789abcdef" for char in token)
        ):
            raise CommandError("--apply requires the exact SHA-256 preview digest.")
        try:
            original = Snapshot.objects.get(pk=options["snapshot"])
        except Snapshot.DoesNotExist as exc:
            raise CommandError("Snapshot not found.") from exc
        failed = {
            url: info for url, info in original.manifest["assets"].items()
            if info.get("error") and not info.get("digest")
        }
        if len(failed) > 50:
            raise CommandError("Recovery is limited to 50 recorded failed images per snapshot.")
        fetcher = Fetcher()
        results, responses = [], {}
        for url in sorted(failed):
            try:
                response = fetch_image(fetcher, url)
            except LimitExceeded as exc:
                raise CommandError(str(exc)) from exc
            except (ImportFailure, ValueError) as exc:
                logger.warning("Media recovery failed for %s: %s", url, exc)
                results.append({"url": url, "recovered": False, "error": str(exc)})
                continue
            responses[url] = response
            results.append({
                "url": url, "recovered": True,
                "requested_url": image_request_url(url), "resolved_url": response.url,
                "digest": hashlib.sha256(response.body).hexdigest(),
                "media_type": response.media_type, "size": len(response.body),
            })
        plan = {
            "snapshot": original.pk, "source_digest": original.digest,
            "manifest_digest": fingerprint(original.manifest), "results": results,
            "app_version": versions.APP_VERSION, "profile": get_profile().key,
        }
        digest = fingerprint(plan)
        report = {
            **plan, "preview_digest": digest, "applied": False,
            "recovered_images": len(responses),
            "remaining_failed_images": len(failed) - len(responses),
            "semantics": "media_recovery_not_source_refresh_or_review_certification",
        }
        if token is not None:
            if token != digest:
                raise CommandError(
                    "Recovery changed since preview; run a new preview before applying."
                )
            if not responses:
                raise CommandError("No images recovered; no snapshot was created.")
            manifest = copy.deepcopy(original.manifest)
            recovered = [item for item in results if item["recovered"]]
            captured_at = timezone.now().isoformat()
            manifest["media_recovery"] = {
                "version": 1, "source_snapshot": original.pk,
                "source_digest": original.digest, "preview_digest": digest,
                "retrieved_at": captured_at, "results": results,
                "app_version": versions.APP_VERSION, "profile": get_profile().key,
            }
            remaining_warnings = [
                warning for warning in original.warnings
                if not any(warning.startswith(f"Missing image {url}:") for url in responses)
            ]
            try:
                with transaction.atomic():
                    for item in recovered:
                        body = responses[item["url"]].body
                        retained_digest = store_blob(body)
                        info = {key: item[key] for key in ("digest", "media_type", "size")}
                        if retained_digest != info["digest"]:
                            raise ValueError("Recovered image digest changed before storage.")
                        Blob.objects.get_or_create(digest=retained_digest, defaults={
                            "media_type": info["media_type"], "size": info["size"],
                        })
                        manifest["assets"][item["url"]] = info
                    snapshot, created = Snapshot.objects.get_or_create(
                        document_id=original.document_id,
                        digest=snapshot_digest(manifest),
                        defaults={"manifest": manifest, "warnings": remaining_warnings},
                    )
            except (OSError, ValueError) as exc:
                raise CommandError(f"Unable to retain recovered media: {exc}") from exc
            report.update(applied=True, recovered_snapshot=snapshot.pk, created=created)
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
