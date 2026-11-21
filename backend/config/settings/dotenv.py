"""Minimal .env loader for running without Docker (Docker passes .env via env_file).

Real environment variables always win; blank lines and # comments are skipped;
surrounding quotes are stripped. Values are never logged.
"""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def load_dotenv(path: Path = PROJECT_ROOT / ".env") -> None:
    """Copy KEY=VALUE pairs from ``path`` into os.environ unless already set."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key, value)
