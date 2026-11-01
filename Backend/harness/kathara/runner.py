"""Orquestra um cenário de ponta a ponta no Kathará.

Sobe o laboratório, inicia o servidor, injeta a falha, mede antes, roda o loop do
agente (fase 09) com o controlador real (fase 10), mede depois e derruba tudo. É
a base do `scripts/eval_kathara.py` (fase 10) e da repro por anomalia (fase 12).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from Backend.harness.kathara.controller import KatharaController
from Backend.harness.kathara.inject import injection_for, start_server
from Backend.harness.kathara.lab import build_lab, default_config, start_lab, stop_lab
from Backend.harness.kathara.metrics import collect
from Backend.services.agent.actions import AutonomyLevel
from Backend.services.agent.loop import LoopBudget, run_agent_loop
from Backend.services.agent.tools import tools_for_scenario


@dataclass
class ScenarioResult:
    scenario: str
    metric: str | None
    metric_before: float | None
    metric_after: float | None
    outcome: str
    trajectory_hash: str
    trajectory: dict[str, Any]
    operational_metrics: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "metric": self.metric,
            "metric_before": self.metric_before,
            "metric_after": self.metric_after,
            "outcome": self.outcome,
            "trajectory_hash": self.trajectory_hash,
            "operational_metrics": self.operational_metrics,
            "trajectory": self.trajectory,
        }


def _target_for(scope: str, config: Mapping[str, Any]) -> str:
    roles = {
        "host": config["server_host"],
        "victim": config["server_host"],
        "attacker": config.get("attacker_host", "h2"),
        "dst": config.get("dst_host", "h3"),
        "switch": config["bridge_host"],
        "flow": config["bridge_host"],
    }
    return roles.get(scope, config["server_host"])


def run_scenario(
    scenario: str,
    config: Mapping[str, Any] | None = None,
    *,
    budget: LoopBudget | None = None,
    level: AutonomyLevel = AutonomyLevel.N2,
    keep: bool = False,
) -> ScenarioResult:
    config = dict(config) if config is not None else default_config()
    server = config["server_ip"]
    tools = tools_for_scenario(scenario)
    metric = tools[0].verify_metric if tools else None
    metric_machine = _target_for(tools[0].metric_scope or tools[0].scope, config) if tools else None

    lab = build_lab(config)
    start_lab(lab)
    controller = KatharaController(
        lab_name=lab.name,
        targets={
            "host": config["server_host"],
            "victim": config["server_host"],
            "attacker": config.get("attacker_host", "h2"),
            "dst": config.get("dst_host", "h3"),
            "switch": config["bridge_host"],
            "flow": config["bridge_host"],
        },
        server=server,
    )
    try:
        for machine, command in start_server(config["server_host"]):
            controller.exec(machine, command)

        injection = injection_for(scenario)
        for machine, command in injection.setup:
            controller.exec(machine, command)

        before = None
        if metric is not None:
            before = float(collect(controller._runner, metric_machine, server=server)[metric])

        run = run_agent_loop(
            scenario=scenario,
            metric_before=float(before or 0.0),
            controller=controller,
            level=level,
            budget=budget,
        )

        after = None
        if metric is not None:
            after = float(collect(controller._runner, metric_machine, server=server)[metric])

        for machine, command in injection.cleanup:
            controller.exec(machine, command)

        return ScenarioResult(
            scenario=scenario,
            metric=metric,
            metric_before=before,
            metric_after=after,
            outcome=run.trajectory.outcome,
            trajectory_hash=run.trajectory.hash(),
            trajectory=run.trajectory.to_dict(),
            operational_metrics=run.operational_metrics(),
        )
    finally:
        if not keep:
            stop_lab(lab)
