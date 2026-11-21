from drf_spectacular.utils import extend_schema
from rest_framework import generics, mixins, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from common.permissions import IsAdminRole

from .models import User
from .serializers import LoginSerializer, RegisterSerializer, UserSerializer


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
    """Admins list users (e.g. to assign tasks or review the team)."""

    serializer_class = UserSerializer
    permission_classes = [IsAdminRole]
    queryset = User.objects.filter(is_active=True).order_by("username")
    search_fields = ["username", "email", "first_name", "last_name"]
    filterset_fields = ["role"]
