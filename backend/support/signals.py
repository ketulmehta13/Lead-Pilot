"""Classify tickets automatically (sentiment -> priority) whenever their text changes."""

from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import Ticket
from .services import apply_classification


@receiver(pre_save, sender=Ticket)
def classify_ticket(sender, instance: Ticket, **kwargs) -> None:
    if instance.pk is None:
        apply_classification(instance)
        return
    previous = Ticket.objects.filter(pk=instance.pk).values("subject", "description").first()
    if previous and (
        previous["subject"] != instance.subject or previous["description"] != instance.description
    ):
        apply_classification(instance)
