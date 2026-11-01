"""Guardrails do contrato do agente.

Extrai, valida e normaliza a saída do modelo para o schema da SPEC. Saída
inválida nunca vira decisão: vira `None` (o loop do agente decide o retry ou a
abstenção).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from Backend.services.agent.telemetry import CLASSES, SEVERITY_BY_SCENARIO

ABSTAIN_LABEL = "ABSTAIN"


@dataclass
class AgentOutput:
    predicted_scenario: str
    is_anomaly: bool
    confidence: float
    severity: str = "OK"
    evidence: list[dict[str, Any]] = field(default_factory=list)
    root_cause: str = ""
    impact: str = ""
    remediation_playbook: list[str] = field(default_factory=list)
    probabilities: dict[str, float] = field(default_factory=dict)
    abstain: bool = False
    model_id: str = ""
    prompt_version: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "predicted_scenario": self.predicted_scenario,
            "is_anomaly": self.is_anomaly,
            "confidence": self.confidence,
            "severity": self.severity,
            "evidence": self.evidence,
            "root_cause": self.root_cause,
            "impact": self.impact,
            "remediation_playbook": self.remediation_playbook,
            "probabilities": self.probabilities,
            "abstain": self.abstain,
            "model_id": self.model_id,
            "prompt_version": self.prompt_version,
        }


def _extract_balanced(text: str) -> str | None:
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        char = text[i]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def extract_json(text: str) -> str | None:
    if text is None:
        return None
    candidate = text.strip()
    if candidate.startswith("{"):
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass
    return _extract_balanced(text)


def _coerce_probabilities(raw: Any) -> dict[str, float]:
    if not isinstance(raw, dict):
        return {}
    result: dict[str, float] = {}
    for key, value in raw.items():
        label = str(key).strip().upper()
        if label in CLASSES:
            try:
                result[label] = float(value)
            except (TypeError, ValueError):
                continue
    return result


def validate_output(
    data: Any, *, model_id: str = "", prompt_version: str = ""
) -> AgentOutput:
    if not isinstance(data, dict):
        raise ValueError("saída não é um objeto JSON")

    abstain = bool(data.get("abstain", False))
    if abstain:
        return AgentOutput(
            predicted_scenario=ABSTAIN_LABEL,
            is_anomaly=False,
            confidence=0.0,
            severity="UNKNOWN",
            abstain=True,
            model_id=model_id,
            prompt_version=prompt_version,
        )

    scenario = str(data.get("predicted_scenario", "")).strip().upper()
    if scenario not in CLASSES:
        raise ValueError(f"cenário inválido: {scenario!r}")

    try:
        confidence = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        raise ValueError("confiança inválida")
    confidence = max(0.0, min(1.0, confidence))

    severity = str(data.get("severity") or SEVERITY_BY_SCENARIO.get(scenario, "OK")).upper()
    is_anomaly = bool(data.get("is_anomaly", scenario != "NORMAL"))

    evidence = data.get("evidence", [])
    if not isinstance(evidence, list):
        evidence = []
    playbook = data.get("remediation_playbook", [])
    if not isinstance(playbook, list):
        playbook = []

    return AgentOutput(
        predicted_scenario=scenario,
        is_anomaly=is_anomaly,
        confidence=confidence,
        severity=severity,
        evidence=[e for e in evidence if isinstance(e, dict)],
        root_cause=str(data.get("root_cause", "")),
        impact=str(data.get("impact", "")),
        remediation_playbook=[str(step) for step in playbook],
        probabilities=_coerce_probabilities(data.get("probabilities")),
        abstain=False,
        model_id=model_id,
        prompt_version=prompt_version,
    )


def parse_output(
    text: str, *, model_id: str = "", prompt_version: str = ""
) -> AgentOutput | None:
    raw = extract_json(text)
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    try:
        return validate_output(data, model_id=model_id, prompt_version=prompt_version)
    except ValueError:
        return None
