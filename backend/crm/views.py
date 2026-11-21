from django.db.models import Count, Q, QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response

from common.viewsets import OwnerScopedViewSet

from . import services
from .filters import ActivityFilter, CompanyFilter, ContactFilter, LeadFilter, TaskFilter
from .models import Activity, Company, Contact, Lead, Task
from .serializers import (
    ActivitySerializer,
    CompanySerializer,
    ContactImportResultSerializer,
    ContactSerializer,
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
    queryset = Lead.objects.select_related("contact", "contact__company", "owner")
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
