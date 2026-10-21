"""Avalia o holdout externo (fase 13): transferência direta do interno.

Treina os baselines no dataset interno e avalia em um dataset público externo, sem
re-treinar em nada externo. Features ausentes no externo são preenchidas com a
mediana do treino interno (documentado) — o descompasso é reportado, não escondido.

Uso:
    .venv/bin/python scripts/eval_external.py --dataset UNSW-NB15 \\
        --path /caminho/UNSW_NB15.csv --label-column attack_cat
    .venv/bin/python scripts/eval_external.py --dataset UNSW-NB15 --summary
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from Backend.harness.baselines import run_baselines
from Backend.harness.datasets import load_labeled_csv
from Backend.harness.datasets_external import LABEL_MAPS, load_external
from Backend.harness.splits import temporal_split

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INTERNAL = ROOT / "netspot_anomaly_dataset.csv"
RESULTS = ROOT / "Backend" / "harness" / "results"


def _impute(external_X: np.ndarray, train_X: np.ndarray) -> tuple[np.ndarray, list[str]]:
    """Preenche NaN do externo com a mediana do treino interno, por coluna."""
    X = np.array(external_X, dtype=float, copy=True)
    imputed: list[str] = []
    for col in range(X.shape[1]):
        column = X[:, col]
        if np.isnan(column).any():
            median = float(np.nanmedian(train_X[:, col]))
            if np.isnan(median):
                median = 0.0
            column[np.isnan(column)] = median
            imputed.append(str(col))
    return X, imputed


def main() -> None:
    parser = argparse.ArgumentParser(description="Holdout externo (fase 13).")
    parser.add_argument("--dataset", required=True, choices=sorted(LABEL_MAPS))
    parser.add_argument("--path", type=str, default=None)
    parser.add_argument("--label-column", default="Label")
    parser.add_argument("--internal", type=Path, default=DEFAULT_INTERNAL)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--summary", action="store_true", help="só o mapeamento, sem dados")
    parser.add_argument("--out", type=Path, default=RESULTS / "external_holdout.jsonl")
    args = parser.parse_args()

    if args.summary or args.path is None:
        print(f"mapeamento {args.dataset}: {len(LABEL_MAPS[args.dataset])} rótulos")
        if args.path is None and not args.summary:
            print("sem --path: nada a avaliar (use --path ou --summary)")
        return

    external = load_external(args.path, args.dataset, label_column=args.label_column)
    print(json.dumps(external.report, indent=2, ensure_ascii=False))

    internal = load_labeled_csv(
        args.internal, label_column="scenario", time_column="timestamp", name="internal"
    )
    train, _val, _test = temporal_split(internal, name="internal")

    X_external, imputed_cols = _impute(external.split.X, train.X)
    from Backend.harness.datasets import DatasetSplit

    external_eval = DatasetSplit(
        X=X_external,
        y=external.split.y,
        severity=external.split.severity,
        groups=external.split.groups,
        times=external.split.times,
        meta={**external.split.meta, "name": f"external:{args.dataset}"},
    )

    result = run_baselines(
        {"train": train, "test": external_eval},
        seed=args.seed,
        results_dir=None,
        tune=True,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for record in result["table"]:
            fh.write(
                json.dumps(
                    {
                        "dataset": args.dataset,
                        "engine": record.get("engine"),
                        "macro_f1": record.get("macro_f1"),
                        "macro_f1_ci": record.get("macro_f1_ci"),
                        "accuracy": record.get("accuracy"),
                        "report": external.report,
                        "dropped_labels": external.dropped_labels,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    print(f"escrito {args.out}")
    best = max(result["table"], key=lambda r: r.get("macro_f1", 0.0))
    print(f"melhor motor: {best.get('engine')} macro-F1={best.get('macro_f1', 0.0):.3f}")


if __name__ == "__main__":
    main()
