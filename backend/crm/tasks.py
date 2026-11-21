"""Celery tasks for the CRM app."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import Task

logger = logging.getLogger(__name__)


@shared_task(name="crm.send_overdue_task_reminders")
def send_overdue_task_reminders() -> dict[str, int]:
    """Email each assignee a list of their overdue, unfinished tasks (scheduled daily).

    A task is reminded at most once per ~day (`reminded_at`), so a re-run is harmless.
    """
    now = timezone.now()
    today = timezone.localdate()
    tasks = (
        Task.objects.exclude(status=Task.Status.DONE)
        .filter(due_date__lt=today, assigned_to__isnull=False, assigned_to__is_active=True)
        .exclude(reminded_at__gt=now - timedelta(hours=20))
        .select_related("assigned_to", "contact")
        .order_by("due_date")
    )
    by_user: dict[int, list[Task]] = defaultdict(list)
    for task in tasks:
        by_user[task.assigned_to_id].append(task)

    emails = 0
    for user_tasks in by_user.values():
        user = user_tasks[0].assigned_to
        lines = [
            f"- {t.title} (due {t.due_date:%d %b}"
            + (f", {t.contact.full_name}" if t.contact else "")
            + ")"
            for t in user_tasks
        ]
        if user.email:
            send_mail(
                subject=f"LeadPilot: {len(user_tasks)} overdue task(s)",
                message=(
                    f"Hi {user.first_name or user.username},\n\n"
                    "These tasks are past their due date:\n\n" + "\n".join(lines) + "\n\n"
                    f"Open your tasks: {settings.FRONTEND_URL}/tasks\n"
                ),
                from_email=None,
                recipient_list=[user.email],
            )
            emails += 1
        Task.objects.filter(pk__in=[t.pk for t in user_tasks]).update(reminded_at=now)

    total = sum(len(v) for v in by_user.values())
    logger.info("Overdue reminders: %s tasks, %s emails", total, emails)
    return {"tasks": total, "emails": emails}
