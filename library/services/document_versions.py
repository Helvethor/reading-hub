import uuid

from django.db import transaction
from django.utils import timezone

from library.models import (
    Document,
    DocumentBranch,
    DocumentDraftBase,
    DocumentReaderSelection,
    DocumentVersion,
    Rendition,
)
from library.services.semantic_documents import fingerprint


class ReaderSelectionConflict(ValueError):
    pass


@transaction.atomic
def version_for_rendition(rendition):
    rendition = Rendition.objects.select_related("document", "snapshot").get(pk=rendition.pk)
    if rendition.document_version_id:
        version = rendition.document_version
        if version.document_id != rendition.document_id:
            raise ValueError("The rendition's version identity belongs to another work.")
        return version

    evidence = {
        "kind": "retained-rendition",
        "rendition": rendition.pk,
        "identity": rendition.identity,
        "output_digest": rendition.output_digest,
        "snapshot": rendition.snapshot_id,
        "snapshot_digest": rendition.snapshot.digest,
    }
    version = DocumentVersion.objects.create(
        document_id=rendition.document_id,
        origin=DocumentVersion.Origin.SOURCE_GENERATED,
        ancestry=DocumentVersion.Ancestry.KNOWN,
        source_snapshot=rendition.snapshot,
        content_digest=rendition.output_digest,
        evidence=evidence,
        evidence_digest=fingerprint(evidence),
        created_at=rendition.created_at,
    )
    Rendition.objects.filter(pk=rendition.pk).update(document_version=version)
    return version


@transaction.atomic
def create_working_copy(
    rendition, reviewer, document, evidence, *, profile, parent_version, origin,
    source_snapshot=None, starting_revision=None,
):
    if parent_version and parent_version.document_id != rendition.document_id:
        raise ValueError("The working copy's starting version belongs to another work.")
    if source_snapshot and source_snapshot.document_id != rendition.document_id:
        raise ValueError("The retained source snapshot belongs to another work.")
    if parent_version is None and source_snapshot is None:
        raise ValueError("A working copy needs a verified starting version or source snapshot.")
    draft_id = uuid.uuid4()
    now = timezone.now()
    base_evidence = {
        "kind": "working-copy-base",
        "draft": str(draft_id),
        "document_digest": fingerprint(document),
        "evidence_digest": fingerprint(evidence),
        "source_evidence": {
            key: evidence[key]
            for key in (
                "kind", "rendition", "identity", "output_digest", "snapshot",
                "snapshot_digest", "anchor", "correction_origin", "generation_digest",
            )
            if key in evidence
        },
    }
    version = DocumentVersion.objects.create(
        document_id=rendition.document_id,
        parent=parent_version,
        origin=origin,
        source_snapshot=source_snapshot,
        ancestry=(
            parent_version.ancestry if parent_version else
            DocumentVersion.Ancestry.KNOWN
        ),
        content_digest=fingerprint(document),
        evidence=base_evidence,
        evidence_digest=fingerprint(base_evidence),
        created_at=now,
    )
    draft = DocumentDraftBase.objects.create(
        id=draft_id,
        rendition=rendition,
        profile=profile,
        document=document,
        document_digest=fingerprint(document),
        evidence=evidence,
        evidence_digest=fingerprint(evidence),
        reviewer=reviewer,
        document_version=version,
    )
    DocumentBranch.objects.create(
        document_id=rendition.document_id,
        draft=draft,
        base_version=version,
        starting_version=version if source_snapshot else parent_version,
        starting_revision=starting_revision,
        reviewer=reviewer,
        created_at=now,
    )
    return draft


def version_for_saved_state(draft, number):
    row = draft if number == 0 else draft.revisions.filter(revision=number).first()
    if row is None or row.document_version_id is None:
        raise ValueError("This saved version has no normalized version identity.")
    version = row.document_version
    expected_digest = row.document_digest
    if version.document_id != draft.rendition.document_id:
        raise ValueError("The saved version identity belongs to another work.")
    if version.content_digest != expected_digest:
        raise ValueError("The saved version identity does not match its content.")
    if fingerprint(version.evidence) != version.evidence_digest:
        raise ValueError("The saved version evidence failed its integrity check.")
    return version


@transaction.atomic
def select_reader_target(document, rendition_id, reviewer, expected_rendition_id, reason):
    document = Document.objects.select_for_update().get(pk=document.pk)
    current = document.reader_target()
    current_id = current.pk if current else None
    if current_id != expected_rendition_id:
        raise ReaderSelectionConflict(
            "The reader selection changed. Review the current target before choosing again."
        )
    rendition = Rendition.objects.filter(
        pk=rendition_id, document=document,
    ).first()
    if rendition is None:
        raise ValueError("Choose a reader version belonging to this work.")
    from library.services.document_lineage import node_is_archived

    if node_is_archived(document, f"edition:{rendition.pk}"):
        raise ValueError("Restore this archived version before selecting it for readers.")
    reason = reason.strip() if isinstance(reason, str) else ""
    if not reason or len(reason) > 2000:
        raise ValueError("Explain the reader selection in 1-2000 characters.")
    if current_id == rendition.pk and document.reader_selection_explicit:
        raise ValueError("This version is already the explicitly selected reader target.")
    Document.objects.filter(pk=document.pk).update(
        reader_rendition=rendition,
        reader_selection_explicit=True,
    )
    return DocumentReaderSelection.objects.create(
        document=document,
        previous_rendition=current,
        rendition=rendition,
        reviewer=reviewer,
        reason=reason,
        explicit=True,
    )


@transaction.atomic
def restore_reader_fallback(document, reviewer, expected_rendition_id, reason):
    document = Document.objects.select_for_update().get(pk=document.pk)
    current = document.reader_target()
    current_id = current.pk if current else None
    if current_id != expected_rendition_id:
        raise ReaderSelectionConflict(
            "The reader selection changed. Review the current target before resetting it."
        )
    rendition = document.source_generated_reader_fallback()
    if rendition is None:
        raise ValueError("This work has no source-generated reader version to use as fallback.")
    reason = reason.strip() if isinstance(reason, str) else ""
    if not reason or len(reason) > 2000:
        raise ValueError("Explain the reader fallback change in 1-2000 characters.")
    if current_id == rendition.pk and not document.reader_selection_explicit:
        raise ValueError("The source-generated fallback is already selected.")
    Document.objects.filter(pk=document.pk).update(
        reader_rendition=rendition,
        reader_selection_explicit=False,
    )
    return DocumentReaderSelection.objects.create(
        document=document,
        previous_rendition=current,
        rendition=rendition,
        reviewer=reviewer,
        reason=reason,
        explicit=False,
    )
