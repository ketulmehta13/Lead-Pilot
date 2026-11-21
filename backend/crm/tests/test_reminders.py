from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone

from config.celery import app
from crm.models import Task
from crm.tasks import send_overdue_task_reminders

pytestmark = pytest.mark.django_db


def test_reminder_emails_each_assignee_once(rep, other_rep, contact_of):
    today = timezone.localdate()
    contact = contact_of(rep, first_name="Meera", last_name="Shah")
    Task.objects.create(owner=rep, assigned_to=rep, title="Call back", contact=contact,
                        due_date=today - timedelta(days=2))  # fmt: skip
    Task.objects.create(
        owner=rep, assigned_to=rep, title="Send quote", due_date=today - timedelta(1)
    )
    Task.objects.create(owner=rep, assigned_to=rep, title="Due today", due_date=today)
    Task.objects.create(owner=rep, assigned_to=rep, title="Finished",
                        due_date=today - timedelta(5), status=Task.Status.DONE)  # fmt: skip
    Task.objects.create(owner=other_rep, assigned_to=other_rep, title="Theirs",
                        due_date=today - timedelta(1))  # fmt: skip

    result = send_overdue_task_reminders()

    assert result == {"tasks": 3, "emails": 2}
    assert sorted(m.to[0] for m in mail.outbox) == ["rep1@test.io", "rep2@test.io"]
    rep_mail = next(m for m in mail.outbox if m.to == ["rep1@test.io"])
    assert "2 overdue task(s)" in rep_mail.subject
    assert "Call back" in rep_mail.body and "Meera Shah" in rep_mail.body
    assert "Due today" not in rep_mail.body and "Finished" not in rep_mail.body


def test_running_twice_does_not_resend(rep):
    Task.objects.create(owner=rep, assigned_to=rep, title="Late",
                        due_date=timezone.localdate() - timedelta(1))  # fmt: skip
    send_overdue_task_reminders()
    assert send_overdue_task_reminders() == {"tasks": 0, "emails": 0}
    assert len(mail.outbox) == 1


def test_reminder_job_is_scheduled_daily():
    schedule = app.conf.beat_schedule["overdue-task-reminders"]
    assert schedule["task"] == "crm.send_overdue_task_reminders"
    assert schedule["schedule"].hour == {8}
