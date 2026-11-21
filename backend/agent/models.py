"""CRM agent: a run (one goal) made of logged steps (tool calls)."""

from django.conf import settings
from django.db import models


class AgentRun(models.Model):
    class Status(models.TextChoices):
        PLANNING = "planning", "Planning"
        AWAITING_APPROVAL = "awaiting_approval", "Awaiting approval"
        RUNNING = "running", "Running"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    ACTIVE = (Status.PLANNING, Status.RUNNING)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agent_runs"
    )
    goal = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNING)
    # Full LLM conversation (neutral message format, see genai/llm.py) so a paused run can resume.
    messages = models.JSONField(default=list, blank=True)
    final_summary = models.TextField(blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Run {self.pk}: {self.goal[:50]}"


class AgentStep(models.Model):
    class Status(models.TextChoices):
        DONE = "done", "Done"
        PENDING_APPROVAL = "pending_approval", "Waiting for approval"
        REJECTED = "rejected", "Rejected"
        FAILED = "failed", "Failed"

    run = models.ForeignKey(AgentRun, on_delete=models.CASCADE, related_name="steps")
    order = models.PositiveSmallIntegerField()
    tool_name = models.CharField(max_length=60)
    tool_call_id = models.CharField(max_length=120)
    tool_input = models.JSONField(default=dict, blank=True)
    tool_output = models.JSONField(null=True, blank=True)
    # What the model said alongside the call (its plan / reasoning text, if any).
    note = models.TextField(blank=True)
    requires_approval = models.BooleanField(default=False)
    approved = models.BooleanField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DONE)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["run", "order"]
        constraints = [
            models.UniqueConstraint(fields=["run", "order"], name="agent_step_unique_order")
        ]

    def __str__(self) -> str:
        return f"{self.run_id}.{self.order} {self.tool_name}"
