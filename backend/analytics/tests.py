from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.cache import cache
from django.utils import timezone

from analytics import services
from crm import services as crm_services
from crm.models import Deal, Task

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()


def make_deal(user, contact, stage, value, closed_days_ago=None):
    deal = crm_services.create_deal(
        owner=user, contact=contact, title="d", stage=stage, value=Decimal(value)
    )
    if closed_days_ago is not None:
        Deal.objects.filter(pk=deal.pk).update(
            closed_at=timezone.now() - timedelta(days=closed_days_ago)
        )
    return deal


def test_summary_matches_manual_counts(client_for, rep, other_rep, contact_of, lead_of):
    contact = contact_of(rep)
    lead_of(rep, contact=contact, source="web")
    lead_of(rep, contact=contact, source="web")
    lead_of(rep, contact=contact, source="ads", status="converted")
    lead_of(other_rep, source="web")  # not rep's

    make_deal(rep, contact, "new", "1000")
    make_deal(rep, contact, "proposal", "3000")
    make_deal(rep, contact, "won", "5000", closed_days_ago=0)
    make_deal(rep, contact, "won", "7000", closed_days_ago=400)  # outside the 12-month trend
    make_deal(rep, contact, "lost", "9000", closed_days_ago=0)

    today = timezone.localdate()
    Task.objects.create(owner=rep, assigned_to=rep, title="today", due_date=today)
    Task.objects.create(owner=rep, assigned_to=rep, title="late", due_date=today - timedelta(1))
    Task.objects.create(
        owner=rep, assigned_to=rep, title="done", due_date=today, status=Task.Status.DONE
    )

    data = client_for(rep).get("/api/analytics/summary/").json()

    by_source = {r["source"]: r["count"] for r in data["leads_by_source"]}
    assert by_source == {"web": 2, "referral": 0, "ads": 1, "event": 0, "cold": 0}
    by_stage = {r["stage"]: (r["count"], Decimal(str(r["value"]))) for r in data["deals_by_stage"]}
    assert by_stage["won"] == (2, Decimal("12000"))
    assert by_stage["new"] == (1, Decimal("1000"))
    assert data["win_rate"] == round(100 * 2 / 3, 1)
    assert Decimal(str(data["revenue_this_month"])) == Decimal("5000")
    assert data["tasks_due_today"] == 1
    assert data["tasks_overdue"] == 1
    assert data["totals"]["leads"] == 3
    assert data["totals"]["open_leads"] == 2
    assert data["totals"]["open_deals"] == 2
    assert Decimal(str(data["totals"]["pipeline_value"])) == Decimal("4000")
    # 1000*10% + 3000*50%
    assert Decimal(str(data["totals"]["weighted_pipeline_value"])) == Decimal("1600")

    trend = data["revenue_trend"]
    assert len(trend) == 12
    assert trend[-1]["month"] == today.strftime("%Y-%m")
    assert Decimal(str(trend[-1]["revenue"])) == Decimal("5000")
    assert sum(Decimal(str(m["revenue"])) for m in trend) == Decimal("5000")


def test_admin_sees_everyone(client_for, admin_user, rep, other_rep, lead_of):
    lead_of(rep)
    lead_of(other_rep)
    assert client_for(admin_user).get("/api/analytics/summary/").json()["totals"]["leads"] == 2


def test_win_rate_is_null_without_closed_deals(client_for, rep):
    assert client_for(rep).get("/api/analytics/summary/").json()["win_rate"] is None


def test_support_and_anonymous_are_blocked(client_for, support_user):
    assert client_for(support_user).get("/api/analytics/summary/").status_code == 403
    assert client_for(None).get("/api/analytics/summary/").status_code == 401


def test_summary_is_cached_but_invalidated_by_crm_changes(rep, lead_of, django_assert_num_queries):
    lead_of(rep)
    first = services.get_summary(rep)
    with django_assert_num_queries(0):
        services.get_summary(rep)  # served from cache

    lead_of(rep)  # post_save signal bumps the cache version
    assert services.get_summary(rep)["totals"]["leads"] == first["totals"]["leads"] + 1


def test_moving_a_deal_refreshes_dashboard(rep, contact_of):
    contact = contact_of(rep)
    deal = make_deal(rep, contact, "negotiation", "8000")
    assert services.get_summary(rep)["revenue_this_month"] == Decimal("0")
    crm_services.move_deal(deal, stage="won", position=0, actor=rep)
    assert services.get_summary(rep)["revenue_this_month"] == Decimal("8000")


def test_revenue_trend_fills_empty_months(rep):
    trend = services.compute_summary(rep)["revenue_trend"]
    assert len(trend) == 12 and all(m["revenue"] == 0 for m in trend)
    months = [m["month"] for m in trend]
    assert months == sorted(months) and len(set(months)) == 12
