from django.core.management.base import BaseCommand, CommandError
from django.utils.module_loading import import_string

from library.models import CrawlCapture
from library.profile import get_profile
from library.services.catalogue import register_book
from library.services.errors import ImportFailure
from library.services.fetch import canonical_url
from library.services.storage import read_blob
from library.sources.base import parse_html


class Command(BaseCommand):
    help = "Register one retained book contents page and its chapter membership offline."

    def add_arguments(self, parser):
        parser.add_argument("url")
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        profile = get_profile()
        try:
            url = canonical_url(options["url"])
            capture = (
                CrawlCapture.objects.filter(
                    site__profile=profile.key,
                    url=url,
                )
                .select_related("site")
                .order_by("-captured_at", "-pk")
                .first()
            )
            if capture is None or capture.discovery_only:
                raise CommandError("No readable retained contents page exists for this URL.")
            configured = next(
                source for source in profile.sources if source.host == capture.site.host
            )
            adapter = import_string(configured.catalogue_adapter)
            if not hasattr(adapter, "book_source"):
                raise CommandError("This source does not support verified book membership.")
            soup = parse_html(
                read_blob(capture.response["digest"]), capture.response.get("headers", {})
            )
            source = adapter.book_source(soup, url)
            if source is None:
                raise CommandError("Retained page is not recognized as a book contents page.")
            self.stdout.write(f"Book: {source.title}")
            for part in source.parts:
                self.stdout.write(f"  {part.title.strip()}: {part.url}")
            if options["apply"]:
                book = register_book(capture.site, url, source)
                if book.chapters.exists():
                    self.stdout.write(f"Registered book {book.pk} and its chapter relationships.")
                else:
                    self.stdout.write(
                        f"Retained book {book.pk}; no matching complete rendition yet. "
                        "Build the complete book before publishing chapter membership."
                    )
            else:
                self.stdout.write("Dry run; no changes made. Use --apply to register this book.")
        except (ImportFailure, OSError, KeyError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
