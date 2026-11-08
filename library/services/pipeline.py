import hashlib
import json
import logging
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path
from time import perf_counter
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
from django.db import transaction
from django.db.models import F, OuterRef, Q, Subquery, Window
from django.db.models.functions import RowNumber
from django.utils import timezone

from library import versions
from library.models import (
    Blob,
    CatalogueEntry,
    CrawlCapture,
    CrawlSite,
    Document,
    FetchCheck,
    Job,
    PageTypeDecision,
    Rendition,
    RenditionAsset,
    Snapshot,
    SourceCorrection,
    URLAlias,
)
from library.profile import get_profile
from library.services.catalogue import enrich_from_rendition, register_book
from library.services.corrections import apply_expected, apply_retained_correction
from library.services.errors import ImportFailure, LimitExceeded
from library.services.fetch import MAX_BYTES, MAX_PAGES, Fetcher, canonical_url
from library.services.media import fetch_image
from library.services.storage import read_blob, save_response, store_blob
from library.sources.adapters import discover, extract, image_url, parse_html
from library.sources.capitalization import author_names, normalize_capitalization
from library.sources.classification import clean_authors, infer_topics, split_authors, unique
from library.sources.normalize import normalize

logger = logging.getLogger("library")


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def snapshot_digest(manifest):
    return fingerprint({
        "pages": [
            {key: entry[key] for key in ("url", "resolved_url", "digest")}
            for entry in manifest["pages"]
        ],
        "assets": manifest["assets"],
    })


def reject_reviewed_index(url):
    reject_reviewed_indexes([url])


def reject_reviewed_indexes(urls):
    urls = list(dict.fromkeys(urls))
    if not urls:
        return
    profile = get_profile()
    decisions = PageTypeDecision.objects.filter(site__profile=profile.key)
    latest = decisions.filter(url=OuterRef("url")).order_by("-pk")
    if (
        decisions.filter(
            url__in=urls, discovery_only=True, pk=Subquery(latest.values("pk")[:1])
        ).exists()
        or CatalogueEntry.objects.filter(
            site__profile=profile.key, url__in=urls, discovery_only=True
        ).exists()
        or CrawlCapture.objects.filter(
            site__profile=profile.key, url__in=urls, discovery_only=True
        ).exists()
    ):
        raise ImportFailure("This URL is a discovery index, not an article or a book.", "discovery")


def enqueue(url, mode=Job.Mode.IMPORT, snapshot=None):
    url = canonical_url(url)
    reject_reviewed_index(url)
    chapter = (
        CatalogueEntry.objects.filter(site__profile=get_profile().key, url=url, book__isnull=False)
        .select_related("book")
        .first()
    )
    if chapter:
        url = chapter.book.url
        reject_reviewed_index(url)
        if mode == Job.Mode.REFORMAT:
            book_document = Document.objects.filter(url=url).first()
            book_version = book_document.latest() if book_document else None
            if book_version is None:
                raise ImportFailure("Build the complete book before reformatting.", "incomplete")
            snapshot = book_version.snapshot
    with transaction.atomic():
        alias = URLAlias.objects.select_related("document").filter(url=url).first()
        if alias:
            document = alias.document
        else:
            document, _ = Document.objects.get_or_create(url=url)
            URLAlias.objects.get_or_create(url=url, defaults={"document": document})
        active = document.jobs.filter(status__in=[Job.Status.QUEUED, Job.Status.RUNNING]).first()
        if active:
            return active
        if mode == Job.Mode.IMPORT:
            reader_target = document.reader_target()
            if reader_target:
                return reader_target
        if mode == Job.Mode.REFORMAT and (snapshot is None or snapshot.document_id != document.pk):
            raise ImportFailure(
                "Select a stored source snapshot belonging to this document.", "invalid_snapshot"
            )
        return Job.objects.create(document=document, mode=mode, snapshot=snapshot)


def progress(job, stage, completed=None, total=None):
    fields = {"stage": stage[:250], "heartbeat": timezone.now()}
    if completed is not None:
        fields["completed"] = completed
    if total is not None:
        fields["total"] = total
    Job.objects.filter(pk=job.pk, status=Job.Status.RUNNING).update(**fields)
    if job.worker_id:
        from library.models import WorkerInstance

        WorkerInstance.objects.filter(pk=job.worker_id).update(
            heartbeat=fields["heartbeat"], activity=stage[:250]
        )


def import_page(job, fetcher, url):
    capture = None
    if job.mode == Job.Mode.IMPORT:
        capture = (
            CrawlCapture.objects.filter(site__profile=get_profile().key)
            .filter(Q(url=url) | Q(response__resolved_url=url))
            .order_by("-captured_at", "-pk")
            .first()
        )
    if capture:
        progress(job, "Reusing HTML cached by catalogue crawler")
        entry = {**capture.response, "url": url}
        body = read_blob(entry["digest"])
        fetcher.downloaded += len(body)
        if fetcher.downloaded > MAX_BYTES:
            raise LimitExceeded(f"Import exceeds the {MAX_BYTES}-byte source limit.")
        return entry, body
    response = fetcher.fetch(url)
    return save_response(response, url), response.body


def prepare_pages(manifest, organization=None, *, provenance=None, original_source=False):
    if type(original_source) is not bool:
        raise ValueError("Choose whether to use original source inputs.")
    if original_source and organization is not None:
        raise ValueError("Original-source generation cannot use an organization override.")
    entries = {canonical_url(entry["url"]): entry for entry in manifest["pages"]}
    initial = manifest["pages"][0]
    reject_reviewed_index(canonical_url(initial["url"]))
    soup = parse_html(read_blob(initial["digest"]), initial["headers"])
    source = discover(soup, canonical_url(initial["url"]))
    from library.services.organizations import organized_source

    if original_source:
        if provenance is not None:
            provenance["organization"] = {
                "id": None, "rendition": None, "specification": None,
            }
    else:
        source = organized_source(source, initial["url"], organization, provenance=provenance)
    if provenance is not None:
        provenance["corrections"] = []
        provenance["input_policy"] = (
            "original-retained-source" if original_source else "applicable-reviewed-inputs"
        )

    def record_correction(correction):
        if provenance is not None:
            from library.services.corrections import export_correction

            provenance["corrections"].append({
                "id": correction.pk, "capture": correction.capture_id,
                "reviewer": correction.reviewer_id,
                "binding": export_correction(correction),
            })
    reject_reviewed_indexes(
        canonical_url(part.url)
        for part in source.parts
        if canonical_url(part.url) != canonical_url(initial["url"])
    )
    correction_urls = {canonical_url(part.url) for part in source.parts if not part.section} | {
        canonical_url(initial["url"])
    }
    correction_pairs = {
        (entries[url]["url"], entries[url]["digest"]) for url in correction_urls if url in entries
    }
    matching = Q()
    for url, source_digest in sorted(correction_pairs):
        matching |= Q(capture__url=url, source_digest=source_digest)
    corrections_by_source = {}
    if correction_pairs and not original_source:
        corrections = (
            SourceCorrection.objects.filter(
                profile=get_profile().key,
                capture__site__profile=get_profile().key,
            )
            .filter(matching)
            .select_related("capture__site")
            .annotate(
                latest_for_source=Window(
                    expression=RowNumber(),
                    partition_by=[F("capture__url"), F("source_digest")],
                    order_by=[F("created_at").desc(), F("pk").desc()],
                )
            )
            .filter(latest_for_source=1)
        )
        for correction in corrections:
            key = (correction.capture.url, correction.source_digest)
            corrections_by_source[key] = (correction,)
    pages = []
    index_images = set()
    from library.services.source_excerpts import validate_source_ranges

    for entry in manifest["pages"]:
        validate_source_ranges(entry, source.parts)
    index_body = None
    if source.book and not any(
        canonical_url(part.url) == canonical_url(initial["url"])
        and not part.section and not part.excerpt
        for part in source.parts
    ):
        index_body = extract(
            soup, initial["url"], index=True, book=False, chapter_title=source.title
        )
        correction = apply_retained_correction(
            source,
            index_body,
            initial,
            metadata=True,
            corrections=corrections_by_source.get((initial["url"], initial["digest"]), ()),
        )
        if correction:
            record_correction(correction)
            source.metadata.setdefault("corrections", []).append(correction.pk)
    for part in source.parts:
        entry = entries.get(canonical_url(part.url))
        if not entry:
            raise ImportFailure(
                f"Stored source lacks required chapter: {part.url}. Refresh source first.",
                "incomplete",
            )
        if part.excerpt:
            from library.services.source_excerpts import select_excerpt

            pages.append((part, select_excerpt(entry, part.excerpt)))
            continue
        if part.section:
            from library.sources.index_sections import selected

            if canonical_url(part.url) != canonical_url(initial["url"]) or index_body is None:
                raise ImportFailure(
                    "Sections must belong to the book's contents source.", "incomplete"
                )
            section_body = selected(
                index_body, part.section, use_source_headings=part.use_source_headings
            )
            pages.append((part, section_body))
            continue
        soup = parse_html(read_blob(entry["digest"]), entry["headers"])
        body = extract(
            soup,
            part.url,
            index=source.book and canonical_url(part.url) == canonical_url(initial["url"]),
            book=source.book and not part.use_source_headings,
            group=part.group,
            chapter_title=part.title,
        )
        if source.book and canonical_url(part.url) == canonical_url(initial["url"]):
            index_images.update(image_url(image, part.url) for image in body.select("img"))
        correction = apply_retained_correction(
            source,
            body,
            entry,
            metadata=canonical_url(part.url) == canonical_url(initial["url"]),
            book_part=source.book and canonical_url(part.url) != canonical_url(initial["url"]),
            corrections=corrections_by_source.get((entry["url"], entry["digest"]), ()),
        )
        if correction:
            record_correction(correction)
            source.metadata.setdefault("corrections", []).append(correction.pk)
        pages.append((part, body))
    if source.book:
        present_images = {
            image_url(image, part.url) for part, body in pages for image in body.select("img")
        }
        for cover in reversed(source.metadata.get("covers", [])):
            if cover["url"] in present_images or cover["url"] in index_images:
                continue
            markup = BeautifulSoup("<figure><img></figure>", "html.parser")
            markup.img["src"] = cover["url"]
            markup.img["alt"] = cover["alt"]
            pages[0][1].insert(0, markup.figure)
    return source, pages


def fetch_snapshot(job):
    reject_reviewed_index(job.document.url)
    fetcher = Fetcher(lambda stage: progress(job, stage))
    initial, body = import_page(job, fetcher, job.document.url)
    soup = parse_html(body, initial["headers"])
    source = discover(soup, job.document.url)
    from library.services.organizations import organized_source

    source = organized_source(source, job.document.url)
    unique_urls = list(dict.fromkeys([job.document.url] + [part.url for part in source.parts]))
    if len(unique_urls) > MAX_PAGES:
        raise LimitExceeded(f"Book index exceeds the {MAX_PAGES} unique HTML page limit.")
    manifest = {"pages": [initial], "assets": {}, "parts": [asdict(p) for p in source.parts]}
    progress(job, "Discovered source structure", 1, len(unique_urls))
    for index, url in enumerate(unique_urls[1:], 2):
        entry, _ = import_page(job, fetcher, url)
        manifest["pages"].append(entry)
        progress(job, "Downloaded chapter", index, len(unique_urls))
    source, pages = prepare_pages(manifest)
    asset_urls = list(
        dict.fromkeys(
            image_url(img, part.url) for part, body in pages for img in body.select("img")
        )
    )
    asset_warnings = []
    for index, url in enumerate(asset_urls, 1):
        progress(job, f"Downloading image {index}/{len(asset_urls)}")
        try:
            response = fetch_image(fetcher, url)
            media_type = response.media_type
            digest = store_blob(response.body)
            Blob.objects.get_or_create(
                digest=digest,
                defaults={
                    "media_type": media_type,
                    "size": len(response.body),
                },
            )
            manifest["assets"][url] = {
                "digest": digest,
                "media_type": media_type,
                "size": len(response.body),
            }
        except LimitExceeded:
            raise
        except (ImportFailure, ValueError) as exc:
            message = f"Missing image {url}: {exc}"
            logger.warning(message)
            manifest["assets"][url] = {"error": str(exc)}
            asset_warnings.append(message)
    return manifest, asset_warnings


def format_rendition(manifest, asset_warnings, organization=None, *,
                     timings=None, provenance=None, original_source=False):
    started = perf_counter() if timings is not None else None
    source, pages = prepare_pages(
        manifest, organization, provenance=provenance, original_source=original_source,
    )
    if timings is not None:
        now = perf_counter()
        timings["prepare_pages_seconds"] = now - started
        started = now
    profile = get_profile()
    source.metadata["profile"] = profile.key
    source.metadata["author"] = normalize_capitalization(
        source.metadata.get("author", ""),
        author=True,
        language=source.metadata.get("language", "en"),
    )
    if not source.metadata.get("author_is_fallback"):
        source.metadata["authors"] = [
            normalize_capitalization(
                name, author=True, language=source.metadata.get("language", "en")
            )
            for name in clean_authors(
                source.metadata.get("authors") or split_authors(source.metadata["author"])
            )
        ]
    source.metadata["topics"] = unique(
        source.metadata.get("topics", [])
        + infer_topics(
            source.title + " " + " ".join(body.get_text(" ", strip=True) for _, body in pages),
            profile.topic_rules,
        )
    )
    source.title = normalize_capitalization(
        source.title,
        names=author_names(source.metadata["author"]),
        language=source.metadata.get("language", "en"),
    )
    from library.services.organizations import override

    retained = (
        override(canonical_url(manifest["pages"][0]["url"]))
        if provenance is None and not original_source else None
    )
    specification = (
        organization if organization is not None else (retained.specification if retained else None)
    )
    if provenance is not None:
        specification = provenance["organization"]["specification"]
        provenance["parts"] = [asdict(part) for part, _ in pages]
    if specification is not None:
        source.title = specification["title"]
    reviewed_metadata = source.metadata.pop("_reviewed_metadata", None)
    if reviewed_metadata is not None:
        apply_expected(source, None, {"metadata": reviewed_metadata})
    asset_warnings = list(asset_warnings)
    for part, body in pages:
        for image in body.select("img"):
            url = image_url(image, part.url)
            if url not in manifest["assets"]:
                asset_warnings.append(
                    f"Image {url} was not captured by the old adapter. Refresh source to save it."
                )
    if timings is not None:
        now = perf_counter()
        timings["metadata_and_assets_seconds"] = now - started
        started = now
    html, structure = normalize(pages, source, manifest["assets"])
    if timings is not None:
        now = perf_counter()
        timings["normalize_seconds"] = now - started
        started = now
    stylesheet = (
        Path(__file__).resolve().parent.parent / "static" / "library" / "reader.css"
    ).read_text()
    if timings is not None:
        timings["stylesheet_seconds"] = perf_counter() - started
    return source, html, structure, stylesheet, asset_warnings


@transaction.atomic
def publish(
    job, manifest, asset_warnings, *, organization=None, register_membership=True,
    generation_evidence=None,
):
    from library.services.organizations import lock_organization

    lock_organization()
    progress(job, "Formatting stored source")
    source, html, structure, stylesheet, asset_warnings = format_rendition(
        manifest, asset_warnings, organization
    )
    profile = get_profile()
    digest = snapshot_digest(manifest)
    output_digest = fingerprint([html, structure, source.metadata, source.title, stylesheet])
    identity = fingerprint(
        [
            job.document_id,
            digest,
            versions.APP_VERSION,
            profile.adapter_version,
            versions.FORMAT_VERSION,
            output_digest,
        ]
    )
    with transaction.atomic():
        for entry in manifest["pages"][:1]:
            resolved = canonical_url(entry["resolved_url"])
            alias, _ = URLAlias.objects.get_or_create(
                url=resolved, defaults={"document": job.document}
            )
            if alias.document_id != job.document_id:
                raise ImportFailure(
                    f"This URL resolves to an existing document: {resolved}. "
                    f"Open /documents/{alias.document_id}/ instead.",
                    "duplicate_source",
                )
        snapshot, _ = Snapshot.objects.get_or_create(
            document=job.document,
            digest=digest,
            defaults={"manifest": manifest, "warnings": asset_warnings},
        )
        rendition, created = Rendition.objects.get_or_create(
            identity=identity,
            defaults={
                "document": job.document,
                "snapshot": snapshot,
                "title": source.title,
                "metadata": source.metadata,
                "structure": structure,
                "html": html,
                "stylesheet": stylesheet,
                "warnings": asset_warnings,
                "app_version": versions.APP_VERSION,
                "adapter_version": profile.adapter_version,
                "format_version": versions.FORMAT_VERSION,
                "output_digest": output_digest,
            },
        )
        from library.services.document_versions import version_for_rendition

        rendition.document_version = version_for_rendition(
            rendition, generation_evidence=generation_evidence,
        )
        for asset in manifest["assets"].values():
            if "digest" in asset:
                RenditionAsset.objects.get_or_create(rendition=rendition, blob_id=asset["digest"])
        aliases = list(
            dict.fromkeys(job.document.aliases + [p["resolved_url"] for p in manifest["pages"][:1]])
        )
        Document.objects.filter(pk=job.document_id).update(
            title=source.title,
            aliases=aliases,
        )
        Document.objects.filter(
            pk=job.document_id, reader_selection_explicit=False,
        ).update(reader_rendition=rendition)
        enrich_from_rendition(rendition)
        if register_membership and source.book:
            site = CrawlSite.objects.filter(
                profile=profile.key, host=urlsplit(job.document.url).hostname
            ).first()
            if site:
                register_book(site, job.document.url, source, rendition=rendition)
        from library.models import ContentOrganization

        ContentOrganization.objects.filter(
            entry__site__profile=profile.key, entry__url=job.document.url
        ).update(rendition=rendition)
        Job.objects.filter(pk=job.pk).update(
            status=Job.Status.READY,
            stage="Ready" if created else "Unchanged; cached version reused",
            rendition=rendition,
            snapshot=snapshot,
            heartbeat=timezone.now(),
            finished_at=timezone.now(),
        )
        if job.mode != Job.Mode.REFORMAT:
            FetchCheck.objects.create(
                job=job, document=job.document, outcome="new_version" if created else "unchanged"
            )
    return rendition


def process_job(job):
    try:
        if job.mode == Job.Mode.REFORMAT:
            manifest, asset_warnings = job.snapshot.manifest, job.snapshot.warnings
        else:
            manifest, asset_warnings = fetch_snapshot(job)
        return publish(job, manifest, asset_warnings)
    except (ImportFailure, OSError, ValueError) as exc:
        logger.exception("Import job %s failed", job.pk)
        code = exc.code if isinstance(exc, ImportFailure) else "storage_or_data"
        fail_job(job, str(exc), code)
    except MemoryError:
        from library.services.workers import release_memory_limit

        release_memory_limit()
        logger.exception("Worker memory exhausted in job %s", job.pk)
        fail_job(
            job,
            "Worker memory budget exhausted. Increase its limit before retrying.",
            "memory_limit",
        )
        raise
    except Exception as exc:
        # Persist unexpected errors for the UI, log the traceback, and stop the worker.
        logger.exception("Unexpected import failure in job %s", job.pk)
        fail_job(job, str(exc), "internal")
        raise
    return None


def fail_job(job, message, code):
    with transaction.atomic():
        Job.objects.filter(pk=job.pk).update(
            status=Job.Status.FAILED,
            error=message,
            error_code=code,
            stage="Import failed",
            heartbeat=timezone.now(),
            finished_at=timezone.now(),
        )
        if job.mode != Job.Mode.REFORMAT:
            FetchCheck.objects.get_or_create(
                job=job, defaults={"document": job.document, "outcome": code, "detail": message}
            )


def claim_job(worker=None):
    with transaction.atomic():
        job = Job.objects.filter(status=Job.Status.QUEUED).order_by("created_at").first()
        if job:
            job.status = Job.Status.RUNNING
            job.heartbeat = timezone.now()
            job.stage = "Starting import"
            job.worker = worker
            job.save(update_fields=["status", "heartbeat", "stage", "worker"])
        return job


def recover_interrupted():
    from library.services.workers import process_info

    cutoff = timezone.now() - timedelta(minutes=5)
    for job in Job.objects.filter(status=Job.Status.RUNNING).select_related("worker"):
        if (job.worker_id and not process_info(job.worker)) or (
            not job.worker_id and (not job.heartbeat or job.heartbeat < cutoff)
        ):
            fail_job(
                job, "Worker interrupted. Use Retry to enqueue the request again.", "interrupted"
            )
