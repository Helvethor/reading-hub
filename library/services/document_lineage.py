"""Work-wide, read-only derivation and correction lineage."""

from copy import deepcopy
from datetime import datetime

from django.db import transaction

from library.models import (
    BookMembershipGeneration,
    Document,
    DocumentDraftBase,
    DocumentEditRevision,
    DocumentLineageArchive,
    DocumentLineageRestore,
    DocumentPublication,
    Rendition,
    ReviewerRun,
    Snapshot,
)
from library.services.pipeline import fingerprint as output_fingerprint
from library.services.pipeline import snapshot_digest
from library.services.semantic_documents import fingerprint

MAX_LINEAGE_ELEMENTS = 5000
ARCHIVABLE_TYPES = {"edition", "generation", "history", "revision"}


class LineageLimitExceeded(ValueError):
    pass


class LineageConflict(ValueError):
    pass


def _fingerprint_issue(value, expected, label):
    try:
        actual = fingerprint(value)
    except (TypeError, ValueError, RecursionError) as exc:
        return f"{label} is corrupt; integrity fingerprint could not be calculated: {exc}"
    if actual != expected:
        return f"{label} integrity fingerprint does not match its stored digest."
    return ""


def _bounded(queryset, label):
    rows = list(queryset[:MAX_LINEAGE_ELEMENTS + 1])
    if len(rows) > MAX_LINEAGE_ELEMENTS:
        raise LineageLimitExceeded(
            f"This work exceeds the {MAX_LINEAGE_ELEMENTS}-element lineage display limit. "
            f"Use a narrower history before opening its {label}."
        )
    return rows


def _revision_id(draft_id, revision):
    return f"revision:{draft_id}:{revision}"


def _base_id(draft, drafts=None, seen=None):
    seen = set() if seen is None else seen
    if str(draft.pk) in seen:
        return None
    seen.add(str(draft.pk))
    evidence = draft.evidence if isinstance(draft.evidence, dict) else {}
    origin = evidence.get("correction_origin")
    if isinstance(origin, dict):
        source_id = str(origin.get("draft", ""))
        number = origin.get("revision")
        if type(number) is int and number > 0:
            return _revision_id(source_id, number)
        if type(number) is int and number == 0 and drafts and source_id in drafts:
            return _base_id(drafts[source_id], drafts, seen)
        return None
    if evidence.get("kind") == "fresh-retained-source":
        return f"generation:{draft.pk}"
    return f"edition:{draft.rendition_id}"


def _date_sort(node):
    value = node.get("created_at")
    return value or datetime.min


def _active_archives(document):
    operations = _bounded(
        DocumentLineageArchive.objects.filter(document=document)
        .select_related("reviewer")
        .prefetch_related("restore", "restore__reviewer")
        .order_by("created_at", "pk"),
        "archive records",
    )
    covered, history = set(), []
    for operation in operations:
        try:
            restored = operation.restore
        except DocumentLineageRestore.DoesNotExist:
            restored = None
        scope = operation.scope if isinstance(operation.scope, dict) else {}
        node_ids = scope.get("node_ids", [])
        if not isinstance(node_ids, list) or any(not isinstance(item, str) for item in node_ids):
            raise ValueError(f"Archive operation {operation.pk} has corrupt scope evidence.")
        if restored is None:
            covered.update(node_ids)
        history.append({
            "id": str(operation.pk), "node_ids": node_ids,
            "target_id": scope.get("target_id", ""),
            "preserved_publications": scope.get("preserved_publications", []),
            "reviewer": operation.reviewer.get_username(),
            "created_at": operation.created_at, "reason": operation.reason,
            "restored": restored is not None,
            "restored_by": restored.reviewer.get_username() if restored else "",
            "restored_at": restored.created_at if restored else None,
            "restore_reason": restored.reason if restored else "",
        })
    return covered, history


def archived_node_ids(document):
    covered, _ = _active_archives(document)
    return covered


def archived_draft_ids(document):
    return [
        node_id.removeprefix("history:")
        for node_id in archived_node_ids(document)
        if node_id.startswith("history:")
    ]


def build_lineage(document, *, selected="", filter_name="all"):
    """Build one bounded tree with one query per evidence collection."""
    document = Document.objects.get(pk=document.pk)
    snapshots = _bounded(
        Snapshot.objects.filter(document=document).order_by("fetched_at", "pk"),
        "source snapshots",
    )
    renditions = _bounded(
        Rendition.objects.filter(document=document)
        .select_related("snapshot", "document", "document_version")
        .select_related(
            "document_publication__revision__draft", "document_publication__reviewer",
        )
        .order_by("created_at", "pk"),
        "editions",
    )
    drafts = _bounded(
        DocumentDraftBase.objects.filter(rendition__document=document)
        .exclude(pk__in=ReviewerRun.objects.values("draft_id"))
        .select_related(
            "reviewer", "rendition", "rendition__snapshot", "document_version",
            "branch__starting_version", "branch__base_version",
            "branch__starting_revision",
        )
        .order_by("created_at", "pk"),
        "correction histories",
    )
    revisions = _bounded(
        DocumentEditRevision.objects.filter(draft__rendition__document=document)
        .exclude(draft_id__in=ReviewerRun.objects.values("draft_id"))
        .select_related("draft", "reviewer", "document_version")
        .order_by("draft_id", "revision"),
        "saved revisions",
    )
    generations = _bounded(
        BookMembershipGeneration.objects.filter(rendition__document=document)
        .select_related("rendition", "reviewer")
        .order_by("created_at", "pk"),
        "membership-seeded generations",
    )
    if (
        len(snapshots) + len(renditions) + len(drafts) + len(revisions)
        + len(generations) > MAX_LINEAGE_ELEMENTS
    ):
        raise LineageLimitExceeded(
            f"This work exceeds the {MAX_LINEAGE_ELEMENTS}-element lineage display limit."
        )
    archived_ids, archive_history = _active_archives(document)
    reader_target = document.reader_target()
    reader_target_id = reader_target.pk if reader_target else None

    nodes = {
        f"work:{document.pk}": {
            "id": f"work:{document.pk}", "type": "work", "label": document.title or document.url,
            "created_at": document.created_at, "parent_id": None, "children": [],
            "secondary_ids": [], "details": [], "archived": False,
        }
    }

    def add(node):
        nodes[node["id"]] = {
            "parent_id": None, "children": [], "secondary_ids": [], "details": [],
            "archived": False, "context_only": False, **node,
        }

    for snapshot in snapshots:
        retained_warnings = snapshot.warnings if isinstance(snapshot.warnings, list) else []
        try:
            calculated_digest = snapshot_digest(snapshot.manifest)
            snapshot_issue = (
                "" if calculated_digest == snapshot.digest else
                "Retained snapshot manifest digest does not match its stored digest."
            )
        except (KeyError, TypeError, ValueError, RecursionError) as exc:
            snapshot_issue = f"Retained snapshot manifest is corrupt: {exc}"
        if not isinstance(snapshot.manifest, dict):
            snapshot_issue = "Retained snapshot manifest is not a structured object."
        if not isinstance(snapshot.warnings, list):
            snapshot_issue = (
                f"{snapshot_issue} Retained warning evidence is not a list."
            ).strip()
        pages = snapshot.manifest.get("pages") if isinstance(snapshot.manifest, dict) else None
        add({
            "id": f"snapshot:{snapshot.pk}", "type": "snapshot",
            "label": f"Retained source snapshot {snapshot.pk}",
            "created_at": snapshot.fetched_at, "parent_id": f"work:{document.pk}",
            "snapshot_id": snapshot.pk, "snapshot_digest": snapshot.digest,
            "manifest": snapshot.manifest, "warnings": retained_warnings,
            "integrity_errors": [snapshot_issue] if snapshot_issue else [],
            "details": [
                ("Snapshot digest", snapshot.digest),
                ("Source pages", len(pages) if isinstance(pages, list) else "Unavailable"),
                ("Retained warnings", len(retained_warnings)
                 if isinstance(snapshot.warnings, list) else "Unavailable"),
            ],
        })

    publication_outputs = {}
    latest_revision_by_draft = {}
    for row in revisions:
        key = str(row.draft_id)
        current = latest_revision_by_draft.get(key)
        if current is None or row.revision > current.revision:
            latest_revision_by_draft[key] = row
    snapshot_siblings = {}
    generations_by_rendition = {}
    for generation in generations:
        generations_by_rendition.setdefault(generation.rendition_id, []).append(generation)
    for rendition in renditions:
        snapshot_siblings.setdefault(rendition.snapshot_id, []).append(rendition)
        try:
            publication = rendition.document_publication
        except DocumentPublication.DoesNotExist:
            publication = None
        if publication:
            publication_outputs[(str(publication.revision.draft_id),
                                 publication.revision.revision)] = rendition.pk
        parent_id = (
            _revision_id(publication.revision.draft_id, publication.revision.revision)
            if publication else f"snapshot:{rendition.snapshot_id}"
        )
        details = [
            ("Edition", rendition.pk),
            ("Snapshot", rendition.snapshot_id),
            ("Snapshot digest", rendition.snapshot.digest),
            ("Output digest", rendition.output_digest),
            ("Application", rendition.app_version),
            ("Adapter", rendition.adapter_version),
            ("Formatting", rendition.format_version),
            ("Generation input policy", "Published from a saved revision" if publication else
             "Not recorded for this historical generation"),
        ]
        if publication:
            latest_revision = latest_revision_by_draft.get(
                str(publication.revision.draft_id),
            )
            latest_revision_number = latest_revision.revision if latest_revision else 0
            details.extend([
                ("Published from", f"{publication.revision.draft_id} revision "
                 f"{publication.revision.revision}"),
                ("Publication preview digest", publication.preview_digest),
                ("Branch's latest saved version", latest_revision_number),
            ])
        version = rendition.document_version if rendition.document_version_id else None
        if version:
            details.extend([
                ("Content version identity", version.pk),
                ("Content origin", version.get_origin_display()),
                ("Version ancestry", version.get_ancestry_display()),
            ])
        generation_issues = []
        for generation in generations_by_rendition.get(rendition.pk, []):
            binding = generation.binding if isinstance(generation.binding, dict) else {}
            try:
                if fingerprint(generation.binding) != generation.binding_digest:
                    generation_issues.append(
                        f"Membership generation {generation.pk} binding digest does not match."
                    )
            except (TypeError, ValueError, RecursionError) as exc:
                generation_issues.append(
                    f"Membership generation {generation.pk} binding is corrupt: {exc}"
                )
            members = binding.get("membership")
            sources = binding.get("sources")
            assets = binding.get("assets")
            details.extend([
                ("Membership generation", generation.pk),
                ("Membership binding digest", generation.binding_digest),
                ("Bound member URLs", len(members) if isinstance(members, list) else "Unavailable"),
                ("Bound retained pages", len(sources) if isinstance(sources, dict)
                 else "Unavailable"),
                ("Bound assets", len(assets) if isinstance(assets, dict) else "Unavailable"),
                ("Generation reviewer", generation.reviewer.get_username()),
                ("Generation reason", generation.reason),
            ])
        try:
            output_parts = [
                rendition.html, rendition.structure, rendition.metadata,
                rendition.title, rendition.stylesheet,
            ]
            calculated_output_digests = {
                fingerprint(output_parts),
                output_fingerprint(output_parts),
            }
            rendition_issue = (
                "" if rendition.output_digest in calculated_output_digests else
                "Edition output fingerprint does not match its stored digest."
            )
        except (TypeError, ValueError, RecursionError) as exc:
            rendition_issue = f"Edition evidence is corrupt: {exc}"
        add({
            "id": f"edition:{rendition.pk}", "type": "publication" if publication else "edition",
            "label": (
                f"Published edition {rendition.pk}: {rendition.title}" if publication else
                f"Generated edition {rendition.pk}: {rendition.title}"
            ),
            "created_at": publication.created_at if publication else rendition.created_at,
            "reviewer": publication.reviewer.get_username() if publication else "",
            "parent_id": parent_id, "rendition_id": rendition.pk,
            "reader_url": f"/versions/{rendition.pk}/",
            "pdf_url": f"/versions/{rendition.pk}/download.pdf",
            "publication": bool(publication), "snapshot_id": rendition.snapshot_id,
            "version_id": version.pk if version else None,
            "reader_target": reader_target_id == rendition.pk,
            "snapshot_digest": rendition.snapshot.digest,
            "input_policy": "Not recorded for this historical generation",
            "unknown_ancestry": (
                "The generation input policy and any earlier correction ancestry were not "
                "recorded for this edition."
            ) if not publication else "",
            "integrity_errors": (
                ([rendition_issue] if rendition_issue else []) + generation_issues
            ),
            "details": details,
            **({
                "publication_draft_id": str(publication.revision.draft_id),
                "publication_root_rendition_id": publication.revision.draft.rendition_id,
                "publication_revision_number": publication.revision.revision,
                "publication_latest_revision_number": latest_revision_number,
                "publication_is_latest": (
                    latest_revision is not None
                    and latest_revision.document_version_id
                    == publication.revision.document_version_id
                ),
                "publication_history_archived": (
                    f"history:{publication.revision.draft_id}" in archived_ids
                ),
            } if publication else {}),
        })
        if publication:
            nodes[f"edition:{rendition.pk}"]["secondary_ids"].append(
                f"snapshot:{rendition.snapshot_id}"
            )

    draft_by_id = {str(draft.pk): draft for draft in drafts}
    revision_rows = {
        (str(row.draft_id), row.revision): row for row in revisions
    }
    version_node_ids = {}
    for draft in drafts:
        if draft.document_version_id:
            evidence = draft.evidence if isinstance(draft.evidence, dict) else {}
            node_id = (
                f"generation:{draft.pk}"
                if evidence.get("kind") == "fresh-retained-source"
                and not isinstance(evidence.get("correction_origin"), dict)
                else f"history:{draft.pk}"
            )
            version_node_ids.setdefault(draft.document_version_id, node_id)
    for row in revisions:
        if row.document_version_id:
            version_node_ids.setdefault(
                row.document_version_id, _revision_id(str(row.draft_id), row.revision),
            )
    for rendition in renditions:
        if rendition.document_version_id:
            version_node_ids.setdefault(
                rendition.document_version_id, f"edition:{rendition.pk}",
            )

    def normalized_parent_id(version):
        if not version.parent_id:
            return None
        return version_node_ids.get(version.parent_id)

    for draft in drafts:
        evidence = draft.evidence if isinstance(draft.evidence, dict) else {}
        draft_integrity = [
            issue for issue in (
                _fingerprint_issue(draft.document, draft.document_digest, "Draft document"),
                _fingerprint_issue(draft.evidence, draft.evidence_digest, "Draft evidence"),
            ) if issue
        ]
        if evidence.get("kind") == "fresh-retained-source":
            expected_anchor = {
                "rendition": draft.rendition_id, "identity": draft.rendition.identity,
                "output_digest": draft.rendition.output_digest,
                "snapshot": draft.rendition.snapshot_id,
                "snapshot_digest": draft.rendition.snapshot.digest,
            }
            if evidence.get("anchor") != expected_anchor:
                draft_integrity.append(
                    "Fresh-generation anchor does not match the retained edition evidence."
                )
            if (
                evidence.get("snapshot") != draft.rendition.snapshot_id
                or evidence.get("snapshot_digest") != draft.rendition.snapshot.digest
            ):
                draft_integrity.append(
                    "Fresh-generation snapshot binding does not match its retained edition."
                )
        legacy_application = evidence.get("legacy_application")
        if not isinstance(legacy_application, dict):
            legacy_application = {}
        if evidence.get("kind") == "retained-rendition" and (
            evidence.get("rendition") != draft.rendition_id
            or evidence.get("snapshot") != draft.rendition.snapshot_id
            or evidence.get("snapshot_digest") != draft.rendition.snapshot.digest
        ):
            draft_integrity.append(
                "Correction starting edition binding conflicts with its retained evidence."
            )
        if evidence.get("kind") == "fresh-retained-source" and not isinstance(
            evidence.get("correction_origin"), dict
        ):
            snapshot_id = evidence.get("snapshot")
            anchor_id = (
                f"snapshot:{snapshot_id}"
                if isinstance(snapshot_id, int) and f"snapshot:{snapshot_id}" in nodes else None
            )
            input_policy = evidence.get("input_policy", "Unknown")
            add({
                "id": f"generation:{draft.pk}", "type": "generation",
                "label": f"Fresh retained-source generation for history {draft.pk}",
                "created_at": draft.created_at, "reviewer": draft.reviewer.get_username(),
                "parent_id": anchor_id or f"work:{document.pk}",
                "rendition_id": draft.rendition_id,
                "draft_id": str(draft.pk), "snapshot_id": snapshot_id,
                "version_id": draft.document_version_id,
                "source_snapshot_id": (
                    draft.document_version.source_snapshot_id
                    if draft.document_version_id else None
                ),
                "input_policy": input_policy,
                "unknown_ancestry": "" if anchor_id else
                "Retained snapshot ancestry is missing or belongs to another work.",
                "details": [
                    ("Generation kind", evidence.get("kind")),
                    ("Input policy", input_policy),
                    ("Snapshot", snapshot_id),
                    ("Snapshot digest", evidence.get("snapshot_digest", "Unavailable")),
                    ("Content version identity", draft.document_version_id or "Unavailable"),
                    ("Saved edits replayed", legacy_application.get(
                        "saved_editor_revisions", "Not recorded")),
                    ("Profile digest", evidence.get("profile_digest", "Unavailable")),
                    ("Evidence digest", draft.evidence_digest),
                ],
                "integrity_errors": draft_integrity,
            })

        origin = evidence.get("correction_origin")
        if isinstance(origin, dict):
            parent_draft_id = str(origin.get("draft", ""))
            parent_draft = draft_by_id.get(parent_draft_id)
            revision_number = origin.get("revision")
            parent_row = None
            if type(revision_number) is int and revision_number > 0:
                parent_id = _revision_id(parent_draft_id, revision_number)
                parent_row = revision_rows.get((parent_draft_id, revision_number))
            elif type(revision_number) is int and revision_number == 0 and parent_draft:
                parent_id = _base_id(parent_draft, draft_by_id)
            else:
                parent_id = None
            parent_base_row = (
                revision_rows.get((parent_draft_id, int(parent_id.rsplit(":", 1)[-1])))
                if parent_id and parent_id.startswith("revision:") else None
            )
            expected_document_digest = (
                parent_row.document_digest if parent_row else
                parent_base_row.document_digest if parent_base_row else
                parent_draft.document_digest if parent_draft and revision_number == 0 else None
            )
            missing_parent = (
                not parent_draft or parent_id is None or
                (type(revision_number) is int and revision_number > 0 and parent_row is None)
            )
            unknown = ""
            if not missing_parent and (
                origin.get("document_digest") != expected_document_digest
                or origin.get("evidence_digest") != parent_draft.evidence_digest
            ):
                missing_parent = True
                unknown = (
                    "Unknown historical ancestry: the correction starting-base digests "
                    "conflict with the referenced revision."
                )
            elif missing_parent:
                unknown = (
                    "Unknown historical ancestry: the exact correction starting revision is "
                    "missing or its evidence is unavailable."
                )
        else:
            parent_id = _base_id(draft)
            missing_parent = parent_id not in nodes
            unknown = (
                "Unknown historical ancestry: the correction starting edition is unavailable."
            ) if missing_parent else ""
            if legacy_application.get("correction_revision_bindings"):
                unknown = (
                    "Earlier correction ancestry is unknown; this history is pinned to the "
                    "retained edition shown, and no earlier revision is inferred."
                )
        base_version = (
            draft.document_version if draft.document_version_id else None
        )
        if base_version:
            branch = getattr(draft, "branch", None)
            normalized_start = None
            if branch:
                if branch.starting_revision_id:
                    normalized_start = _revision_id(
                        branch.starting_revision.draft_id,
                        branch.starting_revision.revision,
                    )
                elif branch.starting_version_id:
                    normalized_start = version_node_ids.get(branch.starting_version_id)
            if base_version.ancestry == "unknown" or (branch and not normalized_start):
                parent_id = f"work:{document.pk}"
                missing_parent = True
                unknown = (
                    "Unknown historical ancestry: the normalized version record could not "
                    "verify its exact starting point."
                )
            elif normalized_start:
                parent_id = normalized_start
                missing_parent = normalized_start not in nodes and not normalized_start.startswith(
                    ("revision:", "history:", "generation:", "edition:")
                )
                if missing_parent:
                    parent_id = f"work:{document.pk}"
            elif not base_version.source_snapshot_id:
                parent_id = f"work:{document.pk}"
                missing_parent = True
                unknown = (
                    "Unknown historical ancestry: the normalized version has no exact "
                    "starting version or retained source binding."
                )
        add({
            "id": f"history:{draft.pk}", "type": "history",
            "label": f"Correction history {str(draft.pk)[:8]}",
            "created_at": draft.created_at, "reviewer": draft.reviewer.get_username(),
            "parent_id": parent_id if not missing_parent else f"work:{document.pk}",
            "draft_id": str(draft.pk), "rendition_id": draft.rendition_id,
            "integrity_errors": draft_integrity,
            "base_title": (
                f"Starting from {parent_id}" if parent_id else "Starting ancestry unknown"
            ),
            "unknown_ancestry": unknown,
            "details": [
                ("Starting edition", draft.rendition_id),
                ("Base document digest", draft.document_digest),
                ("Evidence digest", draft.evidence_digest),
                ("Normalized version identity", base_version.pk if base_version else
                 "Unavailable in historical evidence"),
                ("Version origin", base_version.get_origin_display() if base_version else
                 "Unmapped"),
                ("Version ancestry", base_version.get_ancestry_display() if base_version else
                 "Unknown"),
                ("Starting base", origin or (
                    "Fresh retained-source generation" if evidence.get("kind") ==
                    "fresh-retained-source" else "Pinned edition; earlier history unknown"
                )),
            ],
        })

    previous_digest = {}
    previous_document = {}
    latest_revision = {}
    for row in revisions:
        draft_key = str(row.draft_id)
        latest_revision[draft_key] = max(latest_revision.get(draft_key, 0), row.revision)
    for revision in revisions:
        draft_id = str(revision.draft_id)
        before_document = previous_document.get(draft_id, revision.draft.document)
        before_html = before_document.get("html") if isinstance(before_document, dict) else None
        current_document = revision.document
        current_html = current_document.get("html") if isinstance(current_document, dict) else None
        lineage = revision.lineage if isinstance(revision.lineage, dict) else {}
        expected_parent_revision = revision.revision - 1
        expected_parent = (
            revision.draft if expected_parent_revision == 0 else
            revision_rows.get((draft_id, expected_parent_revision))
        )
        parent_id = f"history:{draft_id}"
        ancestry_unknown = ""
        revision_integrity = [
            issue for issue in (
                _fingerprint_issue(
                    revision.document, revision.document_digest,
                    f"Saved revision {revision.revision} document",
                ),
                "Saved document is not a structured object."
                if not isinstance(revision.document, dict) else "",
            ) if issue
        ]
        if not lineage:
            ancestry_unknown = (
                "Unknown historical ancestry: the exact preceding revision digest was not "
                "recorded. This version is shown in its history without a claimed parent."
            )
            parent_id = f"work:{document.pk}"
        elif not all(key in lineage for key in ("draft", "revision", "document_digest",
                                                 "evidence_digest")):
            ancestry_unknown = (
                "Unknown historical ancestry: this revision has incomplete parent bindings."
            )
            parent_id = f"work:{document.pk}"
        elif expected_parent is None:
            revision_integrity.append(
                f"Saved revision {revision.revision} names an unavailable predecessor."
            )
            ancestry_unknown = (
                "Unknown historical ancestry: the expected preceding saved revision is absent."
            )
            parent_id = f"work:{document.pk}"
        else:
            expected_digest = expected_parent.document_digest
            if (
                lineage["draft"] != draft_id
                or type(lineage["revision"]) is not int
                or lineage["revision"] != expected_parent_revision
                or lineage["document_digest"] != expected_digest
                or lineage["evidence_digest"] != revision.draft.evidence_digest
            ):
                revision_integrity.append(
                    f"Saved revision {revision.revision} parent bindings conflict with "
                    "the immutable sequence."
                )
                ancestry_unknown = (
                    "Unknown historical ancestry: recorded parent bindings conflict with "
                    "the saved history."
                )
                parent_id = f"work:{document.pk}"
            else:
                parent_id = (
                    f"history:{draft_id}" if expected_parent_revision == 0 else
                    _revision_id(draft_id, expected_parent_revision)
                )
        before_digest = previous_digest.get(draft_id, revision.draft.document_digest)
        if not isinstance(current_document, dict):
            change_kind = "Saved document evidence is malformed"
        elif ancestry_unknown:
            change_kind = (
                "Content unchanged; exact parent unknown" if before_html == current_html else
                "Content differs; exact parent unknown"
            )
        elif before_html != current_html:
            change_kind = "Content edit"
        elif before_digest != revision.document_digest:
            change_kind = "Metadata-only change"
        else:
            change_kind = "Review-only; content unchanged"
        version = revision.document_version if revision.document_version_id else None
        prior_version_id = (
            expected_parent.document_version_id if expected_parent else None
        )
        if version and version.pk != prior_version_id:
            normalized_parent = normalized_parent_id(version)
            if version.ancestry == "known" and normalized_parent:
                parent_id = normalized_parent
            else:
                parent_id = f"work:{document.pk}"
                ancestry_unknown = (
                    "Unknown historical ancestry: the normalized saved version has no "
                    "verified exact parent."
                )
        previous_digest[draft_id] = revision.document_digest
        previous_document[draft_id] = current_document
        add({
            "id": _revision_id(draft_id, revision.revision), "type": "revision",
            "label": (
                f"Saved revision {revision.revision} — {change_kind}"
            ),
            "created_at": revision.created_at, "reviewer": revision.reviewer.get_username(),
            "parent_id": parent_id, "draft_id": draft_id,
            "revision_number": revision.revision,
            "rendition_id": revision.draft.rendition_id,
            "review": revision.get_review_display(), "review_code": revision.review,
            "verified_sections": revision.verified_sections, "issues": revision.issues,
            "content_changed": before_html != current_html,
            "change_kind": change_kind, "editorial": revision.editorial,
            "integrity_errors": revision_integrity,
            "publication_id": publication_outputs.get((draft_id, revision.revision)),
            "version_id": version.pk if version else None,
            "latest": latest_revision.get(draft_id) == revision.revision,
            "unknown_ancestry": ancestry_unknown,
            "details": [
                ("Revision", revision.revision),
                ("Reviewer", revision.reviewer.get_username()),
                ("Review scope", revision.get_review_display()),
                ("Verified sections", revision.verified_sections),
                ("Unresolved issues", revision.issues),
                ("Change kind", change_kind),
                ("Editorial changes", revision.editorial),
                ("Document digest", revision.document_digest),
                ("Evidence digest", revision.lineage.get("evidence_digest", "Unavailable")
                 if isinstance(revision.lineage, dict) else "Corrupt revision lineage"),
                ("Content version identity", version.pk if version else "Unavailable"),
                ("Version origin", version.get_origin_display() if version else "Unmapped"),
                ("Version ancestry", version.get_ancestry_display() if version else "Unknown"),
            ],
        })

    renditions_by_snapshot = {}
    fresh_generations_by_snapshot = {}
    for node in nodes.values():
        if node["type"] in {"edition", "publication"}:
            renditions_by_snapshot.setdefault(node.get("snapshot_id"), []).append(node)
        elif node["type"] == "generation":
            fresh_generations_by_snapshot.setdefault(node.get("snapshot_id"), []).append(node)
    root_id = f"work:{document.pk}"
    for start_id in tuple(nodes):
        chain, positions, current_id = [], {}, start_id
        while current_id in nodes and current_id != root_id:
            if current_id in positions:
                cycle = chain[positions[current_id]:]
                broken_id = min(cycle)
                nodes[broken_id]["parent_id"] = root_id
                for cycle_id in cycle:
                    cycle_node = nodes[cycle_id]
                    cycle_node["unknown_ancestry"] = (
                        "Unknown historical ancestry: the recorded lineage contains a cycle."
                    )
                    cycle_node.setdefault("integrity_errors", []).append(
                        "Lineage ancestry cycle detected; this edge is shown as unresolved."
                    )
                break
            positions[current_id] = len(chain)
            chain.append(current_id)
            current_id = nodes[current_id].get("parent_id")

    for node in nodes.values():
        parent_id = node["parent_id"]
        if parent_id and parent_id in nodes:
            nodes[parent_id]["children"].append(node["id"])
        elif parent_id and parent_id not in nodes:
            node["unknown_ancestry"] = (
                "Unknown historical ancestry: the recorded parent element is unavailable."
            )
            node["parent_id"] = f"work:{document.pk}"
        for secondary_id in node.get("secondary_ids", []):
            if secondary_id not in nodes:
                node.setdefault("warnings", []).append(
                    f"Secondary evidence {secondary_id} is unavailable."
                )

    history_by_node = {}
    for operation in archive_history:
        for node_id in operation["node_ids"]:
            history_by_node.setdefault(node_id, []).append(operation)
            if node_id not in nodes:
                nodes[f"work:{document.pk}"].setdefault("integrity_errors", []).append(
                    f"Archive operation {operation['id']} references unavailable element "
                    f"{node_id}."
                )
    for node in nodes.values():
        node["archived"] = node["id"] in archived_ids
        node["archive_history"] = history_by_node.get(node["id"], [])
    for node in nodes.values():
        node["children"].sort(key=lambda child_id: (
            _date_sort(nodes[child_id]), nodes[child_id]["label"].casefold()
        ))
        node["secondary_links"] = [
            {"id": item, "label": nodes[item]["label"]}
            for item in node.get("secondary_ids", []) if item in nodes
        ]
        if node["type"] == "snapshot":
            node["related_editions"] = [
                {"id": sibling["id"], "label": sibling["label"],
                 "rendition_id": sibling["rendition_id"], "reader_url": sibling["reader_url"],
                 "archived": sibling["archived"]}
                for sibling in renditions_by_snapshot.get(node["snapshot_id"], [])
                if sibling["type"] == "edition"
            ]
            node["related_generations"] = [
                {"id": sibling["id"], "label": sibling["label"],
                 "rendition_id": sibling["rendition_id"], "archived": sibling["archived"]}
                for sibling in fresh_generations_by_snapshot.get(node["snapshot_id"], [])
            ]

    root_id = f"work:{document.pk}"
    selection_error = ""
    if selected and selected not in nodes:
        selection_error = (
            "The requested lineage element is missing from this work. Showing the work root "
            "without substituting another element."
        )
    if not selected or selected not in nodes:
        selected = root_id

    def matches(node):
        if filter_name == "publications":
            return node["type"] == "publication"
        if filter_name == "corrections":
            return node["type"] in {"history", "revision"} and not node["archived"]
        if filter_name == "generations":
            return node["type"] in {"edition", "generation"}
        if filter_name == "archived":
            return node["archived"]
        return node["id"] == root_id or not node["archived"]

    included = {root_id}

    def include_matches(node_id):
        node = nodes[node_id]
        if matches(node):
            included.add(node_id)
        for child_id in node["children"]:
            include_matches(child_id)

    include_matches(root_id)
    for node_id in tuple(included):
        parent_id = nodes[node_id]["parent_id"]
        while parent_id:
            included.add(parent_id)
            parent_id = nodes[parent_id]["parent_id"]
    selected_path_id = selected
    while selected_path_id:
        included.add(selected_path_id)
        selected_path_id = nodes[selected_path_id]["parent_id"]

    def projected(node_id):
        if node_id not in included:
            return None
        node = deepcopy(nodes[node_id])
        node["context_only"] = node_id not in {root_id} and not matches(nodes[node_id])
        node["children"] = [
            child for child_id in nodes[node_id]["children"]
            if (child := projected(child_id)) is not None
        ]
        return node

    tree = projected(root_id)
    selected_node = deepcopy(nodes[selected])
    selected_node["context_only"] = selected != root_id and not matches(nodes[selected])
    selected_path = []
    path_node = nodes[selected]
    while path_node:
        selected_path.append(path_node["id"])
        parent_id = path_node["parent_id"]
        path_node = nodes.get(parent_id) if parent_id else None
    return {
        "document": document, "tree": tree, "nodes": nodes,
        "selected": selected_node, "filter_name": filter_name,
        "selected_path": selected_path,
        "selection_error": selection_error,
        "archive_history": archive_history,
        "archive_digest": fingerprint({
            "nodes": [
                list(item) for item in sorted(
                    (node_id, node["type"], node["parent_id"])
                    for node_id, node in nodes.items()
                )
            ],
            "active_archives": sorted(
                operation["id"] for operation in archive_history if not operation["restored"]
            ),
            "archived_ids": sorted(archived_ids),
        }),
    }


def archive_impact(lineage, node_id):
    nodes = lineage["nodes"]
    target = nodes.get(node_id)
    if not target or target["type"] not in ARCHIVABLE_TYPES:
        raise LineageConflict("Choose a correction branch or generation to archive.")
    if target["archived"]:
        raise LineageConflict(
            "This element is already covered by an archive. Restore that operation first."
        )
    scope_ids, descendant_ids = set(), set()

    def walk(current_id):
        current = nodes[current_id]
        if current_id != node_id:
            descendant_ids.add(current_id)
        if current["type"] in ARCHIVABLE_TYPES:
            scope_ids.add(current_id)
        for child_id in current["children"]:
            walk(child_id)

    walk(node_id)
    if not scope_ids:
        raise LineageConflict("The selected history has no archivable lineage elements.")
    preserved = [
        nodes[item] for item in sorted(descendant_ids)
        if nodes[item]["type"] == "publication"
    ]
    siblings = []
    if target.get("snapshot_id"):
        siblings = [
            node for node in nodes.values()
            if node.get("snapshot_id") == target["snapshot_id"]
            and node["id"] != node_id and node["type"] in {"edition", "generation"}
        ]
    preview = {
        "target": target, "scope_ids": sorted(scope_ids),
        "affected": [nodes[item] for item in sorted(scope_ids)],
        "preserved_publications": preserved, "surviving_siblings": siblings,
    }
    preview["digest"] = fingerprint({
        "lineage": lineage["archive_digest"], "target": node_id,
        "scope": preview["scope_ids"],
        "preserved_publications": sorted(item["id"] for item in preserved),
        "surviving_siblings": sorted(item["id"] for item in siblings),
    })
    return preview


@transaction.atomic
def archive_lineage(document, node_id, reviewer, preview_digest, reason):
    document = Document.objects.select_for_update().get(pk=document.pk)
    if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > 2000:
        raise LineageConflict("Provide an archival reason of 1–2000 characters.")
    lineage = build_lineage(document, selected=node_id)
    preview = archive_impact(lineage, node_id)
    if preview_digest != preview["digest"]:
        raise LineageConflict("The lineage changed after preview. Review the impact again.")
    return DocumentLineageArchive.objects.create(
        document=document,
        scope={
            "version": 1, "target_id": node_id,
            "node_ids": preview["scope_ids"],
            "preserved_publications": [item["id"] for item in preview["preserved_publications"]],
            "surviving_siblings": [item["id"] for item in preview["surviving_siblings"]],
            "preview_digest": preview["digest"],
        },
        reason=reason.strip(), reviewer=reviewer,
    )


@transaction.atomic
def restore_archive(document, archive_id, reviewer, reason=""):
    document = Document.objects.select_for_update().get(pk=document.pk)
    operation = DocumentLineageArchive.objects.filter(
        document=document, pk=archive_id
    ).select_related("reviewer").first()
    if operation is None:
        raise LineageConflict("The selected archive record does not belong to this work.")
    if hasattr(operation, "restore"):
        raise LineageConflict("This archive operation has already been restored.")
    if not isinstance(reason, str) or len(reason.strip()) > 2000:
        raise LineageConflict("Restore reason must be 2000 characters or fewer.")
    from library.models import DocumentLineageRestore

    return DocumentLineageRestore.objects.create(
        archive=operation, reviewer=reviewer, reason=reason.strip(),
    )


def node_is_archived(document, node_id):
    return node_id in archived_node_ids(document)
