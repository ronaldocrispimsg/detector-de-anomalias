"""Fase 11: antialucinação e verificação."""

from __future__ import annotations

from Backend.services.agent.actions import AutonomyLevel
from Backend.services.agent.grounding import (
    apply_grounding,
    ground_evidence,
    ungrounded_evidence_rate,
)
from Backend.services.agent.guardrails import AgentOutput
from Backend.services.agent.planner import (
    SelfConsistentPlanner,
    ToolDecision,
)
from Backend.services.agent.structured import (
    AGENT_OUTPUT_SCHEMA,
    TOOL_CALL_SCHEMA,
    structured_call,
    validate_schema,
)
from Backend.services.agent.telemetry import Telemetry
from Backend.services.agent.tool_guard import (
    GuardError,
    command_for,
    guard_decision,
    off_catalog_rate,
)
from Backend.services.agent.tools import tools_for_scenario
from Backend.services.agent.verifier import verify_plan


def _telemetry(**overrides) -> Telemetry:
    base = dict(
        latency_ms=10.0,
        packet_loss_pct=0.0,
        jitter_ms=1.0,
        cpu_usage_pct=10.0,
        ram_usage_pct=20.0,
        disk_usage_pct=30.0,
        network_in_bps=1000.0,
        network_out_bps=1000.0,
        http_status_code=200,
        http_response_time_ms=20.0,
        tcp_port_open=True,
        active_connections=10,
    )
    base.update(overrides)
    return Telemetry.from_mapping(base)


def _output(**overrides) -> AgentOutput:
    base = dict(
        predicted_scenario="DDOS_ATTACK",
        is_anomaly=True,
        confidence=0.8,
        evidence=[],
    )
    base.update(overrides)
    return AgentOutput(**base)  # type: ignore[arg-type]


def test_schema_rejects_extra_field_and_wrong_type():
    good = {"predicted_scenario": "DDOS_ATTACK", "is_anomaly": True, "confidence": 0.7}
    assert validate_schema(good, AGENT_OUTPUT_SCHEMA) == []

    extra = {**good, "invented": 1}
    assert any("não permitido" in e for e in validate_schema(extra, AGENT_OUTPUT_SCHEMA))

    wrong_type = {**good, "is_anomaly": "sim"}
    assert any("esperado boolean" in e for e in validate_schema(wrong_type, AGENT_OUTPUT_SCHEMA))

    out_of_range = {**good, "confidence": 1.5}
    assert any("acima do máximo" in e for e in validate_schema(out_of_range, AGENT_OUTPUT_SCHEMA))


def test_structured_call_retries_with_feedback_then_succeeds():
    good = '{"tool_id": "rate_limit", "params": {"rate": "1mbit"}}'
    bad = '{"tool_id": "rate_limit", "extra": true}'
    prompts: list[str] = []

    def generate(prompt: str) -> str:
        prompts.append(prompt)
        return bad if len(prompts) == 1 else good

    result = structured_call(generate, "escolha", TOOL_CALL_SCHEMA, max_retries=2)
    assert result.ok
    assert result.attempts == 2
    assert len(prompts) == 2
    assert "rejeitada pelo validador" in prompts[1]


def test_structured_call_gives_up_after_budget():
    def generate(_: str) -> str:
        return '{"tool_id": "x", "extra": 1}'

    result = structured_call(generate, "escolha", TOOL_CALL_SCHEMA, max_retries=1)
    assert not result.ok
    assert result.attempts == 2
    assert result.errors


def test_ungrounded_evidence_is_dropped_and_confidence_falls():
    sample = _telemetry(network_in_bps=9000.0)
    output = _output(
        confidence=0.8,
        evidence=[
            {"metric": "network_in_bps", "value": 9000.0},
            {"metric": "made_up_metric", "value": 42.0},
        ],
    )
    result = apply_grounding(output, sample)
    assert len(result.dropped) == 1
    assert len(result.output.evidence) == 1
    assert result.agreement == 0.5
    assert result.output.confidence < 0.8
    assert not result.output.abstain


def test_grounding_forces_abstention_when_agreement_is_low():
    sample = _telemetry()
    output = _output(
        confidence=0.9,
        evidence=[
            {"metric": "invented_a", "value": 1.0},
            {"metric": "invented_b", "value": 2.0},
        ],
    )
    result = apply_grounding(output, sample, min_agreement=0.5)
    assert result.agreement == 0.0
    assert result.output.abstain
    assert result.output.predicted_scenario == "ABSTAIN"


def test_no_evidence_is_not_penalized():
    sample = _telemetry()
    output = _output(evidence=[])
    result = ground_evidence(output, sample)
    assert result.agreement == 1.0
    assert ungrounded_evidence_rate([output], [sample]) == 0.0


def test_tool_guard_blocks_command_outside_catalog():
    decision = ToolDecision(tool_id="nuke_everything", params={})
    result = guard_decision(decision, level=AutonomyLevel.N2, scenario="DDOS_ATTACK")
    assert not result.allowed
    assert result.command is None
    assert "fora do catálogo" in result.reasons[0]
    assert off_catalog_rate([decision]) == 1.0

    try:
        command_for(decision)
    except GuardError:
        pass
    else:  # pragma: no cover
        raise AssertionError("comando fora do catálogo deveria falhar")


def test_tool_guard_allows_catalog_command_and_renders_it():
    decision = ToolDecision(tool_id="rate_limit", params={"rate": "2mbit"})
    result = guard_decision(decision, level=AutonomyLevel.N2, scenario="DDOS_ATTACK")
    assert result.allowed
    assert result.command is not None and "2mbit" in result.command


def test_tool_guard_blocks_at_low_autonomy():
    decision = ToolDecision(tool_id="rate_limit", params={})
    result = guard_decision(decision, level=AutonomyLevel.N1, scenario="DDOS_ATTACK")
    assert not result.allowed
    assert "autonomia" in result.reasons[0]


def test_verifier_rejects_action_that_does_not_match_telemetry():
    tools = tools_for_scenario("DDOS_ATTACK")
    decision = ToolDecision(tool_id="rate_limit", params={})
    healthy = _telemetry().to_mapping()
    verdict = verify_plan("DDOS_ATTACK", decision, healthy, tools)
    assert not verdict.ok
    assert verdict.status == "wrong_action"


def test_verifier_accepts_action_matching_telemetry():
    tools = tools_for_scenario("DDOS_ATTACK")
    decision = ToolDecision(tool_id="rate_limit", params={})
    flood = _telemetry(network_in_bps=9_000_000.0).to_mapping()
    assert verify_plan("DDOS_ATTACK", decision, flood, tools).ok


def test_verifier_flags_ungrounded_metric():
    tools = tools_for_scenario("DDOS_ATTACK")
    decision = ToolDecision(tool_id="rate_limit", params={})
    missing = _telemetry(network_in_bps=9_000_000.0).to_mapping()
    del missing["network_in_bps"]
    verdict = verify_plan("DDOS_ATTACK", decision, missing, tools)
    assert verdict.status == "ungrounded:network_in_bps"


def test_self_consistency_abstains_when_samples_diverge():
    outputs = iter(
        [
            '{"tool_id": "rate_limit"}',
            '{"tool_id": "block_source"}',
        ]
    )
    planner = SelfConsistentPlanner(generate=lambda _: next(outputs), k=2)
    decision = planner.decide(scenario="DDOS_ATTACK", tools=tools_for_scenario("DDOS_ATTACK"))
    assert decision is None


def test_self_consistency_returns_majority():
    planner = SelfConsistentPlanner(generate=lambda _: '{"tool_id": "block_source"}', k=3)
    decision = planner.decide(scenario="DDOS_ATTACK", tools=tools_for_scenario("DDOS_ATTACK"))
    assert decision is not None and decision.tool_id == "block_source"


def test_loop_verifier_blocks_action_not_matching_telemetry():
    from Backend.services.agent.controllers.mock import MockController
    from Backend.services.agent.loop import run_agent_loop

    healthy = _telemetry().to_mapping()
    run = run_agent_loop(
        scenario="DDOS_ATTACK",
        metric_before=1000.0,
        controller=MockController(effect=lambda before: before * 0.5),
        level=AutonomyLevel.N2,
        telemetry=healthy,
        verifier=lambda decision: verify_plan(
            "DDOS_ATTACK", decision, healthy, tools_for_scenario("DDOS_ATTACK")
        ),
    )
    assert run.trajectory.steps
    assert all(step.verdict == "blocked" for step in run.trajectory.steps)
    assert run.operational_metrics()["actions_applied"] == 0.0


def test_loop_guard_blocks_command_outside_catalog():
    from Backend.services.agent.controllers.mock import MockController
    from Backend.services.agent.loop import run_agent_loop
    from Backend.services.agent.planner import DeterministicPlanner

    class EvilPlanner(DeterministicPlanner):
        def decide(self, **_):
            return ToolDecision(tool_id="rm_rf", params={})

    run = run_agent_loop(
        scenario="DDOS_ATTACK",
        metric_before=1000.0,
        controller=MockController(),
        level=AutonomyLevel.N2,
        planner=EvilPlanner(),
        guard=lambda decision: guard_decision(
            decision, level=AutonomyLevel.N2, scenario="DDOS_ATTACK"
        ),
    )
    assert run.trajectory.steps == [] or all(
        step.verdict == "blocked" for step in run.trajectory.steps
    )
    assert run.operational_metrics()["actions_applied"] == 0.0

