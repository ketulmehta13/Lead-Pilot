"""Agent runs execute in Celery (inline in dev without Redis)."""

from celery import shared_task

from . import agent


@shared_task(name="agent.advance", time_limit=900, soft_time_limit=840)
def advance(run_id: int) -> str:
    return agent.advance(run_id).status
