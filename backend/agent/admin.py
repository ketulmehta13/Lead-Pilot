from django.contrib import admin

from .models import AgentRun, AgentStep


class StepInline(admin.TabularInline):
    model = AgentStep
    extra = 0
    fields = ("order", "tool_name", "status", "requires_approval", "approved")
    readonly_fields = fields


@admin.register(AgentRun)
class AgentRunAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "goal", "created_at")
    list_filter = ("status",)
    inlines = [StepInline]
