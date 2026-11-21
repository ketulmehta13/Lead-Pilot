"""ML at runtime: load trained models, score CRM records, serve insights.

Every entry point degrades gracefully: if a model file is missing or broken, it logs a
warning and returns None / 0 instead of raising, so the CRM keeps working without ML.
"""

from __future__ import annotations

import functools
import json
import logging
from collections.abc import Iterable
from typing import Any

import joblib
import pandas as pd
from django.core.cache import cache
from django.db.models import QuerySet
from django.utils import timezone

from accounts.models import User
from crm.models import Contact, Deal, Lead

from . import features
from .pipelines import churn, lead_score, segment, sentiment
from .pipelines import forecast as forecast_pipeline
from .pipelines.common import metrics_path, model_path

logger = logging.getLogger(__name__)
MODEL_NAMES = ["lead_score", "churn", "segment", "sentiment", "forecast"]
FORECAST_CACHE_SECONDS = 3600


@functools.cache
def load_model(name: str) -> Any | None:
    """Load a model once per process. Missing or unreadable files -> None (logged)."""
    path = model_path(name)
    if not path.exists():
        logger.warning("ML model %s not found at %s; run `manage.py ml_train`", name, path)
        return None
    try:
        return joblib.load(path)
    except Exception:  # noqa: BLE001 - a corrupt model must not take the app down
        logger.exception("Could not load ML model %s", name)
        return None


def reload_models() -> None:
    load_model.cache_clear()


def model_status() -> dict[str, bool]:
    return {name: model_path(name).exists() for name in MODEL_NAMES}


# --- Lead scoring --------------------------------------------------------------------------


def score_leads(leads: Iterable[Lead]) -> int:
    """Score leads in one batch and save score, label and top-3 SHAP explanation.

    Uses bulk_update, so no post_save signals fire (no rescoring loops).
    Returns the number of leads scored (0 if the model is unavailable).
    """
    model = load_model("lead_score")
    leads = list(leads)
    if model is None or not leads:
        return 0
    X = features.lead_frame(leads)
    proba = model.predict_proba(X)[:, 1]
    explanations = lead_score.explain(model, X)
    by_id = {lead.id: lead for lead in leads}
    for lead_id, p, why in zip(X.index, proba, explanations, strict=True):
        lead = by_id[lead_id]
        lead.score = max(0, min(100, round(float(p) * 100)))
        lead.score_label = lead_score.label_for(lead.score)
        lead.score_explanation = why
    Lead.objects.bulk_update(leads, ["score", "score_label", "score_explanation"], batch_size=500)
    return len(leads)


def score_lead(lead: Lead) -> Lead | None:
    """Score one lead; returns it refreshed, or None if the model is unavailable."""
    if not score_leads([lead]):
        return None
    lead.refresh_from_db(fields=["score", "score_label", "score_explanation"])
    return lead


def rescore_all(queryset: QuerySet[Lead] | None = None) -> int:
    queryset = queryset if queryset is not None else Lead.objects.all()
    total = 0
    batch: list[Lead] = []
    for lead in queryset.only("id", "contact_id", "source").iterator(chunk_size=500):
        batch.append(lead)
        if len(batch) == 500:
            total += score_leads(batch)
            batch = []
    return total + score_leads(batch)


# --- Segments + churn ----------------------------------------------------------------------


def refresh_customer_insights() -> dict[str, int]:
    """Recompute segment and churn_risk for every customer (contact with a won deal).

    Non-customers get both fields cleared. Percentiles are relative to the whole customer
    base, so this always runs over everyone, not one contact.
    """
    seg_model, churn_model = load_model("segment"), load_model("churn")
    frame = features.customer_frame()
    result = {"customers": len(frame), "segmented": 0, "churn_scored": 0}
    if frame.empty:
        Contact.objects.exclude(segment=None, churn_risk=None).update(segment=None, churn_risk=None)
        return result

    contacts = list(Contact.objects.filter(id__in=frame.index).only("id", "segment", "churn_risk"))
    by_id = {c.id: c for c in contacts}
    if seg_model is not None:
        for cid, name in zip(frame.index, segment.assign(seg_model, frame), strict=True):
            by_id[cid].segment = name
        result["segmented"] = len(frame)
    if churn_model is not None:
        proba = churn_model.predict_proba(frame[churn.FEATURES])[:, 1]
        for cid, p in zip(frame.index, proba, strict=True):
            by_id[cid].churn_risk = round(float(p), 4)
        result["churn_scored"] = len(frame)
    Contact.objects.bulk_update(contacts, ["segment", "churn_risk"], batch_size=500)
    Contact.objects.exclude(id__in=frame.index).exclude(segment=None, churn_risk=None).update(
        segment=None, churn_risk=None
    )
    return result


def segment_summary(user: User) -> dict[str, Any]:
    """Customers per segment (scoped to the user) plus the trained model's profile."""
    contacts = Contact.objects.exclude(segment=None)
    if not user.is_admin:
        contacts = contacts.filter(owner=user)
    counts = {name: 0 for name in segment.SEGMENTS}
    churn_by_segment: dict[str, list[float]] = {name: [] for name in segment.SEGMENTS}
    for row in contacts.values("segment", "churn_risk"):
        counts[row["segment"]] = counts.get(row["segment"], 0) + 1
        if row["churn_risk"] is not None:
            churn_by_segment.setdefault(row["segment"], []).append(row["churn_risk"])
    trained = read_metrics("segment") or {}
    return {
        "segments": [
            {
                "segment": name,
                "customers": counts.get(name, 0),
                "avg_churn_risk": (
                    round(sum(v) / len(v), 3) if (v := churn_by_segment.get(name)) else None
                ),
            }
            for name in segment.SEGMENTS
        ],
        "training_profile": trained.get("profile", []),
        "silhouette": trained.get("silhouette"),
    }


# --- Tickets -------------------------------------------------------------------------------


def classify_ticket_text(text: str) -> dict[str, Any] | None:
    model = load_model("sentiment")
    if model is None:
        return None
    return sentiment.classify(model, [text])[0]


# --- Forecast ------------------------------------------------------------------------------


def _won_deals(user: User | None) -> pd.DataFrame:
    deals = Deal.objects.filter(stage=Deal.Stage.WON, closed_at__isnull=False)
    if user is not None and not user.is_admin:
        deals = deals.filter(owner=user)
    frame = pd.DataFrame(list(deals.values("closed_at", "value")), columns=["closed_at", "value"])
    frame["value"] = frame["value"].astype(float)
    return frame


def forecast_for(user: User) -> dict[str, Any]:
    """History + 3-month forecast with error band, for the user's won deals (admin: all)."""
    from analytics.services import VERSION_KEY

    version = cache.get(VERSION_KEY, 1)
    key = f"ml:forecast:v{version}:u{user.pk if not user.is_admin else 'all'}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    closed = _won_deals(user)
    series = forecast_pipeline.monthly_series(closed, end=pd.Timestamp(timezone.now()))
    result = forecast_pipeline.forecast(series)
    result.pop("model", None)
    cache.set(key, result, FORECAST_CACHE_SECONDS)
    return result


# --- Metrics + retraining ------------------------------------------------------------------


def read_metrics(name: str) -> dict[str, Any] | None:
    path = metrics_path(name)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception("Unreadable metrics file %s", path)
        return None


def all_metrics() -> dict[str, Any]:
    return {name: read_metrics(name) for name in MODEL_NAMES}


def retrain(models: list[str] | None = None) -> dict[str, Any]:
    """Retrain the given models (all by default), reload them and re-apply to the CRM."""
    from .pipelines import churn as churn_p
    from .pipelines import lead_score as lead_p
    from .pipelines import segment as segment_p
    from .pipelines import sentiment as sentiment_p

    trainers = {
        "lead_score": lead_p.train,
        "churn": churn_p.train,
        "segment": segment_p.train,
        "sentiment": sentiment_p.train,
        "forecast": lambda: forecast_pipeline.train(_won_deals(None)),
    }
    results: dict[str, Any] = {}
    for name in models or MODEL_NAMES:
        metrics = trainers[name]()
        results[name] = {
            "chosen_model": metrics.get("chosen_model"),
            "test": {
                k: v for k, v in (metrics.get("test") or {}).items() if k != "confusion_matrix"
            },
        }
    reload_models()
    results["applied"] = {
        "leads_scored": rescore_all(),
        **refresh_customer_insights(),
    }
    return results
