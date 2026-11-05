import logging
from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.db.models import Q
from django.db.models.functions import Lower
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from library.forms import URLRequestForm
from library.models import Blob, CatalogueEntry, CrawlCapture, Document, Job, Rendition
from library.organization_views import redirect_member
from library.profile import SORTS, get_profile, source_name
from library.services.errors import ImportFailure
from library.services.pdf import PDFExportError, cached_pdf, pdf_filename
from library.services.pipeline import enqueue
from library.services.storage import blob_path

logger = logging.getLogger("library")


def csrf_failure(request, reason=""):
    logger.warning("CSRF rejected %s: %s", request.path, reason)
    return render(request, "library/csrf_failure.html", status=403)


def home_context(request, form=None):
    profile = get_profile()
    sort = request.GET.get("sort", profile.default_sort)
    source = request.GET.get("source", "") if profile.source_filter else ""
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
        "browse_errors": errors,
        "browse_query": urlencode({"sort": sort, "source": source}),
        "jobs": Job.objects.exclude(status=Job.Status.READY)
        .select_related("document")
        .order_by("-created_at")[:10],
    }
    return context


@require_GET
def home(request):
    return render(request, "library/home.html", home_context(request))


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
    version = document.latest()
    if version:
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


@require_GET
def reader(request, pk):
    from library.services.book_views import publication_view
    from library.services.document_metadata import metadata_rows
    from library.services.reading_styles import style_context

    rendition = get_object_or_404(Rendition.objects.select_related("document", "snapshot"), pk=pk)
    destination = redirect_member(rendition.document, version=rendition)
    if destination:
        return destination
    try:
        reading_style = style_context(request)
    except ValueError as exc:
        return HttpResponse(str(exc), status=400, content_type="text/plain")
    projection = publication_view(rendition.html, rendition.structure["toc"]) if getattr(
        rendition, "document_publication", None,
    ) else {"content_html": rendition.html, "entries": rendition.structure["toc"]}
    return render(
        request,
        "library/reader.html",
        {
            **reading_style,
            "version": rendition,
            "display_author": rendition.metadata.get("author", "").strip()
            or source_name(rendition.document.url),
            "metadata_rows": metadata_rows(rendition.metadata),
            "toc": toc_tree(projection["entries"]),
            "content_html": projection["content_html"],
            "generated_book": bool(getattr(rendition, "document_publication", None)),
            "other_versions": rendition.document.renditions.order_by("-created_at"),
            "last_check": rendition.document.checks.order_by("-checked_at").first(),
        },
    )


@require_GET
def history(request, pk):
    document = get_object_or_404(Document, pk=pk)
    destination = redirect_member(document)
    if destination:
        return destination
    return render(
        request,
        "library/history.html",
        {
            "document": document,
            "versions": document.renditions.select_related("snapshot").order_by("-created_at"),
            "checks": document.checks.order_by("-checked_at")[:20],
        },
    )


@require_POST
def refresh(request, pk):
    document = get_object_or_404(Document, pk=pk)
    return enqueue_response(request, document.url, Job.Mode.REFRESH)


@require_POST
def reformat(request, pk):
    version = get_object_or_404(Rendition.objects.select_related("snapshot", "document"), pk=pk)
    return enqueue_response(request, version.document.url, Job.Mode.REFORMAT, version.snapshot)


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
    mode = job.mode if job.mode == Job.Mode.REFORMAT else Job.Mode.REFRESH
    return enqueue_response(request, job.document.url, mode, job.snapshot)


@require_GET
def reader_stylesheet(request, pk):
    rendition = get_object_or_404(Rendition.objects.select_related("document"), pk=pk)
    destination = redirect_member(rendition.document, version=rendition, stylesheet=True)
    if destination:
        return destination
    return HttpResponse(rendition.stylesheet, content_type="text/css; charset=utf-8")


@require_GET
def reader_pdf(request, pk):
    from library.services.reading_styles import selected_style
    rendition = get_object_or_404(Rendition.objects.select_related("document"), pk=pk)
    destination = redirect_member(rendition.document, version=rendition, pdf=True)
    if destination:
        return destination
    try:
        reading_style = selected_style(request)
    except ValueError as exc:
        return HttpResponse(str(exc), status=400, content_type="text/plain")
    try:
        path = cached_pdf(rendition, reading_style)
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
