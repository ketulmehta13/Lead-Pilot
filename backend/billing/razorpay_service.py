"""Thin wrapper over the Razorpay SDK. TEST MODE ONLY.

Keys come from env: RAZORPAY_KEY_ID (rzp_test_...), RAZORPAY_KEY_SECRET,
RAZORPAY_WEBHOOK_SECRET. The key secret never leaves the backend; the frontend only receives
the key id and an order id. Amounts go to Razorpay in paise (rupees x 100).
"""

from __future__ import annotations

import hashlib
import hmac
import os
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import razorpay
from razorpay.errors import BadRequestError, GatewayError, ServerError, SignatureVerificationError


class RazorpayNotConfigured(Exception):
    """Keys missing, or not test-mode keys."""


class RazorpayError(Exception):
    """Razorpay rejected the request or is unreachable."""


def key_id() -> str:
    return os.environ.get("RAZORPAY_KEY_ID", "").strip()


def is_configured() -> bool:
    return key_id().startswith("rzp_test_") and bool(os.environ.get("RAZORPAY_KEY_SECRET"))


def client() -> razorpay.Client:
    kid, secret = key_id(), os.environ.get("RAZORPAY_KEY_SECRET", "").strip()
    if not kid or not secret:
        raise RazorpayNotConfigured("Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET (test mode).")
    if not kid.startswith("rzp_test_"):
        raise RazorpayNotConfigured("LeadPilot only accepts Razorpay TEST keys (rzp_test_...).")
    c = razorpay.Client(auth=(kid, secret))
    c.set_app_details({"title": "LeadPilot", "version": "1.0"})
    return c


def to_paise(rupees: Decimal) -> int:
    """Rs 499.50 -> 49950 (rounded half-up to the nearest paisa)."""
    return int((Decimal(rupees) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def to_rupees(paise: int) -> Decimal:
    return (Decimal(int(paise)) / 100).quantize(Decimal("0.01"))


def _call(fn, *args, **kwargs) -> dict[str, Any]:
    try:
        return fn(*args, **kwargs)
    except (BadRequestError, GatewayError, ServerError) as exc:
        raise RazorpayError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - network errors etc.
        raise RazorpayError(f"Razorpay request failed: {exc}") from exc


def create_order(amount: Decimal, receipt: str, notes: dict[str, Any]) -> dict[str, Any]:
    return _call(
        client().order.create,
        data={"amount": to_paise(amount), "currency": "INR", "receipt": receipt, "notes": notes},
    )


def verify_payment(order_id: str, payment_id: str, signature: str) -> bool:
    """Checkout signature: HMAC-SHA256(order_id|payment_id, key secret)."""
    try:
        client().utility.verify_payment_signature(
            {
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": signature,
            }
        )
        return True
    except SignatureVerificationError:
        return False


def create_payment_link(
    amount: Decimal, *, reference_id: str, description: str, customer: dict[str, str],
    notes: dict[str, Any], expire_by: int | None = None,
) -> dict[str, Any]:  # fmt: skip
    data: dict[str, Any] = {
        "amount": to_paise(amount),
        "currency": "INR",
        "accept_partial": False,
        "reference_id": reference_id,
        "description": description[:2048],
        "customer": {k: v for k, v in customer.items() if v},
        "notify": {"email": True, "sms": False},
        "reminder_enable": True,
        "notes": notes,
    }
    if expire_by:
        data["expire_by"] = expire_by
    return _call(client().payment_link.create, data=data)


def refund(payment_id: str, amount: Decimal | None = None, notes: dict | None = None) -> dict:
    data: dict[str, Any] = {"notes": notes or {}}
    if amount is not None:
        data["amount"] = to_paise(amount)
    return _call(client().payment.refund, payment_id, data)


def verify_webhook(body: bytes, signature: str) -> bool:
    """X-Razorpay-Signature = HMAC-SHA256(raw body, webhook secret), compared in constant time."""
    secret = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
