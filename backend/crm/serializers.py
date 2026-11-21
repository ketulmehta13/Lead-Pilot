from rest_framework import serializers

from accounts.models import User
from common.serializers import OwnedModelSerializer, OwnedRelatedField

from .models import Activity, Company, Contact, Deal, Lead, Task


class CompanySerializer(OwnedModelSerializer):
    contact_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Company
        fields = [
            "id", "name", "industry", "size", "website", "city", "contact_count",
            "owner", "owner_name", "created_at", "updated_at",
        ]  # fmt: skip


class ContactSerializer(OwnedModelSerializer):
    company = OwnedRelatedField(queryset=Company.objects.all(), allow_null=True, required=False)
    company_name = serializers.CharField(source="company.name", read_only=True, default=None)
    full_name = serializers.CharField(read_only=True)
    tags = serializers.ListField(
        child=serializers.CharField(max_length=40), required=False, max_length=20
    )

    class Meta:
        model = Contact
        fields = [
            "id", "first_name", "last_name", "full_name", "email", "phone", "company",
            "company_name", "tags", "segment", "churn_risk", "owner", "owner_name",
            "created_at", "updated_at",
        ]  # fmt: skip
        read_only_fields = ["segment", "churn_risk"]

    def validate_email(self, value: str) -> str:
        value = value.strip().lower()
        clash = Contact.objects.filter(email__iexact=value)
        if self.instance is not None:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError("A contact with this email already exists.")
        return value

    def validate_tags(self, value: list[str]) -> list[str]:
        # Trim, drop blanks and duplicates, keep order.
        return list(dict.fromkeys(t.strip().lower() for t in value if t.strip()))


class LeadSerializer(OwnedModelSerializer):
    contact = OwnedRelatedField(queryset=Contact.objects.all())
    contact_name = serializers.CharField(source="contact.full_name", read_only=True)
    contact_email = serializers.EmailField(source="contact.email", read_only=True)
    company_name = serializers.CharField(
        source="contact.company.name", read_only=True, default=None
    )
    deal = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = [
            "id", "contact", "contact_name", "contact_email", "company_name", "source",
            "status", "budget", "notes", "score", "score_label", "score_explanation",
            "last_contacted_at", "deal", "owner", "owner_name", "created_at", "updated_at",
        ]  # fmt: skip
        read_only_fields = ["score", "score_label", "score_explanation", "last_contacted_at"]

    def get_deal(self, obj: Lead) -> int | None:
        """Id of the deal this lead was converted into, if any."""
        deal = getattr(obj, "deal", None)  # reverse one-to-one; missing -> None
        return deal.id if deal else None

    def validate_budget(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Budget cannot be negative.")
        return value


class ActivitySerializer(OwnedModelSerializer):
    contact = OwnedRelatedField(queryset=Contact.objects.all())
    contact_name = serializers.CharField(source="contact.full_name", read_only=True)
    deal = OwnedRelatedField(queryset=Deal.objects.all(), allow_null=True, required=False)

    class Meta:
        model = Activity
        fields = [
            "id", "type", "subject", "body", "contact", "contact_name", "deal", "summary",
            "action_items", "occurred_at", "owner", "owner_name", "created_at", "updated_at",
        ]  # fmt: skip
        read_only_fields = ["summary", "action_items"]


class TaskSerializer(OwnedModelSerializer):
    contact = OwnedRelatedField(queryset=Contact.objects.all(), allow_null=True, required=False)
    contact_name = serializers.CharField(source="contact.full_name", read_only=True, default=None)
    deal = OwnedRelatedField(queryset=Deal.objects.all(), allow_null=True, required=False)
    assigned_to = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True), allow_null=True, required=False
    )
    assigned_to_name = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            "id", "title", "description", "due_date", "status", "priority", "assigned_to",
            "assigned_to_name", "contact", "contact_name", "deal", "created_by_agent", "owner",
            "owner_name", "created_at", "updated_at",
        ]  # fmt: skip
        read_only_fields = ["created_by_agent"]

    def get_assigned_to_name(self, obj: Task) -> str | None:
        user = obj.assigned_to
        return (user.get_full_name() or user.username) if user else None

    def validate_assigned_to(self, value: User | None) -> User | None:
        request = self.context.get("request")
        if value and request and not request.user.is_admin and value != request.user:
            raise serializers.ValidationError("You can only assign tasks to yourself.")
        return value

    def create(self, validated_data: dict) -> Task:
        validated_data.setdefault("assigned_to", self.context["request"].user)
        return super().create(validated_data)


class DealSerializer(OwnedModelSerializer):
    contact = OwnedRelatedField(queryset=Contact.objects.all())
    contact_name = serializers.CharField(source="contact.full_name", read_only=True)
    company_name = serializers.CharField(
        source="contact.company.name", read_only=True, default=None
    )
    probability = serializers.IntegerField(min_value=0, max_value=100, required=False)

    class Meta:
        model = Deal
        fields = [
            "id", "title", "contact", "contact_name", "company_name", "lead", "value", "stage",
            "expected_close_date", "probability", "position", "closed_at", "owner",
            "owner_name", "created_at", "updated_at",
        ]  # fmt: skip
        read_only_fields = ["lead", "position", "closed_at"]

    def validate_value(self, value):
        if value < 0:
            raise serializers.ValidationError("Value cannot be negative.")
        return value


class DealMoveSerializer(serializers.Serializer):
    """Drop target on the Kanban board."""

    stage = serializers.ChoiceField(choices=Deal.Stage.choices)
    position = serializers.IntegerField(
        min_value=0, help_text="Index in the target column, as the user sees it (0 = top)."
    )


class BoardColumnSerializer(serializers.Serializer):
    stage = serializers.CharField()
    label = serializers.CharField()
    count = serializers.IntegerField()
    total_value = serializers.DecimalField(max_digits=14, decimal_places=2)
    deals = DealSerializer(many=True)


class LeadConvertSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200, required=False, allow_blank=True)
    value = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=0, required=False, allow_null=True
    )
    stage = serializers.ChoiceField(
        choices=[s for s in Deal.Stage.choices if s[0] not in Deal.CLOSED_STAGES],
        default=Deal.Stage.QUALIFIED,
    )
    expected_close_date = serializers.DateField(required=False, allow_null=True)


class ContactImportRowSerializer(serializers.Serializer):
    """One row of a contacts CSV import."""

    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    company = serializers.CharField(max_length=200, required=False, allow_blank=True)
    tags = serializers.CharField(required=False, allow_blank=True)


class ContactImportResultSerializer(serializers.Serializer):
    """Response of the CSV import endpoint (used for API docs)."""

    total_rows = serializers.IntegerField()
    created = serializers.IntegerField()
    errors = serializers.ListField(child=serializers.DictField())
