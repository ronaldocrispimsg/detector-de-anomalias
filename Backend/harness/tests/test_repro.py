"""Fase 08: repro determinístico e relatório completo."""

from __future__ import annotations

import json

from Backend.harness.repro import run_all


def test_repro_is_deterministic_and_complete(tmp_path):
    first = run_all(n_per_class=20, n_boot=50, seed=0, results_dir=tmp_path / "a")
    second = run_all(n_per_class=20, n_boot=50, seed=0, results_dir=tmp_path / "b")

    assert first["dataset_hashes"] == second["dataset_hashes"]
    assert first["metric_hashes"] == second["metric_hashes"]
    assert first["config_hashes"] == second["config_hashes"]
    assert set(first["metric_hashes"]) == set(first["baseline_macro_f1"])

    for out_dir in (tmp_path / "a", tmp_path / "b"):
        assert (out_dir / "manifest.json").exists()
        assert (out_dir / "report.md").exists()
        assert (out_dir / "baselines.jsonl").exists()

    report = (tmp_path / "a" / "report.md").read_text(encoding="utf-8")
    assert "Ameaças à validade" in report
    assert "Baselines" in report

    manifest = json.loads((tmp_path / "a" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["git_commit"]
    assert manifest["package_versions"]["numpy"] != "?"
    assert manifest["dataset_hashes"]["test"]
