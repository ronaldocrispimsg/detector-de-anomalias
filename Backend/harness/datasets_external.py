"""Holdout externo: carregador e mapeamento de rótulos (fase 13).

Carrega datasets públicos (UNSW-NB15, CSE-CIC-IDS2018) e mapeia seus rótulos para
as classes do agente. O que não mapeia vira `OTHER` e é descartado — e contado no
relatório, nunca escondido.

As 12 features de `agent/telemetry.py` raramente existem no dataset externo. Onde
não existem, usamos um **proxy documentado** (por exemplo `sload` → `network_in_bps`)
ou marcamos a feature como ausente (`NaN`). O descompasso de features é reportado
como parte da explicação da queda.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

from Backend.harness.datasets import DatasetSplit
from Backend.services.agent.telemetry import CLASSES

OTHER = "OTHER"

# Rótulo externo (normalizado: minúsculo, espaços colapsados) → classe do agente.
LABEL_MAPS: dict[str, dict[str, str]] = {
    "UNSW-NB15": {
        "normal": "NORMAL",
        "dos": "DDOS_ATTACK",
        "reconnaissance": "PORT_SCAN",
        "backdoor": OTHER,
        "analysis": OTHER,
        "fuzzers": OTHER,
        "exploits": OTHER,
        "generic": OTHER,
        "shellcode": OTHER,
        "worms": OTHER,
    },
    "CSE-CIC-IDS2018": {
        "benign": "NORMAL",
        "dos attacks-goldeneye": "DDOS_ATTACK",
        "dos attacks-slowloris": "DDOS_ATTACK",
        "dos attacks-hulk": "DDOS_ATTACK",
        "dos attacks-slowhttptest": "DDOS_ATTACK",
        "ddos attacks-loic-http": "DDOS_ATTACK",
        "ddos attack-loic-udp": "DDOS_ATTACK",
        "ddos attack-hoe": "DDOS_ATTACK",
        "infilteration": "DATA_EXFILTRATION",
        "bot": OTHER,
        "ftp-bruteforce": OTHER,
        "ssh-bruteforce": OTHER,
        "brute force -web": OTHER,
        "brute force -xss": OTHER,
        "sql injection": OTHER,
    },
}

# Feature canônica → coluna do dataset (proxy documentado) ou None (ausente).
FEATURE_PROXIES: dict[str, dict[str, str | None]] = {
    "UNSW-NB15": {
        "latency_ms": None,
        "packet_loss_pct": None,
        "jitter_ms": "sjit",
        "cpu_usage_pct": None,
        "ram_usage_pct": None,
        "disk_usage_pct": None,
        "network_in_bps": "sload",
        "network_out_bps": "dload",
        "http_status_code": None,
        "http_response_time_ms": None,
        "tcp_port_open": None,
        "active_connections": "ct_srv_src",
    },
    "CSE-CIC-IDS2018": {
        "latency_ms": "flow iat mean",
        "packet_loss_pct": None,
        "jitter_ms": "flow iat std",
        "cpu_usage_pct": None,
        "ram_usage_pct": None,
        "disk_usage_pct": None,
        "network_in_bps": "flow byts/s",
        "network_out_bps": None,
        "http_status_code": None,
        "http_response_time_ms": None,
        "tcp_port_open": None,
        "active_connections": None,
    },
}


def _normalize_key(label: Any) -> str:
    return " ".join(str(label).strip().lower().split())


def map_label(dataset: str, label: Any) -> str:
    """Classe do agente para um rótulo externo; `OTHER` se não mapear."""
    table = LABEL_MAPS.get(dataset, {})
    key = _normalize_key(label)
    if key in table:
        return table[key]
    for prefix, mapped in table.items():
        if key.startswith(prefix):
            return mapped
    return OTHER


@dataclass
class ExternalLoad:
    split: DatasetSplit
    report: dict[str, Any]
    dropped_labels: dict[str, int] = field(default_factory=dict)


def _read_table(source: str | Path | pd.DataFrame) -> pd.DataFrame:
    if isinstance(source, pd.DataFrame):
        return source
    path = Path(source)
    if path.suffix in (".parquet", ".pq"):
        return pd.read_parquet(path)
    return pd.read_csv(path)


def _extract_features(
    df: pd.DataFrame, dataset: str
) -> tuple[np.ndarray, list[str], dict[str, str | None]]:
    from Backend.services.agent.telemetry import FEATURE_FIELDS

    proxy = FEATURE_PROXIES.get(dataset, {})
    columns = {name: name for name in df.columns}
    lowered = {_normalize_key(col): col for col in df.columns}
    missing: list[str] = []
    source_of: dict[str, str | None] = {}
    columns_data: list[Iterable[float]] = []
    for feature in FEATURE_FIELDS:
        src: str | None = None
        if feature in columns:
            src = feature
        elif proxy.get(feature):
            src = lowered.get(_normalize_key(proxy[feature]))
        source_of[feature] = src
        if src is None:
            missing.append(feature)
            columns_data.append([np.nan] * len(df))
        else:
            columns_data.append(pd.to_numeric(df[src], errors="coerce"))
    array = np.column_stack([np.asarray(col, dtype=float) for col in columns_data])
    return array, missing, source_of


def load_external(
    source: str | Path | pd.DataFrame,
    dataset: str,
    *,
    label_column: str = "Label",
    name: str | None = None,
) -> ExternalLoad:
    """Carrega e mapeia um dataset externo em `DatasetSplit`.

    Linhas cujo rótulo não mapeia (`OTHER`) são descartadas e contadas.
    """
    df = _read_table(source)
    if label_column not in df.columns:
        raise KeyError(f"{dataset}: coluna de rótulo {label_column!r} ausente")

    mapped = [map_label(dataset, value) for value in df[label_column]]
    keep = np.array([label in CLASSES for label in mapped], dtype=bool)
    X, missing, source_of = _extract_features(df, dataset)
    X = X[keep]
    y = np.array([label for label in mapped if label in CLASSES], dtype=object)

    dropped_labels: dict[str, int] = {}
    for raw, label in zip(df[label_column], mapped):
        if label not in CLASSES:
            key = _normalize_key(raw)
            dropped_labels[key] = dropped_labels.get(key, 0) + 1

    per_class: dict[str, int] = {}
    for label in y:
        per_class[str(label)] = per_class.get(str(label), 0) + 1

    split = DatasetSplit(
        X=X,
        y=y,
        severity=np.zeros(len(y), dtype=float),
        groups=np.array([f"external:{dataset}:{i}" for i in range(len(y))], dtype=object),
        times=np.arange(len(y), dtype=float),
        meta={
            "kind": "external",
            "role": "holdout",
            "name": name or dataset,
            "source": dataset,
        },
    )
    report = {
        "dataset": dataset,
        "n_rows": int(len(df)),
        "n_used": int(len(y)),
        "dropped_other": int(len(df) - len(y)),
        "per_class": per_class,
        "missing_features": missing,
        "feature_source": source_of,
    }
    return ExternalLoad(split=split, report=report, dropped_labels=dropped_labels)
