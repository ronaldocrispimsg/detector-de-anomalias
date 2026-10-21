"""Guarda anti-vazamento do RAG e ablação on/off."""

from __future__ import annotations

import json

import numpy as np

from Backend.harness.config import ExperimentConfig
from Backend.harness.engines.llm_agent import LLMAgentEngine
from Backend.harness.engines.rag_retriever import RagRetriever, run_rag_ablation
from Backend.harness.splits import make_regime_splits
from Backend.services.agent.memory import (
    MemoryIndex,
    assert_no_label_leakage,
    query_text,
)
from Backend.services.agent.models import MockProvider
from Backend.services.agent.telemetry import Telemetry


def _splits(n_per_class: int = 4):
    return make_regime_splits(n_per_class=n_per_class, seed=3)


def _queries(split, n: int = 12) -> list[str]:
    return [query_text(Telemetry.from_features(row)) for row in split.X[:n]]


def test_no_label_leakage_in_documents_ids_and_queries():
    splits = _splits()
    index = MemoryIndex.from_split(splits["train"], docs_per_class=2)
    assert_no_label_leakage(index, _queries(splits["test"]))


def test_index_uses_only_train_groups():
    splits = _splits()
    index = MemoryIndex.from_split(splits["train"], docs_per_class=2)
    assert index.source_groups
    assert all(group.startswith("regime:train:") for group in index.source_groups)


def test_retrieval_depends_only_on_features():
    splits = _splits()
    index = MemoryIndex.from_split(splits["train"], docs_per_class=2)
    row = splits["test"].X[0]
    sample = Telemetry.from_features(row)
    first = index.retrieve_ids(sample, k=3)
    second = index.retrieve_ids(Telemetry.from_features(np.array(row, copy=True)), k=3)
    assert first == second


def test_retrieval_precision_in_range():
    splits = _splits()
    index = MemoryIndex.from_split(splits["train"], docs_per_class=3)
    retriever = RagRetriever(index=index, k=3)
    precision = retriever.retrieval_precision(splits["test"].X, splits["test"].y)
    assert 0.0 <= precision <= 1.0


def _mock_json(prompt: str) -> str:
    return json.dumps(
        {
            "predicted_scenario": "NORMAL",
            "is_anomaly": False,
            "confidence": 0.5,
            "severity": "OK",
            "root_cause": "",
            "remediation_playbook": [],
        }
    )


def test_rag_ablation_machinery(tmp_path):
    splits = _splits(n_per_class=6)
    config = ExperimentConfig(
        name="rag_ablation_test",
        dataset_id="regime",
        split_id="test",
        engine="llm_agent",
        seed=0,
        metrics=("macro_f1",),
    )

    def factory(retriever):
        context_fn = retriever.retrieve if retriever is not None else None
        return LLMAgentEngine(
            MockProvider(responder=_mock_json), context_fn=context_fn, max_retries=0
        )

    result = run_rag_ablation(
        config, splits, factory, k=3, results_dir=str(tmp_path), n_boot=100
    )
    assert {"with_rag", "without_rag", "mcnemar", "n"} <= set(result)
    assert (tmp_path / "rag_ablation.jsonl").exists()
    line = json.loads((tmp_path / "rag_ablation.jsonl").read_text().splitlines()[0])
    assert "with_rag" in line and "mcnemar" in line
