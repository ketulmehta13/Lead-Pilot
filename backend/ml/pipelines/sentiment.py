"""Ticket sentiment: TF-IDF + a linear classifier, then urgency rules -> priority.

Trained on UCI "Sentiment Labelled Sentences" (Amazon/Yelp/IMDb reviews, positive/negative).
The model outputs P(positive); we map it to three classes with a neutral band:

    P >= 0.60 -> positive     P <= 0.40 -> negative     otherwise -> neutral

`score` = 2 * P(positive) - 1, so -1 is very negative and +1 very positive.

Priority (reviews have no notion of urgency, so urgency is a transparent keyword rule):
    negative AND urgent          -> high
    negative OR urgent           -> medium
    otherwise                    -> low
"""

from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline

from . import datasets
from .common import RANDOM_STATE, classification_metrics, save_artifact

NAME = "sentiment"
POSITIVE_AT, NEGATIVE_AT = 0.60, 0.40

URGENT_PATTERNS = [
    r"\burgent(ly)?\b", r"\basap\b", r"\bimmediate(ly)?\b", r"\bright now\b", r"\bemergency\b",
    r"\bcritical\b", r"\b(is|are|went|been) down\b", r"\boutage\b", r"\bnot working\b",
    r"\bstopped working\b", r"\bbroken\b", r"\bcrash(es|ed|ing)?\b", r"\bdata loss\b",
    r"\blost (all|our|my) data\b", r"\bcan'?t (log ?in|access|login)\b", r"\bcannot (log ?in|access)\b",
    r"\blocked out\b", r"\brefund\b", r"\bcancel(l?ing)? (my|our|the) (subscription|account|contract)\b",
    r"\bescalat(e|ion)\b", r"\blegal\b", r"\blawyer\b", r"\bsecurity (breach|issue)\b",
    r"\bcharged twice\b", r"\bdouble charged\b",
]  # fmt: skip
_URGENT = re.compile("|".join(URGENT_PATTERNS), re.IGNORECASE)


def urgent_terms(text: str) -> list[str]:
    return sorted({m.group(0).lower() for m in _URGENT.finditer(text or "")})


def candidates() -> dict[str, Pipeline]:
    tfidf = dict(ngram_range=(1, 2), min_df=2, sublinear_tf=True, strip_accents="unicode")
    return {
        "tfidf_logistic_regression": Pipeline(
            [("tfidf", TfidfVectorizer(**tfidf)), ("model", LogisticRegression(C=4, max_iter=2000))]
        ),
        "tfidf_naive_bayes": Pipeline(
            [("tfidf", TfidfVectorizer(**tfidf)), ("model", MultinomialNB(alpha=0.3))]
        ),
    }


def compare_models(texts: pd.Series, y: pd.Series, folds: int = 5) -> pd.DataFrame:
    cv = StratifiedKFold(folds, shuffle=True, random_state=RANDOM_STATE)
    rows = []
    for name, pipe in candidates().items():
        s = cross_validate(pipe, texts, y, cv=cv, scoring=["roc_auc", "f1", "accuracy"])
        rows.append(
            {
                "model": name,
                "cv_roc_auc": s["test_roc_auc"].mean(),
                "cv_f1": s["test_f1"].mean(),
                "cv_accuracy": s["test_accuracy"].mean(),
                "cv_roc_auc_std": s["test_roc_auc"].std(),
            }
        )
    return pd.DataFrame(rows).sort_values("cv_roc_auc", ascending=False).reset_index(drop=True)


def train(save: bool = True) -> dict[str, Any]:
    df = datasets.load_sentiment()
    X_train, X_test, y_train, y_test = train_test_split(
        df["text"], df["label"], test_size=0.2, stratify=df["label"], random_state=RANDOM_STATE
    )
    comparison = compare_models(X_train, y_train)
    best = comparison.iloc[0]["model"]
    model = candidates()[best].fit(X_train, y_train)
    proba = model.predict_proba(X_test)[:, 1]
    # Binary metrics treat "negative" as the positive class of interest for support.
    test = classification_metrics((y_test == 0).astype(int), 1 - proba)
    test["confusion_matrix"]["labels"] = ["positive text", "negative text"]
    final = candidates()[best].fit(df["text"], df["label"])
    metrics = {
        "task": "classification",
        "dataset": "UCI Sentiment Labelled Sentences",
        "rows": len(df),
        "positive_rate": float((df["label"] == 0).mean()),
        "chosen_model": best,
        "selection": "highest mean 5-fold CV ROC-AUC on the training split",
        "comparison": comparison.to_dict(orient="records"),
        "test": test,
        "neutral_band": [NEGATIVE_AT, POSITIVE_AT],
        "note": "test metrics treat NEGATIVE as the class of interest (the one that needs action)",
    }
    if save:
        metrics = save_artifact(NAME, final, metrics)
    return metrics


def classify(model: Pipeline, texts: list[str]) -> list[dict[str, Any]]:
    """Sentiment, score, urgency and priority for each text."""
    proba = model.predict_proba(texts)[:, 1]
    results = []
    for text, p in zip(texts, np.asarray(proba), strict=True):
        sentiment = (
            "positive" if p >= POSITIVE_AT else "negative" if p <= NEGATIVE_AT else "neutral"
        )
        terms = urgent_terms(text)
        negative, urgent = sentiment == "negative", bool(terms)
        priority = "high" if negative and urgent else "medium" if negative or urgent else "low"
        results.append(
            {
                "sentiment": sentiment,
                "score": round(float(2 * p - 1), 3),
                "urgent": urgent,
                "urgent_terms": terms,
                "priority": priority,
            }
        )
    return results
