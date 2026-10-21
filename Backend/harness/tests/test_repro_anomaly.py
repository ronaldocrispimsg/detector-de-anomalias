"""Reprodução por anomalia e relatório HTML."""

from __future__ import annotations

import json

import pytest

from Backend.harness.kathara.repro_anomaly import (
    ANOMALIES,
    is_reproducible,
    run_all,
    stable_hash,
    write_artifacts,
)
from Backend.harness.kathara.runner import ScenarioResult
from scripts.make_report_html import WORKSTREAMS, build_report_html

SCENARIOS = ("DDOS_ATTACK", "DATA_EXFILTRATION", "PORT_SCAN", "DISK_EXHAUSTION")


def test_same_scenario_has_same_hash():
    for scenario in SCENARIOS:
        assert stable_hash(scenario) == stable_hash(scenario)
        assert is_reproducible(scenario)


def test_stable_hash_varies_by_scenario():
    hashes = {stable_hash(scenario) for scenario in SCENARIOS}
    assert len(hashes) == len(SCENARIOS)


def _result(scenario: str, before: float, after: float, outcome: str) -> ScenarioResult:
    return ScenarioResult(
        scenario=scenario,
        metric="network_in_bps",
        metric_before=before,
        metric_after=after,
        outcome=outcome,
        trajectory_hash=stable_hash(scenario),
        trajectory={
            "scenario": scenario,
            "steps": [{"index": 0, "tool_id": "rate_limit", "verdict": "kept"}],
        },
        operational_metrics={"actions_applied": 1.0},
    )


def test_write_artifacts_has_explicit_verdict(tmp_path):
    result = _result("DDOS_ATTACK", 4_000_000.0, 1_000_000.0, "mitigated")
    out_dir = write_artifacts(result, seed=7, root=tmp_path, versions={"kathara": "3.8.3"})

    assert (out_dir / "before_after.json").exists()
    assert (out_dir / "trajectory.jsonl").exists()
    assert (out_dir / "manifest.json").exists()

    before_after = json.loads((out_dir / "before_after.json").read_text(encoding="utf-8"))
    assert before_after["verdict"] == "mitigated"
    assert before_after["before"] == 4_000_000.0
    assert before_after["after"] == 1_000_000.0

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["seed"] == 7
    assert manifest["reproducible"] is True
    assert manifest["versions"]["kathara"] == "3.8.3"

    step = json.loads((out_dir / "trajectory.jsonl").read_text(encoding="utf-8").strip())
    assert step["tool_id"] == "rate_limit"


def test_anomaly_verdict_requires_improvement():
    from Backend.harness.kathara.repro_anomaly import verdict_from

    assert verdict_from("mitigated", 1.0, 2.0) == "unverified"
    assert verdict_from("mitigated", 2.0, 1.0) == "mitigated"
    assert verdict_from("mitigated", 1.0, 0.0) == "mitigated"
    # delta pequeno (ruído) não conta como mitigação
    assert verdict_from("mitigated", 0.069, 0.065) == "unverified"
    assert verdict_from("reverted", 1.0, 1.0) == "reverted"
    assert verdict_from("mitigated", None, None) == "unverified"


def test_run_all_smoke_covers_every_anomaly(tmp_path):
    outcomes = run_all(root=tmp_path, real=False)
    assert [o.scenario for o in outcomes] == list(ANOMALIES)
    assert all(o.reproducible for o in outcomes)
    for outcome in outcomes:
        assert (tmp_path / outcome.scenario / "before_after.json").exists()


def test_html_contains_all_workstreams_and_anomaly_section(tmp_path):
    kathara_dir = tmp_path / "kathara" / "DDOS_ATTACK"
    kathara_dir.mkdir(parents=True)
    (kathara_dir / "before_after.json").write_text(
        json.dumps(
            {
                "scenario": "DDOS_ATTACK",
                "metric": "network_in_bps",
                "before": 4200000.0,
                "after": 1000000.0,
                "verdict": "mitigated",
                "trajectory_hash": "deadbeef",
            }
        ),
        encoding="utf-8",
    )

    html_text = build_report_html(tmp_path)
    assert len(WORKSTREAMS) >= 13
    for entry in WORKSTREAMS.values():
        assert entry["name"] in html_text
        assert entry["covers"] in html_text
    assert "Ataque DDoS" in html_text
    assert "Mitigação em laboratório" in html_text


@pytest.mark.integration
def test_real_anomaly_run_is_mitigated(tmp_path):
    import shutil
    import subprocess

    if shutil.which("docker") is None or subprocess.run(
        ["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ).returncode != 0:
        pytest.skip("Docker não está acessível")

    from Backend.harness.kathara.repro_anomaly import run_anomaly, verdict_from

    result = run_anomaly("DDOS_ATTACK", seed=1)
    assert result.metric_before is not None and result.metric_after is not None
    assert result.metric_after <= result.metric_before
    assert result.trajectory_hash
    assert verdict_from(result.outcome, result.metric_before, result.metric_after) in {
        "mitigated",
        "unverified",
    }
