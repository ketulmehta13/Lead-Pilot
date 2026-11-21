"""Invoicing + Razorpay with a mocked client. TEST keys only."""

import hashlib
import hmac
import json
from decimal import Decimal

import pytest
from django.core.cache import cache

from analytics.services import get_summary
from billing import razorpay_service as rzp
from billing import services
from billing.models import Invoice, Payment, WebhookEvent
from crm import services as crm_services
from crm.models import Activity

pytestmark = pytest.mark.django_db

KEY_SECRET = "test_key_secret"
WEBHOOK_SECRET = "test_webhook_secret"


@pytest.fixture(autouse=True)
def razorpay_env(monkeypatch):
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_ABC123")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", KEY_SECRET)
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", WEBHOOK_SECRET)
    cache.clear()


@pytest.fixture
def gateway(monkeypatch):
    """Fake Razorpay API calls; records what was sent."""
    sent = {"orders": [], "links": [], "refunds": []}

    def create_order(amount, receipt, notes):
        sent["orders"].append({"amount": rzp.to_paise(amount), "receipt": receipt, "notes": notes})
        return {"id": f"order_{len(sent['orders'])}", "amount": rzp.to_paise(amount)}

    def create_payment_link(amount, **kwargs):
        sent["links"].append({"amount": rzp.to_paise(amount), **kwargs})
        return {"id": "plink_1", "short_url": "https://rzp.io/i/demo"}

    def refund(payment_id, amount=None, notes=None):
        sent["refunds"].append({"payment_id": payment_id, "amount": amount})
        return {"id": "rfnd_1"}

    monkeypatch.setattr(rzp, "create_order", create_order)
    monkeypatch.setattr(rzp, "create_payment_link", create_payment_link)
    monkeypatch.setattr(rzp, "refund", refund)
    return sent


@pytest.fixture
def won_deal(rep, contact_of):
    return crm_services.create_deal(
        owner=rep, contact=contact_of(rep), title="Annual licence", stage="won",
        value=Decimal("100000"),
    )  # fmt: skip


@pytest.fixture
def invoice(won_deal, rep):
    return services.create_invoice(won_deal, owner=rep)


def sign(body: bytes, secret: str = WEBHOOK_SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def webhook(client, event: dict, *, event_id="evt_1", signature=None):
    body = json.dumps(event).encode()
    return client.post(
        "/api/billing/webhook/",
        data=body,
        content_type="application/json",
        HTTP_X_RAZORPAY_SIGNATURE=signature if signature is not None else sign(body),
        HTTP_X_RAZORPAY_EVENT_ID=event_id,
    )


def captured(invoice, payment_id="pay_1", amount=None):
    return {
        "event": "payment.captured",
        "payload": {"payment": {"entity": {
            "id": payment_id, "order_id": invoice.razorpay_order_id or "order_1",
            "amount": amount if amount is not None else rzp.to_paise(invoice.total),
            "method": "card", "status": "captured", "notes": {"invoice_id": str(invoice.id)},
        }}},
    }  # fmt: skip


# --- money ------------------------------------------------------------------------------------


def test_paise_conversion():
    assert rzp.to_paise(Decimal("499.50")) == 49950
    assert rzp.to_paise(Decimal("0.005")) == 1  # half-up
    assert rzp.to_paise(Decimal("118000")) == 11_800_000
    assert rzp.to_rupees(49950) == Decimal("499.50")


def test_only_test_keys_are_accepted(monkeypatch):
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_live_REAL")
    assert not rzp.is_configured()
    with pytest.raises(rzp.RazorpayNotConfigured):
        rzp.client()


# --- invoices ---------------------------------------------------------------------------------


def test_invoice_from_won_deal_adds_gst(client_for, rep, won_deal):
    response = client_for(rep).post(
        "/api/billing/invoices/",
        {"deal": won_deal.id, "items": [
            {"description": "Licence", "quantity": "2", "unit_price": "499.50"},
            {"description": "Onboarding", "quantity": "1", "unit_price": "1000"},
        ]},
        format="json",
    )  # fmt: skip
    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["number"].startswith("LP-") and body["number"].endswith("-00001")
    assert Decimal(body["subtotal"]) == Decimal("1999.00")
    assert Decimal(body["tax"]) == Decimal("359.82")  # 18% GST
    assert Decimal(body["total"]) == Decimal("2358.82")
    assert body["status"] == "draft" and len(body["items"]) == 2
    second = client_for(rep).post("/api/billing/invoices/", {"deal": won_deal.id}, format="json")
    assert second.json()["number"].endswith("-00002")
    assert Decimal(second.json()["total"]) == Decimal("118000.00")


def test_only_won_deals_can_be_invoiced(client_for, rep, contact_of):
    open_deal = crm_services.create_deal(owner=rep, contact=contact_of(rep), title="x", value=10)
    response = client_for(rep).post("/api/billing/invoices/", {"deal": open_deal.id}, format="json")
    assert response.status_code == 400
    assert "Won" in response.json()["error"]["message"]


def test_invoice_scoping_and_roles(client_for, rep, other_rep, support_user, invoice):
    assert client_for(other_rep).get(f"/api/billing/invoices/{invoice.id}/").status_code == 404
    assert client_for(support_user).get("/api/billing/invoices/").status_code == 403


# --- checkout ---------------------------------------------------------------------------------


def test_create_order_returns_key_id_but_never_the_secret(client_for, rep, invoice, gateway):
    response = client_for(rep).post(f"/api/billing/invoices/{invoice.id}/create-order/")
    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["key_id"] == "rzp_test_ABC123" and body["order_id"] == "order_1"
    assert body["amount"] == 11_800_000  # paise
    assert KEY_SECRET not in json.dumps(body)
    assert gateway["orders"][0] == {"amount": 11_800_000, "receipt": invoice.number,
                                    "notes": {"invoice_id": str(invoice.id)}}  # fmt: skip
    # Reuses the same order on a second click.
    client_for(rep).post(f"/api/billing/invoices/{invoice.id}/create-order/")
    assert len(gateway["orders"]) == 1
    invoice.refresh_from_db()
    assert invoice.status == "sent"


def test_payments_unavailable_without_keys(client_for, rep, invoice, monkeypatch):
    monkeypatch.delenv("RAZORPAY_KEY_SECRET")
    response = client_for(rep).post(f"/api/billing/invoices/{invoice.id}/create-order/")
    assert response.status_code == 503


def test_verify_valid_signature_marks_processing(client_for, rep, invoice, gateway):
    client = client_for(rep)
    client.post(f"/api/billing/invoices/{invoice.id}/create-order/")
    signature = hmac.new(KEY_SECRET.encode(), b"order_1|pay_1", hashlib.sha256).hexdigest()
    response = client.post(
        "/api/billing/verify/",
        {"razorpay_order_id": "order_1", "razorpay_payment_id": "pay_1",
         "razorpay_signature": signature},
        format="json",
    )  # fmt: skip
    assert response.status_code == 200, response.json()
    assert response.json()["status"] == "processing"  # the webhook makes it "paid"
    assert Payment.objects.get().status == "authorized"


def test_verify_tampered_signature_is_rejected(client_for, rep, invoice, gateway):
    client = client_for(rep)
    client.post(f"/api/billing/invoices/{invoice.id}/create-order/")
    response = client.post(
        "/api/billing/verify/",
        {"razorpay_order_id": "order_1", "razorpay_payment_id": "pay_1",
         "razorpay_signature": "0" * 64},
        format="json",
    )  # fmt: skip
    assert response.status_code == 400
    invoice.refresh_from_db()
    assert invoice.status == "sent" and not Payment.objects.exists()


# --- webhook ----------------------------------------------------------------------------------


def test_captured_webhook_marks_paid_wins_deal_and_logs_activity(client_for, rep, contact_of,
                                                                  gateway):  # fmt: skip
    deal = crm_services.create_deal(owner=rep, contact=contact_of(rep), title="Pilot",
                                    stage="won", value=Decimal("50000"))  # fmt: skip
    invoice = services.create_invoice(deal, owner=rep)
    client_for(rep).post(f"/api/billing/invoices/{invoice.id}/create-order/")
    invoice.refresh_from_db()
    before = get_summary(rep)["collected_this_month"]

    response = webhook(client_for(None), captured(invoice))
    assert response.status_code == 200 and response.json()["status"] == "processed"
    invoice.refresh_from_db()
    assert invoice.status == "paid" and invoice.paid_at is not None
    payment = Payment.objects.get()
    assert payment.status == "captured" and payment.amount == Decimal("59000.00")
    assert Activity.objects.filter(subject=f"Payment received for {invoice.number}").exists()
    assert get_summary(rep)["collected_this_month"] == before + Decimal("59000.00")


def test_webhook_moves_an_unwon_deal_to_won(rep, contact_of, gateway):
    deal = crm_services.create_deal(owner=rep, contact=contact_of(rep), title="x", stage="won",
                                    value=Decimal("1000"))  # fmt: skip
    invoice = services.create_invoice(deal, owner=rep)
    crm_services.move_deal(deal, stage="negotiation", position=0, actor=rep)
    services.mark_paid(invoice, {"id": "pay_9", "amount": rzp.to_paise(invoice.total)})
    deal.refresh_from_db()
    assert deal.stage == "won"


def test_duplicate_webhook_changes_nothing(client_for, rep, invoice, gateway):
    event = captured(invoice)
    first = webhook(client_for(None), event, event_id="evt_dup")
    activities = Activity.objects.count()
    paid_at = Invoice.objects.get(pk=invoice.pk).paid_at
    second = webhook(client_for(None), event, event_id="evt_dup")
    assert first.json()["status"] == "processed"
    assert second.status_code == 200 and second.json()["status"] == "duplicate"
    assert Activity.objects.count() == activities
    assert Invoice.objects.get(pk=invoice.pk).paid_at == paid_at
    assert WebhookEvent.objects.count() == 1 and Payment.objects.count() == 1


def test_tampered_webhook_signature_returns_400(client_for, invoice):
    response = webhook(client_for(None), captured(invoice), signature="deadbeef" * 8)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_webhook"
    invoice.refresh_from_db()
    assert invoice.status == "draft" and not WebhookEvent.objects.exists()


def test_webhook_body_changed_after_signing_is_rejected(client_for, invoice):
    body = json.dumps(captured(invoice)).encode()
    signature = sign(body)
    forged = body.replace(b'"card"', b'"upi"')
    response = client_for(None).post("/api/billing/webhook/", data=forged,
                                     content_type="application/json",
                                     HTTP_X_RAZORPAY_SIGNATURE=signature)  # fmt: skip
    assert response.status_code == 400


def test_failed_payment_marks_invoice_failed(client_for, invoice):
    event = captured(invoice)
    event["event"] = "payment.failed"
    event["payload"]["payment"]["entity"]["status"] = "failed"
    webhook(client_for(None), event, event_id="evt_fail")
    invoice.refresh_from_db()
    assert invoice.status == "failed"
    assert Payment.objects.get().status == "failed"


def test_payment_link_paid_webhook(client_for, rep, invoice, gateway):
    response = client_for(rep).post(f"/api/billing/invoices/{invoice.id}/payment-link/")
    assert response.json()["payment_link_url"] == "https://rzp.io/i/demo"
    assert gateway["links"][0]["customer"]["email"] == invoice.contact.email
    event = {
        "event": "payment_link.paid",
        "payload": {
            "payment_link": {"entity": {"id": "plink_1", "status": "paid"}},
            "payment": {"entity": {"id": "pay_link_1", "amount": rzp.to_paise(invoice.total),
                                   "method": "upi"}},
        },
    }  # fmt: skip
    assert webhook(client_for(None), event, event_id="evt_link").json()["status"] == "processed"
    invoice.refresh_from_db()
    assert invoice.status == "paid"


def test_underpayment_is_not_marked_paid(client_for, invoice):
    response = webhook(client_for(None), captured(invoice, amount=100))
    assert response.json()["status"] == "ignored"
    invoice.refresh_from_db()
    assert invoice.status == "draft"
    assert "less than the invoice total" in WebhookEvent.objects.get().error


def test_unrelated_events_are_stored_and_ignored(client_for):
    response = webhook(client_for(None), {"event": "order.paid", "payload": {}}, event_id="e9")
    assert response.json()["status"] == "ignored"
    assert WebhookEvent.objects.get().processed


# --- refunds ----------------------------------------------------------------------------------


def test_refund_is_admin_only_and_marks_refunded(client_for, rep, admin_user, invoice, gateway):
    services.mark_paid(invoice, {"id": "pay_r", "amount": rzp.to_paise(invoice.total)})
    payment = Payment.objects.get()
    assert client_for(rep).post(f"/api/billing/payments/{payment.id}/refund/").status_code == 403
    response = client_for(admin_user).post(f"/api/billing/payments/{payment.id}/refund/")
    assert response.status_code == 200, response.json()
    assert response.json()["status"] == "refunded"
    assert gateway["refunds"] == [{"payment_id": "pay_r", "amount": Decimal("118000.00")}]
    invoice.refresh_from_db()
    assert invoice.status == "refunded"
    again = client_for(admin_user).post(f"/api/billing/payments/{payment.id}/refund/")
    assert again.status_code == 400


def test_partial_refund(client_for, admin_user, invoice, gateway):
    services.mark_paid(invoice, {"id": "pay_p", "amount": rzp.to_paise(invoice.total)})
    payment = Payment.objects.get()
    response = client_for(admin_user).post(
        f"/api/billing/payments/{payment.id}/refund/", {"amount": "1000"}, format="json"
    )
    assert response.json()["status"] == "captured"
    assert Decimal(response.json()["refunded_amount"]) == Decimal("1000.00")
    assert Invoice.objects.get(pk=invoice.pk).status == "paid"


# --- agent tools ------------------------------------------------------------------------------


def test_agent_invoice_tools_are_write_tools(rep, won_deal, gateway):
    from agent import tools

    assert tools.TOOLS["create_invoice"].write and tools.TOOLS["create_payment_link"].write
    out = tools.run_tool(rep, "create_invoice", {"deal_id": won_deal.id})
    assert out["status"] == "draft" and out["total"] == "118000.00"
    link = tools.run_tool(rep, "create_payment_link", {"invoice_id": out["invoice_id"]})
    assert link["payment_link"] == "https://rzp.io/i/demo"
