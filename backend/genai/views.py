from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.exceptions import APIException
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from common.permissions import IsAdminRole, RolePermission
from crm.models import Activity, Contact
from crm.serializers import TaskSerializer

from . import llm, rag, services
from .models import Conversation, ConversationMessage, LLMCall


class GenAIThrottle(UserRateThrottle):
    """20 AI requests per minute per user (settings: DEFAULT_THROTTLE_RATES['genai'])."""

    scope = "genai"


class LLMInvalidOutput(APIException):
    status_code = 502
    default_code = "llm_invalid_output"
    default_detail = "The AI returned an invalid response. Please try again."


class LLMUnavailable(APIException):
    status_code = 503
    default_code = "llm_unavailable"
    default_detail = "The AI service is unavailable right now. Please try again shortly."


class LLMRefused(APIException):
    status_code = 422
    default_code = "llm_refused"
    default_detail = "The AI declined this request."


def run_llm(fn, *args, **kwargs):
    """Call a GenAI service and translate failures into clean API errors."""
    try:
        return fn(*args, **kwargs)
    except services.LLMOutputError as exc:
        raise LLMInvalidOutput(str(exc)) from exc
    except llm.LLMRefusal as exc:
        raise LLMRefused(str(exc)) from exc
    except llm.LLMError as exc:
        raise LLMUnavailable() from exc


class GenAIView(APIView):
    permission_classes = [RolePermission]
    allowed_roles = ("sales",)
    throttle_classes = [GenAIThrottle]


def scoped(queryset, user):
    return queryset if user.is_admin else queryset.filter(owner=user)


class DraftEmailSerializer(serializers.Serializer):
    contact_id = serializers.IntegerField()
    goal = serializers.CharField(max_length=500, allow_blank=True, required=False, default="")
    tone = serializers.ChoiceField(choices=services.TONES, default="friendly")


class EmailDraftSerializer(serializers.Serializer):
    subject = serializers.CharField()
    body = serializers.CharField()


class DraftEmailView(GenAIView):
    """Draft a personalised follow-up email from the contact's last 10 activities and deals."""

    @extend_schema(request=DraftEmailSerializer, responses=EmailDraftSerializer)
    def post(self, request: Request) -> Response:
        params = DraftEmailSerializer(data=request.data)
        params.is_valid(raise_exception=True)
        contact = get_object_or_404(
            scoped(Contact.objects.select_related("company"), request.user),
            pk=params.validated_data["contact_id"],
        )
        draft = run_llm(
            services.draft_email,
            contact,
            goal=params.validated_data["goal"],
            tone=params.validated_data["tone"],
            user=request.user,
        )
        return Response(draft.model_dump())


class SummarizeSerializer(serializers.Serializer):
    activity_id = serializers.IntegerField()


class SummarizeActivityView(GenAIView):
    """Summary + action items + sentiment for an activity (saved on the activity)."""

    @extend_schema(request=SummarizeSerializer, responses={200: OpenApiResponse()})
    def post(self, request: Request) -> Response:
        params = SummarizeSerializer(data=request.data)
        params.is_valid(raise_exception=True)
        activity = get_object_or_404(
            scoped(Activity.objects.select_related("contact"), request.user),
            pk=params.validated_data["activity_id"],
        )
        if len((activity.body or "").strip()) < 20:
            raise serializers.ValidationError({"activity_id": ["This activity has no notes."]})
        result = run_llm(services.summarize_activity, activity, user=request.user)
        return Response({"activity_id": activity.id, **result.model_dump()})


class ActionItemsToTasksSerializer(serializers.Serializer):
    activity_id = serializers.IntegerField()
    items = serializers.ListField(child=serializers.IntegerField(min_value=0), min_length=1)


class ActionItemsToTasksView(APIView):
    """Create tasks from the chosen action items of a summarized activity (no LLM call)."""

    permission_classes = [RolePermission]
    allowed_roles = ("sales",)

    @extend_schema(request=ActionItemsToTasksSerializer, responses=TaskSerializer(many=True))
    def post(self, request: Request) -> Response:
        params = ActionItemsToTasksSerializer(data=request.data)
        params.is_valid(raise_exception=True)
        activity = get_object_or_404(
            scoped(Activity.objects.select_related("contact", "deal"), request.user),
            pk=params.validated_data["activity_id"],
        )
        if not (activity.action_items or {}).get("items"):
            raise serializers.ValidationError({"activity_id": ["Summarize the activity first."]})
        tasks = services.tasks_from_action_items(
            activity, params.validated_data["items"], user=request.user
        )
        return Response(
            TaskSerializer(tasks, many=True, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class StatusView(APIView):
    """Which LLM provider is active (so the UI can say when it's in offline mode)."""

    permission_classes = [RolePermission]
    allowed_roles = ("sales", "support")

    @extend_schema(responses={200: OpenApiResponse()})
    def get(self, request: Request) -> Response:
        provider = llm.provider_name()
        return Response(
            {"configured": llm.is_configured(), "provider": provider,
             "model": llm.model_name(provider)}  # fmt: skip
        )


class UsageView(APIView):
    """Admin: LLM calls and tokens per feature (from the token usage log)."""

    permission_classes = [IsAdminRole]

    @extend_schema(responses={200: OpenApiResponse()})
    def get(self, request: Request) -> Response:
        rows = (
            LLMCall.objects.values("purpose", "status")
            .annotate(calls=Count("id"), prompt_tokens=Sum("prompt_tokens"),
                      completion_tokens=Sum("completion_tokens"))  # fmt: skip
            .order_by("purpose", "status")
        )
        return Response(list(rows))


# --- Ask LeadPilot (RAG) ----------------------------------------------------------------------


class AskSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=1000, trim_whitespace=True)
    conversation_id = serializers.IntegerField(required=False, allow_null=True)


class AskView(APIView):
    """Answer a question from the user's own CRM records, with citations to the sources."""

    permission_classes = [RolePermission]
    allowed_roles = ("sales", "support")
    throttle_classes = [GenAIThrottle]

    @extend_schema(request=AskSerializer, responses={200: OpenApiResponse()})
    def post(self, request: Request) -> Response:
        params = AskSerializer(data=request.data)
        params.is_valid(raise_exception=True)
        conversation = None
        if params.validated_data.get("conversation_id"):
            conversation = get_object_or_404(
                Conversation, pk=params.validated_data["conversation_id"], user=request.user
            )
        result = run_llm(rag.answer, params.validated_data["question"], request.user, conversation)
        return Response(result)


class ConversationMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConversationMessage
        fields = ["id", "role", "content", "citations", "created_at"]


class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = ["id", "title", "created_at", "updated_at"]


class ConversationDetailSerializer(ConversationSerializer):
    messages = ConversationMessageSerializer(many=True, read_only=True)

    class Meta(ConversationSerializer.Meta):
        fields = [*ConversationSerializer.Meta.fields, "messages"]


class ConversationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Your Ask LeadPilot chat history (each user only sees their own)."""

    permission_classes = [RolePermission]
    allowed_roles = ("sales", "support")

    def get_queryset(self):
        return Conversation.objects.filter(user=self.request.user).prefetch_related("messages")

    def get_serializer_class(self):
        return ConversationDetailSerializer if self.action == "retrieve" else ConversationSerializer
