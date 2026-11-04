import json

from django.core.management.base import BaseCommand, CommandError

from library.models import Rendition
from library.services.document_edits import preview_rendition_import
from library.services.semantic_documents import (
    SCHEMA_VERSION,
    canonical_document,
    document_issues,
    fingerprint,
)


class Command(BaseCommand):
    help = "Check up to 50 retained editions against the draft semantic contract, read-only."

    def add_arguments(self, parser):
        parser.add_argument("renditions", type=int, nargs="+", help="Exact retained edition IDs.")
        parser.add_argument(
            "--preview-conversion", action="store_true",
            help="Propose audited legacy wrapper repairs without saving or approving them.",
        )
        parser.add_argument(
            "--include-document", action="store_true",
            help="Include the proposed semantic document for one conversion preview.",
        )

    def handle(self, *args, **options):
        ids = options["renditions"]
        if not 1 <= len(ids) <= 50 or len(ids) != len(set(ids)) or any(pk <= 0 for pk in ids):
            raise CommandError("Choose 1-50 distinct positive rendition IDs.")
        if options["include_document"] and (
            not options["preview_conversion"] or len(ids) != 1
        ):
            raise CommandError("Document output requires one edition and --preview-conversion.")
        editions = {
            row.pk: row for row in Rendition.objects.filter(pk__in=ids).select_related("snapshot")
        }
        results = []
        for pk in ids:
            row = editions.get(pk)
            if row is None:
                results.append({
                    "rendition": pk, "compatible": False, "error": "Edition not found.",
                })
                continue
            try:
                original = {
                    "version": SCHEMA_VERSION, "title": row.title,
                    "metadata": row.metadata, "html": row.html,
                }
                proposal = preview_rendition_import(row) if options["preview_conversion"] else None
                value = proposal["document"] if proposal else canonical_document(original)
                if canonical_document(value) != value:
                    raise ValueError("Semantic round-trip changed the canonical document.")
            except ValueError as exc:
                results.append({"rendition": pk, "compatible": False, "error": str(exc)})
                continue
            assets = set(row.assets.values_list("blob_id", flat=True))
            results.append({
                "rendition": pk, "compatible": True, "document_digest": fingerprint(value),
                "issues": document_issues(value, assets),
                **({
                    "conversion": proposal["conversion"],
                    "approval_digest": proposal["approval_digest"],
                    "requires_approval": proposal["requires_approval"],
                } if proposal else {}),
                **({"document": value} if options["include_document"] else {}),
            })
        self.stdout.write(json.dumps({
            "document_version": SCHEMA_VERSION,
            "semantics": "contract_check_not_review_certification",
            "results": results,
        }, ensure_ascii=False, indent=2))
        if any(not item["compatible"] or item.get("issues") for item in results):
            raise CommandError("Some editions require semantic conversion or relationship repair.")
