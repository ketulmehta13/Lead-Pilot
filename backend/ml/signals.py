"""Keep ML outputs fresh as CRM data changes.

Tasks are queued with transaction.on_commit so workers never read uncommitted rows.
Scores are written with bulk_update/update(), which sends no signals, so there is no loop.
"""

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from crm.models import Activity, Deal, Lead

from . import tasks

SCORE_FIELDS = {"score", "score_label", "score_explanation"}


@receiver(post_save, sender=Lead)
def rescore_lead_on_change(sender, instance: Lead, update_fields=None, **kwargs) -> None:
    if update_fields is not None and set(update_fields) <= SCORE_FIELDS | {"updated_at"}:
        return
    lead_id = instance.pk
    transaction.on_commit(lambda: tasks.score_lead.delay(lead_id))


@receiver(post_save, sender=Activity)
def rescore_contact_on_activity(sender, instance: Activity, created: bool, **kwargs) -> None:
    if created:
        contact_id = instance.contact_id
        transaction.on_commit(lambda: tasks.score_contact_leads.delay(contact_id))


@receiver(pre_save, sender=Deal)
def remember_deal_stage(sender, instance: Deal, **kwargs) -> None:
    instance._previous_stage = (
        Deal.objects.filter(pk=instance.pk).values_list("stage", flat=True).first()
        if instance.pk
        else None
    )


@receiver(post_save, sender=Deal)
def refresh_insights_on_close(sender, instance: Deal, **kwargs) -> None:
    """Entering or leaving Won/Lost changes RFM and churn features for the customer base."""
    before = getattr(instance, "_previous_stage", None)
    if before == instance.stage:
        return
    if before in Deal.CLOSED_STAGES or instance.stage in Deal.CLOSED_STAGES:
        transaction.on_commit(tasks.refresh_customer_insights.delay)
