"""Explicit publication of exact saved semantic revisions, never verification."""

from copy import deepcopy

from bs4 import BeautifulSoup
from django.db import transaction
from django.db.models import F

from library import versions
from library.models import Blob, DocumentPublication, Rendition, RenditionAsset
from library.profile import get_profile
from library.services.book_views import publication_toc
from library.services.document_edits import (
    DocumentEditConflict,
    saved_source_tickets,
    validate_editor_metadata,
)
from library.services.editor_sources import ticket_evidence
from library.services.editor_structure import section_structure
from library.services.semantic_documents import canonical_document, document_issues, fingerprint
from library.services.storage import read_blob
from library.sources.adapters import adapter_for

PUBLICATION_VERSION = 4


def prepare_publication(draft, expected_revision):
    from library.services.document_lineage import node_is_archived

    if node_is_archived(draft.rendition.document, f"history:{draft.pk}"):
        raise DocumentEditConflict(
            "This correction history is archived. Restore it before previewing publication."
        )
    if type(expected_revision) is not int or expected_revision < 1:
        raise ValueError("Preview an exact saved revision before publishing.")
    if draft.profile != get_profile().key:
        raise ValueError("Switch to the draft's profile before publishing.")
    source = draft.rendition
    adapter_for(source.document.url)
    revision = draft.revisions.first()
    if revision is None or revision.revision != expected_revision:
        raise DocumentEditConflict("The draft changed. Preview its latest saved revision.")
    if (
        fingerprint(draft.document) != draft.document_digest
        or fingerprint(draft.evidence) != draft.evidence_digest
        or fingerprint(revision.document) != revision.document_digest
    ):
        raise ValueError("Document publication evidence failed its integrity check.")
    evidence = draft.evidence
    origin = evidence.get("correction_origin", {})
    fresh = evidence["kind"] == "fresh-retained-source"
    if fresh:
        from library.services.fresh_document_drafts import anchor_binding

        if evidence["anchor"] != anchor_binding(source):
            raise DocumentEditConflict("The fresh draft's anchor changed. Start a new draft.")
    if (
        source.snapshot.digest != evidence["snapshot_digest"]
        or source.snapshot_id != evidence["snapshot"]
        or source.snapshot.manifest != evidence["manifest"]
    ):
        raise DocumentEditConflict("The retained snapshot evidence changed. Start a new draft.")
    if not fresh and (
        source.html != evidence["generated_html"]
        or source.stylesheet != evidence["stylesheet"]
        or source.structure != evidence["structure"]
        or source.snapshot.digest != evidence["snapshot_digest"]
        or source.snapshot_id != evidence["snapshot"]
        or source.identity != evidence["identity"]
        or source.output_digest != evidence["output_digest"]
        or source.snapshot.manifest != evidence["manifest"]
        or source.title != origin.get("generated_title", draft.document["title"])
        or source.metadata != origin.get("generated_metadata", draft.document["metadata"])
    ):
        raise DocumentEditConflict("The retained source evidence changed. Start a new draft.")
    document = canonical_document(revision.document)
    document["metadata"] = validate_editor_metadata(
        draft.document["metadata"], document["metadata"],
    )
    document = canonical_document(document)
    source_tickets = saved_source_tickets(draft, revision)
    extra_assets = ticket_evidence(source_tickets, rendition=source)
    issues = document_issues(document, set(evidence["assets"]) | set(extra_assets))
    if issues:
        raise ValueError("Resolve document issues before publishing: " + "; ".join(issues))
    soup = BeautifulSoup(document["html"], "html.parser")
    assets = sorted({image["src"].split("/")[2] for image in soup.select("img")})
    bindings = (
        Blob.objects.in_bulk(evidence["assets"]) if fresh else
        {asset.blob_id: asset.blob for asset in source.assets.select_related("blob")}
    )
    bindings.update(Blob.objects.in_bulk(extra_assets))
    for digest in assets:
        if digest not in bindings:
            raise ValueError(f"Publication asset is no longer bound to the source: {digest}")
        try:
            data = read_blob(digest)
        except OSError as exc:
            raise ValueError(f"Publication asset is unavailable or corrupt: {digest}") from exc
        if len(data) != bindings[digest].size:
            raise ValueError(f"Publication asset size does not match its evidence: {digest}")
        if (
            fresh and digest in evidence["asset_bindings"]
            and evidence["asset_bindings"][digest] != {
                "size": bindings[digest].size, "media_type": bindings[digest].media_type,
            }
        ):
            raise ValueError(f"Publication asset differs from fresh draft evidence: {digest}")
    toc = publication_toc(soup)
    structure = {
        **section_structure(soup, evidence["structure"],
                            document["metadata"].get("content_organization")),
        "toc": toc,
    }
    html = canonical_document({**document, "html": str(soup)})["html"]
    output = {
        "title": document["title"], "metadata": document["metadata"], "html": html,
        "structure": structure, "stylesheet": evidence["stylesheet"],
        "warnings": deepcopy(evidence["warnings"]),
        "app_version": versions.APP_VERSION,
        "adapter_version": evidence["versions"]["adapter"],
        "format_version": evidence["versions"]["format"],
    }
    digest = fingerprint({
        "publication_version": PUBLICATION_VERSION, "draft": str(draft.pk),
        "revision": revision.pk, "document_digest": revision.document_digest,
        "evidence_digest": draft.evidence_digest, "output": output, "assets": assets,
        "review": revision.review, "verified_sections": revision.verified_sections,
        "editorial": revision.editorial,
        **({"source_tickets": source_tickets} if source_tickets else {}),
    })
    return {"revision": revision, "output": output, "assets": assets, "digest": digest}


@transaction.atomic
def publish_revision(draft, reviewer, expected_revision, preview_digest):
    # Share the draft-save lock, including on SQLite.
    Rendition.objects.filter(pk=draft.rendition_id).update(id=F("id"))
    draft.refresh_from_db()
    candidate = prepare_publication(draft, expected_revision)
    if preview_digest != candidate["digest"]:
        raise DocumentEditConflict("The publication preview changed. Review it again.")
    revision = candidate["revision"]
    previous = DocumentPublication.objects.filter(revision=revision).first()
    if previous:
        if previous.preview_digest != candidate["digest"]:
            raise DocumentEditConflict(
                "This revision was published with another preview. Save a new revision "
                "before publishing under the current rules."
            )
        return previous
    source = draft.rendition
    output = candidate["output"]
    rendition = Rendition.objects.create(
        document=source.document, snapshot=source.snapshot,
        identity=fingerprint(["document-publication", candidate["digest"]]),
        output_digest=fingerprint([
            output["html"], output["structure"], output["metadata"],
            output["title"], output["stylesheet"],
        ]),
        **output,
    )
    RenditionAsset.objects.bulk_create([
        RenditionAsset(rendition=rendition, blob_id=digest) for digest in candidate["assets"]
    ])
    return DocumentPublication.objects.create(
        revision=revision, rendition=rendition, preview_digest=candidate["digest"],
        publication_version=PUBLICATION_VERSION, reviewer=reviewer,
    )
