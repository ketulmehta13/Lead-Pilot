"""CRM -> model feature mapping.

Each model was trained on a public dataset mapped to a small shared feature space
(see the docstrings in ml/pipelines/*). These functions compute the *same* columns from
LeadPilot records so the trained models can score our data.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

import pandas as pd
from django.db.models import Count, Max, Min, OuterRef, Q, Subquery, Sum
from django.utils import timezone

from crm.models import Activity, Contact, Deal, Lead

from .pipelines import churn, lead_score, segment

# Minutes of engagement credited per activity type. X Education measures time on site; a
# meeting is the strongest buying signal we log, an email the weakest. Kept within X Ed's
# range (median ~4 min, p95 ~26 min) so a few interactions land in a realistic band.
ENGAGEMENT_MINUTES = {"meeting": 12.0, "call": 6.0, "email": 2.0, "note": 0.0}
LAST_TOUCH = {"call": "call", "email": "email", "meeting": "meeting", "note": "other"}
NO_EMAIL_TAGS = {"do-not-email", "unsubscribed", "no-email"}
DAYS_PER_MONTH = 30.44


def lead_frame(leads: Iterable[Lead]) -> pd.DataFrame:
    """Lead-scoring features for `leads`, indexed by lead id (columns = lead_score.FEATURES)."""
    leads = list(leads)
    if not leads:
        return pd.DataFrame(columns=lead_score.FEATURES)
    contact_ids = {lead.contact_id for lead in leads}

    counts: dict[int, dict[str, int]] = defaultdict(dict)
    for row in (
        Activity.objects.filter(contact_id__in=contact_ids)
        .values("contact_id", "type")
        .annotate(n=Count("id"))
        .order_by()
    ):
        counts[row["contact_id"]][row["type"]] = row["n"]

    latest = Activity.objects.filter(contact=OuterRef("pk")).order_by("-occurred_at", "-id")
    contacts = {
        c.id: c
        for c in Contact.objects.filter(id__in=contact_ids).annotate(
            last_type=Subquery(latest.values("type")[:1])
        )
    }

    rows = []
    for lead in leads:
        c = contacts[lead.contact_id]
        by_type = counts.get(lead.contact_id, {})
        tags = {t.lower() for t in (c.tags or [])}
        rows.append(
            {
                "id": lead.id,
                "source": lead.source,
                "last_touch": LAST_TOUCH.get(c.last_type or "", "none"),
                "touches": float(sum(by_type.values())),
                "engagement_min": float(
                    sum(ENGAGEMENT_MINUTES.get(t, 0) * n for t, n in by_type.items())
                ),
                "do_not_email": int(bool(tags & NO_EMAIL_TAGS)),
            }
        )
    return pd.DataFrame(rows).set_index("id")[lead_score.FEATURES]


def customer_frame() -> pd.DataFrame:
    """One row per *customer* (contact with at least one won deal), indexed by contact id.

    Columns: raw RFM (recency_days, frequency, monetary), RFM percentile scores
    (segment.FEATURES) and churn features (churn.FEATURES). Percentiles are computed within
    our customer base, matching how the models were trained.
    """
    now = timezone.now()
    won = Q(deals__stage=Deal.Stage.WON)
    rows = list(
        Contact.objects.filter(won)
        .annotate(
            last_won=Max("deals__closed_at", filter=won),
            first_won=Min("deals__closed_at", filter=won),
            n_won=Count("deals", filter=won, distinct=True),
            total=Sum("deals__value", filter=won),
            n_active=Count(
                "deals",
                filter=Q(deals__stage__in=[Deal.Stage.PROPOSAL, Deal.Stage.NEGOTIATION]),
                distinct=True,
            ),
        )
        .values("id", "last_won", "first_won", "n_won", "total", "n_active")
    )
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).set_index("id")
    df["total"] = df["total"].astype(float)
    df["recency_days"] = [(now - d).days if d else 9999 for d in df["last_won"]]
    df["frequency"] = df["n_won"]
    df["monetary"] = df["total"]
    tenure = [max((now - d).days / DAYS_PER_MONTH, 1.0) if d else 1.0 for d in df["first_won"]]
    df["tenure_months"] = tenure
    df = df.join(segment.rfm_scores(df[["recency_days", "frequency", "monetary"]]))
    df["monthly_value_pct"] = churn.percentile(df["total"] / df["tenure_months"])
    df["total_value_pct"] = churn.percentile(df["total"])
    df["products_pct"] = churn.percentile(df["n_won"])
    df["committed"] = ((df["n_won"] >= 2) | (df["n_active"] > 0)).astype(int)
    return df
