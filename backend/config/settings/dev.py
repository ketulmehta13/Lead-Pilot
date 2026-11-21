"""Development settings."""

import os

from .dotenv import load_dotenv

# Must run before base is imported: base reads env vars at import time.
load_dotenv()

from .base import *  # noqa: E402,F401,F403
from .base import env_bool  # noqa: E402

DEBUG = env_bool("DJANGO_DEBUG", True)
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or "dev-only-insecure-key-change-me"
ALLOWED_HOSTS = ["*"]

# Use Redis for caching when it's available (Docker); otherwise Django's in-memory cache.
if os.environ.get("REDIS_URL"):
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": os.environ["REDIS_URL"],
        }
    }
else:
    # No Redis (running without Docker): execute Celery tasks inline so ML scoring etc. still
    # happens instead of hanging on an unreachable broker.
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = False
    CELERY_BROKER_URL = "memory://"
    CELERY_RESULT_BACKEND = "cache+memory://"
