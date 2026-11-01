"""Reprodução de ponta a ponta (Fase 08).

Executa os baselines do zero a partir de configs, emite o manifesto (commit,
hashes de config/dataset/motor, seeds, versões) e o relatório. Determinístico:
rodar duas vezes produz os mesmos hashes de métrica.

Uso:
    python -m Backend.harness.repro --smoke
    python -m Backend.harness.repro --full
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from Backend.harness.baselines import run_baselines
from Backend.harness.config import ExperimentConfig
from Backend.harness.report import build_report
from Backend.harness.splits import make_regime_splits

SMOKE = {"n_per_class": 40, "n_boot": 200}
FULL = {"n_per_class": 500, "n_boot": 1000}


def dataset_hash(split: Any) -> str:
    digest = hashlib.sha256()
    digest.update(np.round(np.asarray(split.X, dtype=float), 6).tobytes())
    digest.update(np.asarray(split.y, dtype=object).astype(str).tobytes())
    digest.update(np.round(np.asarray(split.severity, dtype=float), 6).tobytes())
    return digest.hexdigest()[:32]


def package_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for name in ("numpy", "scipy", "sklearn", "pandas", "matplotlib", "torch", "transformers"):
        try:
            module = __import__(name)
            versions[name] = str(getattr(module, "__version__", "?"))
        except ImportError:
            versions[name] = "ausente"
    return versions


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True
        ).strip()
    except Exception:
        return "desconhecido"


def run_all(
    *,
    n_per_class: int = 40,
    seed: int = 0,
    n_boot: int = 200,
    results_dir: str | Path = "Backend/harness/results",
    tune: bool = True,
    write: bool = True,
) -> dict[str, Any]:
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    splits = make_regime_splits(n_per_class=n_per_class, seed=seed)
    baselines = run_baselines(
        splits, seed=seed, results_dir=results_dir if write else None, n_boot=n_boot, tune=tune
    )

    configs = {
        "baseline:heuristic": ExperimentConfig(
            name="baseline:heuristic", dataset_id="regime", split_id="train->test",
            engine="heuristic", seed=seed,
        ).config_hash,
        "baseline:random_forest": ExperimentConfig(
            name="baseline:random_forest", dataset_id="regime", split_id="train->test",
            engine="random_forest", seed=seed,
        ).config_hash,
    }

    manifest: dict[str, Any] = {
        "git_commit": git_commit(),
        "generated_at": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "seed": seed,
        "n_per_class": n_per_class,
        "n_boot": n_boot,
        "package_versions": package_versions(),
        "config_hashes": configs,
        "dataset_hashes": {name: dataset_hash(split) for name, split in splits.items()},
        "engines": {r["engine"]: r["engine"] for r in baselines["table"]},
        "metric_hashes": {
            r["engine"]: r["canonical_hash"] for r in baselines["table"]
        },
        "baseline_macro_f1": {
            r["engine"]: round(r["macro_f1"], 6) for r in baselines["table"]
        },
    }

    if write:
        (results_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        build_report(results_dir, manifest, write=True)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--results-dir", default="Backend/harness/results")
    args = parser.parse_args()

    params = FULL if args.full else SMOKE
    manifest = run_all(
        n_per_class=params["n_per_class"],
        n_boot=params["n_boot"],
        seed=args.seed,
        results_dir=args.results_dir,
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
