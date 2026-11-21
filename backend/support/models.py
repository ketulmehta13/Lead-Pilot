"""Support tickets. Sentiment and priority are filled automatically (see support/signals.py)."""

from django.conf import settings
from django.db import models

from common.models import OwnedModel, TimeStampedModel
from crm.models import Contact


class Ticket(OwnedModel):
    """A customer support request. `owner` is the person who logged it."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    class Sentiment(models.TextChoices):
        POSITIVE = "positive", "Positive"
        NEUTRAL = "neutral", "Neutral"
        NEGATIVE = "negative", "Negative"

    subject = models.CharField(max_length=200)
    description = models.TextField()
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="tickets")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    priority = models.CharField(max_length=6, choices=Priority.choices, default=Priority.MEDIUM)
    # True once a person sets the priority by hand; the model then stops overriding it.
    priority_overridden = models.BooleanField(default=False)
    sentiment = models.CharField(  # noqa: DJ001 - null = not classified (model missing)
        max_length=8, choices=Sentiment.choices, null=True, blank=True
    )
    # -1 (very negative) .. +1 (very positive)
    sentiment_score = models.FloatField(null=True, blank=True)
    urgent = models.BooleanField(default=False, help_text="Urgent keywords found in the text")
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tickets",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "priority"])]

    def __str__(self) -> str:
        return self.subject


class TicketComment(TimeStampedModel):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    body = models.TextField()

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Comment on {self.ticket_id}"
