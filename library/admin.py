from django import forms
from django.contrib import admin

from library.models import ReadingStyleAdminDefault
from library.services.document_metadata import WORK_TYPES
from library.services.reading_styles import validate_style_layer


class ReadingStyleAdminDefaultForm(forms.ModelForm):
    work_type = forms.ChoiceField(choices=WORK_TYPES)
    settings = forms.JSONField(
        help_text="Sparse JSON overrides. Omit a setting to inherit; false and zero remain explicit.",
    )

    class Meta:
        model = ReadingStyleAdminDefault
        fields = ("work_type", "settings")

    def clean_settings(self):
        return validate_style_layer(self.cleaned_data["settings"])


@admin.register(ReadingStyleAdminDefault)
class ReadingStyleAdminDefaultAdmin(admin.ModelAdmin):
    form = ReadingStyleAdminDefaultForm
    list_display = ("work_type", "updated_at")
    ordering = ("work_type",)
    fields = ("work_type", "settings")
