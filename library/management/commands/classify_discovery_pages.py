from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils.module_loading import import_string

from library.models import CatalogueEntry, CrawlCapture, CrawlPage, MetadataSuggestion
from library.profile import get_profile
from library.services.errors import ImportFailure
from library.services.page_types import is_discovery_page, preserve_readable_author_reviews
from library.services.storage import read_blob
from library.sources.base import parse_html


class Command(BaseCommand):
    help = "Classify retained discovery indexes offline; preserve source and review history."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Persist classifications.")

    def handle(self, *args, **options):
        profile = get_profile()
        count = 0
        skipped = 0
        for source in profile.sources:
            adapter = import_string(source.catalogue_adapter) if source.catalogue_adapter else None
            if adapter is None or not hasattr(adapter, "is_discovery_page"):
                continue
            captures = CrawlCapture.objects.filter(
                site__profile=profile.key, site__host=source.host
            ).order_by("pk")
            last_pk = 0
            while batch := list(captures.filter(pk__gt=last_pk)[:100]):
                for capture in batch:
                    try:
                        soup = parse_html(
                            read_blob(capture.response["digest"]),
                            capture.response.get("headers", {}),
                        )
                    except (OSError, KeyError, ValueError) as exc:
                        raise CommandError(f"Cannot classify capture {capture.pk}: {exc}") from exc
                    except ImportFailure as exc:
                        if exc.code != "encoding":
                            raise CommandError(
                                f"Cannot classify capture {capture.pk}: {exc}"
                            ) from exc
                        skipped += 1
                        self.stderr.write(
                            f"Skipped unclassifiable capture {capture.pk} ({capture.url}): {exc}"
                        )
                        continue
                    if not is_discovery_page(adapter, soup, capture.url, site=capture.site):
                        continue
                    count += 1
                    self.stdout.write(f"Discovery index: capture {capture.pk} {capture.url}")
                    if options["apply"]:
                        CrawlCapture.objects.filter(pk=capture.pk).update(discovery_only=True)
                        CatalogueEntry.objects.filter(
                            site_id=capture.site_id, url=capture.url
                        ).update(discovery_only=True)
                        # A formerly article-labelled index may never have had its
                        # links followed. Retry it on the next normal crawl resume.
                        CrawlPage.objects.filter(
                            site_id=capture.site_id,
                            url=capture.url,
                            is_article=True,
                            status="done",
                        ).update(status="pending", error="")
                        CrawlPage.objects.filter(site_id=capture.site_id, url=capture.url).update(
                            is_article=False
                        )
                last_pk = batch[-1].pk
        self.stdout.write(
            f"{'Classified' if options['apply'] else 'Would classify'} {count} retained indexes. "
            f"{skipped} captures skipped with reported encoding errors. "
            "No source blobs, decisions, corrections or renditions deleted."
        )
        if not options["apply"]:
            return
        # Author proposals aggregate evidence from multiple works. An index must
        # not hide a proposal that still has a verified, readable evidence page.
        pending = (
            MetadataSuggestion.objects.filter(
                status=MetadataSuggestion.Status.PENDING,
                field=MetadataSuggestion.Field.AUTHOR,
            )
            .filter(Q(capture__discovery_only=True) | Q(entry__discovery_only=True))
            .filter(Q(capture__site__profile=profile.key) | Q(entry__site__profile=profile.key))
        )
        try:
            kept = preserve_readable_author_reviews(pending)
        except (OSError, KeyError, ValueError) as exc:
            raise CommandError(f"Cannot inspect retained review evidence: {exc}") from exc
        for suggestion_id, capture_id in kept:
            self.stdout.write(
                f"Kept author proposal {suggestion_id} using readable capture {capture_id}."
            )
