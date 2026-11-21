"""Customer segmentation with K-Means on RFM (recency, frequency, monetary).

Trained on UCI Online Retail. R, F and M are turned into percentile scores in [0, 1]
(1 = best: most recent, most frequent, biggest spender) so clusters learned on UK retail
baskets apply to rupee B2B deals. Clusters are then named by their centroids:

    Champions  bought recently, often, a lot
    Loyal      buy often, still fairly recent
    At Risk    used to buy (good F/M) but not lately
    Lost       low on everything
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from . import datasets
from .common import RANDOM_STATE, save_artifact

NAME = "segment"
FEATURES = ["r_score", "f_score", "m_score"]
SEGMENTS = ["Champions", "Loyal", "At Risk", "Lost"]
DEFAULT_K = 4


def clean_retail(raw: pd.DataFrame) -> pd.DataFrame:
    """Drop cancellations, returns, bad prices and rows without a customer id."""
    df = raw.dropna(subset=["CustomerID"]).copy()
    df = df[~df["InvoiceNo"].astype(str).str.startswith("C")]
    df = df[(df["Quantity"] > 0) & (df["UnitPrice"] > 0)]
    df["amount"] = df["Quantity"] * df["UnitPrice"]
    df["CustomerID"] = df["CustomerID"].astype(int)
    return df


def rfm_table(tx: pd.DataFrame) -> pd.DataFrame:
    """Raw RFM per customer from cleaned transactions."""
    snapshot = tx["InvoiceDate"].max() + pd.Timedelta(days=1)
    return tx.groupby("CustomerID").agg(
        recency_days=("InvoiceDate", lambda d: (snapshot - d.max()).days),
        frequency=("InvoiceNo", "nunique"),
        monetary=("amount", "sum"),
    )


def rfm_scores(rfm: pd.DataFrame) -> pd.DataFrame:
    """Percentile scores in [0, 1], higher = better (so recency is inverted)."""
    return pd.DataFrame(
        {
            "r_score": 1 - rfm["recency_days"].rank(pct=True, method="average") + 1 / len(rfm),
            "f_score": rfm["frequency"].rank(pct=True, method="average"),
            "m_score": rfm["monetary"].rank(pct=True, method="average"),
        },
        index=rfm.index,
    )


def evaluate_k(scores: pd.DataFrame, ks=range(2, 9), sample: int = 3000) -> pd.DataFrame:
    """Inertia (elbow) and silhouette for each k."""
    X = StandardScaler().fit_transform(scores[FEATURES])
    rng = np.random.default_rng(RANDOM_STATE)
    idx = rng.choice(len(X), size=min(sample, len(X)), replace=False)
    rows = []
    for k in ks:
        km = KMeans(n_clusters=k, n_init=10, random_state=RANDOM_STATE).fit(X)
        rows.append(
            {
                "k": k,
                "inertia": km.inertia_,
                "silhouette": silhouette_score(X[idx], km.labels_[idx]),
            }
        )
    return pd.DataFrame(rows)


def name_clusters(centroids: pd.DataFrame) -> dict[int, str]:
    """Name k=4 clusters from their centroids (in score space)."""
    total = centroids[FEATURES].sum(axis=1)
    champions = int(total.idxmax())
    lost = int(total.idxmin())
    rest = [c for c in centroids.index if c not in (champions, lost)]
    at_risk = int(min(rest, key=lambda c: centroids.loc[c, "r_score"]))
    loyal = int(next(c for c in rest if c != at_risk))
    return {champions: "Champions", loyal: "Loyal", at_risk: "At Risk", lost: "Lost"}


def train(save: bool = True, k: int = DEFAULT_K) -> dict[str, Any]:
    tx = clean_retail(datasets.load_retail())
    rfm = rfm_table(tx)
    scores = rfm_scores(rfm)
    k_table = evaluate_k(scores)

    model = Pipeline(
        [
            ("scale", StandardScaler()),
            ("kmeans", KMeans(n_clusters=k, n_init=20, random_state=RANDOM_STATE)),
        ]
    ).fit(scores[FEATURES])
    labels = model.predict(scores[FEATURES])
    centroids = scores.assign(cluster=labels).groupby("cluster")[FEATURES].mean()
    names = name_clusters(centroids)
    profile = (
        rfm.assign(segment=[names[c] for c in labels])
        .groupby("segment")
        .agg(customers=("frequency", "size"), recency_days=("recency_days", "median"),
             frequency=("frequency", "median"), monetary=("monetary", "median"))  # fmt: skip
        .reindex(SEGMENTS)
        .reset_index()
    )
    chosen = k_table.set_index("k").loc[k]
    metrics = {
        "task": "clustering",
        "dataset": "UCI Online Retail",
        "rows": int(len(scores)),
        "transactions": int(len(tx)),
        "features": FEATURES,
        "chosen_model": f"kmeans_k{k}",
        "k": k,
        "silhouette": float(chosen["silhouette"]),
        "selection": (
            "k=4 sits at the elbow of the inertia curve and maps onto the four standard RFM "
            "segments; its silhouette is reported next to the alternatives"
        ),
        "k_comparison": k_table.to_dict(orient="records"),
        "cluster_names": {str(c): n for c, n in names.items()},
        "centroids": {
            names[c]: {f: float(centroids.loc[c, f]) for f in FEATURES} for c in centroids.index
        },
        "profile": profile.to_dict(orient="records"),
    }
    artifact = {"model": model, "names": names}
    if save:
        metrics = save_artifact(NAME, artifact, metrics)
    return metrics


def assign(artifact: dict[str, Any], scores: pd.DataFrame) -> list[str]:
    """Segment names for rows of percentile scores (columns = FEATURES)."""
    labels = artifact["model"].predict(scores[FEATURES])
    return [artifact["names"][int(c)] for c in labels]
