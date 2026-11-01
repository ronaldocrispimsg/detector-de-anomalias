"""Registro de execuções.

Cada trial vira uma linha JSONL em results/runs.jsonl e uma entrada no índice
results/index.json, consultável por run_id ou config_hash.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from Backend.harness.config import canonical_json, sha256_of


class RunRegistry:
    def __init__(self, results_dir: str | Path) -> None:
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.runs_path = self.results_dir / "runs.jsonl"
        self.index_path = self.results_dir / "index.json"

    def _load_index(self) -> dict[str, Any]:
        if self.index_path.exists():
            return json.loads(self.index_path.read_text(encoding="utf-8"))
        return {}

    def _save_index(self, index: dict[str, Any]) -> None:
        self.index_path.write_text(canonical_json(index), encoding="utf-8")

    def write(self, record: dict[str, Any]) -> dict[str, Any]:
        with self.runs_path.open("a", encoding="utf-8") as fh:
            fh.write(canonical_json(record) + "\n")
        index = self._load_index()
        index[record["run_id"]] = {
            "config_hash": record["config_hash"],
            "canonical_hash": record["canonical_hash"],
            "engine": record["engine"],
            "n_samples": record["n_samples"],
        }
        self._save_index(index)
        return record

    def get(self, run_id: str) -> dict[str, Any] | None:
        if not self.runs_path.exists():
            return None
        for line in self.runs_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if record["run_id"] == run_id:
                return record
        return None

    def find_by_config(self, config_hash: str) -> list[dict[str, Any]]:
        index = self._load_index()
        return [rid for rid, meta in index.items() if meta["config_hash"] == config_hash]


def canonical_record_hash(
    config_hash: str,
    dataset_id: str,
    split_id: str,
    engine: str,
    y_true: list[str],
    y_pred: list[str],
    metrics: dict[str, Any],
) -> str:
    """Hash estável do que define o resultado, ignorando timestamp/run_id."""
    payload = {
        "config_hash": config_hash,
        "dataset_id": dataset_id,
        "split_id": split_id,
        "engine": engine,
        "y_true": y_true,
        "y_pred": y_pred,
        "metrics": metrics,
    }
    return sha256_of(payload)
