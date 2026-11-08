import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class UserSettings(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    theme = models.CharField(max_length=20, blank=True, default="")


class Document(models.Model):
    url = models.URLField(max_length=2048, unique=True)
    aliases = models.JSONField(default=list)
    title = models.CharField(max_length=1000, blank=True)
    reader_rendition = models.ForeignKey(
        "Rendition", null=True, blank=True, on_delete=models.PROTECT,
        related_name="selected_for_documents",
    )
    reader_selection_explicit = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def latest(self):
        from library.profile import get_profile

        organization = (
            ContentOrganization.objects.filter(
                entry__url=self.url, entry__site__profile=get_profile().key
            )
            .select_related("rendition")
            .first()
        )
        if organization:
            return organization.rendition
        return self.renditions.order_by("-created_at", "-pk").first()

    def reader_target(self):
        if self.reader_rendition_id:
            target = self.reader_rendition
            if target.document_id != self.pk:
                raise ValueError("The selected reader version belongs to another work.")
            return target
        return self.latest()

    def source_generated_reader_fallback(self):
        from library.profile import get_profile

        organization = (
            ContentOrganization.objects.filter(
                entry__url=self.url, entry__site__profile=get_profile().key,
            ).select_related("rendition").first()
        )
        if (
            organization
            and organization.rendition.document_id == self.pk
            and not DocumentPublication.objects.filter(
                rendition_id=organization.rendition_id,
            ).exists()
        ):
            return organization.rendition
        return (
            self.renditions.filter(document_publication__isnull=True)
            .order_by("-created_at", "-pk")
            .first()
        )


class URLAlias(models.Model):
    url = models.URLField(max_length=2048, unique=True)
    document = models.ForeignKey(Document, on_delete=models.PROTECT, related_name="url_aliases")


class Snapshot(models.Model):
    document = models.ForeignKey(Document, on_delete=models.PROTECT, related_name="snapshots")
    digest = models.CharField(max_length=64)
    manifest = models.JSONField()
    warnings = models.JSONField(default=list)
    fetched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["document", "digest"], name="unique_snapshot")
        ]


class Blob(models.Model):
    digest = models.CharField(max_length=64, primary_key=True)
    media_type = models.CharField(max_length=100)
    size = models.PositiveBigIntegerField()


class Rendition(models.Model):
    document = models.ForeignKey(Document, on_delete=models.PROTECT, related_name="renditions")
    snapshot = models.ForeignKey(Snapshot, on_delete=models.PROTECT, related_name="renditions")
    document_version = models.ForeignKey(
        "DocumentVersion", null=True, blank=True, on_delete=models.PROTECT,
        related_name="renditions",
    )
    identity = models.CharField(max_length=64, unique=True)
    title = models.CharField(max_length=1000)
    metadata = models.JSONField(default=dict)
    structure = models.JSONField()
    html = models.TextField()
    stylesheet = models.TextField()
    warnings = models.JSONField(default=list)
    app_version = models.CharField(max_length=100)
    adapter_version = models.CharField(max_length=100)
    format_version = models.CharField(max_length=100)
    output_digest = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)


class RenditionAsset(models.Model):
    rendition = models.ForeignKey(Rendition, on_delete=models.PROTECT, related_name="assets")
    blob = models.ForeignKey(Blob, on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["rendition", "blob"], name="unique_rendition_asset")
        ]

class ReadingStyleProfile(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    settings = models.JSONField()
    is_default = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "name"], name="unique_reading_style_name"),
            models.UniqueConstraint(fields=["owner"], condition=Q(is_default=True),
                                    name="one_default_reading_style"),
        ]


class ImmutableDocumentEvidenceQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValueError("Document review evidence is immutable.")

    def delete(self):
        raise ValueError("Document review evidence is immutable.")


class ImmutableDocumentEvidence(models.Model):
    objects = ImmutableDocumentEvidenceQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValueError("Document review evidence is immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Document review evidence is immutable.")


class DocumentDraftBase(ImmutableDocumentEvidence):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rendition = models.ForeignKey(
        Rendition, on_delete=models.PROTECT, related_name="document_drafts"
    )
    document_version = models.ForeignKey(
        "DocumentVersion", null=True, blank=True, on_delete=models.PROTECT,
        related_name="draft_base",
    )
    profile = models.CharField(max_length=100)
    document = models.JSONField()
    document_digest = models.CharField(max_length=64)
    evidence = models.JSONField()
    evidence_digest = models.CharField(max_length=64)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class DocumentEditRevision(ImmutableDocumentEvidence):
    class Review(models.TextChoices):
        PARTIAL = "partial", "Partial edits"
        SECTIONS = "sections", "Verified sections"
        FULL = "full", "Verified whole document"

    draft = models.ForeignKey(
        DocumentDraftBase, on_delete=models.PROTECT, related_name="revisions"
    )
    document_version = models.ForeignKey(
        "DocumentVersion", null=True, blank=True, on_delete=models.PROTECT,
        related_name="review_records",
    )
    revision = models.PositiveIntegerField()
    document = models.JSONField()
    document_digest = models.CharField(max_length=64)
    lineage = models.JSONField(default=dict)
    review = models.CharField(max_length=10, choices=Review.choices, default=Review.PARTIAL)
    verified_sections = models.JSONField(default=list)
    issues = models.JSONField(default=list)
    editorial = models.BooleanField(default=False)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-revision"]
        constraints = [
            models.UniqueConstraint(
                fields=["draft", "revision"], name="unique_document_edit_revision"
            ),
            models.CheckConstraint(
                condition=Q(revision__gte=1), name="positive_document_edit_revision"
            ),
        ]


class DocumentVersion(ImmutableDocumentEvidence):
    class Origin(models.TextChoices):
        SOURCE_GENERATED = "source_generated", "Source-generated"
        WORKING_COPY = "working_copy", "Working copy"
        MANUAL_SAVE = "manual_save", "Manual save"

    class Ancestry(models.TextChoices):
        KNOWN = "known", "Known"
        UNKNOWN = "unknown", "Unknown"

    document = models.ForeignKey(
        Document, on_delete=models.PROTECT, related_name="document_versions"
    )
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT,
        related_name="children",
    )
    source_snapshot = models.ForeignKey(
        Snapshot, null=True, blank=True, on_delete=models.PROTECT,
        related_name="generated_versions",
    )
    origin = models.CharField(max_length=20, choices=Origin.choices)
    ancestry = models.CharField(
        max_length=10, choices=Ancestry.choices, default=Ancestry.UNKNOWN,
    )
    content_digest = models.CharField(max_length=64)
    evidence = models.JSONField(default=dict)
    evidence_digest = models.CharField(max_length=64)
    created_at = models.DateTimeField()


class DocumentBranch(ImmutableDocumentEvidence):
    document = models.ForeignKey(
        Document, on_delete=models.PROTECT, related_name="document_branches"
    )
    draft = models.OneToOneField(
        DocumentDraftBase, on_delete=models.PROTECT, related_name="branch"
    )
    base_version = models.ForeignKey(
        DocumentVersion, on_delete=models.PROTECT, related_name="based_branches",
    )
    starting_version = models.ForeignKey(
        DocumentVersion, null=True, blank=True, on_delete=models.PROTECT,
        related_name="branches",
    )
    starting_revision = models.ForeignKey(
        DocumentEditRevision, null=True, blank=True, on_delete=models.PROTECT,
        related_name="starting_branches",
    )
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField()


class DocumentPublication(ImmutableDocumentEvidence):
    revision = models.OneToOneField(
        DocumentEditRevision, on_delete=models.PROTECT, related_name="publication"
    )
    rendition = models.OneToOneField(
        Rendition, on_delete=models.PROTECT, related_name="document_publication"
    )
    preview_digest = models.CharField(max_length=64)
    publication_version = models.PositiveIntegerField(default=1, editable=False)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class DocumentLineageArchive(ImmutableDocumentEvidence):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        Document, on_delete=models.PROTECT, related_name="lineage_archives"
    )
    scope = models.JSONField()
    reason = models.TextField()
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class DocumentLineageRestore(ImmutableDocumentEvidence):
    archive = models.OneToOneField(
        DocumentLineageArchive, on_delete=models.PROTECT, related_name="restore"
    )
    reason = models.TextField(blank=True, default="")
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class DocumentReaderSelection(ImmutableDocumentEvidence):
    document = models.ForeignKey(
        Document, on_delete=models.PROTECT, related_name="reader_selections"
    )
    previous_rendition = models.ForeignKey(
        Rendition, null=True, blank=True, on_delete=models.PROTECT,
        related_name="previous_reader_selections",
    )
    rendition = models.ForeignKey(
        Rendition, on_delete=models.PROTECT, related_name="reader_selections"
    )
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.TextField()
    explicit = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class BookMembershipGeneration(ImmutableDocumentEvidence):
    rendition = models.ForeignKey(
        Rendition, on_delete=models.PROTECT, related_name="membership_generations",
    )
    binding = models.JSONField()
    binding_digest = models.CharField(max_length=64)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["rendition", "binding_digest"],
                name="unique_book_membership_generation_binding",
            ),
        ]


class ReviewerTask(ImmutableDocumentEvidence):
    starting_draft = models.ForeignKey(DocumentDraftBase, on_delete=models.PROTECT)
    title = models.CharField(max_length=200)
    scope = models.CharField(max_length=1000)
    instructions = models.TextField()
    binding = models.JSONField()
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class ReviewerRun(ImmutableDocumentEvidence):
    task = models.ForeignKey(ReviewerTask, on_delete=models.PROTECT, related_name="runs")
    draft = models.OneToOneField(DocumentDraftBase, on_delete=models.PROTECT)
    practice = models.BooleanField(default=False)
    app_version = models.CharField(max_length=100)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class ReviewerResult(ImmutableDocumentEvidence):
    run = models.OneToOneField(ReviewerRun, on_delete=models.PROTECT, related_name="result")
    revision = models.ForeignKey(
        DocumentEditRevision, null=True, blank=True, on_delete=models.PROTECT,
    )
    observations = models.JSONField()
    binding = models.JSONField()
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class Annotation(models.Model):
    class Kind(models.TextChoices):
        HIGHLIGHT = "highlight", "Highlight"
        UNDERLINE = "underline", "Underline"

    class Color(models.TextChoices):
        YELLOW = "yellow", "Yellow"
        GREEN = "green", "Green"
        BLUE = "blue", "Blue"
        PINK = "pink", "Pink"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rendition = models.ForeignKey(Rendition, on_delete=models.PROTECT, related_name="annotations")
    start = models.PositiveIntegerField()
    end = models.PositiveIntegerField()
    quote = models.TextField()
    kind = models.CharField(max_length=12, choices=Kind)
    color = models.CharField(max_length=12, choices=Color)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["pk"]
        indexes = [models.Index(fields=["owner", "rendition"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(end__gt=models.F("start")), name="annotation_nonempty"
            ),
        ]


class Job(models.Model):
    class Mode(models.TextChoices):
        IMPORT = "import", "Import"
        REFRESH = "refresh", "Refresh source"
        REFORMAT = "reformat", "Reformat stored source"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.PROTECT, related_name="jobs")
    mode = models.CharField(max_length=10, choices=Mode)
    snapshot = models.ForeignKey(Snapshot, null=True, on_delete=models.PROTECT)
    rendition = models.ForeignKey(Rendition, null=True, on_delete=models.PROTECT)
    status = models.CharField(max_length=10, choices=Status, default=Status.QUEUED)
    stage = models.CharField(max_length=250, default="Waiting for the import worker")
    completed = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True)
    error_code = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    heartbeat = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)
    worker = models.ForeignKey(
        "WorkerInstance", null=True, on_delete=models.SET_NULL, related_name="jobs"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["document"],
                condition=Q(status__in=["queued", "running"]),
                name="one_active_document_job",
            )
        ]


class FetchCheck(models.Model):
    document = models.ForeignKey(Document, on_delete=models.PROTECT, related_name="checks")
    job = models.OneToOneField(Job, on_delete=models.PROTECT)
    checked_at = models.DateTimeField(auto_now_add=True)
    outcome = models.CharField(max_length=30)
    detail = models.TextField(blank=True)


class CrawlSite(models.Model):
    profile = models.CharField(max_length=100)
    host = models.CharField(max_length=253)
    enabled = models.BooleanField(default=False)
    fetch_articles = models.BooleanField(default=False)
    max_pages = models.PositiveIntegerField(default=1000)
    max_bytes = models.PositiveBigIntegerField(default=100 * 1024 * 1024)
    max_urls = models.PositiveIntegerField(default=10000)
    request_interval = models.PositiveIntegerField(default=2)
    pages = models.PositiveIntegerField(default=0)
    downloaded = models.PositiveBigIntegerField(default=0)
    status = models.CharField(max_length=30, default="paused")
    error = models.TextField(blank=True)
    heartbeat = models.DateTimeField(null=True)
    last_step = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["profile", "host"], name="unique_crawl_site")
        ]


class CrawlPage(models.Model):
    site = models.ForeignKey(CrawlSite, on_delete=models.CASCADE, related_name="frontier")
    url = models.URLField(max_length=2048)
    is_article = models.BooleanField(default=False)
    status = models.CharField(max_length=20, default="pending")
    error = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["site", "url"], name="unique_crawl_page")]


class CatalogueEntry(models.Model):
    membership_reviewed = models.BooleanField(default=False)
    metadata_overrides = models.JSONField(default=dict)
    metadata_baseline = models.JSONField(default=dict)
    book = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="chapters"
    )
    discovery_only = models.BooleanField(default=False)
    site = models.ForeignKey(CrawlSite, on_delete=models.CASCADE, related_name="entries")
    url = models.URLField(max_length=2048)
    title = models.CharField(max_length=1000)
    author = models.CharField(max_length=1000, blank=True)
    authors = models.JSONField(default=list)
    published = models.CharField(max_length=100, blank=True)
    language = models.CharField(max_length=35, blank=True)
    topic = models.CharField(max_length=500, blank=True)
    topics = models.JSONField(default=list)
    era = models.CharField(max_length=100, blank=True)
    discovered_at = models.DateTimeField(auto_now_add=True)
    checked_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["site", "url"], name="unique_catalogue_entry")
        ]


class ContentOrganization(models.Model):
    entry = models.OneToOneField(
        CatalogueEntry, on_delete=models.PROTECT, related_name="organization"
    )
    specification = models.JSONField()
    rendition = models.ForeignKey(Rendition, on_delete=models.PROTECT)


class BookMembershipDecision(models.Model):
    entry = models.ForeignKey(CatalogueEntry, on_delete=models.PROTECT)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.TextField()
    before = models.JSONField()
    after = models.JSONField()
    evidence = models.JSONField()
    undo_of = models.ForeignKey("self", null=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-pk"]


class CatalogueOverlayDecision(models.Model):
    entry = models.ForeignKey(
        CatalogueEntry, on_delete=models.PROTECT, related_name="overlay_decisions"
    )
    correction = models.ForeignKey("SourceCorrection", on_delete=models.PROTECT)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.CharField(max_length=2000)
    before = models.JSONField()
    after = models.JSONField()
    undo_of = models.ForeignKey("self", null=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-pk"]


class ContentOrganizationDecision(models.Model):
    profile = models.CharField(max_length=100)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.TextField()
    before = models.JSONField()
    after = models.JSONField()
    evidence = models.JSONField()
    undo_of = models.ForeignKey("self", null=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-pk"]


class CanonicalAuthor(models.Model):
    name = models.CharField(max_length=500)
    authority_uri = models.URLField(max_length=2048, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "pk"]

    def __str__(self):
        return self.name


class AuthorAlias(models.Model):
    author = models.ForeignKey(CanonicalAuthor, on_delete=models.CASCADE, related_name="aliases")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    name = models.CharField(max_length=500)
    normalized_name = models.CharField(max_length=500, db_index=True)
    surname_key = models.CharField(max_length=200, db_index=True, blank=True, default="")
    language = models.CharField(max_length=35, blank=True)
    source_url = models.URLField(max_length=2048, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["author", "normalized_name", "language"], name="unique_author_alias"
            )
        ]


class MetadataSuggestion(models.Model):
    class Field(models.TextChoices):
        AUTHOR = "author", "Author identity"
        PUBLISHED = "published", "Publication date"
        TOPIC = "topic", "Topic"

    class DateType(models.TextChoices):
        PUBLICATION = "publication", "Publication"
        WRITTEN = "written", "Written"
        ONLINE_EDITION = "online_edition", "Online edition"
        UNKNOWN = "unknown", "Unspecified date"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        SUPERSEDED = "superseded", "Superseded by correction"

    entry = models.ForeignKey(
        CatalogueEntry,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="metadata_suggestions",
    )
    capture = models.ForeignKey(
        "CrawlCapture", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    field = models.CharField(max_length=20, choices=Field)
    value = models.CharField(max_length=1000)
    normalized_value = models.CharField(max_length=1000, blank=True)
    date_type = models.CharField(
        max_length=20, choices=DateType, default=DateType.UNKNOWN, blank=True
    )
    evidence = models.JSONField(default=list)
    method = models.CharField(max_length=100)
    fingerprint = models.CharField(max_length=64)
    status = models.CharField(max_length=12, choices=Status, default=Status.PENDING)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at", "pk"]
        permissions = [("review_metadata", "Can review catalogue metadata suggestions")]
        constraints = [
            models.UniqueConstraint(
                fields=["field", "fingerprint"],
                condition=Q(field="author"),
                name="unique_author_metadata_suggestion",
            ),
            models.UniqueConstraint(
                fields=["entry", "field", "fingerprint"],
                condition=Q(field__in=["published", "topic"]),
                name="unique_entry_metadata_suggestion",
            ),
        ]
        indexes = [models.Index(fields=["status", "field", "created_at"])]


class MetadataReviewEvent(models.Model):
    suggestion = models.ForeignKey(
        MetadataSuggestion, on_delete=models.PROTECT, related_name="review_events"
    )
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    previous_status = models.CharField(max_length=12, choices=MetadataSuggestion.Status)
    status = models.CharField(max_length=12, choices=MetadataSuggestion.Status)
    reason = models.TextField(blank=True)
    correction = models.ForeignKey(
        "SourceCorrection",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="review_resolutions",
    )

    class Meta:
        ordering = ["created_at", "pk"]


class CatalogueAuthor(models.Model):
    class Role(models.TextChoices):
        AUTHOR = "author", "Author"
        EDITOR = "editor", "Editor"
        TRANSLATOR = "translator", "Translator"

    entry = models.ForeignKey(CatalogueEntry, on_delete=models.CASCADE, related_name="people")
    author = models.ForeignKey(CanonicalAuthor, on_delete=models.PROTECT, related_name="works")
    source_name = models.CharField(max_length=500)
    role = models.CharField(max_length=20, choices=Role, default=Role.AUTHOR)
    suggestion = models.ForeignKey(
        MetadataSuggestion, null=True, blank=True, on_delete=models.SET_NULL, related_name="links"
    )
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["entry", "author", "role"], name="unique_catalogue_author_role"
            )
        ]


class CatalogueWorker(models.Model):
    profile = models.CharField(max_length=100, unique=True)
    heartbeat = models.DateTimeField()


class PageTypeDecision(models.Model):
    site = models.ForeignKey(
        CrawlSite, on_delete=models.PROTECT, related_name="page_type_decisions"
    )
    url = models.URLField(max_length=2048)
    discovery_only = models.BooleanField()
    previous_flags = models.JSONField(default=dict)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.CharField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-pk"]
        indexes = [models.Index(fields=["site", "url", "-id"])]


class SourceCorrection(models.Model):
    capture = models.ForeignKey(
        "CrawlCapture", on_delete=models.PROTECT, related_name="corrections"
    )
    revision = models.PositiveIntegerField()
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(blank=True)
    source_digest = models.CharField(max_length=64)
    profile = models.CharField(max_length=100)
    adapter_version = models.CharField(max_length=100)
    schema_version = models.PositiveSmallIntegerField(default=1)
    original = models.JSONField()
    expected = models.JSONField()
    imported_from = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-revision"]
        constraints = [
            models.UniqueConstraint(
                fields=["capture", "revision"], name="unique_capture_correction_revision"
            )
        ]


class ImmutableExcerptQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValueError("Excerpt revisions are immutable.")

    def delete(self):
        raise ValueError("Excerpt revisions are immutable.")


class SourceExcerptRevision(models.Model):
    definition = models.UUIDField(default=uuid.uuid4, editable=False)
    capture = models.ForeignKey("CrawlCapture", on_delete=models.PROTECT, related_name="excerpts")
    revision = models.PositiveIntegerField()
    name = models.CharField(max_length=1000)
    source_digest = models.CharField(max_length=64)
    blocks = models.JSONField()
    deleted = models.BooleanField(default=False)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.CharField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = ImmutableExcerptQuerySet.as_manager()

    class Meta:
        ordering = ["-revision"]
        constraints = [
            models.UniqueConstraint(
                fields=["definition", "revision"], name="unique_excerpt_definition_revision"
            )
        ]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValueError("Excerpt revisions are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Excerpt revisions are immutable.")


class AppendOnlyFeedbackQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValueError("Correction feedback is append-only.")

    def delete(self):
        raise ValueError("Correction feedback is append-only.")


class CorrectionFeedback(models.Model):
    class Decision(models.TextChoices):
        CORRECTION = "correction", "Explicit correction"
        VERIFIED_KEEP = "verified_keep", "Verified keep"
        SUGGESTION_ACCEPTED = "suggestion_accepted", "Suggestion accepted"
        SUGGESTION_REJECTED = "suggestion_rejected", "Suggestion rejected"
        SUGGESTION_REVISED = "suggestion_revised", "Suggestion revised"
        ABSTAINED = "abstained", "Abstained"
        SUPERSEDED = "superseded", "Superseded"
        RESET = "reset", "Reset"

    capture = models.ForeignKey(
        "CrawlCapture", on_delete=models.PROTECT, related_name="correction_feedback"
    )
    correction = models.ForeignKey(
        SourceCorrection,
        null=True,
        on_delete=models.PROTECT,
        related_name="feedback_events",
    )
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    correction_revision = models.PositiveIntegerField(default=0)
    profile = models.CharField(max_length=100)
    source_digest = models.CharField(max_length=64)
    adapter_version = models.CharField(max_length=100)
    body_digest = models.CharField(max_length=64)
    operation = models.CharField(max_length=100)
    decision = models.CharField(max_length=32, choices=Decision.choices)
    value = models.JSONField(null=True, blank=True)
    proposal_id = models.UUIDField(null=True, blank=True)
    reason = models.TextField(blank=True)

    objects = AppendOnlyFeedbackQuerySet.as_manager()

    class Meta:
        ordering = ["created_at", "pk"]
        indexes = [
            models.Index(
                fields=["capture", "body_digest", "operation", "-id"],
                name="feedback_capture_op_idx",
            )
        ]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValueError("Correction feedback is append-only.")
        if self.decision not in self.Decision.values:
            raise ValueError("Unsupported correction feedback decision.")
        if not self.operation or len(self.operation) > 100:
            raise ValueError("Feedback requires a bounded target operation.")
        if self.decision.startswith("suggestion_") and self.proposal_id is None:
            raise ValueError("Suggestion feedback requires a proposal identifier.")
        if not self.decision.startswith("suggestion_") and self.proposal_id is not None:
            raise ValueError("Only suggestion feedback may reference a proposal.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Correction feedback is append-only.")


class WorkerPool(models.Model):
    profile = models.CharField(max_length=100, unique=True)
    worker_count = models.PositiveSmallIntegerField(default=1)
    memory_mib = models.PositiveIntegerField(default=1024)


class WorkerInstance(models.Model):
    pool = models.ForeignKey(WorkerPool, on_delete=models.CASCADE, related_name="workers")
    number = models.PositiveSmallIntegerField()
    memory_mib = models.PositiveIntegerField(default=1024)
    applied_memory_mib = models.PositiveIntegerField(null=True)
    desired_running = models.BooleanField(default=False)
    restart_requested = models.BooleanField(default=False)
    status = models.CharField(max_length=20, default="stopped")
    token = models.UUIDField(null=True)
    pid = models.PositiveIntegerField(null=True)
    process_start = models.CharField(max_length=50, blank=True)
    started_at = models.DateTimeField(null=True)
    heartbeat = models.DateTimeField(null=True)
    activity = models.CharField(max_length=250, default="Stopped")
    error = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["pool", "number"], name="unique_worker_number")
        ]


class CrawlCapture(models.Model):
    discovery_only = models.BooleanField(default=False)
    site = models.ForeignKey(CrawlSite, on_delete=models.PROTECT, related_name="captures")
    url = models.URLField(max_length=2048)
    response = models.JSONField()
    captured_at = models.DateTimeField(auto_now_add=True)
