"""GenAI features: AI writer (follow-up emails) and activity summarizer."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any, Literal, TypeVar

from django.db import transaction
from django.utils import timezone
from pydantic import BaseModel, Field, ValidationError

from accounts.models import User
from crm.models import Activity, Contact, Deal, Lead, Task

from . import llm
from .prompts import fence, render

T = TypeVar("T", bound=BaseModel)

HISTORY_ACTIVITIES = 10
BODY_CHARS = 600


class LLMOutputError(Exception):
    """The model's reply wasn't valid JSON for the schema, even after one retry."""


# --- Structured output ----------------------------------------------------------------------


def structured_chat(
    messages: list[dict[str, Any]], schema: type[T], *, purpose: str, user: User | None
) -> T:
    """Ask for JSON matching `schema`, validate with Pydantic, retry once on bad output."""
    json_schema = schema.model_json_schema()
    attempt_messages = list(messages)
    last_error = ""
    for attempt in range(2):
        response = llm.chat(attempt_messages, json_schema=json_schema, purpose=purpose, user=user)
        try:
            return schema.model_validate_json(_extract_json(response.content))
        except (ValidationError, ValueError) as exc:
            last_error = str(exc)[:500]
            if attempt == 0:
                attempt_messages = [
                    *messages,
                    {"role": "assistant", "content": response.content},
                    {
                        "role": "user",
                        "content": "That reply was not valid JSON for the required schema "
                        f"({last_error}). Reply again with only the corrected JSON object.",
                    },
                ]
    _mark_last_call_invalid(user, purpose, last_error)
    raise LLMOutputError("The AI returned an invalid response twice. Please try again.")


def _extract_json(text: str) -> str:
    """Tolerate ```json fences or text around a single JSON object."""
    text = text.strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in reply")
    candidate = text[start : end + 1]
    json.loads(candidate)  # raises ValueError (JSONDecodeError) if malformed
    return candidate


def _mark_last_call_invalid(user: User | None, purpose: str, error: str) -> None:
    from .models import LLMCall

    last = LLMCall.objects.filter(purpose=purpose, user=user if user else None).first()
    if last:
        last.status, last.error = LLMCall.Status.INVALID_OUTPUT, error
        last.save(update_fields=["status", "error"])


# --- AI writer ------------------------------------------------------------------------------


class EmailDraft(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=5000)


TONES = ["friendly", "professional", "concise", "enthusiastic", "formal"]


def contact_context(contact: Contact) -> str:
    """Plain-text CRM context for one contact: profile, insights, deals, leads, history."""
    company = contact.company
    lines = [f"Contact: {contact.full_name} <{contact.email}>"]
    if company:
        lines.append(f"Company: {company.name} ({company.get_industry_display()}, {company.city})")
    if contact.segment:
        lines.append(f"Customer segment: {contact.segment}")
    if contact.churn_risk is not None:
        lines.append(f"Churn risk: {round(contact.churn_risk * 100)}%")
    for d in Deal.objects.filter(contact=contact).order_by("-updated_at")[:5]:
        when = f", expected close {d.expected_close_date:%d %b %Y}" if d.expected_close_date else ""
        lines.append(
            f"Deal: {d.title} - stage {d.get_stage_display()}, value Rs {d.value:,.0f}{when}"
        )
    for lead in Lead.objects.filter(contact=contact).order_by("-created_at")[:3]:
        budget = f", budget Rs {lead.budget:,.0f}" if lead.budget else ""
        lines.append(f"Lead: status {lead.get_status_display()}, source {lead.source}{budget}")
    activities = list(
        Activity.objects.filter(contact=contact).order_by("-occurred_at")[:HISTORY_ACTIVITIES]
    )
    lines.append("Recent activity (newest first):" if activities else "No logged activity yet.")
    for a in activities:
        body = (a.summary or a.body or "").strip().replace("\n", " ")
        if len(body) > BODY_CHARS:
            body = body[:BODY_CHARS] + "..."
        lines.append(f"- {a.occurred_at:%d %b %Y} {a.get_type_display()}: {a.subject}. {body}")
    return fence("\n".join(lines))


def draft_email(contact: Contact, *, goal: str, tone: str, user: User) -> EmailDraft:
    """Draft a personalised follow-up email from the contact's history and deals."""
    prompt = render(
        "draft_email",
        goal=goal.strip() or "follow up on our last conversation and agree a next step",
        tone=tone,
        rep_name=user.first_name or user.username,
        context=contact_context(contact),
    )
    return structured_chat(
        [{"role": "system", "content": prompt}, {"role": "user", "content": "Write the email."}],
        EmailDraft,
        purpose="draft_email",
        user=user,
    )


# --- Activity summarizer --------------------------------------------------------------------


class ActionItem(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    due_in_days: int | None = Field(default=None, ge=0, le=365)


class ActivitySummary(BaseModel):
    summary: str = Field(min_length=1, max_length=2000)
    action_items: list[ActionItem] = Field(default_factory=list, max_length=15)
    sentiment: Literal["positive", "neutral", "negative"]


def summarize_activity(activity: Activity, *, user: User) -> ActivitySummary:
    """Summarize an activity's notes into summary + action items + sentiment, and save them."""
    context = fence(
        f"{activity.get_type_display()} on {activity.occurred_at:%d %b %Y} with "
        f"{activity.contact.full_name}\nSubject: {activity.subject}\n\n{activity.body}"
    )
    result = structured_chat(
        [
            {"role": "system", "content": render("summarize_activity", context=context)},
            {"role": "user", "content": "Summarize this activity."},
        ],
        ActivitySummary,
        purpose="summarize_activity",
        user=user,
    )
    activity.summary = result.summary
    activity.action_items = {
        "items": [item.model_dump() for item in result.action_items],
        "sentiment": result.sentiment,
        "generated_at": timezone.now().isoformat(),
    }
    activity.save(update_fields=["summary", "action_items", "updated_at"])
    return result


@transaction.atomic
def tasks_from_action_items(activity: Activity, indexes: list[int], *, user: User) -> list[Task]:
    """Create tasks for the chosen action items of a summarized activity."""
    items = (activity.action_items or {}).get("items", [])
    chosen = [items[i] for i in sorted(set(indexes)) if 0 <= i < len(items)]
    today = timezone.localdate()
    tasks = [
        Task(
            owner=user,
            assigned_to=user,
            contact=activity.contact,
            deal=activity.deal,
            title=item["title"][:200],
            description=f"From the AI summary of: {activity.subject}",
            due_date=(
                today + timedelta(days=item["due_in_days"])
                if item.get("due_in_days") is not None
                else None
            ),
        )
        for item in chosen
    ]
    return Task.objects.bulk_create(tasks)
