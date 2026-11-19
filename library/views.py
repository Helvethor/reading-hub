import logging
from dataclasses import asdict
from urllib.parse import urlencode

from django.conf import settings
from django.core.paginator import Paginator
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.models import Q
from django.db.models.functions import Lower
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from library.forms import URLRequestForm
from library.metadata_views import metadata_reviewer_required
from library.models import Blob, CatalogueEntry, CrawlCapture, Document, Job, Rendition
from library.organization_views import redirect_member
from library.profile import SORTS, get_profile, source_name
from library.services.errors import ImportFailure
from library.services.pdf import PDFExportError, cached_pdf, pdf_filename
from library.services.pipeline import book_reimport_source, enqueue, fingerprint
from library.services.storage import blob_path

logger = logging.getLogger("library")


def csrf_failure(request, reason=""):
    logger.warning("CSRF rejected %s: %s", request.path, reason)
    return render(request, "library/csrf_failure.html", status=403)


def home_context(request, form=None):
    profile = get_profile()
    sort = request.GET.get("sort", profile.default_sort)
    source = request.GET.get("source", "") if profile.source_filter else ""
    search = request.GET.get("q", "").strip()[:200]
    errors = []
    if sort not in profile.sort_choices:
        errors.append("Unknown sort option. Showing the configured default order.")
        sort = profile.default_sort
    if source and source not in {site.host for site in profile.sources}:
        errors.append("Unknown source filter. Showing all sources.")
        source = ""
    documents = Document.objects.filter(renditions__isnull=False).distinct()
    documents = documents.exclude(
        url__in=CatalogueEntry.objects.filter(
            site__profile=profile.key,
            book__isnull=False,
        ).values("url")
    )
    documents = documents.exclude(
        url__in=CatalogueEntry.objects.filter(
            site__profile=profile.key, discovery_only=True
        ).values("url")
    ).exclude(
        url__in=CrawlCapture.objects.filter(site__profile=profile.key, discovery_only=True).values(
            "url"
        )
    )
    if source:
        hosts = [source] + [alias for alias, target in profile.aliases.items() if target == source]
        query = Q()
        for host in hosts:
            query |= Q(url__startswith=f"https://{host}/")
            query |= Q(url__startswith=f"http://{host}/")
        documents = documents.filter(query)
    if search:
        documents = documents.filter(Q(title__icontains=search) | Q(url__icontains=search))
    order = Lower("title") if sort == "title" else SORTS[sort]
    page = Paginator(documents.order_by(order, "pk"), profile.page_size).get_page(
        request.GET.get("page", 1)
    )
    context = {
        "form": form or URLRequestForm(),
        "documents": page,
        "page": page,
        "selected_sort": sort,
        "selected_source": source,
        "search": search,
        "browse_errors": errors,
        "browse_query": urlencode({"sort": sort, "source": source, "q": search}),
        "jobs": Job.objects.exclude(status=Job.Status.READY)
        .select_related("document")
        .order_by("-created_at")[:10],
    }
    return context


@require_GET
def home(request):
    return render(request, "library/home.html", home_context(request))


@require_GET
def health(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        if cursor.fetchone() != (1,):
            return HttpResponse("unavailable", status=503, content_type="text/plain")
    executor = MigrationExecutor(connection)
    if executor.migration_plan(executor.loader.graph.leaf_nodes()):
        return HttpResponse("unavailable", status=503, content_type="text/plain")
    return HttpResponse("ok", content_type="text/plain")


def queued_response(result):
    return (
        redirect("reader", pk=result.pk)
        if isinstance(result, Rendition)
        else redirect("job", pk=result.pk)
    )


def enqueue_error(request, url, error):
    form = URLRequestForm({"url": url})
    form.add_error("url", str(error))
    return render(request, "library/home.html", home_context(request, form), status=400)


def enqueue_response(request, url, mode=Job.Mode.IMPORT, snapshot=None):
    try:
        result = enqueue(url, mode, snapshot)
    except ImportFailure as exc:
        return enqueue_error(request, url, exc)
    return queued_response(result)


@require_POST
def request_document(request):
    form = URLRequestForm(request.POST)
    if not form.is_valid():
        return render(request, "library/home.html", home_context(request, form), status=400)
    return enqueue_response(request, form.cleaned_data["url"])


@require_GET
def latest(request, pk):
    document = get_object_or_404(Document, pk=pk)
    destination = redirect_member(document)
    if destination:
        return destination
    version = document.reader_target()
    if version:
        if (
            settings.READING_HUB_EDITOR_PILOT
            and request.user.is_authenticated
            and (request.user.is_staff or request.user.has_perm("library.review_metadata"))
        ):
            return redirect(
                reverse("document-editor", args=[version.pk]) + "?start=edition&tab=read"
            )
        return redirect("reader", pk=version.pk)
    job = document.jobs.order_by("-created_at").first()
    if job:
        return redirect("job", pk=job.pk)
    raise Http404("No cached version is available.")


def toc_tree(entries):
    root = []
    stack = [(1, root)]
    for entry in entries:
        node = {**entry, "children": []}
        while len(stack) > 1 and stack[-1][0] >= entry["level"]:
            stack.pop()
        stack[-1][1].append(node)
        stack.append((entry["level"], node["children"]))
    return root


def contents_tree(entries):
    """Generated contents pages omit hidden entries; navigation keeps the full tree."""
    return toc_tree([entry for entry in entries if entry.get("in_toc", True)])


def endmatter_ids(markup):
    """Choose stable end-matter IDs without shadowing IDs retained in source HTML."""
    from bs4 import BeautifulSoup

    used = {node["id"] for node in BeautifulSoup(markup, "html.parser").select("[id]")}
    result = {}
    for key, base in (
        ("metadata_page_id", "document-metadata"),
        ("edition_status_id", "document-edition-status"),
    ):
        identifier = base
        suffix = 2
        while identifier in used or f"{identifier}-heading" in used:
            identifier = f"{base}-{suffix}"
            suffix += 1
        used.update((identifier, f"{identifier}-heading"))
        result[key] = identifier
    return result


def with_edition_status(entries, edition_status_id):
    """Add the mandatory end section to navigation, never to the printed contents list."""
    return [*entries, {
        "id": edition_status_id,
        "title": "Edition and review status",
        "level": 2,
        "in_toc": False,
        "editor_entry": False,
        "style": "none",
        "number": 1,
        "marker": "",
    }]


@require_GET
def reader(request, pk, *, workspace_page=False, initial_tab="read"):
    from library.services.book_views import layout_context, publication_view
    from library.services.document_metadata import metadata_context, with_metadata_page
    from library.services.reading_styles import style_context
    from library.services.semantic_documents import inline_quote_presentation

    rendition = get_object_or_404(Rendition.objects.select_related("document", "snapshot"), pk=pk)
    destination = redirect_member(rendition.document, version=rendition)
    if destination:
        return destination
    try:
        reading_style = style_context(request, rendition)
    except ValueError as exc:
        return HttpResponse(str(exc), status=400, content_type="text/plain")
    book = rendition.structure.get("book")
    projection = (
        publication_view(
            rendition.html, rendition.structure["toc"], rendition.title,
            book=bool(book), metadata=rendition.metadata,
        )
        if (
            getattr(rendition, "document_publication", None)
            or rendition.metadata.get("layout")
        )
        else {"content_html": rendition.html, "entries": rendition.structure["toc"]}
    )
    projection["content_html"] = inline_quote_presentation(
        projection["content_html"], rendition.format_version,
    )
    display_author = rendition.metadata.get("author", "").strip() or source_name(
        rendition.document.url)
    identifiers = endmatter_ids(projection["content_html"])
    metadata_values = metadata_context(
        rendition.metadata, rendition.title, display_author, book, rendition.document.url,
    )
    metadata_values["metadata_page_id"] = identifiers["metadata_page_id"]
    navigation = with_metadata_page(projection["entries"], rendition.metadata, book)
    for entry in navigation:
        if entry["id"] == "document-metadata":
            entry["id"] = identifiers["metadata_page_id"]
    navigation = with_edition_status(navigation, identifiers["edition_status_id"])
    page_layout = layout_context(rendition.metadata, bool(book))
    if "body_separation" in projection:
        page_layout["layout_policy"] = True
        page_layout["layout_boundaries"]["body"]["value"] = projection["body_separation"]
    return render(
        request,
        "library/reader_workspace.html" if workspace_page else "library/reader.html",
        {
            **reading_style,
            "version": rendition,
            "reader_target": rendition.document.reader_target(),
            "editor_pilot": settings.READING_HUB_EDITOR_PILOT,
            "can_edit_work": bool(
                request.user.is_authenticated and (
                    request.user.is_staff or request.user.has_perm("library.review_metadata")
                )
            ),
            "display_author": display_author,
            **metadata_values,
            **page_layout,
            "toc": toc_tree(navigation),
            "edition_status_id": identifiers["edition_status_id"],
            "contents_toc": contents_tree(projection["entries"]),
            "content_html": projection["content_html"],
            "generated_book": bool(getattr(rendition, "document_publication", None)),
            "last_check": rendition.document.checks.order_by("-checked_at").first(),
            "workspace_page": workspace_page,
            "initial_tab": initial_tab,
        },
    )


@require_GET
def history(request, pk):
    document = get_object_or_404(Document, pk=pk)
    destination = redirect_member(document)
    if destination:
        return destination
    return redirect("document-lineage", pk=document.pk)


@require_POST
def refresh(request, pk):
    document = get_object_or_404(Document, pk=pk)
    return enqueue_response(request, document.url, Job.Mode.REFRESH)


@require_POST
def reformat(request, pk):
    version = get_object_or_404(Rendition.objects.select_related("snapshot", "document"), pk=pk)
    return enqueue_response(request, version.document.url, Job.Mode.REFORMAT, version.snapshot)


@require_http_methods(["GET", "POST"])
@metadata_reviewer_required
def reimport_book(request, pk):
    version = get_object_or_404(Rendition.objects.select_related("snapshot", "document"), pk=pk)
    source, error, digest = None, "", ""
    try:
        source = book_reimport_source(version.snapshot.manifest)
        digest = fingerprint({
            "snapshot": version.snapshot_id,
            "parts": [asdict(part) for part in source.parts],
        })
        if request.method == "POST":
            if request.POST.get("confirm") != "yes":
                raise ValueError("Confirm fetching the linked sections as a book.")
            if request.POST.get("preview_digest") != digest:
                raise ValueError(
                    "The proposed sections changed. Review this preview and confirm again."
                )
            return queued_response(enqueue(
                version.document.url, Job.Mode.BOOK, version.snapshot,
            ))
    except (ImportFailure, ValueError, OSError) as exc:
        error = str(exc)
    return render(request, "library/reimport_book.html", {
        "version": version, "source": source, "reimport_error": error,
        "preview_digest": digest,
    }, status=422 if error else 200)


@require_GET
def job_detail(request, pk):
    job = get_object_or_404(Job.objects.select_related("document", "rendition"), pk=pk)
    return render(request, "library/job.html", {"job": job})


@require_GET
def job_status(request, pk):
    job = get_object_or_404(Job, pk=pk)
    return JsonResponse(
        {
            "status": job.status,
            "stage": job.stage,
            "completed": job.completed,
            "total": job.total,
            "error": job.error,
            "url": reverse("reader", kwargs={"pk": job.rendition_id}) if job.rendition_id else None,
        }
    )


@require_POST
def retry_job(request, pk):
    job = get_object_or_404(Job.objects.select_related("document", "snapshot"), pk=pk)
    if job.status != Job.Status.FAILED:
        return redirect("job", pk=job.pk)
    if job.mode == Job.Mode.BOOK:
        return redirect("reimport-book", pk=job.snapshot.renditions.order_by("pk").first().pk)
    mode = job.mode if job.mode == Job.Mode.REFORMAT else Job.Mode.REFRESH
    return enqueue_response(request, job.document.url, mode, job.snapshot)


@require_GET
def reader_stylesheet(request, pk):
    from library.services.semantic_documents import inline_quote_stylesheet

    rendition = get_object_or_404(Rendition.objects.select_related("document"), pk=pk)
    destination = redirect_member(rendition.document, version=rendition, stylesheet=True)
    if destination:
        return destination
    stylesheet = inline_quote_stylesheet(rendition.stylesheet, rendition.format_version)
    return HttpResponse(stylesheet, content_type="text/css; charset=utf-8")


@require_GET
def reader_pdf(request, pk):
    from library.services.reading_styles import selected_style, selected_theme
    rendition = get_object_or_404(Rendition.objects.select_related("document"), pk=pk)
    destination = redirect_member(rendition.document, version=rendition, pdf=True)
    if destination:
        return destination
    try:
        reading_style = selected_style(request, rendition)
    except ValueError as exc:
        return HttpResponse(str(exc), status=400, content_type="text/plain")
    try:
        path = cached_pdf(rendition, reading_style, theme=selected_theme(request))
        return FileResponse(
            path.open("rb"),
            content_type="application/pdf",
            as_attachment=True,
            filename=pdf_filename(rendition.title),
        )
    except (PDFExportError, OSError) as exc:
        logger.exception("Unable to export rendition %s as PDF", pk)
        response = render(
            request, "library/pdf_error.html", {"version": rendition, "error": str(exc)}, status=503
        )
        response.headers["Retry-After"] = "10"
        return response


@require_GET
def asset(request, digest):
    blob = get_object_or_404(
        Blob.objects.filter(renditionasset__isnull=False).distinct(), digest=digest
    )
    try:
        file = blob_path(digest).open("rb")
    except OSError:
        logger.exception("Published asset %s is unavailable", digest)
        return HttpResponse(
            "Cached image unavailable. Check storage or refresh the source.",
            status=503,
            content_type="text/plain",
        )
    response = FileResponse(file, content_type=blob.media_type)
    response.headers["Content-Disposition"] = f'inline; filename="{digest}"'
    return response
