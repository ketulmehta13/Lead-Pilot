"""Celery tasks for ML. In local dev without Redis they run inline (CELERY_TASK_ALWAYS_EAGER)."""

from __future__ import annotations

from typing import Any

from celery import shared_task

from crm.models import Lead

from . import services


@shared_task(name="ml.score_lead")
def score_lead(lead_id: int) -> int | None:
    lead = Lead.objects.filter(pk=lead_id).only("id", "contact_id", "source").first()
    if lead is None:
        return None
    scored = services.score_lead(lead)
    return scored.score if scored else None


@shared_task(name="ml.score_contact_leads")
def score_contact_leads(contact_id: int) -> int:
    """A new activity changes engagement features for every lead of that contact."""
    return services.score_leads(Lead.objects.filter(contact_id=contact_id))


@shared_task(name="ml.rescore_all")
def rescore_all() -> int:
    return services.rescore_all()


@shared_task(name="ml.refresh_customer_insights")
def refresh_customer_insights() -> dict[str, int]:
    return services.refresh_customer_insights()


@shared_task(name="ml.retrain", time_limit=1800, soft_time_limit=1700)
def retrain(models: list[str] | None = None) -> dict[str, Any]:
    return services.retrain(models)
