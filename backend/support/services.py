"""Ticket business logic."""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from accounts.models import User

from .models import Ticket, TicketComment


def apply_classification(ticket: Ticket) -> None:
    """Fill sentiment, score, urgency and (unless a person overrode it) priority from the text.

    If the sentiment model file is missing, the fields stay empty and priority keeps its
    current value: tickets are never blocked by ML.
    """
    from ml import services as ml  # local import: ml imports support for features

    result = ml.classify_ticket_text(f"{ticket.subject}. {ticket.description}")
    if result is None:
        return
    ticket.sentiment = result["sentiment"]
    ticket.sentiment_score = result["score"]
    ticket.urgent = result["urgent"]
    if not ticket.priority_overridden:
        ticket.priority = result["priority"]


def create_ticket(*, owner: User, **data: Any) -> Ticket:
    """Create a ticket; a priority given explicitly counts as a manual override."""
    manual_priority = "priority" in data
    ticket = Ticket(owner=owner, priority_overridden=manual_priority, **data)
    ticket.save()  # the pre_save signal classifies it
    return ticket


def update_ticket(ticket: Ticket, **data: Any) -> Ticket:
    """Edit a ticket. Setting priority by hand pins it; status changes stamp resolved_at."""
    if "priority" in data and data["priority"] != ticket.priority:
        ticket.priority_overridden = True
    new_status = data.get("status", ticket.status)
    done = (Ticket.Status.RESOLVED, Ticket.Status.CLOSED)
    if new_status in done and ticket.status not in done:
        ticket.resolved_at = timezone.now()
    elif new_status not in done:
        ticket.resolved_at = None
    for field, value in data.items():
        setattr(ticket, field, value)
    ticket.save()
    return ticket


def add_comment(ticket: Ticket, *, author: User, body: str) -> TicketComment:
    return TicketComment.objects.create(ticket=ticket, author=author, body=body)
