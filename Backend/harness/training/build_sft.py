"""Construção do dataset de SFT, a partir do split de treino.

Cada exemplo é um chat: system (tarefa + classes + schema), user (telemetria
serializada, sem rótulo) e assistant (JSON-alvo). O user nunca contém o rótulo;
o assistant é a resposta supervisionada.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from Backend.services.agent.policy import SYSTEM_INSTRUCTIONS
from Backend.services.agent.representation import serialize
from Backend.services.agent.telemetry import (
    CLASSES,
    FEATURE_FIELDS,
    SEVERITY_BY_SCENARIO,
    Telemetry,
)

_HIGH_SIGNAL = {
    "HOST_DOWN": ["packet_loss_pct", "http_status_code"],
    "DDOS_ATTACK": ["latency_ms", "active_connections"],
    "MEMORY_LEAK": ["ram_usage_pct", "active_connections"],
    "DDOS_ATTACK_ALT": ["network_out_bps"],
    "DISK_EXHAUSTION": ["disk_usage_pct"],
    "PORT_SCAN": ["tcp_port_open"],
    "SERVICE_OUTAGE": ["http_status_code", "http_response_time_ms"],
    "NETWORK_CONGESTION": ["latency_ms", "jitter_ms", "packet_loss_pct"],
    "DATA_EXFILTRATION": ["network_out_bps", "network_in_bps"],
    "COMBINED_FAULT": ["latency_ms", "cpu_usage_pct", "disk_usage_pct"],
    "NORMAL": [],
}


def _evidence(sample: Telemetry) -> list[dict[str, Any]]:
    mapping = sample.to_mapping()
    return [
        {"metric": name, "value": round(float(mapping[name]), 2)}
        for name in ("latency_ms", "cpu_usage_pct", "ram_usage_pct")
    ]


def assistant_target(sample: Telemetry, label: str) -> str:
    if label not in CLASSES:
        raise ValueError(f"rótulo fora das classes: {label!r}")
    payload = {
        "predicted_scenario": label,
        "is_anomaly": label != "NORMAL",
        "confidence": 0.95,
        "severity": SEVERITY_BY_SCENARIO.get(label, "OK"),
        "evidence": _evidence(sample),
        "root_cause": f"padrão compatível com {label}",
        "impact": "",
        "remediation_playbook": [],
    }
    return json.dumps(payload, ensure_ascii=False)


def build_sft_pairs(split: Any, *, limit: int | None = None) -> list[dict[str, Any]]:
    rows = np.asarray(split.X, dtype=float)
    labels = [str(v) for v in np.asarray(split.y).tolist()]
    pairs: list[dict[str, Any]] = []
    for row, label in zip(rows, labels):
        sample = Telemetry.from_features(row)
        user = serialize(sample)
        for name in CLASSES:
            if name in user:
                raise AssertionError(f"vazamento de rótulo '{name}' no prompt do user")
        pairs.append(
            {
                "messages": [
                    {"role": "system", "content": SYSTEM_INSTRUCTIONS},
                    {"role": "user", "content": user},
                    {"role": "assistant", "content": assistant_target(sample, label)},
                ]
            }
        )
        if limit is not None and len(pairs) >= limit:
            break
    return pairs


def write_sft_jsonl(pairs: Sequence[dict[str, Any]], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for pair in pairs:
            fh.write(json.dumps(pair, ensure_ascii=False) + "\n")
    return path


def build_and_write(split: Any, path: str | Path, *, limit: int | None = None) -> Path:
    return write_sft_jsonl(build_sft_pairs(split, limit=limit), path)
