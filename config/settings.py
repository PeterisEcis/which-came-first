"""Django settings for the game service.

Everything that differs between a laptop and production comes from the
environment, with `.env` filling in for local runs (see `.env.example`):

    DJANGO_DEBUG          "1" locally; unset in production
    DJANGO_SECRET_KEY     required unless DJANGO_DEBUG is on
    DJANGO_ALLOWED_HOSTS  comma-separated; localhost when debugging
    DATABASE_URL          defaults to the docker compose database

Real environment variables win over `.env`, so a value set in CI or on the host
is never overridden by a stray file.
"""

from __future__ import annotations

import os
from pathlib import Path

import dj_database_url
import django_stubs_ext
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

# Lets classes such as ModelAdmin take type parameters at runtime, as the type
# stubs expect.
django_stubs_ext.monkeypatch()

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

LOCAL_DATABASE_URL = "postgres://wcf:wcf@127.0.0.1:5432/wcf"
"""The database `docker compose up -d` starts. See compose.yaml.

127.0.0.1 rather than localhost: localhost tries IPv6 first, where compose isn't
listening, and on some machines that attempt hangs until the connect timeout
instead of failing at once."""


# --- Environment-dependent -----------------------------------------------------

DEBUG = os.environ.get("DJANGO_DEBUG", "") == "1"

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY must be set unless DJANGO_DEBUG=1. "
            "For local runs, copy .env.example to .env."
        )
    SECRET_KEY = "insecure-key-for-local-development-only"

ALLOWED_HOSTS = [
    host.strip() for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if host.strip()
]
if DEBUG and not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]

DATABASES = {
    "default": dj_database_url.parse(
        os.environ.get("DATABASE_URL", LOCAL_DATABASE_URL),
        conn_max_age=60,
        conn_health_checks=True,
    )
}
# Postgres's client waits forever for a server that never answers. Fail in
# seconds instead -- long enough for a hosted database waking from sleep.
DATABASES["default"].setdefault("OPTIONS", {}).setdefault("connect_timeout", 10)

# Cookies travel over HTTPS only, once off a laptop.
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG


# --- Application ---------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "game",
]

MIDDLEWARE = [
    # First, so probes are answered before the host check and the player cookie.
    "config.health.HealthCheckMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "game.players.PlayerCookieMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
USE_I18N = True

# The game's day is the UTC day: one live puzzle worldwide, rolling over at
# 00:00 UTC (todo.md, Open decisions: what "today" means).
TIME_ZONE = "UTC"
USE_TZ = True

STATIC_URL = "static/"
# Filled by `collectstatic`, which the image build runs (see Dockerfile).
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # File names carry a hash of their contents, so browsers can cache them for
    # good and a deploy never pairs a new page with an old puzzle.js.
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(levelname)-7s %(name)s: %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "loggers": {
        "puzzle_generator": {"handlers": ["console"], "level": "INFO"},
        "game": {"handlers": ["console"], "level": "INFO"},
        "config": {"handlers": ["console"], "level": "INFO"},
    },
}
