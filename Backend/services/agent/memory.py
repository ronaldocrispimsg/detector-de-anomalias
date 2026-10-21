"""Memória de recuperação (RAG) sem vazamento de rótulo.

Indexa apenas o split de treino. Cada documento é um **perfil estatístico** de
um bloco de amostras, com id opaco; o texto e o id nunca contêm o nome do
cenário. O rótulo fica só em metadado interno, usado para medir a qualidade do
retrieval — nunca injetado no prompt.

A similaridade é numérica (features normalizadas pelo baseline do treino),
robusta para dados tabulares; embedding de texto é opcional e plugável.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np

from Backend.services.agent.representation import Baseline
from Backend.services.agent.telemetry import CLASSES, FEATURE_FIELDS, Telemetry

_QUANTILES = (10, 90)


@dataclass
class Document:
    doc_id: str
    text: str
    centroid: np.ndarray
    meta: dict[str, Any] = field(default_factory=dict)


def _profile_text(stats: dict[str, dict[str, float]], n: int) -> str:
    lines = ["perfil_historico_de_host:", f"- n_amostras: {n}"]
    for name in FEATURE_FIELDS:
        s = stats[name]
        lines.append(
            f"- {name}: media={s['mean']:.2f} desvio={s['std']:.2f} "
            f"p10={s['p10']:.2f} p90={s['p90']:.2f}"
        )
    return "\n".join(lines)


def _feature_stats(block: np.ndarray) -> dict[str, dict[str, float]]:
    stats: dict[str, dict[str, float]] = {}
    for j, name in enumerate(FEATURE_FIELDS):
        column = block[:, j]
        stats[name] = {
            "mean": float(column.mean()),
            "std": float(column.std()),
            "p10": float(np.percentile(column, 10)),
            "p90": float(np.percentile(column, 90)),
        }
    return stats


def _zscore(vector: np.ndarray, baseline: Baseline) -> np.ndarray:
    mean = np.asarray(baseline.mean, dtype=float)
    std = np.asarray(baseline.std, dtype=float)
    return (vector - mean) / std


@dataclass
class MemoryIndex:
    documents: list[Document]
    baseline: Baseline
    source_groups: set[str] = field(default_factory=set)

    @classmethod
    def from_split(
        cls,
        split: Any,
        *,
        docs_per_class: int = 1,
        id_prefix: str = "doc",
    ) -> "MemoryIndex":
        baseline = Baseline.from_features(split.X)
        X = np.asarray(split.X, dtype=float)
        y = np.asarray(split.y)
        documents: list[Document] = []
        counter = 0
        for label in CLASSES:
            idx = np.where(y == label)[0]
            if idx.size == 0:
                continue
            blocks = np.array_split(idx, max(1, docs_per_class))
            for block_idx in blocks:
                if block_idx.size == 0:
                    continue
                block = X[block_idx]
                centroid = _zscore(block.mean(axis=0), baseline)
                documents.append(
                    Document(
                        doc_id=f"{id_prefix}-{counter:04d}",
                        text=_profile_text(_feature_stats(block), int(block.shape[0])),
                        centroid=centroid,
                        meta={"label": str(label), "n": int(block.shape[0])},
                    )
                )
                counter += 1
        groups = set()
        if hasattr(split, "groups"):
            groups = {str(g) for g in set(np.asarray(split.groups).tolist())}
        return cls(documents=documents, baseline=baseline, source_groups=groups)

    def _query_vector(self, sample: Telemetry) -> np.ndarray:
        from Backend.services.agent.representation import to_features

        return _zscore(np.asarray(to_features(sample), dtype=float), self.baseline)

    def _rank(self, sample: Telemetry) -> list[tuple[float, Document]]:
        query = self._query_vector(sample)
        qnorm = np.linalg.norm(query) or 1.0
        scored: list[tuple[float, Document]] = []
        for doc in self.documents:
            dnorm = np.linalg.norm(doc.centroid) or 1.0
            similarity = float(np.dot(query, doc.centroid) / (qnorm * dnorm))
            scored.append((similarity, doc))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return scored

    def retrieve(self, sample: Telemetry, k: int = 3) -> list[str]:
        return [doc.text for _, doc in self._rank(sample)[:k]]

    def retrieve_ids(self, sample: Telemetry, k: int = 3) -> list[str]:
        return [doc.doc_id for _, doc in self._rank(sample)[:k]]

    def hidden_labels(self) -> list[str]:
        return [str(doc.meta.get("label", "")) for doc in self.documents]


def query_text(sample: Telemetry) -> str:
    """Query textual da telemetria, sem rótulo."""
    from Backend.services.agent.representation import serialize

    return serialize(sample)


def assert_no_label_leakage(index: MemoryIndex, queries: Sequence[str]) -> None:
    """Falha se qualquer nome de cenário aparecer em documento, id ou query."""
    haystacks = [doc.text for doc in index.documents]
    haystacks += [doc.doc_id for doc in index.documents]
    haystacks += list(queries)
    for needle in CLASSES:
        for hay in haystacks:
            if needle in hay:
                raise AssertionError(f"vazamento de rótulo '{needle}' em: {hay[:80]!r}")
