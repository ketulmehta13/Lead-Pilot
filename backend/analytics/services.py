"""Dashboard aggregates.

Results are cached for 60 s per user. Any save/delete of a Lead, Deal or Task bumps a global
version number (see signals.py), so the next request recomputes instead of showing stale data.
"""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from django.core.cache import cache
from django.db.models import Count, Q, QuerySet, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from accounts.models import User
from crm.models import Deal, Lead, Task

CACHE_SECONDS = 60
VERSION_KEY = "analytics:summary:version"
OPEN_STAGES = [s for s in Deal.Stage.values if s not in Deal.CLOSED_STAGES]


def invalidate_summary_cache() -> None:
    """Make every cached dashboard summary stale (cheap: bumps one counter)."""
    try:
        cache.incr(VERSION_KEY)
    except ValueError:  # key missing
        cache.set(VERSION_KEY, 2, None)


def _scoped(queryset: QuerySet, user: User) -> QuerySet:
    return queryset if user.is_admin else queryset.filter(owner=user)


def _scoped_tasks(user: User) -> QuerySet[Task]:
    tasks = Task.objects.all()
    return tasks if user.is_admin else tasks.filter(Q(owner=user) | Q(assigned_to=user))


def _month_start(day: date) -> datetime:
    return timezone.make_aware(datetime.combine(day.replace(day=1), time.min))


def _shift_months(day: date, months: int) -> date:
    index = day.year * 12 + (day.month - 1) + months
    return date(index // 12, index % 12 + 1, 1)


def revenue_by_month(deals: QuerySet[Deal], months: int = 12) -> list[dict[str, Any]]:
    """Won-deal value per calendar month for the last `months` months, oldest first.

    Months with no wins are included with 0 so charts have a continuous axis.
    """
    today = timezone.localdate()
    first = _shift_months(today, -(months - 1))
    rows = (
        deals.filter(stage=Deal.Stage.WON, closed_at__gte=_month_start(first))
        .annotate(month=TruncMonth("closed_at"))
        .values("month")
        .annotate(revenue=Sum("value"), deals=Count("id"))
    )
    found = {
        (r["month"].date() if isinstance(r["month"], datetime) else r["month"]).replace(day=1): r
        for r in rows
    }
    series = []
    for i in range(months):
        month = _shift_months(first, i)
        row = found.get(month)
        series.append(
            {
                "month": month.strftime("%Y-%m"),
                "revenue": row["revenue"] if row else Decimal("0"),
                "deals": row["deals"] if row else 0,
            }
        )
    return series


def compute_summary(user: User) -> dict[str, Any]:
    """All dashboard numbers for `user` (admins see everyone's data)."""
    leads = _scoped(Lead.objects.all(), user)
    deals = _scoped(Deal.objects.all(), user)
    tasks = _scoped_tasks(user).exclude(status=Task.Status.DONE)
    today = timezone.localdate()

    leads_by_source = {s: 0 for s in Lead.Source.values}
    for row in leads.values("source").annotate(count=Count("id")):
        leads_by_source[row["source"]] = row["count"]

    stage_rows = {
        r["stage"]: r for r in deals.values("stage").annotate(count=Count("id"), value=Sum("value"))
    }
    deals_by_stage = [
        {
            "stage": stage,
            "label": Deal.Stage(stage).label,
            "count": stage_rows.get(stage, {}).get("count", 0),
            "value": stage_rows.get(stage, {}).get("value") or Decimal("0"),
        }
        for stage in Deal.Stage.values
    ]

    won = stage_rows.get(Deal.Stage.WON, {}).get("count", 0)
    lost = stage_rows.get(Deal.Stage.LOST, {}).get("count", 0)
    win_rate = round(100 * won / (won + lost), 1) if won + lost else None

    open_deals = deals.filter(stage__in=OPEN_STAGES)
    trend = revenue_by_month(deals)
    month_start = _month_start(today)

    return {
        "generated_at": timezone.now().isoformat(),
        "totals": {
            "leads": leads.count(),
            "open_leads": leads.filter(
                status__in=[Lead.Status.NEW, Lead.Status.CONTACTED, Lead.Status.QUALIFIED]
            ).count(),
            "open_deals": open_deals.count(),
            "pipeline_value": open_deals.aggregate(v=Sum("value"))["v"] or Decimal("0"),
            "weighted_pipeline_value": sum(
                (d.value * d.probability / 100 for d in open_deals.only("value", "probability")),
                Decimal("0"),
            ).quantize(Decimal("0.01")),
        },
        "leads_by_source": [
            {"source": s, "label": Lead.Source(s).label, "count": c}
            for s, c in leads_by_source.items()
        ],
        "deals_by_stage": deals_by_stage,
        "win_rate": win_rate,
        "revenue_this_month": deals.filter(
            stage=Deal.Stage.WON, closed_at__gte=month_start
        ).aggregate(v=Sum("value"))["v"]
        or Decimal("0"),
        "revenue_trend": trend,
        "tasks_due_today": tasks.filter(due_date=today).count(),
        "tasks_overdue": tasks.filter(due_date__lt=today).count(),
    }


def get_summary(user: User) -> dict[str, Any]:
    """Cached `compute_summary`."""
    version = cache.get_or_set(VERSION_KEY, 1, None)
    key = f"analytics:summary:v{version}:u{user.pk}"
    data = cache.get(key)
    if data is None:
        data = compute_summary(user)
        cache.set(key, data, CACHE_SECONDS)
    return data
