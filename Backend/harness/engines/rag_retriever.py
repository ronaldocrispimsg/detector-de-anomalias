"""Retriever RAG do harness e ablação RAG on/off.

Envolve `MemoryIndex` e oferece a métrica de precisão do retrieval. A ablação
compara o agente com e sem contexto recuperado, com IC bootstrap e McNemar.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np

from Backend.harness.metrics import macro_f1
from Backend.harness.stats import bootstrap_ci_metric, mcnemar
from Backend.services.agent.memory import MemoryIndex
from Backend.services.agent.telemetry import Telemetry


@dataclass
class RagRetriever:
    index: MemoryIndex
    k: int = 3

    def retrieve(self, sample: Telemetry) -> list[str]:
        return self.index.retrieve(sample, k=self.k)

    def retrieval_precision(self, X: Any, y: Sequence[Any]) -> float:
        """Fração de vizinhos recuperados cujo rótulo interno bate com o real."""
        labels = self.index.hidden_labels()
        rows = np.asarray(X, dtype=float)
        truth = [str(v) for v in np.asarray(y).tolist()]
        hits = 0
        total = 0
        for row, real in zip(rows, truth):
            sample = Telemetry.from_features(row)
            ranked = self.index._rank(sample)[: self.k]
            for _, doc in ranked:
                total += 1
                if str(doc.meta.get("label")) == real:
                    hits += 1
        return hits / total if total else 0.0


def run_rag_ablation(
    config: Any,
    splits: dict[str, Any],
    engine_factory: Any,
    *,
    k: int = 3,
    results_dir: str | None = None,
    n_boot: int = 1000,
) -> dict[str, Any]:
    """Compara agente sem RAG e com RAG no mesmo teste.

    `engine_factory(retriever_or_none) -> Engine`. Cada motor roda uma só vez.
    """
    import json
    from pathlib import Path

    test = splits["test"]
    index = MemoryIndex.from_split(splits["train"], docs_per_class=4)
    retriever = RagRetriever(index=index, k=k)

    y_true = np.asarray([str(v) for v in test.y.tolist()], dtype=object)
    y_off = _predict(engine_factory(None), test.X)
    y_on = _predict(engine_factory(retriever), test.X)

    ci_off = bootstrap_ci_metric(y_true, y_off, macro_f1, n_boot=n_boot, seed=config.seed)
    ci_on = bootstrap_ci_metric(y_true, y_on, macro_f1, n_boot=n_boot, seed=config.seed)
    result = {
        "k": k,
        "retrieval_precision": retriever.retrieval_precision(test.X, test.y),
        "without_rag": {"macro_f1": macro_f1(y_true, y_off), "ci": ci_off},
        "with_rag": {"macro_f1": macro_f1(y_true, y_on), "ci": ci_on},
        "mcnemar": mcnemar(y_true, y_off, y_on),
        "n": int(len(y_true)),
    }
    if results_dir is not None:
        out = Path(results_dir)
        out.mkdir(parents=True, exist_ok=True)
        with (out / "rag_ablation.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(result, ensure_ascii=False) + "\n")
    return result


def _predict(engine: Any, X: Any) -> np.ndarray:
    return np.asarray([str(v) for v in engine.predict(X)], dtype=object)
