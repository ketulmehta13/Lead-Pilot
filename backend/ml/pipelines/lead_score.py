"""Lead scoring: probability that a lead converts.

Trained on the public X Education dataset, mapped onto features our CRM can also compute
(see `ml/features.py` for the CRM side). The same five columns feed both:

    source            web / referral / ads / event / cold
    touches           number of interactions (X Ed: TotalVisits; CRM: activities logged)
    engagement_min    minutes of engagement (X Ed: time on site; CRM: weighted activity time)
    last_touch        email / call / meeting / other / none
    do_not_email      contact opted out of email
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

from . import datasets
from .common import RANDOM_STATE, classification_metrics, save_artifact

NAME = "lead_score"
CATEGORICAL = ["source", "last_touch"]
NUMERIC = ["touches", "engagement_min", "do_not_email"]
FEATURES = CATEGORICAL + NUMERIC
FEATURE_LABELS = {
    "source": "Lead source",
    "last_touch": "Last interaction",
    "touches": "Number of interactions",
    "engagement_min": "Engagement time",
    "do_not_email": "Opted out of email",
}
HOT, WARM = 70, 40  # score thresholds for labels

# --- X Education -> shared feature space ----------------------------------------------------

_ADS = {"google", "bing", "facebook", "pay per click ads", "social media", "youtubechannel"}
_REFERRAL = {"reference", "referral sites"}
_CALL = {"sms sent", "had a phone conversation", "approached upfront"}
_EMAIL = {
    "email opened", "email link clicked", "email bounced", "email received",
    "view in browser link clicked", "email marked spam", "unsubscribed", "resubscribed to emails",
}  # fmt: skip
_MEETING = {"visited booth in tradeshow"}
_NONE = {"", "unreachable"}


def map_source(origin: str, source: str) -> str:
    """X Education origin/source -> our CRM's lead source choices."""
    origin, source = (origin or "").strip().lower(), (source or "").strip().lower()
    if origin == "lead import":
        return "cold"  # bought/imported lists
    if origin == "lead add form":
        return "event"  # leads typed in from offline forms (events, walk-ins)
    if source in _ADS:
        return "ads"
    if source in _REFERRAL:
        return "referral"
    return "web"  # direct, organic, chat widget, own websites


def map_last_touch(activity: str) -> str:
    a = (activity or "").strip().lower()
    if a in _CALL:
        return "call"
    if a in _EMAIL:
        return "email"
    if a in _MEETING:
        return "meeting"
    if a in _NONE:
        return "none"
    return "other"  # page visits, forms, chat widget


def to_features(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Clean X Education and map it to the shared feature columns."""
    df = raw.copy()
    X = pd.DataFrame(
        {
            "source": [
                map_source(o, s)
                for o, s in zip(df["Lead Origin"], df["Lead Source"].fillna(""), strict=True)
            ],
            "last_touch": df["Last Activity"].fillna("").map(map_last_touch),
            # A handful of bots visit hundreds of times: cap the long tail.
            "touches": df["TotalVisits"].clip(upper=30),
            "engagement_min": (df["Total Time Spent on Website"] / 60).round(2),
            "do_not_email": (df["Do Not Email"].str.strip().str.lower() == "yes").astype(int),
        }
    )
    return X[FEATURES], df["Converted"].astype(int)


# --- Models ---------------------------------------------------------------------------------


def preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        [
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
            (
                "num",
                Pipeline(
                    [("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]
                ),
                NUMERIC,
            ),
        ]
    )


def candidates(pos_weight: float) -> dict[str, Any]:
    """Three model families; each handles the ~38% / 62% imbalance with class weights."""
    return {
        "logistic_regression": LogisticRegression(max_iter=2000, class_weight="balanced"),
        "random_forest": RandomForestClassifier(
            n_estimators=300, min_samples_leaf=5, class_weight="balanced",
            random_state=RANDOM_STATE, n_jobs=-1,
        ),  # fmt: skip
        "xgboost": XGBClassifier(
            n_estimators=300, max_depth=4, learning_rate=0.05, subsample=0.9,
            colsample_bytree=0.9, scale_pos_weight=pos_weight, eval_metric="logloss",
            random_state=RANDOM_STATE, n_jobs=-1,
        ),  # fmt: skip
    }


def build(estimator) -> Pipeline:
    return Pipeline([("prep", preprocessor()), ("model", estimator)])


def compare_models(X: pd.DataFrame, y: pd.Series, folds: int = 5) -> pd.DataFrame:
    """Stratified k-fold CV for every candidate; sorted by ROC-AUC."""
    pos_weight = float((y == 0).sum() / max((y == 1).sum(), 1))
    cv = StratifiedKFold(folds, shuffle=True, random_state=RANDOM_STATE)
    rows = []
    for name, est in candidates(pos_weight).items():
        scores = cross_validate(build(est), X, y, cv=cv, scoring=["roc_auc", "f1", "precision",
                                "recall"], n_jobs=1)  # fmt: skip
        rows.append(
            {
                "model": name,
                **{f"cv_{m}": scores[f"test_{m}"].mean() for m in ("roc_auc", "f1", "precision",
                                                                    "recall")},  # fmt: skip
                "cv_roc_auc_std": scores["test_roc_auc"].std(),
            }
        )
    return pd.DataFrame(rows).sort_values("cv_roc_auc", ascending=False).reset_index(drop=True)


def train(save: bool = True) -> dict[str, Any]:
    """Compare models with CV, pick the best by ROC-AUC, evaluate on a held-out 20% test set,
    refit on all data and save. Returns the metrics dict."""
    X, y = to_features(datasets.load_leads())
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
        "dataset": "X Education lead scoring",
        "rows": len(X),
        "positive_rate": float(y.mean()),
        "features": FEATURES,
        "chosen_model": best,
        "selection": "highest mean 5-fold CV ROC-AUC on the training split",
        "comparison": comparison.to_dict(orient="records"),
        "test": test,
        "thresholds": {"hot": HOT, "warm": WARM},
    }
    if save:
        metrics = save_artifact(NAME, final, metrics)
    return metrics


# --- Scoring + explanations (used by ml.services at runtime) --------------------------------


def label_for(score: int) -> str:
    return "hot" if score >= HOT else "warm" if score >= WARM else "cold"


def _feature_groups(prep: ColumnTransformer) -> list[str]:
    """Map each transformed column back to its original feature name."""
    groups = []
    for name, transformer, cols in prep.transformers_:
        if name == "cat":
            for col, cats in zip(cols, transformer.categories_, strict=True):
                groups += [col] * len(cats)
        elif name == "num":
            groups += list(cols)
    return groups


def contributions(model: Pipeline, X: pd.DataFrame) -> np.ndarray:
    """Per-feature contribution to each prediction (log-odds), shape (rows, len(FEATURES)).

    XGBoost: exact TreeSHAP via the booster's `pred_contribs` (no `shap` import needed at
    runtime). Logistic regression: coef * standardized value. Random forest: `shap`'s
    TreeExplainer. One-hot columns are summed back into their source feature.
    """
    prep, est = model.named_steps["prep"], model.named_steps["model"]
    Xt = prep.transform(X)
    Xt = Xt.toarray() if hasattr(Xt, "toarray") else np.asarray(Xt)
    if isinstance(est, XGBClassifier):
        import xgboost as xgb

        raw = est.get_booster().predict(xgb.DMatrix(Xt), pred_contribs=True)[:, :-1]
    elif isinstance(est, LogisticRegression):
        raw = Xt * est.coef_[0]
    else:
        import shap

        values = shap.TreeExplainer(est).shap_values(Xt)
        raw = values[1] if isinstance(values, list) else values[..., 1]
    groups = _feature_groups(prep)
    out = np.zeros((Xt.shape[0], len(FEATURES)))
    for j, feature in enumerate(groups):
        out[:, FEATURES.index(feature)] += raw[:, j]
    return out


def _describe(feature: str, value: Any) -> str:
    if feature == "engagement_min":
        return f"{float(value):.0f} min"
    if feature == "touches":
        return f"{int(value)}"
    if feature == "do_not_email":
        return "yes" if int(value) else "no"
    return str(value)


def explain(model: Pipeline, X: pd.DataFrame, top: int = 3) -> list[list[dict[str, Any]]]:
    """Top-N factors per row, strongest first: [{feature, label, value, impact, direction}]."""
    contrib = contributions(model, X)
    explanations = []
    for i in range(len(X)):
        order = np.argsort(-np.abs(contrib[i]))[:top]
        explanations.append(
            [
                {
                    "feature": FEATURES[j],
                    "label": FEATURE_LABELS[FEATURES[j]],
                    "value": _describe(FEATURES[j], X.iloc[i][FEATURES[j]]),
                    "impact": round(float(contrib[i, j]), 3),
                    "direction": "up" if contrib[i, j] > 0 else "down",
                }
                for j in order
            ]
        )
    return explanations
