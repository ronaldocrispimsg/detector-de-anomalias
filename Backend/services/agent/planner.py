"""Seleção de ferramenta: piso determinístico e camada LLM.

O plano tem duas camadas. O piso determinístico mapeia cenário → ferramenta e
nunca desaparece. A camada LLM escolhe e parametriza a ferramenta; se a saída não
validar contra o schema da ferramenta, o piso assume.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Protocol, Sequence

from Backend.services.agent.guardrails import extract_json
from Backend.services.agent.tools import (
    ActionTool,
    ToolParamError,
    validate_params,
)


@dataclass
class ToolDecision:
    tool_id: str
    params: dict[str, Any] = field(default_factory=dict)
    rationale: str = ""
    source: str = "deterministic"  # deterministic | llm


class ToolPlanner(Protocol):
    def decide(
        self,
        *,
        scenario: str,
        tools: Sequence[ActionTool],
        history: Sequence[str] = (),
        telemetry: Mapping[str, Any] | None = None,
    ) -> ToolDecision | None:  # pragma: no cover
        ...


class DeterministicPlanner:
    """Piso: a primeira ferramenta ainda não tentada, com os defaults do schema."""

    def decide(
        self,
        *,
        scenario: str,
        tools: Sequence[ActionTool],
        history: Sequence[str] = (),
        telemetry: Mapping[str, Any] | None = None,
    ) -> ToolDecision | None:
        for tool in tools:
            if tool.id in history:
                continue
            try:
                params = validate_params(tool, {})
            except ToolParamError:
                continue
            return ToolDecision(
                tool_id=tool.id,
                params=params,
                rationale="piso determinístico (cenário → ferramenta)",
                source="deterministic",
            )
        return None


def plan_prompt(
    scenario: str,
    tools: Sequence[ActionTool],
    telemetry: Mapping[str, Any] | None = None,
) -> str:
    lines = [
        "Escolha uma ferramenta de mitigação para a anomalia.",
        f"Cenário previsto: {scenario}.",
    ]
    if telemetry:
        lines.append(
            "Telemetria: "
            + json.dumps({k: telemetry[k] for k in sorted(telemetry)}, sort_keys=True)
        )
    lines.append("Ferramentas permitidas:")
    for tool in tools:
        params = ", ".join(
            f"{name}:{spec.type}" + ("" if spec.required else "?")
            for name, spec in tool.params.items()
        )
        lines.append(f"- {tool.id} ({params}) — {tool.description}")
    lines.append(
        'Responda só com JSON: {"tool_id": "...", "params": {...}, "rationale": "..."}'
    )
    return "\n".join(lines)


def parse_tool_decision(
    text: str, allowed: Sequence[ActionTool]
) -> ToolDecision | None:
    """Extrai e valida a decisão; None se o tool_id ou os parâmetros não batem."""
    raw = extract_json(text or "")
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    tool_id = str(data.get("tool_id", "")).strip()
    by_id = {tool.id: tool for tool in allowed}
    if tool_id not in by_id:
        return None
    tool = by_id[tool_id]
    try:
        params = validate_params(tool, data.get("params"))
    except ToolParamError:
        return None
    return ToolDecision(
        tool_id=tool_id,
        params=params,
        rationale=str(data.get("rationale", "")),
        source="llm",
    )


@dataclass
class LLMToolPlanner:
    """Camada LLM com fallback determinístico embutido."""

    generate: Callable[[str], str] | None = None
    fallback: DeterministicPlanner = field(default_factory=DeterministicPlanner)

    def decide(
        self,
        *,
        scenario: str,
        tools: Sequence[ActionTool],
        history: Sequence[str] = (),
        telemetry: Mapping[str, Any] | None = None,
    ) -> ToolDecision | None:
        available = [tool for tool in tools if tool.id not in history]
        if self.generate is not None and available:
            text = self.generate(plan_prompt(scenario, available, telemetry))
            decision = parse_tool_decision(text, available)
            if decision is not None:
                return decision
        return self.fallback.decide(
            scenario=scenario, tools=tools, history=history, telemetry=telemetry
        )


@dataclass
class SelfConsistentPlanner:
    """Self-consistency para risco alto: k amostras e maioria estrita.

    Sem maioria estrita (`count * 2 > k`), abstém (retorna `None`) e escala, em vez
    de agir sobre uma escolha instável. Custa mais latência — usar só em alto risco.
    """

    generate: Callable[[str], str] | None = None
    k: int = 3
    fallback: DeterministicPlanner = field(default_factory=DeterministicPlanner)

    def decide(
        self,
        *,
        scenario: str,
        tools: Sequence[ActionTool],
        history: Sequence[str] = (),
        telemetry: Mapping[str, Any] | None = None,
    ) -> ToolDecision | None:
        available = [tool for tool in tools if tool.id not in history]
        if self.generate is None or not available:
            return self.fallback.decide(
                scenario=scenario, tools=tools, history=history, telemetry=telemetry
            )
        prompt = plan_prompt(scenario, available, telemetry)
        votes: dict[str, list[ToolDecision]] = {}
        for _ in range(max(1, self.k)):
            decision = parse_tool_decision(self.generate(prompt), available)
            if decision is not None:
                votes.setdefault(decision.tool_id, []).append(decision)
        if not votes:
            return self.fallback.decide(
                scenario=scenario, tools=tools, history=history, telemetry=telemetry
            )
        _, group = max(votes.items(), key=lambda item: len(item[1]))
        if len(group) * 2 <= max(1, self.k):
            return None
        return group[0]
