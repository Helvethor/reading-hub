from dataclasses import replace

from profiles.marxist.site import PROFILE as BASE

PROFILE = replace(
    BASE,
    theme_css="marxist/dark.css",
    admin_theme_css="marxist/dark-admin.css",
    reading_paper="#181818",
    reading_ink="#e6e6e6",
)
