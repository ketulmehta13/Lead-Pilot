import django_filters
from django.db.models import Q

from .models import Ticket


class TicketFilter(django_filters.FilterSet):
    open = django_filters.BooleanFilter(method="filter_open", label="Open or in progress")

    class Meta:
        model = Ticket
        fields = ["status", "priority", "sentiment", "urgent", "contact", "assigned_to"]

    def filter_open(self, queryset, name, value):
        active = Q(status__in=[Ticket.Status.OPEN, Ticket.Status.IN_PROGRESS])
        return queryset.filter(active) if value else queryset.exclude(active)
