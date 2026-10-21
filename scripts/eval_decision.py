"""Decisão real: calibração + ensemble + curva cobertura-risco (Fase 06).

Treina RF/HGB/LogReg no treino, calibra na validação e avalia abstenção no
teste. Escreve `coverage_risk.jsonl` e `decision_calibration.json`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from Backend.harness.metrics import expected_calibration_error
from Backend.harness.splits import make_regime_splits
from Backend.services.agent.decision import (
    WeightedEnsemble,
    abstention_curve,
    apply_temperature,
    decide_with_abstention,
    reorder_proba,
    temperature_scale,
)
from Backend.services.agent.telemetry import CLASSES


def _engines():
    from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
    from sklearn.linear_model import LogisticRegression

    return {
        "random_forest": RandomForestClassifier(n_estimators=200, random_state=0),
        "hist_gradient_boosting": HistGradientBoostingClassifier(random_state=0),
        "logistic_regression": LogisticRegression(max_iter=2000),
    }


def main() -> None:
    splits = make_regime_splits(n_per_class=400, seed=0)
    train, val, test = splits["train"], splits["val"], splits["test"]

    val_probs, test_probs = [], []
    per_engine = []
    for name, model in _engines().items():
        model.fit(train.X, train.y)
        p_val = reorder_proba(model.classes_, model.predict_proba(val.X), CLASSES)
        p_test = reorder_proba(model.classes_, model.predict_proba(test.X), CLASSES)
        ece_before, _ = expected_calibration_error(val.y, p_val, classes=CLASSES)
        p_val_cal, temperature = temperature_scale(p_val, val.y, CLASSES)
        ece_after, _ = expected_calibration_error(val.y, p_val_cal, classes=CLASSES)
        per_engine.append(
            {"engine": name, "ece_before": ece_before, "ece_after": ece_after, "temperature": temperature}
        )
        val_probs.append(p_val_cal)
        test_probs.append(apply_temperature(p_test, temperature))

    ensemble = WeightedEnsemble(classes=tuple(CLASSES)).fit(val_probs, val.y)
    ensemble_val = ensemble.predict_proba(val_probs)
    ensemble_test = ensemble.predict_proba(test_probs)
    ece_ensemble, _ = expected_calibration_error(val.y, ensemble_val, classes=CLASSES)

    # Limiar por alvo de cobertura: quantil das confianças máximas da validação.
    # Transfere melhor entre regimes que um limiar absoluto de probabilidade.
    target_coverage = 0.7
    val_conf = ensemble_val.max(axis=1)
    threshold = float(np.quantile(val_conf, 1.0 - target_coverage))

    grid = sorted({round(0.02 * i, 2) for i in range(1, 50)} | {round(threshold, 2)})
    curve = abstention_curve(ensemble_test, test.y, CLASSES, thresholds=grid)
    preds = decide_with_abstention(ensemble_test, CLASSES, threshold=threshold)
    abstain_rate = float(np.mean([p == "ABSTAIN" for p in preds]))
    answered = preds != "ABSTAIN"
    test_risk = float((preds[answered] != np.asarray(test.y)[answered]).mean()) if answered.any() else 0.0
    test_coverage = float(answered.mean())

    out = Path("Backend/harness/results")
    out.mkdir(parents=True, exist_ok=True)
    with (out / "coverage_risk.jsonl").open("w", encoding="utf-8") as fh:
        for point in curve:
            fh.write(json.dumps(point, ensure_ascii=False) + "\n")
    (out / "decision_calibration.json").write_text(
        json.dumps(
            {
                "per_engine": per_engine,
                "ensemble": {"ece": ece_ensemble, "weights": ensemble.weights.tolist()},
                "target_coverage": target_coverage,
                "chosen_threshold": threshold,
                "test_coverage": test_coverage,
                "test_risk_at_threshold": test_risk,
                "test_abstain_rate": abstain_rate,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"per_engine": per_engine, "ensemble_ece": ece_ensemble,
                      "ensemble_weights": ensemble.weights.tolist(),
                      "chosen_threshold": threshold,
                      "test_coverage": test_coverage,
                      "test_risk_at_threshold": test_risk,
                      "test_abstain_rate": abstain_rate}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
