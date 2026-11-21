"""Keep the RAG index in sync with activities, tickets and lead notes."""

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from crm.models import Activity, Lead
from support.models import Ticket, TicketComment

from . import rag, tasks
from .models import DocumentChunk

SOURCES = {
    Activity: DocumentChunk.Source.ACTIVITY,
    Ticket: DocumentChunk.Source.TICKET,
    Lead: DocumentChunk.Source.LEAD,
}
# Saves that only touch these fields don't change the indexed text.
IGNORED_FIELDS = {"score", "score_label", "score_explanation", "updated_at", "last_contacted_at",
                  "priority", "sentiment", "sentiment_score", "urgent"}  # fmt: skip


def _queue(source_type: str, source_id: int) -> None:
    transaction.on_commit(lambda: tasks.index_source.delay(source_type, source_id))


@receiver(post_save, sender=Activity)
@receiver(post_save, sender=Ticket)
@receiver(post_save, sender=Lead)
def reindex_on_save(sender, instance, update_fields=None, **kwargs) -> None:
    if update_fields is not None and set(update_fields) <= IGNORED_FIELDS:
        return
    _queue(SOURCES[sender], instance.pk)


@receiver(post_save, sender=TicketComment)
def reindex_ticket_on_comment(sender, instance: TicketComment, created: bool, **kwargs) -> None:
    if created:
        _queue(DocumentChunk.Source.TICKET, instance.ticket_id)


@receiver(post_delete, sender=Activity)
@receiver(post_delete, sender=Ticket)
@receiver(post_delete, sender=Lead)
def drop_on_delete(sender, instance, **kwargs) -> None:
    rag.delete_source(SOURCES[sender], instance.pk)
