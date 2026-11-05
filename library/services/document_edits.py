"""Append-only rendition-based editing foundations, not a publishing API."""

import re
from copy import deepcopy

from bs4 import BeautifulSoup
from django.conf.locale import LANG_INFO
from django.db import transaction
from django.db.models import F

from library import versions
from library.models import DocumentDraftBase, DocumentEditRevision, Rendition
from library.profile import get_profile
from library.services.semantic_documents import (
    SCHEMA_VERSION,
    canonical_document,
    document_issues,
    fingerprint,
)
from library.services.semantic_import import preview_import
from library.sources.adapters import adapter_for


class DocumentEditConflict(ValueError):
    pass


def check_draft_integrity(draft):
    if draft.profile != get_profile().key:
        raise ValueError("Switch to the draft's profile before editing.")
    adapter_for(draft.rendition.document.url)
    if (
        fingerprint(draft.document) != draft.document_digest
        or fingerprint(draft.evidence) != draft.evidence_digest
    ):
        raise ValueError("Generated draft evidence failed its integrity check.")


def saved_state(draft, number):
    if type(number) is not int or number < 0:
        raise ValueError("Choose an exact nonnegative saved version.")
    check_draft_integrity(draft)
    row = draft if number == 0 else draft.revisions.filter(revision=number).first()
    if row is None:
        raise ValueError("That saved version does not exist in this history.")
    if fingerprint(row.document) != row.document_digest:
        raise ValueError("The saved document failed its integrity check.")
    return row


@transaction.atomic
def branch_draft(draft, reviewer, number):
    """Start from an exact saved state, retaining generation and immediate ancestry."""
    row = saved_state(draft, number)
    evidence = deepcopy(draft.evidence)
    origin = evidence.get("correction_origin", {})
    evidence["correction_origin"] = {
        "version": 1, "draft": str(draft.pk), "revision": number,
        "document_digest": row.document_digest, "evidence_digest": draft.evidence_digest,
        "root_draft": origin.get("root_draft", str(draft.pk)),
        "generated_title": origin.get("generated_title", draft.document["title"]),
        "generated_metadata": origin.get("generated_metadata", draft.document["metadata"]),
        "app": versions.APP_VERSION,
        "editorial": row.editorial if number else origin.get("editorial", False),
    }
    # Evaluation membership belongs to the old working copy, not this correction.
    evidence.pop("evaluation_origin", None)
    return DocumentDraftBase.objects.create(
        rendition=draft.rendition, profile=draft.profile,
        document=deepcopy(row.document), document_digest=row.document_digest,
        evidence=evidence, evidence_digest=fingerprint(evidence), reviewer=reviewer,
    )


def validate_editor_metadata(original, submitted):
    if not isinstance(original, dict) or not isinstance(submitted, dict):
        raise ValueError("Document metadata must be an object.")
    result = deepcopy(submitted)
    editable = {
        "author", "author_is_fallback", "authors", "contributors", "subtitle",
        "language", "date_facts", "published", "topics", "topic",
        "content_organization",
    }
    if (
        set(original) - editable != set(submitted) - editable
        or any(
            original[key] != submitted[key]
            for key in set(original) & set(submitted) - editable
        )
    ):
        raise ValueError(
            "Only bibliographic and content organization metadata can be changed here."
        )
    if "content_organization" in result:
        organization = result["content_organization"]
        if (
            not isinstance(organization, dict) or set(organization) != {"book"}
            or type(organization["book"]) is not bool
        ):
            raise ValueError("Content organization requires exactly a boolean book classification.")
    from library.services.corrections import validate_expected

    groups = (
        ("contributors", "people", ("author", "authors", "author_is_fallback")),
        ("date_facts", "dates", ("published",)),
        ("topics", "topics", ("topic",)),
    )
    for field, correction_field, derived in groups:
        if result.get(field) != original.get(field):
            if field not in result:
                raise ValueError(f"Use an empty list to clear {field}.")
            values = result[field]
            validate_expected({"metadata": {correction_field: values}},
                              BeautifulSoup("", "html.parser"))
            for item in values:
                texts = item.values() if isinstance(item, dict) else [item]
                if any(isinstance(text, str) and re.search(r"[\x00-\x1f\x7f]", text)
                       for text in texts):
                    raise ValueError("Bibliographic values cannot contain control characters.")
            if field == "contributors":
                authors = [person["name"] for person in values if person["role"] == "author"]
                changes = {
                    "authors": authors, "author": ", ".join(authors), "author_is_fallback": False,
                }
            elif field == "date_facts":
                changes = {"published": next((
                    date["value"] + (f" / {date['end_value']}" if "end_value" in date else "")
                    for date in values if date["type"] == "publication"
                ), "")}
            else:
                changes = {"topic": ", ".join(values)}
            for key, expected in changes.items():
                if (
                    key in result and result[key] != original.get(key)
                    and result[key] != expected
                ):
                    raise ValueError(f"{key} conflicts with the structured {field} values.")
                result[key] = expected
        else:
            for key in derived:
                if key in {"author", "author_is_fallback"}:
                    continue
                if key == "authors" and result.get("author") != original.get("author"):
                    author = result.get("author", "")
                    if (
                        isinstance(author, str)
                        and result.get(key) == ([author.strip()] if author.strip() else [])
                    ):
                        continue
                if result.get(key) != original.get(key):
                    raise ValueError(f"Change {field}, not its derived {key} value.")
    if (
        result.get("contributors") == original.get("contributors")
        and result.get("author") != original.get("author")
    ):
        author = result.get("author", "")
        if not isinstance(author, str):
            raise ValueError("Author must be text.")
        author = author.strip()
        result["authors"] = [author] if author else []
        if "contributors" in original:
            result["contributors"] = [
                person for person in original["contributors"] if person["role"] != "author"
            ] + ([{"name": author, "source_name": author, "role": "author"}] if author else [])
    for field, limit in (("author", 1000), ("subtitle", 1000)):
        value = result.get(field, "")
        if not isinstance(value, str):
            raise ValueError(f"{field.title()} must be text.")
        value = value.strip()
        if len(value) > limit or re.search(r"[\x00-\x1f\x7f]", value):
            raise ValueError(f"{field.title()} exceeds its text limits.")
        if value:
            result[field] = value
        else:
            result.pop(field, None)
    if "author" in result:
        result["author_is_fallback"] = False
    elif result.get("contributors") != original.get("contributors"):
        result["author_is_fallback"] = False
    elif original.get("author_is_fallback") is True:
        result["author_is_fallback"] = True
    else:
        result.pop("author_is_fallback", None)
    language = result.get("language", "")
    if not isinstance(language, str):
        raise ValueError("Language must be a language code.")
    language = language.strip().replace("_", "-").lower()
    if language and (
        len(language) > 35
        or not re.fullmatch(r"(?:[a-z]{2,3}|und)(?:-[a-z0-9]{1,8})*", language)
        or (language != "und" and language.split("-", 1)[0] not in LANG_INFO)
    ):
        raise ValueError("Choose a recognized language code such as en, en-us, fr or und.")
    if language:
        parts = language.split("-")
        result["language"] = "-".join(
            [parts[0], *(
                part.title() if len(part) == 4 and part.isalpha()
                else part.upper() if (len(part) == 2 and part.isalpha())
                or (len(part) == 3 and part.isdigit())
                else part
                for part in parts[1:]
            )]
        )
    else:
        result.pop("language", None)
    return result


def preview_rendition_import(rendition):
    return preview_import({
        "version": SCHEMA_VERSION,
        "title": rendition.title,
        "metadata": rendition.metadata,
        "html": rendition.html,
    }, binding={
        "rendition": rendition.pk,
        "identity": rendition.identity,
        "output_digest": rendition.output_digest,
        "snapshot": rendition.snapshot_id,
        "snapshot_digest": rendition.snapshot.digest,
        "manifest_digest": fingerprint(rendition.snapshot.manifest),
        "stylesheet_digest": fingerprint(rendition.stylesheet),
        "structure_digest": fingerprint(rendition.structure),
        "warnings_digest": fingerprint(rendition.warnings),
        "assets": list(rendition.assets.order_by("blob_id").values_list("blob_id", flat=True)),
        "versions": {
            "app": rendition.app_version, "adapter": rendition.adapter_version,
            "format": rendition.format_version,
        },
        "profile": get_profile().key,
    })


@transaction.atomic
def create_draft(rendition, reviewer, *, conversion_approval=None):
    """Pin an existing edition exactly; do not claim it is a verified ML target."""
    rendition = Rendition.objects.select_related("snapshot", "document").get(pk=rendition.pk)
    adapter_for(rendition.document.url)
    proposal = preview_rendition_import(rendition)
    if proposal["requires_approval"] and conversion_approval != proposal["approval_digest"]:
        raise DocumentEditConflict(
            "Preview and explicitly approve this exact legacy conversion before creating a draft."
        )
    if conversion_approval is not None and conversion_approval != proposal["approval_digest"]:
        raise DocumentEditConflict("The conversion preview changed. Review the new proposal.")
    document = proposal["document"]
    evidence = {
        "kind": "retained-rendition",
        "rendition": rendition.pk,
        "identity": rendition.identity,
        "output_digest": rendition.output_digest,
        "snapshot": rendition.snapshot_id,
        "snapshot_digest": rendition.snapshot.digest,
        "manifest": rendition.snapshot.manifest,
        "generated_html": rendition.html,
        "structure": rendition.structure,
        "stylesheet": rendition.stylesheet,
        "warnings": rendition.warnings,
        "versions": {
            "app": rendition.app_version, "adapter": rendition.adapter_version,
            "format": rendition.format_version, "document": SCHEMA_VERSION,
        },
        "assets": list(rendition.assets.order_by("blob_id").values_list("blob_id", flat=True)),
        "legacy_application": {
            "state": "already materialized; never reapply to this draft",
            "correction_revision_bindings": "unavailable in historical rendition",
        },
        "import": {
            **proposal["conversion"],
            "approval_digest": proposal["approval_digest"],
            "explicitly_approved": conversion_approval is not None,
        },
    }
    return DocumentDraftBase.objects.create(
        rendition=rendition, profile=get_profile().key, document=document,
        document_digest=fingerprint(document), evidence=evidence,
        evidence_digest=fingerprint(evidence), reviewer=reviewer,
    )


@transaction.atomic
def save_revision(draft, reviewer, document, expected_revision, *,
                  review="partial", verified_sections=None, editorial=None):
    if type(expected_revision) is not int or expected_revision < 0:
        raise ValueError("Provide the exact nonnegative current revision.")
    if (
        not isinstance(review, str) or review not in DocumentEditRevision.Review.values
        or (editorial is not None and type(editorial) is not bool)
    ):
        raise ValueError("Choose an explicit review state and editorial flag.")
    # The existing rendition row serializes even the first save on SQLite.
    draft = DocumentDraftBase.objects.get(pk=draft.pk)
    Rendition.objects.filter(pk=draft.rendition_id).update(id=F("id"))
    if draft.profile != get_profile().key:
        raise ValueError("Switch to the draft's profile before editing.")
    if (
        fingerprint(draft.document) != draft.document_digest
        or fingerprint(draft.evidence) != draft.evidence_digest
    ):
        raise ValueError("Generated draft evidence failed its integrity check.")
    current = draft.revisions.first()
    if (current.revision if current else 0) != expected_revision:
        raise DocumentEditConflict("The document changed. Reload before saving another revision.")
    if current and fingerprint(current.document) != current.document_digest:
        raise ValueError("The previous saved document failed its integrity check.")
    if editorial is None:
        editorial = current.editorial if current else draft.evidence.get(
            "correction_origin", {},
        ).get("editorial", False)
    document = canonical_document(document)
    document["metadata"] = validate_editor_metadata(
        draft.document["metadata"], document["metadata"],
    )
    document = canonical_document(document)
    issues = document_issues(document, set(draft.evidence["assets"]))
    sections = [] if verified_sections is None else verified_sections
    if (
        not isinstance(sections, list)
        or any(not isinstance(value, str) for value in sections)
        or len(sections) != len(set(sections))
        or (review == "sections" and not sections)
        or (review != "sections" and sections)
    ):
        raise ValueError("Section verification requires distinct section IDs and section review.")
    soup = BeautifulSoup(document["html"], "html.parser")
    section_ids = {node["id"] for node in soup.select("section[id]")}
    if not set(sections) <= section_ids:
        raise ValueError("Verify only existing semantic sections.")
    if review != "partial" and issues:
        raise ValueError("Resolve document issues before verifying a document or section.")
    # Each save certifies only its explicitly submitted scope; old approvals
    # are never inherited, including after metadata or relationship changes.
    return DocumentEditRevision.objects.create(
        draft=draft, revision=expected_revision + 1, document=deepcopy(document),
        document_digest=fingerprint(document), review=review,
        verified_sections=sorted(sections), issues=issues, editorial=editorial,
        reviewer=reviewer,
        lineage={
            "version": 1, "draft": str(draft.pk), "revision": expected_revision,
            "document_digest": current.document_digest if current else draft.document_digest,
            "evidence_digest": draft.evidence_digest, "app": versions.APP_VERSION,
        },
    )
