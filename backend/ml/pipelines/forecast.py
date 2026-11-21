"""Sales forecast: next 3 months of won-deal revenue.

Input is our own CRM: a monthly series of won-deal value. Candidates:

    linear_regression           lags 1-3 + linear trend + month-of-year (sin/cos)
    trend_seasonal_regression   trend + month-of-year only (fewer parameters)
    ridge_regression            all features, standardized, L2-regularized
    naive                       next month = this month                     (baseline)
    moving_average              next month = mean of the last 3 months      (baseline)

All are scored in a rolling-origin backtest over the last BACKTEST_MONTHS months: each month is
predicted only from the months before it, so nothing peeks into the future. The method with
the lowest backtest RMSE produces the forecast. On short, noisy histories a baseline can win;
that is reported honestly rather than hidden.

The error band is +/- 1.96 x the chosen method's backtest RMSE (~95% if errors are roughly
normal), widened by sqrt(h) for h months ahead.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .common import save_artifact

NAME = "forecast"
LAGS = 3
HORIZON = 3
BACKTEST_MONTHS = 9
MIN_MONTHS = LAGS + BACKTEST_MONTHS + 3  # enough rows to fit before the first backtest month
FEATURES = [f"lag{i}" for i in range(1, LAGS + 1)] + ["t", "sin", "cos"]

REGRESSIONS: dict[str, tuple[Callable[[], Any], list[str]]] = {
    "linear_regression": (LinearRegression, FEATURES),
    "trend_seasonal_regression": (LinearRegression, ["t", "sin", "cos"]),
    "ridge_regression": (lambda: make_pipeline(StandardScaler(), Ridge(alpha=3.0)), FEATURES),
}
BASELINES = ["naive", "moving_average"]
METHODS = [*REGRESSIONS, *BASELINES]


def monthly_series(closed: pd.DataFrame, end: pd.Timestamp | None = None) -> pd.Series:
    """Revenue per month from rows with columns closed_at, value. Missing months -> 0."""
    if closed.empty:
        return pd.Series(dtype=float)
    month = pd.to_datetime(closed["closed_at"], utc=True).dt.tz_localize(None).dt.to_period("M")
    series = closed.assign(month=month).groupby("month")["value"].sum().astype(float)
    if end is not None:
        end = pd.Timestamp(end)
        last = (end.tz_localize(None) if end.tzinfo else end).to_period("M")
    else:
        last = series.index.max()
    full = pd.period_range(series.index.min(), last, freq="M")
    return series.reindex(full, fill_value=0.0)


def design(series: pd.Series) -> pd.DataFrame:
    """Lag, trend and seasonality features for each month that has LAGS months of history."""
    df = pd.DataFrame({"y": series.values}, index=series.index)
    for lag in range(1, LAGS + 1):
        df[f"lag{lag}"] = df["y"].shift(lag)
    df["t"] = np.arange(len(df))
    months = np.array([p.month for p in series.index])
    df["sin"] = np.sin(2 * np.pi * months / 12)
    df["cos"] = np.cos(2 * np.pi * months / 12)
    return df.dropna()


def _next_row(history: pd.Series) -> pd.DataFrame:
    """Feature row for the month right after `history`."""
    month = (history.index[-1] + 1).month
    values = {f"lag{lag}": float(history.iloc[-lag]) for lag in range(1, LAGS + 1)}
    values.update(
        t=len(history),  # design()'s t is the month's index in the full series
        sin=np.sin(2 * np.pi * month / 12),
        cos=np.cos(2 * np.pi * month / 12),
    )
    return pd.DataFrame([values])[FEATURES]


def _fit(method: str, history: pd.Series) -> Any:
    if method in BASELINES:
        return None
    make, cols = REGRESSIONS[method]
    train = design(history)
    return make().fit(train[cols], train["y"])


def _predict_next(method: str, model: Any, history: pd.Series) -> float:
    if method == "naive":
        return float(history.iloc[-1])
    if method == "moving_average":
        return float(history.iloc[-3:].mean())
    cols = REGRESSIONS[method][1]
    return max(float(model.predict(_next_row(history)[cols])[0]), 0.0)


def backtest(series: pd.Series, months: int = BACKTEST_MONTHS) -> pd.DataFrame:
    """One-step-ahead predictions of every method for the last `months` months."""
    rows = []
    for i in range(len(series) - months, len(series)):
        history = series.iloc[:i]
        if len(design(history)) < 4:
            continue
        row = {"month": str(series.index[i]), "actual": float(series.iloc[i])}
        for method in METHODS:
            row[method] = _predict_next(method, _fit(method, history), history)
        rows.append(row)
    return pd.DataFrame(rows)


def score_methods(bt: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for method in METHODS:
        rows.append(
            {
                "method": method,
                "mae": mean_absolute_error(bt["actual"], bt[method]),
                "rmse": float(np.sqrt(mean_squared_error(bt["actual"], bt[method]))),
                "r2": r2_score(bt["actual"], bt[method]) if len(bt) > 1 else float("nan"),
            }
        )
    return pd.DataFrame(rows).sort_values("rmse").reset_index(drop=True)


def forecast(series: pd.Series, horizon: int = HORIZON) -> dict[str, Any]:
    """Backtest every method, then forecast `horizon` months with the lowest-RMSE one."""
    if len(series) < MIN_MONTHS:
        return {
            "ok": False,
            "reason": f"Need at least {MIN_MONTHS} months of won deals (have {len(series)}).",
        }
    bt = backtest(series)
    methods = score_methods(bt)
    chosen = str(methods.iloc[0]["method"])
    rmse = float(methods.iloc[0]["rmse"])

    model = _fit(chosen, series)
    history = series.copy()
    points = []
    for h in range(1, horizon + 1):
        value = _predict_next(chosen, model, history)
        period = history.index[-1] + 1
        band = 1.96 * rmse * np.sqrt(h)
        points.append(
            {
                "month": str(period),
                "forecast": round(value, 2),
                "lower": round(max(value - band, 0.0), 2),
                "upper": round(value + band, 2),
            }
        )
        history = pd.concat([history, pd.Series([value], index=[period])])
    return {
        "ok": True,
        "chosen": chosen,
        "history": [{"month": str(p), "revenue": round(float(v), 2)} for p, v in series.items()],
        "forecast": points,
        "backtest": bt.round(2).to_dict(orient="records"),
        "methods": methods.to_dict(orient="records"),
        "model": model,
    }


def train(closed: pd.DataFrame, save: bool = True) -> dict[str, Any]:
    """Backtest + fit on CRM won deals (`closed`: columns closed_at, value)."""
    series = monthly_series(closed, end=pd.Timestamp.now())
    result = forecast(series)
    if not result["ok"]:
        return {"task": "regression", "ok": False, "reason": result["reason"]}
    best = result["methods"][0]
    metrics = {
        "task": "regression",
        "dataset": "LeadPilot won deals (monthly revenue)",
        "rows": len(series),
        "features": FEATURES,
        "chosen_model": result["chosen"],
        "selection": (
            f"lowest RMSE in a rolling-origin backtest over the last {BACKTEST_MONTHS} months, "
            "regressions vs naive and 3-month moving-average baselines"
        ),
        "test": {"mae": best["mae"], "rmse": best["rmse"], "r2": best["r2"]},
        "comparison": result["methods"],
        "backtest": result["backtest"],
    }
    if save:
        metrics = save_artifact(
            NAME, {"method": result["chosen"], "model": result["model"]}, metrics
        )
    return metrics
