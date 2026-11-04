import hashlib

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils.module_loading import import_string

from library.models import (
    AuthorAlias,
    CatalogueAuthor,
    CatalogueEntry,
    CrawlCapture,
    CrawlSite,
    MetadataSuggestion,
)
from library.profile import get_profile
from library.services.errors import ImportFailure
from library.services.metadata_review import normalize_author_name
from library.services.page_types import is_discovery_page
from library.services.storage import read_blob
from library.sources.base import parse_html
from library.sources.classification import clean_authors, split_authors, unique

AUTHOR_SELECTORS = (
    "meta[name=author], meta[name='dc.creator'], meta[name='dcterms.creator'], "
    ".author, .auteur, .byline, .createdby, [rel=author], [itemprop=author]"
)
DATE_SELECTORS = (
    "meta[name='dc.date'], meta[name='dcterms.issued'], meta[name=date], "
    "meta[property='article:published_time'], time[datetime], [itemprop=datePublished], "
    ".information, .info, .pagenote, .an_pub"
)
TOPIC_SELECTORS = (
    "meta[name='dc.subject'], meta[name=classification], meta[property='article:section'], "
    "[rel=category], [rel='category tag'], [itemprop=articleSection], "
    ".category, .post-category"
)


def source_evidence(soup, field, value):
    selectors = {
        MetadataSuggestion.Field.AUTHOR: AUTHOR_SELECTORS,
        MetadataSuggestion.Field.PUBLISHED: DATE_SELECTORS,
        MetadataSuggestion.Field.TOPIC: TOPIC_SELECTORS,
    }[field]
    target = value.casefold()
    for node in soup.select(selectors):
        text = (
            str(node.get("content", "")) if node.name == "meta" else node.get_text(" ", strip=True)
        )
        text = " ".join(text.split())
        if text and (target in text.casefold() or text.casefold() in target):
            return text[:1000]
    return value[:1000]


def fingerprint(field, value, date_type=""):
    return hashlib.sha256(f"{field}\0{date_type}\0{value}".encode()).hexdigest()


def retained_captures(captures):
    """Release each SQLite read cursor before parsing or writing suggestions."""
    remaining = captures
    while batch := list(remaining[:100]):
        yield from batch
        last = batch[-1]
        remaining = captures.filter(
            Q(captured_at__lt=last.captured_at) | Q(captured_at=last.captured_at, pk__lt=last.pk)
        )


class Command(BaseCommand):
    help = (
        "Propose metadata from retained article HTML for human review; "
        "never fetches or auto-applies."
    )

    def add_arguments(self, parser):
        parser.add_argument("--host", help="Limit processing to one configured source host.")
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Maximum distinct captured article pages to inspect; use 0 for all.",
        )
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        profile = get_profile()
        sources = {source.host: source for source in profile.sources}
        host = options["host"]
        if host and host not in sources:
            raise CommandError(f"Source {host!r} is not configured in the active profile.")
        if options["limit"] < 0:
            raise CommandError("--limit cannot be negative.")
        if host:
            sources = {host: sources[host]}
        sites = list(CrawlSite.objects.filter(profile=profile.key, host__in=sources))
        if not sites:
            self.stdout.write("No configured catalogue sources.")
            return
        adapters = {
            source_host: import_string(source.catalogue_adapter)
            for source_host, source in sources.items()
        }
        entries = {
            (entry.site_id, entry.url): entry
            for entry in CatalogueEntry.objects.filter(
                site__in=sites, discovery_only=False
            ).select_related("site")
        }
        captures = (
            CrawlCapture.objects.filter(site__in=sites, discovery_only=False)
            .select_related("site")
            .order_by("-captured_at", "-pk")
        )
        seen = set()
        dry_run_suggestions = set()
        inspected = 0
        proposed = {field: 0 for field in MetadataSuggestion.Field.values}
        unsupported = 0
        for capture in retained_captures(captures):
            key = (capture.site_id, capture.url)
            entry = entries.get(key)
            if entry is None or key in seen:
                continue
            seen.add(key)
            if options["limit"] and inspected >= options["limit"]:
                break
            inspected += 1
            adapter = adapters[capture.site.host]
            try:
                body = read_blob(capture.response["digest"])
                soup = parse_html(body, capture.response.get("headers", {}))
                if is_discovery_page(adapter, soup, capture.url, site=capture.site):
                    unsupported += 1
                    continue
                link = adapter.metadata(soup, capture.url)
            except ImportFailure:
                unsupported += 1
                continue
            except (KeyError, ValueError) as exc:
                raise CommandError(f"Invalid retained capture for {capture.url}: {exc}") from exc
            if not link:
                unsupported += 1
                continue
            method = (
                f"profile:{profile.key}:{profile.adapter_version}:"
                f"{capture.site.host}:{adapter.__module__}"
            )[:100]

            def add_suggestion(
                field,
                value,
                *,
                date_type="",
                evidence="",
                entry=entry,
                capture=capture,
                soup=soup,
                method=method,
            ):
                value = " ".join(str(value).split()).strip()
                if not value:
                    return
                normalized = (
                    normalize_author_name(value)
                    if field == MetadataSuggestion.Field.AUTHOR
                    else value.casefold()
                )
                value_fingerprint = fingerprint(field, normalized, date_type)
                query = MetadataSuggestion.objects.filter(
                    field=field, fingerprint=value_fingerprint
                )
                if field != MetadataSuggestion.Field.AUTHOR:
                    query = query.filter(entry=entry)
                current = query.first()
                evidence_item = {
                    "url": capture.url,
                    "title": entry.title,
                    "excerpt": (evidence or source_evidence(soup, field, value))[:1000],
                    "captured_at": capture.captured_at.isoformat(),
                }
                if current:
                    if (
                        current.status == MetadataSuggestion.Status.PENDING
                        and current.capture_id
                        and current.capture.discovery_only
                        and not options["dry_run"]
                    ):
                        current.capture = capture
                        current.save(update_fields=["capture"])
                    if (
                        evidence_item["url"]
                        not in {
                            item.get("url") for item in current.evidence if isinstance(item, dict)
                        }
                        and len(current.evidence) < 20
                        and current.status == MetadataSuggestion.Status.PENDING
                    ):
                        current.evidence = [*current.evidence, evidence_item]
                        if not options["dry_run"]:
                            current.save(update_fields=["evidence"])
                    return
                if options["dry_run"]:
                    key = (
                        None if field == MetadataSuggestion.Field.AUTHOR else entry.pk,
                        field,
                        value_fingerprint,
                    )
                    if key in dry_run_suggestions:
                        return
                    dry_run_suggestions.add(key)
                    proposed[field] += 1
                    return
                MetadataSuggestion.objects.create(
                    entry=None if field == MetadataSuggestion.Field.AUTHOR else entry,
                    capture=capture,
                    field=field,
                    value=value[:1000],
                    normalized_value=normalized,
                    date_type=date_type or MetadataSuggestion.DateType.UNKNOWN,
                    evidence=[evidence_item],
                    method=method,
                    fingerprint=value_fingerprint,
                )
                proposed[field] += 1

            raw_authors = clean_authors(link.authors or split_authors(link.author))
            for name in raw_authors:
                normalized = normalize_author_name(name)
                if not normalized:
                    continue
                matches = list(
                    AuthorAlias.objects.filter(normalized_name=normalized).select_related("author")[
                        :2
                    ]
                )
                if len(matches) == 1:
                    if not options["dry_run"]:
                        CatalogueAuthor.objects.get_or_create(
                            entry=entry,
                            author=matches[0].author,
                            role=CatalogueAuthor.Role.AUTHOR,
                            defaults={
                                "source_name": name,
                                "reviewed_by": matches[0].reviewed_by,
                            },
                        )
                    # Existing aliases were reviewed; no new identity proposal is needed.
                    continue
                add_suggestion(
                    MetadataSuggestion.Field.AUTHOR,
                    name,
                    evidence=source_evidence(soup, MetadataSuggestion.Field.AUTHOR, name),
                )

            date_facts = (
                adapter.date_facts(soup, capture.url)
                if callable(getattr(adapter, "date_facts", None))
                else []
            )
            if not date_facts:
                date_facts = (
                    [
                        {
                            "value": link.published,
                            "type": MetadataSuggestion.DateType.PUBLICATION,
                            "evidence": source_evidence(
                                soup, MetadataSuggestion.Field.PUBLISHED, link.published
                            ),
                            "method": "adapter-publication-metadata",
                        }
                    ]
                    if link.published
                    else []
                )
            for fact in date_facts:
                kind = fact.get("type", MetadataSuggestion.DateType.UNKNOWN)
                value = fact.get("value", "")
                if kind == MetadataSuggestion.DateType.PUBLICATION and entry.published:
                    continue
                add_suggestion(
                    MetadataSuggestion.Field.PUBLISHED,
                    value,
                    date_type=kind,
                    evidence=fact.get("evidence", ""),
                )

            for topic in unique(link.topics or [part.strip() for part in link.topic.split(",")]):
                if topic.casefold() in {
                    value.casefold() for value in [*(entry.topics or []), entry.topic]
                }:
                    continue
                topic_evidence = source_evidence(soup, MetadataSuggestion.Field.TOPIC, topic)
                if topic_evidence == topic:
                    body_text = soup.body.get_text(" ", strip=True) if soup.body else ""
                    for term in profile.topic_rules.get(topic, ()):
                        offset = body_text.casefold().find(term.casefold())
                        if offset >= 0:
                            topic_evidence = body_text[max(0, offset - 100) : offset + 200]
                            break
                add_suggestion(MetadataSuggestion.Field.TOPIC, topic, evidence=topic_evidence)
        self.stdout.write(
            f"{'Would propose' if options['dry_run'] else 'Proposed'} "
            f"from {inspected} retained pages "
            f"({unsupported} unsupported): "
            + ", ".join(f"{proposed[field]} {field}" for field in proposed)
            + ". No network requests or automatic fact changes."
        )
