from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsAdminRole, RolePermission

from . import razorpay_service as rzp
from . import services
from .models import Invoice, Payment
from .serializers import (
    InvoiceCreateSerializer,
    InvoiceSerializer,
    PaymentSerializer,
    RefundSerializer,
    VerifySerializer,
)


class PaymentsUnavailable(APIException):
    status_code = 503
    default_code = "payments_unavailable"
    default_detail = "Payments are not configured. Add Razorpay TEST keys to the backend .env."


class PaymentGatewayError(APIException):
    status_code = 502
    default_code = "payment_gateway_error"
    default_detail = "Razorpay rejected the request. Please try again."


def billing_call(fn, *args, **kwargs):
    """Run a billing service and translate failures into clean API errors."""
    try:
        return fn(*args, **kwargs)
    except rzp.RazorpayNotConfigured as exc:
        raise PaymentsUnavailable(str(exc)) from exc
    except rzp.RazorpayError as exc:
        raise PaymentGatewayError(str(exc)) from exc
    except services.BillingError as exc:
        raise serializers.ValidationError({"non_field_errors": [str(exc)]}) from exc


def invoice_queryset():
    return Invoice.objects.select_related(
        "deal", "contact", "contact__company", "owner"
    ).prefetch_related("items", Prefetch("payments", Payment.objects.order_by("-created_at")))


class InvoiceViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Invoices for Won deals. Sales reps see their own; admins see all."""

    permission_classes = [RolePermission]
    allowed_roles = ("sales",)
    serializer_class = InvoiceSerializer
    filterset_fields = ["status", "deal", "contact"]
    search_fields = ["number", "contact__first_name", "contact__last_name", "deal__title"]
    ordering_fields = ["created_at", "total", "paid_at", "number"]

    def get_queryset(self):
        user = self.request.user
        invoices = invoice_queryset()
        return invoices if user.is_admin else invoices.filter(owner=user)

    @extend_schema(request=InvoiceCreateSerializer, responses={201: InvoiceSerializer})
    def create(self, request: Request) -> Response:
        params = InvoiceCreateSerializer(data=request.data, context={"request": request})
        params.is_valid(raise_exception=True)
        data = params.validated_data
        invoice = billing_call(
            services.create_invoice,
            data["deal"],
            owner=request.user,
            items=data.get("items"),
            due_in_days=data["due_in_days"],
            notes=data["notes"],
        )
        return Response(
            InvoiceSerializer(invoice_queryset().get(pk=invoice.pk)).data,
            status=status.HTTP_201_CREATED,
        )

    def perform_destroy(self, instance: Invoice) -> None:
        if instance.status != Invoice.Status.DRAFT:
            raise serializers.ValidationError(
                {"non_field_errors": ["Only draft invoices can be deleted."]}
            )
        instance.delete()

    @extend_schema(request=None, responses={200: OpenApiResponse(description="Checkout options")})
    @action(detail=True, methods=["post"], url_path="create-order")
    def create_order(self, request: Request, pk=None) -> Response:
        """Create a Razorpay order; returns key_id + order_id for Checkout.js (no secrets)."""
        return Response(billing_call(services.start_checkout, self.get_object()))

    @extend_schema(request=None, responses=InvoiceSerializer)
    @action(detail=True, methods=["post"], url_path="payment-link")
    def payment_link(self, request: Request, pk=None) -> Response:
        """Create a Razorpay Payment Link that Razorpay emails to the customer."""
        invoice = billing_call(services.create_payment_link, self.get_object())
        return Response(InvoiceSerializer(invoice_queryset().get(pk=invoice.pk)).data)


class VerifyPaymentView(APIView):
    """Checkout.js success handler posts here; we verify the signature (status: processing).
    The webhook later confirms the payment and marks the invoice paid."""

    permission_classes = [RolePermission]
    allowed_roles = ("sales",)

    @extend_schema(request=VerifySerializer, responses=InvoiceSerializer)
    def post(self, request: Request) -> Response:
        params = VerifySerializer(data=request.data)
        params.is_valid(raise_exception=True)
        d = params.validated_data
        owned = Invoice.objects.filter(razorpay_order_id=d["razorpay_order_id"])
        if not request.user.is_admin:
            owned = owned.filter(owner=request.user)
        if not owned.exists():
            raise serializers.ValidationError({"non_field_errors": ["Unknown order."]})
        invoice = billing_call(
            services.confirm_checkout,
            d["razorpay_order_id"],
            d["razorpay_payment_id"],
            d["razorpay_signature"],
        )
        return Response(InvoiceSerializer(invoice_queryset().get(pk=invoice.pk)).data)


class WebhookView(APIView):
    """Razorpay webhooks: no login, but X-Razorpay-Signature must match. Idempotent."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(request=None, responses={200: OpenApiResponse(), 400: OpenApiResponse()})
    def post(self, request: Request) -> Response:
        body = request.body  # raw bytes: the signature covers the exact body
        try:
            outcome, event = services.handle_webhook(
                body,
                request.headers.get("X-Razorpay-Signature", ""),
                request.headers.get("X-Razorpay-Event-Id", ""),
            )
        except services.BillingError as exc:
            return Response(
                {"error": {"code": "invalid_webhook", "message": str(exc), "details": None}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"status": outcome, "event": event.event_id})


class RefundView(APIView):
    """Admin only: refund a captured payment (full amount by default)."""

    permission_classes = [IsAdminRole]

    @extend_schema(request=RefundSerializer, responses=PaymentSerializer)
    def post(self, request: Request, pk: int) -> Response:
        payment = get_object_or_404(Payment.objects.select_related("invoice"), pk=pk)
        params = RefundSerializer(data=request.data)
        params.is_valid(raise_exception=True)
        payment = billing_call(
            services.refund_payment,
            payment,
            actor=request.user,
            amount=params.validated_data.get("amount"),
        )
        return Response(PaymentSerializer(payment).data)


class ConfigView(APIView):
    """Razorpay config for the frontend: the key id only, never the secret."""

    permission_classes = [RolePermission]
    allowed_roles = ("sales",)

    @extend_schema(responses={200: OpenApiResponse()})
    def get(self, request: Request) -> Response:
        return Response(
            {"configured": rzp.is_configured(), "key_id": rzp.key_id(), "test_mode": True}
        )
