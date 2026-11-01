"""Fase 10: laboratório Kathará (topologia, controlador, coleta, injeção).

Testes unitários com o manager mockado — não precisam de Docker.
"""

from __future__ import annotations

from Backend.harness.kathara.controller import KatharaController
from Backend.harness.kathara.inject import INJECTIONS, injection_for
from Backend.harness.kathara.lab import build_lab, default_config, load_config
from Backend.harness.kathara.metrics import parse_metrics, probe_script
from Backend.services.agent.tools import to_action, tools_for_scenario


class FakeManager:
    """Captura os comandos e devolve saídas programadas."""

    def __init__(self, outputs: dict[str, str] | None = None):
        self.calls: list[tuple[str, object]] = []
        self.outputs = outputs or {}

    def exec(self, machine, command, lab_name=None, stream=False, wait=False):
        self.calls.append((machine, command))
        text = self.outputs.get("__default__", "")
        return text.encode(), b"", 0


def test_default_config_present_and_well_formed():
    config = default_config()
    assert config["lab_name"]
    assert config["server_host"] in config["machines"]
    assert config["bridge_host"] in config["machines"]
    assert set(config["links"]) == {"l1", "l2", "l3"}


def test_build_lab_creates_machines_and_links():
    lab = build_lab(load_config())
    for name in ("bridge", "h1", "h2", "h3"):
        assert lab.has_machine(name)
    assert lab.has_link("l1")
    assert lab.has_link("l2")


def test_probe_script_substitutes_server():
    assert "10.0.0.1" in probe_script("10.0.0.1")
    assert "__SERVER__" not in probe_script()


def test_parse_metrics_normalizes_types():
    text = "\n".join(
        [
            "latency_ms=12.5",
            "packet_loss_pct=0",
            "jitter_ms=1.2",
            "cpu_usage_pct=33.3",
            "ram_usage_pct=40.0",
            "disk_usage_pct=55",
            "network_in_bps=8000",
            "network_out_bps=16000",
            "http_status_code=200",
            "http_response_time_ms=95.0",
            "tcp_port_open=1",
            "active_connections=7",
        ]
    )
    metrics = parse_metrics(text)
    assert metrics["http_status_code"] == 200
    assert metrics["tcp_port_open"] is True
    assert metrics["active_connections"] == 7
    assert metrics["latency_ms"] == 12.5
    assert metrics["network_out_bps"] == 16000.0


def test_controller_wraps_commands_in_sh_c():
    manager = FakeManager({"__default__": "latency_ms=5\nactive_connections=1"})
    controller = KatharaController(lab_name="noc", manager=manager)
    tool = tools_for_scenario("DDOS_ATTACK")[0]
    action = to_action(tool, {})
    controller.apply(action, metric_before=100.0)
    machine, command = manager.calls[0]
    assert machine == "bridge"  # rate_limit tem escopo flow → bridge
    assert command[:2] == ["sh", "-c"]


def test_controller_verify_uses_direction_and_margin():
    manager = FakeManager({"__default__": "network_in_bps=10\n"})
    controller = KatharaController(lab_name="noc", manager=manager)
    tool = tools_for_scenario("DDOS_ATTACK")[0]
    action = to_action(tool, {})
    result = controller.apply(action, metric_before=100.0)
    assert controller.verify(result, margin=0.0) is True
    assert result.metric_after == 10.0


def test_controller_verify_false_when_worse():
    manager = FakeManager({"__default__": "network_in_bps=500\n"})
    controller = KatharaController(lab_name="noc", manager=manager)
    tool = tools_for_scenario("DDOS_ATTACK")[0]
    action = to_action(tool, {})
    result = controller.apply(action, metric_before=100.0)
    assert controller.verify(result) is False


def test_controller_rollback_runs_rollback_command():
    manager = FakeManager({"__default__": "network_in_bps=500\n"})
    controller = KatharaController(lab_name="noc", manager=manager)
    tool = tools_for_scenario("DDOS_ATTACK")[0]
    action = to_action(tool, {})
    result = controller.apply(action, metric_before=100.0)
    rolled = controller.rollback(result)
    assert rolled.rolled_back is True
    assert manager.calls[-1][1] == ["sh", "-c", action.rollback]


def test_alert_action_verifies_without_metric():
    manager = FakeManager()
    controller = KatharaController(lab_name="noc", manager=manager)
    tool = {t.id: t for t in tools_for_scenario("HOST_DOWN")}["alert"]
    action = to_action(tool, {})
    result = controller.apply(action, metric_before=0.0)
    assert controller.verify(result) is True


def test_every_scenario_has_injection():
    for scenario in (
        "NORMAL", "DDOS_ATTACK", "PORT_SCAN", "HOST_DOWN", "SERVICE_OUTAGE",
        "DISK_EXHAUSTION", "MEMORY_LEAK", "NETWORK_CONGESTION",
        "DATA_EXFILTRATION", "COMBINED_FAULT",
    ):
        assert scenario in INJECTIONS
        assert injection_for(scenario).scenario == scenario


def test_injection_commands_only_reference_known_machines():
    known = set(default_config()["machines"])
    for injection in INJECTIONS.values():
        for machine, _ in injection.setup + injection.cleanup:
            assert machine in known
