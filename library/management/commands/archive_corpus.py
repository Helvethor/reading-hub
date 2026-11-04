import json

from django.core.management.base import BaseCommand, CommandError

from library.profile import get_profile
from profiles.marxist.corpus import HOST, ArchiveCorpus


class Command(BaseCommand):
    help = "Start/pause or inspect the persistent multilingual whole-work archive audit."

    def add_arguments(self, parser):
        actions = parser.add_mutually_exclusive_group()
        actions.add_argument("--start", action="store_true")
        actions.add_argument("--pause", action="store_true")
        parser.add_argument("--target", type=int, default=1000)
        parser.add_argument("--retry-failed", action="store_true")
        parser.add_argument("--recheck", action="store_true")

    def handle(self, *args, **options):
        if options["target"] < 1:
            raise CommandError("--target must be positive.")
        if not any(site.host == HOST for site in get_profile().sources):
            raise CommandError("The active profile does not include the Marxists Internet Archive.")
        corpus = ArchiveCorpus()
        try:
            if options["start"]:
                corpus.start(options["target"], options["retry_failed"], options["recheck"])
            elif options["pause"]:
                corpus.pause()
            elif options["retry_failed"] or options["recheck"]:
                raise CommandError("--retry-failed and --recheck require --start.")
            self.stdout.write(json.dumps(corpus.report(), indent=2, ensure_ascii=False))
        finally:
            corpus.close()
