"""Guardrail no nível do passo: nada executa fora do catálogo.

Antes de `apply`, confere que a ferramenta existe no catálogo, que é permitida ao
cenário, que os parâmetros obedecem ao schema e que o nível de autonomia autoriza
a ação (risco alto exige reversível). O comando só existe se puder ser renderizado
a partir de um `ActionTool` conhecido — texto livre do modelo nunca vira comando.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from Backend.services.agent.actions import AutonomyLevel, gate
from Backend.services.agent.planner import ToolDecision
from Backend.services.agent.tools import (
    CATALOG,
    ActionTool,
    ToolParamError,
    to_action,
    tools_for_scenario,
    validate_params,
)


class GuardError(ValueError):
    """Tentativa de resolução de comando fora do catálogo."""


@dataclass
class GuardResult:
    allowed: bool
    tool_id: str
    command: str | None = None
    reasons: list[str] = field(default_factory=list)


def command_for(decision: ToolDecision, catalog: Mapping[str, ActionTool] | None = None) -> str:
    """Renderiza o comando só se a ferramenta existir no catálogo; senão, erro."""
    catalog = catalog or CATALOG
    tool = catalog.get(decision.tool_id)
    if tool is None:
        raise GuardError(f"ferramenta fora do catálogo: {decision.tool_id!r}")
    params = validate_params(tool, decision.params)
    return to_action(tool, params).parameters["command"]


def guard_decision(
    decision: ToolDecision | None,
    *,
    level: AutonomyLevel,
    scenario: str | None = None,
    catalog: Mapping[str, ActionTool] | None = None,
) -> GuardResult:
    catalog = catalog or CATALOG
    if decision is None:
        return GuardResult(False, "", None, ["nenhuma ferramenta escolhida"])

    tool = catalog.get(decision.tool_id)
    if tool is None:
        return GuardResult(
            False, decision.tool_id, None, [f"comando fora do catálogo: {decision.tool_id!r}"]
        )

    if scenario is not None:
        allowed_ids = {t.id for t in tools_for_scenario(scenario)}
        if tool.id not in allowed_ids:
            return GuardResult(
                False,
                tool.id,
                None,
                [f"{tool.id!r} não é permitida para o cenário {scenario}"],
            )

    try:
        params = validate_params(tool, decision.params)
    except ToolParamError as exc:
        return GuardResult(False, tool.id, None, [f"parâmetros inválidos: {exc}"])

    action = to_action(tool, params)
    if not gate(level, action, high_risk=(tool.risk == "high")):
        return GuardResult(
            False, tool.id, None, ["bloqueado pelo gate de autonomia"]
        )

    return GuardResult(True, tool.id, action.parameters["command"], [])


def off_catalog_rate(decisions: Any, catalog: Mapping[str, Any] | None = None) -> float:
    """Fração de decisões cujo `tool_id` não existe no catálogo."""
    catalog = catalog or CATALOG
    decisions = list(decisions)
    if not decisions:
        return 0.0
    bad = sum(1 for d in decisions if getattr(d, "tool_id", None) not in catalog)
    return bad / len(decisions)
