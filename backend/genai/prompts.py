"""Prompt files live in genai/prompts/*.txt and use $placeholders (string.Template)."""

from __future__ import annotations

from functools import cache
from pathlib import Path
from string import Template

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


@cache
def _load(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.txt").read_text(encoding="utf-8").strip()


def render(name: str, **values: object) -> str:
    """Fill a prompt template. `$guard` is always available. Missing keys raise KeyError."""
    values.setdefault("guard", _load("guard"))
    return Template(_load(name)).substitute({k: str(v) for k, v in values.items()})


def fence(text: str) -> str:
    """Neutralize anything in untrusted data that could close our <crm_data> fence."""
    return text.replace("</crm_data>", "</crm-data>").replace("<crm_data>", "<crm-data>")
