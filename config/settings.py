import hashlib
import os
import secrets
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from config.environments import validate_environment

BASE_DIR = Path(__file__).resolve().parent.parent
READING_HUB_ENVIRONMENT = os.environ.get("READING_HUB_ENVIRONMENT", "live")
if READING_HUB_ENVIRONMENT != "live" and not os.environ.get("READING_HUB_DATA"):
    raise ImproperlyConfigured("Non-live environments require an explicit READING_HUB_DATA.")
try:
    DATA_DIR, DATABASE_PATH = validate_environment(
        READING_HUB_ENVIRONMENT,
        BASE_DIR,
        os.environ.get("READING_HUB_DATA", BASE_DIR / "data"),
        os.environ.get(
            "READING_HUB_DATABASE_PATH",
            Path(os.environ.get("READING_HUB_DATA", BASE_DIR / "data")) / "library.sqlite3",
        ),
    )
except (ValueError, OSError) as exc:
    raise ImproperlyConfigured(str(exc)) from exc
READING_HUB_REVISION = os.environ.get("READING_HUB_REVISION", "unmanaged")
READING_HUB_INSTANCE = os.environ.get("READING_HUB_INSTANCE", "")
READING_HUB_ALLOW_WORKERS = (
    READING_HUB_ENVIRONMENT == "live"
    or (
        READING_HUB_ENVIRONMENT in {"development", "staging", "production"}
        and os.environ.get("READING_HUB_ALLOW_WORKERS") != "0"
    )
    or (READING_HUB_ENVIRONMENT == "test" and os.environ.get("READING_HUB_ALLOW_WORKERS") == "1")
)
READING_HUB_AUTO_WORKERS = (
    READING_HUB_ENVIRONMENT in {"development", "staging", "production"}
    and READING_HUB_ALLOW_WORKERS
)
DATA_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
secret_path = DATA_DIR / "secret-key"
try:
    with secret_path.open("x", encoding="ascii") as secret_file:
        secret_file.write(secrets.token_urlsafe(48))
    secret_path.chmod(0o600)
except FileExistsError:
    pass
SECRET_KEY = secret_path.read_text(encoding="ascii").strip()
DEBUG = READING_HUB_ENVIRONMENT == "development"
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]
READING_HUB_ALLOW_SIGNUP = True
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "library",
    "django.contrib.staticfiles",
]
READING_HUB_PROFILE = os.environ.get("READING_HUB_PROFILE", "profiles.marxist.site")
READING_HUB_EDITOR_PILOT = os.environ.get("READING_HUB_EDITOR_PILOT", "1") == "1"
STATICFILES_DIRS = [BASE_DIR / "profiles" / "static"]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "library.middleware.ReaderPolicyMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "library" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "library.profile.site_context",
            ]
        },
    }
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATABASE_PATH,
        "OPTIONS": {"timeout": 20, "transaction_mode": "IMMEDIATE"},
    }
}
if READING_HUB_ENVIRONMENT == "test" and os.environ.get("READING_HUB_TEST_DATABASE_FILE") == "1":
    DATABASES["default"]["TEST"] = {"NAME": DATA_DIR / "worker-test.sqlite3"}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LANGUAGE_CODE = "en"
TIME_ZONE = "UTC"
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = DATA_DIR / "static"
SECURE_CONTENT_TYPE_NOSNIFF = True
CSRF_COOKIE_HTTPONLY = True
CSRF_FAILURE_VIEW = "library.views.csrf_failure"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
READING_HUB_THEME_COOKIE_NAME = "reading_hub_theme"
if READING_HUB_ENVIRONMENT != "live":
    cookie_suffix = hashlib.sha256(str(DATA_DIR).encode()).hexdigest()[:16]
    SESSION_COOKIE_NAME = f"reading_hub_{cookie_suffix}_session"
    CSRF_COOKIE_NAME = f"reading_hub_{cookie_suffix}_csrf"
    READING_HUB_THEME_COOKIE_NAME = f"reading_hub_{cookie_suffix}_theme"
    MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
X_FRAME_OPTIONS = "DENY"
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        "library": {"handlers": ["console"], "level": "INFO"},
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
    },
}
