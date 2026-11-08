from dataclasses import asdict

from django.db import transaction

from library.models import (
    BookMembershipDecision,
    BookMembershipGeneration,
    ContentOrganization,
    CrawlCapture,
    Document,
    Job,
    Rendition,
    Snapshot,
    SourceCorrection,
)
from library.profile import get_profile
from library.services.fetch import MAX_PAGES, canonical_url
from library.services.organizations import (
    entries,
    guessed_role,
    lock_organization,
    retained_manifest,
    stored_source,
    validate_spec,
)
from library.services.pipeline import fingerprint, format_rendition, publish, snapshot_digest
from library.services.semantic_documents import fingerprint as evidence_fingerprint


def _generation_spec(book, members):
    source = stored_source(book.url)
    if not source.book:
        raise ValueError("The retained book contents page is not a supported book index.")
    member_by_url = {entry.url: entry for entry in members}
    if not member_by_url:
        raise ValueError("Attach at least one retained source URL before generating a book.")

    organization = ContentOrganization.objects.filter(entry=book).first()
    title = (
        organization.specification.get("title", "")
        if organization else ""
    ) or source.title or book.title
    parts = []
    ordered_members = set()
    for source_part in source.parts:
        url = canonical_url(source_part.url)
        if url != book.url and url not in member_by_url:
            continue
        part = {
            key: value for key, value in asdict(source_part).items()
            if key in {
                "url", "title", "group", "use_source_headings", "role", "section", "excerpt",
            } and value is not None
        }
        part["url"] = url
        if url != book.url:
            part["role"] = (
                source_part.role
                if source_part.section or url == book.url
                else guessed_role(source_part.title)
            )
            ordered_members.add(url)
        parts.append(part)
    if not any(part["url"] == book.url for part in parts):
        raise ValueError("The retained contents page has no book section to generate.")

    warnings = []
    for url in sorted(
        {canonical_url(part.url) for part in source.parts} - member_by_url.keys() - {book.url}
    ):
        warnings.append(
            f"Contents-page source {url} is not current catalogue membership and was excluded."
        )
    unresolved = sorted(set(member_by_url) - ordered_members)
    for url in unresolved:
        entry = member_by_url[url]
        parts.append({
            "url": url,
            "title": entry.title.strip() or url,
            "role": guessed_role(entry.title),
            "group": "",
            "use_source_headings": True,
        })
        warnings.append(
            f"No retained contents-page order exists for {url}; it was appended by URL."
        )
    if len(parts) > MAX_PAGES:
        raise ValueError(f"A generated book cannot exceed {MAX_PAGES} retained parts.")
    return validate_spec({
        "url": book.url,
        "title": title,
        "book": True,
        "parts": parts,
    }), warnings


def _source_binding(book, members, manifest):
    urls = list(dict.fromkeys([book.url, *[entry.url for entry in members]]))
    snapshots = list(Snapshot.objects.order_by("pk"))
    selected_pages = {
        canonical_url(page["url"]): page for page in manifest["pages"]
    }
    snapshots_by_url = {}
    for snapshot in snapshots:
        for page in snapshot.manifest.get("pages", []):
            url = canonical_url(page["url"])
            if url in urls:
                snapshots_by_url.setdefault(url, []).append((snapshot, page))

    captures = {}
    for capture in CrawlCapture.objects.filter(
        site__profile=get_profile().key, url__in=urls,
    ).order_by("pk"):
        captures[capture.url] = capture

    sources = {}
    for url, selected_page in selected_pages.items():
        capture = captures.get(url)
        if capture:
            sources[url] = {
                "kind": "capture",
                "id": capture.pk,
                "page": selected_page,
            }
            continue
        matching = next(
            (
                (snapshot, page)
                for snapshot, page in snapshots_by_url.get(url, [])
                if page == selected_page
            ),
            None,
        )
        if matching is None:
            raise ValueError(f"Unable to bind retained snapshot evidence for {url}.")
        snapshot, _ = matching
        sources[url] = {
            "kind": "snapshot",
            "id": snapshot.pk,
            "snapshot_digest": snapshot.digest,
            "page": selected_page,
        }

    decisions = {}
    entry_ids = [entry.pk for entry in members]
    for decision in BookMembershipDecision.objects.filter(
        entry_id__in=entry_ids,
    ).order_by("pk"):
        decisions[decision.entry_id] = {
            "id": decision.pk,
            "before": decision.before,
            "after": decision.after,
            "undo_of": decision.undo_of_id,
            "reviewer": decision.reviewer_id,
            "reason": decision.reason,
            "created_at": str(decision.created_at),
        }
    assets = {
        url: {
            "digest": asset.get("digest"),
            "media_type": asset.get("media_type"),
            "size": asset.get("size"),
            "error": asset.get("error"),
        }
        for url, asset in sorted(manifest.get("assets", {}).items())
    }
    asset_sources = {}
    for asset_url, asset in manifest.get("assets", {}).items():
        source = next(
            (
                snapshot for snapshot in snapshots
                if any(
                    canonical_url(page["url"]) in urls
                    for page in snapshot.manifest.get("pages", [])
                )
                and snapshot.manifest.get("assets", {}).get(asset_url) == asset
            ),
            None,
        )
        if source is None:
            raise ValueError(f"Unable to bind retained asset evidence for {asset_url}.")
        asset_sources[asset_url] = {
            "snapshot": source.pk,
            "snapshot_digest": source.digest,
        }
    return {
        "profile": get_profile().key,
        "book_entry": book.pk,
        "book_url": book.url,
        "book_title": book.title,
        "book_membership_reviewed": book.membership_reviewed,
        "membership": [
            {
                "entry": entry.pk,
                "url": entry.url,
                "title": entry.title,
                "reviewed": entry.membership_reviewed,
                "decision": decisions.get(entry.pk),
            }
            for entry in members
        ],
        "sources": sources,
        "asset_sources": asset_sources,
        "assets": assets,
        "corrections": list(
            SourceCorrection.objects.filter(capture__url__in=urls)
            .order_by("capture_id", "revision").values(
                "pk", "capture_id", "revision", "source_digest", "profile",
                "adapter_version", "schema_version", "original", "expected",
                "imported_from",
            )
        ),
    }


def preview_membership_generation(book):
    book = entries().filter(pk=book.pk, book__isnull=True).first()
    if book is None:
        raise ValueError("Choose a root catalogue work to generate.")
    members = list(
        entries().filter(book=book).order_by("url", "pk")
    )
    spec, warnings = _generation_spec(book, members)
    urls = [book.url, *[entry.url for entry in members]]
    if Job.objects.filter(
        document__url__in=urls, status__in=[Job.Status.QUEUED, Job.Status.RUNNING],
    ).exists():
        raise ValueError("An affected work has an active import. Wait and preview again.")
    manifest, asset_warnings = retained_manifest(spec)
    binding = _source_binding(book, members, manifest)
    source, html, structure, stylesheet, asset_warnings = format_rendition(
        manifest, asset_warnings, organization=spec,
    )
    digest = fingerprint([html, structure, source.metadata, source.title, stylesheet])
    existing = Document.objects.filter(url=book.url).first()
    revision = fingerprint({
        "binding": binding,
        "organization": spec,
        "manifest_digest": snapshot_digest(manifest),
        "versions": list(
            Rendition.objects.filter(document__url__in=urls)
            .order_by("pk").values_list("pk", "output_digest")
        ),
        "book_organization": (
            ContentOrganization.objects.filter(entry=book)
            .values("pk", "specification", "rendition_id").first()
        ),
    })
    return {
        "book": book.pk,
        "url": book.url,
        "title": spec["title"],
        "members": [entry.url for entry in members],
        "specification": spec,
        "manifest": manifest,
        "binding": binding,
        "warnings": warnings + asset_warnings,
        "revision": revision,
        "digest": digest,
        "existing_rendition": (
            existing.latest().pk
            if existing and existing.latest() and existing.latest().output_digest == digest
            else None
        ),
    }


@transaction.atomic
def generate_from_membership(book, reviewer, reason, expected_revision, expected_digest):
    reason = reason.strip() if isinstance(reason, str) else ""
    if not reason or len(reason) > 2000:
        raise ValueError("Explain this source-generated book in 1-2000 characters.")
    lock_organization()
    fresh = preview_membership_generation(book)
    if (
        fresh["revision"] != expected_revision
        or fresh["digest"] != expected_digest
    ):
        raise ValueError("Membership, retained sources or output changed since preview.")
    binding = fresh["binding"]
    binding_digest = evidence_fingerprint(binding)
    document, _ = Document.objects.get_or_create(url=fresh["url"])
    job = Job.objects.create(document=document, mode=Job.Mode.REFORMAT)
    rendition = publish(
        job,
        fresh["manifest"],
        fresh["warnings"],
        organization=fresh["specification"],
        register_membership=False,
        generation_evidence={"book_membership_binding": binding},
    )
    if rendition.output_digest != fresh["digest"]:
        raise ValueError("Generated output differs from the reviewed preview.")
    book_entry = entries().get(pk=fresh["book"])
    ContentOrganization.objects.update_or_create(
        entry=book_entry,
        defaults={
            "specification": fresh["specification"],
            "rendition": rendition,
        },
    )
    BookMembershipGeneration.objects.get_or_create(
        rendition=rendition,
        binding_digest=binding_digest,
        defaults={
            "binding": binding,
            "reviewer": reviewer,
            "reason": reason,
        },
    )
    return rendition
