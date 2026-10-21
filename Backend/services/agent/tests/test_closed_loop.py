"""Fase 06: calibração/ensemble, abstenção, gate e ciclo fechado."""

from __future__ import annotations

import numpy as np

from Backend.harness.metrics import expected_calibration_error
from Backend.services.agent.actions import (
    ActionSpec,
    AutonomyLevel,
    gate,
    plan_actions,
    plan_for_output,
)
from Backend.services.agent.controllers.base import run_closed_loop
from Backend.services.agent.controllers.mock import MockController
from Backend.services.agent.decision import (
    WeightedEnsemble,
    abstention_curve,
    calibrate_engines,
    reorder_proba,
    temperature_scale,
)

CLASSES = (0, 1, 2)


def _synthetic(n: int = 800, seed: int = 0):
    rng = np.random.default_rng(seed)
    y = rng.integers(0, 3, n)

    def engine(acc: float) -> np.ndarray:
        probs = np.full((n, 3), 0.01)
        correct = rng.random(n) < acc
        pred = np.where(correct, y, rng.integers(0, 3, n))
        probs[np.arange(n), pred] = 0.98
        return probs

    return y, [engine(0.9), engine(0.7), engine(0.5)]


def test_ensemble_calibrated_ece_not_worse_than_engines():
    y, prob_mats = _synthetic()
    report = calibrate_engines(prob_mats, y, CLASSES)
    ece_before = [e["ece_before"] for e in report["per_engine"]]
    ece_after = [e["ece_after"] for e in report["per_engine"]]
    for before, after in zip(ece_before, ece_after):
        assert after <= before + 1e-9
    assert report["ensemble"]["ece"] <= max(ece_before) + 1e-9


def test_reorder_proba_aligns_sklearn_class_order():
    # sklearn ordena alfabeticamente: ['a','b','c']; alvo em outra ordem.
    model_classes = ["a", "b", "c"]
    probs = np.array([[0.7, 0.2, 0.1]])  # colunas a,b,c
    reordered = reorder_proba(model_classes, probs, ["c", "b", "a"])
    assert reordered.tolist() == [[0.1, 0.2, 0.7]]


def test_temperature_scaling_lowers_ece():
    y, prob_mats = _synthetic()
    probs = prob_mats[0]
    ece_before, _ = expected_calibration_error(y, probs, classes=CLASSES)
    calibrated, temperature = temperature_scale(probs, y, CLASSES)
    ece_after, _ = expected_calibration_error(y, calibrated, classes=CLASSES)
    assert ece_after <= ece_before
    assert temperature > 0


def test_abstention_curve_reduces_risk():
    y, prob_mats = _synthetic()
    ensemble = WeightedEnsemble(classes=CLASSES).fit(prob_mats, y)
    probs = ensemble.predict_proba(prob_mats)
    curve = abstention_curve(probs, y, CLASSES, thresholds=(0.0, 0.5, 0.9, 1.01))
    coverages = [p["coverage"] for p in curve]
    assert coverages == sorted(coverages, reverse=True)
    assert curve[-1]["coverage"] == 0.0 or curve[-1]["risk"] <= curve[0]["risk"]


def test_dry_run_does_not_change_state():
    controller = MockController()
    before = dict(controller.state)
    result = controller.dry_run(ActionSpec("rate_limit"))
    assert result.applied is False
    assert controller.state == before


def _output(scenario: str, abstain: bool = False):
    from Backend.services.agent.guardrails import AgentOutput

    return AgentOutput(
        predicted_scenario=scenario,
        is_anomaly=scenario != "NORMAL",
        confidence=0.9,
        abstain=abstain,
    )


def test_verify_false_triggers_rollback():
    controller = MockController(effect=lambda before: before * 2.0)
    actions = plan_actions("DDOS_ATTACK")
    loop = run_closed_loop(
        _output("DDOS_ATTACK"), actions, controller, level=AutonomyLevel.N2,
        metric_before=100.0,
    )
    applied = [r for r in loop.results if r.applied]
    assert applied and all(r.rolled_back for r in applied)
    assert loop.operational_metrics()["rollback_rate"] == 1.0


def test_gate_blocks_action_at_n1():
    controller = MockController()
    actions = plan_actions("DDOS_ATTACK")
    loop = run_closed_loop(
        _output("DDOS_ATTACK"), actions, controller, level=AutonomyLevel.N1,
        metric_before=100.0,
    )
    assert loop.results and all(not r.applied for r in loop.results)
    assert loop.operational_metrics()["actions_applied"] == 0.0


def test_gate_semantics_and_plan_for_output():
    reversible = ActionSpec("rate_limit", reversible=True)
    irreversible = ActionSpec("drop_table", reversible=False)
    assert gate(AutonomyLevel.N1, reversible) is False
    assert gate(AutonomyLevel.N2, reversible) is True
    assert gate(AutonomyLevel.N2, irreversible, high_risk=True) is False
    planned = plan_for_output(_output("DDOS_ATTACK"), level=AutonomyLevel.N2)
    assert planned and all(p["allowed"] for p in planned)
    assert plan_for_output(_output("NORMAL", abstain=True), level=AutonomyLevel.N2) == []
