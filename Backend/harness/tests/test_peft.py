"""Fase 05: dataset SFT, spec LoRA/QLoRA, comparativo e model card."""

from __future__ import annotations

import json

import numpy as np
import pytest

from Backend.harness.splits import make_regime_splits
from Backend.harness.training.build_sft import build_sft_pairs
from Backend.harness.training.compare import render_model_card, run_peft_comparison
from Backend.harness.training.train_peft import (
    LoraSpec,
    load_base_model,
    qlora_supported,
)
from Backend.services.agent.guardrails import validate_output
from Backend.services.agent.telemetry import CLASSES


def _splits(n_per_class: int = 3):
    return make_regime_splits(n_per_class=n_per_class, seed=5)


def test_sft_pairs_structure_and_no_label_in_user():
    splits = _splits()
    pairs = build_sft_pairs(splits["train"], limit=8)
    assert pairs
    for pair in pairs:
        roles = [m["role"] for m in pair["messages"]]
        assert roles == ["system", "user", "assistant"]
        user = pair["messages"][1]["content"]
        for name in CLASSES:
            assert name not in user
        target = json.loads(pair["messages"][2]["content"])
        parsed = validate_output(target)
        assert parsed.predicted_scenario in CLASSES


def test_sft_uses_only_train_split():
    splits = _splits(n_per_class=4)
    pairs = build_sft_pairs(splits["train"])
    assert len(pairs) == len(splits["train"])


def test_lora_spec_enforces_alpha_and_serializes():
    spec = LoraSpec(r=8, alpha=16)
    assert spec.to_dict()["target_modules"] == ["q_proj", "k_proj", "v_proj", "o_proj"]
    with pytest.raises(ValueError):
        LoraSpec(r=8, alpha=8)


def test_qlora_requires_cuda():
    if qlora_supported():
        pytest.skip("máquina com CUDA+bitsandbytes: guard não se aplica")
    with pytest.raises(RuntimeError):
        load_base_model(LoraSpec(quant_4bit=True), "Qwen/Qwen2.5-1.5B-Instruct")


def test_lora_config_via_peft():
    peft = pytest.importorskip("peft")
    config = LoraSpec(r=16, alpha=32).to_lora_config()
    assert config.r == 16 and config.lora_alpha == 32
    assert "q_proj" in config.target_modules


class _FakeEngine:
    def __init__(self, preds, engine_id="fake"):
        self.preds = np.asarray(preds, dtype=object)
        self.id = engine_id
        self.outputs = []

    def predict(self, X):
        return self.preds


def test_peft_comparison_runs_hypotheses(tmp_path):
    splits = _splits(n_per_class=4)
    y_true = np.asarray([str(v) for v in splits["test"].y.tolist()], dtype=object)
    zero = _FakeEngine(np.full(len(y_true), "NORMAL"), "zero_shot")
    lora = _FakeEngine(y_true.copy(), "lora")

    summary = run_peft_comparison(
        splits,
        {"zero_shot": lambda: zero, "lora": lambda: lora},
        reference="zero_shot",
        fine_tuned="lora",
        best_baseline=0.5,
        results_dir=str(tmp_path),
        n_boot=100,
    )
    assert summary["H1_confirmed"] is True
    assert summary["H2_confirmed"] is True
    assert summary["delta_fine_tuned_minus_reference"] > 0.05
    assert "mcnemar_reference_vs_fine_tuned" in summary
    assert (tmp_path / "peft_comparison.jsonl").exists()


def test_model_card_renders_fields(tmp_path):
    card = render_model_card(
        base_model="Qwen/Qwen2.5-7B-Instruct",
        adapter_version="lora-v1",
        data_description="regime de treino (simulado)",
        hyperparameters={"r": 16, "alpha": 32},
        metrics={"macro_f1": 0.42},
        limitations=["teste em regime sutil"],
        path=tmp_path / "model_card.md",
    )
    assert "Qwen/Qwen2.5-7B-Instruct" in card
    assert "lora-v1" in card
    assert (tmp_path / "model_card.md").exists()
