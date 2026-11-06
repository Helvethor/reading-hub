from dataclasses import replace

from django import forms
from django.templatetags.static import static

from library import profile as site_profiles
from library.models import UserSettings

COOKIE = "reading_hub_theme"
THEMES = {
    "paper": ("Marxist Paper", "marxist/theme.css", "marxist/admin.css", "#faf5ef", "#302221"),
    "dark": ("Marxist Dark", "marxist/dark.css", "marxist/dark-admin.css", "#181818", "#e6e6e6"),
}


def theme_choices():
    profile = site_profiles.get_profile()
    choices = [("", "Site default")]
    if profile.key == "marxist":
        choices.extend((key, value[0]) for key, value in THEMES.items())
    return choices


class ThemeForm(forms.Form):
    theme = forms.ChoiceField(label="Theme", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["theme"].choices = theme_choices()


def selected_theme(request):
    if hasattr(request, "reading_hub_theme"):
        return request.reading_hub_theme
    choice = request.COOKIES.get(COOKIE, "")
    if request.user.is_authenticated:
        saved = (
            UserSettings.objects.filter(user=request.user).values_list("theme", flat=True).first()
        )
        if saved is not None:
            choice = saved
    request.reading_hub_theme = choice if choice in dict(theme_choices()) else ""
    return request.reading_hub_theme


def themed_profile(request):
    return profile_for_theme(selected_theme(request))


def profile_for_theme(choice):
    profile = site_profiles.get_profile()
    if not choice:
        return profile
    if choice not in dict(theme_choices()):
        raise ValueError("Choose an available theme.")
    _, css, admin_css, paper, ink = THEMES[choice]
    return replace(profile, theme_css=css, admin_theme_css=admin_css,
                   reading_paper=paper, reading_ink=ink)


def theme_payload(request):
    profile = themed_profile(request)
    return {
        "theme": selected_theme(request),
        "stylesheet": static(profile.theme_css),
    }
