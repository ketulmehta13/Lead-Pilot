"""Pure pipeline logic (no trained models or datasets needed)."""

import pandas as pd
import pytest

from ml.pipelines import churn, forecast, lead_score, segment


@pytest.mark.parametrize(
    ("origin", "source", "expected"),
    [
        ("Lead Import", "Google", "cold"),
        ("Lead Add Form", "Reference", "event"),
        ("API", "Google", "ads"),
        ("API", "Reference", "referral"),
        ("Landing Page Submission", "Direct Traffic", "web"),
        ("API", "", "web"),
    ],
)
def test_x_education_source_mapping(origin, source, expected):
    assert lead_score.map_source(origin, source) == expected


@pytest.mark.parametrize(
    ("activity", "expected"),
    [
        ("SMS Sent", "call"),
        ("Had a Phone Conversation", "call"),
        ("Email Opened", "email"),
        ("Visited Booth in Tradeshow", "meeting"),
        ("Olark Chat Conversation", "other"),
        ("", "none"),
    ],
)
def test_x_education_last_touch_mapping(activity, expected):
    assert lead_score.map_last_touch(activity) == expected


def test_score_labels():
    assert [lead_score.label_for(s) for s in (95, 70, 69, 40, 39, 0)] == [
        "hot", "hot", "warm", "warm", "cold", "cold",
    ]  # fmt: skip


def test_rfm_scores_are_percentiles_with_recency_inverted():
    rfm = pd.DataFrame(
        {"recency_days": [1, 100, 365], "frequency": [10, 3, 1], "monetary": [5000, 500, 50]}
    )
    s = segment.rfm_scores(rfm)
    assert list(s["r_score"].round(3)) == [1.0, 0.667, 0.333]
    assert list(s["f_score"].round(3)) == [1.0, 0.667, 0.333]


def test_cluster_naming_from_centroids():
    centroids = pd.DataFrame(
        {
            "r_score": [0.9, 0.2, 0.7, 0.1],
            "f_score": [0.9, 0.7, 0.6, 0.1],
            "m_score": [0.9, 0.8, 0.5, 0.2],
        }
    )
    assert segment.name_clusters(centroids) == {
        0: "Champions", 1: "At Risk", 2: "Loyal", 3: "Lost",
    }  # fmt: skip


def test_churn_percentile_handles_ties():
    assert list(churn.percentile(pd.Series([1, 1, 2]))) == [0.5, 0.5, 1.0]


def test_monthly_series_fills_gaps():
    closed = pd.DataFrame(
        {
            "closed_at": pd.to_datetime(["2026-01-05", "2026-01-20", "2026-03-02"], utc=True),
            "value": [100.0, 50.0, 70.0],
        }
    )
    series = forecast.monthly_series(closed)
    assert [str(p) for p in series.index] == ["2026-01", "2026-02", "2026-03"]
    assert list(series) == [150.0, 0.0, 70.0]


def test_forecast_learns_a_trend():
    months = pd.period_range("2024-01", periods=24, freq="M")
    series = pd.Series([100.0 + 10 * i for i in range(24)], index=months)
    result = forecast.forecast(series)
    assert result["ok"]
    first = result["forecast"][0]
    assert first["month"] == "2026-01"
    assert first["forecast"] == pytest.approx(340.0, rel=0.05)
    assert result["forecast"][2]["upper"] - result["forecast"][2]["lower"] >= (
        result["forecast"][0]["upper"] - result["forecast"][0]["lower"]
    )  # band widens with horizon


def test_forecast_refuses_short_history():
    series = pd.Series([1.0] * 4, index=pd.period_range("2026-01", periods=4, freq="M"))
    assert forecast.forecast(series)["ok"] is False
