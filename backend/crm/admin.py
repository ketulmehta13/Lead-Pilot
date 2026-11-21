from django.contrib import admin

from .models import Activity, Company, Contact, Deal, Lead, Task


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "industry", "size", "city", "owner")
    list_filter = ("industry", "size")
    search_fields = ("name", "city")


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "email", "company", "segment", "owner")
    list_filter = ("segment",)
    search_fields = ("first_name", "last_name", "email")
    list_select_related = ("company", "owner")


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("contact", "source", "status", "budget", "score", "score_label", "owner")
    list_filter = ("source", "status", "score_label")
    search_fields = ("contact__first_name", "contact__last_name", "contact__email")
    list_select_related = ("contact", "owner")


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ("subject", "type", "contact", "occurred_at", "owner")
    list_filter = ("type",)
    search_fields = ("subject", "body")
    list_select_related = ("contact", "owner")


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "priority", "due_date", "assigned_to", "created_by_agent")
    list_filter = ("status", "priority", "created_by_agent")
    search_fields = ("title",)


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = ("title", "stage", "value", "probability", "expected_close_date", "owner")
    list_filter = ("stage",)
    search_fields = ("title", "contact__first_name", "contact__last_name")
    list_select_related = ("contact", "owner")
