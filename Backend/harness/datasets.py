"""Datasets do agente.

Constrói conjuntos com regime controlado a partir do simulador real
(`AnomalySimulator`), carrega o CSV real com divisão temporal e oferece um
carregador genérico para bases externas (holdout). Toda amostra carrega, além
das features, a severidade do regime, o grupo e o tempo, usados na guarda
anti-vazamento.
"""

from __future__ import annotations

import csv
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

from Backend.services.agent.telemetry import CLASSES, FEATURE_FIELDS, LABEL_FIELD
from Backend.services.anomaly_simulator import AnomalySimulator

__all__ = [
    "CLASSES",
    "FEATURE_FIELDS",
    "LABEL_FIELD",
    "DatasetSplit",
    "generate_regime_dataset",
    "load_labeled_csv",
    "sample_to_row",
    "try_load_external",
]


@dataclass
class DatasetSplit:
    """Conjunto de amostras com metadados de vazamento."""

    X: np.ndarray
    y: np.ndarray
    severity: np.ndarray
    groups: np.ndarray
    times: np.ndarray
    feature_names: tuple[str, ...] = FEATURE_FIELDS
    meta: dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        return int(self.X.shape[0])

    def class_counts(self) -> dict[str, int]:
        labels, counts = np.unique(self.y, return_counts=True)
        return {str(lbl): int(c) for lbl, c in zip(labels, counts)}


def sample_to_row(sample: Any) -> list[float]:
    data = sample.model_dump() if hasattr(sample, "model_dump") else sample.dict()
    row: list[float] = []
    for name in FEATURE_FIELDS:
        value = data[name]
        if name == "tcp_port_open":
            row.append(1.0 if value else 0.0)
        else:
            row.append(float(value))
    return row


def generate_regime_dataset(
    *,
    n_per_class: int,
    seed: int,
    severity_range: tuple[float, float],
    name: str,
    time_step: float = 10.0,
    block: int = 50,
    start_time: float = 0.0,
) -> DatasetSplit:
    """Gera um conjunto em que cada classe é amostrada num regime de severidade.

    NORMAL é mantido no regime saudável (severidade 0). As classes anômalas
    recebem severidade uniforme em `severity_range`, produzindo conjuntos com
    parâmetros geradores disjuntos entre splits.
    """
    simulator = AnomalySimulator()
    rng = random.Random(seed)
    rows: list[list[float]] = []
    labels: list[str] = []
    severities: list[float] = []
    groups: list[str] = []
    times: list[float] = []
    k = 0
    for scenario in CLASSES:
        for i in range(n_per_class):
            severity = 0.0 if scenario == "NORMAL" else rng.uniform(*severity_range)
            timestamp = start_time + k * time_step
            sample = simulator.generate_sample(
                scenario, timestamp=timestamp, severity=severity, rng=rng
            )
            rows.append(sample_to_row(sample))
            labels.append(scenario)
            severities.append(severity)
            groups.append(f"{name}:{scenario}:{i // block}")
            times.append(timestamp)
            k += 1
    return DatasetSplit(
        X=np.asarray(rows, dtype=float),
        y=np.asarray(labels, dtype=object),
        severity=np.asarray(severities, dtype=float),
        groups=np.asarray(groups, dtype=object),
        times=np.asarray(times, dtype=float),
        meta={
            "kind": "regime",
            "name": name,
            "seed": seed,
            "severity_range": [float(severity_range[0]), float(severity_range[1])],
        },
    )


def _parse_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "t"}


def load_labeled_csv(
    path: str | Path,
    *,
    time_column: str = "timestamp",
    label_column: str = LABEL_FIELD,
    feature_columns: Sequence[str] | None = None,
    name: str | None = None,
    block: int = 1000,
) -> DatasetSplit:
    """Carrega um CSV com cabeçalho em um DatasetSplit.

    Preserva o tempo para permitir divisão temporal. Features binárias são
    convertidas para 0/1.
    """
    path = Path(path)
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError(f"{path}: CSV sem cabeçalho")
        if feature_columns is None:
            feature_columns = tuple(
                c for c in reader.fieldnames if c not in (time_column, label_column)
            )
        feature_columns = tuple(feature_columns)
        rows: list[list[float]] = []
        labels: list[str] = []
        times: list[float] = []
        for i, record in enumerate(reader):
            row = []
            for col in feature_columns:
                raw = record[col]
                if col == "tcp_port_open" or raw in {"True", "False", "true", "false"}:
                    row.append(1.0 if _parse_bool(raw) else 0.0)
                else:
                    row.append(float(raw))
            rows.append(row)
            labels.append(str(record[label_column]))
            times.append(float(record[time_column]) if time_column in record else float(i))
    groups = [f"{name or path.stem}:{i // block}" for i in range(len(rows))]
    return DatasetSplit(
        X=np.asarray(rows, dtype=float),
        y=np.asarray(labels, dtype=object),
        severity=np.zeros(len(rows), dtype=float),
        groups=np.asarray(groups, dtype=object),
        times=np.asarray(times, dtype=float),
        feature_names=tuple(feature_columns),
        meta={"kind": "csv", "name": name or path.stem, "source": str(path)},
    )


def try_load_external(path: str | Path, *, name: str, **kwargs: Any) -> DatasetSplit | None:
    """Carrega base externa (holdout) se existir; senão devolve None.

    Bases externas nunca entram no treino; são usadas só para validar
    generalização.
    """
    path = Path(path)
    if not path.exists():
        return None
    split = load_labeled_csv(path, name=name, **kwargs)
    split.meta["kind"] = "external"
    split.meta["role"] = "holdout"
    return split
