"""Offline regeneration into separate editor drafts, never intermediate editions."""

import json
from copy import deepcopy
from dataclasses import asdict

from django.db import transaction
from django.db.models import F

from library import versions
from library.models import Blob, DocumentDraftBase, Rendition
from library.profile import get_profile
from library.services.document_edits import DocumentEditConflict
from library.services.pipeline import format_rendition, snapshot_digest
from library.services.semantic_documents import SCHEMA_VERSION, document_issues, fingerprint
from library.services.semantic_import import preview_import
from library.services.storage import read_blob
from library.sources.adapters import adapter_for


def anchor_binding(rendition):
    return {
        "rendition": rendition.pk, "identity": rendition.identity,
        "output_digest": rendition.output_digest, "snapshot": rendition.snapshot_id,
        "snapshot_digest": rendition.snapshot.digest,
    }


def preview_fresh_draft(rendition, *, original_source=False):
    """Read retained bytes under current policy; bind the actual generation inputs."""
    adapter_for(rendition.document.url)
    snapshot = rendition.snapshot
    if snapshot.document_id != rendition.document_id:
        raise ValueError("Choose a retained snapshot belonging to this document.")
    manifest = deepcopy(snapshot.manifest)
    if snapshot_digest(manifest) != snapshot.digest:
        raise ValueError("The retained snapshot failed its integrity check.")
    for page in manifest["pages"]:
        read_blob(page["digest"])
    assets = {}
    for entry in manifest["assets"].values():
        if "digest" not in entry:
            continue
        digest = entry["digest"]
        blob = Blob.objects.filter(pk=digest).first()
        if blob is None:
            raise ValueError(f"Retained image has no blob record: {digest}")
        data = read_blob(digest)
        if len(data) != blob.size or len(data) != entry["size"]:
            raise ValueError(f"Retained image size differs from its manifest: {digest}")
        if blob.media_type != entry["media_type"]:
            raise ValueError(f"Retained image type differs from its manifest: {digest}")
        assets[digest] = {"size": blob.size, "media_type": blob.media_type}
    provenance = {}
    source, html, structure, stylesheet, warnings = format_rendition(
        manifest, deepcopy(snapshot.warnings), provenance=provenance,
        original_source=original_source,
    )
    profile = get_profile()
    configuration = json.loads(json.dumps(asdict(profile)))
    evidence = {
        "kind": "fresh-retained-source", "generation_version": 1,
        "input_policy": provenance["input_policy"],
        "anchor": anchor_binding(rendition), "rendition": rendition.pk,
        "snapshot": snapshot.pk, "snapshot_digest": snapshot.digest, "manifest": manifest,
        "snapshot_fetched_at": snapshot.fetched_at.isoformat(),
        "generated_html": html, "generated_title": source.title,
        "generated_metadata": source.metadata, "structure": structure,
        "stylesheet": stylesheet, "warnings": warnings,
        "profile": profile.key, "profile_configuration": configuration,
        "profile_digest": fingerprint(configuration),
        "versions": {
            "app": versions.APP_VERSION, "adapter": profile.adapter_version,
            "format": versions.FORMAT_VERSION, "document": SCHEMA_VERSION,
        },
        "assets": sorted(assets), "asset_bindings": assets,
        "generation": provenance,
        "legacy_application": {
            "state": "excluded from original-source generation" if original_source else
            "applied once during generation; never reapply to this draft",
            "saved_editor_revisions": "not replayed",
        },
    }
    proposal = preview_import({
        "version": SCHEMA_VERSION, "title": source.title,
        "metadata": source.metadata, "html": html,
    }, binding={"generation_digest": fingerprint(evidence)})
    evidence["import"] = proposal["conversion"]
    document = proposal["document"]
    digest = fingerprint({"document": document, "evidence": evidence})
    return {
        "document": document, "evidence": evidence, "digest": digest,
        "repairs": proposal["conversion"]["repairs"],
        "issues": document_issues(document, set(assets)),
    }


@transaction.atomic
def create_fresh_draft(rendition, reviewer, preview_digest, *, original_source=False):
    Rendition.objects.filter(pk=rendition.pk).update(id=F("id"))
    rendition = Rendition.objects.select_related("document", "snapshot").get(pk=rendition.pk)
    proposal = preview_fresh_draft(rendition, original_source=original_source)
    if preview_digest != proposal["digest"]:
        raise DocumentEditConflict(
            "Fresh generation changed. Review a new preview before starting."
        )
    evidence = deepcopy(proposal["evidence"])
    evidence["confirmation"] = {
        "preview_digest": proposal["digest"], "explicitly_approved": True,
    }
    return DocumentDraftBase.objects.create(
        rendition=rendition, profile=get_profile().key, reviewer=reviewer,
        document=proposal["document"], document_digest=fingerprint(proposal["document"]),
        evidence=evidence, evidence_digest=fingerprint(evidence),
    )
