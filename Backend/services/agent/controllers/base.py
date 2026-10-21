"""Interface do controlador para o ciclo fechado.

O adaptador real (Ryu/ONOS) implementa a mesma interface; o `MockController`
serve aos testes. O ciclo: recomendar (N1) → aplicar com gate (N2) → verificar →
rollback se não melhorar.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Sequence

from Backend.services.agent.actions import ActionSpec, AutonomyLevel, gate


@dataclass
class ActionResult:
    action: str
    applied: bool
    verified: bool
    rolled_back: bool
    metric_before: float | None = None
    metric_after: float | None = None
    note: str = ""


@dataclass
class ClosedLoopResult:
    scenario: str
    level: AutonomyLevel
    results: list[ActionResult] = field(default_factory=list)

    def operational_metrics(self) -> dict[str, float]:
        applied = [r for r in self.results if r.applied]
        verified = [r for r in applied if r.verified]
        rolled = [r for r in applied if r.rolled_back]
        return {
            "actions_planned": float(len(self.results)),
            "actions_applied": float(len(applied)),
            "mitigation_success_rate": (len(verified) / len(applied)) if applied else 0.0,
            "rollback_rate": (len(rolled) / len(applied)) if applied else 0.0,
        }


class Controller(ABC):
    @abstractmethod
    def dry_run(self, action: ActionSpec) -> ActionResult:  # pragma: no cover
        ...

    @abstractmethod
    def apply(self, action: ActionSpec, metric_before: float) -> ActionResult:  # pragma: no cover
        ...

    @abstractmethod
    def verify(self, result: ActionResult, *, margin: float = 0.0) -> bool:  # pragma: no cover
        ...

    @abstractmethod
    def rollback(self, result: ActionResult) -> ActionResult:  # pragma: no cover
        ...


def run_closed_loop(
    output: Any,
    actions: Sequence[ActionSpec],
    controller: Controller,
    *,
    level: AutonomyLevel,
    metric_before: float,
    margin: float = 0.0,
) -> ClosedLoopResult:
    """Executa o ciclo para as ações permitidas pelo gate."""
    result = ClosedLoopResult(
        scenario=getattr(output, "predicted_scenario", "NORMAL"), level=level
    )
    for action in actions:
        if not gate(level, action):
            result.results.append(
                ActionResult(action.name, applied=False, verified=False, rolled_back=False,
                             note="bloqueado pelo gate")
            )
            continue
        dry = controller.dry_run(action)
        applied = controller.apply(action, metric_before)
        applied.metric_before = metric_before
        if controller.verify(applied, margin=margin):
            applied.verified = True
        else:
            applied = controller.rollback(applied)
        result.results.append(applied)
    return result
