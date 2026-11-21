"""End-to-end test settings (Playwright): a real server with deterministic, offline AI.

- Separate SQLite file (e2e.sqlite3), rebuilt by `seed_demo --flush` before each run.
- Celery tasks run inline; LLM = offline mock (no keys, deterministic); hash embeddings.
- A test-only Razorpay webhook secret so the suite can send signed webhooks.
"""

import os

os.environ["LLM_PROVIDER"] = "mock"
os.environ["EMBEDDINGS_BACKEND"] = "hash"
os.environ.setdefault("RAZORPAY_WEBHOOK_SECRET", "e2e_webhook_secret")
os.environ.setdefault("LOGIN_RATE_LIMIT", "1000/min")
os.environ.setdefault("GENAI_RATE_LIMIT", "1000/min")

from .base import *  # noqa: E402,F401,F403
from .base import BASE_DIR, REST_FRAMEWORK  # noqa: E402

DEBUG = True
SECRET_KEY = "e2e-only-not-secret-key-long-enough-for-hs256"
ALLOWED_HOSTS = ["*"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "e2e.sqlite3"}}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = False
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_RATES": {"genai": "1000/min", "login": "1000/min"},
}
