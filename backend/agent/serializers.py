from rest_framework import serializers

from .models import AgentRun, AgentStep


class AgentStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentStep
        fields = [
            "id", "order", "tool_name", "tool_input", "tool_output", "note",
            "requires_approval", "approved", "status", "decided_at", "created_at",
        ]  # fmt: skip


class AgentRunSerializer(serializers.ModelSerializer):
    steps = AgentStepSerializer(many=True, read_only=True)
    max_steps = serializers.SerializerMethodField()

    class Meta:
        model = AgentRun
        fields = [
            "id", "goal", "status", "final_summary", "error", "steps", "max_steps",
            "created_at", "updated_at", "finished_at",
        ]  # fmt: skip

    def get_max_steps(self, obj) -> int:
        from .agent import MAX_STEPS

        return MAX_STEPS


class AgentRunListSerializer(serializers.ModelSerializer):
    step_count = serializers.IntegerField(source="steps.count", read_only=True)

    class Meta:
        model = AgentRun
        fields = ["id", "goal", "status", "step_count", "created_at", "finished_at"]


class StartRunSerializer(serializers.Serializer):
    goal = serializers.CharField(min_length=5, max_length=1000, trim_whitespace=True)
