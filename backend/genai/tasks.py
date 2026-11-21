"""Celery tasks for GenAI (run inline in dev without Redis)."""

from celery import shared_task

from . import rag


@shared_task(name="genai.index_source")
def index_source(source_type: str, source_id: int) -> int:
    return rag.index_source(source_type, source_id)


@shared_task(name="genai.reindex_all", time_limit=3600)
def reindex_all() -> dict[str, int]:
    return rag.reindex_all()
