"""Test settings: fast and isolated. Uses DATABASE_URL (Postgres in CI) or in-memory SQLite."""
import os

from .base import *  # noqa: F401,F403

DEBUG = False
SECRET_KEY = "test-only-key"
if not os.environ.get("DATABASE_URL"):
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"
