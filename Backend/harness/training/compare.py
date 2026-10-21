"""Comparativo zero-shot vs few-shot vs LoRA/QLoRA e model card."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np

from Backend.harness.metrics import macro_f1
from Backend.harness.stats import bootstrap_ci_metric, mcnemar


@dataclass
class EngineResult:
    name: str
    y_pred: np.ndarray
    macro_f1: float
    ci: dict[str, float]
    json_validity: float | None
    seconds_per_sample: float | None


def _evaluate(name: str, engine: Any, X: Any, y_true: np.ndarray, *, n_boot: int, seed: int) -> EngineResult:
    import time

    t0 = time.time()
    y_pred = np.asarray([str(v) for v in engine.predict(X)], dtype=object)
    elapsed = time.time() - t0
    outputs = getattr(engine, "outputs", None)
    validity = None
    if outputs:
        validity = float(np.mean([0 if o.abstain else 1 for o in outputs]))
    return EngineResult(
        name=name,
        y_pred=y_pred,
        macro_f1=macro_f1(y_true, y_pred),
        ci=bootstrap_ci_metric(y_true, y_pred, macro_f1, n_boot=n_boot, seed=seed),
        json_validity=validity,
        seconds_per_sample=elapsed / max(1, len(y_true)),
    )


def run_peft_comparison(
    splits: dict[str, Any],
    engines: dict[str, Callable[[], Any]],
    *,
    reference: str = "zero_shot",
    fine_tuned: str = "lora",
    hypothesis_margin: float = 0.05,
    best_baseline: float | None = None,
    results_dir: str | Path | None = None,
    n_boot: int = 1000,
    seed: int = 0,
) -> dict[str, Any]:
    """Avalia cada motor no teste e testa H1 e H2.

    H1: macro-F1(fine_tuned) - macro-F1(reference) >= margem.
    H2: macro-F1(fine_tuned) >= best_baseline (se fornecido).
    """
    test = splits["test"]
    y_true = np.asarray([str(v) for v in np.asarray(test.y).tolist()], dtype=object)
    results = {
        name: _evaluate(name, factory(), test.X, y_true, n_boot=n_boot, seed=seed)
        for name, factory in engines.items()
    }

    pairwise: dict[str, Any] = {}
    if reference in results and fine_tuned in results:
        pairwise = mcnemar(y_true, results[reference].y_pred, results[fine_tuned].y_pred)

    delta = None
    h1 = None
    if reference in results and fine_tuned in results:
        delta = results[fine_tuned].macro_f1 - results[reference].macro_f1
        h1 = bool(delta >= hypothesis_margin)
    h2 = None
    if best_baseline is not None and fine_tuned in results:
        h2 = bool(results[fine_tuned].macro_f1 >= best_baseline)

    summary = {
        "n": int(len(y_true)),
        "reference": reference,
        "fine_tuned": fine_tuned,
        "hypothesis_margin": hypothesis_margin,
        "results": {
            name: {
                "macro_f1": r.macro_f1,
                "ci": r.ci,
                "json_validity": r.json_validity,
                "seconds_per_sample": r.seconds_per_sample,
            }
            for name, r in results.items()
        },
        "delta_fine_tuned_minus_reference": delta,
        "mcnemar_reference_vs_fine_tuned": pairwise,
        "H1_confirmed": h1,
        "H2_confirmed": h2,
        "best_baseline": best_baseline,
    }

    if results_dir is not None:
        out = Path(results_dir)
        out.mkdir(parents=True, exist_ok=True)
        with (out / "peft_comparison.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(summary, ensure_ascii=False) + "\n")
    return summary


def render_model_card(
    *,
    base_model: str,
    adapter_version: str,
    data_description: str,
    hyperparameters: dict[str, Any],
    metrics: dict[str, Any],
    limitations: Sequence[str],
    path: str | Path | None = None,
) -> str:
    lines = [
        f"# Model card — {base_model} ({adapter_version})",
        "",
        "## Base",
        base_model,
        "",
        "## Dados de treino",
        data_description,
        "",
        "## Hiperparâmetros",
        "```json",
        json.dumps(hyperparameters, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Métricas",
        "```json",
        json.dumps(metrics, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Limitações",
    ]
    lines.extend(f"- {item}" for item in limitations)
    text = "\n".join(lines) + "\n"
    if path is not None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return text
