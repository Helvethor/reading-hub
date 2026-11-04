"""Explicit human observations, separate from content verification and ML data."""

from copy import deepcopy

from django.db import transaction
from django.db.models import F

from library import versions
from library.models import (
    DocumentDraftBase,
    DocumentEditRevision,
    Rendition,
    ReviewerResult,
    ReviewerRun,
    ReviewerTask,
)
from library.profile import get_profile
from library.services.document_edits import DocumentEditConflict
from library.services.semantic_documents import fingerprint
from library.sources.adapters import adapter_for


def check_base(draft):
    if draft.profile != get_profile().key:
        raise ValueError("Switch to the task's profile before evaluating it.")
    adapter_for(draft.rendition.document.url)
    if (
        fingerprint(draft.document) != draft.document_digest
        or fingerprint(draft.evidence) != draft.evidence_digest
    ):
        raise ValueError("The evaluation starting evidence failed its integrity check.")


def task_binding(draft):
    return {
        "version": 1, "draft": str(draft.pk), "profile": draft.profile,
        "document_digest": draft.document_digest, "evidence_digest": draft.evidence_digest,
        "rendition": draft.rendition_id, "snapshot": draft.evidence["snapshot"],
        "generation_versions": draft.evidence["versions"],
        "created_with_app": versions.APP_VERSION,
    }


def create_task(draft, reviewer, *, title, scope, instructions):
    check_base(draft)
    for label, value, maximum in (
        ("Title", title, 200), ("Scope", scope, 1000), ("Instructions", instructions, 5000),
    ):
        if not isinstance(value, str) or not value.strip() or len(value) > maximum:
            raise ValueError(f"{label} must contain 1-{maximum} characters.")
    return ReviewerTask.objects.create(
        starting_draft=draft, title=title.strip(), scope=scope.strip(),
        instructions=instructions.strip(), binding=task_binding(draft), reviewer=reviewer,
    )


@transaction.atomic
def start_run(task, reviewer, *, practice):
    if type(practice) is not bool:
        raise ValueError("Choose whether this is a practice run.")
    source = task.starting_draft
    check_base(source)
    binding = task_binding(source)
    binding["created_with_app"] = task.binding["created_with_app"]
    if binding != task.binding:
        raise DocumentEditConflict("The task's pinned starting evidence changed.")
    evidence = deepcopy(source.evidence)
    evidence["evaluation_origin"] = {
        "task": task.pk, "starting_draft": str(source.pk),
        "starting_evidence_digest": source.evidence_digest,
        "starting_document_digest": source.document_digest,
    }
    draft = DocumentDraftBase.objects.create(
        rendition=source.rendition, profile=source.profile,
        document=deepcopy(source.document), document_digest=source.document_digest,
        evidence=evidence, evidence_digest=fingerprint(evidence), reviewer=reviewer,
    )
    return ReviewerRun.objects.create(
        task=task, draft=draft, reviewer=reviewer, practice=practice,
        app_version=versions.APP_VERSION,
    )


@transaction.atomic
def record_result(run, reviewer, revision_number, observations):
    if run.reviewer_id != reviewer.pk:
        raise ValueError("Only the reviewer who started this run can record its result.")
    check_base(run.draft)
    Rendition.objects.filter(pk=run.draft.rendition_id).update(id=F("id"))
    if ReviewerResult.objects.filter(run=run).exists():
        raise DocumentEditConflict("This run already has an immutable result. Start another run.")
    if type(revision_number) is not int or revision_number < 0:
        raise ValueError("Choose an exact nonnegative saved revision; zero is the starting base.")
    revision = None
    if revision_number:
        revision = DocumentEditRevision.objects.filter(
            draft=run.draft, revision=revision_number,
        ).first()
        if revision is None:
            raise ValueError("Choose a saved revision from this run's working draft.")
        if fingerprint(revision.document) != revision.document_digest:
            raise ValueError("The result revision failed its integrity check.")
    required = {
        "outcome", "active_minutes", "remaining_errors", "severe_errors",
        "keyboard", "screen_reader", "narrow_screen", "notes",
    }
    if not isinstance(observations, dict) or set(observations) != required:
        raise ValueError("Provide the complete evaluation observations.")
    if observations["outcome"] not in ("completed", "blocked"):
        raise ValueError("Choose completed or blocked.")
    for key in ("active_minutes", "remaining_errors", "severe_errors"):
        value = observations[key]
        if value is not None and (type(value) is not int or not 0 <= value <= 100000):
            raise ValueError("Measurements must be whole numbers from 0 to 100000, or unknown.")
    errors, severe = observations["remaining_errors"], observations["severe_errors"]
    if severe is not None and (errors is None or severe > errors):
        raise ValueError("Severe errors require a total error count and cannot exceed it.")
    for key in ("keyboard", "screen_reader", "narrow_screen"):
        if observations[key] not in ("not_tested", "completed", "blocked"):
            raise ValueError("Record accessibility as not tested, completed or blocked.")
    if (
        not isinstance(observations["notes"], str) or not observations["notes"].strip()
        or len(observations["notes"]) > 5000
    ):
        raise ValueError("Describe the observed outcome and any failures in 1-5000 characters.")
    return ReviewerResult.objects.create(
        run=run, reviewer=reviewer, revision=revision, observations=observations,
        binding={
            "version": 1, "semantics": "reviewer_observations_not_acceptance_or_training_data",
            "task_binding": deepcopy(run.task.binding),
            "task": run.task_id, "draft": str(run.draft_id),
            "evidence_digest": run.draft.evidence_digest,
            "revision": revision_number,
            "document_digest": revision.document_digest if revision else run.draft.document_digest,
            "saved_review": revision.review if revision else None,
            "verified_sections": revision.verified_sections if revision else [],
            "run_app_version": run.app_version, "recorded_with_app": versions.APP_VERSION,
            "practice": run.practice,
        },
    )
