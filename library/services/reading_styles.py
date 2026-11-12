"""Bounded reading preferences shared verbatim by browser and PDF presentation."""

import hashlib
import json

from django import forms
from django.core import signing
from django.urls import reverse

from library.models import (
    ReadingStyleAccountDefault,
    ReadingStyleAdminDefault,
    ReadingStyleOutputOverride,
    ReadingStyleProfile,
)

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
    "paragraph_spacing": 1, "line_width": 70,
    "palette": "neutral", "mode": "light", "contrast": "standard",
    "italic_to_bold": False, "underline_to_bold": False, "hyphenation": False,
}
PRESET_NAME = "Marxist — standard (read-only)"
SALT = "reading-hub-reading-style-v1"
PRESENTATION_SALT = "reading-hub-presentation-snapshot-v1"
STYLE_VERSION = 7
STYLE_SCOPES = ("output", "account")

# (ink, paper, accent) per palette, light/dark mode and contrast level. Accents colour headings
# and links; None keeps them in the ink colour. Every combination is checked in tests: low
# >= 4.5:1 (WCAG AA), standard >= 7:1 (AAA), high >= 15:1, accents >= 4.5:1 (7:1 for high).
PALETTES = {
    "neutral": ("Neutral", {
        "light": {"low": ("#5b5552", "#f1eee9", None), "standard": ("#302221", "#ffffff", None),
                  "high": ("#000000", "#ffffff", None)},
        "dark": {"low": ("#b9b2aa", "#2a2826", None), "standard": ("#e6e0d8", "#1c1a19", None),
                 "high": ("#ffffff", "#000000", None)},
    }),
    "sepia": ("Sepia", {
        "light": {"low": ("#5c4d3c", "#f3e6c8", "#7a4a1e"),
                  "standard": ("#24201c", "#fff4d8", "#6b3d12"),
                  "high": ("#000000", "#fffaeb", "#4a2706")},
        "dark": {"low": ("#c2b29a", "#2e261d", "#d9a066"),
                 "standard": ("#eadbc2", "#211b14", "#e8b47c"),
                 "high": ("#fff6e5", "#0d0a06", "#f7cf9f")},
    }),
    "lenin": ("Lenin red", {
        "light": {"low": ("#5e4440", "#f6e9e2", "#a33a32"),
                  "standard": ("#2a1615", "#fff8f3", "#a4161a"),
                  "high": ("#000000", "#ffffff", "#7a0000")},
        "dark": {"low": ("#d4b8b0", "#2d1514", "#f08a7e"),
                 "standard": ("#f4e4dc", "#1f0a0a", "#ff7a6b"),
                 "high": ("#ffffff", "#0f0000", "#ffa59c")},
    }),
    "slate": ("Slate blue", {
        "light": {"low": ("#4c5666", "#eaeef3", "#345a8a"),
                  "standard": ("#1e2733", "#f8fafc", "#1f4e8c"),
                  "high": ("#000000", "#ffffff", "#0b3a75")},
        "dark": {"low": ("#a8b2c1", "#222934", "#8fb3e6"),
                 "standard": ("#dde4ee", "#141a22", "#8cb8ff"),
                 "high": ("#ffffff", "#000814", "#bcd6ff")},
    }),
    "forest": ("Forest green", {
        "light": {"low": ("#4b5746", "#eaf0e3", "#3f6b2f"),
                  "standard": ("#1f2a1c", "#f9fbf5", "#2f5f22"),
                  "high": ("#000000", "#ffffff", "#1d4512")},
        "dark": {"low": ("#adb9a5", "#212820", "#9cc78a"),
                 "standard": ("#dfe7d8", "#141a12", "#a9d98f"),
                 "high": ("#ffffff", "#000000", "#c6f0b0")},
    }),
}
# Style version 4 combined palette and contrast in one "contrast" choice.
LEGACY_CONTRAST = {
    "theme": ("theme", "standard"), "standard": ("neutral", "standard"),
    "cream": ("sepia", "standard"), "high": ("neutral", "high"),
}


def upgrade_style(value):
    """Read settings saved before palette/mode/contrast were separate without rewriting them."""
    if not isinstance(value, dict) or "palette" in value or "mode" in value:
        return value
    legacy = LEGACY_CONTRAST.get(value.get("contrast"))
    if legacy is None:
        return value
    palette, contrast = legacy
    return {**value, "palette": palette, "mode": "light", "contrast": contrast}


def palette_colors(value, profile):
    """Return (ink, paper, accent); the theme palette follows the site's reading colours."""
    if value["palette"] == "theme":
        return profile.reading_ink, profile.reading_paper, None
    ink, paper, accent = PALETTES[value["palette"]][1][value["mode"]][value["contrast"]]
    return ink, paper, accent


def mix(color, base, amount):
    """Blend `amount` of hex `color` into hex `base` (both #rgb or #rrggbb)."""
    def rgb(value):
        value = value.lstrip("#")
        value = "".join(c * 2 for c in value) if len(value) == 3 else value
        return [int(value[i:i + 2], 16) for i in (0, 2, 4)]
    pairs = zip(rgb(color), rgb(base), strict=True)
    return "#" + "".join(f"{round(a * amount + b * (1 - amount)):02x}" for a, b in pairs)


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
    palette = forms.ChoiceField(
        label="Colour palette",
        choices=[("theme", "Follow site theme (transparent page)")]
        + [(key, label) for key, (label, _modes) in PALETTES.items()],
        help_text="Follow site theme uses the site's colours; light/dark and contrast "
                  "apply to the other palettes.",
    )
    mode = forms.ChoiceField(label="Light or dark", choices=[
        ("light", "Light: dark text on a light page"), ("dark", "Dark: light text on a dark page"),
    ])
    contrast = forms.ChoiceField(label="Contrast", choices=[
        ("low", "Low: softer text"), ("standard", "Standard"),
        ("high", "High: maximum contrast"),
    ])
    italic_to_bold = forms.BooleanField(label="Show italics as bold, not slanted", required=False)
    underline_to_bold = forms.BooleanField(label="Show underlining as bold", required=False,
                                         help_text="Links remain visibly underlined.")
    hyphenation = forms.BooleanField(label="Allow automatic hyphenation", required=False)


def validate_style(value):
    value = upgrade_style(value)
    if not isinstance(value, dict) or set(value) != set(DEFAULTS):
        raise ValueError("Reading style must contain exactly the supported settings.")
    for key in ("italic_to_bold", "underline_to_bold", "hyphenation"):
        if type(value[key]) is not bool:
            raise ValueError("Accessibility switches must be boolean.")
    if any(
        isinstance(value[key], bool)
        for key in ("font_size", "line_height", "letter_spacing", "word_spacing",
                    "paragraph_spacing", "line_width")
    ):
        raise ValueError("Numeric reading style settings must be numbers.")
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


def work_type_choices():
    from library.services.document_metadata import WORK_TYPES

    choices = list(WORK_TYPES)
    if "anthology" not in dict(choices):
        choices.insert(1, ("anthology", "Anthology"))
    return tuple(choices)


def work_type_keys():
    return tuple(key for key, _label in work_type_choices())


def normalize_work_type(value):
    return value if isinstance(value, str) and value in work_type_keys() else "other"


def validate_style_layer(value):
    """Validate a sparse override without losing explicit false, zero or reset state."""
    if not isinstance(value, dict) or set(value) - set(DEFAULTS):
        raise ValueError("A reading style layer contains an unknown setting.")
    if not value:
        return {}
    return {
        key: validate_style({**DEFAULTS, **value})[key]
        for key in value
    }


def style_presentation_token(settings, theme, *, work_type="other", origins=None):
    from library.themes import THEMES

    if theme not in ("", *THEMES):
        raise ValueError("Choose an available theme.")
    kind = normalize_work_type(work_type)
    origins = origins or {}
    if not isinstance(origins, dict) or set(origins) - set(DEFAULTS):
        raise ValueError("Appearance origins are invalid.")
    safe_origins = {}
    for key, origin in origins.items():
        if (
            not isinstance(origin, dict)
            or set(origin) != {"source", "label"}
            or not all(isinstance(value, str) for value in origin.values())
        ):
            raise ValueError("Appearance origins are invalid.")
        safe_origins[key] = dict(origin)
    return signing.dumps({
        "version": 1, "settings": validate_style(settings), "theme": theme,
        "work_type": kind, "origins": safe_origins,
    }, salt=PRESENTATION_SALT, compress=True)


def token_presentation(token):
    if not isinstance(token, str) or len(token) > 8192:
        raise ValueError("Invalid appearance snapshot.")
    try:
        value = signing.loads(token, salt=PRESENTATION_SALT)
    except signing.BadSignature as exc:
        raise ValueError("Appearance snapshot is invalid. Refresh Read and retry.") from exc
    if (
        not isinstance(value, dict)
        or set(value) != {"version", "settings", "theme", "work_type", "origins"}
        or value["version"] != 1
    ):
        raise ValueError("Appearance snapshot is invalid. Refresh Read and retry.")
    from library.themes import THEMES

    if value["theme"] not in ("", *THEMES):
        raise ValueError("Appearance snapshot contains an unavailable theme.")
    if value["work_type"] not in work_type_keys():
        raise ValueError("Appearance snapshot contains an unavailable work type.")
    settings = validate_style(value["settings"])
    origins = value["origins"]
    if not isinstance(origins, dict) or set(origins) - set(settings):
        raise ValueError("Appearance snapshot contains invalid origins.")
    for origin in origins.values():
        if (
            not isinstance(origin, dict)
            or set(origin) != {"source", "label"}
            or not all(isinstance(item, str) for item in origin.values())
        ):
            raise ValueError("Appearance snapshot contains invalid origins.")
    return {
        "settings": settings, "theme": value["theme"], "work_type": value["work_type"],
        "origins": origins,
    }


def resolve_style(work_type="other", *, user=None, rendition=None, guest_overrides=None):
    """Resolve each setting independently and retain the layer that supplied it."""
    kind = normalize_work_type(work_type)
    layers = [
        ("built-in", f"Built-in · {kind.title()}", dict(DEFAULTS)),
        (
            "administrator", f"Administrator · {kind.title()}",
            (ReadingStyleAdminDefault.objects.filter(work_type=kind)
             .values_list("settings", flat=True).first() or {}),
        ),
    ]
    if user is not None and getattr(user, "is_authenticated", False):
        layers.append((
            "account", f"My defaults · {kind.title()}",
            (ReadingStyleAccountDefault.objects.filter(owner=user, work_type=kind)
             .values_list("settings", flat=True).first() or {}),
        ))
    if rendition is not None:
        output = {}
        if user is not None and getattr(user, "is_authenticated", False):
            output = (ReadingStyleOutputOverride.objects.filter(
                owner=user, rendition=rendition,
            ).values_list("settings", flat=True).first() or {})
        elif guest_overrides is not None:
            output = guest_overrides
        layers.append(("output", "This version", validate_style_layer(output)))

    effective = {}
    origins = {}
    layer_values = {}
    for source, label, values in layers:
        validated = dict(values) if source == "built-in" else validate_style_layer(values)
        layer_values[source] = validated
        for key, value in validated.items():
            effective[key] = value
            origins[key] = {"source": source, "label": label}
    complete = validate_style(effective)
    return {
        "settings": complete, "origins": origins, "work_type": kind,
        "layers": layer_values,
        "output_id": rendition.identity if rendition is not None else None,
        "rendition_id": rendition.pk if rendition is not None else None,
    }


def rendition_work_type(rendition):
    metadata = getattr(rendition, "metadata", None)
    return normalize_work_type(metadata.get("work_type") if isinstance(metadata, dict) else None)


def apply_layer_changes(current, changes, reset=()):
    values = validate_style_layer(current)
    patch = validate_style_layer(changes)
    if not isinstance(reset, (tuple, list)) or any(
        not isinstance(key, str) or key not in DEFAULTS for key in reset
    ):
        raise ValueError("Choose supported reading style settings to reset.")
    values.update(patch)
    for key in reset:
        values.pop(key, None)
    return values


def stylesheet_url(token, theme=""):
    from urllib.parse import urlencode

    return reverse("reading-style-css") + "?" + urlencode({
        "style": token, "theme": theme, "v": STYLE_VERSION,
    })


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


def selected_style(request, rendition=None, *, work_type=None, guest_overrides=None):
    presentation = request.GET.get("presentation")
    if presentation:
        return token_presentation(presentation)["settings"]
    token = request.GET.get("style")
    if token:
        return token_style(token)
    kind = work_type or rendition_work_type(rendition)
    return resolve_style(
        kind, user=request.user, rendition=rendition, guest_overrides=guest_overrides,
    )["settings"]


def selected_theme(request):
    presentation = request.GET.get("presentation")
    if presentation:
        return token_presentation(presentation)["theme"]
    from library.themes import selected_theme as current_theme

    return current_theme(request)


def style_context(
    request, rendition=None, *, work_type=None, guest_overrides=None, include_profiles=False,
):
    from library.themes import selected_theme

    kind = work_type or rendition_work_type(rendition)
    resolved = resolve_style(
        kind, user=request.user, rendition=rendition, guest_overrides=guest_overrides,
    )
    theme = selected_theme(request)
    if request.GET.get("style"):
        token_style(request.GET["style"])
    presentation = request.GET.get("presentation")
    if presentation:
        snapshot = token_presentation(presentation)
        if snapshot["work_type"] == resolved["work_type"]:
            resolved["settings"] = snapshot["settings"]
            theme = snapshot["theme"]
            resolved["origins"] = snapshot["origins"]
    settings = resolved["settings"]
    token = style_token(settings)
    profiles = list(ReadingStyleProfile.objects.filter(owner=request.user)) \
        if include_profiles and request.user.is_authenticated else []
    default = next((str(profile.pk) for profile in profiles if profile.is_default), "")
    form = ReadingStyleForm(initial=settings)
    return {
        "reading_style": settings, "reading_style_token": token,
        "reading_presentation_token": style_presentation_token(
            settings, theme, work_type=resolved["work_type"], origins=resolved["origins"],
        ),
        "reading_theme": theme,
        "reading_style_url": stylesheet_url(token, theme),
        "reading_style_form": form,
        "reading_style_profiles": profiles, "reading_style_profile": "",
        "reading_default_profile": default,
        "reading_preset_name": PRESET_NAME,
        "reading_style_version": STYLE_VERSION,
        "reading_style_origins": resolved["origins"],
        "reading_style_layers": resolved["layers"],
        "reading_style_origin_labels": {
            key: value["label"] for key, value in resolved["origins"].items()
        },
        "reading_style_output_override_keys": list(
            resolved["layers"].get("output", {}),
        ),
        "reading_style_account_override_keys": list(
            resolved["layers"].get("account", {}),
        ),
        "reading_style_work_type": resolved["work_type"],
        "reading_style_output_id": resolved["output_id"],
        "reading_style_rendition_id": rendition.pk if rendition is not None else "",
        "reading_style_authenticated": request.user.is_authenticated,
        "reading_style_account_settings": rendition is None,
        "reading_style_groups": [
            ("Typography", [form[key] for key in (
                "font_mode", "font_size", "paragraph_align", "title_align",
            )]),
            ("Fonts by purpose", [form[key] for key in (
                "body_font", "title_font", "metadata_font", "contents_font", "code_font",
            )]),
            ("Spacing & page", [form[key] for key in (
                "line_height", "paragraph_spacing", "letter_spacing", "word_spacing",
                "line_width",
            )]),
            ("Colours", [form[key] for key in ("palette", "mode", "contrast")]),
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


def style_css(settings, font_base="/static/library/fonts/", profile=None):
    from library.profile import get_profile

    value = validate_style(settings)
    def family(concern):
        return FONTS[
            value[f"{concern}_font"] if value["font_mode"] == "mixed" else value["font_mode"]
        ][0]
    profile = get_profile() if profile is None else profile
    theme = value["palette"] == "theme"
    ink, paper, accent = palette_colors(value, profile)
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
{scope} :is(.document-header,.document-contents,.reader-content,.document-metadata-page) {{
  max-width: {value['line_width']}ch; margin-inline: auto; box-sizing: border-box;
}}
{scope} :is(.reader-content,.document-metadata-page) {{
  font: inherit; color: inherit; hyphens: {'auto' if value['hyphenation'] else 'none'}; }}
{text} p {{
  text-align: {value['paragraph_align']}; margin-block-end: {value['paragraph_spacing']}em;
}}
{titles} {{
  font-family: {family('title')}; text-align: {value['title_align']};
  line-height: 1.3; letter-spacing: inherit; color: inherit;
}}
{scope} h1 {{ font-size: 2em; }}
{scope} h2 {{ font-size: 1.6em; }}
{scope} :is(.document-contents > h2,.reader-content h2,.document-metadata-page > h2) {{
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
{scope} .document-contents {{ font-family: {family('body')}; }}
{scope} .document-contents :is(ul,ol) {{ font-family: {family('contents')}; }}
{scope} .reader-content :is(.text-align-left) {{ text-align: left; }}
{scope} .reader-content :is(.text-align-right) {{ text-align: right; }}
{scope} .reader-content :is(.text-align-center) {{ text-align: center; }}
{scope} .reader-content :is(.text-align-justify) {{ text-align: justify; }}
{scope} {{ color-scheme: {'normal' if theme else value['mode']}; }}
{scope} .reader-content a > :is(sup,sub) {{
  display: inline-block; text-decoration: inherit;
}}
@media print {{
  html, body {{ background: {paper} !important; }}
  {scope} {{ color: {ink}; }}
  @page {{
    background: {paper}; color: {ink};
  }}
  {scope} :is(.document-contents a,.print-toc a,.reader-content figcaption) {{ color: inherit; }}
  {scope} .document-metadata-table :is(th,td) {{ border-bottom-color: currentColor; }}
  @page reading-content {{
    @top-left {{ font-family: {family('metadata')}; }}
    @top-right {{ font-family: {family('metadata')}; }}
    @bottom-center {{ font-family: {family('metadata')}; }}
  }}
}}
"""
    if not theme:
        # The site theme loads after this sheet, so palette rules out-rank its selectors.
        link = accent or ink
        blocks = (f"{scope} :is(.document-header,.document-contents,.reader-content,"
                  ".document-metadata-page,.notice)")
        css += f"""
{scope} .eyebrow {{ color: {link}; }}
{blocks} a[href], {blocks} a[href]:hover {{ color: {link}; text-decoration-color: currentColor; }}
{scope} .document-contents a[href], {scope} .document-contents a[href]:hover {{ color: inherit; }}
{scope} .document-contents a[href]:hover {{ text-decoration-color: {link}; }}
{scope} .notice {{
  color: inherit; background: {mix(link, paper, .08)}; border-color: {mix(link, paper, .45)};
}}
{scope} .reader-content :is(blockquote,figcaption,.media-credit) {{ color: inherit; }}
{scope} :is(.reader-content,.document-metadata-page) :is(blockquote,th,td,hr) {{
  border-color: {mix(ink, paper, .3)};
}}
"""
    if accent:
        css += f"""
{titles} {{ color: {accent}; }}
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
