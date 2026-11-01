"""Fase 10 (integração): sobe um laboratório Kathará de verdade.

Requer Docker em execução. Marque/rode com:

    .venv/bin/python -m pytest -m integration \\
        Backend/harness/tests/test_kathara_integration.py -q

Sem Docker, os testes são pulados.
"""

from __future__ import annotations

import shutil
import sys

import pytest

from Backend.harness.kathara.controller import KatharaController
from Backend.harness.kathara.lab import build_lab, load_config, start_lab, stop_lab

pytestmark = pytest.mark.integration


def _docker_ready() -> bool:
    if shutil.which("docker") is None:
        return False
    import subprocess

    return subprocess.run(
        ["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ).returncode == 0


@pytest.fixture(scope="module")
def lab():
    if not _docker_ready():
        pytest.skip("Docker não está acessível")
    # O Kathará faz select() em sys.stdin durante o startup; sob captura do
    # pytest o stdin não tem fileno() e a chamada quebra. Damos um stdin real.
    saved_stdin = sys.stdin
    try:
        sys.stdin = open("/dev/null")  # noqa: SIM115 - restaurado no finally
    except OSError:
        pass
    try:
        running = build_lab(load_config())
        start_lab(running)
        yield running
        stop_lab(running)
    finally:
        sys.stdin = saved_stdin


def test_machines_run_and_bridge_is_up(lab):
    controller = KatharaController(lab_name=lab.name)
    out, err, rc = controller.exec("bridge", "brctl show")
    assert rc == 0, err
    assert "br0" in out


def test_hosts_reach_each_other(lab):
    controller = KatharaController(lab_name=lab.name)
    out, _, rc = controller.exec("h2", "ping -c 2 -W 2 10.0.0.1")
    assert rc == 0
    assert "0% packet loss" in out or "1 received" in out


def test_metrics_collection_returns_schema(lab):
    controller = KatharaController(lab_name=lab.name)
    metrics = controller._runner  # noqa: SLF001 - smoke do wiring
    from Backend.harness.kathara.metrics import collect

    values = collect(metrics, "h1", server="10.0.0.1")
    assert set(values) == {
        "latency_ms", "packet_loss_pct", "jitter_ms", "cpu_usage_pct",
        "ram_usage_pct", "disk_usage_pct", "network_in_bps", "network_out_bps",
        "http_status_code", "http_response_time_ms", "tcp_port_open",
        "active_connections",
    }
    assert "latency_ms" in values
