"""Keep the dashboard cache honest: any CRM change invalidates cached summaries."""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from crm.models import Deal, Lead, Task

from .services import invalidate_summary_cache


@receiver([post_save, post_delete], sender=Lead)
@receiver([post_save, post_delete], sender=Deal)
@receiver([post_save, post_delete], sender=Task)
def _crm_changed(sender, **kwargs) -> None:
    invalidate_summary_cache()
