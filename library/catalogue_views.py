import json
import re
from calendar import month_name
from datetime import timedelta
from urllib.parse import urlencode

from django.conf.locale import LANG_INFO
from django.core.paginator import Paginator
from django.db.models import Case, CharField, Q, Value, When
from django.db.models.functions import Coalesce, Lower, NullIf, Trim
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.module_loading import import_string
from django.utils.translation import get_language_info
from django.views.decorators.http import require_GET, require_POST

from library.account_views import administrator_required
from library.forms import CrawlSettingsForm
from library.models import CatalogueEntry, CatalogueWorker, Document, Job, Rendition, URLAlias
from library.profile import get_profile
from library.services.catalogue import change_site, configured_sites, enrich_from_rendition
from library.services.errors import ImportFailure
from library.services.metadata_review import catalogue_author_names
from library.services.pipeline import enqueue
from library.sources.capitalization import normalize_capitalization
from library.sources.classification import clean_authors, normalize_language, split_authors, unique
from library.views import enqueue_error, queued_response

GROUPS = {
    "source": "Source site",
    "author": "Author",
    "published": "Date",
    "year": "Year",
    "month": "Month",
    "topic": "Topic",
    "era": "Era",
    "language": "Language",
}
ORDERS = {
    "title": "Title",
    "published": "Date",
    "author": "Author",
    "source": "Source site",
    "language": "Language",
}


def language_label(value):
    value = normalize_language(value)
    if not value or value == "und":
        return "Unknown language"
    code = (
        value
        if value in LANG_INFO
        else next((candidate for candidate in LANG_INFO if candidate.startswith(value + "-")), "")
    )
    info = get_language_info(code) if code else None
    return f"{info['name']} ({value})" if info else value


def require_catalogue():
    if not get_profile().catalogue_enabled:
        raise Http404("The catalogue is disabled in this profile.")


def controls_context(invalid_site=None, form=None, error=""):
    sites = configured_sites()
    labels = {s.host: s.label for s in get_profile().sources}
    rows = [
        {
            "site": site,
            "label": labels[site.host],
            "form": form
            if site.pk == invalid_site and form
            else CrawlSettingsForm(instance=site, auto_id=f"crawl_{site.pk}_%s"),
            "pending": site.frontier.filter(status="pending").count(),
            "failed": site.frontier.filter(status="failed").count(),
            "entries": site.entries.count(),
            "captures": site.captures.count(),
            "recent_errors": site.frontier.exclude(error="").order_by("-pk")[:3],
        }
        for site in sites.order_by("pk")
    ]
    worker = CatalogueWorker.objects.filter(profile=get_profile().key).first()
    corpus_report = None
    service = get_profile().corpus_service
    if service:
        corpus = import_string(service)()
        try:
            corpus_report = corpus.report()
        finally:
            corpus.close()
    return {
        "corpus": corpus_report,
        "rows": rows,
        "control_error": error,
        "worker": worker,
        "worker_recent": worker and worker.heartbeat >= timezone.now() - timedelta(seconds=90),
        "import_busy": Job.objects.filter(status=Job.Status.RUNNING).exists(),
    }


@require_GET
@administrator_required
def crawl_controls(request):
    require_catalogue()
    return render(request, "library/crawl_controls.html", controls_context())


@require_POST
@administrator_required
def crawl_control(request, pk):
    require_catalogue()
    site = get_object_or_404(configured_sites(), pk=pk)
    action = request.POST.get("action")
    error = ""
    form = None
    if action not in {"save", "pause", "resume", "restart"}:
        error = "Unknown crawl operation."
    else:
        form = CrawlSettingsForm(request.POST, instance=site, auto_id=f"crawl_{site.pk}_%s")
        if action == "pause":
            change_site(site, action)
            return redirect("crawl-controls")
        if form.is_valid():
            try:
                change_site(site, action, form.cleaned_data)
            except ValueError as exc:
                error = str(exc)
            else:
                return redirect("crawl-controls")
    return render(
        request,
        "library/crawl_controls.html",
        controls_context(site.pk, form, error),
        status=400,
    )


@require_POST
def catalogue_open(request, pk):
    require_catalogue()
    entry = get_object_or_404(
        CatalogueEntry,
        pk=pk,
        discovery_only=False,
        site__profile=get_profile().key,
        site__host__in=[s.host for s in get_profile().sources],
    )
    try:
        result = enqueue(entry.url)
    except ImportFailure as exc:
        return enqueue_error(request, entry.url, exc)
    if isinstance(result, Rendition):
        enrich_from_rendition(result)
    return queued_response(result)


def group_keys(entry, field, labels):
    if field == "author":
        keys = catalogue_author_names(entry) or [entry.display_author]
    elif field == "topic":
        keys = entry.topics or unique(entry.topic.split(","))
    elif field == "language":
        keys = [language_label(entry.language)]
    elif field in {"year", "month"}:
        pattern = r"^\d{4}(?=-|$)" if field == "year" else r"^\d{4}-(?:0[1-9]|1[0-2])(?=-|T|$)"
        match = re.match(pattern, entry.published)
        keys = [match.group()] if match else []
    else:
        key = labels[entry.site.host] if field == "source" else getattr(entry, field)
        if field == "published":
            key = key.split("T", 1)[0]
        keys = [key] if key else []
    return unique(keys) or [f"Unknown {GROUPS[field].lower()}"]


def make_tree(entries, levels, labels, descending, query, path):
    if not levels:
        return {"entries": entries, "children": []}
    counts = {}
    for entry in entries:
        for key in group_keys(entry, levels[0], labels):
            counts[key] = counts.get(key, 0) + 1
    return {
        "entries": [],
        "children": [
            {
                "label": key,
                "count": counts[key],
                "url": reverse("catalogue")
                + "?"
                + urlencode({**query, "branch": json.dumps([*path, key])}),
            }
            for key in sorted(counts, key=str.casefold, reverse=descending)
        ],
    }


@require_GET
def catalogue(request):
    require_catalogue()
    profile = get_profile()
    labels = {s.host: s.label for s in profile.sources}
    primary = request.GET.get("group", "source")
    secondary = request.GET.get("then", "author")
    order = request.GET.get("order", "title")
    direction = request.GET.get("direction", "asc")
    source = request.GET.get("source", "")
    year = request.GET.get("year", "")
    month = request.GET.get("month", "")
    requested_language = request.GET.get("language", "").strip().lower()
    language = normalize_language(requested_language)
    errors = []
    if (
        primary not in GROUPS
        or secondary not in {"", *GROUPS}
        or order not in ORDERS
        or direction not in {"asc", "desc"}
        or (source and source not in labels)
        or (year and not re.fullmatch(r"[1-9]\d{3}", year))
        or (month and not re.fullmatch(r"0[1-9]|1[0-2]", month))
        or (requested_language and not language)
    ):
        errors.append("Unknown catalogue display option. Showing the default hierarchy.")
        primary, secondary, order, direction, source = "source", "author", "title", "asc", ""
        year, month = "", ""
        language = ""
    entries = (
        CatalogueEntry.objects.filter(
            site__profile=profile.key,
            site__host__in=labels,
            discovery_only=False,
            book__isnull=True,
        )
        .select_related("site")
        .prefetch_related("people__author")
        .annotate(
            display_author=Case(
                When(
                    metadata_overrides__has_key="authors",
                    then=Coalesce(NullIf(Trim("author"), Value("")), Value("Unknown author")),
                ),
                default=Coalesce(
                    NullIf(Trim("author"), Value("")),
                    Case(
                        *[
                            When(site__host=host, then=Value(label))
                            for host, label in labels.items()
                        ],
                        default="site__host",
                        output_field=CharField(),
                    ),
                ),
                output_field=CharField(),
            )
        )
    )
    if source:
        entries = entries.filter(site__host=source)
    languages = {
        normalize_language(value) or "und" for value in entries.values_list("language", flat=True)
    }
    if language:
        languages.add(language)
        entries = entries.filter(
            Q(language="") | Q(language="und")
            if language == "und"
            else Q(language=language) | Q(language__startswith=language + "-")
        )
    years = sorted(
        {
            value[:4]
            for value in entries.values_list("published", flat=True)
            if re.match(r"^[1-9]\d{3}(?:-|$)", value)
        },
        reverse=True,
    )
    if year:
        entries = entries.filter(published__regex=rf"^{year}(?:-|$)")
        if year not in years:
            years = sorted([*years, year], reverse=True)
    if month:
        entries = entries.filter(published__regex=rf"^[1-9]\d{{3}}-{month}(?:-|$|T)")
    search = request.GET.get("q", "").strip()[:200]
    if search:
        entries = entries.filter(
            Q(title__icontains=search)
            | Q(display_author__icontains=search)
            | (
                Q(people__author__name__icontains=search)
                & ~Q(metadata_overrides__has_key="authors")
            )
            | Q(topic__icontains=search)
            | Q(topics__icontains=search)
        ).distinct()
    field = "site__host" if order == "source" else order
    if field == "author":
        field = "display_author"
    expression = Lower(field)
    expression = expression.desc() if direction == "desc" else expression.asc()
    entries = list(entries.order_by(expression, "pk"))
    for entry in entries:
        entry.language = normalize_language(entry.language)
        entry.author = normalize_capitalization(entry.author, author=True)
        entry.authors = clean_authors(entry.authors or split_authors(entry.author))
        entry.display_authors = catalogue_author_names(entry)
        entry.display_author = normalize_capitalization(entry.display_author, author=True)
    if order == "author":
        entries.sort(
            key=lambda entry: (
                ", ".join(entry.display_authors).casefold()
                if entry.display_authors
                else entry.display_author.casefold()
            ),
            reverse=direction == "desc",
        )
    total_count = len(entries)
    levels = list(dict.fromkeys([primary] + ([secondary] if secondary else [])))
    query = {
        "group": primary,
        "then": secondary,
        "order": order,
        "direction": direction,
        "source": source,
        "q": search,
        "year": year,
        "month": month,
        "language": language,
    }
    try:
        path = json.loads(request.GET.get("branch", "[]"))
        if (
            not isinstance(path, list)
            or len(path) > len(levels)
            or any(not isinstance(key, str) or len(key) > 1000 for key in path)
        ):
            raise ValueError("Invalid catalogue branch.")
    except ValueError, TypeError:
        errors.append("Invalid catalogue branch. Showing the full hierarchy.")
        path = []
    for level, key in zip(levels, path, strict=False):
        entries = [entry for entry in entries if key in group_keys(entry, level, labels)]
    page = Paginator(entries, profile.page_size).get_page(request.GET.get("page"))
    remaining_levels = levels[len(path) :]
    tree = make_tree(
        entries if remaining_levels else list(page),
        remaining_levels,
        labels,
        direction == "desc",
        query,
        path,
    )
    if not remaining_levels and tree["entries"]:
        entry_urls = [entry.url for entry in tree["entries"]]
        work_ids = dict(
            Document.objects.filter(url__in=entry_urls).values_list("url", "pk")
        )
        work_ids.update(
            URLAlias.objects.filter(url__in=entry_urls).values_list("url", "document_id")
        )
        for entry in tree["entries"]:
            entry.work_id = work_ids.get(entry.url)
    browse_query = urlencode({**query, "branch": json.dumps(path)})
    context = {
        "tree": tree,
        "leaf": not remaining_levels,
        "total_count": total_count,
        "branch_path": path,
        "parent_url": "?" + urlencode({**query, "branch": json.dumps(path[:-1])}),
        "page": page,
        "groups": GROUPS.items(),
        "orders": ORDERS.items(),
        "selected_group": primary,
        "selected_then": secondary,
        "selected_order": order,
        "selected_direction": direction,
        "selected_source": source,
        "search": search,
        "years": years,
        "months": [(f"{number:02}", month_name[number]) for number in range(1, 13)],
        "selected_year": year,
        "selected_month": month,
        "languages": sorted(
            [(value, language_label(value)) for value in languages], key=lambda pair: pair[1]
        ),
        "selected_language": language,
        "browse_query": browse_query,
        "browse_errors": errors,
    }
    return render(
        request,
        "library/catalogue_branch.html"
        if request.GET.get("partial") == "1"
        else "library/catalogue.html",
        context,
    )
