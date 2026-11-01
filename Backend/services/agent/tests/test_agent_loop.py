"""Fase 09: loop do agente autônomo e catálogo de ferramentas."""

from __future__ import annotations

from Backend.services.agent.actions import AutonomyLevel, gate
from Backend.services.agent.controllers.mock import MockController
from Backend.services.agent.loop import LoopBudget, run_agent_loop
from Backend.services.agent.planner import (
    DeterministicPlanner,
    LLMToolPlanner,
    parse_tool_decision,
)
from Backend.services.agent.tools import (
    CATALOG,
    ToolParamError,
    to_action,
    tools_for_scenario,
    validate_params,
)


def _run(scenario, controller, level=AutonomyLevel.N2, budget=None):
    return run_agent_loop(
        scenario=scenario,
        metric_before=100.0,
        controller=controller,
        level=level,
        budget=budget,
    )


def test_improves_then_keeps_and_stops():
    controller = MockController(effect=lambda before: before * 0.5)
    run = _run("DDOS_ATTACK", controller)
    kept = [step for step in run.trajectory.steps if step.verdict == "kept"]
    assert len(kept) == 1
    assert run.trajectory.outcome == "mitigated"
    assert run.operational_metrics()["rollback_rate"] == 0.0
    assert kept[0].command.startswith("tc qdisc add dev eth0")


def test_no_improvement_rolls_back_and_tries_next_tool():
    controller = MockController(effect=lambda before: before * 2.0)
    run = _run("DDOS_ATTACK", controller)
    steps = run.trajectory.steps
    assert len(steps) == 2
    assert {step.tool_id for step in steps} == {"rate_limit", "block_source"}
    assert all(step.rolled_back for step in steps)
    assert run.trajectory.outcome == "reverted"
    assert run.operational_metrics()["rollback_rate"] == 1.0


def test_gate_blocks_all_actions_at_n1():
    controller = MockController()
    run = _run("DDOS_ATTACK", controller, level=AutonomyLevel.N1)
    assert run.trajectory.steps
    assert all(step.verdict == "blocked" for step in run.trajectory.steps)
    assert run.operational_metrics()["actions_applied"] == 0.0


def test_invalid_llm_params_fall_back_to_deterministic_floor():
    planner = LLMToolPlanner(
        generate=lambda prompt: '{"tool_id": "rate_limit", "params": {"rate": 123}}'
    )
    run = run_agent_loop(
        scenario="DDOS_ATTACK",
        metric_before=100.0,
        controller=MockController(),
        level=AutonomyLevel.N2,
        planner=planner,
    )
    assert run.trajectory.steps
    assert run.trajectory.steps[0].source == "deterministic"
    assert run.trajectory.steps[0].tool_id == "rate_limit"


def test_valid_llm_decision_is_used():
    planner = LLMToolPlanner(
        generate=lambda prompt: (
            '{"tool_id": "block_source", "params": {"src": "10.0.0.9", "ttl_s": 120}}'
        )
    )
    run = run_agent_loop(
        scenario="PORT_SCAN",
        metric_before=10.0,
        controller=MockController(),
        level=AutonomyLevel.N2,
        planner=planner,
    )
    step = run.trajectory.steps[0]
    assert step.source == "llm"
    assert step.tool_id == "block_source"
    assert step.metric_before == 10.0


def test_budget_limits_steps():
    controller = MockController(effect=lambda before: before * 2.0)
    run = _run("DDOS_ATTACK", controller, budget=LoopBudget(max_steps=1))
    assert len(run.trajectory.steps) == 1


def test_trajectory_hash_is_deterministic():
    first = _run("DDOS_ATTACK", MockController(effect=lambda before: before * 0.5))
    second = _run("DDOS_ATTACK", MockController(effect=lambda before: before * 0.5))
    assert first.trajectory.hash() == second.trajectory.hash()
    other = _run("DDOS_ATTACK", MockController(effect=lambda before: before * 2.0))
    assert other.trajectory.hash() != first.trajectory.hash()


def test_noop_scenario_does_not_act():
    run = run_agent_loop(
        scenario="NORMAL",
        metric_before=1.0,
        controller=MockController(),
        level=AutonomyLevel.N2,
    )
    assert run.trajectory.outcome == "noop"
    assert run.trajectory.steps[0].verdict == "noop"


def test_tool_params_validation_and_rendering():
    tool = CATALOG["rate_limit"]
    params = validate_params(tool, {"src": "10.0.0.5", "rate": "1mbit"})
    assert params["iface"] == "eth0"
    action = to_action(tool, params)
    assert "10.0.0.5" in action.parameters["command"]
    assert action.rollback == "tc qdisc del dev eth0 root"
    try:
        validate_params(tool, {"nope": 1})
    except ToolParamError:
        pass
    else:  # pragma: no cover
        raise AssertionError("parâmetro desconhecido deveria falhar")


def test_scenario_mapping_points_to_known_tools():
    for scenario in (
        "NORMAL", "DDOS_ATTACK", "PORT_SCAN", "HOST_DOWN", "SERVICE_OUTAGE",
        "DISK_EXHAUSTION", "MEMORY_LEAK", "NETWORK_CONGESTION",
        "DATA_EXFILTRATION", "COMBINED_FAULT",
    ):
        tools = tools_for_scenario(scenario)
        assert tools
        assert all(tool.id in CATALOG for tool in tools)


def test_deterministic_planner_skips_history():
    planner = DeterministicPlanner()
    tools = tools_for_scenario("DDOS_ATTACK")
    first = planner.decide(scenario="DDOS_ATTACK", tools=tools, history=[])
    assert first is not None and first.tool_id == "rate_limit"
    second = planner.decide(scenario="DDOS_ATTACK", tools=tools, history=["rate_limit"])
    assert second is not None and second.tool_id == "block_source"


def test_parse_tool_decision_rejects_unknown_tool():
    tools = tools_for_scenario("DDOS_ATTACK")
    assert parse_tool_decision('{"tool_id": "nuke"}', tools) is None
    decision = parse_tool_decision('{"tool_id": "rate_limit"}', tools)
    assert decision is not None and decision.params["iface"] == "eth0"


def test_gate_high_risk_requires_reversibility():
    from Backend.services.agent.actions import ActionSpec

    assert gate(AutonomyLevel.N2, ActionSpec("x", reversible=True), high_risk=True) is True
    assert gate(AutonomyLevel.N2, ActionSpec("x", reversible=False), high_risk=True) is False
