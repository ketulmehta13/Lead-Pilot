from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import RolePermission

from .services import get_summary


class SummaryView(APIView):
    """Dashboard KPIs: leads by source, deals by stage, win rate, revenue, tasks due.

    Admins see company-wide numbers; sales reps see their own. Cached for 60 seconds and
    invalidated whenever leads, deals or tasks change.
    """

    permission_classes = [RolePermission]
    allowed_roles = ("sales",)

    @extend_schema(responses={200: OpenApiResponse(description="Dashboard summary")})
    def get(self, request: Request) -> Response:
        return Response(get_summary(request.user))
