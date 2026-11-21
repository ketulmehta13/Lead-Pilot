"""Agent tools. Each tool = a function + a JSON schema + a read/write flag.

READ tools run automatically. WRITE tools change CRM data and only run after the user approves
the step. No tool can delete data or move money (payment links only create a link the customer
may pay; refunds are admin-only and not exposed to the agent).

Tools call existing services (crm.services, genai.services, genai.rag, billing.services);
they never duplicate ORM logic. Every tool is scoped to what the run's user may access.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.utils import timezone

from accounts.models import User
from crm import services as crm
from crm.models import Contact, Deal

MAX_LIST = 20


class ToolError(Exception):
    """A problem the model should see and can recover from (bad id, not allowed...)."""


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    write: bool
    fn: Callable[..., dict[str, Any]]

    def schema(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description, "parameters": self.parameters}


def _obj(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


def _contact(user: User, contact_id: Any) -> Contact:
    contacts = Contact.objects.select_related("company")
    if not user.is_admin:
        contacts = contacts.filter(owner=user)
    contact = contacts.filter(pk=contact_id).first()
    if contact is None:
        raise ToolError(f"Contact {contact_id} not found (or not yours).")
    return contact


def _deal(user: User, deal_id: Any) -> Deal:
    deals = Deal.objects.select_related("contact")
    if not user.is_admin:
        deals = deals.filter(owner=user)
    deal = deals.filter(pk=deal_id).first()
    if deal is None:
        raise ToolError(f"Deal {deal_id} not found (or not yours).")
    return deal


# --- READ tools -----------------------------------------------------------------------------


def search_leads(user: User, label: str | None = None, status: str | None = None,
                 not_contacted_days: int | None = None, min_score: int | None = None,
                 limit: int = 10) -> dict[str, Any]:  # fmt: skip
    leads = crm.search_leads(
        user,
        label=label,
        status=status,
        not_contacted_days=not_contacted_days,
        min_score=min_score,
        limit=min(int(limit or 10), MAX_LIST),
    )
    now = timezone.now()
    return {
        "count": len(leads),
        "leads": [
            {
                "lead_id": lead.id,
                "contact_id": lead.contact_id,
                "contact": lead.contact.full_name,
                "company": lead.contact.company.name if lead.contact.company else None,
                "score": lead.score,
                "label": lead.score_label,
                "status": lead.status,
                "budget": float(lead.budget) if lead.budget is not None else None,
                "days_since_contact": (
                    (now - lead.last_contacted_at).days if lead.last_contacted_at else None
                ),
            }
            for lead in leads
        ],
    }


def get_contact_history(user: User, contact_id: int) -> dict[str, Any]:
    from genai.services import contact_context

    contact = _contact(user, contact_id)
    return {"contact_id": contact.id, "history": contact_context(contact)}


def draft_email(user: User, contact_id: int, goal: str, tone: str = "friendly") -> dict[str, Any]:
    from genai import services as genai

    contact = _contact(user, contact_id)
    if tone not in genai.TONES:
        tone = "friendly"
    draft = genai.draft_email(contact, goal=goal, tone=tone, user=user)
    return {"contact_id": contact.id, "to": contact.email, **draft.model_dump(),
            "note": "Draft only. Nothing was sent."}  # fmt: skip


def ask_crm(user: User, question: str) -> dict[str, Any]:
    from genai import rag

    answer, citations = rag.grounded_answer(question, user)
    return {
        "answer": answer,
        "sources": [{"type": c["type"], "id": c["id"], "snippet": c["snippet"]} for c in citations],
    }


# --- WRITE tools (need approval) ------------------------------------------------------------


def create_task(user: User, title: str, contact_id: int | None = None, deal_id: int | None = None,
                due_in_days: int | None = None, priority: str = "medium",
                description: str = "") -> dict[str, Any]:  # fmt: skip
    contact = _contact(user, contact_id) if contact_id else None
    deal = _deal(user, deal_id) if deal_id else None
    if priority not in ("low", "medium", "high"):
        priority = "medium"
    due = (
        timezone.localdate() + timedelta(days=int(due_in_days)) if due_in_days is not None else None
    )
    task = crm.create_task(owner=user, title=title, contact=contact, deal=deal, due_date=due,
                           priority=priority, description=description,
                           created_by_agent=True)  # fmt: skip
    return {"task_id": task.id, "title": task.title, "due_date": str(task.due_date or "")}


def update_deal_stage(user: User, deal_id: int, stage: str) -> dict[str, Any]:
    if stage not in Deal.Stage.values:
        raise ToolError(f"Unknown stage '{stage}'. Use one of {Deal.Stage.values}.")
    deal = _deal(user, deal_id)
    visible = Deal.objects.all() if user.is_admin else Deal.objects.filter(owner=user)
    before = deal.stage
    deal = crm.move_deal(deal, stage=stage, position=10_000, actor=user, visible=visible)
    return {"deal_id": deal.id, "from": before, "to": deal.stage}


TOOLS: dict[str, Tool] = {}


def register(tool: Tool) -> Tool:
    TOOLS[tool.name] = tool
    return tool


register(Tool(
    "search_leads",
    "Find the user's open leads. Filter by AI score label (hot/warm/cold), status, minimum "
    "score, or leads not contacted for N days. Returns lead and contact ids, scores and how "
    "many days since the last contact.",
    _obj({
        "label": {"type": "string", "enum": ["hot", "warm", "cold"]},
        "status": {"type": "string", "enum": ["new", "contacted", "qualified"]},
        "not_contacted_days": {"type": "integer", "minimum": 0, "maximum": 365},
        "min_score": {"type": "integer", "minimum": 0, "maximum": 100},
        "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIST},
    }),
    write=False, fn=search_leads,
))  # fmt: skip
register(Tool(
    "get_contact_history",
    "Profile, deals, leads and the last 10 activities of one contact.",
    _obj({"contact_id": {"type": "integer"}}, ["contact_id"]),
    write=False, fn=get_contact_history,
))  # fmt: skip
register(Tool(
    "draft_email",
    "Draft (do NOT send) a personalised follow-up email to a contact from their history.",
    _obj({
        "contact_id": {"type": "integer"},
        "goal": {"type": "string", "description": "What the email should achieve"},
        "tone": {"type": "string",
                 "enum": ["friendly", "professional", "concise", "enthusiastic", "formal"]},
    }, ["contact_id", "goal"]),
    write=False, fn=draft_email,
))  # fmt: skip
register(Tool(
    "ask_crm",
    "Answer a question from the CRM's notes, activities and tickets, with sources.",
    _obj({"question": {"type": "string"}}, ["question"]),
    write=False, fn=ask_crm,
))  # fmt: skip
register(Tool(
    "create_task",
    "Create a follow-up task for the user (requires the user's approval).",
    _obj({
        "title": {"type": "string", "maxLength": 200},
        "contact_id": {"type": "integer"},
        "deal_id": {"type": "integer"},
        "due_in_days": {"type": "integer", "minimum": 0, "maximum": 365},
        "priority": {"type": "string", "enum": ["low", "medium", "high"]},
        "description": {"type": "string"},
    }, ["title"]),
    write=True, fn=create_task,
))  # fmt: skip
register(Tool(
    "update_deal_stage",
    "Move a deal to another pipeline stage (requires the user's approval).",
    _obj({
        "deal_id": {"type": "integer"},
        "stage": {"type": "string", "enum": list(Deal.Stage.values)},
    }, ["deal_id", "stage"]),
    write=True, fn=update_deal_stage,
))  # fmt: skip


def create_invoice(user: User, deal_id: int, due_in_days: int = 7) -> dict[str, Any]:
    from billing import services as billing

    deal = _deal(user, deal_id)
    try:
        invoice = billing.create_invoice(deal, owner=user, due_in_days=int(due_in_days))
    except billing.BillingError as exc:
        raise ToolError(str(exc)) from exc
    return {"invoice_id": invoice.id, "number": invoice.number, "total": str(invoice.total),
            "status": invoice.status}  # fmt: skip


def create_payment_link(user: User, invoice_id: int) -> dict[str, Any]:
    from billing import razorpay_service as rzp
    from billing import services as billing
    from billing.models import Invoice

    invoices = Invoice.objects.select_related("contact", "deal")
    if not user.is_admin:
        invoices = invoices.filter(owner=user)
    invoice = invoices.filter(pk=invoice_id).first()
    if invoice is None:
        raise ToolError(f"Invoice {invoice_id} not found (or not yours).")
    try:
        invoice = billing.create_payment_link(invoice)
    except (billing.BillingError, rzp.RazorpayError, rzp.RazorpayNotConfigured) as exc:
        raise ToolError(str(exc)) from exc
    return {"invoice_id": invoice.id, "payment_link": invoice.payment_link_url,
            "note": "Razorpay emails this link to the customer; nothing was charged."}  # fmt: skip


register(Tool(
    "create_invoice",
    "Create a draft invoice (GST 18%) for one of the user's Won deals (requires approval).",
    _obj({
        "deal_id": {"type": "integer"},
        "due_in_days": {"type": "integer", "minimum": 0, "maximum": 90},
    }, ["deal_id"]),
    write=True, fn=create_invoice,
))  # fmt: skip
register(Tool(
    "create_payment_link",
    "Create a Razorpay payment link for an invoice; Razorpay emails it to the customer. "
    "Does not charge anyone (requires approval).",
    _obj({"invoice_id": {"type": "integer"}}, ["invoice_id"]),
    write=True, fn=create_payment_link,
))  # fmt: skip


def schemas() -> list[dict[str, Any]]:
    return [t.schema() for t in TOOLS.values()]


def run_tool(user: User, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Execute a tool; problems come back as {"error": ...} for the model to read."""
    tool = TOOLS.get(name)
    if tool is None:
        return {"error": f"Unknown tool '{name}'. Available: {sorted(TOOLS)}"}
    allowed = set(tool.parameters["properties"])
    args = {k: v for k, v in (arguments or {}).items() if k in allowed}
    missing = [k for k in tool.parameters.get("required", []) if k not in args]
    if missing:
        return {"error": f"Missing required argument(s): {', '.join(missing)}"}
    try:
        return tool.fn(user, **args)
    except ToolError as exc:
        return {"error": str(exc)}
    except (TypeError, ValueError) as exc:
        return {"error": f"Invalid arguments: {exc}"}
