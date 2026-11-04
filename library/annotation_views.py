import json
from functools import wraps
from html.parser import HTMLParser

from django import forms
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from library.models import Annotation, Rendition

MAX_ANNOTATIONS = 1000


class StyleForm(forms.Form):
    kind = forms.ChoiceField(choices=Annotation.Kind)
    color = forms.ChoiceField(choices=Annotation.Color)


class SelectionForm(StyleForm):
    start = forms.IntegerField(min_value=0, max_value=2**31 - 1)
    end = forms.IntegerField(min_value=1, max_value=2**31 - 1)
    quote = forms.CharField(strip=False, max_length=20000)


def authenticated(view):
    @wraps(view)
    def guarded(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {"error": "Your session expired. Sign in to use private annotations."}, status=401
            )
        return view(request, *args, **kwargs)

    return guarded


def payload(request, form_type):
    if request.content_type != "application/json":
        return None, JsonResponse({"error": "Send annotation data as JSON."}, status=415)
    try:
        data = json.loads(request.body)
    except ValueError, UnicodeDecodeError:
        return None, JsonResponse({"error": "Invalid JSON annotation data."}, status=400)
    if not isinstance(data, dict) or set(data) != set(form_type.base_fields):
        return None, JsonResponse({"error": "Unexpected or missing annotation fields."}, status=400)
    form = form_type(data)
    if not form.is_valid():
        return None, JsonResponse({"errors": form.errors.get_json_data()}, status=400)
    return form.cleaned_data, None


class ReaderText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip_newline = False

    def handle_starttag(self, tag, attrs):
        self.skip_newline = tag in {"pre", "textarea", "listing"}

    def handle_endtag(self, tag):
        self.skip_newline = False

    def handle_comment(self, data):
        self.skip_newline = False

    def handle_data(self, data):
        if self.skip_newline and data.startswith("\n"):
            data = data[1:]
        self.skip_newline = False
        self.parts.append(data)


def reader_text(html):
    # BeautifulSoup collapses whitespace-only nodes, shifting browser selection offsets.
    parser = ReaderText()
    parser.feed(html.replace("\r\n", "\n").replace("\r", "\n"))
    parser.close()
    return "".join(parser.parts)


def matching_selection(html, start, end, quote):
    text = reader_text(html).encode("utf-16-le")
    if end <= start or end * 2 > len(text):
        return False
    try:
        return text[start * 2 : end * 2].decode("utf-16-le") == quote
    except UnicodeDecodeError:
        return False


def serialized(annotation):
    return {
        key: getattr(annotation, key)
        for key in (
            "id",
            "start",
            "end",
            "quote",
            "kind",
            "color",
            "created_at",
            "updated_at",
        )
    }


@require_http_methods(["GET", "POST"])
@authenticated
def collection(request, pk):
    rendition = get_object_or_404(Rendition, pk=pk)
    owned = Annotation.objects.filter(owner=request.user, rendition=rendition)
    if request.method == "GET":
        return JsonResponse({"annotations": [serialized(item) for item in owned]})
    data, error = payload(request, SelectionForm)
    if error is not None:
        return error
    if not matching_selection(rendition.html, data["start"], data["end"], data["quote"]):
        return JsonResponse(
            {
                "error": "The selection does not match this cached version. "
                "Reload and select the text again."
            },
            status=400,
        )
    with transaction.atomic():
        if owned.count() >= MAX_ANNOTATIONS:
            return JsonResponse(
                {
                    "error": "This version already has 1,000 private annotations. "
                    "Remove one before adding more."
                },
                status=409,
            )
        annotation = Annotation.objects.create(owner=request.user, rendition=rendition, **data)
    return JsonResponse({"annotation": serialized(annotation)}, status=201)


@require_http_methods(["PATCH", "DELETE"])
@authenticated
def detail(request, pk, annotation_id):
    annotation = get_object_or_404(
        Annotation, pk=annotation_id, rendition_id=pk, owner=request.user
    )
    if request.method == "DELETE":
        annotation.delete()
        return JsonResponse({"deleted": annotation_id})
    data, error = payload(request, StyleForm)
    if error is not None:
        return error
    annotation.kind, annotation.color = data["kind"], data["color"]
    annotation.save(update_fields=["kind", "color", "updated_at"])
    return JsonResponse({"annotation": serialized(annotation)})
