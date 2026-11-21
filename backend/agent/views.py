from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import RolePermission
from genai.views import GenAIThrottle

from . import agent, tasks
from .models import AgentRun, AgentStep
from .serializers import AgentRunListSerializer, AgentRunSerializer, StartRunSerializer


def _queue(run_id: int) -> None:
    transaction.on_commit(lambda: tasks.advance.delay(run_id))


class AgentRunViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Start a run with a goal, then poll it (GET /runs/<id>/) to watch its steps."""

    permission_classes = [RolePermission]
    allowed_roles = ("sales",)

    def get_queryset(self):
        runs = AgentRun.objects.prefetch_related("steps")
        return runs if self.request.user.is_admin else runs.filter(user=self.request.user)

    def get_serializer_class(self):
        return AgentRunListSerializer if self.action == "list" else AgentRunSerializer

    def get_throttles(self):
        return [GenAIThrottle()] if self.action == "create" else super().get_throttles()

    @extend_schema(request=StartRunSerializer, responses={201: AgentRunSerializer})
    def create(self, request: Request) -> Response:
        params = StartRunSerializer(data=request.data)
        params.is_valid(raise_exception=True)
        run = agent.start_run(request.user, params.validated_data["goal"])
        _queue(run.id)
        return Response(AgentRunSerializer(run).data, status=status.HTTP_201_CREATED)


class StepDecisionView(APIView):
    """POST /api/agent/steps/<id>/approve/ or /reject/ (only the run's owner or an admin)."""

    permission_classes = [RolePermission]
    allowed_roles = ("sales",)
    approve = True

    @extend_schema(request=None, responses=AgentRunSerializer)
    def post(self, request: Request, pk: int) -> Response:
        steps = AgentStep.objects.select_related("run")
        if not request.user.is_admin:
            steps = steps.filter(run__user=request.user)
        step = get_object_or_404(steps, pk=pk)
        try:
            run = agent.decide(step.id, request.user, approve=self.approve)
        except agent.AgentStateError as exc:
            raise serializers.ValidationError({"non_field_errors": [str(exc)]}) from exc
        if run.status == AgentRun.Status.PLANNING:
            _queue(run.id)
        run.refresh_from_db()
        return Response(AgentRunSerializer(run).data)
