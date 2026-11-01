"""Testes da fase 02: baselines e ajuste sem vazamento."""

from __future__ import annotations

import inspect
from pathlib import Path

import numpy as np

from Backend.harness.baselines import (
    DEFAULT_THRESHOLDS,
    HeuristicBaseline,
    IsolationForestDetector,
    SklearnBaseline,
    _multiclass_baselines,
    run_baselines,
    tune_heuristic,
)
from Backend.harness.metrics import macro_f1
from Backend.harness.splits import make_regime_splits


def test_heuristic_predicts_known_scenarios():
    heuristic = HeuristicBaseline()
    row_host_down = np.array([0.0, 100.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    row_normal = np.array([15.0, 0.0, 2.0, 28.0, 45.0, 40.0, 5e6, 2e6, 200.0, 120.0, 1.0, 45.0])
    assert heuristic.predict(row_host_down.reshape(1, -1))[0] == "HOST_DOWN"
    assert heuristic.predict(row_normal.reshape(1, -1))[0] == "NORMAL"


def test_tune_heuristic_uses_only_train_and_never_worsens():
    splits = make_regime_splits(n_per_class=80, seed=0)
    train = splits["train"]
    # Assinatura não expõe o teste.
    params = inspect.signature(tune_heuristic).parameters
    assert "X_train" in params and all("test" not in p for p in params)

    tuned = tune_heuristic(train.X, train.y, n_iter=8, seed=1)
    default_score = macro_f1(train.y, HeuristicBaseline(DEFAULT_THRESHOLDS).predict(train.X))
    tuned_score = macro_f1(train.y, HeuristicBaseline(tuned).predict(train.X))
    assert tuned_score >= default_score


def test_tuned_thresholds_are_deterministic():
    splits = make_regime_splits(n_per_class=60, seed=3)
    first = tune_heuristic(splits["train"].X, splits["train"].y, n_iter=6, seed=2)
    second = tune_heuristic(splits["train"].X, splits["train"].y, n_iter=6, seed=2)
    assert first == second


def test_sklearn_baselines_fit_predict_and_probabilities():
    splits = make_regime_splits(n_per_class=80, seed=4)
    train, test = splits["train"], splits["test"]
    for baseline in _multiclass_baselines(seed=0):
        baseline.fit(train.X, train.y)
        preds = baseline.predict(test.X)
        assert len(preds) == len(test)
        assert set(np.unique(preds)).issubset(set(train.y.tolist()))
        proba = baseline.predict_proba(test.X)
        assert proba.shape[0] == len(test)
        assert np.allclose(proba.sum(axis=1), 1.0, atol=1e-6)


def test_heuristic_yields_no_probabilities():
    # Regras não produzem probabilidade calibrada: o contrato não expõe predict_proba.
    assert not hasattr(HeuristicBaseline(), "predict_proba")


def test_isolation_forest_is_binary():
    splits = make_regime_splits(n_per_class=80, seed=5)
    train, test = splits["train"], splits["test"]
    detector = IsolationForestDetector(seed=0).fit(train.X, np.where(train.y == "NORMAL", "NORMAL", "ANOMALY"))
    labels = set(detector.predict(test.X).tolist())
    assert labels.issubset({"NORMAL", "ANOMALY"})


def test_run_baselines_writes_table_with_ci(tmp_path: Path):
    splits = make_regime_splits(n_per_class=60, seed=6)
    result = run_baselines(splits, seed=0, results_dir=tmp_path, n_boot=50)
    engines = {row["engine"] for row in result["table"]}
    assert {"heuristic", "majority", "random_forest", "isolation_forest"} <= engines
    for row in result["table"]:
        assert 0.0 <= row["macro_f1"] <= 1.0
        assert row["macro_f1_ci"] is not None
    assert (tmp_path / "baselines.jsonl").exists()


def test_classical_baseline_beats_majority():
    splits = make_regime_splits(n_per_class=120, seed=7)
    result = run_baselines(splits, seed=0, n_boot=50)
    by_engine = {row["engine"]: row["macro_f1"] for row in result["table"]}
    assert by_engine["random_forest"] > by_engine["majority"]
