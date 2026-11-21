from django.db.models import Case, IntegerField, QuerySet, Value, When
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from common.viewsets import OwnerScopedViewSet

from . import services
from .filters import TicketFilter
from .models import Ticket
from .serializers import TicketCommentSerializer, TicketSerializer

PRIORITY_RANK = Case(
    When(priority=Ticket.Priority.HIGH, then=Value(0)),
    When(priority=Ticket.Priority.MEDIUM, then=Value(1)),
    default=Value(2),
    output_field=IntegerField(),
)


class TicketViewSet(OwnerScopedViewSet):
    """Support queue. Support + admin work every ticket; sales reps can read tickets for their
    own contacts. Default order: highest priority first, then newest."""

    queryset = (
        Ticket.objects.select_related("contact", "contact__company", "owner", "assigned_to")
        .annotate(priority_rank=PRIORITY_RANK)
        .order_by("priority_rank", "-created_at")
    )
    serializer_class = TicketSerializer
    filterset_class = TicketFilter
    allowed_roles = ("support",)
    read_only_roles = ("sales",)
    unscoped_read_roles = ("support",)
    search_fields = ["subject", "description", "contact__first_name", "contact__last_name"]
    ordering_fields = ["created_at", "priority_rank", "status", "sentiment_score"]

    def scope_queryset(self, queryset: QuerySet, user) -> QuerySet:
        return queryset.filter(contact__owner=user)

    def perform_create(self, serializer) -> None:
        serializer.instance = services.create_ticket(
            owner=self.request.user, **serializer.validated_data
        )

    def perform_update(self, serializer) -> None:
        serializer.instance = services.update_ticket(
            serializer.instance, **serializer.validated_data
        )

    @extend_schema(request=TicketCommentSerializer, responses=TicketCommentSerializer(many=True))
    @action(detail=True, methods=["get", "post"])
    def comments(self, request: Request, pk=None) -> Response:
        ticket = self.get_object()
        if request.method == "POST":
            serializer = TicketCommentSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            comment = services.add_comment(
                ticket, author=request.user, body=serializer.validated_data["body"]
            )
            return Response(TicketCommentSerializer(comment).data, status=status.HTTP_201_CREATED)
        return Response(TicketCommentSerializer(ticket.comments.all(), many=True).data)
