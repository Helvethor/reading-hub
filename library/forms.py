from django import forms

from library.models import CrawlSite
from library.services.errors import ImportFailure
from library.services.fetch import canonical_url


class URLRequestForm(forms.Form):
    url = forms.URLField(
        max_length=2048,
        label="Article or book URL",
        assume_scheme="https",
        widget=forms.URLInput(
            attrs={
                "placeholder": "https://…",
                "autocomplete": "url",
                "required": True,
            }
        ),
    )

    def clean_url(self):
        try:
            return canonical_url(self.cleaned_data["url"])
        except ImportFailure as exc:
            raise forms.ValidationError(str(exc)) from exc


class ReviewerTaskForm(forms.Form):
    title = forms.CharField(max_length=200, label="Task name")
    scope = forms.CharField(
        max_length=1000, label="What to review",
        help_text="Name the article, chapters or passages included; state what is excluded.",
    )
    instructions = forms.CharField(
        max_length=5000, widget=forms.Textarea(attrs={"rows": 4}), label="What to do",
        help_text="Describe source-backed corrections and how to check the result.",
    )


class ReviewerResultForm(forms.Form):
    revision = forms.TypedChoiceField(coerce=int, label="Saved result")
    outcome = forms.ChoiceField(
        choices=[("", "Choose an outcome"), ("completed", "Completed the task"),
                 ("blocked", "Could not complete the task")],
        label="Outcome",
    )
    active_minutes = forms.IntegerField(
        required=False, min_value=0, max_value=100000, label="Active review time (minutes)",
        help_text="Include source inspection and rework, exclude breaks. "
        "Leave blank if not measured.",
    )
    remaining_errors = forms.IntegerField(
        required=False, min_value=0, max_value=100000, label="Remaining errors observed",
        help_text="Blank means unknown, not zero. Count only the stated scope.",
    )
    severe_errors = forms.IntegerField(
        required=False, min_value=0, max_value=100000, label="Of these, severe errors",
        help_text="Content loss, meaning changes, broken navigation or blocked completion.",
    )
    checks = [
        ("not_tested", "Not tested"), ("completed", "Completed"),
        ("blocked", "Blocked / failed"),
    ]
    keyboard = forms.ChoiceField(choices=checks, label="Keyboard-only use")
    screen_reader = forms.ChoiceField(choices=checks, label="Screen-reader use")
    narrow_screen = forms.ChoiceField(choices=checks, label="Narrow-screen use")
    notes = forms.CharField(
        max_length=5000, widget=forms.Textarea(attrs={"rows": 4}),
        label="What worked or failed",
        help_text="Describe residual errors, failed actions and what you actually tested.",
    )

    def __init__(self, *args, run, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["revision"].choices = [
            (0, "Starting document (no saved changes)"),
            *[(row.revision, f"Saved revision {row.revision} — {row.get_review_display()}")
              for row in run.draft.revisions.all()],
        ]
        choices = self.fields["revision"].choices
        self.fields["revision"].initial = choices[1][0] if len(choices) > 1 else 0

    def clean(self):
        cleaned = super().clean()
        severe, total = cleaned.get("severe_errors"), cleaned.get("remaining_errors")
        if severe is not None and (total is None or severe > total):
            self.add_error("severe_errors", "Provide a total error count at least this large.")
        return cleaned


class CrawlSettingsForm(forms.ModelForm):
    max_pages = forms.IntegerField(min_value=1, max_value=1000000, label="Page requests per run")
    max_bytes = forms.IntegerField(min_value=1024, max_value=10 * 1024**3, label="Bytes per run")
    max_urls = forms.IntegerField(min_value=1, max_value=1000000, label="Discovered URL limit")
    request_interval = forms.IntegerField(
        min_value=1, max_value=300, label="Minimum seconds between requests"
    )
    fetch_articles = forms.BooleanField(
        required=False, label="Fetch article metadata and cache source HTML"
    )

    class Meta:
        model = CrawlSite
        fields = ["max_pages", "max_bytes", "max_urls", "request_interval", "fetch_articles"]


class WorkerMemoryForm(forms.Form):
    memory_mib = forms.IntegerField(
        min_value=256,
        max_value=8192,
        label="Memory ceiling per worker (MiB)",
        help_text="Hard virtual-address-space ceiling, not reserved RAM. Changes apply on restart.",
    )


class WorkerPoolForm(WorkerMemoryForm):
    worker_count = forms.IntegerField(
        min_value=1,
        max_value=8,
        label="Number of workers",
        help_text="Default: 1. Different sources and archive sampling can run concurrently.",
    )
