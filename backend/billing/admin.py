from django.contrib import admin

from .models import Invoice, InvoiceItem, Payment, WebhookEvent


class ItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ("razorpay_payment_id", "amount", "method", "status", "refunded_amount")
    fields = readonly_fields


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "contact", "total", "status", "paid_at", "owner")
    list_filter = ("status",)
    search_fields = ("number", "contact__first_name", "contact__last_name")
    inlines = [ItemInline, PaymentInline]


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ("event_id", "event_type", "processed", "received_at")
    list_filter = ("event_type", "processed")
