from drf_spectacular.utils import extend_schema
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from common.permissions import IsAdminRole

from . import services
from .models import User
from .serializers import (
    AdminUserUpdateSerializer,
    ChangePasswordSerializer,
    LoginSerializer,
    ProfileSerializer,
    RegisterSerializer,
    SetPasswordSerializer,
    UserSerializer,
)


class LoginView(TokenObtainPairView):
    """POST username + password → access + refresh tokens and the user."""

    serializer_class = LoginSerializer
    # Slow down password guessing: LOGIN_RATE_LIMIT per IP (default 10/min).
    throttle_scope = "login"
    throttle_classes = [ScopedRateThrottle]


class MeView(APIView):
    """The signed-in user."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses=UserSerializer)
    def get(self, request: Request) -> Response:
        return Response(UserSerializer(request.user).data)

    @extend_schema(request=ProfileSerializer, responses=UserSerializer)
    def patch(self, request: Request) -> Response:
        serializer = ProfileSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = services.update_profile(request.user, serializer.validated_data)
        return Response(UserSerializer(user).data)


class ChangePasswordView(APIView):
    """Change your own password (the current one is required)."""

    permission_classes = [IsAuthenticated]
    throttle_scope = "login"  # same brute-force protection as login
    throttle_classes = [ScopedRateThrottle]

    @extend_schema(request=ChangePasswordSerializer, responses={204: None})
    def post(self, request: Request) -> Response:
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.change_password(request.user, **serializer.validated_data)
        return Response(status=status.HTTP_204_NO_CONTENT)


class RegisterView(generics.CreateAPIView):
    """Admins create users (there is no public sign-up)."""

    serializer_class = RegisterSerializer
    permission_classes = [IsAdminRole]

    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=201)


class UserViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Admins manage the team. Users are deactivated, never deleted.

    The list shows active users unless ?include_inactive=true (Settings > Team).
    """

    serializer_class = UserSerializer
    permission_classes = [IsAdminRole]
    queryset = User.objects.order_by("username")
    search_fields = ["username", "email", "first_name", "last_name"]
    filterset_fields = ["role", "is_active"]

    def get_queryset(self):
        qs = super().get_queryset()
        include = self.request.query_params.get("include_inactive", "").lower()
        if self.action == "list" and include not in {"1", "true", "yes"}:
            qs = qs.filter(is_active=True)
        return qs

    @extend_schema(request=AdminUserUpdateSerializer, responses=UserSerializer)
    def partial_update(self, request: Request, pk: str | None = None) -> Response:
        serializer = AdminUserUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = services.admin_update_user(
            request.user, self.get_object(), serializer.validated_data
        )
        return Response(UserSerializer(user).data)

    @extend_schema(request=SetPasswordSerializer, responses={204: None})
    @action(detail=True, methods=["post"], url_path="set-password")
    def set_password(self, request: Request, pk: str | None = None) -> Response:
        serializer = SetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.admin_set_password(
            request.user, self.get_object(), serializer.validated_data["password"]
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
