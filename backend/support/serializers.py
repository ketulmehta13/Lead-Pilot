from rest_framework import serializers

from accounts.models import User
from common.serializers import OwnedModelSerializer
from crm.models import Contact

from .models import Ticket, TicketComment


class TicketCommentSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()

    class Meta:
        model = TicketComment
        fields = ["id", "body", "author", "author_name", "created_at"]
        read_only_fields = ["author", "created_at"]

    def get_author_name(self, obj: TicketComment) -> str | None:
        a = obj.author
        return (a.get_full_name() or a.username) if a else None


class TicketSerializer(OwnedModelSerializer):
    # Support staff work on every customer's tickets, so any contact may be linked.
    contact = serializers.PrimaryKeyRelatedField(queryset=Contact.objects.all())
    contact_name = serializers.CharField(source="contact.full_name", read_only=True)
    company_name = serializers.CharField(
        source="contact.company.name", read_only=True, default=None
    )
    assigned_to = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True, role__in=["admin", "support"]),
        allow_null=True,
        required=False,
    )
    assigned_to_name = serializers.SerializerMethodField()
    comment_count = serializers.IntegerField(source="comments.count", read_only=True)

    class Meta:
        model = Ticket
        fields = [
            "id", "subject", "description", "contact", "contact_name", "company_name",
            "status", "priority", "priority_overridden", "sentiment", "sentiment_score",
            "urgent", "assigned_to", "assigned_to_name", "resolved_at", "comment_count",
            "owner", "owner_name", "created_at", "updated_at",
        ]  # fmt: skip
        read_only_fields = [
            "priority_overridden", "sentiment", "sentiment_score", "urgent", "resolved_at",
        ]  # fmt: skip
        extra_kwargs = {"priority": {"required": False}}

    def get_assigned_to_name(self, obj: Ticket) -> str | None:
        u = obj.assigned_to
        return (u.get_full_name() or u.username) if u else None


class ClassifyTextSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=10_000)
