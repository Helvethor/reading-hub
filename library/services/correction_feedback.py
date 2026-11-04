"""Capture-bound, append-only reviewer feedback for future offline evaluation."""

from library.models import CorrectionFeedback
from library.profile import get_profile
from library.services.corrections import baseline, extraction


def operation_values(expected, original):
    blocks = {block["index"]: block for block in original["blocks"]}
    values = {}
    for edit in expected.get("blocks", []):
        if edit["action"] != "exclude":
            original_tag = blocks[edit["index"]]["tag"]
            if edit["action"] == original_tag:
                continue
            values[f"block-type:{edit['index']}"] = edit
    for pair in expected.get("heading_numbers", []):
        values[f"heading-number:{pair['heading']}"] = pair
    for edit in expected.get("presentation", []):
        values[f"presentation:{edit['index']}"] = edit
    return values


def record_correction_revision(correction, previous):
    """Record only decisions made by a local reviewer, never dataset imports."""
    current_values = operation_values(correction.expected, correction.original)
    same_evidence = (
        previous
        and all(
            getattr(previous, field) == getattr(correction, field)
            for field in ("profile", "source_digest", "adapter_version")
        )
        and previous.original["body_digest"] == correction.original["body_digest"]
    )
    previous_values = (
        operation_values(previous.expected, previous.original) if same_evidence else {}
    )
    common = {
        "capture": correction.capture,
        "correction": correction,
        "reviewer": correction.reviewer,
        "profile": correction.profile,
        "correction_revision": correction.revision,
        "source_digest": correction.source_digest,
        "adapter_version": correction.adapter_version,
        "body_digest": correction.original["body_digest"],
    }
    events = [
        CorrectionFeedback(
            **common,
            operation=operation,
            decision=CorrectionFeedback.Decision.CORRECTION,
            value=value,
        )
        for operation, value in current_values.items()
    ]
    events.extend(
        CorrectionFeedback(
            **common,
            operation=operation,
            decision=CorrectionFeedback.Decision.SUPERSEDED,
            value=value,
        )
        for operation, value in previous_values.items()
        if operation not in current_values
    )
    if not any(operation.startswith("block-type:") for operation in current_values):
        events.append(
            CorrectionFeedback(
                **common,
                operation="block-type:*",
                decision=CorrectionFeedback.Decision.RESET,
                value={},
            )
        )
    if any(operation.startswith("heading-number:") for operation in previous_values) and not any(
        operation.startswith("heading-number:") for operation in current_values
    ):
        events.append(
            CorrectionFeedback(
                **common,
                operation="heading-number:*",
                decision=CorrectionFeedback.Decision.RESET,
                value={},
            )
        )
    CorrectionFeedback.objects.bulk_create(events)


def record_verified_heading_keep(capture, reviewer, block_index, reason):
    """Record an explicit verified-keep for one unchanged paragraph/heading block."""
    profile = get_profile()
    if capture.site.profile != profile.key:
        raise ValueError("Feedback must use a capture from the active profile.")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
        raise ValueError("A verified keep requires a reason of at most 2000 characters.")
    source, _, body, _ = extraction(capture)
    original = baseline(source, body)
    if type(block_index) is not int or not 0 <= block_index < len(original["blocks"]):
        raise ValueError("Choose an existing source block.")
    block = original["blocks"][block_index]
    if block["tag"] not in {"p", "h1", "h2", "h3", "h4", "h5", "h6"}:
        raise ValueError("Verified type labels require an existing paragraph or heading.")
    latest = capture.corrections.filter(profile=profile.key).order_by("-revision").first()
    return CorrectionFeedback.objects.create(
        capture=capture,
        correction=latest,
        reviewer=reviewer,
        correction_revision=latest.revision if latest else 0,
        profile=profile.key,
        source_digest=capture.response["digest"],
        adapter_version=profile.adapter_version,
        body_digest=original["body_digest"],
        operation=f"block-type:{block_index}",
        decision=CorrectionFeedback.Decision.VERIFIED_KEEP,
        value={"tag": block["tag"]},
        reason=reason.strip(),
    )
