"""Tests use PostgreSQL, with only cache and transport replaced."""

import os
import secrets

os.environ.setdefault("DJANGO_SECRET_KEY", secrets.token_urlsafe(48))
os.environ.setdefault("DJANGO_DEBUG", "true")

from .settings import *  # noqa: E402,F403

ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
if os.environ.get("USE_SQLITE_TESTS") == "1" or os.environ.get("DATABASE_URL", "").startswith("sqlite"):
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
else:
    DATABASES["default"]["CONN_MAX_AGE"] = 0  # noqa: F405
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
SECURE_SSL_REDIRECT = False
