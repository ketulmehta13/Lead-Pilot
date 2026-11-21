from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("invoices", views.InvoiceViewSet, basename="invoice")

urlpatterns = [
    path("verify/", views.VerifyPaymentView.as_view(), name="billing-verify"),
    path("webhook/", views.WebhookView.as_view(), name="billing-webhook"),
    path("payments/<int:pk>/refund/", views.RefundView.as_view(), name="billing-refund"),
    path("config/", views.ConfigView.as_view(), name="billing-config"),
    *router.urls,
]
