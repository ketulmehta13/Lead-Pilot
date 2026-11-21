"""ML services, APIs and the signals that keep scores fresh.

These use the trained models committed in ml/models/ (small files). Tests that need a
model to be *missing* point the loader at an empty directory.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from crm import services as crm_services
from crm.models import Contact, Deal, Lead
from ml import features, services
from ml.pipelines import common, forecast, lead_score, sentiment

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _fresh_models():
    services.reload_models()
    yield
    services.reload_models()


@pytest.fixture
def no_models(tmp_path, monkeypatch):
    """Simulate a fresh checkout where nothing has been trained."""
    monkeypatch.setattr(common, "MODELS_DIR", tmp_path)
    services.reload_models()


# --- Lead scoring ---------------------------------------------------------------------------


def test_lead_features_come_from_crm_activity(rep, contact_of):
    contact = contact_of(rep, tags=["unsubscribed"])
    lead = Lead.objects.create(owner=rep, contact=contact, source="referral")
    for kind in ("meeting", "call", "email", "note"):
        crm_services.log_activity(owner=rep, contact=contact, type=kind, subject=kind)
    row = features.lead_frame([lead]).loc[lead.id]
    assert row["source"] == "referral"
    assert row["touches"] == 4
    assert row["engagement_min"] == 12 + 6 + 2 + 0
    assert row["last_touch"] == "other"  # the note was logged last
    assert row["do_not_email"] == 1


def test_score_is_0_to_100_with_label_and_three_reasons(rep, lead_of):
    lead = lead_of(rep)
    scored = services.score_lead(lead)
    assert 0 <= scored.score <= 100
    assert scored.score_label == lead_score.label_for(scored.score)
    reasons = scored.score_explanation
    assert len(reasons) == 3
    assert {"feature", "label", "value", "impact", "direction"} <= set(reasons[0])
    assert abs(reasons[0]["impact"]) >= abs(reasons[-1]["impact"])  # strongest first


def test_engagement_raises_the_score(rep, contact_of):
    cold = Lead.objects.create(owner=rep, contact=contact_of(rep), source="cold")
    warm_contact = contact_of(rep)
    warm = Lead.objects.create(owner=rep, contact=warm_contact, source="referral")
    for _ in range(4):
        crm_services.log_activity(owner=rep, contact=warm_contact, type="meeting", subject="m")
    crm_services.log_activity(owner=rep, contact=warm_contact, type="call", subject="c")
    services.score_leads([cold, warm])
    cold.refresh_from_db()
    warm.refresh_from_db()
    assert warm.score > cold.score


def test_editing_a_lead_rescores_it(rep, lead_of, django_capture_on_commit_callbacks):
    lead = lead_of(rep)
    Lead.objects.filter(pk=lead.pk).update(score=None)
    with django_capture_on_commit_callbacks(execute=True):
        lead.notes = "Asked for a demo"
        lead.save()
    lead.refresh_from_db()
    assert lead.score is not None and lead.score_explanation


def test_logging_an_activity_rescores_the_contacts_leads(
    rep, lead_of, django_capture_on_commit_callbacks
):
    lead = lead_of(rep, source="cold")
    services.score_lead(lead)
    before = Lead.objects.get(pk=lead.pk).score
    with django_capture_on_commit_callbacks(execute=True):
        for _ in range(3):
            crm_services.log_activity(owner=rep, contact=lead.contact, type="meeting", subject="m")
    assert Lead.objects.get(pk=lead.pk).score != before


def test_score_lead_api_and_permissions(client_for, rep, other_rep, lead_of):
    lead = lead_of(rep)
    response = client_for(rep).post(f"/api/ml/score-lead/{lead.id}/")
    assert response.status_code == 200
    assert 0 <= response.json()["score"] <= 100
    assert client_for(other_rep).post(f"/api/ml/score-lead/{lead.id}/").status_code == 404


def test_missing_model_fails_gracefully(client_for, rep, lead_of, no_models):
    lead = lead_of(rep)
    assert services.score_lead(lead) is None
    lead.refresh_from_db()
    assert lead.score is None
    response = client_for(rep).post(f"/api/ml/score-lead/{lead.id}/")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "model_unavailable"
    # The CRM itself keeps working.
    assert (
        client_for(rep)
        .patch(f"/api/crm/leads/{lead.id}/", {"status": "qualified"}, format="json")
        .status_code
        == 200
    )


# --- Tickets --------------------------------------------------------------------------------


ANGRY = (
    "This is unacceptable! Your app has been down all morning, our team can't log in and we "
    "are losing customers. Fix it immediately or we will cancel our subscription."
)


def test_angry_ticket_is_negative_and_high_priority(client_for, support_user, contact_of, rep):
    response = client_for(support_user).post(
        "/api/support/tickets/",
        {"subject": "Everything is broken", "description": ANGRY, "contact": contact_of(rep).id},
        format="json",
    )
    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["sentiment"] == "negative"
    assert body["priority"] == "high"
    assert body["urgent"] is True
    assert body["sentiment_score"] < 0


def test_happy_ticket_is_positive_and_low_priority(client_for, support_user, contact_of, rep):
    body = (
        client_for(support_user)
        .post(
            "/api/support/tickets/",
            {
                "subject": "Thank you",
                "description": "Great product and excellent support, the team was wonderful.",
                "contact": contact_of(rep).id,
            },
            format="json",
        )
        .json()
    )
    assert body["sentiment"] == "positive" and body["priority"] == "low"


def test_classifier_rules():
    model = services.load_model("sentiment")
    (neutral_urgent,) = sentiment.classify(model, ["Please reset my password asap."])
    assert neutral_urgent["urgent"] and neutral_urgent["priority"] in ("medium", "high")
    assert sentiment.urgent_terms("We were charged twice, refund please") == [
        "charged twice", "refund",
    ]  # fmt: skip


def test_ticket_without_model_still_saves(client_for, support_user, contact_of, rep, no_models):
    response = client_for(support_user).post(
        "/api/support/tickets/",
        {"subject": "Hi", "description": ANGRY, "contact": contact_of(rep).id},
        format="json",
    )
    assert response.status_code == 201
    assert response.json()["sentiment"] is None and response.json()["priority"] == "medium"


# --- Segments, churn, forecast -------------------------------------------------------------


def _customer(user, contact, values, days_ago):
    for value, days in zip(values, days_ago, strict=True):
        deal = crm_services.create_deal(
            owner=user, contact=contact, title="d", stage="won", value=Decimal(value)
        )
        Deal.objects.filter(pk=deal.pk).update(closed_at=timezone.now() - timedelta(days=days))


def test_customer_insights_segment_and_churn(rep, contact_of):
    best = contact_of(rep)
    _customer(rep, best, ["900000", "800000", "700000"], [5, 40, 90])
    lapsed = contact_of(rep)
    _customer(rep, lapsed, ["50000"], [600])
    prospect = contact_of(rep)
    Contact.objects.filter(pk=prospect.pk).update(segment="Lost", churn_risk=0.9)  # stale

    result = services.refresh_customer_insights()
    assert result == {"customers": 2, "segmented": 2, "churn_scored": 2}
    best.refresh_from_db()
    lapsed.refresh_from_db()
    prospect.refresh_from_db()
    assert best.segment == "Champions"
    assert lapsed.segment in ("Lost", "At Risk")
    assert 0 <= best.churn_risk <= 1 and 0 <= lapsed.churn_risk <= 1
    assert best.churn_risk < lapsed.churn_risk
    assert prospect.segment is None and prospect.churn_risk is None


def test_winning_a_deal_refreshes_insights(rep, contact_of, django_capture_on_commit_callbacks):
    contact = contact_of(rep)
    deal = crm_services.create_deal(owner=rep, contact=contact, title="x", value=Decimal("1000"))
    with django_capture_on_commit_callbacks(execute=True):
        crm_services.move_deal(deal, stage="won", position=0, actor=rep)
    contact.refresh_from_db()
    assert contact.segment is not None and contact.churn_risk is not None


def test_forecast_needs_history_then_predicts_three_months(client_for, admin_user, rep, contact_of):
    assert client_for(admin_user).get("/api/ml/forecast/").json()["ok"] is False
    contact = contact_of(rep)
    _customer(rep, contact, ["100000"] * 18, [15 + 30 * i for i in range(18)])
    data = client_for(admin_user).get("/api/ml/forecast/").json()
    assert data["ok"] is True
    assert len(data["forecast"]) == 3
    for point in data["forecast"]:
        assert 0 <= point["lower"] <= point["forecast"] <= point["upper"]
    assert {m["method"] for m in data["methods"]} == set(forecast.METHODS)
    assert data["chosen"] == data["methods"][0]["method"]


def test_metrics_and_segments_endpoints(client_for, rep, support_user):
    data = client_for(rep).get("/api/ml/metrics/").json()
    assert data["available"]["lead_score"] is True
    assert data["models"]["lead_score"]["test"]["roc_auc"] > 0.7
    assert client_for(rep).get("/api/ml/segments/").status_code == 200
    assert client_for(support_user).get("/api/ml/metrics/").status_code == 403


def test_retrain_is_admin_only(client_for, rep):
    assert client_for(rep).post("/api/ml/retrain/", {}, format="json").status_code == 403
