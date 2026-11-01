"""Avalia um cenário no laboratório Kathará (fase 10).

Uso:
    .venv/bin/python scripts/eval_kathara.py --scenario DDOS_ATTACK
    .venv/bin/python scripts/eval_kathara.py --all
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from Backend.harness.kathara.runner import run_scenario
from Backend.services.agent.telemetry import CLASSES

RESULTS = Path(__file__).resolve().parents[1] / "Backend" / "harness" / "results" / "kathara"


def main() -> None:
    parser = argparse.ArgumentParser(description="Avalia cenários Kathará.")
    parser.add_argument("--scenario", choices=list(CLASSES), default="DDOS_ATTACK")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--keep", action="store_true", help="não derruba o laboratório")
    args = parser.parse_args()

    scenarios = list(CLASSES) if args.all else [args.scenario]
    RESULTS.mkdir(parents=True, exist_ok=True)

    for scenario in scenarios:
        result = run_scenario(scenario, keep=args.keep)
        out = RESULTS / f"{scenario}.json"
        out.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        print(
            f"{scenario}: outcome={result.outcome} metric={result.metric} "
            f"before={result.metric_before} after={result.metric_after} "
            f"hash={result.trajectory_hash[:12]} → {out}"
        )


if __name__ == "__main__":
    main()
