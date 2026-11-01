"""Fase 07: correspondência de evidência, rubrica e fidelidade contrafactual."""

from __future__ import annotations

import json
import random

import numpy as np

from Backend.harness.training.build_sft import assistant_target
from Backend.services.agent.guardrails import parse_output
from Backend.services.agent.telemetry import Telemetry
from Backend.services.agent.xai import (
    counterfactual_fidelity,
    evidence_matches_telemetry,
    occlusion_importance,
    permutation_importance,
    rubric_score,
    xai_report,
)

from Backend.services.anomaly_simulator import AnomalySimulator


def _sample(scenario="DDOS_ATTACK", severity=0.7) -> Telemetry:
    sim = AnomalySimulator()
    raw = sim.generate_sample(scenario, timestamp=0.0, severity=severity, rng=random.Random(0))
    return Telemetry.from_mapping(raw.model_dump())


def _output(sample: Telemetry, label: str = "DDOS_ATTACK"):
    return parse_output(assistant_target(sample, label))


def test_evidence_non_empty_and_matches_telemetry():
    sample = _sample()
    output = _output(sample)
    assert output is not None and not output.abstain
    assert output.evidence
    assert all(evidence_matches_telemetry(output, sample))


def test_evidence_mismatch_detected():
    sample = _sample()
    output = _output(sample)
    output.evidence[0]["value"] = output.evidence[0]["value"] + 1000
    assert not all(evidence_matches_telemetry(output, sample))


def test_counterfactual_control_changes_class():
    def predict_fn(sample: Telemetry) -> str:
        return "HOST_DOWN" if sample.latency_ms > 200 else "NORMAL"

    sample = _sample()
    low = sample.__class__(**{**sample.to_mapping(), "latency_ms": 100.0})
    result = counterfactual_fidelity(predict_fn, low, "latency_ms", factor=3.0)
    assert result["original"] == "NORMAL"
    assert result["perturbed"] == "HOST_DOWN"
    assert result["changed"] is True


def test_rubric_and_occlusion_with_random_forest():
    from sklearn.ensemble import RandomForestClassifier

    from Backend.harness.splits import make_regime_splits

    splits = make_regime_splits(n_per_class=6, seed=1)
    model = RandomForestClassifier(n_estimators=50, random_state=0).fit(
        splits["train"].X, splits["train"].y
    )
    importance = permutation_importance(model, splits["test"].X, splits["test"].y, n_repeats=3)
    assert set(importance) == set(Telemetry.from_features(splits["test"].X[0]).to_mapping())

    sample = Telemetry.from_features(splits["test"].X[0])
    occlusion = occlusion_importance(model, sample, _sample("NORMAL", 0.0), classes=splits["test"].y)
    assert len(occlusion) == 12


def test_xai_report_per_class():
    splits_labels = ["NORMAL", "DDOS_ATTACK", "PORT_SCAN"]
    samples = [_sample(label, 0.0 if label == "NORMAL" else 0.6) for label in splits_labels]
    outputs = [_output(sample, label) for sample, label in zip(samples, splits_labels)]
    report = xai_report(outputs, samples, splits_labels)
    assert set(report) == set(splits_labels)
    for entry in report.values():
        assert 0.0 <= entry["mean_rubric"] <= 3.0
        assert entry["evidence_agreement"] == 1.0
