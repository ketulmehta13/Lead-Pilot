from django.contrib import admin

from .models import Ticket, TicketComment


class CommentInline(admin.TabularInline):
    model = TicketComment
    extra = 0


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("subject", "contact", "status", "priority", "sentiment", "urgent", "created_at")
    list_filter = ("status", "priority", "sentiment", "urgent")
    search_fields = ("subject", "description")
    list_select_related = ("contact",)
    inlines = [CommentInline]
