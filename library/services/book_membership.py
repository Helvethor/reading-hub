"""Catalogue ownership changes independent of corrected document sections."""

from django.db import transaction
from django.db.models import Q

from library.models import BookMembershipDecision, Document, Job
from library.profile import get_profile
from library.services.fetch import canonical_url
from library.services.organizations import (
    entries,
    entry_for_url,
    lock_organization,
    retained_manifest,
    stored_source,
)
from library.services.pipeline import fingerprint, format_rendition, publish
from library.sources.adapters import adapter_for


def state(entry):
    return {"book": entry.book_id, "reviewed": entry.membership_reviewed}


def catalogue_book(version):
    entry = entries().filter(url=version.document.url).select_related("book").first()
    return entry.book if entry and entry.book_id else entry


def standalone_preview(url):
    document = Document.objects.filter(url=url).first()
    rendition = document.latest() if document else None
    if rendition:
        return {"rendition": rendition.pk, "digest": rendition.output_digest}
    source = stored_source(url)
    spec = {
        "url": url, "title": source.title, "book": False,
        "parts": [{"url": url, "title": source.title, "role": "chapter",
                   "group": "", "use_source_headings": True}],
    }
    manifest, warnings = retained_manifest(spec)
    source, html, structure, stylesheet, warnings = format_rendition(manifest, warnings, spec)
    if not html.strip():
        raise ValueError("The retained page has no standalone content.")
    return {
        "spec": spec, "manifest_digest": fingerprint(manifest),
        "digest": fingerprint([html, structure, source.metadata, source.title, stylesheet]),
        "html": html, "warnings": warnings,
    }


def preview_membership(book, url, action, *, undo=None):
    if book is None:
        raise ValueError("Import this work into the catalogue before changing membership.")
    if book.site.profile != get_profile().key or book.book_id:
        raise ValueError("Choose a root work in the active catalogue profile.")
    parent = Document.objects.filter(url=book.url).first()
    edition = parent.latest() if parent else None
    if not edition or not parent.renditions.filter(structure__book=True).exists():
        raise ValueError("The catalogue work needs an available book edition.")
    url = canonical_url(url)
    adapter_for(url)
    if url == book.url:
        raise ValueError("The book's own source URL cannot be attached or detached.")
    source = stored_source(url)  # Requires retained evidence; never fetches.
    retained, _ = retained_manifest({
        "url": url, "parts": [{"url": url}],
    })
    entry = entries().filter(url=url).first()
    before = state(entry) if entry else {"book": None, "reviewed": False}
    if action not in {"attach", "detach"}:
        raise ValueError("Choose Attach or Detach.")
    if action == "attach":
        if source.book or (entry and entry.chapters.exists()):
            raise ValueError("Nested books cannot be attached as a source page.")
        if before["book"] is not None:
            raise ValueError("This URL already belongs to a book. Detach it there first.")
        after = {"book": book.pk, "reviewed": True}
    else:
        if before["book"] != book.pk:
            raise ValueError("This URL is not a member of the selected book.")
        after = {"book": None, "reviewed": True}
    if undo:
        if undo.entry.site.profile != get_profile().key or undo.entry.url != url:
            raise ValueError("Choose a membership decision in this profile.")
        if before != undo.after or undo.entry_id != (entry.pk if entry else None):
            raise ValueError("Membership changed after this decision; undo is unavailable.")
        latest = BookMembershipDecision.objects.filter(entry=entry).first()
        if not latest or latest.pk != undo.pk:
            raise ValueError("A newer membership decision requires a fresh preview.")
        # Undo is itself explicit, so crawlers must not resurrect a detached link.
        after = {**undo.before, "reviewed": True}
    urls = [book.url, url]
    if Job.objects.filter(
        document__url__in=urls, status__in=[Job.Status.QUEUED, Job.Status.RUNNING],
    ).exists():
        raise ValueError("An affected work has an active import. Wait and preview again.")
    standalone = standalone_preview(url) if after["book"] is None else None
    return {
        "book": book.pk, "url": url, "action": action, "entry": entry.pk if entry else None,
        "before": before, "after": after, "profile": get_profile().key,
        "source_title": source.title, "parent_rendition": edition.pk,
        "source_manifest_digest": fingerprint(retained),
        "standalone": standalone, "undo": undo.pk if undo else None,
        "last_decision": (
            BookMembershipDecision.objects.filter(entry=entry).values_list("pk", flat=True).first()
            if entry else None
        ),
    }


@transaction.atomic
def commit_membership(payload, reviewer, reason):
    reason = reason.strip()
    if not reason or len(reason) > 2000:
        raise ValueError("Explain the membership change in 1-2000 characters.")
    lock_organization()
    book = entries().filter(pk=payload["book"]).first()
    undo = (
        BookMembershipDecision.objects.select_related("entry__site").get(pk=payload["undo"])
        if payload.get("undo") else None
    )
    fresh = preview_membership(book, payload["url"], payload["action"], undo=undo)
    if fingerprint(fresh) != fingerprint(payload):
        raise ValueError("Membership, source or routing changed since preview. Preview again.")
    entry = entry_for_url(fresh["url"], fresh["source_title"])
    standalone = fresh["standalone"]
    standalone_binding = standalone
    if standalone and "spec" in standalone:
        document, _ = Document.objects.get_or_create(url=fresh["url"])
        manifest, warnings = retained_manifest(standalone["spec"])
        job = Job.objects.create(document=document, mode=Job.Mode.REFORMAT)
        rendition = publish(
            job, manifest, warnings, organization=standalone["spec"], register_membership=False,
        )
        if rendition.output_digest != standalone["digest"]:
            raise ValueError("The standalone edition differs from its preview.")
        standalone_binding = {"rendition": rendition.pk, "digest": rendition.output_digest}
    entry.book_id = fresh["after"]["book"]
    entry.membership_reviewed = True
    entry.save(update_fields=["book", "membership_reviewed"])
    return BookMembershipDecision.objects.create(
        entry=entry, reviewer=reviewer, reason=reason,
        before=fresh["before"], after=fresh["after"], undo_of=undo,
        evidence={
            **{key: value for key, value in fresh.items() if key != "standalone"},
            "standalone": standalone_binding,
        },
    )


def decisions_for(book):
    return BookMembershipDecision.objects.filter(
        Q(after__book=book.pk) | Q(before__book=book.pk),
        entry__site__profile=get_profile().key,
    ).select_related("entry", "reviewer", "undo_of")[:30]
