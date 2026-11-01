"""Representação da telemetria para o agente.

Normaliza pelo baseline do próprio host, deriva features úteis e serializa em
texto determinístico (ordem fixa, unidades explícitas) para o prompt. Nunca
inclui o rótulo.
"""

from __future__ import annotations

from dataclasses import dataclass

from Backend.services.agent.telemetry import FEATURE_FIELDS, Telemetry


@dataclass(frozen=True)
class Baseline:
    """Média e desvio de referência por feature, calculados no treino."""

    mean: tuple[float, ...]
    std: tuple[float, ...]

    @classmethod
    def from_features(cls, rows) -> "Baseline":
        import numpy as np

        array = np.asarray(rows, dtype=float)
        mean = array.mean(axis=0)
        std = array.std(axis=0)
        std = np.where(std == 0.0, 1.0, std)
        return cls(mean=tuple(mean.tolist()), std=tuple(std.tolist()))


def to_features(sample: Telemetry) -> list[float]:
    mapping = sample.to_mapping()
    return [float(mapping[name]) for name in FEATURE_FIELDS]


def derived_features(sample: Telemetry) -> dict[str, float]:
    ratio = sample.network_out_bps / max(1.0, sample.network_in_bps)
    return {
        "out_in_ratio": round(ratio, 4),
        "tcp_port_closed": 0.0 if sample.tcp_port_open else 1.0,
        "http_error": 1.0 if sample.http_status_code in {0, 500, 502, 503, 504} else 0.0,
    }


def _fmt_bytes_per_s(value: float) -> str:
    return f"{value / 1_000_000:.2f} MB/s"


def serialize(sample: Telemetry) -> str:
    """Serialização em texto, estável e sem rótulo."""
    derived = derived_features(sample)
    lines = [
        "telemetria_do_host:",
        f"- latency_ms: {sample.latency_ms:.2f} ms",
        f"- packet_loss_pct: {sample.packet_loss_pct:.2f} %",
        f"- jitter_ms: {sample.jitter_ms:.2f} ms",
        f"- cpu_usage_pct: {sample.cpu_usage_pct:.2f} %",
        f"- ram_usage_pct: {sample.ram_usage_pct:.2f} %",
        f"- disk_usage_pct: {sample.disk_usage_pct:.2f} %",
        f"- network_in: {_fmt_bytes_per_s(sample.network_in_bps)}",
        f"- network_out: {_fmt_bytes_per_s(sample.network_out_bps)}",
        f"- http_status_code: {sample.http_status_code}",
        f"- http_response_time_ms: {sample.http_response_time_ms:.2f} ms",
        f"- tcp_port_open: {str(sample.tcp_port_open).lower()}",
        f"- active_connections: {sample.active_connections}",
        f"- out_in_ratio: {derived['out_in_ratio']:.4f}",
        f"- tcp_port_closed: {int(derived['tcp_port_closed'])}",
        f"- http_error: {int(derived['http_error'])}",
    ]
    return "\n".join(lines)


def normalize_features(sample: Telemetry, baseline: Baseline) -> list[float]:
    raw = to_features(sample)
    return [
        (value - mean) / std
        for value, mean, std in zip(raw, baseline.mean, baseline.std)
    ]
