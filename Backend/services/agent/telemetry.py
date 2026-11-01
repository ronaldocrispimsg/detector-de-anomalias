"""Esquema canônico de telemetria do agente.

Fonte única da verdade das features e das classes. O rótulo (`scenario`) NUNCA
faz parte da entrada do agente.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from Backend.services.anomaly_simulator import SCENARIOS_META

FEATURE_FIELDS: tuple[str, ...] = (
    "latency_ms",
    "packet_loss_pct",
    "jitter_ms",
    "cpu_usage_pct",
    "ram_usage_pct",
    "disk_usage_pct",
    "network_in_bps",
    "network_out_bps",
    "http_status_code",
    "http_response_time_ms",
    "tcp_port_open",
    "active_connections",
)
LABEL_FIELD = "scenario"

# `CUSTOM` é modo de entrada de teste, não fenômeno: fora do conjunto de classes.
CLASSES: tuple[str, ...] = tuple(name for name in SCENARIOS_META if name != "CUSTOM")

SEVERITY_BY_SCENARIO: dict[str, str] = {
    "NORMAL": "OK",
    "HOST_DOWN": "CRITICAL",
    "COMBINED_FAULT": "CRITICAL",
    "DDOS_ATTACK": "CRITICAL",
    "DATA_EXFILTRATION": "CRITICAL",
    "DISK_EXHAUSTION": "CRITICAL",
    "MEMORY_LEAK": "WARNING",
    "PORT_SCAN": "WARNING",
    "SERVICE_OUTAGE": "CRITICAL",
    "NETWORK_CONGESTION": "WARNING",
}


@dataclass(frozen=True)
class Telemetry:
    """Uma amostra de telemetria, sem rótulo."""

    latency_ms: float
    packet_loss_pct: float
    jitter_ms: float
    cpu_usage_pct: float
    ram_usage_pct: float
    disk_usage_pct: float
    network_in_bps: float
    network_out_bps: float
    http_status_code: int
    http_response_time_ms: float
    tcp_port_open: bool
    active_connections: int

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> "Telemetry":
        return cls(
            latency_ms=float(mapping["latency_ms"]),
            packet_loss_pct=float(mapping["packet_loss_pct"]),
            jitter_ms=float(mapping["jitter_ms"]),
            cpu_usage_pct=float(mapping["cpu_usage_pct"]),
            ram_usage_pct=float(mapping["ram_usage_pct"]),
            disk_usage_pct=float(mapping["disk_usage_pct"]),
            network_in_bps=float(mapping["network_in_bps"]),
            network_out_bps=float(mapping["network_out_bps"]),
            http_status_code=int(mapping["http_status_code"]),
            http_response_time_ms=float(mapping["http_response_time_ms"]),
            tcp_port_open=bool(mapping["tcp_port_open"]),
            active_connections=int(mapping["active_connections"]),
        )

    @classmethod
    def from_features(cls, features: Sequence[float]) -> "Telemetry":
        values = list(features)
        if len(values) != len(FEATURE_FIELDS):
            raise ValueError(
                f"esperado {len(FEATURE_FIELDS)} features, recebido {len(values)}"
            )
        mapping: dict[str, Any] = {}
        for name, value in zip(FEATURE_FIELDS, values):
            if name == "tcp_port_open":
                mapping[name] = bool(round(float(value)))
            elif name == "active_connections":
                mapping[name] = int(round(float(value)))
            elif name == "http_status_code":
                mapping[name] = int(round(float(value)))
            else:
                mapping[name] = float(value)
        return cls.from_mapping(mapping)

    def to_mapping(self) -> dict[str, Any]:
        return {
            "latency_ms": self.latency_ms,
            "packet_loss_pct": self.packet_loss_pct,
            "jitter_ms": self.jitter_ms,
            "cpu_usage_pct": self.cpu_usage_pct,
            "ram_usage_pct": self.ram_usage_pct,
            "disk_usage_pct": self.disk_usage_pct,
            "network_in_bps": self.network_in_bps,
            "network_out_bps": self.network_out_bps,
            "http_status_code": self.http_status_code,
            "http_response_time_ms": self.http_response_time_ms,
            "tcp_port_open": self.tcp_port_open,
            "active_connections": self.active_connections,
        }
