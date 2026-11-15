"""Bounded, offline fixtures; never an import or a live-data repair command."""

import io
import json
import os
import secrets
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.urls import reverse
from PIL import Image, ImageDraw

from config.environments import validate_environment
from library import versions
from library.models import (
    Blob,
    Document,
    DocumentPublication,
    Rendition,
    RenditionAsset,
    Snapshot,
    URLAlias,
)
from library.profile import get_profile
from library.services.document_edits import (
    create_draft,
    preview_rendition_import,
    save_revision,
)
from library.services.document_publication import prepare_publication, publish_revision
from library.services.document_versions import version_for_rendition
from library.services.pipeline import fingerprint, snapshot_digest
from library.services.storage import read_blob, store_blob
from library.sources.base import Part, Source, parse_html
from library.sources.normalize import normalize

FIXTURE_VERSION = 1
ROLES = {
    "reviewer": ("development-reviewer", True, False),
    "reader": ("development-reader", False, False),
    "administrator": ("development-administrator", True, True),
}


def isolated_data_dir():
    environment = getattr(settings, "READING_HUB_ENVIRONMENT", "live")
    if environment not in {"development", "staging", "test"}:
        raise CommandError(
            "Synthetic fixtures require development, staging or test; live is refused."
        )
    data = Path(settings.DATA_DIR).resolve()
    database = str(settings.DATABASES["default"]["NAME"])
    memory = database == ":memory:" or database.startswith("file:memorydb_")
    if memory:
        if environment != "test":
            raise CommandError("Only test fixtures may use an in-memory database.")
    elif not Path(database).resolve().is_relative_to(data):
        raise CommandError("The fixture database must be inside the isolated data directory.")
    try:
        validate_environment(
            environment,
            settings.BASE_DIR,
            data,
            data / "fixture-test.sqlite3" if memory else database,
        )
    except ValueError as exc:
        raise CommandError(f"Synthetic fixtures require isolated non-live storage: {exc}") from exc
    return data


def write_private_json(path, value):
    # Exclusive creation prevents replacing credentials or following an existing symlink.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        json.dump(value, output, ensure_ascii=False, indent=2)
        output.write("\n")


def fixture_users(path):
    user_model = get_user_model()
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file():
            raise CommandError("The fixture credentials path must be a private regular file.")
        try:
            credentials = json.loads(path.read_text(encoding="utf-8"))
            for role, (username, _, _) in ROLES.items():
                record = credentials[role]
                if record["username"] != username or not isinstance(record["password"], str):
                    raise ValueError
        except (ValueError, KeyError, TypeError) as exc:
            raise CommandError(
                "Invalid fixture credentials file; no passwords were changed."
            ) from exc
        path.chmod(0o600)
    else:
        if user_model.objects.filter(username__in=[value[0] for value in ROLES.values()]).exists():
            raise CommandError("Fixture usernames already exist without fixture credentials.")
        credentials = {
            role: {"username": username, "password": secrets.token_urlsafe(24)}
            for role, (username, _, _) in ROLES.items()
        }
        write_private_json(path, credentials)
    users = {}
    for role, (username, staff, administrator) in ROLES.items():
        user = user_model.objects.filter(username=username).first()
        if user is None:
            user = user_model.objects.create_user(
                username,
                password=credentials[role]["password"],
                is_staff=staff,
                is_superuser=administrator,
            )
        users[role] = user
    return users


def retained_plate():
    output = io.BytesIO()
    image = Image.new("RGB", (160, 96), "#e4e9d6")
    draw = ImageDraw.Draw(image)
    draw.rectangle((15, 15, 70, 80), fill="#456b4e")
    draw.ellipse((85, 20, 145, 80), fill="#b59253")
    image.save(output, format="PNG")
    data = output.getvalue()
    digest = store_blob(data)
    blob, _ = Blob.objects.get_or_create(
        digest=digest,
        defaults={"media_type": "image/png", "size": len(data)},
    )
    return blob


def synthetic_pages(kind, root, plate_url):
    figure = (
        f'<figure><img src="{plate_url}" alt="Synthetic geometric plate">'
        "<figcaption>Geometric plate. Created locally for this fixture.</figcaption></figure>"
    )
    if kind == "article":
        return [
            (
                root,
                "Synthetic reading article",
                "article",
                '<h2 id="opening">An offline reading exercise</h2>'
                '<p id="prose">Synthetic source text for <em>careful reading</em>. '
                '<sup><a id="ref" href="#note">1</a></sup></p>'
                '<h3 id="detail">A smaller heading</h3>'
                "<p>Unicode café — Ελληνικά. No source was downloaded.</p>"
                "<ul><li>Read the source.</li><li>Save an explicit revision.</li></ul>"
                + figure
                + '<p id="note">A synthetic endnote. '
                '<a class="note-backlink" href="#ref">Return to text</a></p>',
            )
        ]
    first = root.rsplit("/", 1)[0] + "/chapter-one.htm"
    second = root.rsplit("/", 1)[0] + "/chapter-two.htm"
    return [
        (
            first,
            "First observations",
            "chapter",
            '<p id="prose">Synthetic source text opens the first chapter. '
            f'<sup><a id="ref" href="{second}#note">1</a></sup></p>'
            '<h3 id="detail">Reading deliberately</h3>'
            "<p>A short subsection with <strong>emphasis</strong>.</p>" + figure,
        ),
        (
            second,
            "Methods and notes",
            "chapter",
            "<p>Record only the review scope actually performed.</p>"
            "<blockquote><p>A synthetic quotation, written for this fixture.</p></blockquote>"
            "<table><tbody><tr><th>Stage</th><th>Purpose</th></tr>"
            "<tr><td>Save</td><td>Retain a revision</td></tr>"
            "<tr><td>Publish</td><td>Expose that saved revision</td></tr></tbody></table>"
            "<ol><li>Inspect retained sources.</li><li>Compare saved states.</li></ol>"
            f'<p id="note">A synthetic cross-chapter endnote. '
            f'<a class="note-backlink" href="{first}#ref">Return to chapter one</a></p>',
        ),
    ]


def seed_work(kind, reviewer, blob):
    profile = get_profile()
    root = f"https://{profile.sources[0].host}/reading-hub-synthetic/{kind}/index.htm"
    marker = f"reading-hub-development-v{FIXTURE_VERSION}:{profile.key}:{kind}"
    source = (
        Rendition.objects.filter(
            document__url=root,
            metadata__development_fixture=marker,
        )
        .order_by("pk")
        .first()
    )
    if source:
        draft = source.document_drafts.filter(reviewer=reviewer).order_by("created_at").first()
        if draft is None or not draft.revisions.exists():
            raise CommandError(
                "Existing synthetic fixture history is incomplete; no edits were reset."
            )
        publication = DocumentPublication.objects.filter(
            revision=draft.revisions.order_by("revision").first(),
        ).first()
        if publication is None:
            raise CommandError("Existing synthetic publication is missing; no edits were reset.")
        return fixture_record(kind, source, draft, publication)
    if Document.objects.filter(url=root).exists():
        raise CommandError("A fixture source URL already exists without synthetic provenance.")
    title = "Synthetic reading article" if kind == "article" else "Synthetic field guide"
    metadata = {
        "profile": profile.key,
        "language": "en",
        "author": "Synthetic Example Author",
        "authors": ["Synthetic Example Author"],
        "author_is_fallback": False,
        "work_type": kind,
        "content_organization": {"book": kind == "book"},
        "contents_page": kind == "book",
        "development_fixture": marker,
        "notes": "Offline synthetic development fixture; not a retained historical work.",
    }
    plate_url = root.rsplit("/", 1)[0] + "/plate.png"
    assets = {
        plate_url: {
            "digest": blob.pk,
            "media_type": blob.media_type,
            "size": blob.size,
        }
    }
    retained, pages, parts = [], [], []
    specifications = synthetic_pages(kind, root, plate_url)
    if kind == "book":
        index = (
            "<h1>Synthetic field guide</h1><ul>"
            + "".join(
                f'<li><a href="{url}">{label}</a></li>' for url, label, _, _ in specifications
            )
            + "</ul>"
        )
        retained.append(retain_html(root, title, index))
    for url, label, role, html in specifications:
        entry = retain_html(url, label, html)
        retained.append(entry)
        part = Part(url, label, role=role, use_source_headings=kind == "article")
        parts.append(part)
        pages.append((part, parse_html(read_blob(entry["digest"]), entry["headers"]).body))
    manifest = {"pages": retained, "assets": assets, "synthetic": True}
    html, structure = normalize(pages, Source(title, metadata, parts, kind == "book"), assets)
    stylesheet = (Path(settings.BASE_DIR) / "library/static/library/reader.css").read_text()
    output_digest = fingerprint([html, structure, metadata, title, stylesheet])
    document = Document.objects.create(url=root, title=title)
    URLAlias.objects.create(url=root, document=document)
    snapshot = Snapshot.objects.create(
        document=document,
        digest=snapshot_digest(manifest),
        manifest=manifest,
    )
    source = Rendition.objects.create(
        document=document,
        snapshot=snapshot,
        title=title,
        metadata=metadata,
        html=html,
        structure=structure,
        stylesheet=stylesheet,
        identity=fingerprint([marker, snapshot.digest, output_digest]),
        output_digest=output_digest,
        app_version=versions.APP_VERSION,
        adapter_version=profile.adapter_version,
        format_version=versions.FORMAT_VERSION,
    )
    RenditionAsset.objects.create(rendition=source, blob=blob)
    version_for_rendition(source, generation_evidence={"synthetic": True, "fixture": marker})
    proposal = preview_rendition_import(source)
    draft = create_draft(
        source,
        reviewer,
        conversion_approval=proposal["approval_digest"] if proposal["requires_approval"] else None,
    )
    edited = {
        **draft.document,
        "html": draft.document["html"].replace(
            "Synthetic source text",
            "Synthetic edited text",
            1,
        ),
    }
    revision = save_revision(draft, reviewer, edited, 0, review="partial", editorial=True)
    candidate = prepare_publication(draft, revision.revision)
    publication = publish_revision(draft, reviewer, revision.revision, candidate["digest"])
    source.refresh_from_db()
    return fixture_record(kind, source, draft, publication)


def retain_html(url, title, body):
    data = (
        f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f"<title>{title}</title></head><body>{body}</body></html>"
    ).encode("utf-8")
    return {
        "url": url,
        "resolved_url": url,
        "digest": store_blob(data),
        "headers": {"content-type": "text/html; charset=utf-8"},
        "retrieved_at": "2026-01-01T00:00:00+00:00",
    }


def fixture_record(kind, source, draft, publication):
    query = f"?draft={draft.pk}"
    return {
        "kind": kind,
        "document_id": source.document_id,
        "snapshot_id": source.snapshot_id,
        "source_rendition_id": source.pk,
        "source_version_id": str(source.document_version_id),
        "draft_id": str(draft.pk),
        "revision": publication.revision.revision,
        "published_rendition_id": publication.rendition_id,
        "published_version_id": str(publication.rendition.document_version_id),
        "source_url": source.document.url,
        "workspace_url": reverse("document-editor", args=[source.pk]) + query + "&tab=edit",
        "reader_url": reverse("reader", args=[publication.rendition_id]),
        "history_url": reverse("document-editor-history", args=[source.pk]) + query,
        "comparison_url": reverse("document-comparison", args=[source.pk]) + query,
        "publication_url": reverse("document-publication", args=[source.pk])
        + query
        + f"&revision={publication.revision.revision}",
        "source_inspection_url": reverse("document-editor-source-inspection", args=[source.pk]),
        "lineage_url": reverse("document-lineage", args=[source.document_id]),
        "pdf_url": reverse("reader-pdf", args=[publication.rendition_id]),
    }


class Command(BaseCommand):
    help = "Seed two offline synthetic works and private local accounts in isolated non-live data."

    def handle(self, *args, **options):
        data = isolated_data_dir()
        data.mkdir(parents=True, exist_ok=True, mode=0o700)
        credentials_path = data / "development-credentials.json"
        manifest_path = data / "development-fixtures.json"
        if manifest_path.is_symlink():
            raise CommandError("The fixture manifest must not be a symlink.")
        with transaction.atomic():
            users = fixture_users(credentials_path)
            blob = retained_plate()
            fixtures = {
                kind: seed_work(kind, users["reviewer"], blob) for kind in ("article", "book")
            }
            manifest = {
                "version": FIXTURE_VERSION,
                "synthetic": True,
                "profile": get_profile().key,
                "fixtures": fixtures,
            }
            if manifest_path.exists():
                try:
                    previous = json.loads(manifest_path.read_text(encoding="utf-8"))
                except ValueError as exc:
                    raise CommandError(
                        "Invalid fixture manifest; no developer state was reset."
                    ) from exc
                if previous != manifest:
                    raise CommandError(
                        "Existing fixture manifest differs; no developer state was reset."
                    )
            else:
                write_private_json(manifest_path, manifest)
        self.stdout.write(str(credentials_path))
        self.stdout.write(str(manifest_path))
        for fixture in fixtures.values():
            self.stdout.write(fixture["source_url"])
            self.stdout.write(fixture["workspace_url"])
