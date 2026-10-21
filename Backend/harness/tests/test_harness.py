"""Testes do harness (fase 00): métricas, estatística, config e repro."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from sklearn.metrics import f1_score

from Backend.harness.config import ExperimentConfig, load_config
from Backend.harness.metrics import macro_f1
from Backend.harness.registry import RunRegistry
from Backend.harness.run_trial import repro, run_trial
from Backend.harness.stats import bootstrap_ci_metric, holm_bonferroni, mcnemar

Y_TRUE = np.array(["A", "A", "B", "B", "C", "C", "A", "B", "C", "A"])
Y_PRED = np.array(["A", "B", "B", "B", "C", "A", "A", "B", "C", "C"])


class DummyEngine:
    """Motor determinístico: prevê pela primeira feature, sem estado externo."""

    id = "dummy"

    def predict(self, X: np.ndarray) -> np.ndarray:
        z = np.asarray(X)[:, 0]
        return np.where(z > 0.5, "A", "B")


def _X(n: int) -> np.ndarray:
    return np.linspace(0.0, 1.0, n).reshape(-1, 1)


def test_macro_f1_matches_sklearn() -> None:
    expected = f1_score(Y_TRUE, Y_PRED, average="macro", zero_division=0)
    assert abs(macro_f1(Y_TRUE, Y_PRED) - expected) < 1e-12


def test_bootstrap_ci_is_deterministic() -> None:
    a = bootstrap_ci_metric(Y_TRUE, Y_PRED, macro_f1, n_boot=200, seed=7)
    b = bootstrap_ci_metric(Y_TRUE, Y_PRED, macro_f1, n_boot=200, seed=7)
    assert a == b
    assert a["lo"] <= a["point"] <= a["hi"] or a["lo"] <= a["hi"]


def test_mcnemar_identical_engines_gives_p_one() -> None:
    result = mcnemar(Y_TRUE, Y_PRED, Y_PRED)
    assert result["pvalue"] == 1.0
    assert result["method"] == "none"


def test_holm_bonferroni_monotone() -> None:
    adjusted = holm_bonferroni({"a": 0.01, "b": 0.04, "c": 0.03})
    assert adjusted["a"] <= adjusted["c"] <= adjusted["b"] <= 1.0


def test_config_hash_stable_and_loadable() -> None:
    path = Path(__file__).resolve().parents[1] / "configs" / "base.json"
    config = load_config(path)
    assert config.engine == "dummy"
    assert config.config_hash == load_config(path).config_hash


def test_repro_reports_equal() -> None:
    config = ExperimentConfig(
        name="smoke", dataset_id="synthetic", split_id="v1", engine="dummy", seed=1
    )
    result = repro(config, _X(len(Y_TRUE)), Y_TRUE, DummyEngine)
    assert result["equal"] is True


def test_run_trial_persists_and_indexes(tmp_path: Path) -> None:
    config = ExperimentConfig(
        name="smoke", dataset_id="synthetic", split_id="v1", engine="dummy", seed=1
    )
    trial = run_trial(
        config, _X(len(Y_TRUE)), Y_TRUE, DummyEngine(), results_dir=tmp_path, n_boot=50
    )
    registry = RunRegistry(tmp_path)
    stored = registry.get(trial.run_id)
    assert stored is not None
    assert stored["canonical_hash"] == trial.canonical_hash
    assert trial.run_id in registry.find_by_config(config.config_hash)
