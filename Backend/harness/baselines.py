"""Baselines de referência.

Piso de comparação: heurística de NOC (limiares ajustados apenas no treino),
modelos clássicos (RandomForest, HistGradientBoosting, Regressão Logística) e
um detector binário (IsolationForest). Toda avaliação usa `run_trial`, que
anexa intervalo de confiança bootstrap.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Callable

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, IsolationForest, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from Backend.harness.config import ExperimentConfig
from Backend.harness.datasets import DatasetSplit
from Backend.harness.metrics import macro_f1
from Backend.harness.run_trial import run_trial

# Índices das colunas em FEATURE_FIELDS.
LATENCY, LOSS, JITTER, CPU, RAM, DISK, NET_IN, NET_OUT, HTTP, HTTP_RESP, TCP, CONN = range(12)

DEFAULT_THRESHOLDS: dict[str, float] = {
    "host_down_loss": 99.0,
    "ddos_in_bps": 80_000_000.0,
    "ddos_conn": 2000.0,
    "ddos_loss": 20.0,
    "portscan_conn": 700.0,
    "portscan_loss": 15.0,
    "portscan_in_bps": 40_000_000.0,
    "exfil_out_bps": 100_000_000.0,
    "exfil_ratio": 3.5,
    "ram_critical": 90.0,
    "cpu_for_mem": 65.0,
    "disk_critical": 95.0,
    "http_ok_loss": 90.0,
    "cong_latency": 140.0,
    "cong_jitter": 40.0,
    "cong_loss": 10.0,
    "cpu_high": 90.0,
    "combined_cpu": 88.0,
    "combined_ram": 88.0,
    "combined_disk": 88.0,
}


def _classify_row(row: np.ndarray, t: dict[str, float]) -> str:
    latency, loss, jitter, cpu, ram, disk = row[:6]
    net_in, net_out, http, _http_resp, tcp, conn = row[6:12]

    rules: set[str] = set()
    critical = 0

    if loss >= t["host_down_loss"] and latency == 0.0:
        rules.add("HOST_DOWN")
    if net_in > t["ddos_in_bps"] or (conn > t["ddos_conn"] and loss > t["ddos_loss"]):
        rules.add("DDOS")
        critical += 1
    if conn > t["portscan_conn"] and loss < t["portscan_loss"] and net_in < t["portscan_in_bps"]:
        rules.add("PORTSCAN")
    if net_out > t["exfil_out_bps"] and net_out > net_in * t["exfil_ratio"]:
        rules.add("EXFIL")
        critical += 1
    if ram >= t["ram_critical"]:
        rules.add("MEMLEAK")
        if cpu > t["cpu_for_mem"]:
            critical += 1
    if disk >= t["disk_critical"]:
        rules.add("DISK")
        critical += 1
    if (http in {500.0, 502.0, 503.0, 504.0} or tcp == 0.0) and loss < t["http_ok_loss"]:
        rules.add("SERVICE")
    if (
        latency > t["cong_latency"]
        or jitter > t["cong_jitter"]
        or (t["cong_loss"] <= loss < 90.0)
    ):
        rules.add("CONG")
    if cpu >= t["cpu_high"]:
        critical += 1

    if "HOST_DOWN" in rules:
        return "HOST_DOWN"
    if (
        cpu >= t["combined_cpu"] and ram >= t["combined_ram"] and disk >= t["combined_disk"]
    ) or critical >= 4:
        return "COMBINED_FAULT"
    if "DDOS" in rules:
        return "DDOS_ATTACK"
    if "EXFIL" in rules:
        return "DATA_EXFILTRATION"
    if "DISK" in rules:
        return "DISK_EXHAUSTION"
    if "MEMLEAK" in rules:
        return "MEMORY_LEAK"
    if "PORTSCAN" in rules:
        return "PORT_SCAN"
    if "SERVICE" in rules:
        return "SERVICE_OUTAGE"
    if "CONG" in rules:
        return "NETWORK_CONGESTION"
    return "NORMAL"


class HeuristicBaseline:
    id = "heuristic"

    def __init__(self, thresholds: dict[str, float] | None = None) -> None:
        self.thresholds = dict(thresholds or DEFAULT_THRESHOLDS)

    def fit(self, X: np.ndarray, y: np.ndarray) -> "HeuristicBaseline":
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.asarray([_classify_row(np.asarray(row), self.thresholds) for row in X], dtype=object)


def tune_heuristic(
    X_train: np.ndarray,
    y_train: np.ndarray,
    *,
    n_iter: int = 24,
    seed: int = 0,
) -> dict[str, float]:
    """Ajusta limiares da heurística usando SOMENTE o treino.

    Para não piorar em relação ao padrão, o conjunto de candidatos inclui os
    limiares originais.
    """
    rng = random.Random(seed)
    best = dict(DEFAULT_THRESHOLDS)
    best_score = macro_f1(y_train, HeuristicBaseline(best).predict(X_train))
    for _ in range(n_iter):
        candidate = dict(best)
        for key, value in DEFAULT_THRESHOLDS.items():
            if rng.random() < 0.5:
                candidate[key] = value * rng.uniform(0.6, 1.4)
        score = macro_f1(y_train, HeuristicBaseline(candidate).predict(X_train))
        if score > best_score:
            best, best_score = candidate, score
    return best


class SklearnBaseline:
    def __init__(self, engine_id: str, estimator: Any, *, scale: bool = False) -> None:
        self.id = engine_id
        self._estimator = estimator
        self._scale = scale
        self._scaler: StandardScaler | None = None

    def fit(self, X: np.ndarray, y: np.ndarray) -> "SklearnBaseline":
        if self._scale:
            self._scaler = StandardScaler().fit(X)
            X = self._scaler.transform(X)
        self._estimator.fit(X, y)
        return self

    def _transform(self, X: np.ndarray) -> np.ndarray:
        return self._scaler.transform(X) if self._scaler is not None else X

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self._estimator.predict(self._transform(X))

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        method = getattr(self._estimator, "predict_proba", None)
        if method is None:
            raise NotImplementedError
        return method(self._transform(X))


class IsolationForestDetector:
    """Detector binário: NORMAL vs ANOMALY (não classifica o tipo)."""

    id = "isolation_forest"

    def __init__(self, seed: int) -> None:
        self._estimator = IsolationForest(random_state=seed, n_jobs=-1)

    def fit(self, X: np.ndarray, y: np.ndarray) -> "IsolationForestDetector":
        self._estimator.fit(X)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        raw = self._estimator.predict(X)
        return np.where(raw == -1, "ANOMALY", "NORMAL")


def _multiclass_baselines(seed: int) -> list[SklearnBaseline]:
    return [
        SklearnBaseline(
            "random_forest",
            RandomForestClassifier(n_estimators=200, random_state=seed, n_jobs=-1),
        ),
        SklearnBaseline(
            "hist_gradient_boosting",
            HistGradientBoostingClassifier(random_state=seed),
        ),
        SklearnBaseline(
            "logistic_regression",
            LogisticRegression(max_iter=1000, random_state=seed),
            scale=True,
        ),
    ]


def _evaluate(
    engine: Any,
    X_test: np.ndarray,
    y_test: np.ndarray,
    *,
    name: str,
    dataset_id: str,
    split_id: str,
    seed: int,
    n_boot: int,
) -> dict[str, Any]:
    config = ExperimentConfig(
        name=name,
        dataset_id=dataset_id,
        split_id=split_id,
        engine=engine.id,
        seed=seed,
    )
    trial = run_trial(config, X_test, y_test, engine, persist=False, n_boot=n_boot)
    return {
        "engine": engine.id,
        "macro_f1": trial.metrics["macro_f1"],
        "balanced_accuracy": trial.metrics["balanced_accuracy"],
        "accuracy": trial.metrics["accuracy"],
        "macro_f1_ci": trial.metrics_ci.get("macro_f1"),
        "canonical_hash": trial.canonical_hash,
    }


def run_baselines(
    splits: dict[str, DatasetSplit],
    *,
    seed: int = 0,
    results_dir: str | Path | None = None,
    n_boot: int = 1000,
    tune: bool = True,
) -> dict[str, Any]:
    """Treina e avalia todos os baselines; devolve tabela comparativa."""
    train, test = splits["train"], splits["test"]
    dataset_id = str(test.meta.get("name", "regime:test"))
    split_id = f"{train.meta.get('name')}->{test.meta.get('name')}"

    records: list[dict[str, Any]] = []

    # Heurística (limiares ajustados só no treino).
    thresholds = tune_heuristic(train.X, train.y, seed=seed) if tune else dict(DEFAULT_THRESHOLDS)
    heuristic = HeuristicBaseline(thresholds).fit(train.X, train.y)
    records.append(
        _evaluate(
            heuristic, test.X, test.y, name="baseline:heuristic",
            dataset_id=dataset_id, split_id=split_id, seed=seed, n_boot=n_boot,
        )
    )

    # Classe majoritária (referência inferior).
    majority = _MajorityBaseline(train.y)
    records.append(
        _evaluate(
            majority, test.X, test.y, name="baseline:majority",
            dataset_id=dataset_id, split_id=split_id, seed=seed, n_boot=n_boot,
        )
    )

    for baseline in _multiclass_baselines(seed):
        baseline.fit(train.X, train.y)
        records.append(
            _evaluate(
                baseline, test.X, test.y, name=f"baseline:{baseline.id}",
                dataset_id=dataset_id, split_id=split_id, seed=seed, n_boot=n_boot,
            )
        )

    # Detector binário separado (não classifica o tipo de anomalia).
    binary_test = np.where(test.y == "NORMAL", "NORMAL", "ANOMALY")
    detector = IsolationForestDetector(seed).fit(train.X, np.where(train.y == "NORMAL", "NORMAL", "ANOMALY"))
    records.append(
        _evaluate(
            detector, test.X, binary_test, name="baseline:isolation_forest_binary",
            dataset_id=dataset_id, split_id=split_id, seed=seed, n_boot=n_boot,
        )
    )

    result = {"thresholds": thresholds, "table": records}
    if results_dir is not None:
        path = Path(results_dir) / "baselines.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            for record in records:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return result


class _MajorityBaseline:
    id = "majority"

    def __init__(self, y_train: np.ndarray) -> None:
        labels, counts = np.unique(y_train, return_counts=True)
        self._label = labels[int(np.argmax(counts))]

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.asarray([self._label] * len(X), dtype=object)
