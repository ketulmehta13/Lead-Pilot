"""Customer churn: probability that a paying customer leaves.

Trained on IBM's Telco Customer Churn dataset. Money and product counts live on different
scales in Telco (USD per month, add-on services) and in our CRM (rupee deals), so they are
converted to percentile ranks *within each dataset*: "top 10% spender" means the same thing in
both. Shared features:

    tenure_months     months as a customer (absolute; both are months)
    monthly_value_pct percentile of average monthly spend
    total_value_pct   percentile of lifetime spend
    products_pct      percentile of products/services bought
    committed         on a longer-term commitment (Telco: 1-2 year contract;
                      CRM: repeat buyer or a deal currently in proposal/negotiation)
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from . import datasets
from .common import RANDOM_STATE, classification_metrics, save_artifact

NAME = "churn"
FEATURES = ["tenure_months", "monthly_value_pct", "total_value_pct", "products_pct", "committed"]
SERVICE_COLUMNS = [
    "PhoneService", "MultipleLines", "OnlineSecurity", "OnlineBackup", "DeviceProtection",
    "TechSupport", "StreamingTV", "StreamingMovies",
]  # fmt: skip


def percentile(series: pd.Series) -> pd.Series:
    """Rank in (0, 1]; ties share the average rank."""
    return series.rank(pct=True, method="average")


def to_features(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    df = raw.copy()
    # TotalCharges is blank for brand-new customers (tenure 0): they have paid nothing yet.
    df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce").fillna(0.0)
    services = (df[SERVICE_COLUMNS] == "Yes").sum(axis=1) + (df["InternetService"] != "No")
    X = pd.DataFrame(
        {
            "tenure_months": df["tenure"].astype(float),
            "monthly_value_pct": percentile(df["MonthlyCharges"]),
            "total_value_pct": percentile(df["TotalCharges"]),
            "products_pct": percentile(services),
            "committed": (df["Contract"] != "Month-to-month").astype(int),
        }
    )
    return X[FEATURES], (df["Churn"] == "Yes").astype(int)


def candidates(pos_weight: float) -> dict[str, Any]:
    return {
        "logistic_regression": LogisticRegression(max_iter=2000, class_weight="balanced"),
        "random_forest": RandomForestClassifier(
            n_estimators=300, min_samples_leaf=10, class_weight="balanced",
            random_state=RANDOM_STATE, n_jobs=-1,
        ),  # fmt: skip
        "xgboost": XGBClassifier(
            n_estimators=250, max_depth=3, learning_rate=0.05, subsample=0.9,
            scale_pos_weight=pos_weight, eval_metric="logloss", random_state=RANDOM_STATE,
            n_jobs=-1,
        ),  # fmt: skip
    }


def build(estimator) -> Pipeline:
    return Pipeline([("scale", StandardScaler()), ("model", estimator)])


def compare_models(X: pd.DataFrame, y: pd.Series, folds: int = 5) -> pd.DataFrame:
    pos_weight = float((y == 0).sum() / max((y == 1).sum(), 1))
    cv = StratifiedKFold(folds, shuffle=True, random_state=RANDOM_STATE)
    rows = []
    for name, est in candidates(pos_weight).items():
        s = cross_validate(build(est), X, y, cv=cv,
                           scoring=["roc_auc", "f1", "precision", "recall"])  # fmt: skip
        rows.append(
            {
                "model": name,
                **{f"cv_{m}": s[f"test_{m}"].mean() for m in ("roc_auc", "f1", "precision",
                                                               "recall")},  # fmt: skip
                "cv_roc_auc_std": s["test_roc_auc"].std(),
            }
        )
    return pd.DataFrame(rows).sort_values("cv_roc_auc", ascending=False).reset_index(drop=True)


def train(save: bool = True) -> dict[str, Any]:
    X, y = to_features(datasets.load_telco())
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE
    )
    comparison = compare_models(X_train, y_train)
    best = comparison.iloc[0]["model"]
    pos_weight = float((y_train == 0).sum() / (y_train == 1).sum())
    model = build(candidates(pos_weight)[best]).fit(X_train, y_train)
    test = classification_metrics(y_test, model.predict_proba(X_test)[:, 1])
    final = build(candidates(pos_weight)[best]).fit(X, y)
    metrics = {
        "task": "classification",
        "dataset": "IBM Telco Customer Churn",
        "rows": len(X),
        "positive_rate": float(y.mean()),
        "features": FEATURES,
        "chosen_model": best,
        "selection": "highest mean 5-fold CV ROC-AUC on the training split",
        "comparison": comparison.to_dict(orient="records"),
        "test": test,
    }
    if save:
        metrics = save_artifact(NAME, final, metrics)
    return metrics
