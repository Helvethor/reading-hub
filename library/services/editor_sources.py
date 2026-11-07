"""Inert retained-source inspection and bounded structured insertion previews."""

from copy import deepcopy
from itertools import chain
from types import SimpleNamespace
from urllib.parse import unquote, urljoin

from bs4 import BeautifulSoup
from django.core import signing

from library.models import Blob, CrawlCapture, Snapshot, SourceExcerptRevision
from library.profile import get_profile
from library.services.fetch import canonical_url
from library.services.pipeline import snapshot_digest
from library.services.semantic_documents import SCHEMA_VERSION, canonical_document, fingerprint
from library.services.semantic_import import preview_import
from library.services.source_excerpts import UNSAFE, source_blocks
from library.services.storage import read_blob
from library.sources.adapters import adapter_for, image_url
from library.sources.base import Part, Source
from library.sources.normalize import make_id, normalize

MAX_SELECTION = 2000
TICKET_SALT = "editor-retained-source-v1"


def member_choices(rendition):
    from library.services.book_membership import catalogue_book
    from library.services.organizations import entries

    book = catalogue_book(rendition)
    if book is None:
        return []
    return list(entries().filter(book=book).order_by("title", "url").values("url", "title"))


def retained_url_source(rendition, url):
    url = canonical_url(url)
    adapter_for(url)
    # Prefer the pinned edition for its own pages, then the newest retained snapshot.
    snapshots = chain(
        [rendition.snapshot],
        Snapshot.objects.exclude(pk=rendition.snapshot_id).order_by("-pk").iterator(),
    )
    for snapshot in snapshots:
        manifest = snapshot.manifest
        pages = manifest.get("pages", []) if isinstance(manifest, dict) else []
        if not isinstance(pages, list):
            continue
        for index, entry in enumerate(pages):
            if isinstance(entry, dict) and entry.get("url") == url:
                return SimpleNamespace(
                    snapshot=snapshot, snapshot_id=snapshot.pk, structure=rendition.structure,
                ), index
    capture = CrawlCapture.objects.filter(
        site__profile=get_profile().key, url=url,
    ).order_by("-captured_at", "-pk").first()
    if capture:
        try:
            manifest = {"pages": [{**capture.response, "url": url}], "assets": {}}
            snapshot = SimpleNamespace(
                manifest=manifest, digest=snapshot_digest(manifest), pk=None,
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("The retained capture is corrupt.") from exc
        return SimpleNamespace(
            snapshot=snapshot, snapshot_id=None, structure=rendition.structure,
        ), 0
    raise ValueError(
        "This URL has no retained source. Capture or import it first; "
        "the editor never fetches live URLs."
    )


def source_ticket(result, rendition, draft_id, revision, reviewer):
    token = signing.dumps({
        "version": 1, "profile": get_profile().key, "rendition": rendition.pk,
        "draft": str(draft_id) if draft_id else None, "revision": revision,
        "reviewer": reviewer.pk, "binding": result["binding"],
        "page": result["source_entry"], "assets": result["asset_bindings"],
        "asset_sources": result["asset_sources"],
    }, salt=TICKET_SALT, compress=True)
    if len(token) > 60000:
        raise ValueError("This source preview has too much evidence to save in one draft.")
    return token


def ticket_evidence(tokens, *, rendition, draft_id=None, revision=None, reviewer=None,
                    check_scope=False):
    if not isinstance(tokens, list) or len(tokens) > 200 or any(
        not isinstance(token, str) or len(token) > 60000 for token in tokens
    ) or sum(map(len, tokens)) > 60000:
        raise ValueError("Invalid retained source evidence.")
    assets = {}
    for token in tokens:
        try:
            evidence = signing.loads(token, salt=TICKET_SALT)
        except signing.BadSignature as exc:
            raise ValueError("Retained source evidence failed its signature check.") from exc
        if (
            not isinstance(evidence, dict) or evidence.get("version") != 1
            or evidence.get("profile") != get_profile().key
            or evidence.get("rendition") != rendition.pk
            or not isinstance(evidence.get("page"), dict)
            or not isinstance(evidence.get("binding"), dict)
            or not isinstance(evidence.get("assets"), dict)
            or not isinstance(evidence.get("asset_sources"), dict)
        ):
            raise ValueError("Retained source evidence does not match this edition.")
        if check_scope and (
            evidence.get("draft") != (str(draft_id) if draft_id else None)
            or evidence.get("revision") != revision or evidence.get("reviewer") != reviewer.pk
        ):
            raise ValueError("The source preview is stale. Inspect and insert it again.")
        binding = evidence["binding"]
        page = evidence["page"]
        if (
            page.get("digest") != binding.get("source_digest")
            or page.get("url") != binding.get("url")
        ):
            raise ValueError("Retained source evidence is inconsistent.")
        if any(
            not isinstance(url, str) or not isinstance(info, dict)
            or info.get("digest") not in evidence["assets"]
            or evidence["assets"][info["digest"]] != {
                "size": info.get("size"), "media_type": info.get("media_type"),
            }
            for url, info in evidence["asset_sources"].items()
        ) or set(evidence["assets"]) != {
            info.get("digest") for info in evidence["asset_sources"].values()
        }:
            raise ValueError("Retained source asset evidence is inconsistent.")
        try:
            read_blob(page["digest"])
            for digest, expected in evidence["assets"].items():
                blob = Blob.objects.filter(pk=digest).first()
                if (
                    not blob or expected != {"size": blob.size, "media_type": blob.media_type}
                    or len(read_blob(digest)) != blob.size
                ):
                    raise ValueError(
                        f"Retained asset evidence failed its integrity check: {digest}"
                    )
                if digest in assets and assets[digest] != expected:
                    raise ValueError("Conflicting retained asset evidence.")
                assets[digest] = expected
        except (OSError, KeyError) as exc:
            raise ValueError("Retained source or asset is unavailable or corrupt.") from exc
    return assets


def original_section(rendition, target, *, allowed_assets=None):
    proposal = preview_import({
        "version": SCHEMA_VERSION, "title": rendition.title,
        "metadata": rendition.metadata, "html": rendition.html,
    })
    soup = BeautifulSoup(proposal["document"]["html"], "html.parser")
    section = soup.find("section", id=target)
    if section is None:
        raise ValueError("Choose a section from this original edition.")
    assets = {image["src"].split("/")[2] for image in section.select("img")}
    if allowed_assets is not None and not assets <= set(allowed_assets):
        raise ValueError("This original section uses images not bound to this draft.")
    bindings = Blob.objects.in_bulk(assets)
    for digest in assets:
        if digest not in bindings or len(read_blob(digest)) != bindings[digest].size:
            raise ValueError("An original section asset failed its integrity check: " + digest)
    part = next(
        (part for part in rendition.structure.get("parts", []) if part.get("id") == target), {},
    )
    return {
        "html": str(section), "title": part.get("title", target),
        "url": part.get("url", ""), "role": part.get("role", "chapter"),
        "target": target, "repairs": proposal["conversion"]["repairs"],
        "binding": {"rendition": rendition.pk, "output_digest": rendition.output_digest},
    }


def section_candidates(entry, blocks):
    candidates = []
    for index, node in enumerate(blocks):
        if node.name not in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            continue
        end = next((
            i for i in range(index + 1, len(blocks))
            if blocks[i].name in {"h1", "h2", "h3", "h4", "h5", "h6"}
            and blocks[i].name <= node.name
        ), len(blocks))
        candidates.append({
            "title": node.get_text(" ", strip=True), "kind": "Parsed heading range",
            "blocks": list(range(index, end)),
        })
    seen = set()
    excerpts = SourceExcerptRevision.objects.filter(
        capture__site__profile=get_profile().key, capture__url=entry["url"],
    ).order_by("definition", "-revision")
    for excerpt in excerpts:
        if excerpt.definition in seen:
            continue
        seen.add(excerpt.definition)
        if not excerpt.deleted and excerpt.source_digest == entry["digest"]:
            candidates.append({
                "title": excerpt.name, "kind": "Saved excerpt", "blocks": excerpt.blocks,
            })
    return candidates


def source_page(rendition, page_number, selection=None, *, allowed_assets=None,
                require_images=False):
    manifest = rendition.snapshot.manifest
    try:
        if (
            not isinstance(manifest, dict) or not isinstance(manifest["pages"], list)
            or not isinstance(manifest["assets"], dict)
            or any(
                not isinstance(entry, dict)
                or any(not isinstance(entry.get(key), str) for key in
                       ("url", "resolved_url", "digest"))
                or not isinstance(entry.get("headers", {}), dict)
                for entry in manifest["pages"]
            )
            or any(not isinstance(asset, dict) for asset in manifest["assets"].values())
            or snapshot_digest(manifest) != rendition.snapshot.digest
        ):
            raise ValueError("The retained source manifest failed its integrity check.")
    except (KeyError, TypeError) as exc:
        raise ValueError("The retained source manifest failed its integrity check.") from exc
    if type(page_number) is not int or not 0 <= page_number < len(manifest["pages"]):
        raise ValueError("Choose a retained page from this edition.")
    entry = manifest["pages"][page_number]
    soup, blocks = source_blocks(entry)
    result = {
        "pages": [{"number": i, "url": page["url"]} for i, page in enumerate(manifest["pages"])],
        "page": page_number, "url": entry["url"], "source_digest": entry["digest"],
        "snapshot": rendition.snapshot_id, "snapshot_digest": rendition.snapshot.digest,
        "blocks": [
            {"index": i, "tag": node.name, "text": node.get_text(" ", strip=True)[:500]
             or node.get("alt", "") or "(Image or divider)"}
            for i, node in enumerate(blocks)
        ],
        "candidates": section_candidates(entry, blocks),
        "original_sections": [
            {"id": part["id"], "title": part["title"], "url": part.get("url", ""),
             "role": part.get("role", "chapter")}
            for part in rendition.structure.get("parts", []) if part.get("id")
        ],
    }
    if selection is None:
        return result
    if (
        not isinstance(selection, list) or not 1 <= len(selection) <= MAX_SELECTION
        or any(type(i) is not int or not 0 <= i < len(blocks) for i in selection)
        or selection != sorted(set(selection))
    ):
        raise ValueError("Choose 1-2000 distinct source blocks in source order.")
    if require_images:
        for index in selection:
            root = blocks[index]
            for image in ([root] if root.name == "img" else root.find_all("img")):
                remote = image_url(image, entry["url"])
                if not manifest["assets"].get(remote, {}).get("digest"):
                    raise ValueError(
                        f"Selected image is not retained: {remote}. Import the source "
                        "with its images before inserting it."
                    )
    for entry_asset in manifest["assets"].values():
        if "digest" not in entry_asset:
            continue
        digest = entry_asset["digest"]
        blob = Blob.objects.filter(pk=digest).first()
        if (
            blob is None or blob.size != entry_asset.get("size")
            or blob.media_type != entry_asset.get("media_type")
            or len(read_blob(digest)) != blob.size
        ):
            raise ValueError(f"Retained asset failed its integrity check: {digest}")
    body = soup.new_tag("div")
    targets = {}
    for i, original in enumerate(blocks):
        node = deepcopy(original)
        anchors = []
        for previous in original.previous_siblings:
            if getattr(previous, "name", None) is None:
                if str(previous).strip():
                    break
                continue
            if (
                previous.name not in {"a", "span"} or previous.get_text(strip=True)
                or previous.find(["img", "hr"])
                or not (previous.get("id") or previous.get("name"))
            ):
                break
            anchors.append(previous)
        if anchors:
            wrapper = soup.new_tag("div")
            for anchor in reversed(anchors):
                wrapper.append(deepcopy(anchor))
            wrapper.append(node)
            node = wrapper
        node.__dict__["_reviewed_excerpt_block"] = i
        for target in [node, *node.find_all(True)]:
            for key in ("id", "name"):
                if target.get(key):
                    raw = str(target[key])
                    targets.setdefault(make_id("c1", raw), urljoin(entry["url"], "#" + raw))
        body.append(node)
    for node in list(body.find_all(UNSAFE)):
        node.decompose()
    part = Part(entry["url"], "", use_source_headings=True)
    html, _ = normalize(
        [(part, body)], Source("", {}, [part], False), manifest["assets"], review=True,
    )
    normalized = BeautifulSoup(html, "html.parser")
    chosen = [normalized.select_one(f'[data-excerpt-block="{i}"]') for i in selection]
    if any(node is None for node in chosen):
        raise ValueError("A selected source block could not be preserved; choose other blocks.")
    retained_ids = {node["id"] for root in chosen for node in [root, *root.select("[id]")]
                    if node.get("id")}
    external_links = 0
    omitted_generated_backlinks = 0
    for root in chosen:
        for link in [root, *root.select("a[href]")]:
            href = link.get("href", "")
            if not href.startswith("#") or unquote(href[1:]) in retained_ids:
                continue
            target = unquote(href[1:])
            if target == "c1":
                link["href"] = entry["url"]
            elif target in targets:
                link["href"] = targets[target]
            elif "note-backlink" in link.get("class", []):
                # Normalization may add a return link to a generated reference ID.
                # It is not original source content or a target outside the selection.
                link.decompose()
                omitted_generated_backlinks += 1
                continue
            else:
                raise ValueError("A link outside this selection has no exact source target.")
            external_links += 1
        for node in [root, *root.find_all(True)]:
            node.attrs.pop("data-excerpt-block", None)
    raw = "".join(str(node) for node in chosen)
    proposal = preview_import({
        "version": SCHEMA_VERSION, "title": "Retained source selection", "metadata": {},
        "html": "<section>" + raw + "</section>",
    })
    document = canonical_document(proposal["document"])
    assets = {node["src"].split("/")[2]
              for node in BeautifulSoup(document["html"], "html.parser").select("img")}
    if allowed_assets is not None and not assets <= set(allowed_assets):
        raise ValueError(
            "This selection uses retained images not bound to this draft. "
            "Start a fresh draft from original retained source to include these assets."
        )
    # The single wrapper groups a source selection; it is not a reusable excerpt.
    parsed = BeautifulSoup(document["html"], "html.parser")
    result.update({
        "html": parsed.section.decode_contents(),
        "selection": selection, "external_links": external_links,
        "omitted_generated_backlinks": omitted_generated_backlinks,
        "repairs": proposal["conversion"]["repairs"],
        "binding": {
            "snapshot": rendition.snapshot_id, "snapshot_digest": rendition.snapshot.digest,
            "manifest_digest": fingerprint(manifest),
            "page": page_number, "url": entry["url"], "source_digest": entry["digest"],
            "blocks": selection, "document_digest": fingerprint(document),
        },
        "source_entry": deepcopy(entry),
        "asset_bindings": {
            digest: {"size": bindings.size, "media_type": bindings.media_type}
            for digest, bindings in Blob.objects.in_bulk(assets).items()
        },
        "asset_sources": {
            url: deepcopy(info) for url, info in manifest["assets"].items()
            if info.get("digest") in assets
        },
    })
    return result
