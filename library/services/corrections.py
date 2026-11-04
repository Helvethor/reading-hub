"""Capture-scoped reviewed overrides; never execute or rewrite retained HTML."""

import hashlib
import re
from copy import deepcopy
from datetime import date as calendar_date

from bs4 import Comment, NavigableString, Tag
from django.db import transaction

from library import versions
from library.models import CanonicalAuthor, CrawlCapture, CrawlSite, SourceCorrection
from library.profile import get_profile
from library.services.errors import ImportFailure
from library.services.fetch import canonical_url
from library.services.storage import read_blob
from library.sources.adapters import discover, extract
from library.sources.base import Part, Source, image_url, parse_html
from library.sources.classification import normalize_language

BLOCKS = "h1,h2,h3,h4,h5,h6,p,li,blockquote,figure,figcaption,table,pre,img"
ROLES = ("author", "editor", "translator", "unknown", "exclude")
SCHEMA_VERSION = 10


def rendition_correction_sources(rendition):
    from urllib.parse import urlsplit

    profile = get_profile()
    if rendition.metadata.get("profile", profile.key) != profile.key:
        raise ValueError("Switch to this rendition's profile before correcting it.")
    pages = rendition.snapshot.manifest.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ValueError("This historical snapshot has no retained source pages to correct.")
    parts = rendition.structure.get("parts") or rendition.snapshot.manifest.get("parts", [])
    labels = {canonical_url(part["url"]): part["title"] for part in parts}
    rows = []
    for index, page in enumerate(pages):
        url = canonical_url(page["url"])
        site = CrawlSite.objects.filter(profile=profile.key, host=urlsplit(url).hostname).first()
        capture = exact_rendition_capture(site, url, page) if site else None
        rows.append(
            {
                "index": index,
                "url": url,
                "label": (
                    "Book metadata / contents / cover images"
                    if rendition.structure.get("book") and index == 0
                    else labels.get(url, rendition.title)
                ),
                "capture": capture,
                "page": page,
            }
        )
    return rows


def exact_rendition_capture(site, url, page):
    return (
        CrawlCapture.objects.filter(
            site=site,
            url=url,
            response__digest=page["digest"],
            response__headers=page.get("headers", {}),
            response__resolved_url=page["resolved_url"],
        )
        .order_by("pk")
        .first()
    )


@transaction.atomic
def retain_rendition_capture(rendition, index):
    from urllib.parse import urlsplit

    from django.db.models import F

    rows = rendition_correction_sources(rendition)
    if index < 0 or index >= len(rows):
        raise ValueError("Choose a source page belonging to this exact rendition.")
    row = rows[index]
    url, page = row["url"], row["page"]
    read_blob(page["digest"])
    site, _ = CrawlSite.objects.get_or_create(
        profile=get_profile().key, host=urlsplit(url).hostname
    )
    # Serialize check/create on SQLite without changing crawl configuration.
    CrawlSite.objects.filter(pk=site.pk).update(status=F("status"))
    capture = exact_rendition_capture(site, url, page)
    if capture:
        return capture
    from library.services.page_types import latest_decision

    decision = latest_decision(site, url)
    return CrawlCapture.objects.create(
        site=site,
        url=url,
        response={**page, "url": url},
        discovery_only=bool(decision and decision.discovery_only),
    )


class CorrectionConflict(ValueError):
    pass


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def extraction(capture, *, excerpt_mapping=False):
    if capture.site.profile != get_profile().key:
        raise ValueError("Switch to this capture's profile before correcting it.")
    if capture.discovery_only:
        raise ValueError("This is a discovery index/listing, not a readable work to correct.")
    raw = read_blob(capture.response["digest"])
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError("This first editor supports source pages up to 2 MiB.")
    soup = parse_html(raw, capture.response.get("headers", {}))
    marker = "data-internal-excerpt-block"
    if excerpt_mapping:
        from library.services.source_excerpts import semantic_blocks

        for node in soup.find_all(True):
            node.attrs.pop(marker, None)
        for index, node in enumerate(semantic_blocks(soup)):
            for child in [node, *node.find_all(True)]:
                child[marker] = str(index)
    url = capture.url
    source = discover(deepcopy(soup), url)
    part = next(
        (
            part
            for part in source.parts
            if canonical_url(part.url) == canonical_url(url) and not part.section
        ),
        None,
    )
    part = part or Part(url, source.title)
    body = extract(
        deepcopy(soup),
        url,
        book=source.book and not part.use_source_headings,
        group=part.group,
        chapter_title=part.title,
        index=source.book,
    )
    if not isinstance(body, Tag):
        raise ValueError("The adapter did not return an editable document body.")
    if len(editable_nodes(body)) > 2000:
        raise ValueError("This first editor supports at most 2000 extracted blocks per page.")
    if excerpt_mapping:
        mapping = []
        for node in editable_nodes(body):
            owner = node if isinstance(node, Tag) else node.parent
            value = owner.get(marker)
            mapping.append(int(value) if value is not None else None)
        for root in (soup, body):
            for node in [root, *root.find_all(True)]:
                node.attrs.pop(marker, None)
        body.__dict__["_excerpt_blocks"] = mapping
    return source, part, body, soup


def editable_nodes(body):
    blocks = body.select(BLOCKS)
    covered = {id(node) for node in blocks}
    # Append newly supported elements after legacy blocks/text to preserve saved indices.
    return (
        blocks
        + [
            node
            for node in body.descendants
            if isinstance(node, NavigableString)
            and not isinstance(node, Comment)
            and node.strip()
            and not any(id(parent) in covered for parent in node.parents)
            and not any(parent.name in {"script", "style", "template"} for parent in node.parents)
        ]
        + body.select("hr")
    )


def block_rows(body):
    return [
        {
            "index": index,
            "tag": node.name if isinstance(node, Tag) else "unwrapped text",
            "text": (
                divider_label(node)
                if node.name == "hr"
                else node.get_text(" ", strip=True) or str(node.get("alt", ""))
                if isinstance(node, Tag)
                else str(node)
            ),
        }
        for index, node in enumerate(editable_nodes(body))
    ]


def divider_label(node):
    following = node.find_next(["h1", "h2", "h3", "h4", "h5", "h6", "p"])
    if following is not None:
        return "Horizontal divider before: " + following.get_text(" ", strip=True)[:160]
    return "Horizontal divider"


def baseline(source, body):
    return {
        "title": source.title,
        "metadata": deepcopy(source.metadata),
        "body_digest": digest(str(body)),
        "blocks": block_rows(body),
        "provenance": {
            "topic_rules": get_profile().topic_rules,
            "app_version": versions.APP_VERSION,
        },
    }


def latest(capture):
    return capture.corrections.order_by("-revision").first()


def validate_expected(value, body, source=None):
    if not isinstance(value, dict) or set(value) - {
        "metadata", "blocks", "media", "notes", "heading_numbers", "presentation"
    }:
        raise ValueError(
            "Expected output contains unsupported correction fields."
        )
    metadata = value.get("metadata", {})
    if not isinstance(metadata, dict) or set(metadata) - {
        "title",
        "subtitle",
        "language",
        "people",
        "dates",
        "topics",
        "excluded_covers",
    }:
        raise ValueError("Unknown metadata correction field.")
    covers = metadata.get("excluded_covers", [])
    if (
        not isinstance(covers, list)
        or len(covers) > 100
        or any(
            not isinstance(url, str)
            or len(url) > 2048
            or not url.startswith(("https://", "http://"))
            for url in covers
        )
        or len(set(covers)) != len(covers)
    ):
        raise ValueError("Excluded covers must be a list of distinct source image URLs.")
    if source is not None and set(covers) - {
        cover["url"] for cover in source.metadata.get("covers", [])
    }:
        raise ValueError("An excluded cover image is not present in this source.")
    for key, limit in (("title", 1000), ("language", 35)):
        if key in metadata:
            text = metadata[key]
            if not isinstance(text, str) or not text.strip() or len(text) > limit:
                raise ValueError(f"Enter a non-empty {key} of at most {limit} characters.")
    if "subtitle" in metadata and (
        not isinstance(metadata["subtitle"], str) or len(metadata["subtitle"]) > 1000
    ):
        raise ValueError("Enter a subtitle of at most 1000 characters, or leave it empty.")
    if "language" in metadata:
        language = metadata["language"]
        if normalize_language(language) != language:
            raise ValueError("Use a normalized base language code, or und for unknown.")
    people = metadata.get("people", [])
    if not isinstance(people, list) or len(people) > 30:
        raise ValueError("People must be a list of at most 30 components.")
    for person in people:
        if not isinstance(person, dict) or set(person) not in (
            {"name", "source_name", "role"},
            {"name", "source_name", "role", "canonical"},
        ):
            raise ValueError("Each person requires name, source_name and role.")
        if not isinstance(person["role"], str) or person["role"] not in ROLES:
            raise ValueError("Unknown attribution role.")
        for key in ("name", "source_name"):
            if (
                not isinstance(person[key], str)
                or not person[key].strip()
                or len(person[key]) > 500
            ):
                raise ValueError("Person names must contain 1-500 characters.")
        if "canonical" in person:
            identity = person["canonical"]
            if (
                not isinstance(identity, dict)
                or set(identity) != {"name", "authority_uri"}
                or not isinstance(identity["name"], str)
                or not isinstance(identity["authority_uri"], str)
                or identity["name"] != person["name"]
                or not CanonicalAuthor.objects.filter(
                    name=identity["name"], authority_uri=identity["authority_uri"]
                ).exists()
            ):
                raise ValueError(
                    "Selected canonical person no longer matches. "
                    "Select it again or use a scoped name."
                )
    topics = metadata.get("topics", [])
    if (
        not isinstance(topics, list)
        or len(topics) > 100
        or any(
            not isinstance(topic, str) or not topic.strip() or len(topic) > 500 for topic in topics
        )
    ):
        raise ValueError("Topics must be a list of at most 100 non-empty labels.")
    dates = metadata.get("dates", [])
    if not isinstance(dates, list) or len(dates) > 20:
        raise ValueError("Dates must be a list of at most 20 typed values.")
    for date in dates:
        if (
            not isinstance(date, dict)
            or set(date) not in ({"value", "type"}, {"value", "end_value", "type"})
            or not isinstance(date["type"], str)
            or date["type"] not in {"publication", "written", "online_edition", "unknown"}
        ):
            raise ValueError("Dates require an explicit type and YYYY, YYYY-MM or YYYY-MM-DD.")
        for key in ("value", "end_value") if "end_value" in date else ("value",):
            text = date[key]
            if not isinstance(text, str) or not re.fullmatch(
                r"[12]\d{3}(?:-\d{2}(?:-\d{2})?)?", text
            ):
                raise ValueError("Dates require YYYY, YYYY-MM or YYYY-MM-DD.")
            try:
                calendar_date.fromisoformat(text + {4: "-01-01", 7: "-01", 10: ""}[len(text)])
            except ValueError as exc:
                raise ValueError("Invalid calendar date.") from exc
        if "end_value" in date:
            if len(date["value"]) != len(date["end_value"]):
                raise ValueError("Use the same precision for both ends of a date range.")
            if date["end_value"] < date["value"]:
                raise ValueError("The end date must not be earlier than the start date.")
    if sum(date["type"] == "publication" for date in dates) > 1:
        raise ValueError(
            "This first editor supports one publication date; leave conflicts unresolved."
        )
    edits = value.get("blocks", [])
    nodes = editable_nodes(body)
    if not isinstance(edits, list) or len(edits) > 500:
        raise ValueError("Block corrections must be a list of at most 500 edits.")
    seen = set()
    for edit in edits:
        if not isinstance(edit, dict) or set(edit) != {"index", "action"}:
            raise ValueError("Each block edit requires index and action.")
        index, action = edit["index"], edit["action"]
        if type(index) is not int or not 0 <= index < len(nodes) or index in seen:
            raise ValueError("Select a unique existing block index.")
        if not isinstance(action, str) or action not in {
            "subtitle",
            "exclude",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "p",
        }:
            raise ValueError("Unsupported block action.")
        if action != "exclude" and (
            not isinstance(nodes[index], Tag)
            or nodes[index].name
            not in {
                "h1",
                "h2",
                "h3",
                "h4",
                "h5",
                "h6",
                "p",
            }
        ):
            raise ValueError("Only paragraph and heading blocks can change heading level.")
        seen.add(index)
    for edit in edits:
        if any(
            nodes[parent["index"]] in nodes[edit["index"]].parents
            for parent in edits
            if parent["action"] == "exclude" and parent["index"] != edit["index"]
        ):
            raise ValueError("Do not edit a block inside another excluded block.")
    from library.services.media_corrections import association_nodes

    association_nodes(value.get("media", []), nodes, edits)
    from library.services.note_corrections import note_nodes, validate_note_conflicts

    validate_note_conflicts(note_nodes(value.get("notes", []), nodes), nodes, edits)
    from library.services.heading_numbers import number_heading_pairs

    number_heading_pairs(
        value.get("heading_numbers", []), nodes, edits,
        value.get("media", []), value.get("notes", []),
    )
    from library.services.presentation import validate_presentations

    validate_presentations(
        value.get("presentation", []), nodes,
        [edit["index"] for edit in edits if edit["action"] == "exclude"],
    )
    return deepcopy(value)


def apply_expected(source, body, expected):
    from library.services.presentation import apply_presentations

    if expected.get("presentation"):
        apply_presentations(expected["presentation"], editable_nodes(body))
    from library.services.heading_numbers import apply_number_heading_pairs, number_heading_pairs
    from library.services.media_corrections import apply_associations, association_nodes
    from library.services.note_corrections import apply_notes, note_nodes, validate_note_conflicts

    note_blocks = editable_nodes(body) if expected.get("notes") else []
    notes = note_nodes(expected.get("notes", []), note_blocks)
    validate_note_conflicts(notes, note_blocks, expected.get("blocks", []))

    associations = association_nodes(
        expected.get("media", []),
        editable_nodes(body) if expected.get("media") else [],
        expected.get("blocks", []),
    )
    numbered = number_heading_pairs(
        expected.get("heading_numbers", []),
        editable_nodes(body) if expected.get("heading_numbers") else [],
        expected.get("blocks", []), expected.get("media", []), expected.get("notes", []),
    )
    metadata = expected.get("metadata", {})
    if "excluded_covers" in metadata:
        source.metadata["covers"] = [
            cover
            for cover in source.metadata.get("covers", [])
            if cover["url"] not in metadata["excluded_covers"]
        ]
    if "title" in metadata:
        source.title = metadata["title"]
    for key in ("subtitle", "language", "topics"):
        if key in metadata:
            source.metadata[key] = deepcopy(metadata[key])
    if "topics" in metadata:
        source.metadata["topic"] = ", ".join(metadata["topics"])
    if "people" in metadata:
        source.metadata["contributors"] = deepcopy(metadata["people"])
        source.metadata["authors"] = [
            person["name"] for person in metadata["people"] if person["role"] == "author"
        ]
        source.metadata["author"] = ", ".join(source.metadata["authors"])
        source.metadata["author_is_fallback"] = False
    if "dates" in metadata:
        source.metadata["date_facts"] = deepcopy(metadata["dates"])
        source.metadata["published"] = next(
            (
                date["value"] + (f" / {date['end_value']}" if "end_value" in date else "")
                for date in metadata["dates"]
                if date["type"] == "publication"
            ),
            "",
        )
    edits = expected.get("blocks", [])
    nodes = editable_nodes(body) if edits else []
    for edit in edits:
        node = nodes[edit["index"]]
        if edit["action"] == "exclude":
            if isinstance(node, Tag):
                node.decompose()
            else:
                node.extract()
        else:
            original_level = int(node.name[1]) if node.name.startswith("h") else None
            node.name = "p" if edit["action"] == "subtitle" else edit["action"]
            if edit["action"] == "subtitle":
                node.__dict__["_reviewed_subtitle"] = True
            if edit["action"].startswith("h"):
                # Private markers cannot be supplied by retained HTML.
                node.__dict__["_reviewed_heading_level"] = int(edit["action"][1])
                node.__dict__["_reviewed_original_level"] = original_level
    apply_associations(associations)
    if notes:
        apply_notes(notes, body)
    apply_number_heading_pairs(numbered)
    if metadata.get("excluded_covers"):
        for image in list(body.select("img")):
            if image_url(image, source.parts[0].url) in metadata["excluded_covers"]:
                image.decompose()


@transaction.atomic
def save_correction(capture, reviewer, expected, base_revision, reason, *, record_feedback=True):
    capture = CrawlCapture.objects.select_for_update().select_related("site").get(pk=capture.pk)
    current = latest(capture)
    if base_revision != (current.revision if current else 0):
        raise CorrectionConflict("Another reviewer saved a revision. Reload before saving.")
    source, _, body, _ = extraction(capture)
    expected = validate_expected(expected, body, source)
    profile = get_profile()
    correction = SourceCorrection.objects.create(
        capture=capture,
        revision=base_revision + 1,
        reviewer=reviewer,
        reason=reason,
        source_digest=capture.response["digest"],
        profile=profile.key,
        adapter_version=profile.adapter_version,
        schema_version=SCHEMA_VERSION,
        original=baseline(source, body),
        expected=expected,
    )
    if record_feedback:
        from library.services.correction_feedback import record_correction_revision

        record_correction_revision(correction, current)
    return correction


def legacy_index_metadata(correction, body):
    return (
        correction.original.get("blocks") == []
        and correction.original["body_digest"] == digest("<div></div>")
        and not any(
            correction.expected.get(key) for key in ("blocks", "media", "notes", "heading_numbers")
        )
    )


def apply_retained_correction(
    source, body, entry, *, metadata=False, corrections=None, book_part=False
):
    profile = get_profile()
    if corrections is None:
        corrections = (
            SourceCorrection.objects.filter(
                capture__site__profile=profile.key,
                capture__url=entry["url"],
                source_digest=entry["digest"],
            )
            .select_related("capture__site")
            .order_by("-created_at", "-pk")[:1]
        )
    correction = next(iter(corrections), None)
    if correction is None:
        return None
    if correction.adapter_version != profile.adapter_version:
        raise ImportFailure(
            "Reviewed correction needs revalidation for this adapter version.", "correction"
        )
    if correction.original["body_digest"] != digest(str(body)):
        if metadata and legacy_index_metadata(correction, body):
            # Historical index corrections verified metadata against an empty body.
            apply_expected(source, None, correction.expected)
            source.metadata["_reviewed_metadata"] = correction.expected.get("metadata", {})
            return correction
        if not book_part:
            raise ImportFailure(
                "Reviewed correction no longer matches extracted blocks.", "correction"
            )
        # Book adapters can remove a chapter heading before assembly. Reviewed
        # block indices belong to the standalone workspace, not that variant.
        _, _, reviewed_body, _ = extraction(correction.capture)
        if correction.original["body_digest"] != digest(str(reviewed_body)):
            raise ImportFailure(
                "Reviewed correction no longer matches extracted blocks. "
                f"Revalidate it at /corrections/{correction.capture_id}/.",
                "correction",
            )
        body.clear()
        body.attrs = deepcopy(reviewed_body.attrs)
        for node in list(reviewed_body.contents):
            body.append(node.extract())
    if metadata:
        apply_expected(source, body, correction.expected)
        source.metadata["_reviewed_metadata"] = correction.expected.get("metadata", {})
    else:
        apply_expected(
            Source("", {}, [], False),
            body,
            {
                "blocks": correction.expected.get("blocks", []),
                "media": correction.expected.get("media", []),
                "notes": correction.expected.get("notes", []),
                "heading_numbers": correction.expected.get("heading_numbers", []),
                "presentation": correction.expected.get("presentation", []),
            },
        )
    return correction


def export_correction(correction):
    return {
        "schema_version": correction.schema_version,
        "capture": {
            "url": correction.capture.url,
            "digest": correction.source_digest,
            "captured_at": correction.capture.captured_at.isoformat(),
            "profile": correction.profile,
        },
        "revision": correction.revision,
        "adapter_version": correction.adapter_version,
        "created_at": correction.created_at.isoformat(),
        "reason": correction.reason,
        "original": correction.original,
        "expected": correction.expected,
        "imported_from": correction.imported_from,
    }
