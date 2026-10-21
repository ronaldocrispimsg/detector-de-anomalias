"""Orquestração de um trial reproduzível.

run_trial executa um motor sobre um conjunto, calcula métricas e IC, monta o
registro canônico e (opcionalmente) persiste. repro prova reprodutibilidade
rodando o mesmo config duas vezes e comparando o hash canônico.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol, Sequence

import numpy as np

from Backend.harness.config import ExperimentConfig
from Backend.harness.metrics import classification_metrics, macro_f1
from Backend.harness.registry import RunRegistry, canonical_record_hash
from Backend.harness.seed import set_seed
from Backend.harness.stats import bootstrap_ci_metric


class Engine(Protocol):
    """Motor de classificação: expõe id e predict(X); predict_proba é opcional."""

    id: str

    def predict(self, X: Any) -> np.ndarray:  # pragma: no cover - protocolo
        ...


_METRIC_FNS: dict[str, Callable[[Sequence[Any], Sequence[Any]], float]] = {
    "macro_f1": macro_f1,
}


@dataclass
class TrialResult:
    run_id: str
    config_hash: str
    canonical_hash: str
    metrics: dict[str, Any]
    metrics_ci: dict[str, dict[str, float]]
    record: dict[str, Any]


def _engine_id(engine: Any) -> str:
    return str(getattr(engine, "id", engine.__class__.__name__))


def _predict_proba(engine: Any, X: Any) -> np.ndarray | None:
    method = getattr(engine, "predict_proba", None)
    if method is None:
        return None
    try:
        return np.asarray(method(X), dtype=float)
    except NotImplementedError:
        return None


def run_trial(
    config: ExperimentConfig,
    X: Any,
    y: Sequence[Any],
    engine: Any,
    *,
    results_dir: str | Path | None = None,
    timestamp: str | None = None,
    persist: bool = True,
    n_boot: int = 1000,
) -> TrialResult:
    set_seed(config.seed)
    y_arr = np.asarray(y)
    y_pred = np.asarray(engine.predict(X))
    y_score = _predict_proba(engine, X)

    metrics = classification_metrics(y_arr, y_pred, y_score=y_score)
    metrics_ci: dict[str, dict[str, float]] = {}
    for name in config.metrics:
        metric_fn = _METRIC_FNS.get(name)
        if metric_fn is not None:
            metrics_ci[name] = bootstrap_ci_metric(
                y_arr, y_pred, metric_fn, n_boot=n_boot, seed=config.seed
            )

    engine_id = _engine_id(engine)
    y_true_list = [str(v) for v in y_arr.tolist()]
    y_pred_list = [str(v) for v in y_pred.tolist()]
    canonical_hash = canonical_record_hash(
        config.config_hash,
        config.dataset_id,
        config.split_id,
        engine_id,
        y_true_list,
        y_pred_list,
        metrics,
    )
    ts = timestamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{config.config_hash}-{ts}"

    record: dict[str, Any] = {
        "run_id": run_id,
        "timestamp": ts,
        "config_hash": config.config_hash,
        "canonical_hash": canonical_hash,
        "config": config.to_dict(),
        "seed": config.seed,
        "dataset_id": config.dataset_id,
        "split_id": config.split_id,
        "engine": engine_id,
        "n_samples": int(len(y_arr)),
        "metrics": metrics,
        "metrics_ci": metrics_ci,
    }

    if persist and results_dir is not None:
        RunRegistry(results_dir).write(record)

    return TrialResult(
        run_id=run_id,
        config_hash=config.config_hash,
        canonical_hash=canonical_hash,
        metrics=metrics,
        metrics_ci=metrics_ci,
        record=record,
    )


def repro(
    config: ExperimentConfig,
    X: Any,
    y: Sequence[Any],
    engine_factory: Callable[[], Any],
    *,
    n_boot: int = 200,
) -> dict[str, Any]:
    """Roda o motor duas vezes do zero e compara o hash canônico."""
    first = run_trial(config, X, y, engine_factory(), persist=False, n_boot=n_boot)
    second = run_trial(config, X, y, engine_factory(), persist=False, n_boot=n_boot)
    return {
        "equal": first.canonical_hash == second.canonical_hash,
        "hash_a": first.canonical_hash,
        "hash_b": second.canonical_hash,
    }
