"""Validate an offline, work-separated manifest without changing review data."""

from collections import Counter, defaultdict

from django.db.models import Max

from library.models import CorrectionFeedback, CrawlCapture, SourceCorrection
from library.profile import get_profile
from library.services.corrections import baseline, extraction
from library.services.errors import ImportFailure

MAX_EXAMPLES = 500
SPLITS = {"development", "held_out"}
TASK = "block-type"


def benchmark_report(manifest):
    if (
        not isinstance(manifest, dict)
        or set(manifest) != {"format_version", "task", "examples"}
        or manifest["format_version"] != 1
        or type(manifest["format_version"]) is not int
        or manifest["task"] != TASK
    ):
        raise ValueError("Manifest must declare format_version 1 and task 'block-type'.")
    examples = manifest["examples"]
    if not isinstance(examples, list) or not 1 <= len(examples) <= MAX_EXAMPLES:
        raise ValueError(f"Manifest must contain between 1 and {MAX_EXAMPLES} examples.")

    normalized = []
    capture_ids = set()
    for item in examples:
        required = {"capture_id", "work_key", "split"}
        if (
            not isinstance(item, dict)
            or not required <= set(item)
            or set(item) - (required | {"layout_key"})
            or type(item["capture_id"]) is not int
            or item["capture_id"] <= 0
            or not isinstance(item["split"], str)
            or item["split"] not in SPLITS
            or not isinstance(item["work_key"], str)
            or not item["work_key"].strip()
            or len(item["work_key"]) > 500
            or (
                "layout_key" in item
                and (
                    not isinstance(item["layout_key"], str)
                    or not item["layout_key"].strip()
                    or len(item["layout_key"]) > 250
                )
            )
        ):
            raise ValueError("Each example requires a capture_id, work_key and valid split.")
        if item["capture_id"] in capture_ids:
            raise ValueError(f"Capture {item['capture_id']} appears more than once.")
        capture_ids.add(item["capture_id"])
        normalized_item = {**item, "work_key": item["work_key"].strip()}
        if "layout_key" in item:
            normalized_item["layout_key"] = item["layout_key"].strip()
        normalized.append(normalized_item)
    if {item["split"] for item in normalized} != SPLITS:
        raise ValueError("Benchmark manifest must include both development and held_out splits.")

    profile = get_profile()
    captures = {
        capture.pk: capture
        for capture in CrawlCapture.objects.filter(
            pk__in=capture_ids, site__profile=profile.key
        ).select_related("site")
    }
    missing = capture_ids - captures.keys()
    if missing:
        raise ValueError(
            "Manifest contains missing or non-active-profile captures: "
            + ", ".join(str(pk) for pk in sorted(missing))
        )

    work_splits = defaultdict(set)
    layout_splits = defaultdict(set)
    source_digest_splits = defaultdict(set)
    body_digest_splits = defaultdict(set)
    duplicate_source_counts = Counter()
    duplicate_body_counts = Counter()
    checked = []
    for item in normalized:
        capture = captures[item["capture_id"]]
        work_splits[item["work_key"]].add(item["split"])
        if "layout_key" in item:
            layout_splits[item["layout_key"]].add(item["split"])
        try:
            source, _, body, _ = extraction(capture)
        except (ImportFailure, OSError, ValueError) as exc:
            raise ValueError(f"Capture {capture.pk} cannot be extracted offline: {exc}") from exc
        original = baseline(source, body)
        source_digest = capture.response.get("digest")
        if not isinstance(source_digest, str) or len(source_digest) != 64:
            raise ValueError(f"Capture {capture.pk} has no valid retained-source digest.")
        source_digest_splits[source_digest].add(item["split"])
        duplicate_source_counts[(source_digest, item["split"])] += 1
        if original["blocks"]:
            body_digest_splits[original["body_digest"]].add(item["split"])
            duplicate_body_counts[(original["body_digest"], item["split"])] += 1
        checked.append(
            {
                **item,
                "source_digest": source_digest,
                "adapter_version": profile.adapter_version,
                "body_digest": original["body_digest"],
            }
        )

    leaking_works = sorted(key for key, splits in work_splits.items() if len(splits) > 1)
    leaking_layouts = sorted(key for key, splits in layout_splits.items() if len(splits) > 1)
    leaking_source_digests = sum(
        1 for splits in source_digest_splits.values() if len(splits) > 1
    )
    leaking_body_digests = sum(1 for splits in body_digest_splits.values() if len(splits) > 1)
    if leaking_works or leaking_layouts or leaking_source_digests or leaking_body_digests:
        details = []
        if leaking_works:
            details.append(f"{len(leaking_works)} work group(s)")
        if leaking_layouts:
            details.append(f"{len(leaking_layouts)} layout group(s)")
        if leaking_source_digests:
            details.append(f"{leaking_source_digests} source digest group(s)")
        if leaking_body_digests:
            details.append(f"{leaking_body_digests} body digest group(s)")
        raise ValueError("Split leakage detected: " + ", ".join(details) + ".")

    latest_revision_by_capture = dict(
        SourceCorrection.objects.filter(capture_id__in=capture_ids, profile=profile.key)
        .values("capture_id")
        .annotate(latest_revision=Max("revision"))
        .values_list("capture_id", "latest_revision")
    )
    latest_feedback = {}
    feedback = CorrectionFeedback.objects.filter(
        capture_id__in=capture_ids,
        profile=profile.key,
        source_digest__in={capture.response.get("digest") for capture in captures.values()},
        adapter_version=profile.adapter_version,
        decision__in=[
            CorrectionFeedback.Decision.CORRECTION,
            CorrectionFeedback.Decision.VERIFIED_KEEP,
            CorrectionFeedback.Decision.SUGGESTION_ACCEPTED,
            CorrectionFeedback.Decision.SUGGESTION_REJECTED,
            CorrectionFeedback.Decision.SUGGESTION_REVISED,
            CorrectionFeedback.Decision.ABSTAINED,
            CorrectionFeedback.Decision.SUPERSEDED,
            CorrectionFeedback.Decision.RESET,
        ],
    ).select_related("correction").order_by("created_at", "pk")
    body_digests = {item["capture_id"]: item["body_digest"] for item in checked}
    source_digests = {item["capture_id"]: item["source_digest"] for item in checked}
    for row in feedback:
        if (
            row.source_digest != source_digests[row.capture_id]
            or row.body_digest != body_digests[row.capture_id]
            or row.correction_revision != (latest_revision_by_capture.get(row.capture_id) or 0)
            or (
                row.correction_id
                and (
                    row.correction.capture_id != row.capture_id
                    or row.correction.revision != row.correction_revision
                )
            )
        ):
            continue
        key = (row.capture_id, row.operation)
        latest_feedback[key] = row

    feedback_by_capture = defaultdict(list)
    for (capture_id, operation), row in latest_feedback.items():
        if operation.startswith("block-type:"):
            feedback_by_capture[capture_id].append(row)

    def label_summary(group):
        counts = Counter()
        labeled_captures = set()
        for item in group:
            for row in feedback_by_capture.get(item["capture_id"], []):
                if row.decision == CorrectionFeedback.Decision.CORRECTION:
                    counts["explicit_corrections"] += 1
                    labeled_captures.add(item["capture_id"])
                elif row.decision == CorrectionFeedback.Decision.VERIFIED_KEEP:
                    counts["verified_keeps"] += 1
                    labeled_captures.add(item["capture_id"])
                elif row.decision.startswith("suggestion_") or (
                    row.decision == CorrectionFeedback.Decision.ABSTAINED
                ):
                    counts["proposal_outcomes"] += 1
        return {
            "captures_with_labels": len(labeled_captures),
            "captures_without_labels": len(group) - len(labeled_captures),
            "labels": dict(sorted(counts.items())),
        }

    split_report = {}
    for split in sorted(SPLITS):
        split_examples = [item for item in checked if item["split"] == split]
        summary = label_summary(split_examples)
        work_groups = defaultdict(list)
        layout_groups = defaultdict(list)
        for item in split_examples:
            work_groups[item["work_key"]].append(item)
            if "layout_key" in item:
                layout_groups[item["layout_key"]].append(item)
        split_report[split] = {
            "examples": len(split_examples),
            "works": len({item["work_key"] for item in split_examples}),
            "layouts": len(
                {item["layout_key"] for item in split_examples if "layout_key" in item}
            ),
            "captures_with_adjudicated_block_type_labels": summary["captures_with_labels"],
            "captures_without_adjudicated_block_type_labels": summary["captures_without_labels"],
            "labels": summary["labels"],
            "work_breakdown": [
                {"work_key": key, "examples": len(items), **label_summary(items)}
                for key, items in sorted(work_groups.items())
            ],
            "layout_breakdown": [
                {"layout_key": key, "examples": len(items), **label_summary(items)}
                for key, items in sorted(layout_groups.items())
            ],
        }

    duplicate_source_groups = sum(count > 1 for count in duplicate_source_counts.values())
    duplicate_body_groups = sum(count > 1 for count in duplicate_body_counts.values())
    return {
        "format_version": 1,
        "task": TASK,
        "profile": profile.key,
        "adapter_version": profile.adapter_version,
        "examples_checked": len(checked),
        "splits": split_report,
        "duplicate_source_digest_groups_within_split": duplicate_source_groups,
        "duplicate_body_digest_groups_within_split": duplicate_body_groups,
        "metrics_status": "not_evaluated_no_candidate_predictions",
        "limitations": [
            "Manifest validation does not score extraction accuracy or candidate predictions.",
            "Only exact-binding feedback events are counted; unreviewed fields remain unknown.",
            "A layout key is only as reliable as the maintainer's source-template grouping.",
            "This report reads retained sources and feedback but does not save or fetch data.",
        ],
    }
