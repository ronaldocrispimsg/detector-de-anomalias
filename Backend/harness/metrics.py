"""Métricas de classificação usadas em todas as fases.

Todas recebem arrays do numpy ou sequências; retornam tipos nativos do Python
para que o registro de execução seja serializável em JSON.
"""

from __future__ import annotations

import math
from typing import Any, Sequence

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix as sk_confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)


def macro_f1(y_true: Sequence[Any], y_pred: Sequence[Any]) -> float:
    return float(f1_score(y_true, y_pred, average="macro", zero_division=0))


def weighted_f1(y_true: Sequence[Any], y_pred: Sequence[Any]) -> float:
    return float(f1_score(y_true, y_pred, average="weighted", zero_division=0))


def accuracy(y_true: Sequence[Any], y_pred: Sequence[Any]) -> float:
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    return float((y_true == y_pred).mean()) if len(y_true) else 0.0


def balanced_accuracy(y_true: Sequence[Any], y_pred: Sequence[Any]) -> float:
    return float(balanced_accuracy_score(y_true, y_pred))


def per_class_report(
    y_true: Sequence[Any],
    y_pred: Sequence[Any],
    labels: Sequence[Any] | None = None,
) -> list[dict[str, Any]]:
    if labels is None:
        labels = sorted({str(v) for v in y_true} | {str(v) for v in y_pred})
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=list(labels), zero_division=0
    )
    return [
        {
            "label": str(lbl),
            "precision": float(precision[i]),
            "recall": float(recall[i]),
            "f1": float(f1[i]),
            "support": int(support[i]),
        }
        for i, lbl in enumerate(labels)
    ]


def confusion(
    y_true: Sequence[Any],
    y_pred: Sequence[Any],
    labels: Sequence[Any] | None = None,
) -> list[list[int]]:
    return sk_confusion_matrix(y_true, y_pred, labels=labels).tolist()


def pr_auc_ovr(
    y_true: Sequence[Any],
    y_score: np.ndarray,
    classes: Sequence[Any],
) -> dict[str, float]:
    """PR-AUC one-vs-rest por classe e macro. Classe ausente vira NaN."""
    y_true = np.asarray(y_true)
    y_score = np.asarray(y_score)
    out: dict[str, float] = {}
    for i, cls in enumerate(classes):
        binary = (y_true == cls).astype(int)
        if binary.sum() == 0 or binary.sum() == len(binary):
            out[str(cls)] = float("nan")
        else:
            out[str(cls)] = float(average_precision_score(binary, y_score[:, i]))
    valid = [v for v in out.values() if not math.isnan(v)]
    out["macro"] = float(np.mean(valid)) if valid else float("nan")
    return out


def expected_calibration_error(
    y_true: Sequence[Any],
    y_prob: np.ndarray,
    n_bins: int = 15,
    classes: Sequence[Any] | None = None,
) -> tuple[float, float]:
    """ECE e MCE multiclasse sobre a classe de maior probabilidade.

    Assume que as colunas de y_prob seguem a ordem de `classes` (padrão:
    classes ordenadas de y_true).
    """
    y_prob = np.asarray(y_prob, dtype=float)
    if classes is None:
        classes = sorted({str(v) for v in y_true})
    index = {str(c): i for i, c in enumerate(classes)}
    yt = np.array([index[str(v)] for v in y_true])
    pred = y_prob.argmax(axis=1)
    conf = y_prob.max(axis=1)
    correct = (pred == yt).astype(float)

    edges = np.linspace(0.0, 1.0, n_bins + 1)
    n = len(conf)
    ece = 0.0
    mce = 0.0
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        mask = (conf > lo) & (conf <= hi) if i > 0 else (conf >= lo) & (conf <= hi)
        if not mask.any():
            continue
        gap = abs(correct[mask].mean() - conf[mask].mean())
        ece += (mask.sum() / n) * gap
        mce = max(mce, gap)
    return float(ece), float(mce)


def coverage_risk_curve(
    y_true: Sequence[Any],
    y_prob: np.ndarray,
    thresholds: Sequence[float] = (0.5, 0.6, 0.7, 0.8, 0.9),
) -> list[dict[str, float]]:
    """Para cada limiar de confiança: cobertura e risco (taxa de erro)."""
    y_true = np.asarray([str(v) for v in y_true])
    y_prob = np.asarray(y_prob, dtype=float)
    classes = sorted(set(y_true.tolist()))
    index = {c: i for i, c in enumerate(classes)}
    pred = np.array([classes[i] for i in y_prob.argmax(axis=1)])
    conf = y_prob.max(axis=1)
    out = []
    for t in thresholds:
        mask = conf >= t
        coverage = float(mask.mean())
        risk = float((pred[mask] != y_true[mask]).mean()) if mask.any() else 0.0
        out.append({"threshold": float(t), "coverage": coverage, "risk": risk})
    return out


def classification_metrics(
    y_true: Sequence[Any],
    y_pred: Sequence[Any],
    y_score: np.ndarray | None = None,
    classes: Sequence[Any] | None = None,
    n_bins: int = 15,
) -> dict[str, Any]:
    """Conjunto padrão de métricas usado pelos trials."""
    result: dict[str, Any] = {
        "macro_f1": macro_f1(y_true, y_pred),
        "weighted_f1": weighted_f1(y_true, y_pred),
        "accuracy": accuracy(y_true, y_pred),
        "balanced_accuracy": balanced_accuracy(y_true, y_pred),
        "per_class": per_class_report(y_true, y_pred),
    }
    if y_score is not None:
        if classes is None:
            classes = sorted({str(v) for v in y_true})
        ece, mce = expected_calibration_error(y_true, y_score, n_bins=n_bins, classes=classes)
        result["ece"] = ece
        result["mce"] = mce
        result["pr_auc"] = pr_auc_ovr(y_true, y_score, classes)
    return result
