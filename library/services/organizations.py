"""Offline, previewed changes to the published work graph."""

from copy import deepcopy
from dataclasses import asdict
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
from django.db import transaction
from django.db.models import F, Q

from library.models import (
    Annotation,
    CatalogueEntry,
    ContentOrganization,
    ContentOrganizationDecision,
    CrawlCapture,
    CrawlSite,
    Document,
    Job,
    Rendition,
    Snapshot,
    SourceCorrection,
    URLAlias,
)
from library.profile import get_profile
from library.services.errors import ImportFailure
from library.services.fetch import MAX_PAGES, canonical_url
from library.services.storage import read_blob
from library.sources.adapters import discover
from library.sources.base import Part, parse_html

ROLES = ("preface", "chapter", "appendix", "postscript")
ANNOTATION_POLICY = (
    "Preserve all private annotations on their original immutable versions; do not move or "
    "delete them. Owners can inspect their original quotes in Preserved annotations."
)


def lock_organization():
    # A real write acquires SQLite's writer lock before checking the preview revision.
    # select_for_update alone does not serialize writers on SQLite.
    CrawlSite.objects.filter(profile=get_profile().key).update(status=F("status"))


def entries():
    return CatalogueEntry.objects.filter(site__profile=get_profile().key)


def override(url):
    return ContentOrganization.objects.filter(
        entry__site__profile=get_profile().key, entry__url=url
    ).first()


def organized_source(source, url, specification=None, *, provenance=None):
    retained = override(canonical_url(url)) if specification is None else None
    spec = (
        specification
        if specification is not None
        else (retained.specification if retained else None)
    )
    if provenance is not None:
        provenance["organization"] = {
            "id": retained.pk if retained else None,
            "rendition": retained.rendition_id if retained else None,
            "specification": deepcopy(spec),
        }
    if spec is not None:
        source.title = spec["title"]
        source.book = spec["book"]
        source.parts = [
            Part(**{key: value for key, value in part.items() if key in Part.__dataclass_fields__})
            for part in spec["parts"]
        ]
    return source


def guessed_role(title):
    title = title.lower()
    return next((role for role in ROLES if role in title), "chapter")


def stored_source(url):
    document = Document.objects.filter(url=url).first()
    rendition = document.latest() if document else None
    if rendition:
        initial = rendition.snapshot.manifest["pages"][0]
    else:
        capture = (
            CrawlCapture.objects.filter(site__profile=get_profile().key, url=url)
            .order_by("-pk")
            .first()
        )
        initial = capture.response if capture else None
        if initial is None:
            candidate_urls = {url}
            entry = entries().filter(url=url).select_related("book").first()
            if entry and entry.book_id:
                candidate_urls.add(entry.book.url)
            candidate_urls.update(
                URLAlias.objects.filter(url=url).values_list("document__url", flat=True)
            )
            for snapshot in Snapshot.objects.filter(
                document__url__in=candidate_urls,
            ).order_by("-pk"):
                initial = next(
                    (page for page in snapshot.manifest.get("pages", []) if page["url"] == url),
                    None,
                )
                if initial:
                    break
        if initial is None:
            raise ValueError(f"Missing retained page: {url}. Capture it before organizing.")
    return discover(parse_html(read_blob(initial["digest"]), initial.get("headers", {})), url)


def current_spec(url):
    retained = override(url)
    if retained:
        return deepcopy(retained.specification)
    source = stored_source(url)
    return {
        "url": url,
        "title": source.title,
        "book": source.book,
        "parts": [
            {
                **{key: value for key, value in asdict(part).items() if value is not None},
                "role": part.role if part.section or part.url == url else guessed_role(part.title),
            }
            for part in source.parts
        ],
    }


def validate_spec(value):
    if not isinstance(value, dict) or set(value) != {"url", "title", "book", "parts"}:
        raise ValueError("Each work needs url, title, book and parts.")
    spec = deepcopy(value)
    spec["url"] = canonical_url(spec["url"]) if isinstance(spec["url"], str) else ""
    if not spec["url"] or not isinstance(spec["title"], str) or not spec["title"].strip():
        raise ValueError("Each work needs a URL and a nonempty title.")
    if len(spec["title"]) > 1000 or type(spec["book"]) is not bool:
        raise ValueError("Titles must be at most 1000 characters; book must be true or false.")
    if not isinstance(spec["parts"], list) or not 1 <= len(spec["parts"]) <= MAX_PAGES:
        raise ValueError(f"Each work must contain 1-{MAX_PAGES} retained pages.")
    seen = set()
    for part_index, part in enumerate(spec["parts"]):
        if not isinstance(part, dict) or not {"url", "title", "role"} <= set(part):
            raise ValueError("Every part needs url, title and role.")
        if set(part) - {
            "url", "title", "role", "group", "use_source_headings", "section", "excerpt"
        }:
            raise ValueError("Unknown part fields.")
        if not isinstance(part["url"], str):
            raise ValueError("Part URL must be text.")
        part["url"] = canonical_url(part["url"])
        section = part.get("section", "")
        excerpt = part.get("excerpt")
        if excerpt is not None:
            from library.services.source_excerpts import (
                block_indices,
                descriptor,
                validate_definition_binding,
            )

            descriptor(excerpt)
            validate_definition_binding(excerpt, part["url"])
            if not spec["book"] or section:
                raise ValueError("Source excerpts must be book parts, not index sections.")
            for previous in spec["parts"][:part_index]:
                if previous["url"] != part["url"]:
                    continue
                other = previous.get("excerpt")
                if (not other and not previous.get("section")) or (
                    other
                    and other["source_digest"] == excerpt["source_digest"]
                    and set(block_indices(other)).intersection(block_indices(excerpt))
                ):
                    raise ValueError(
                        "Overlapping excerpts or whole-page duplicates are not allowed."
                    )
        elif any(
            previous["url"] == part["url"] and previous.get("excerpt")
            for previous in spec["parts"][:part_index]
        ) and not section:
            raise ValueError(
                "Do not combine source excerpts with their whole source page."
            )
        if not isinstance(section, str) or len(section) > 100:
            raise ValueError("Section must be a retained index-section identifier.")
        if section and (not spec["book"] or part["url"] != spec["url"]):
            raise ValueError("Index sections must belong to the book's own contents source.")
        from library.services.source_excerpts import excerpt_key

        identity = (part["url"], excerpt_key(excerpt) if excerpt else section)
        if identity in seen or (
            part["url"] in {url for url, _ in seen}
            and (not section and not excerpt or (part["url"], "") in seen)
        ):
            raise ValueError(f"Duplicate page: {part['url']}")
        seen.add(identity)
        if (
            not isinstance(part["title"], str)
            or not part["title"].strip()
            or len(part["title"]) > 1000
            or part["role"] not in ROLES
        ):
            raise ValueError("Parts need a title of 1-1000 characters and a supported role.")
        part.setdefault("group", "")
        part.setdefault("use_source_headings", False)
        if not isinstance(part["group"], str) or len(part["group"]) > 1000:
            raise ValueError("Part group must be text of at most 1000 characters.")
        if type(part["use_source_headings"]) is not bool:
            raise ValueError("use_source_headings must be true or false.")
    if not spec["book"] and (len(spec["parts"]) != 1 or spec["parts"][0]["url"] != spec["url"]):
        raise ValueError("A separate work must contain exactly its own source page.")
    return spec


def change_plan(proposed):
    """Rebuild donor books and make removed pages explicitly separate works."""
    proposed = validate_spec(proposed)
    root = proposed["url"]
    selected = {part["url"] for part in proposed["parts"]}
    attached = {part["url"] for part in proposed["parts"] if not part.get("excerpt")}
    root_entry = entries().filter(url=root).first()
    if root_entry and root_entry.book_id:
        raise ValueError("Open the parent book to detach this page before making it a book.")
    before = {root: current_spec(root)}
    after = {root: proposed}
    old_parts = {part["url"] for part in before[root]["parts"]}
    for member in entries().filter(url__in=selected).select_related("book"):
        excerpt_only = all(
            part.get("excerpt") for part in proposed["parts"] if part["url"] == member.url
        )
        if excerpt_only:
            continue
        if member.url != root and member.chapters.exists():
            raise ValueError(f"Nested books are not supported: {member.url}. Detach pages first.")
        if member.book_id and member.book.url != root:
            donor = member.book.url
            before.setdefault(donor, current_spec(donor))
            remaining = [part for part in before[donor]["parts"] if part["url"] not in attached]
            if not remaining:
                raise ValueError(f"The change would empty {donor}. Keep at least one part.")
            after[donor] = {**before[donor], "parts": remaining}
    for url in (old_parts - selected) - {root}:
        removed = [part for part in before[root]["parts"] if part["url"] == url]
        if all(part.get("excerpt") for part in removed):
            if entries().filter(url=url, book__url=root).exists():
                before.setdefault(url, current_spec(url))
                after[url] = before[url]
            continue
        before.setdefault(url, current_spec(url))
        part = next(part for part in before[root]["parts"] if part["url"] == url)
        after[url] = {
            "url": url,
            "title": part["title"],
            "book": False,
            "parts": [{**part, "group": "", "use_source_headings": True}],
        }
    for url in selected - old_parts - {root}:
        if all(part.get("excerpt") for part in proposed["parts"] if part["url"] == url):
            continue
        if not entries().filter(url=url, book__isnull=False).exists():
            before.setdefault(url, current_spec(url))
            if before[url]["book"] and url != root:
                raise ValueError(f"Cannot attach a complete book as a page: {url}.")
    # Attached standalone work overrides must also survive future crawls; their
    # specifications stay intact, while membership controls their public routing.
    for url, spec in before.items():
        after.setdefault(url, spec)
    return list(before.values()), list(after.values())


def graph_membership(specs, *, undo_of=None):
    roots = {spec["url"] for spec in specs if spec["book"]}
    membership = {}
    restored = undo_of.evidence.get("membership_before") if undo_of else None
    for spec in specs:
        if not spec["book"]:
            continue
        for part in spec["parts"]:
            url = part["url"]
            if url == spec["url"]:
                continue
            if part.get("excerpt"):
                owns_source = (
                    restored.get(url) == spec["url"]
                    if restored is not None
                    else entries().filter(url=url, book__url=spec["url"]).exists()
                )
                if not owns_source:
                    continue
                if membership.get(url) == spec["url"]:
                    continue
            if url in roots or url in membership:
                raise ValueError(f"Conflicting or nested membership: {url}")
            membership[url] = spec["url"]
    return membership


def retained_manifest(spec):
    urls = list(dict.fromkeys([spec["url"], *[part["url"] for part in spec["parts"]]]))
    pages, assets, warnings = {}, {}, []
    candidate_urls = set(urls)
    candidate_urls.update(
        entries().filter(url__in=urls, book__isnull=False)
        .values_list("book__url", flat=True)
    )
    candidate_urls.update(
        URLAlias.objects.filter(url__in=urls).values_list("document__url", flat=True)
    )
    for snapshot in Snapshot.objects.filter(
        document__url__in=candidate_urls,
    ).order_by("pk"):
        relevant = False
        for page in snapshot.manifest.get("pages", []):
            if canonical_url(page["url"]) in urls:
                pages[canonical_url(page["url"])] = page
                relevant = True
        if relevant:
            assets.update(snapshot.manifest.get("assets", {}))
    for capture in CrawlCapture.objects.filter(
        site__profile=get_profile().key, url__in=urls
    ).order_by("pk"):
        pages[capture.url] = {**capture.response, "url": capture.url}
    missing = [url for url in urls if url not in pages]
    if missing:
        raise ValueError("Missing retained pages: " + ", ".join(missing))
    manifest = {
        "pages": [pages[url] for url in urls],
        "assets": assets,
        "parts": spec["parts"],
        "organization": spec,
    }
    return manifest, warnings


def revision(specs):
    from library.services.pipeline import fingerprint

    urls = sorted(
        {spec["url"] for spec in specs} | {part["url"] for spec in specs for part in spec["parts"]}
    )
    captures = CrawlCapture.objects.filter(site__profile=get_profile().key, url__in=urls)
    return fingerprint(
        {
            "profile": get_profile().key,
            "adapter": get_profile().adapter_version,
            "decisions": list(
                ContentOrganizationDecision.objects.filter(profile=get_profile().key).values_list(
                    "pk", flat=True
                )[:1]
            ),
            "entries": list(
                entries()
                .filter(Q(url__in=urls) | Q(book__url__in=urls))
                .order_by("pk")
                .values("pk", "url", "book_id", "discovery_only")
            ),
            "captures": list(captures.order_by("pk").values("pk", "response", "discovery_only")),
            "corrections": list(
                SourceCorrection.objects.filter(capture__in=captures)
                .order_by("pk")
                .values_list("pk", flat=True)
            ),
            "versions": list(
                Rendition.objects.filter(document__url__in=urls)
                .order_by("pk")
                .values_list("pk", "output_digest")
            ),
            "retained": [retained_manifest(spec)[0] for spec in specs],
            "annotations": [
                [row["pk"], str(row["updated_at"])]
                for row in Annotation.objects.filter(rendition__document__url__in=urls)
                .order_by("pk")
                .values("pk", "updated_at")
            ],
            "jobs": list(
                Job.objects.filter(document__url__in=urls)
                .order_by("pk")
                .values_list("status", flat=True)
            ),
        }
    )


def preview_change(before, after, *, undo_of=None):
    from library.services.pipeline import fingerprint, format_rendition

    before = [validate_spec(spec) for spec in before]
    after = [validate_spec(spec) for spec in after]
    initial_revision = revision(before + after)
    if any(current_spec(spec["url"]) != spec for spec in before):
        raise ValueError("An affected work changed. Reload its organization before previewing.")
    membership = graph_membership(after, undo_of=undo_of)
    urls = {spec["url"] for spec in after} | {
        part["url"] for spec in after for part in spec["parts"]
    }
    active = Job.objects.filter(
        document__url__in=urls, status__in=[Job.Status.QUEUED, Job.Status.RUNNING]
    )
    if active.exists():
        raise ValueError("An affected work has an active import. Wait for it to finish.")
    result = []
    for spec in after:
        # An attached former standalone is preserved internally, not republished.
        if spec["url"] in membership:
            continue
        manifest, warnings = retained_manifest(spec)
        source, html, structure, stylesheet, warnings = format_rendition(manifest, warnings, spec)
        soup = BeautifulSoup(html, "html.parser")
        for index in range(len(spec["parts"])):
            section = soup.find("section", id=f"c{index + 1}")
            if not section or not section.get_text(strip=True):
                raise ValueError("Every part must produce nonempty reader content.")
        result.append(
            {
                "spec": spec,
                "html": html,
                "structure": structure,
                "warnings": warnings,
                "digest": fingerprint([html, structure, source.metadata, source.title, stylesheet]),
            }
        )
    annotations = Annotation.objects.filter(
        rendition__document__url__in={spec["url"] for spec in before} | set(membership)
    ).count()
    if revision(before + after) != initial_revision:
        raise ValueError("Content changed while building the preview. Preview again.")
    return {
        "before": before,
        "after": after,
        "works": result,
        "revision": initial_revision,
        "annotations": annotations,
        "annotation_policy": ANNOTATION_POLICY,
    }


def undo_plan(decision):
    if decision.profile != get_profile().key:
        raise ValueError("Switch to the decision's profile before undoing.")
    for spec in decision.after:
        if current_spec(spec["url"]) != spec:
            raise ValueError("An affected work changed after this decision; undo it first.")
    return decision.after, decision.before


def entry_for_url(url, title):
    site = CrawlSite.objects.get(profile=get_profile().key, host=urlsplit(url).hostname)
    entry, _ = CatalogueEntry.objects.get_or_create(site=site, url=url, defaults={"title": title})
    return entry


@transaction.atomic
def commit_change(preview, reviewer, reason, *, undo_of=None):
    from library.services.pipeline import publish

    reason = reason.strip()
    if not reason or len(reason) > 2000:
        raise ValueError("Explain the organization decision in 1-2000 characters.")
    lock_organization()
    if revision(preview["before"] + preview["after"]) != preview["revision"]:
        raise ValueError("Content or reviews changed since preview. Preview again before saving.")
    if undo_of:
        undo_plan(undo_of)
    fresh = preview_change(preview["before"], preview["after"], undo_of=undo_of)
    if [work["digest"] for work in fresh["works"]] != preview["digests"]:
        raise ValueError("Formatting changed since preview. Preview again before saving.")
    membership_before = graph_membership(fresh["before"])
    membership = graph_membership(fresh["after"], undo_of=undo_of)
    affected = {spec["url"] for spec in fresh["after"]}
    for entry in entries().filter(membership_reviewed=True).filter(
        Q(book__url__in=affected) | Q(url__in=affected) | Q(url__in=membership),
    ):
        expected = entries().filter(url=membership.get(entry.url)).first()
        if entry.book_id != (expected.pk if expected else None):
            raise ValueError("Explicit catalogue membership prevents legacy reassignment.")
    built = {}
    for work in fresh["works"]:
        spec = work["spec"]
        document, _ = Document.objects.get_or_create(url=spec["url"])
        manifest, warnings = retained_manifest(spec)
        job = Job.objects.create(document=document, mode=Job.Mode.REFORMAT)
        rendition = publish(job, manifest, warnings, organization=spec, register_membership=False)
        if rendition.output_digest != work["digest"]:
            raise ImportFailure("Built rendition differs from its preview.", "organization")
        built[spec["url"]] = rendition
    # Nothing becomes a member (or is retired) until every affected work is valid.
    affected = {spec["url"] for spec in fresh["after"]}
    entries().filter(Q(book__url__in=affected) | Q(url__in=affected)).update(book=None)
    for spec in fresh["after"]:
        entry = entry_for_url(spec["url"], spec["title"])
        rendition = built.get(spec["url"])
        if rendition:
            ContentOrganization.objects.update_or_create(
                entry=entry,
                defaults={"specification": spec, "rendition": rendition},
            )
        for part in spec["parts"]:
            if not part.get("excerpt"):
                entry_for_url(part["url"], part["title"])
    for url, book_url in membership.items():
        entries().filter(url=url).update(book=entries().get(url=book_url))
    return ContentOrganizationDecision.objects.create(
        profile=get_profile().key,
        reviewer=reviewer,
        reason=reason,
        before=fresh["before"],
        after=fresh["after"],
        undo_of=undo_of,
        evidence={
            "revision": preview["revision"],
            "membership_before": membership_before,
            "annotation_policy": ANNOTATION_POLICY,
            "annotations_preserved": fresh["annotations"],
            "renditions": {url: rendition.pk for url, rendition in built.items()},
        },
    )


def member_destination(document, version=None):
    member = (
        entries()
        .filter(Q(url=document.url) | Q(url__in=document.aliases), book__isnull=False)
        .select_related("book")
        .first()
    )
    if not member:
        retained = override(document.url)
        explicit = entries().filter(url=document.url, membership_reviewed=True).exists()
        if (
            not explicit
            and
            version is not None
            and not version.structure.get("book")
            and retained
            and retained.specification["book"]
        ):
            current = retained.rendition
            section = next(
                (part["id"] for part in current.structure["parts"] if part["url"] == document.url),
                "c1",
            )
            return current, section
        return None
    parent = Document.objects.filter(url=member.book.url).first()
    rendition = parent.reader_target() if parent else None
    if not rendition:
        raise ImportFailure(
            "The complete book is unavailable; preserved evidence is safe.", "incomplete"
        )
    parts = rendition.structure.get("parts", rendition.snapshot.manifest.get("parts", []))
    for index, part in enumerate(parts):
        if part.get("url") and canonical_url(part["url"]) == member.url:
            return rendition, part.get("id", f"c{index + 1}")
    return rendition, ""
