"""Tabela de ações de mitigação, reversíveis e versionadas.

Mapeia cenário → severidade → ações. Níveis de autonomia: N1 apenas recomenda
(gate bloqueia aplicação), N2 aplica com verificação e rollback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Sequence

from Backend.services.agent.telemetry import SEVERITY_BY_SCENARIO

ACTION_TABLE_VERSION = "actions-v1"


class AutonomyLevel(IntEnum):
    N0 = 0  # observar
    N1 = 1  # recomendar (não aplica)
    N2 = 2  # aplicar com gate e rollback


@dataclass(frozen=True)
class ActionSpec:
    name: str
    reversible: bool = True
    parameters: dict[str, Any] = field(default_factory=dict)
    rollback: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "reversible": self.reversible,
            "parameters": dict(self.parameters),
            "rollback": self.rollback,
        }


# Tabela versionada: cenário → ações reversíveis.
_ACTIONS: dict[str, list[ActionSpec]] = {
    "NORMAL": [ActionSpec("noop")],
    "DDOS_ATTACK": [
        ActionSpec("rate_limit", parameters={"pps": 5000}, rollback="remove_rate_limit"),
        ActionSpec("temporary_block", parameters={"ttl_s": 300}, rollback="unblock"),
    ],
    "PORT_SCAN": [
        ActionSpec("temporary_block", parameters={"ttl_s": 600}, rollback="unblock"),
    ],
    "HOST_DOWN": [ActionSpec("alert", parameters={"page": True}, rollback="clear_alert")],
    "SERVICE_OUTAGE": [ActionSpec("restart_service", rollback="restore_service")],
    "DISK_EXHAUSTION": [ActionSpec("prune_logs", rollback="noop")],
    "MEMORY_LEAK": [ActionSpec("restart_service", rollback="restore_service")],
    "NETWORK_CONGESTION": [ActionSpec("tag_traffic", rollback="untag_traffic")],
    "DATA_EXFILTRATION": [
        ActionSpec("temporary_block", parameters={"ttl_s": 900}, rollback="unblock"),
    ],
    "COMBINED_FAULT": [
        ActionSpec("alert", parameters={"page": True}, rollback="clear_alert"),
        ActionSpec("restart_service", rollback="restore_service"),
    ],
}


def plan_actions(scenario: str) -> list[ActionSpec]:
    return list(_ACTIONS.get(scenario, [ActionSpec("alert", rollback="clear_alert")]))


def severity_of(scenario: str) -> str:
    return SEVERITY_BY_SCENARIO.get(scenario, "OK")


def gate(level: AutonomyLevel, action: ActionSpec, *, high_risk: bool = False) -> bool:
    """Decide se a ação pode ser aplicada neste nível de autonomia."""
    if level < AutonomyLevel.N2:
        return False
    if high_risk and not action.reversible:
        return False
    return True


def plan_for_output(output: Any, *, level: AutonomyLevel) -> list[dict[str, Any]]:
    """Ações planejadas com o veredito do gate."""
    scenario = getattr(output, "predicted_scenario", "NORMAL")
    if getattr(output, "abstain", False):
        return []
    actions = plan_actions(scenario)
    return [
        {**action.to_dict(), "allowed": gate(level, action)} for action in actions
    ]
