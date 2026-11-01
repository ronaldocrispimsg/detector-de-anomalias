"""Verificador independente do plano de alto risco.

Quebra o viés de confirmação do "LLM-as-judge": o verificador vê a telemetria e o
catálogo, **não** o texto do gerador. Ele confere se a ação escolhida casa com o
que a telemetria mostra e se os parâmetros/reserva estão no catálogo.

Vereditos: `ok`, `wrong_action` (ação não corresponde à telemetria) e
`ungrounded:<campo>` (o campo citado não tem base na telemetria ou no schema).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

from Backend.services.agent.planner import ToolDecision
from Backend.services.agent.tools import ActionTool, ToolParamError, validate_params


@dataclass
class Verdict:
    status: str
    reasons: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == "ok"


def _num(telemetry: Mapping[str, Any], key: str) -> float:
    try:
        return float(telemetry.get(key, 0.0))
    except (TypeError, ValueError):
        return 0.0


_BIG_BPS = 5_000_000.0


def _ddos(t: Mapping[str, Any]) -> bool:
    return _num(t, "network_in_bps") > _BIG_BPS or _num(t, "active_connections") > 1000


def _port_scan(t: Mapping[str, Any]) -> bool:
    return _num(t, "active_connections") > 500 or _num(t, "packet_loss_pct") > 5


def _host_down(t: Mapping[str, Any]) -> bool:
    return (not t.get("tcp_port_open", True)) and _num(t, "http_status_code") in (0, 503)


def _service_outage(t: Mapping[str, Any]) -> bool:
    return _num(t, "http_status_code") >= 500 or not t.get("tcp_port_open", True)


def _disk(t: Mapping[str, Any]) -> bool:
    return _num(t, "disk_usage_pct") > 85


def _memory(t: Mapping[str, Any]) -> bool:
    return _num(t, "ram_usage_pct") > 85


def _congestion(t: Mapping[str, Any]) -> bool:
    return _num(t, "latency_ms") > 200 or _num(t, "jitter_ms") > 50


def _exfiltration(t: Mapping[str, Any]) -> bool:
    return _num(t, "network_out_bps") > _BIG_BPS


def _combined(t: Mapping[str, Any]) -> bool:
    return _num(t, "cpu_usage_pct") > 90 and _num(t, "disk_usage_pct") > 85


# Cenário → sinal mínimo que a telemetria precisa exibir para sustentar a ação.
SIGNALS: dict[str, Callable[[Mapping[str, Any]], bool]] = {
    "DDOS_ATTACK": _ddos,
    "PORT_SCAN": _port_scan,
    "HOST_DOWN": _host_down,
    "SERVICE_OUTAGE": _service_outage,
    "DISK_EXHAUSTION": _disk,
    "MEMORY_LEAK": _memory,
    "NETWORK_CONGESTION": _congestion,
    "DATA_EXFILTRATION": _exfiltration,
    "COMBINED_FAULT": _combined,
}


def matches_telemetry(scenario: str, telemetry: Mapping[str, Any]) -> bool:
    check = SIGNALS.get(scenario)
    return True if check is None else bool(check(telemetry))


def verify_plan(
    scenario: str,
    decision: ToolDecision | None,
    telemetry: Mapping[str, Any],
    tools: Sequence[ActionTool],
) -> Verdict:
    if decision is None:
        return Verdict("wrong_action", ["nenhuma ferramenta escolhida"])

    by_id = {tool.id: tool for tool in tools}
    tool = by_id.get(decision.tool_id)
    if tool is None:
        return Verdict(
            "wrong_action",
            [f"{decision.tool_id!r} não é permitida para o cenário {scenario}"],
        )

    if tool.verify_metric is not None and tool.verify_metric not in telemetry:
        return Verdict(
            f"ungrounded:{tool.verify_metric}",
            [f"métrica {tool.verify_metric!r} ausente na telemetria"],
        )

    try:
        validate_params(tool, decision.params)
    except ToolParamError as exc:
        return Verdict("ungrounded:params", [str(exc)])

    if not matches_telemetry(scenario, telemetry):
        return Verdict(
            "wrong_action",
            [f"a telemetria não exibe o sinal de {scenario}"],
        )

    return Verdict("ok")

