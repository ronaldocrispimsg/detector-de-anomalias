"""Reprodutibilidade por anomalia no laboratório Kathará (fase 12).

Para cada anomalia: montar o lab, injetar a falha com seed fixa, medir `before`,
rodar o loop do agente, medir `after` e derrubar tudo. Emite os artefatos por
anomalia e o `trajectory_hash`.

A determinismo bit-a-bit só existe sobre o controlador mock (a telemetria real
varia entre execuções). Por isso a checagem de reprodutibilidade roda o pipeline
determinístico; a execução real grava a trajetória observada e o veredito.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from Backend.harness.kathara.runner import ScenarioResult, run_scenario
from Backend.harness.seed import set_seed
from Backend.services.agent.actions import AutonomyLevel
from Backend.services.agent.controllers.mock import MockController
from Backend.services.agent.loop import LoopBudget, run_agent_loop
from Backend.services.agent.telemetry import CLASSES

ANOMALIES: tuple[str, ...] = tuple(CLASSES)
DEFAULT_METRIC_BEFORE = 100.0

RESULTS_DIR = (
    Path(__file__).resolve().parents[1] / "results" / "kathara"
)


def stable_hash(
    scenario: str,
    *,
    level: AutonomyLevel = AutonomyLevel.N2,
    budget: LoopBudget | None = None,
    metric_before: float = DEFAULT_METRIC_BEFORE,
) -> str:
    """Hash determinístico do pipeline (controlador mock, efeito fixo)."""
    run = run_agent_loop(
        scenario=scenario,
        metric_before=metric_before,
        controller=MockController(effect=lambda before: before * 0.5),
        level=level,
        budget=budget,
    )
    return run.trajectory.hash()


def is_reproducible(scenario: str, **kwargs: Any) -> bool:
    return stable_hash(scenario, **kwargs) == stable_hash(scenario, **kwargs)


MIN_REL_IMPROVEMENT = 0.10


def verdict_from(outcome: str, before: float | None, after: float | None) -> str:
    """Veredito a partir do desfecho e das métricas.

    Exige melhora relativa de pelo menos `MIN_REL_IMPROVEMENT` (ou zero absoluto);
    delta menor é ruído de medição, não mitigação.
    """
    if outcome != "mitigated":
        return outcome
    if before is None or after is None:
        return "unverified"
    if after == 0.0 and before > 0.0:
        return "mitigated"
    if before > 0.0 and after <= before * (1.0 - MIN_REL_IMPROVEMENT):
        return "mitigated"
    return "unverified"


def anomaly_verdict(result: ScenarioResult) -> str:
    return verdict_from(result.outcome, result.metric_before, result.metric_after)


def lab_versions() -> dict[str, Any]:
    versions: dict[str, Any] = {}
    try:
        from Kathara import __version__ as kathara_version

        versions["kathara"] = kathara_version
    except Exception:  # pragma: no cover - depende do ambiente
        versions["kathara"] = "unknown"
    try:
        import docker

        client = docker.from_env()
        image = client.images.get("kathara/base")
        versions["kathara_base_image"] = image.id[:12]
    except Exception:  # pragma: no cover - depende do ambiente
        versions["kathara_base_image"] = "unknown"
    return versions


def _seed_value(seed: int) -> int:
    digest = hashlib.sha256(str(seed).encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def run_anomaly(
    scenario: str,
    *,
    seed: int = 0,
    config: Mapping[str, Any] | None = None,
    budget: LoopBudget | None = None,
    level: AutonomyLevel = AutonomyLevel.N2,
    keep: bool = False,
) -> ScenarioResult:
    """Roda a anomalia no lab real com seed fixa."""
    set_seed(_seed_value(seed))
    return run_scenario(scenario, config, budget=budget, level=level, keep=keep)


def write_artifacts(
    result: ScenarioResult,
    *,
    seed: int = 0,
    root: str | Path | None = None,
    versions: Mapping[str, Any] | None = None,
) -> Path:
    """Grava before_after.json, trajectory.jsonl e manifest.json da anomalia."""
    root = Path(root) if root is not None else RESULTS_DIR
    out_dir = root / result.scenario
    out_dir.mkdir(parents=True, exist_ok=True)

    before_after = {
        "scenario": result.scenario,
        "metric": result.metric,
        "before": result.metric_before,
        "after": result.metric_after,
        "verdict": anomaly_verdict(result),
        "outcome": result.outcome,
        "trajectory_hash": result.trajectory_hash,
        "operational_metrics": result.operational_metrics,
    }
    (out_dir / "before_after.json").write_text(
        json.dumps(before_after, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    steps = result.trajectory.get("steps", [])
    lines = [json.dumps(step, sort_keys=True, ensure_ascii=False) for step in steps]
    (out_dir / "trajectory.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    manifest = {
        "scenario": result.scenario,
        "seed": seed,
        "trajectory_hash": result.trajectory_hash,
        "reproducible": is_reproducible(result.scenario),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "versions": dict(versions or {}),
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return out_dir


@dataclass
class ReproOutcome:
    scenario: str
    trajectory_hash: str
    verdict: str
    reproducible: bool
    path: Path


def run_all(
    *,
    seed: int = 0,
    root: str | Path | None = None,
    only: Iterable[str] | None = None,
    real: bool = True,
    keep: bool = False,
) -> list[ReproOutcome]:
    """Roda todas as anomalias (ou as de `only`) e grava os artefatos.

    `real=False` usa o pipeline determinístico (sem Docker) — útil para o smoke.
    """
    scenarios = tuple(only) if only is not None else ANOMALIES
    versions = lab_versions() if real else {}
    outcomes: list[ReproOutcome] = []
    for scenario in scenarios:
        if real:
            result = run_anomaly(scenario, seed=seed, keep=keep)
        else:
            mock = MockController(effect=lambda before: before * 0.5)
            run = run_agent_loop(
                scenario=scenario,
                metric_before=DEFAULT_METRIC_BEFORE,
                controller=mock,
                level=AutonomyLevel.N2,
            )
            result = ScenarioResult(
                scenario=scenario,
                metric=None,
                metric_before=DEFAULT_METRIC_BEFORE,
                metric_after=DEFAULT_METRIC_BEFORE * 0.5,
                outcome=run.trajectory.outcome,
                trajectory_hash=run.trajectory.hash(),
                trajectory=run.trajectory.to_dict(),
                operational_metrics=run.operational_metrics(),
            )
        path = write_artifacts(result, seed=seed, root=root, versions=versions)
        outcomes.append(
            ReproOutcome(
                scenario=scenario,
                trajectory_hash=result.trajectory_hash,
                verdict=anomaly_verdict(result),
                reproducible=is_reproducible(scenario),
                path=path,
            )
        )
    return outcomes


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Repro por anomalia no Kathará.")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--only", nargs="*", choices=list(ANOMALIES))
    parser.add_argument("--smoke", action="store_true", help="pipeline mock, sem Docker")
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()

    outcomes = run_all(
        seed=args.seed, only=args.only, real=not args.smoke, keep=args.keep
    )
    for outcome in outcomes:
        print(
            f"{outcome.scenario}: verdict={outcome.verdict} "
            f"hash={outcome.trajectory_hash[:12]} reproducible={outcome.reproducible} "
            f"→ {outcome.path}"
        )


if __name__ == "__main__":
    main()
