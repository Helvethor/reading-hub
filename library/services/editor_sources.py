"""Inert retained-source inspection and bounded structured insertion previews."""

from copy import deepcopy
from urllib.parse import unquote, urljoin

from bs4 import BeautifulSoup

from library.models import Blob
from library.services.pipeline import snapshot_digest
from library.services.semantic_documents import SCHEMA_VERSION, canonical_document, fingerprint
from library.services.semantic_import import preview_import
from library.services.source_excerpts import UNSAFE, source_blocks
from library.services.storage import read_blob
from library.sources.base import Part, Source
from library.sources.normalize import make_id, normalize

MAX_SELECTION = 100


def source_page(rendition, page_number, selection=None, *, allowed_assets=None):
    manifest = rendition.snapshot.manifest
    if snapshot_digest(manifest) != rendition.snapshot.digest:
        raise ValueError("The retained source manifest failed its integrity check.")
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
    }
    if selection is None:
        return result
    if (
        not isinstance(selection, list) or not 1 <= len(selection) <= MAX_SELECTION
        or any(type(i) is not int or not 0 <= i < len(blocks) for i in selection)
        or selection != sorted(set(selection))
    ):
        raise ValueError("Choose 1-100 distinct source blocks in source order.")
    for entry_asset in manifest["assets"].values():
        if "digest" not in entry_asset:
            continue
        digest = entry_asset["digest"]
        blob = Blob.objects.filter(pk=digest).first()
        if (
            blob is None or blob.size != entry_asset["size"]
            or blob.media_type != entry_asset["media_type"]
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
            "page": page_number, "url": entry["url"], "source_digest": entry["digest"],
            "blocks": selection, "document_digest": fingerprint(document),
        },
    })
    return result
