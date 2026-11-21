"""Shared helpers for training pipelines: paths, metrics and saving models."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np

logger = logging.getLogger(__name__)

ML_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ML_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = ML_DIR / "models"
RANDOM_STATE = 42


def model_path(name: str) -> Path:
    return MODELS_DIR / f"{name}.joblib"


def metrics_path(name: str) -> Path:
    return MODELS_DIR / f"{name}.metrics.json"


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating | float):
        value = float(value)
        return None if np.isnan(value) or np.isinf(value) else round(value, 4)
    if isinstance(value, np.ndarray):
        return _jsonable(value.tolist())
    return value


def save_artifact(name: str, model: Any, metrics: dict[str, Any]) -> dict[str, Any]:
    """Save `model` with joblib and a metrics JSON next to it. Returns the stored metrics."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    metrics = _jsonable(
        {"model": name, "trained_at": datetime.now(UTC).isoformat(timespec="seconds"), **metrics}
    )
    joblib.dump(model, model_path(name), compress=3)
    metrics_path(name).write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    logger.info("Saved %s (%s)", model_path(name).name, metrics.get("chosen_model", ""))
    return metrics


def classification_metrics(y_true, proba, threshold: float = 0.5) -> dict[str, Any]:
    """Precision, recall, F1, ROC-AUC and confusion matrix for a binary classifier."""
    from sklearn.metrics import (
        accuracy_score,
        confusion_matrix,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
    )

    y_true = np.asarray(y_true)
    pred = (np.asarray(proba) >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    return {
        "threshold": threshold,
        "accuracy": accuracy_score(y_true, pred),
        "precision": precision_score(y_true, pred, zero_division=0),
        "recall": recall_score(y_true, pred, zero_division=0),
        "f1": f1_score(y_true, pred, zero_division=0),
        "roc_auc": roc_auc_score(y_true, proba),
        "confusion_matrix": {"labels": ["negative", "positive"], "matrix": [[tn, fp], [fn, tp]]},
        "support": {"negative": int((y_true == 0).sum()), "positive": int((y_true == 1).sum())},
    }
