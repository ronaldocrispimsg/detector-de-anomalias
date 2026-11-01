"""Grounding de evidência: cada métrica citada tem de bater com a telemetria.

Estende `xai.evidence_matches_telemetry`. Evidência não conferida é descartada;
a confiança cai na proporção da evidência que resistiu e, abaixo de um limite, o
agente abstém em vez de agir sobre uma justificativa inventada.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping, Sequence

from Backend.services.agent.guardrails import AgentOutput
from Backend.services.agent.telemetry import Telemetry


def _grounded(item: Mapping[str, Any], mapping: Mapping[str, Any], tol: float) -> bool:
    metric = str(item.get("metric", ""))
    if metric not in mapping:
        return False
    try:
        cited = float(item.get("value"))
    except (TypeError, ValueError):
        return False
    actual = float(mapping[metric])
    return abs(cited - actual) <= tol * max(1.0, abs(actual))


@dataclass
class GroundingResult:
    output: AgentOutput
    valid: list[dict[str, Any]]
    dropped: list[dict[str, Any]]
    agreement: float

    def metrics(self) -> dict[str, float]:
        return {
            "evidence_total": float(len(self.valid) + len(self.dropped)),
            "evidence_ungrounded": float(len(self.dropped)),
            "evidence_agreement": self.agreement,
            "confidence": self.output.confidence,
        }


def ground_evidence(
    output: AgentOutput, sample: Telemetry, *, tol: float = 0.05
) -> GroundingResult:
    """Separa a evidência em conferida e descartada; calcula a concordância."""
    mapping = sample.to_mapping()
    valid: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for item in output.evidence or []:
        if isinstance(item, dict) and _grounded(item, mapping, tol):
            valid.append(item)
        else:
            dropped.append(item if isinstance(item, dict) else {"raw": item})
    total = len(valid) + len(dropped)
    agreement = 1.0 if total == 0 else len(valid) / total
    return GroundingResult(output=output, valid=valid, dropped=dropped, agreement=agreement)


def apply_grounding(
    output: AgentOutput,
    sample: Telemetry,
    *,
    tol: float = 0.05,
    min_agreement: float = 0.5,
) -> GroundingResult:
    """Descarta evidência não conferida, derruba a confiança e, se preciso, abstém."""
    result = ground_evidence(output, sample, tol=tol)
    if not result.dropped:
        return result

    agreement = result.agreement
    grounded = replace(
        output,
        evidence=result.valid,
        confidence=output.confidence * agreement,
        abstain=output.abstain or agreement < min_agreement,
    )
    if grounded.abstain:
        grounded = replace(
            grounded, predicted_scenario="ABSTAIN", is_anomaly=False, severity="UNKNOWN"
        )
    result.output = grounded
    return result


def ungrounded_evidence_rate(outputs: Sequence[AgentOutput], samples: Sequence[Telemetry]) -> float:
    """Fração de itens de evidência que não batem com a telemetria."""
    total = 0
    bad = 0
    for output, sample in zip(outputs, samples):
        result = ground_evidence(output, sample)
        total += len(result.valid) + len(result.dropped)
        bad += len(result.dropped)
    return 0.0 if total == 0 else bad / total
