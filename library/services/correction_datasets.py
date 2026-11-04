"""Bounded, offline transfer of verified overrides, not automatic training labels."""

import hashlib
import json
from copy import deepcopy

from django.db import transaction
from django.utils.dateparse import parse_datetime

from library.models import CrawlCapture, SourceCorrection
from library.profile import get_profile
from library.services.corrections import (
    SCHEMA_VERSION,
    CorrectionConflict,
    baseline,
    export_correction,
    extraction,
    latest,
    save_correction,
    validate_expected,
)

MAX_BYTES = 1024 * 1024
MAX_RECORDS = 50
FORMAT_VERSION = 1
SEMANTICS = "explicit_verified_overrides"


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fingerprint(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def dataset(corrections):
    records = [export_correction(item) for item in corrections]
    if len(records) > MAX_RECORDS:
        raise ValueError(f"Export at most {MAX_RECORDS} revisions; narrow the filters.")
    result = {
        "format_version": FORMAT_VERSION,
        "dataset_schema": SCHEMA_VERSION,
        "semantics": SEMANTICS,
        "corrections": records,
    }
    if len(json.dumps(result, ensure_ascii=False).encode()) > MAX_BYTES:
        raise ValueError("Dataset exceeds 1 MiB; export fewer corrections.")
    return result


def parse_dataset(raw):
    if len(raw) > MAX_BYTES:
        raise ValueError("Dataset exceeds the 1 MiB limit.")
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeDecodeError, RecursionError) as exc:
        raise ValueError("Upload a valid UTF-8 JSON correction dataset.") from exc
    if not isinstance(value, dict) or set(value) - {
        "format_version",
        "dataset_schema",
        "semantics",
        "corrections",
    }:
        raise ValueError("Unknown dataset format or fields.")
    if (
        type(value.get("dataset_schema")) is not int
        or value["dataset_schema"] not in range(1, SCHEMA_VERSION + 1)
        or type(value.get("format_version", 1)) is not int
        or value.get("format_version", 1) != FORMAT_VERSION
        or value.get("semantics", SEMANTICS) != SEMANTICS
    ):
        raise ValueError("Unsupported dataset or correction schema/semantics.")
    records = value.get("corrections")
    if not isinstance(records, list) or not 1 <= len(records) <= MAX_RECORDS:
        raise ValueError(f"Upload between 1 and {MAX_RECORDS} correction revisions.")
    return value


def validate_record(record, depth=0):
    if depth > 4:
        raise ValueError("Import provenance exceeds four transfer generations.")
    required = {
        "schema_version",
        "capture",
        "revision",
        "adapter_version",
        "created_at",
        "reason",
        "original",
        "expected",
    }
    if (
        not isinstance(record, dict)
        or not required <= set(record)
        or set(record) - (required | {"reviewer_id", "imported_from"})
    ):
        raise ValueError("Invalid correction record fields.")
    if type(record["schema_version"]) is not int or record["schema_version"] not in {
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        8,
        9,
        10,
    }:
        raise ValueError("Unsupported correction schema.")
    if type(record["revision"]) is not int or record["revision"] < 1:
        raise ValueError("Invalid source revision.")
    capture = record["capture"]
    if not isinstance(capture, dict) or set(capture) != {"url", "digest", "captured_at", "profile"}:
        raise ValueError("Invalid capture provenance.")
    for value in (capture["captured_at"], record["created_at"]):
        if not isinstance(value, str) or parse_datetime(value) is None:
            raise ValueError("Invalid provenance timestamp.")
    if (
        not isinstance(capture["url"], str)
        or len(capture["url"]) > 2048
        or not isinstance(capture["digest"], str)
        or len(capture["digest"]) != 64
        or any(c not in "0123456789abcdef" for c in capture["digest"])
        or capture["profile"] != get_profile().key
        or not isinstance(record["adapter_version"], str)
        or len(record["adapter_version"]) > 100
        or (depth == 0 and record["adapter_version"] != get_profile().adapter_version)
    ):
        raise ValueError("Profile, adapter version or capture provenance does not match.")
    if not isinstance(record["reason"], str) or len(record["reason"]) > 4000:
        raise ValueError("Invalid revision reason.")
    if (
        not isinstance(record["original"], dict)
        or set(record["original"]) != {"title", "metadata", "body_digest", "blocks", "provenance"}
        or not isinstance(record["original"]["provenance"], dict)
        or set(record["original"]["provenance"]) != {"topic_rules", "app_version"}
    ):
        raise ValueError("Invalid extraction baseline.")
    origin = record.get("imported_from", {})
    if not isinstance(origin, dict):
        raise ValueError("Invalid import provenance.")
    # Legacy account IDs are not portable authority and must not be re-exported.
    clean = deepcopy(record)
    clean.pop("reviewer_id", None)
    if origin:
        if set(origin) != {"fingerprint", "record"}:
            raise ValueError("Invalid import provenance fields.")
        ancestor = validate_record(origin["record"], depth + 1)
        if origin["fingerprint"] != fingerprint(ancestor):
            raise ValueError("Import provenance fingerprint does not match.")
        clean["imported_from"] = {"fingerprint": origin["fingerprint"], "record": ancestor}
    return clean


def prepare_import(value):
    """Resolve every record locally; no write or network access during preview."""
    rows = []
    seen = set()
    local = {}
    for number, raw in enumerate(value["corrections"], 1):
        try:
            record = validate_record(raw)
            if record["schema_version"] > value["dataset_schema"]:
                raise ValueError("Record schema exceeds the dataset's declared correction schema.")
            key = (record["capture"]["url"], record["capture"]["digest"])
            identity = (*key, record["revision"])
            if identity in seen:
                raise ValueError("Duplicate source revision in this dataset.")
            seen.add(identity)
            if key not in local:
                captures = list(
                    CrawlCapture.objects.filter(
                        site__profile=get_profile().key,
                        url=key[0],
                        response__digest=key[1],
                    ).select_related("site")[:2]
                )
                if not captures:
                    raise ValueError("No exact retained local URL/content digest matches.")
                if len(captures) != 1:
                    raise ValueError("Ambiguous local capture; select an unambiguous dataset.")
                capture = captures[0]
                source, _, body, _ = extraction(capture)
                current = latest(capture)
                local[key] = (
                    capture,
                    body,
                    baseline(source, body),
                    current.revision if current else 0,
                )
            capture, body, original, revision = local[key]
            if record["original"].get("body_digest") != original["body_digest"]:
                raise ValueError("Extracted body has changed; revalidate in the workspace.")
            # Compare block evidence as well as the digest before interpreting indices.
            old_blocks = record["original"].get("blocks")
            if (
                not isinstance(old_blocks, list)
                or old_blocks != original["blocks"][: len(old_blocks)]
            ):
                raise ValueError("Block evidence no longer matches the local extraction.")
            if (
                record["original"].get("title") != original["title"]
                or encode(record["original"].get("metadata")) != encode(original["metadata"])
                or encode(record["original"]["provenance"].get("topic_rules"))
                != encode(original["provenance"]["topic_rules"])
            ):
                raise ValueError("Metadata baseline or vocabulary changed; revalidate locally.")
            validate_expected(record["expected"], body, source)
            if record["schema_version"] < 10 and "presentation" in record["expected"]:
                raise ValueError("Presentation corrections require correction schema 10.")
            if (
                record["schema_version"] < 9
                and "subtitle" in record["expected"].get("metadata", {})
            ):
                raise ValueError("Subtitle metadata requires correction schema 9.")
            if record["schema_version"] < 8 and "heading_numbers" in record["expected"]:
                raise ValueError("Heading numbers require correction schema 8.")
            for pair in record["expected"].get("heading_numbers", []):
                if any(pair[key] >= len(old_blocks) for key in ("number", "heading")):
                    raise ValueError("Heading number lacks corresponding source block evidence.")
            if record["schema_version"] < 7 and "notes" in record["expected"]:
                raise ValueError("Note repairs require correction schema 7.")
            for repair in record["expected"].get("notes", []):
                indices = [repair["target"], repair["reference"]["block"]]
                if repair["backlink"] is not None:
                    indices.append(repair["backlink"]["block"])
                if any(index >= len(old_blocks) for index in indices):
                    raise ValueError("Note repair lacks corresponding source block evidence.")
            if record["schema_version"] < 6 and "media" in record["expected"]:
                raise ValueError("Media associations require correction schema 6.")
            for association in record["expected"].get("media", []):
                if any(
                    index is not None and index >= len(old_blocks) for index in association.values()
                ):
                    raise ValueError("Media association lacks corresponding source block evidence.")
            if record["schema_version"] < 5 and "excluded_covers" in record["expected"].get(
                "metadata", {}
            ):
                raise ValueError("Book cover exclusions require correction schema 5.")
            if record["schema_version"] < 4 and any(
                "canonical" in person
                for person in record["expected"].get("metadata", {}).get("people", [])
            ):
                raise ValueError("Canonical person selections require correction schema 4.")
            if any(
                edit["index"] >= len(old_blocks) for edit in record["expected"].get("blocks", [])
            ):
                raise ValueError("Block edit lacks corresponding source block evidence.")
            if record["schema_version"] < 3 and any(
                edit["action"] == "subtitle" for edit in record["expected"].get("blocks", [])
            ):
                raise ValueError("Subtitle edits require correction schema 3.")
            if record["schema_version"] < 2 and any(
                "end_value" in date
                for date in record["expected"].get("metadata", {}).get("dates", [])
            ):
                raise ValueError("Date intervals require correction schema 2 or later.")
            token = fingerprint(record)
            duplicate = SourceCorrection.objects.filter(
                capture=capture, imported_from__fingerprint=token
            ).exists()
            rows.append(
                {
                    "capture": capture,
                    "record": record,
                    "fingerprint": token,
                    "base_revision": revision,
                    "duplicate": duplicate,
                    "title": record["expected"]
                    .get("metadata", {})
                    .get("title", record["original"].get("title", capture.url)),
                    "expected_json": json.dumps(record["expected"], ensure_ascii=False, indent=2),
                    "current_expected": json.dumps(
                        latest(capture).expected if revision else {}, ensure_ascii=False, indent=2
                    ),
                }
            )
        except ValueError as exc:
            raise ValueError(f"Record {number}: {exc}") from exc
    rows.sort(key=lambda row: (row["capture"].pk, row["record"]["revision"]))
    for capture_id in {row["capture"].pk for row in rows}:
        history = [row for row in rows if row["capture"].pk == capture_id]
        if any(not row["duplicate"] for row in history) and history[-1]["duplicate"]:
            # Adding missing older evidence must not accidentally activate it
            # just because the source's newest revision was imported previously.
            history[-1]["duplicate"] = False
            history[-1]["reapply"] = True
    return rows


@transaction.atomic
def commit_import(value, reviewer, bases):
    rows = prepare_import(value)
    for pk in sorted({row["capture"].pk for row in rows}):
        capture = CrawlCapture.objects.select_for_update().get(pk=pk)
        current = latest(capture)
        if bases.get(str(pk)) != (current.revision if current else 0):
            raise CorrectionConflict(
                "A correction changed after preview. Upload again to review it."
            )
    created = 0
    for row in rows:
        if row["duplicate"]:
            continue
        capture = row["capture"]
        current = latest(capture)
        correction = save_correction(
            capture,
            reviewer,
            row["record"]["expected"],
            current.revision if current else 0,
            row["record"]["reason"],
            record_feedback=False,
        )
        correction.imported_from = {
            "fingerprint": row["fingerprint"],
            "record": row["record"],
        }
        correction.save(update_fields=["imported_from"])
        created += 1
    return created, len(rows) - created
