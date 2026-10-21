"""Trajetória auditável do loop do agente.

Cada passo guarda o comando exato, o parâmetro, a métrica antes/depois e o
veredito. O hash da trajetória é determinístico: a mesma entrada com a mesma seed
produz o mesmo hash (base da repro por anomalia, fase 12).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

VERDICTS = ("kept", "rolled_back", "blocked", "noop", "escalated")


@dataclass
class Step:
    index: int
    scenario: str
    tool_id: str
    source: str  # deterministic | llm
    command: str = ""
    rollback_command: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    metric_before: float | None = None
    metric_after: float | None = None
    gate_allowed: bool = False
    applied: bool = False
    verified: bool = False
    rolled_back: bool = False
    verdict: str = "noop"
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "scenario": self.scenario,
            "tool_id": self.tool_id,
            "source": self.source,
            "command": self.command,
            "rollback_command": self.rollback_command,
            "params": dict(self.params),
            "metric_before": self.metric_before,
            "metric_after": self.metric_after,
            "gate_allowed": self.gate_allowed,
            "applied": self.applied,
            "verified": self.verified,
            "rolled_back": self.rolled_back,
            "verdict": self.verdict,
            "reason": self.reason,
        }


@dataclass
class Trajectory:
    scenario: str
    level: int
    metric: str | None = None
    steps: list[Step] = field(default_factory=list)

    def add(self, step: Step) -> None:
        self.steps.append(step)

    @property
    def outcome(self) -> str:
        if any(step.verdict == "kept" for step in self.steps):
            return "mitigated"
        if any(step.verdict == "rolled_back" for step in self.steps):
            return "reverted"
        if any(step.verdict == "blocked" for step in self.steps):
            return "blocked"
        return "noop"

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "level": self.level,
            "metric": self.metric,
            "outcome": self.outcome,
            "steps": [step.to_dict() for step in self.steps],
        }

    def hash(self) -> str:
        """Hash canônico determinístico da trajetória."""
        payload = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def operational_metrics(self) -> dict[str, float]:
        planned = float(len(self.steps))
        applied = [step for step in self.steps if step.applied]
        kept = [step for step in applied if step.verdict == "kept"]
        rolled = [step for step in applied if step.rolled_back]
        return {
            "steps_planned": planned,
            "actions_applied": float(len(applied)),
            "mitigation_success_rate": (len(kept) / len(applied)) if applied else 0.0,
            "rollback_rate": (len(rolled) / len(applied)) if applied else 0.0,
        }
