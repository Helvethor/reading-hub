import re
from difflib import SequenceMatcher

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import transaction
from django.utils import timezone

from library.models import (
    AuthorAlias,
    CanonicalAuthor,
    CatalogueAuthor,
    CatalogueEntry,
    MetadataReviewEvent,
    MetadataSuggestion,
    SourceCorrection,
)
from library.sources.classification import clean_authors, fold, split_authors, unique


def normalize_author_name(value):
    return " ".join(re.findall(r"[^\W_]+", value.casefold(), flags=re.UNICODE))


def scoped_author_correction(suggestion):
    if suggestion.field != MetadataSuggestion.Field.AUTHOR or not suggestion.capture_id:
        return None
    correction = (
        SourceCorrection.objects.filter(
            capture_id=suggestion.capture_id, profile=suggestion.capture.site.profile
        )
        .order_by("-revision")
        .first()
    )
    if correction is None or "people" not in correction.expected.get("metadata", {}):
        return None
    return correction


def candidate_author_matches(value, limit=5, *, authors=None):
    normalized = normalize_author_name(value)
    surname = fold(normalized.split()[-1]) if normalized else ""
    if not surname:
        return []
    aliases = AuthorAlias.objects.filter(surname_key=surname).select_related("author")
    authors = CanonicalAuthor.objects.all() if authors is None else authors
    variants = [(alias.author, alias.normalized_name) for alias in aliases]
    for author in authors:
        name = normalize_author_name(author.name)
        if name and fold(name.split()[-1]) == surname:
            variants.append((author, name))
    scores = {}
    for author, name in variants:
        score = SequenceMatcher(None, fold(normalized), fold(name)).ratio()
        if score < 0.55:
            continue
        current = scores.get(author.pk)
        if current is None or score > current[0]:
            scores[author.pk] = (score, author)
    return [
        (author, score)
        for score, author in sorted(scores.values(), key=lambda item: (-item[0], item[1].name))[
            :limit
        ]
    ]


def link_catalogue_uses(alias, reviewer, suggestion=None):
    """Apply a reviewed exact alias to all matching raw catalogue names."""
    normalized = alias.normalized_name
    linked = 0
    evidence_urls = {
        item["url"]
        for item in (suggestion.evidence if suggestion else [])
        if isinstance(item, dict) and item.get("url")
    }
    entries = CatalogueEntry.objects.filter(discovery_only=False).only(
        "pk", "url", "author", "authors"
    )
    for entry in entries:
        names = clean_authors((entry.authors or []) + split_authors(entry.author))
        name = next((name for name in names if normalize_author_name(name) == normalized), "")
        if not name and entry.url not in evidence_urls:
            continue
        _, created = CatalogueAuthor.objects.get_or_create(
            entry=entry,
            author=alias.author,
            role=CatalogueAuthor.Role.AUTHOR,
            defaults={
                "source_name": name or alias.name,
                "suggestion": suggestion,
                "reviewed_by": reviewer,
            },
        )
        linked += int(created)
    return linked


def catalogue_author_names(entry):
    if "authors" in entry.metadata_overrides:
        return clean_authors(entry.metadata_overrides["authors"])
    people = [person for person in entry.people.all() if person.role == CatalogueAuthor.Role.AUTHOR]
    replacements = {
        normalize_author_name(person.source_name): person.author.name for person in people
    }
    names = [
        replacements.get(normalize_author_name(name), name)
        for name in entry.authors or split_authors(entry.author)
    ]
    return clean_authors([*names, *(person.author.name for person in people)])


@transaction.atomic
def review_suggestion(
    suggestion,
    action,
    reviewer,
    *,
    author_id="",
    canonical_name="",
    authority_uri="",
    reason="",
    correction_id="",
):
    suggestion = MetadataSuggestion.objects.select_for_update().get(pk=suggestion.pk)
    if (
        suggestion.capture_id
        and suggestion.capture.discovery_only
        or suggestion.entry_id
        and suggestion.entry.discovery_only
    ):
        raise ValueError("This proposal concerns a discovery index, not a readable work.")
    if not isinstance(reason, str) or len(reason) > 4000:
        raise ValueError("Review reason must contain at most 4000 characters.")
    if action not in {"approve", "reject", "reopen", "accept_correction"}:
        raise ValueError("Unknown review decision.")
    if action == "approve" and scoped_author_correction(suggestion) is not None:
        raise ValueError(
            "This captured page has a saved people/roles correction. "
            "The original author proposal cannot be approved as a global alias. "
            "Accept the saved correction to resolve the review, or reject the original proposal."
        )
    previous_status = suggestion.status
    if action == "reopen":
        if suggestion.status == MetadataSuggestion.Status.PENDING:
            return False
        if suggestion.status != MetadataSuggestion.Status.REJECTED:
            raise ValueError(
                "Only rejected suggestions can be reopened; approved facts are not undone."
            )
        if not reason.strip():
            raise ValueError("Enter a reason for reopening this suggestion.")
        # Preserve legacy decisions before replacing the current-state fields.
        if not suggestion.review_events.exists() and suggestion.reviewed_by_id:
            event = MetadataReviewEvent.objects.create(
                suggestion=suggestion,
                reviewer=suggestion.reviewed_by,
                previous_status=MetadataSuggestion.Status.PENDING,
                status=suggestion.status,
                reason="Historical decision recorded before reopening.",
            )
            if suggestion.reviewed_at:
                MetadataReviewEvent.objects.filter(pk=event.pk).update(
                    created_at=suggestion.reviewed_at
                )
        MetadataReviewEvent.objects.create(
            suggestion=suggestion,
            reviewer=reviewer,
            previous_status=previous_status,
            status=MetadataSuggestion.Status.PENDING,
            reason=reason.strip(),
        )
        suggestion.status = MetadataSuggestion.Status.PENDING
        suggestion.reviewed_by = None
        suggestion.reviewed_at = None
        suggestion.save(update_fields=["status", "reviewed_by", "reviewed_at"])
        return True
    if suggestion.status != MetadataSuggestion.Status.PENDING:
        return False
    resolution = None
    if action == "accept_correction":
        from library.profile import get_profile
        from library.services.corrections import digest, extraction, legacy_index_metadata

        resolution = scoped_author_correction(suggestion)
        if resolution is None or str(resolution.pk) != str(correction_id):
            raise ValueError("The saved correction changed or is unavailable. Reload this review.")
        if (
            resolution.source_digest != suggestion.capture.response.get("digest")
            or resolution.adapter_version != get_profile().adapter_version
        ):
            raise ValueError("The saved correction is stale. Revalidate it in the workspace.")
        _, _, body, _ = extraction(suggestion.capture)
        if resolution.original.get("body_digest") != digest(
            str(body)
        ) and not legacy_index_metadata(resolution, body):
            raise ValueError("The extracted body changed. Revalidate the saved correction.")
        suggestion.status = MetadataSuggestion.Status.SUPERSEDED
    elif action == "reject":
        suggestion.status = MetadataSuggestion.Status.REJECTED
    elif action == "approve":
        if suggestion.field == MetadataSuggestion.Field.AUTHOR:
            author = None
            if author_id:
                author = CanonicalAuthor.objects.get(pk=author_id)
            else:
                name = canonical_name.strip() or suggestion.value
                author, _ = CanonicalAuthor.objects.get_or_create(name=name[:500])
            authority_uri = authority_uri.strip()
            if authority_uri:
                try:
                    URLValidator()(authority_uri)
                except ValidationError as exc:
                    raise ValueError("Enter a valid authority record URL.") from exc
                if author.authority_uri and author.authority_uri != authority_uri:
                    raise ValueError("This canonical author already has a different authority URL.")
                if not author.authority_uri:
                    author.authority_uri = authority_uri
                    author.save(update_fields=["authority_uri"])
            normalized = normalize_author_name(suggestion.value)
            if not normalized:
                raise ValueError("The proposed author name cannot be normalized.")
            source_url = suggestion.capture.url if suggestion.capture_id else ""
            alias, _ = AuthorAlias.objects.get_or_create(
                author=author,
                normalized_name=normalized,
                language="",
                defaults={
                    "name": suggestion.value,
                    "surname_key": fold(normalized.split()[-1]),
                    "source_url": source_url,
                    "reviewed_by": reviewer,
                },
            )
            link_catalogue_uses(alias, reviewer, suggestion)
        else:
            if suggestion.entry is None:
                raise ValueError("This suggestion is missing its catalogue entry.")
            entry = suggestion.entry
            from library.services.catalogue_overlays import update_metadata

            entry = CatalogueEntry.objects.select_for_update().get(pk=entry.pk)
            if suggestion.field == MetadataSuggestion.Field.PUBLISHED:
                if (
                    suggestion.date_type == MetadataSuggestion.DateType.PUBLICATION
                    and not entry.metadata_baseline.get("published", entry.published)
                ):
                    update_metadata(entry, {"published": suggestion.value})
                    entry.save()
            elif suggestion.field == MetadataSuggestion.Field.TOPIC:
                topics = entry.metadata_baseline.get("topics", entry.topics)
                topic = entry.metadata_baseline.get("topic", entry.topic)
                update_metadata(
                    entry,
                    {
                        "topics": unique([*(topics or []), suggestion.value]),
                        "topic": topic or suggestion.value,
                    },
                )
                entry.save()
        suggestion.status = MetadataSuggestion.Status.APPROVED
    else:
        raise ValueError("Unknown review decision.")
    suggestion.reviewed_by = reviewer
    suggestion.reviewed_at = timezone.now()
    suggestion.save(update_fields=["status", "reviewed_by", "reviewed_at"])
    MetadataReviewEvent.objects.create(
        suggestion=suggestion,
        reviewer=reviewer,
        previous_status=previous_status,
        status=suggestion.status,
        reason=reason.strip(),
        correction=resolution,
    )
    return True
