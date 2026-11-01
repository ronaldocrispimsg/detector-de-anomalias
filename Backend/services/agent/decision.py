"""Decisão: calibração, ensemble ponderado e abstenção.

Os pesos e a temperatura são ajustados **na validação**, nunca fixos no código.
A abstenção usa limiar de confiança e produz a curva cobertura-risco.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

from Backend.harness.metrics import macro_f1

ABSTAIN_LABEL = "ABSTAIN"


def _softmax(logits: np.ndarray, temperature: float) -> np.ndarray:
    z = logits / max(temperature, 1e-6)
    z = z - z.max(axis=1, keepdims=True)
    exp = np.exp(z)
    return exp / exp.sum(axis=1, keepdims=True)


def reorder_proba(
    model_classes: Sequence[object],
    probs: np.ndarray,
    target_classes: Sequence[object],
) -> np.ndarray:
    """Reordena colunas de predict_proba para a ordem de `target_classes`.

    sklearn ordena as classes alfabeticamente; sem reordenar, `argmax` é
    mapeado para o rótulo errado.
    """
    columns = list(model_classes)
    order = [columns.index(c) for c in target_classes]
    return np.asarray(probs, dtype=float)[:, order]


def apply_temperature(probs: np.ndarray, temperature: float) -> np.ndarray:
    """Aplica uma temperatura já ajustada a novas probabilidades."""
    logits = np.log(np.clip(np.asarray(probs, dtype=float), 1e-9, 1.0))
    return _softmax(logits, temperature)


def temperature_scale(
    probs: np.ndarray, y: Sequence[object], classes: Sequence[object]
) -> tuple[np.ndarray, float]:
    """Ajusta uma temperatura única minimizando a NLL na validação."""
    from scipy.optimize import minimize_scalar

    classes = list(classes)
    index = {c: i for i, c in enumerate(classes)}
    y_idx = np.asarray([index[v] for v in y])
    logits = np.log(np.clip(np.asarray(probs, dtype=float), 1e-9, 1.0))
    rows = np.arange(len(y_idx))

    def nll(temperature: float) -> float:
        calibrated = _softmax(logits, temperature)
        return float(-np.mean(np.log(calibrated[rows, y_idx] + 1e-12)))

    result = minimize_scalar(nll, bounds=(0.05, 10.0), method="bounded")
    temperature = float(result.x)
    return _softmax(logits, temperature), temperature


@dataclass
class WeightedEnsemble:
    classes: tuple[object, ...]
    weights: np.ndarray = field(default_factory=lambda: np.ones(0))

    def fit(self, prob_mats: Sequence[np.ndarray], y: Sequence[object]) -> "WeightedEnsemble":
        scores = []
        for probs in prob_mats:
            labels = [self.classes[i] for i in np.asarray(probs).argmax(axis=1)]
            scores.append(max(1e-3, macro_f1(y, labels)))
        weights = np.asarray(scores, dtype=float)
        self.weights = weights / weights.sum()
        return self

    def predict_proba(self, prob_mats: Sequence[np.ndarray]) -> np.ndarray:
        stacked = np.stack([np.asarray(p, dtype=float) for p in prob_mats])
        weighted = np.tensordot(self.weights, stacked, axes=(0, 0))
        return weighted / weighted.sum(axis=1, keepdims=True)

    def predict(self, prob_mats: Sequence[np.ndarray]) -> np.ndarray:
        probs = self.predict_proba(prob_mats)
        return np.asarray([self.classes[i] for i in probs.argmax(axis=1)], dtype=object)


def decide_with_abstention(
    probs: np.ndarray,
    classes: Sequence[object],
    *,
    threshold: float,
    abstain_label: str = ABSTAIN_LABEL,
) -> np.ndarray:
    probs = np.asarray(probs, dtype=float)
    decisions = []
    for row in probs:
        i = int(row.argmax())
        decisions.append(classes[i] if row[i] >= threshold else abstain_label)
    return np.asarray(decisions, dtype=object)


def abstention_curve(
    probs: np.ndarray,
    y: Sequence[object],
    classes: Sequence[object],
    *,
    thresholds: Sequence[float] = (0.0, 0.3, 0.5, 0.7, 0.9),
) -> list[dict[str, float]]:
    """Cobertura (fração respondida) e risco (erro entre respondidas) por limiar."""
    probs = np.asarray(probs, dtype=float)
    y = np.asarray([str(v) for v in y], dtype=object)
    curve = []
    for threshold in thresholds:
        preds = decide_with_abstention(probs, classes, threshold=threshold)
        answered = preds != ABSTAIN_LABEL
        coverage = float(answered.mean())
        if answered.any():
            risk = float((preds[answered] != y[answered]).mean())
        else:
            risk = 0.0
        curve.append({"threshold": float(threshold), "coverage": coverage, "risk": risk})
    return curve


def calibrate_engines(
    prob_mats: Sequence[np.ndarray],
    y_val: Sequence[object],
    classes: Sequence[object],
) -> dict[str, object]:
    """Compara ECE/MCE por motor antes e depois da calibração e do ensemble."""
    from Backend.harness.metrics import expected_calibration_error

    results: dict[str, object] = {"per_engine": []}
    calibrated = []
    for name, probs in zip(("engine0", "engine1", "engine2", "engine3"), prob_mats):
        probs = np.asarray(probs, dtype=float)
        ece_before, _ = expected_calibration_error(y_val, probs, classes=classes)
        cal, temperature = temperature_scale(probs, y_val, classes)
        ece_after, _ = expected_calibration_error(y_val, cal, classes=classes)
        results["per_engine"].append(
            {"engine": name, "ece_before": ece_before, "ece_after": ece_after, "temperature": temperature}
        )
        calibrated.append(cal)

    ensemble = WeightedEnsemble(classes=tuple(classes)).fit(calibrated, y_val)
    ens_probs = ensemble.predict_proba(calibrated)
    ece_ens, _ = expected_calibration_error(y_val, ens_probs, classes=classes)
    results["ensemble"] = {
        "weights": ensemble.weights.tolist(),
        "ece": ece_ens,
        "classes": list(classes),
    }
    return results
