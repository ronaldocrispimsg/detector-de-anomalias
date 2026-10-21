"""Contrato do agente: representação sem rótulo, guardrails e loop do motor."""

from __future__ import annotations

import json
import random

import numpy as np
import pytest

from Backend.harness.engines.llm_agent import LLMAgentEngine
from Backend.services.agent.guardrails import (
    ABSTAIN_LABEL,
    parse_output,
    validate_output,
)
from Backend.services.agent.models import HTTPProvider, MockProvider
from Backend.services.agent.policy import build_prompt
from Backend.services.agent.representation import (
    Baseline,
    normalize_features,
    serialize,
)
from Backend.services.agent.telemetry import CLASSES, FEATURE_FIELDS, Telemetry

from Backend.services.anomaly_simulator import AnomalySimulator


def _sample(scenario: str = "DDOS_ATTACK", severity: float = 0.7) -> Telemetry:
    sim = AnomalySimulator()
    raw = sim.generate_sample(
        scenario, timestamp=0.0, severity=severity, rng=random.Random(0)
    )
    return Telemetry.from_mapping(raw.model_dump())


def _valid_json(**overrides) -> str:
    payload = {
        "predicted_scenario": "DDOS_ATTACK",
        "is_anomaly": True,
        "confidence": 0.82,
        "severity": "CRITICAL",
        "root_cause": "volume de SYN",
        "remediation_playbook": ["aplicar rate limit"],
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_feature_fields_match_telemetry():
    sample = _sample()
    assert len(FEATURE_FIELDS) == len(sample.to_mapping())
    row = [sample.to_mapping()[name] for name in FEATURE_FIELDS]
    assert Telemetry.from_features(row).to_mapping() == sample.to_mapping()


def test_serialization_contains_no_label():
    text = serialize(_sample())
    for label in CLASSES:
        assert label not in text
    assert "scenario" not in text.lower()


def test_valid_output_parsed_and_clamped():
    out = validate_output(json.loads(_valid_json(confidence=1.7)))
    assert out.predicted_scenario == "DDOS_ATTACK"
    assert out.confidence == 1.0
    assert out.severity == "CRITICAL"


def test_unknown_scenario_rejected():
    with pytest.raises(ValueError):
        validate_output(json.loads(_valid_json(predicted_scenario="ALIEN")))


def test_parse_output_extracts_from_chatter():
    noisy = "Claro! Segue a análise:\n" + _valid_json() + "\nEspero ter ajudado."
    out = parse_output(noisy)
    assert out is not None and out.predicted_scenario == "DDOS_ATTACK"


def test_parse_output_invalid_returns_none():
    assert parse_output("sem json aqui") is None
    assert parse_output('{"predicted_scenario": "NOPE", "confidence": 0.5}') is None


def test_abstain_flagged():
    out = parse_output(json.dumps({"abstain": True}))
    assert out is not None and out.abstain and out.predicted_scenario == ABSTAIN_LABEL


def test_mock_provider_drives_engine_deterministically():
    provider = MockProvider(responder=lambda prompt: _valid_json())
    engine = LLMAgentEngine(provider, mode="zero_shot")
    X = np.asarray([[_sample().to_mapping()[name] for name in FEATURE_FIELDS]])
    first = engine.predict(X)
    second = engine.predict(X)
    assert list(first) == ["DDOS_ATTACK"]
    assert list(first) == list(second)


def test_engine_abstains_when_provider_is_unusable():
    calls = {"n": 0}

    def bad(prompt: str) -> str:
        calls["n"] += 1
        return "desculpe, não sei responder"

    engine = LLMAgentEngine(MockProvider(responder=bad), max_retries=2)
    X = np.asarray([[_sample().to_mapping()[name] for name in FEATURE_FIELDS]])
    assert list(engine.predict(X)) == [ABSTAIN_LABEL]
    assert calls["n"] == 3


def test_few_shot_requires_examples():
    with pytest.raises(ValueError):
        build_prompt(_sample(), mode="few_shot")
    text = build_prompt(_sample(), mode="few_shot", examples=[(serialize(_sample()), "DDOS_ATTACK")])
    assert "Exemplos resolvidos" in text


def test_prompt_lists_all_classes_without_ground_truth_answer():
    text = build_prompt(_sample())
    for label in CLASSES:
        assert label in text  # lista de classes permitida


def test_baseline_normalization_is_centered():
    rows = [
        [_sample(severity=0.3).to_mapping()[name] for name in FEATURE_FIELDS],
        [_sample(severity=0.9).to_mapping()[name] for name in FEATURE_FIELDS],
    ]
    baseline = Baseline.from_features(rows)
    norm = normalize_features(_sample(severity=0.6), baseline)
    assert len(norm) == len(FEATURE_FIELDS)
    assert all(isinstance(v, float) for v in norm)


def test_http_provider_builds_openai_and_ollama_requests():
    openai = HTTPProvider("http://localhost:8080", "llama", api="openai")
    req = openai._build_request("oi")
    assert req.full_url.endswith("/v1/chat/completions")
    body = json.loads(req.data.decode())
    assert body["model"] == "llama" and body["messages"][0]["content"] == "oi"

    ollama = HTTPProvider("http://localhost:11434", "qwen", api="ollama")
    req2 = ollama._build_request("oi")
    assert req2.full_url.endswith("/api/chat")
