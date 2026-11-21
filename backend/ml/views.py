from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import APIException
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsAdminRole, RolePermission
from crm.models import Lead
from support.serializers import ClassifyTextSerializer

from . import services, tasks


class ModelUnavailable(APIException):
    status_code = 503
    default_code = "model_unavailable"
    default_detail = "This model hasn't been trained yet. An admin can run `manage.py ml_train`."


class SalesView(APIView):
    permission_classes = [RolePermission]
    allowed_roles = ("sales",)


class ScoreLeadView(SalesView):
    """Score one lead now (normally this happens automatically a moment after each edit)."""

    @extend_schema(request=None, responses={200: OpenApiResponse(description="Score")})
    def post(self, request: Request, pk: int) -> Response:
        leads = (
            Lead.objects.all() if request.user.is_admin else Lead.objects.filter(owner=request.user)
        )
        lead = get_object_or_404(leads, pk=pk)
        scored = services.score_lead(lead)
        if scored is None:
            raise ModelUnavailable()
        return Response(
            {
                "id": scored.id,
                "score": scored.score,
                "score_label": scored.score_label,
                "score_explanation": scored.score_explanation,
            }
        )


class MetricsView(SalesView):
    """Evaluation metrics for every model (as saved next to each .joblib)."""

    @extend_schema(responses={200: OpenApiResponse(description="Metrics per model")})
    def get(self, request: Request) -> Response:
        return Response({"available": services.model_status(), "models": services.all_metrics()})


class ForecastView(SalesView):
    """Monthly won revenue + next 3 months with an error band (admins: company-wide)."""

    @extend_schema(responses={200: OpenApiResponse(description="Forecast")})
    def get(self, request: Request) -> Response:
        return Response(services.forecast_for(request.user))


class SegmentsView(SalesView):
    """Customers per RFM segment with average churn risk."""

    @extend_schema(responses={200: OpenApiResponse(description="Segments")})
    def get(self, request: Request) -> Response:
        return Response(services.segment_summary(request.user))


class RetrainSerializer(serializers.Serializer):
    models = serializers.ListField(
        child=serializers.ChoiceField(choices=services.MODEL_NAMES), required=False
    )


class RetrainView(APIView):
    """Admin only: retrain models from the datasets and re-apply them to the CRM."""

    permission_classes = [IsAdminRole]

    @extend_schema(
        request=RetrainSerializer, responses={202: OpenApiResponse(description="Queued")}
    )
    def post(self, request: Request) -> Response:
        params = RetrainSerializer(data=request.data)
        params.is_valid(raise_exception=True)
        result = tasks.retrain.delay(params.validated_data.get("models"))
        body = {"status": "queued", "task_id": result.id}
        if result.ready():  # eager mode (no Redis): already finished
            body = {"status": "done", "result": result.get()}
        return Response(body, status=status.HTTP_202_ACCEPTED)


class RescoreAllView(APIView):
    """Admin only: recompute every lead score, segment and churn risk."""

    permission_classes = [IsAdminRole]

    @extend_schema(request=None, responses={202: OpenApiResponse(description="Queued")})
    def post(self, request: Request) -> Response:
        tasks.rescore_all.delay()
        tasks.refresh_customer_insights.delay()
        return Response({"status": "queued"}, status=status.HTTP_202_ACCEPTED)


class ClassifyTicketView(APIView):
    """Preview how a ticket text would be classified (sentiment, urgency, priority)."""

    permission_classes = [RolePermission]
    allowed_roles = ("support",)

    @extend_schema(request=ClassifyTextSerializer, responses={200: OpenApiResponse()})
    def post(self, request: Request) -> Response:
        params = ClassifyTextSerializer(data=request.data)
        params.is_valid(raise_exception=True)
        result = services.classify_ticket_text(params.validated_data["text"])
        if result is None:
            raise ModelUnavailable()
        return Response(result)
