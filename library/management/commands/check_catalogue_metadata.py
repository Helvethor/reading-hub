from collections import Counter

from django.core.management.base import BaseCommand, CommandError

from library.models import CatalogueEntry
from library.profile import get_profile
from library.sources.classification import (
    clean_attribution,
    clean_authors,
    normalize_language,
    unique,
)


class Command(BaseCommand):
    help = "Check stored catalogue metadata coherence without network requests or changes."

    def handle(self, *args, **options):
        profile = get_profile()
        counts, unknown, missing, issues = Counter(), Counter(), Counter(), []
        entries = CatalogueEntry.objects.filter(
            site__profile=profile.key, site__host__in=[site.host for site in profile.sources]
        ).select_related("site")
        for entry in entries.iterator():
            counts[entry.site.host] += 1
            if not entry.language or entry.language == "und":
                unknown[entry.site.host] += 1
            for field, absent in (
                ("authors", not entry.author and not entry.authors),
                ("dates", not entry.published),
                ("topics", not entry.topic and not entry.topics),
                ("eras", not entry.era),
            ):
                missing[entry.site.host, field] += bool(absent)
            problems = []
            if not entry.title.strip():
                problems.append("empty title")
            if entry.language and normalize_language(entry.language) != entry.language:
                problems.append("invalid or noncanonical language code")
            if clean_attribution(entry.author) != entry.author:
                problems.append("date-only author or trailing author date")
            if not isinstance(entry.authors, list) or any(
                not isinstance(value, str) or not value.strip() for value in entry.authors
            ):
                problems.append("invalid author list")
            elif clean_authors(entry.authors) != entry.authors:
                problems.append("dates, affiliations, or duplicates in author list")
            if not isinstance(entry.topics, list) or any(
                not isinstance(value, str) or not value.strip() for value in entry.topics
            ):
                problems.append("invalid topic list")
            elif unique(entry.topics) != entry.topics:
                problems.append("duplicate or untrimmed topics")
            if problems:
                issues.append((entry.url, "; ".join(problems)))
        for host in sorted(counts):
            self.stdout.write(
                f"{host}: {counts[host]} entries checked; {unknown[host]} unknown languages."
            )
            self.stdout.write(
                "  Missing source evidence: "
                + ", ".join(
                    f"{missing[host, field]} {field}"
                    for field in ("authors", "dates", "topics", "eras")
                )
                + ". Missing authors use the website display fallback."
            )
        for url, problem in issues[:20]:
            self.stderr.write(f"{url}: {problem}")
        if issues:
            raise CommandError(
                f"{len(issues)} entries have metadata coherence issues "
                "(showing at most 20); rebuild cached metadata before checking again."
            )
        self.stdout.write(
            f"Checked {sum(counts.values())} entries: no coherence issues; no network used."
        )
