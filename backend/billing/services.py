"""Invoicing + payments business logic.

Flow (Checkout):  create_invoice -> start_checkout (Razorpay order) -> Checkout.js in the
browser -> confirm_checkout (verify signature, mark "processing") -> webhook payment.captured
-> mark_paid (source of truth): invoice paid, deal won, Activity "Payment received",
dashboard cache cleared.
Flow (Payment Link): create_payment_link -> customer pays by email link -> webhook
payment_link.paid -> mark_paid.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from accounts.models import User
from analytics.services import invalidate_summary_cache
from crm import services as crm
from crm.models import Activity, Deal

from . import razorpay_service as rzp
from .models import GST_RATE, Invoice, InvoiceItem, Payment, WebhookEvent

logger = logging.getLogger(__name__)
CENT = Decimal("0.01")


class BillingError(ValueError):
    """A request that doesn't fit the invoice's state (e.g. paying a paid invoice)."""


# --- Invoices -------------------------------------------------------------------------------


def _next_number() -> str:
    """LP-<year>-00001, sequential per year."""
    prefix = f"LP-{timezone.localdate().year}-"
    last = Invoice.objects.filter(number__startswith=prefix).aggregate(m=Max("number"))["m"]
    seq = int(last.rsplit("-", 1)[1]) + 1 if last else 1
    return f"{prefix}{seq:05d}"


def _totals(items: list[dict[str, Any]], tax_rate: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    subtotal = sum((Decimal(i["quantity"]) * Decimal(i["unit_price"]) for i in items), Decimal(0))
    subtotal = subtotal.quantize(CENT)
    tax = (subtotal * tax_rate / 100).quantize(CENT)
    return subtotal, tax, subtotal + tax


def create_invoice(
    deal: Deal,
    *,
    owner: User,
    items: list[dict[str, Any]] | None = None,
    due_in_days: int = 7,
    notes: str = "",
) -> Invoice:
    """Invoice a Won deal. Default: one line for the deal's value. GST 18% on top."""
    if deal.stage != Deal.Stage.WON:
        raise BillingError("Only Won deals can be invoiced.")
    items = items or [{"description": deal.title, "quantity": 1, "unit_price": deal.value}]
    subtotal, tax, total = _totals(items, GST_RATE)
    if total <= 0:
        raise BillingError("Invoice total must be more than zero.")
    for attempt in range(3):  # two users invoicing at once may collide on the number
        try:
            with transaction.atomic():
                invoice = Invoice.objects.create(
                    owner=owner,
                    number=_next_number(),
                    deal=deal,
                    contact=deal.contact,
                    subtotal=subtotal,
                    tax_rate=GST_RATE,
                    tax=tax,
                    total=total,
                    due_date=timezone.localdate() + timedelta(days=due_in_days),
                    notes=notes,
                )
                InvoiceItem.objects.bulk_create(
                    InvoiceItem(
                        invoice=invoice,
                        description=str(i["description"])[:200],
                        quantity=Decimal(i["quantity"]),
                        unit_price=Decimal(i["unit_price"]).quantize(CENT),
                        amount=(Decimal(i["quantity"]) * Decimal(i["unit_price"])).quantize(CENT),
                    )
                    for i in items
                )
            return invoice
        except IntegrityError:
            if attempt == 2:
                raise
    raise AssertionError("unreachable")


# --- Checkout -------------------------------------------------------------------------------


def start_checkout(invoice: Invoice) -> dict[str, Any]:
    """Create (or reuse) a Razorpay order; return what Checkout.js needs (no secrets)."""
    if invoice.status in (Invoice.Status.PAID, Invoice.Status.REFUNDED):
        raise BillingError(f"Invoice {invoice.number} is already {invoice.status}.")
    if not invoice.razorpay_order_id:
        order = rzp.create_order(
            invoice.total, receipt=invoice.number, notes={"invoice_id": str(invoice.id)}
        )
        invoice.razorpay_order_id = order["id"]
        if invoice.status == Invoice.Status.DRAFT:
            invoice.status = Invoice.Status.SENT
        invoice.save(update_fields=["razorpay_order_id", "status", "updated_at"])
    contact = invoice.contact
    return {
        "key_id": rzp.key_id(),
        "order_id": invoice.razorpay_order_id,
        "amount": rzp.to_paise(invoice.total),
        "currency": invoice.currency,
        "name": "LeadPilot",
        "description": f"Invoice {invoice.number}",
        "invoice_id": invoice.id,
        "prefill": {"name": contact.full_name, "email": contact.email, "contact": contact.phone},
    }


def confirm_checkout(order_id: str, payment_id: str, signature: str) -> Invoice:
    """Verify the Checkout signature and mark the invoice "processing". The webhook confirms."""
    invoice = Invoice.objects.filter(razorpay_order_id=order_id).first()
    if invoice is None:
        raise BillingError("Unknown order.")
    if not rzp.verify_payment(order_id, payment_id, signature):
        raise BillingError("Payment signature is invalid.")
    with transaction.atomic():
        Payment.objects.get_or_create(
            razorpay_payment_id=payment_id,
            defaults={"invoice": invoice, "razorpay_order_id": order_id, "amount": invoice.total,
                      "status": Payment.Status.AUTHORIZED},  # fmt: skip
        )
        if invoice.status not in (Invoice.Status.PAID, Invoice.Status.REFUNDED):
            invoice.status = Invoice.Status.PROCESSING
            invoice.save(update_fields=["status", "updated_at"])
    return invoice


def create_payment_link(invoice: Invoice) -> Invoice:
    """Payment link Razorpay emails to the customer."""
    if invoice.status in (Invoice.Status.PAID, Invoice.Status.REFUNDED):
        raise BillingError(f"Invoice {invoice.number} is already {invoice.status}.")
    if invoice.payment_link_url:
        return invoice
    contact = invoice.contact
    link = rzp.create_payment_link(
        invoice.total,
        reference_id=invoice.number,
        description=f"Invoice {invoice.number} - {invoice.deal.title}",
        customer={"name": contact.full_name, "email": contact.email, "contact": contact.phone},
        notes={"invoice_id": str(invoice.id)},
    )
    invoice.razorpay_payment_link_id = link["id"]
    invoice.payment_link_url = link.get("short_url", "")
    if invoice.status == Invoice.Status.DRAFT:
        invoice.status = Invoice.Status.SENT
    invoice.save(
        update_fields=["razorpay_payment_link_id", "payment_link_url", "status", "updated_at"]
    )
    return invoice


# --- Webhook (source of truth) --------------------------------------------------------------


def handle_webhook(body: bytes, signature: str, event_id: str = "") -> tuple[str, WebhookEvent]:
    """Verify, store and process a webhook once. Returns ("processed" | "duplicate" |
    "ignored", event). Raises BillingError on a bad signature or body."""
    if not rzp.verify_webhook(body, signature):
        raise BillingError("Invalid webhook signature.")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise BillingError("Webhook body is not JSON.") from exc
    event_type = str(payload.get("event", ""))
    # Razorpay sends X-Razorpay-Event-Id; fall back to a hash of the body.
    event_id = event_id or hashlib.sha256(body).hexdigest()

    with transaction.atomic():
        event, created = WebhookEvent.objects.select_for_update().get_or_create(
            event_id=event_id, defaults={"event_type": event_type, "payload": payload}
        )
        if not created and event.processed:
            return "duplicate", event
        try:
            outcome = _process(event_type, payload.get("payload", {}))
        except BillingError as exc:
            event.error = str(exc)
            event.save(update_fields=["error"])
            logger.warning("Webhook %s not applied: %s", event_id, exc)
            return "ignored", event
        event.processed, event.error = True, ""
        event.save(update_fields=["processed", "error"])
    return outcome, event


def _invoice_for(payment: dict[str, Any], link: dict[str, Any] | None = None) -> Invoice:
    q = Invoice.objects.select_for_update()
    invoice = None
    if link and link.get("id"):
        invoice = q.filter(razorpay_payment_link_id=link["id"]).first()
    if invoice is None and payment.get("order_id"):
        invoice = q.filter(razorpay_order_id=payment["order_id"]).first()
    notes = (payment.get("notes") or {}) if isinstance(payment.get("notes"), dict) else {}
    if invoice is None and str(notes.get("invoice_id", "")).isdigit():
        invoice = q.filter(pk=int(notes["invoice_id"])).first()
    if invoice is None:
        raise BillingError("No invoice matches this payment.")
    return invoice


def _process(event_type: str, data: dict[str, Any]) -> str:
    payment = (data.get("payment") or {}).get("entity") or {}
    if event_type == "payment.captured":
        mark_paid(_invoice_for(payment), payment)
        return "processed"
    if event_type == "payment_link.paid":
        link = (data.get("payment_link") or {}).get("entity") or {}
        mark_paid(_invoice_for(payment, link), payment)
        return "processed"
    if event_type == "payment.failed":
        mark_failed(_invoice_for(payment), payment)
        return "processed"
    return "ignored"  # other events are stored but need no action


def _upsert_payment(invoice: Invoice, payment: dict[str, Any], status: str) -> Payment:
    obj, _ = Payment.objects.update_or_create(
        razorpay_payment_id=payment.get("id") or f"unknown_{invoice.id}",
        defaults={
            "invoice": invoice,
            "razorpay_order_id": payment.get("order_id") or "",
            "amount": rzp.to_rupees(payment.get("amount", rzp.to_paise(invoice.total))),
            "method": str(payment.get("method") or "")[:20],
            "status": status,
            "raw": payment,
        },
    )
    return obj


def mark_paid(invoice: Invoice, payment: dict[str, Any]) -> Invoice:
    """Idempotent: invoice paid, deal won, timeline Activity, dashboard cache cleared."""
    if invoice.status == Invoice.Status.PAID:
        return invoice
    paid = rzp.to_rupees(payment.get("amount", rzp.to_paise(invoice.total)))
    if paid < invoice.total:
        raise BillingError(f"Paid Rs {paid} is less than the invoice total Rs {invoice.total}.")
    _upsert_payment(invoice, payment, Payment.Status.CAPTURED)
    invoice.status, invoice.paid_at = Invoice.Status.PAID, timezone.now()
    invoice.save(update_fields=["status", "paid_at", "updated_at"])

    deal = Deal.objects.get(pk=invoice.deal_id)  # fresh: the cached relation may be stale
    owner = invoice.owner or deal.owner
    if deal.stage != Deal.Stage.WON and owner is not None:
        crm.move_deal(deal, stage=Deal.Stage.WON, position=10_000, actor=owner)
    crm.log_activity(
        owner=owner,
        contact=invoice.contact,
        deal=deal,
        type=Activity.Type.NOTE,
        subject=f"Payment received for {invoice.number}",
        body=f"Rs {invoice.total:,.2f} received via Razorpay "
        f"({payment.get('method') or 'online'}, payment {payment.get('id', '-')}).",
    )
    invalidate_summary_cache()
    return invoice


def mark_failed(invoice: Invoice, payment: dict[str, Any]) -> Invoice:
    _upsert_payment(invoice, payment, Payment.Status.FAILED)
    if invoice.status not in (Invoice.Status.PAID, Invoice.Status.REFUNDED):
        invoice.status = Invoice.Status.FAILED
        invoice.save(update_fields=["status", "updated_at"])
    return invoice


# --- Refunds (admin only) -------------------------------------------------------------------


def refund_payment(payment: Payment, *, actor: User, amount: Decimal | None = None) -> Payment:
    if payment.status != Payment.Status.CAPTURED:
        raise BillingError("Only captured payments can be refunded.")
    amount = amount or payment.amount
    if amount <= 0 or amount > payment.amount - payment.refunded_amount:
        raise BillingError("Refund amount is more than what can be refunded.")
    result = rzp.refund(payment.razorpay_payment_id, amount, notes={"by": actor.username})
    with transaction.atomic():
        payment.refund_id = result.get("id", "")
        payment.refunded_amount += amount
        if payment.refunded_amount >= payment.amount:
            payment.status = Payment.Status.REFUNDED
        payment.save()
        invoice = payment.invoice
        if payment.status == Payment.Status.REFUNDED:
            invoice.status = Invoice.Status.REFUNDED
            invoice.save(update_fields=["status", "updated_at"])
        crm.log_activity(
            owner=invoice.owner or actor,
            contact=invoice.contact,
            deal=invoice.deal,
            type=Activity.Type.NOTE,
            subject=f"Refund issued for {invoice.number}",
            body=f"Rs {amount:,.2f} refunded by {actor.get_full_name() or actor.username}.",
        )
    invalidate_summary_cache()
    return payment
