import os
from pathlib import Path
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

if os.environ.get("READING_HUB_ENVIRONMENT") not in (None, "production"):
    raise ImproperlyConfigured("Production settings require READING_HUB_ENVIRONMENT=production.")
if not os.environ.get("READING_HUB_DATA"):
    raise ImproperlyConfigured("Production settings require an explicit READING_HUB_DATA.")

os.environ["READING_HUB_ENVIRONMENT"] = "production"

from config.settings import *  # noqa: E402, F403, F405
from config.settings import DATA_DIR as BASE_DATA_DIR  # noqa: E402
from config.settings import MIDDLEWARE as BASE_MIDDLEWARE  # noqa: E402

DEBUG = False
ALLOWED_HOSTS = ["read.shabang.ch"]
CSRF_TRUSTED_ORIGINS = ["https://read.shabang.ch"]
if os.environ.get("READING_HUB_LOCAL_SIMULATION") == "1":
    simulation_origin = os.environ.get("READING_HUB_LOCAL_SIMULATION_ORIGIN", "")
    try:
        parsed_origin = urlsplit(simulation_origin)
        simulation_port = parsed_origin.port
    except ValueError as exc:
        message = "The local simulation origin must be a localhost HTTPS origin."
        raise ImproperlyConfigured(message) from exc
    if (
        parsed_origin.scheme != "https"
        or parsed_origin.hostname != "localhost"
        or simulation_port is None
        or parsed_origin.netloc != f"localhost:{simulation_port}"
        or parsed_origin.path
        or parsed_origin.query
        or parsed_origin.fragment
    ):
        raise ImproperlyConfigured("The local simulation origin must be a localhost HTTPS origin.")
    CSRF_TRUSTED_ORIGINS.append(simulation_origin)
elif os.environ.get("READING_HUB_LOCAL_SIMULATION_ORIGIN"):
    raise ImproperlyConfigured("A local simulation origin requires READING_HUB_LOCAL_SIMULATION=1.")
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 86400
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
READING_HUB_ALLOW_SIGNUP = False
STATIC_ROOT = Path(os.environ.get("READING_HUB_STATIC_ROOT", BASE_DATA_DIR / "static"))
MIDDLEWARE = list(BASE_MIDDLEWARE)
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
MIDDLEWARE.append("django.middleware.clickjacking.XFrameOptionsMiddleware")
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
