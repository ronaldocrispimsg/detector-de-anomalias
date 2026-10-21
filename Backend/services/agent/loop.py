"""Loop do agente autônomo: observar → decidir → aplicar → medir → manter/reverter.

Diferente do ciclo fechado da fase 06 (uma passada), aqui o agente tenta a
próxima ferramenta quando a atual não melhora, dentro de um orçamento de passos, e
registra cada passo na trajetória.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

from Backend.services.agent.actions import AutonomyLevel, gate
from Backend.services.agent.controllers.base import Controller
from Backend.services.agent.planner import DeterministicPlanner, ToolDecision, ToolPlanner
from Backend.services.agent.tools import CATALOG, ActionTool, to_action, tools_for_scenario
from Backend.services.agent.trajectory import Step, Trajectory


@dataclass
class LoopBudget:
    max_steps: int = 4
    margin: float = 0.0


@dataclass
class LoopRun:
    trajectory: Trajectory

    def operational_metrics(self) -> dict[str, float]:
        return self.trajectory.operational_metrics()


def run_agent_loop(
    *,
    scenario: str,
    metric_before: float,
    controller: Controller,
    level: AutonomyLevel,
    planner: ToolPlanner | None = None,
    tools: Sequence[ActionTool] | None = None,
    budget: LoopBudget | None = None,
    telemetry: Mapping[str, Any] | None = None,
    guard: Callable[[ToolDecision], Any] | None = None,
    verifier: Callable[[ToolDecision], Any] | None = None,
) -> LoopRun:
    """Roda o loop até mitigar, esgotar as ferramentas ou estourar o orçamento."""
    planner = planner or DeterministicPlanner()
    budget = budget or LoopBudget()
    allowed = list(tools) if tools is not None else tools_for_scenario(scenario)
    metric = allowed[0].verify_metric if allowed else None
    trajectory = Trajectory(scenario=scenario, level=int(level), metric=metric)

    history: list[str] = []
    current = metric_before
    for index in range(budget.max_steps):
        decision = planner.decide(
            scenario=scenario, tools=allowed, history=history, telemetry=telemetry
        )
        if decision is None or decision.tool_id not in CATALOG:
            break
        tool = CATALOG[decision.tool_id]
        if tool.id in history:
            break
        action = to_action(tool, decision.params)
        step = Step(
            index=index,
            scenario=scenario,
            tool_id=tool.id,
            source=decision.source,
            command=str(action.parameters.get("command", "")),
            rollback_command=action.rollback,
            params=dict(decision.params),
        )

        if guard is not None:
            guarded = guard(decision)
            if not guarded.allowed:
                step.verdict = "blocked"
                step.reason = "guardrail: " + "; ".join(guarded.reasons)
                history.append(tool.id)
                trajectory.add(step)
                continue

        if verifier is not None:
            verdict = verifier(decision)
            if not verdict.ok:
                step.verdict = "blocked"
                step.reason = f"verificador: {verdict.status}"
                history.append(tool.id)
                trajectory.add(step)
                continue

        if not gate(level, action, high_risk=(tool.risk == "high")):
            step.verdict = "blocked"
            step.reason = "bloqueado pelo gate de autonomia"
            history.append(tool.id)
            trajectory.add(step)
            continue
        step.gate_allowed = True

        controller.dry_run(action)
        applied = controller.apply(action, current)
        step.applied = applied.applied
        step.metric_before = applied.metric_before

        if not tool.requires_verification:
            step.verified = True
            step.metric_after = applied.metric_after
            step.verdict = "noop" if tool.id == "noop" else "kept"
            step.reason = "ação informativa (sem métrica de verificação)"
            trajectory.add(step)
            break

        if controller.verify(applied, margin=budget.margin):
            step.verified = True
            step.metric_after = applied.metric_after
            step.verdict = "kept"
            step.reason = f"métrica melhorou ({step.metric_before} → {step.metric_after})"
            trajectory.add(step)
            break

        controller.rollback(applied)
        step.metric_after = applied.metric_after
        step.rolled_back = True
        step.verdict = "rolled_back"
        step.reason = f"sem melhora ({step.metric_before} → {step.metric_after}); revertida"
        history.append(tool.id)
        trajectory.add(step)

    return LoopRun(trajectory=trajectory)
