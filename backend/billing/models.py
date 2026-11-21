"""Invoices and Razorpay payments. Money is stored as Decimal rupees; Razorpay gets paise."""

from decimal import Decimal

from django.db import models

from common.models import OwnedModel, TimeStampedModel
from crm.models import Contact, Deal

GST_RATE = Decimal("18.00")


class Invoice(OwnedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"
        PROCESSING = "processing", "Processing"  # paid in Checkout, waiting for the webhook
        PAID = "paid", "Paid"
        FAILED = "failed", "Payment failed"
        REFUNDED = "refunded", "Refunded"

    number = models.CharField(max_length=20, unique=True)
    deal = models.ForeignKey(Deal, on_delete=models.PROTECT, related_name="invoices")
    contact = models.ForeignKey(Contact, on_delete=models.PROTECT, related_name="invoices")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    currency = models.CharField(max_length=3, default="INR")
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=GST_RATE)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    razorpay_order_id = models.CharField(max_length=40, blank=True, db_index=True)
    razorpay_payment_link_id = models.CharField(max_length=40, blank=True, db_index=True)
    payment_link_url = models.URLField(blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "paid_at"])]
        constraints = [
            models.CheckConstraint(condition=models.Q(total__gte=0), name="invoice_total_gte_0")
        ]

    def __str__(self) -> str:
        return self.number


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
    description = models.CharField(max_length=200)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return self.description


class Payment(TimeStampedModel):
    class Status(models.TextChoices):
        AUTHORIZED = "authorized", "Authorized"  # Checkout succeeded, signature verified
        CAPTURED = "captured", "Captured"  # confirmed by webhook
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payments")
    razorpay_payment_id = models.CharField(max_length=40, unique=True)
    razorpay_order_id = models.CharField(max_length=40, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices)
    refund_id = models.CharField(max_length=40, blank=True)
    refunded_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    raw = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.razorpay_payment_id


class WebhookEvent(models.Model):
    """Every Razorpay webhook we accepted. `event_id` is unique: duplicates are skipped."""

    event_id = models.CharField(max_length=80, unique=True)
    event_type = models.CharField(max_length=60)
    payload = models.JSONField()
    processed = models.BooleanField(default=False)
    error = models.TextField(blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at"]

    def __str__(self) -> str:
        return f"{self.event_type} {self.event_id}"
