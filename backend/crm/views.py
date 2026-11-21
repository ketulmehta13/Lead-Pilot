from django.db.models import Count, Q, QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response

from common.viewsets import OwnerScopedViewSet

from . import services
from .filters import (
    ActivityFilter,
    CompanyFilter,
    ContactFilter,
    DealFilter,
    LeadFilter,
    TaskFilter,
)
from .models import Activity, Company, Contact, Deal, Lead, Task
from .serializers import (
    ActivitySerializer,
    BoardColumnSerializer,
    CompanySerializer,
    ContactImportResultSerializer,
    ContactSerializer,
    DealMoveSerializer,
    DealSerializer,
    LeadConvertSerializer,
    LeadSerializer,
    TaskSerializer,
)


class CompanyViewSet(OwnerScopedViewSet):
    # Meta.ordering is dropped in GROUP BY queries, so order explicitly.
    queryset = (
        Company.objects.select_related("owner")
        .annotate(contact_count=Count("contacts"))
        .order_by("name", "id")
    )
    serializer_class = CompanySerializer
    filterset_class = CompanyFilter
    search_fields = ["name", "website", "city"]
    ordering_fields = ["name", "industry", "city", "created_at", "contact_count"]


class ContactViewSet(OwnerScopedViewSet):
    queryset = Contact.objects.select_related("company", "owner")
    serializer_class = ContactSerializer
    filterset_class = ContactFilter
    # Support staff can look up any customer, but cannot change contacts.
    read_only_roles = ("support",)
    unscoped_read_roles = ("support",)
    search_fields = ["first_name", "last_name", "email", "phone", "company__name"]
    ordering_fields = ["first_name", "last_name", "email", "created_at", "churn_risk"]

    @extend_schema(
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {"file": {"type": "string", "format": "binary"}},
            }
        },
        responses={200: ContactImportResultSerializer},
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="import",
        parser_classes=[MultiPartParser, FormParser],
    )
    def import_csv(self, request: Request) -> Response:
        """Import contacts from a CSV file; returns per-row errors for skipped rows."""
        upload = request.FILES.get("file")
        if upload is None:
            raise serializers.ValidationError({"file": ["Upload a CSV file in the 'file' field."]})
        if not upload.name.lower().endswith(".csv"):
            raise serializers.ValidationError({"file": ["Only .csv files are accepted."]})
        try:
            result = services.import_contacts_csv(upload, owner=request.user)
        except services.CsvImportError as exc:
            raise serializers.ValidationError({"file": [str(exc)]}) from exc
        return Response(result.as_dict(), status=status.HTTP_200_OK)


class LeadViewSet(OwnerScopedViewSet):
    queryset = Lead.objects.select_related("contact", "contact__company", "owner", "deal")
    serializer_class = LeadSerializer
    filterset_class = LeadFilter
    search_fields = [
        "contact__first_name",
        "contact__last_name",
        "contact__email",
        "contact__company__name",
        "notes",
    ]
    ordering_fields = ["created_at", "budget", "score", "status", "last_contacted_at"]

    @extend_schema(request=LeadConvertSerializer, responses={201: DealSerializer})
    @action(detail=True, methods=["post"])
    def convert(self, request: Request, pk=None) -> Response:
        """Create a deal from this lead and mark the lead converted."""
        lead = self.get_object()
        params = LeadConvertSerializer(data=request.data)
        params.is_valid(raise_exception=True)
        try:
            deal = services.convert_lead(lead, **params.validated_data)
        except services.LeadAlreadyConverted as exc:
            raise serializers.ValidationError({"non_field_errors": [str(exc)]}) from exc
        return Response(
            DealSerializer(deal, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )


class DealViewSet(OwnerScopedViewSet):
    queryset = Deal.objects.select_related("contact", "contact__company", "owner")
    serializer_class = DealSerializer
    filterset_class = DealFilter
    search_fields = ["title", "contact__first_name", "contact__last_name", "contact__company__name"]
    ordering_fields = ["value", "expected_close_date", "created_at", "position", "closed_at"]

    def perform_create(self, serializer) -> None:
        serializer.instance = services.create_deal(
            owner=self.request.user, **serializer.validated_data
        )

    def perform_update(self, serializer) -> None:
        serializer.instance = services.update_deal(
            serializer.instance, actor=self.request.user, **serializer.validated_data
        )

    @extend_schema(responses=BoardColumnSerializer(many=True))
    @action(detail=False, methods=["get"], pagination_class=None)
    def board(self, request: Request) -> Response:
        """All visible deals grouped into Kanban columns (supports the same filters)."""
        deals = self.filter_queryset(self.get_queryset())
        columns = services.board_columns(deals)
        return Response(
            BoardColumnSerializer(columns, many=True, context=self.get_serializer_context()).data
        )

    @extend_schema(request=DealMoveSerializer, responses=DealSerializer)
    @action(detail=True, methods=["post"])
    def move(self, request: Request, pk=None) -> Response:
        """Drag-and-drop: set stage and position atomically."""
        deal = self.get_object()
        params = DealMoveSerializer(data=request.data)
        params.is_valid(raise_exception=True)
        deal = services.move_deal(
            deal, actor=request.user, visible=self.get_queryset(), **params.validated_data
        )
        return Response(self.get_serializer(deal).data)


class ActivityViewSet(OwnerScopedViewSet):
    """Activities power the contact timeline: GET /activities/?contact=<id>."""

    queryset = Activity.objects.select_related("contact", "owner")
    serializer_class = ActivitySerializer
    filterset_class = ActivityFilter
    search_fields = ["subject", "body"]
    ordering_fields = ["occurred_at", "created_at", "type"]

    def perform_create(self, serializer) -> None:
        serializer.instance = services.log_activity(
            owner=self.request.user, **serializer.validated_data
        )


class TaskViewSet(OwnerScopedViewSet):
    queryset = Task.objects.select_related("contact", "assigned_to", "owner")
    serializer_class = TaskSerializer
    filterset_class = TaskFilter
    search_fields = ["title", "description"]
    ordering_fields = ["due_date", "priority", "status", "created_at"]

    def scope_queryset(self, queryset: QuerySet, user) -> QuerySet:
        # Reps see tasks they created and tasks assigned to them.
        return queryset.filter(Q(owner=user) | Q(assigned_to=user))
