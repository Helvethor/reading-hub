"""Read-only discovery of recurring explicit corrections, not extraction accuracy."""

import hashlib
import json
from collections import Counter, defaultdict

from django.db.models import Count, OuterRef, Subquery

from library.models import CatalogueEntry, SourceCorrection
from library.profile import get_profile
from library.services.corrections import (
    SCHEMA_VERSION,
    apply_expected,
    digest,
    extraction,
    legacy_index_metadata,
    validate_expected,
)
from library.services.errors import ImportFailure


def current_compatibility(profile, *, limit=100):
    """Check bounded newest revisions against retained workspace extraction, without saving."""
    if not 1 <= limit <= 1000:
        raise ValueError("Compatibility limit must be between 1 and 1000.")
    current_profile = get_profile()
    if profile != current_profile.key:
        raise ValueError("Compatibility checks require the active profile.")
    revisions = SourceCorrection.objects.filter(profile=profile)
    latest = revisions.filter(capture_id=OuterRef("capture_id")).order_by("-revision")
    active = revisions.filter(pk=Subquery(latest.values("pk")[:1]))
    total = active.count()
    results = []
    for row in active.select_related("capture__site").order_by("pk")[:limit]:
        result = {
            "correction": row.pk,
            "capture": row.capture_id,
            "url": row.capture.url,
            "revision": row.revision,
        }
        reasons = []
        if row.schema_version > SCHEMA_VERSION:
            result.update(status="unsupported", reasons=["Unsupported correction schema."])
        elif not row.expected:
            result.update(status="reset", reasons=[])
        else:
            if row.source_digest != row.capture.response.get("digest"):
                reasons.append("Retained source digest changed.")
            if row.adapter_version != current_profile.adapter_version:
                reasons.append("Adapter version changed.")
            if reasons:
                result.update(status="needs_revalidation", reasons=reasons)
            else:
                try:
                    source, _, body, _ = extraction(row.capture)
                    legacy = legacy_index_metadata(row, body)
                    if row.original["body_digest"] != digest(str(body)) and not legacy:
                        result.update(
                            status="needs_revalidation", reasons=["Extracted body changed."]
                        )
                    else:
                        expected = validate_expected(row.expected, body, source)
                        apply_expected(source, body, expected)
                        result.update(status="compatible", reasons=[], legacy_index_metadata=legacy)
                except (ValueError, ImportFailure, OSError) as exc:
                    result.update(status="unavailable", reasons=[str(exc)])
        results.append(result)
    return {
        "adapter_version": current_profile.adapter_version,
        "limit": limit,
        "total": total,
        "checked": len(results),
        "remaining": max(0, total - len(results)),
        "status_counts": dict(sorted(Counter(row["status"] for row in results).items())),
        "results": results,
        "limitations": [
            "Newest revisions per capture, ordered by correction ID; no random sampling.",
            "Compatibility checks bindings and operation application, not extraction accuracy.",
            "No whole-book assembly, reader-link validation, network access or saved changes.",
            "Conflicting answers can each be compatible; consult conflicts separately.",
        ],
    }


def correction_patterns(profile):
    revisions = SourceCorrection.objects.filter(profile=profile)
    latest = revisions.filter(capture_id=OuterRef("capture_id")).order_by("-revision")
    active = list(
        revisions.filter(pk=Subquery(latest.values("pk")[:1]))
        .select_related("capture__site")
        .order_by("pk")
    )
    urls = {row.capture.url for row in active}
    works = {
        (site, url): book_url or url
        for site, url, book_url in CatalogueEntry.objects.filter(
            site__profile=profile, url__in=urls
        ).values_list("site_id", "url", "book__url")
    }
    totals = revisions.aggregate(revisions=Count("pk"), captures=Count("capture", distinct=True))
    groups, seen, unsupported = {}, set(), []
    evidence = defaultdict(list)
    conflicts = []
    resets = 0
    for row in active:
        if row.schema_version > SCHEMA_VERSION:
            unsupported.append({"correction": row.pk, "schema": row.schema_version})
            continue
        if not row.expected:
            resets += 1
        identity = (
            row.capture.url,
            row.source_digest,
            row.adapter_version,
            row.original["body_digest"],
        )
        evidence[identity].append(row)
    for identity, rows in evidence.items():
        answers = {json.dumps(row.expected, sort_keys=True, separators=(",", ":")) for row in rows}
        if len(answers) > 1:
            conflicts.append(
                {
                    "url": identity[0],
                    "source_digest": identity[1],
                    "adapter_version": identity[2],
                    "body_digest": identity[3],
                    "reviews": [
                        {
                            "correction": row.pk,
                            "capture": row.capture_id,
                            "revision": row.revision,
                            "reset": not bool(row.expected),
                        }
                        for row in rows
                    ],
                }
            )
            continue
        row = rows[0]
        original = row.original
        expected = row.expected
        if not expected:
            continue
        seen.add(identity)
        blocks = {block["index"]: block for block in original["blocks"]}
        # This is a coarse extracted-layout proxy, not an identified website template.
        layout = hashlib.sha256(
            " ".join(block["tag"] for block in original["blocks"]).encode()
        ).hexdigest()[:16]
        operations = Counter()
        for edit in expected.get("blocks", []):
            operations[f"block:{blocks[edit['index']]['tag']}->{edit['action']}"] += 1
        for field in expected.get("metadata", {}):
            operations[f"metadata:{field}"] += 1
        if expected.get("media"):
            operations["media:association"] += len(expected["media"])
        if expected.get("notes"):
            operations["notes:repair"] += len(expected["notes"])
        if expected.get("heading_numbers"):
            operations["heading:number"] += len(expected["heading_numbers"])
        for edit in expected.get("presentation", []):
            if "align" in edit:
                operations["presentation:alignment"] += 1
            if edit.get("styles"):
                operations["presentation:block-style"] += 1
            if edit.get("ranges"):
                operations["presentation:text-style"] += len(edit["ranges"])
        language = original["metadata"].get("language") or "und"
        work = works.get((row.capture.site_id, row.capture.url), row.capture.url)
        for operation, count in operations.items():
            key = (row.capture.site.host, row.adapter_version, language, operation)
            group = groups.setdefault(
                key,
                {
                    "examples": 0,
                    "operations": 0,
                    "urls": set(),
                    "works": set(),
                    "layouts": Counter(),
                    "work_breakdown": {},
                    "samples": [],
                },
            )
            group["examples"] += 1
            group["operations"] += count
            group["urls"].add(row.capture.url)
            group["works"].add(work)
            group["layouts"][layout] += 1
            work_group = group["work_breakdown"].setdefault(
                work, {"examples": 0, "operations": 0, "urls": set()}
            )
            work_group["examples"] += 1
            work_group["operations"] += count
            work_group["urls"].add(row.capture.url)
            if len(group["samples"]) < 5:
                group["samples"].append(
                    {"correction": row.pk, "capture": row.capture_id, "url": row.capture.url}
                )
    output = []
    for (host, adapter, language, operation), group in groups.items():
        output.append(
            {
                "host": host,
                "adapter_version": adapter,
                "language": language,
                "layout_proxies": dict(sorted(group["layouts"].items())),
                "operation": operation,
                "independent_examples": group["examples"],
                "operation_count": group["operations"],
                "source_urls": len(group["urls"]),
                "works": len(group["works"]),
                "work_breakdown": [
                    {
                        "url": work,
                        "independent_examples": counts["examples"],
                        "operation_count": counts["operations"],
                        "source_urls": len(counts["urls"]),
                    }
                    for work, counts in sorted(group["work_breakdown"].items())
                ],
                "samples": group["samples"],
            }
        )
    output.sort(
        key=lambda group: (
            -group["source_urls"],
            -group["independent_examples"],
            group["host"],
            group["operation"],
            group["adapter_version"],
        )
    )
    return {
        "profile": profile,
        **totals,
        "active_captures": len(active),
        "active_resets": resets,
        "independent_corrected_examples": len(seen),
        "unsupported": unsupported,
        "conflicting_examples": len(conflicts),
        "conflicts": conflicts,
        "limitations": [
            "Newest revisions only; duplicate URL/digest/adapter/body evidence counts once.",
            "Conflicting newest answers for identical evidence are excluded, not resolved.",
            "An empty answer is a reset, not verification that extraction was correct.",
            "Partial answers only: counts do not measure parser accuracy or verified documents.",
            "Layout hashes are extracted tag-sequence proxies, not proven shared source templates.",
            "Work counts use current catalogue book membership, or the source URL when absent.",
            "Different captures of a work are not independent held-out works.",
            "No revalidation, network requests, automatic rule promotion or data changes.",
        ],
        "groups": output,
    }
