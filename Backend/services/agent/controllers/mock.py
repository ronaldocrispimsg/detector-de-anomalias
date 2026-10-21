"""Controlador mock determinístico para o ciclo fechado."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from Backend.services.agent.actions import ActionSpec
from Backend.services.agent.controllers.base import ActionResult


@dataclass
class MockController:
    """Simula aplicar uma ação e medir a métrica.

    `effect(before) -> after` define o resultado da ação. `improve=False` faz a
    ação piorar a métrica, forçando o rollback no verify.
    """

    effect: Callable[[float], float] | None = None
    margin: float = 0.0
    state: dict[str, bool] | None = None

    def __post_init__(self) -> None:
        if self.state is None:
            self.state = {}

    def dry_run(self, action: ActionSpec) -> ActionResult:
        return ActionResult(
            action=action.name, applied=False, verified=False, rolled_back=False,
            note="dry_run",
        )

    def apply(self, action: ActionSpec, metric_before: float) -> ActionResult:
        self.state[action.name] = True
        effect = self.effect or (lambda before: before * 0.5)
        return ActionResult(
            action=action.name,
            applied=True,
            verified=False,
            rolled_back=False,
            metric_before=metric_before,
            metric_after=float(effect(metric_before)),
        )

    def verify(self, result: ActionResult, *, margin: float = 0.0) -> bool:
        margin = self.margin or margin
        return bool(
            result.metric_after is not None
            and result.metric_before is not None
            and result.metric_after < result.metric_before - margin
        )

    def rollback(self, result: ActionResult) -> ActionResult:
        self.state[result.action] = False
        result.rolled_back = True
        result.note = "rollback"
        return result
