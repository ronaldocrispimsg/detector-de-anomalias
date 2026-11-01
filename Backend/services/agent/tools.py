"""Catálogo de ferramentas executáveis do agente.

Cada `ActionTool` descreve uma ação de mitigação de forma verificável: o comando
(template com parâmetros validados), o rollback, a métrica que comprova o efeito,
o risco e o escopo. O comando real é embasado por pesquisa — bridge nativo
(`brctl`), shaping com `tc` e filtro L2 com `nftables` (família `bridge`).

O rótulo (`scenario`) é usado aqui só para selecionar o conjunto de ferramentas
permitido; ele nunca entra na telemetria do classificador.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from string import Template
from typing import Any, Mapping

from Backend.services.agent.actions import ActionSpec

CATALOG_VERSION = "tools-v1"


class ToolParamError(ValueError):
    """Parâmetro ausente, mal tipado ou fora de faixa."""


@dataclass(frozen=True)
class Param:
    type: str  # "int" | "float" | "str" | "bool"
    required: bool = True
    default: Any = None
    minimum: float | None = None
    maximum: float | None = None
    choices: tuple[str, ...] | None = None


@dataclass(frozen=True)
class ActionTool:
    id: str
    command: str
    rollback_command: str
    verify_metric: str | None
    direction: str = "lower_better"
    risk: str = "low"  # low | medium | high
    scope: str = "host"  # host | switch | flow | victim | dst  (onde roda o comando)
    metric_scope: str | None = None  # onde a métrica é medida (default: scope)
    reversible: bool = True
    requires_verification: bool = True
    params: dict[str, Param] = field(default_factory=dict)
    description: str = ""

    def render(self, values: Mapping[str, Any]) -> str:
        return Template(self.command).substitute(**values)

    def render_rollback(self, values: Mapping[str, Any]) -> str:
        return Template(self.rollback_command).substitute(**values)


def _coerce(name: str, spec: Param, value: Any) -> Any:
    if spec.type == "str":
        if not isinstance(value, str):
            raise ToolParamError(f"{name}: esperado str")
        if spec.choices is not None and value not in spec.choices:
            raise ToolParamError(f"{name}: fora de {spec.choices}")
        return value
    if spec.type == "bool":
        if isinstance(value, bool):
            return value
        raise ToolParamError(f"{name}: esperado bool")
    if spec.type in ("int", "float"):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ToolParamError(f"{name}: esperado número")
        number = int(value) if spec.type == "int" else float(value)
        if spec.minimum is not None and number < spec.minimum:
            raise ToolParamError(f"{name}: abaixo do mínimo {spec.minimum}")
        if spec.maximum is not None and number > spec.maximum:
            raise ToolParamError(f"{name}: acima do máximo {spec.maximum}")
        return number
    raise ToolParamError(f"{name}: tipo desconhecido {spec.type!r}")


def validate_params(tool: ActionTool, values: Mapping[str, Any] | None) -> dict[str, Any]:
    """Valida e normaliza os parâmetros; aplica os defaults. Levanta se inválido."""
    values = dict(values or {})
    unknown = set(values) - set(tool.params)
    if unknown:
        raise ToolParamError(f"parâmetros desconhecidos: {sorted(unknown)}")
    normalized: dict[str, Any] = {}
    for name, spec in tool.params.items():
        if name in values and values[name] is not None:
            normalized[name] = _coerce(name, spec, values[name])
        elif spec.default is not None:
            normalized[name] = spec.default
        elif spec.required:
            raise ToolParamError(f"{name}: obrigatório")
    return normalized


def to_action(tool: ActionTool, values: Mapping[str, Any]) -> ActionSpec:
    """Converte uma ferramenta + parâmetros em `ActionSpec` executável."""
    params = validate_params(tool, values)
    parameters = dict(params)
    parameters["command"] = tool.render(params)
    parameters["rollback_command"] = tool.render_rollback(params)
    parameters["scope"] = tool.scope
    parameters["metric_scope"] = tool.metric_scope or tool.scope
    parameters["risk"] = tool.risk
    if tool.verify_metric is not None:
        parameters["verify_metric"] = tool.verify_metric
        parameters["direction"] = tool.direction
    return ActionSpec(
        name=tool.id,
        reversible=tool.reversible,
        parameters=parameters,
        rollback=tool.render_rollback(params),
    )


_LINK = Param("str", default="eth0")
_SRC = Param("str", default="10.0.0.2")
_RATE = Param("str", default="1mbit")

_TOOLS: tuple[ActionTool, ...] = (
    ActionTool(
        id="noop",
        command="true",
        rollback_command="true",
        verify_metric=None,
        requires_verification=False,
        risk="low",
        scope="host",
        description="Observar sem agir (cenário NORMAL).",
    ),
    ActionTool(
        id="rate_limit",
        command=(
            "tc qdisc add dev $iface root handle 1: htb default 30 && "
            "tc class add dev $iface parent 1: classid 1:10 htb rate $rate burst $burst && "
            "tc filter add dev $iface parent 1: protocol ip prio 1 "
            "u32 match ip src $src flowid 1:10"
        ),
        rollback_command="tc qdisc del dev $iface root",
        verify_metric="network_in_bps",
        direction="lower_better",
        risk="high",
        scope="flow",
        metric_scope="victim",
        params={
            "iface": _LINK,
            "rate": _RATE,
            "burst": Param("str", default="15k"),
            "src": _SRC,
        },
        description="Shaping HTB por origem no bridge (ddos de banda).",
    ),
    ActionTool(
        id="block_source",
        command="ebtables -A FORWARD -p IPv4 --ip-src $src -j DROP",
        rollback_command="ebtables -D FORWARD -p IPv4 --ip-src $src -j DROP",
        verify_metric="network_in_bps",
        direction="lower_better",
        risk="medium",
        scope="flow",
        metric_scope="victim",
        params={"src": _SRC, "ttl_s": Param("int", default=600, minimum=1, maximum=86400)},
        description="Bloqueio temporário da origem no bridge (port scan).",
    ),
    ActionTool(
        id="block_egress",
        command="ebtables -A FORWARD -p IPv4 --ip-dst $dst -j DROP",
        rollback_command="ebtables -D FORWARD -p IPv4 --ip-dst $dst -j DROP",
        verify_metric="network_in_bps",
        direction="lower_better",
        risk="medium",
        scope="flow",
        metric_scope="dst",
        params={"dst": Param("str", default="10.0.0.3")},
        description="Bloqueio de egresso ao destino (exfiltração).",
    ),
    ActionTool(
        id="alert",
        command='logger -t netspot-agent "alert page=$page"',
        rollback_command='logger -t netspot-agent "alert cleared"',
        verify_metric=None,
        requires_verification=False,
        risk="low",
        scope="host",
        params={"page": Param("bool", default=True)},
        description="Alerta/paging quando não há o que restaurar de fora.",
    ),
    ActionTool(
        id="restart_service",
        command="systemctl stop $service; sleep $drain_s; systemctl start $service",
        rollback_command="systemctl restart $service",
        verify_metric="http_response_time_ms",
        direction="lower_better",
        risk="medium",
        scope="host",
        params={
            "service": Param("str", default="nginx"),
            "drain_s": Param("int", default=2, minimum=0, maximum=120),
        },
        description="Restart do serviço com drenagem.",
    ),
    ActionTool(
        id="prune_logs",
        command="journalctl --vacuum-size=$size; logrotate -f /etc/logrotate.conf",
        rollback_command="true",
        verify_metric="disk_usage_pct",
        direction="lower_better",
        risk="low",
        scope="host",
        params={"size": Param("str", default="200M")},
        description="Poda de logs para liberar disco.",
    ),
    ActionTool(
        id="shape_traffic",
        command=(
            "tc qdisc add dev $iface root tbf rate $rate burst $burst latency $latency"
        ),
        rollback_command="tc qdisc del dev $iface root",
        verify_metric="latency_ms",
        direction="lower_better",
        risk="high",
        scope="flow",
        metric_scope="victim",
        params={
            "iface": _LINK,
            "rate": Param("str", default="20mbit"),
            "burst": Param("str", default="32k"),
            "latency": Param("str", default="400ms"),
        },
        description="Shaping TBF no bridge (congestionamento).",
    ),
)

CATALOG: dict[str, ActionTool] = {tool.id: tool for tool in _TOOLS}

TOOLS_BY_SCENARIO: dict[str, tuple[str, ...]] = {
    "NORMAL": ("noop",),
    "DDOS_ATTACK": ("rate_limit", "block_source"),
    "PORT_SCAN": ("block_source",),
    "HOST_DOWN": ("alert",),
    "SERVICE_OUTAGE": ("restart_service",),
    "DISK_EXHAUSTION": ("prune_logs",),
    "MEMORY_LEAK": ("restart_service",),
    "NETWORK_CONGESTION": ("shape_traffic",),
    "DATA_EXFILTRATION": ("block_egress",),
    "COMBINED_FAULT": ("alert", "restart_service"),
}


def tools_for_scenario(scenario: str) -> list[ActionTool]:
    """Ferramentas permitidas para o cenário, na ordem de preferência."""
    ids = TOOLS_BY_SCENARIO.get(scenario, ("alert",))
    return [CATALOG[tool_id] for tool_id in ids]
