"""Configuração de experimentos.

Uma config descreve o que será executado (dataset, split, motor, métricas) e
tem um hash canônico estável usado no run_id e na detecção de duplicatas.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def canonical_json(obj: Any) -> str:
    """Serializa de forma determinística (chaves ordenadas, sem espaços)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_of(obj: Any) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ExperimentConfig:
    """Configuração imutável de um experimento."""

    name: str
    dataset_id: str
    split_id: str
    engine: str
    seed: int = 0
    engine_params: dict[str, Any] = field(default_factory=dict)
    metrics: tuple[str, ...] = ("macro_f1", "balanced_accuracy")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "dataset_id": self.dataset_id,
            "split_id": self.split_id,
            "engine": self.engine,
            "seed": self.seed,
            "engine_params": dict(self.engine_params),
            "metrics": list(self.metrics),
        }

    @property
    def config_hash(self) -> str:
        return sha256_of(self.to_dict())[:16]


def config_from_dict(data: dict[str, Any]) -> ExperimentConfig:
    metrics = data.get("metrics", ("macro_f1", "balanced_accuracy"))
    return ExperimentConfig(
        name=str(data["name"]),
        dataset_id=str(data["dataset_id"]),
        split_id=str(data["split_id"]),
        engine=str(data["engine"]),
        seed=int(data.get("seed", 0)),
        engine_params=dict(data.get("engine_params", {})),
        metrics=tuple(metrics),
    )


def load_config(path: str | Path) -> ExperimentConfig:
    """Carrega config de um .json (stdlib) ou .yaml (se pyyaml existir)."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if path.suffix in {".yaml", ".yml"}:
        import yaml  # opcional

        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    return config_from_dict(data)
