import django_filters
from django.db.models import Q

from .models import Activity, Company, Contact, Lead, Task


class CompanyFilter(django_filters.FilterSet):
    city = django_filters.CharFilter(lookup_expr="iexact")

    class Meta:
        model = Company
        fields = ["industry", "size", "city"]


class ContactFilter(django_filters.FilterSet):
    tag = django_filters.CharFilter(method="filter_tag", label="Has tag")
    has_company = django_filters.BooleanFilter(
        field_name="company", lookup_expr="isnull", exclude=True
    )

    class Meta:
        model = Contact
        fields = ["company", "segment"]

    def filter_tag(self, queryset, name, value):
        # Matches the quoted JSON string, so "vip" does not match "vip-old".
        return queryset.filter(tags__icontains=f'"{value.strip().lower()}"')


class LeadFilter(django_filters.FilterSet):
    budget_min = django_filters.NumberFilter(field_name="budget", lookup_expr="gte")
    budget_max = django_filters.NumberFilter(field_name="budget", lookup_expr="lte")
    not_contacted_since = django_filters.IsoDateTimeFilter(method="filter_not_contacted_since")

    class Meta:
        model = Lead
        fields = ["status", "source", "score_label", "contact"]

    def filter_not_contacted_since(self, queryset, name, value):
        return queryset.filter(Q(last_contacted_at__lt=value) | Q(last_contacted_at__isnull=True))


class ActivityFilter(django_filters.FilterSet):
    occurred_after = django_filters.IsoDateTimeFilter(field_name="occurred_at", lookup_expr="gte")
    occurred_before = django_filters.IsoDateTimeFilter(field_name="occurred_at", lookup_expr="lte")

    class Meta:
        model = Activity
        fields = ["contact", "type"]


class TaskFilter(django_filters.FilterSet):
    due_before = django_filters.DateFilter(field_name="due_date", lookup_expr="lte")
    due_after = django_filters.DateFilter(field_name="due_date", lookup_expr="gte")
    open = django_filters.BooleanFilter(method="filter_open", label="Open (not done)")

    def filter_open(self, queryset, name, value):
        done = Task.Status.DONE
        return queryset.exclude(status=done) if value else queryset.filter(status=done)

    class Meta:
        model = Task
        fields = ["status", "priority", "contact", "assigned_to", "created_by_agent"]
