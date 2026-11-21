from decimal import Decimal

from rest_framework import serializers

from common.serializers import OwnedModelSerializer, OwnedRelatedField
from crm.models import Deal

from .models import Invoice, InvoiceItem, Payment


class InvoiceItemSerializer(serializers.ModelSerializer):
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0"))

    class Meta:
        model = InvoiceItem
        fields = ["id", "description", "quantity", "unit_price", "amount"]
        read_only_fields = ["amount"]


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            "id", "razorpay_payment_id", "amount", "method", "status", "refunded_amount",
            "refund_id", "created_at",
        ]  # fmt: skip


class InvoiceSerializer(OwnedModelSerializer):
    deal_title = serializers.CharField(source="deal.title", read_only=True)
    contact_name = serializers.CharField(source="contact.full_name", read_only=True)
    contact_email = serializers.EmailField(source="contact.email", read_only=True)
    company_name = serializers.CharField(
        source="contact.company.name", read_only=True, default=None
    )
    items = InvoiceItemSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id", "number", "deal", "deal_title", "contact", "contact_name", "contact_email",
            "company_name", "status", "currency", "items", "subtotal", "tax_rate", "tax",
            "total", "due_date", "notes", "razorpay_order_id", "payment_link_url", "paid_at",
            "payments", "owner", "owner_name", "created_at", "updated_at",
        ]  # fmt: skip
        read_only_fields = fields


class InvoiceCreateSerializer(serializers.Serializer):
    deal = OwnedRelatedField(queryset=Deal.objects.all())
    items = InvoiceItemSerializer(many=True, required=False)
    due_in_days = serializers.IntegerField(min_value=0, max_value=365, default=7)
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_items(self, items):
        if items is not None and not items:
            raise serializers.ValidationError("Add at least one line item.")
        return items


class VerifySerializer(serializers.Serializer):
    razorpay_order_id = serializers.CharField(max_length=40)
    razorpay_payment_id = serializers.CharField(max_length=40)
    razorpay_signature = serializers.CharField(max_length=200)


class RefundSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01"), required=False
    )
