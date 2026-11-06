"""Bounded reading preferences shared verbatim by browser and PDF presentation."""

import hashlib
import json

from django import forms
from django.core import signing
from django.urls import reverse

from library.models import ReadingStyleProfile

FONTS = {
    "serif": ('"Liberation Serif", Georgia, serif', "Liberation Serif (serif)"),
    "sans": ('"Liberation Sans", Arial, sans-serif', "Liberation Sans (sans-serif)"),
    "mono": ('"Liberation Mono", monospace', "Liberation Mono (monospace)"),
    "dyslexic": ('"OpenDyslexic", "Liberation Sans", sans-serif', "OpenDyslexic"),
}
FONT_FILES = {
    f"{filename}-{variant}.{extension}": (family, style, weight)
    for filename, family, extension in (
        ("OpenDyslexic", "OpenDyslexic", "otf"),
        ("LiberationSerif", "Liberation Serif", "ttf"),
        ("LiberationSans", "Liberation Sans", "ttf"),
        ("LiberationMono", "Liberation Mono", "ttf"),
    )
    for variant, style, weight in (
        ("Regular", "normal", 400), ("Bold", "normal", 700),
        ("Italic", "italic", 400), ("BoldItalic", "italic", 700),
    )
}
DEFAULTS = {
    "font_mode": "mixed", "body_font": "serif", "title_font": "sans",
    "metadata_font": "sans", "contents_font": "sans", "code_font": "mono",
    "paragraph_align": "left", "title_align": "left",
    "font_size": 14, "line_height": 1.65, "letter_spacing": 0, "word_spacing": 0,
    "paragraph_spacing": 1, "line_width": 70, "contrast": "standard",
    "italic_to_bold": False, "underline_to_bold": False, "hyphenation": False,
}
PRESET_NAME = "Marxist — standard (read-only)"
SALT = "reading-hub-reading-style-v1"
STYLE_VERSION = 4


class ReadingStyleForm(forms.Form):
    font_mode = forms.ChoiceField(label="Font combination", choices=[
        ("mixed", "Mixed: per-concern fonts"), ("serif", "All serif"), ("sans", "All sans-serif"),
        ("dyslexic", "All OpenDyslexic"),
    ])
    body_font = forms.ChoiceField(label="Prose font", choices=[(k, v[1]) for k, v in FONTS.items()])
    title_font = forms.ChoiceField(label="Heading font",
                                  choices=[(k, v[1]) for k, v in FONTS.items()])
    metadata_font = forms.ChoiceField(label="Metadata font",
                                     choices=[(k, v[1]) for k, v in FONTS.items()])
    contents_font = forms.ChoiceField(label="Contents font",
                                     choices=[(k, v[1]) for k, v in FONTS.items()])
    code_font = forms.ChoiceField(label="Preformatted / code font",
                                 choices=[(k, v[1]) for k, v in FONTS.items()])
    paragraph_align = forms.ChoiceField(label="Default paragraph alignment", choices=[
        (value, value.title()) for value in ("left", "center", "right", "justify")
    ], help_text="Explicit alignment on an individual block is preserved.")
    title_align = forms.ChoiceField(label="Default title alignment", choices=[
        (value, value.title()) for value in ("left", "center", "right", "justify")
    ])
    font_size = forms.FloatField(label="General font size (pt)", min_value=9, max_value=28,
                                widget=forms.NumberInput(attrs={"step": ".5"}))
    line_height = forms.FloatField(label="Line height", min_value=1.2, max_value=2.5,
                                  widget=forms.NumberInput(attrs={"step": ".05"}))
    letter_spacing = forms.FloatField(label="Letter spacing (em)", min_value=0, max_value=.2,
                                     widget=forms.NumberInput(attrs={"step": ".01"}))
    word_spacing = forms.FloatField(label="Extra word spacing (em)", min_value=0, max_value=.5,
                                   widget=forms.NumberInput(attrs={"step": ".01"}))
    paragraph_spacing = forms.FloatField(
        label="Paragraph spacing (em)", min_value=.25, max_value=2,
        widget=forms.NumberInput(attrs={"step": ".05"}),
    )
    line_width = forms.IntegerField(label="Maximum line length (characters)", min_value=40,
                                   max_value=100)
    contrast = forms.ChoiceField(label="Page contrast", choices=[
        ("theme", "Follow theme (transparent page)"),
        ("standard", "Standard: dark on white"), ("cream", "Dark on cream"),
        ("high", "High contrast: black on white"),
    ])
    italic_to_bold = forms.BooleanField(label="Show italics as bold, not slanted", required=False)
    underline_to_bold = forms.BooleanField(label="Show underlining as bold", required=False,
                                         help_text="Links remain visibly underlined.")
    hyphenation = forms.BooleanField(label="Allow automatic hyphenation", required=False)


def validate_style(value):
    if not isinstance(value, dict) or set(value) != set(DEFAULTS):
        raise ValueError("Reading style must contain exactly the supported settings.")
    for key in ("italic_to_bold", "underline_to_bold", "hyphenation"):
        if type(value[key]) is not bool:
            raise ValueError("Accessibility switches must be boolean.")
    form = ReadingStyleForm(value)
    if not form.is_valid():
        raise ValueError("Invalid reading style: " + form.errors.as_text())
    return form.cleaned_data


def style_token(settings):
    return signing.dumps(validate_style(settings), salt=SALT, compress=True)


def token_style(token):
    if not isinstance(token, str) or len(token) > 8192:
        raise ValueError("Invalid reading style token.")
    try:
        value = signing.loads(token, salt=SALT)
    except signing.BadSignature as exc:
        raise ValueError("Reading style link is invalid. Apply your settings again.") from exc
    return validate_style(value)


def style_digest(settings):
    return hashlib.sha256(json.dumps(
        [STYLE_VERSION, validate_style(settings)], sort_keys=True,
    ).encode()).hexdigest()[:24]


def profile_key(value):
    if not value.isascii() or not value.isdecimal() or len(value) > 19:
        raise ValueError("Choose an available reading style profile.")
    key = int(value)
    if key < 1 or key > 2**63 - 1:
        raise ValueError("Choose an available reading style profile.")
    return key


def stylesheet_url(token):
    return reverse("reading-style-css") + f"?style={token}&v={STYLE_VERSION}"


def selected_style(request):
    if request.GET.get("style"):
        return token_style(request.GET["style"])
    if request.GET.get("style_action") == "apply":
        form = ReadingStyleForm(request.GET)
        if not form.is_valid():
            raise ValueError("Invalid reading style: " + form.errors.as_text())
        return form.cleaned_data
    selected = request.GET.get("style_profile")
    if request.GET.get("style_action") == "load" and not selected:
        raise ValueError("Choose a profile to load.")
    if selected == "marxist":
        return dict(DEFAULTS)
    profiles = ReadingStyleProfile.objects.filter(owner=request.user) \
        if request.user.is_authenticated else ReadingStyleProfile.objects.none()
    if selected:
        profile = profiles.filter(pk=profile_key(selected)).first()
        if profile is None:
            raise ValueError("This reading style profile is not available to your account.")
        return validate_style(profile.settings)
    profile = profiles.filter(is_default=True).first()
    return validate_style(profile.settings) if profile else dict(DEFAULTS)


def style_context(request):
    settings = selected_style(request)
    token = style_token(settings)
    profiles = list(ReadingStyleProfile.objects.filter(owner=request.user)) \
        if request.user.is_authenticated else []
    default = next((str(profile.pk) for profile in profiles if profile.is_default), "marxist")
    selected = request.GET.get("style_profile", default)
    if (request.GET.get("style") or request.GET.get("style_action") == "apply") \
            and not request.GET.get("style_profile"):
        selected = ""
    form = ReadingStyleForm(initial=settings)
    return {
        "reading_style": settings, "reading_style_token": token,
        "reading_style_url": stylesheet_url(token),
        "reading_style_form": form,
        "reading_style_profiles": profiles, "reading_style_profile": selected,
        "reading_default_profile": default,
        "reading_preset_name": PRESET_NAME,
        "reading_style_version": STYLE_VERSION,
        "reading_style_groups": [
            ("Typography", [form[key] for key in (
                "font_mode", "font_size", "paragraph_align", "title_align",
            )]),
            ("Fonts by purpose", [form[key] for key in (
                "body_font", "title_font", "metadata_font", "contents_font", "code_font",
            )]),
            ("Spacing & page", [form[key] for key in (
                "line_height", "paragraph_spacing", "letter_spacing", "word_spacing",
                "line_width", "contrast",
            )]),
            ("Reading aids", [form[key] for key in (
                "italic_to_bold", "underline_to_bold", "hyphenation",
            )]),
        ],
    }


def font_css(base):
    return "\n".join(
        f'@font-face {{ font-family: "{family}"; '
        f'src: url("{base}{filename}"); '
        f"font-style: {style}; font-weight: {weight}; font-display: swap; }}"
        for filename, (family, style, weight) in FONT_FILES.items()
    )


def style_css(settings, font_base="/static/library/fonts/"):
    from library.profile import get_profile

    value = validate_style(settings)
    def family(concern):
        return FONTS[
            value[f"{concern}_font"] if value["font_mode"] == "mixed" else value["font_mode"]
        ][0]
    profile = get_profile()
    theme = value["contrast"] == "theme"
    ink, paper = {"theme": (profile.reading_ink, profile.reading_paper),
                  "standard": ("#302221", "#ffffff"), "cream": ("#24201c", "#fff4d8"),
                  "high": ("#000000", "#ffffff")}[value["contrast"]]
    scope = ".publication-content"
    text = f"{scope} .reader-content"
    titles = f"{scope} :is(h1,h2,h3,h4,h5,h6)"
    css = font_css(font_base)
    css += f"""
{scope} {{
  color: {f'var(--ink, {ink})' if theme else ink};
  background: {'transparent' if theme else paper}; font-size: {value['font_size']}pt;
  line-height: {value['line_height']}; font-family: {family('body')};
  letter-spacing: {value['letter_spacing']}em; word-spacing: {value['word_spacing']}em;
}}
{scope} :is(.document-header,.document-contents,.reader-content) {{
  max-width: {value['line_width']}ch; margin-inline: auto; box-sizing: border-box;
}}
{text} {{ font: inherit; color: inherit; hyphens: {'auto' if value['hyphenation'] else 'none'}; }}
{text} p {{
  text-align: {value['paragraph_align']}; margin-block-end: {value['paragraph_spacing']}em;
}}
{titles} {{
  font-family: {family('title')}; text-align: {value['title_align']};
  line-height: 1.3; letter-spacing: inherit; color: inherit;
}}
{scope} h1 {{ font-size: 2em; }}
{scope} h2 {{ font-size: 1.6em; }}
{scope} :is(.document-contents > h2,.reader-content h2) {{
  font-weight: 600; margin-block: 2.2em .85em;
}}
{text} [data-reading-marker]::before {{ content: attr(data-reading-marker); }}
{scope} h3 {{ font-size: 1.35em; }}
{scope} h4 {{ font-size: 1.15em; }}
{scope} :is(h5,h6) {{ font-size: 1em; }}
{scope} :is(.document-metadata,.document-subtitle,figcaption,.media-credit) {{
  font-family: {family('metadata')}; color: inherit;
}}
{text} :is(figcaption,.media-credit,.document-subtitle) {{
  font-family: {family('metadata')}; line-height: inherit;
}}
{text} :is(pre,code,kbd,samp) {{ font-family: {family('code')}; }}
{scope} .document-metadata {{ font-size: .9em; }}
{scope} .document-subtitle {{ font-size: 1.15em; }}
{scope} .document-contents {{ font-family: {family('contents')}; }}
{scope} .reader-content :is(.text-align-left) {{ text-align: left; }}
{scope} .reader-content :is(.text-align-right) {{ text-align: right; }}
{scope} .reader-content :is(.text-align-center) {{ text-align: center; }}
{scope} .reader-content :is(.text-align-justify) {{ text-align: justify; }}
{scope} .reader-content a > :is(sup,sub) {{
  display: inline-block; text-decoration: inherit;
}}
@media print {{
  html, body {{ background: {paper} !important; }}
  {scope} {{ color: {ink}; }}
  @page {{
    background: {paper}; color: {ink};
  }}
  @page reading-content {{
    @top-left {{ font-family: {family('metadata')}; }}
    @top-right {{ font-family: {family('metadata')}; }}
    @bottom-center {{ font-family: {family('metadata')}; }}
  }}
}}
"""
    if value["italic_to_bold"]:
        css += f"""
{scope} :is(em,i,cite,.text-italic-on,.document-subtitle,.media-credit) {{
  font-style: normal !important; font-weight: 700 !important;
}}
"""
    if value["underline_to_bold"]:
        css += f"""
{scope} :is(u,.text-underline-on) {{
  text-decoration-line: none !important; font-weight: 700 !important;
}}
{scope} :is(s,.text-strikethrough-on) {{ text-decoration-line: line-through !important; }}
{scope} a[href] {{ text-decoration-line: underline !important; }}
"""
    return css
