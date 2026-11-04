from copy import deepcopy

from django.db import transaction

from library.models import CatalogueEntry, CatalogueOverlayDecision, ContentOrganization
from library.profile import get_profile
from library.services.corrections import (
    CorrectionConflict,
    apply_expected,
    digest,
    extraction,
    latest,
    legacy_index_metadata,
    validate_expected,
)

FIELDS = ("title", "author", "authors", "published", "language", "topic", "topics")


def update_metadata(entry, values):
    """Retain new underlying facts while keeping explicit catalogue overlays visible."""
    baseline = deepcopy(entry.metadata_baseline)
    for field, value in values.items():
        if field in entry.metadata_overrides:
            baseline[field] = deepcopy(value)
        else:
            setattr(entry, field, value)
    entry.metadata_baseline = baseline
    for field, value in entry.metadata_overrides.items():
        setattr(entry, field, deepcopy(value))


@transaction.atomic
def persist_metadata(pk, values):
    entry = CatalogueEntry.objects.select_for_update().get(pk=pk)
    update_metadata(entry, values)
    entry.save()


def state(entry):
    return {
        "values": {field: deepcopy(getattr(entry, field)) for field in FIELDS},
        "overrides": deepcopy(entry.metadata_overrides),
        "baseline": deepcopy(entry.metadata_baseline),
        "decision": entry.overlay_decisions.values_list("pk", flat=True).first(),
    }


def matching_entry(capture):
    entry = (
        CatalogueEntry.objects.select_related("site")
        .filter(site=capture.site, url=capture.url)
        .first()
    )
    if entry is None:
        raise ValueError("No catalogue entry exists for this exact source URL.")
    if entry.site.profile != get_profile().key:
        raise ValueError("Switch to this entry's profile.")
    if entry.discovery_only or capture.discovery_only:
        raise ValueError("Discovery indexes cannot receive readable catalogue metadata.")
    if entry.book_id:
        raise ValueError("This page belongs to a book. Correct the book contents metadata instead.")
    return entry


def proposal(capture, *, undo=False):
    entry = matching_entry(capture)
    previous = entry.overlay_decisions.first()
    if undo:
        if previous is None or previous.undo_of_id:
            raise ValueError("There is no latest catalogue overlay change to undo.")
        correction = previous.correction
        overrides = previous.before["overrides"]
    else:
        correction = latest(capture)
        if correction is None:
            raise ValueError("Save a metadata correction before applying it to the catalogue.")
        source, _, body, _ = extraction(capture)
        if (
            correction.source_digest != capture.response["digest"]
            or correction.adapter_version != get_profile().adapter_version
            or (
                correction.original["body_digest"] != digest(str(body))
                and not legacy_index_metadata(correction, body)
            )
        ):
            raise ValueError("The correction is stale. Revalidate and save it before applying.")
        expected = validate_expected(correction.expected, body, source)
        metadata = expected.get("metadata", {})
        if not set(metadata) & {"title", "people", "dates", "language", "topics"}:
            raise ValueError("This correction has no catalogue metadata overrides.")
        apply_expected(source, None, {"metadata": metadata})
        overrides = {}
        if "title" in metadata:
            overrides["title"] = source.title
        for key, fields in {
            "people": ("author", "authors"),
            "dates": ("published",),
            "language": ("language",),
            "topics": ("topic", "topics"),
        }.items():
            if key in metadata:
                overrides.update({field: source.metadata[field] for field in fields})
    organization = ContentOrganization.objects.filter(entry=entry).first()
    if (
        organization
        and overrides.get("title", organization.specification["title"])
        != (organization.specification["title"])
    ):
        raise ValueError("The title conflicts with reviewed book organization. Correct that first.")
    before = state(entry)
    values = deepcopy(before["values"])
    values.update(before["baseline"])
    values.update(overrides)
    for field, value in values.items():
        limit = CatalogueEntry._meta.get_field(field).max_length
        if limit and len(value) > limit:
            raise ValueError(f"Catalogue {field} exceeds its {limit}-character limit.")
    return {
        "entry": entry,
        "correction": correction,
        "before": before,
        "overrides": overrides,
        "values": values,
        "undo": previous.pk if undo else None,
        "rows": [
            {"field": field, "before": before["values"][field], "after": values[field]}
            for field in FIELDS
        ],
    }


def binding(plan):
    return {
        "entry": plan["entry"].pk,
        "correction": plan["correction"].pk,
        "before": plan["before"],
        "overrides": plan["overrides"],
        "values": plan["values"],
        "undo": plan["undo"],
    }


@transaction.atomic
def commit(capture, reviewer, expected, reason):
    reason = reason.strip()
    if not reason or len(reason) > 2000:
        raise ValueError("Enter a reason of 1-2000 characters.")
    CatalogueEntry.objects.select_for_update().get(pk=expected["entry"])
    plan = proposal(capture, undo=bool(expected["undo"]))
    if binding(plan) != expected:
        raise CorrectionConflict("Catalogue or correction changed after preview. Preview again.")
    entry = plan["entry"]
    baseline = {
        field: deepcopy(entry.metadata_baseline.get(field, getattr(entry, field)))
        for field in plan["overrides"]
    }
    entry.metadata_overrides = deepcopy(plan["overrides"])
    entry.metadata_baseline = baseline
    for field, value in plan["values"].items():
        setattr(entry, field, value)
    entry.save(update_fields=[*FIELDS, "metadata_overrides", "metadata_baseline"])
    return CatalogueOverlayDecision.objects.create(
        entry=entry,
        correction=plan["correction"],
        reviewer=reviewer,
        reason=reason,
        before=plan["before"],
        after=state(entry),
        undo_of_id=plan["undo"],
    )
