"""Exact-source ranges and named block selections, independent of extraction."""

import hashlib
import json
import uuid
from copy import deepcopy

from django.db import transaction
from django.db.models import F

from library.models import CrawlCapture, SourceExcerptRevision
from library.profile import get_profile
from library.services.errors import ImportFailure
from library.services.storage import read_blob
from library.sources.base import parse_html

BLOCK_TAGS = {
    "p",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "blockquote",
    "pre",
    "table",
    "ul",
    "ol",
    "figure",
    "img",
    "hr",
}
UNSAFE = {"script", "style", "template", "iframe", "object", "embed", "form", "input"}
MAX_BLOCKS = 2000


def source_blocks(entry):
    raw = read_blob(entry["digest"])
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError("Source excerpt selection supports pages up to 2 MiB.")
    soup = parse_html(raw, entry.get("headers", {}))
    return soup, semantic_blocks(soup)


def semantic_blocks(soup):
    root = soup.body or soup
    nodes = [
        node
        for node in root.find_all(BLOCK_TAGS)
        if not any(parent.name in BLOCK_TAGS | UNSAFE for parent in node.parents)
    ]
    if len(nodes) > MAX_BLOCKS:
        raise ValueError("Source excerpt selection supports at most 2000 source blocks.")
    return nodes


def normalized_preview(entry):
    """Show retained evidence in reader typography, without source navigation."""
    from library.sources.base import Part, Source
    from library.sources.normalize import normalize

    soup, nodes = source_blocks(entry)
    body = soup.new_tag("div")
    for index, original in enumerate(nodes):
        node = deepcopy(original)
        node.__dict__["_reviewed_excerpt_block"] = index
        body.append(node)
    for node in list(body.find_all(UNSAFE)):
        node.decompose()
    for link in body.select("a[href]"):
        del link["href"]
    part = Part(entry["url"], "", use_source_headings=True)
    html, _ = normalize([(part, body)], Source("", {}, [part], False), {}, review=True)
    return html


def descriptor(value):
    if (
        not isinstance(value, dict)
        or type(value.get("version")) is not int
        or value["version"] not in (1, 2)
        or not isinstance(value.get("source_digest"), str)
        or len(value["source_digest"]) != 64
        or any(char not in "0123456789abcdef" for char in value["source_digest"])
    ):
        raise ValueError("An excerpt requires a supported selector and exact source digest.")
    if value["version"] == 1:
        valid = (
            set(value) == {"version", "source_digest", "start", "end"}
            and all(type(value[key]) is int for key in ("start", "end"))
            and 0 <= value["start"] <= value["end"] < MAX_BLOCKS
        )
    else:
        valid = (
            set(value) == {"version", "source_digest", "blocks", "definition", "revision"}
            and isinstance(value["blocks"], list)
            and 0 < len(value["blocks"]) <= MAX_BLOCKS
            and all(type(index) is int and 0 <= index < MAX_BLOCKS for index in value["blocks"])
            and value["blocks"] == sorted(set(value["blocks"]))
            and type(value["revision"]) is int
            and value["revision"] > 0
            and isinstance(value["definition"], str)
        )
        if valid:
            try:
                valid = str(uuid.UUID(value["definition"])) == value["definition"]
            except ValueError:
                valid = False
    if not valid:
        raise ValueError("An excerpt requires ordered source blocks and a valid version binding.")
    return value


def block_indices(value):
    descriptor(value)
    if value["version"] == 1:
        return list(range(value["start"], value["end"] + 1))
    return value["blocks"]


def selected_nodes(nodes, value):
    if max(block_indices(value)) >= len(nodes):
        raise ValueError("Excerpt source blocks are no longer available.")
    if value["version"] == 1:
        return range_nodes(nodes, value)
    selected = []
    for index in value["blocks"]:
        node = nodes[index]
        anchors = []
        for previous in node.previous_siblings:
            if getattr(previous, "name", None) is None:
                if str(previous).strip():
                    break
                continue
            if (
                previous.name not in {"a", "span"}
                or previous.get_text(strip=True)
                or previous.find(["img", "hr"])
                or not (previous.get("id") or previous.get("name"))
            ):
                break
            anchors.append(previous)
        selected.extend(reversed(anchors))
        selected.append(node)
    return selected


def select_excerpt(entry, value):
    descriptor(value)
    if entry["digest"] != value["source_digest"]:
        raise ImportFailure(
            "Excerpt source changed. Review its retained source selection again.", "correction"
        )
    soup, nodes = source_blocks(entry)
    selected = selected_nodes(nodes, value)
    body = soup.new_tag("div")
    for node in selected:
        body.append(deepcopy(node))
    for node in list(body.find_all(UNSAFE)):
        node.decompose()
    if not body.get_text(strip=True) and not body.find(["img", "table"]):
        raise ValueError("An excerpt must contain readable text, an image or a table.")
    return body


def range_nodes(nodes, value):
    first, last = nodes[value["start"]], nodes[value["end"]]
    if first.parent is not last.parent:
        raise ValueError("Excerpt boundaries must be complete blocks in the same container.")
    selected = []
    for node in [first, *first.next_siblings]:
        selected.append(node)
        if node is last:
            break
    if selected[-1] is not last:
        raise ValueError("Excerpt end must follow its start within the same container.")
    return selected


def validate_source_ranges(entry, parts):
    """Detect duplicate original nodes across manual and legacy automatic sections."""
    from library.sources.index_sections import sections

    relevant = [part for part in parts if part.url == entry["url"]]
    if not any(part.excerpt for part in relevant):
        return
    soup, blocks = source_blocks(entry)
    automatic = {part.section: nodes for part, nodes in sections(soup, entry["url"])}
    used = set()
    for part in relevant:
        if part.excerpt:
            descriptor(part.excerpt)
            validate_definition_binding(part.excerpt, entry["url"], entry=entry)
            if part.excerpt["source_digest"] != entry["digest"]:
                raise ImportFailure(
                    "Excerpt source changed. Review the selection again.", "correction"
                )
            selected = selected_nodes(blocks, part.excerpt)
        elif part.section:
            selected = automatic.get(part.section, [])
        else:
            raise ValueError("Do not combine an excerpt with its whole source page.")
        identities = set()
        for node in selected:
            if getattr(node, "name", None):
                identities.add(id(node))
                identities.update(id(child) for child in node.find_all(True))
        if used.intersection(identities):
            raise ValueError("Selected excerpts and automatic sections overlap in the source.")
        used.update(identities)


def evidence(entry):
    _, nodes = source_blocks(entry)
    parents = {}
    rows = []
    for index, node in enumerate(nodes):
        parent = parents.setdefault(id(node.parent), len(parents))
        rows.append(
            {
                "index": index,
                "tag": node.name,
                "container": parent,
                "text": node.get_text(" ", strip=True) or node.get("alt", "") or "(empty block)",
            }
        )
    return {"source_digest": entry["digest"], "blocks": rows}


def excerpt_key(value):
    descriptor(value)
    if value["version"] == 1:
        raw = f"{value['version']}:{value['source_digest']}:{value['start']}:{value['end']}"
    else:
        raw = json.dumps(value, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def revision_data(row):
    return {
        "definition": str(row.definition),
        "revision": row.revision,
        "name": row.name,
        "deleted": row.deleted,
        "capture": row.capture_id,
        "url": row.capture.url,
        "reason": row.reason,
        "reviewer": row.reviewer.get_username(),
        "created_at": row.created_at.isoformat(),
        "excerpt": {
            "version": 2,
            "source_digest": row.source_digest,
            "blocks": row.blocks,
            "definition": str(row.definition),
            "revision": row.revision,
        },
    }


def definitions_for_capture(capture):
    rows = capture.excerpts.select_related("capture", "reviewer").order_by("-revision", "-pk")
    seen, result = set(), []
    for row in rows:
        if row.definition not in seen:
            result.append(revision_data(row))
            seen.add(row.definition)
    return result


def definitions_for_entry(entry):
    captures = CrawlCapture.objects.filter(
        site__profile=get_profile().key, url=entry["url"], response__digest=entry["digest"]
    )
    result = []
    for capture in captures:
        result.extend(item for item in definitions_for_capture(capture) if not item["deleted"])
    return result


def validate_definition_binding(value, url, *, entry=None):
    if value["version"] == 1:
        return
    row = (
        SourceExcerptRevision.objects.filter(
            definition=value["definition"],
            revision=value["revision"],
            capture__url=url,
            capture__site__profile=get_profile().key,
        )
        .select_related("capture", "reviewer")
        .first()
    )
    if row is None or revision_data(row)["excerpt"] != value or row.deleted:
        raise ValueError("The excerpt does not match its saved definition revision.")
    if entry is not None and (
        row.capture.response.get("headers", {}).get("content-type", "")
        != entry.get("headers", {}).get("content-type", "")
    ):
        raise ImportFailure(
            "Excerpt source encoding evidence changed. Review its retained selection again.",
            "correction",
        )


@transaction.atomic
def save_definition(capture, reviewer, value):
    if not isinstance(value, dict):
        raise ValueError("An excerpt definition must be an object.")
    # Serialize concurrent edits even for a definition's first revision.
    CrawlCapture.objects.filter(pk=capture.pk).update(id=F("id"))
    if capture.site.profile != get_profile().key:
        raise ValueError("Switch to the capture's profile before defining excerpts.")
    name, reason = value.get("name"), value.get("reason", "")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 1000:
        raise ValueError("Enter an excerpt name of 1-1000 characters.")
    if not isinstance(reason, str) or len(reason.strip()) > 2000:
        raise ValueError("Excerpt revision reason must contain at most 2000 characters.")
    deleted = value.get("deleted", False)
    if type(deleted) is not bool:
        raise ValueError("Deleted must be true or false.")
    definition = value.get("definition")
    if definition is not None:
        try:
            definition = uuid.UUID(str(definition))
        except ValueError as exc:
            raise ValueError("Invalid excerpt identity.") from exc
        current = SourceExcerptRevision.objects.filter(
            definition=definition, capture=capture
        ).first()
        if not current:
            raise ValueError("This excerpt does not belong to this retained capture.")
        if current.deleted:
            raise ValueError("This excerpt was deleted. Create a new definition instead.")
        if type(value.get("revision")) is not int or current.revision != value["revision"]:
            raise ValueError("The excerpt changed. Reload before saving another revision.")
        revision = current.revision + 1
    else:
        if deleted:
            raise ValueError("Choose an existing excerpt to delete.")
        definition, revision = uuid.uuid4(), 1
    if deleted:
        name = current.name
        value = {**value, "source_digest": current.source_digest, "blocks": current.blocks}
    selection = {
        "version": 2,
        "definition": str(definition),
        "revision": revision,
        "source_digest": value.get("source_digest"),
        "blocks": value.get("blocks"),
    }
    select_excerpt({**capture.response, "url": capture.url}, selection)
    return SourceExcerptRevision.objects.create(
        definition=definition,
        revision=revision,
        capture=capture,
        source_digest=selection["source_digest"],
        blocks=selection["blocks"],
        name=name.strip(),
        reason=reason.strip(),
        reviewer=reviewer,
        deleted=deleted,
    )
