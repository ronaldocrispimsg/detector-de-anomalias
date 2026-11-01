"""Avalia o agente LLM no split de regime (Fase 03).

Uso:
    python scripts/eval_llm_agent.py --model Qwen/Qwen2.5-0.5B-Instruct \
        --n-per-class 30 --mode zero_shot

Escreve um registro em `Backend/harness/results/` e um JSONL de respostas cruas
para auditoria. Não faz parte do pytest (depende de rede/modelo).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from Backend.harness.metrics import classification_metrics, macro_f1
from Backend.harness.splits import make_regime_splits
from Backend.harness.stats import bootstrap_ci_metric
from Backend.services.agent.models import TorchProvider
from Backend.services.agent.policy import PROMPT_VERSION
from Backend.services.agent.representation import serialize
from Backend.services.agent.telemetry import Telemetry

warnings.filterwarnings("ignore")


def _few_shot_examples(train, k: int) -> list[tuple[str, str]]:
    examples: list[tuple[str, str]] = []
    labels = train.y
    for label in sorted(set(labels.tolist())):
        idx = np.where(labels == label)[0][:k]
        for i in idx:
            sample = Telemetry.from_features(np.asarray(train.X[i], dtype=float))
            examples.append((serialize(sample), str(label)))
    return examples


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
    parser.add_argument("--n-per-class", type=int, default=30)
    parser.add_argument("--mode", default="zero_shot", choices=["zero_shot", "few_shot"])
    parser.add_argument("--few-shot-k", type=int, default=3)
    parser.add_argument("--max-new-tokens", type=int, default=192)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--results-dir", default="Backend/harness/results")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    from Backend.harness.engines.llm_agent import LLMAgentEngine

    splits = make_regime_splits(n_per_class=args.n_per_class, seed=args.seed)
    test = splits["test"]
    examples = (
        _few_shot_examples(splits["train"], args.few_shot_k)
        if args.mode == "few_shot"
        else None
    )

    provider = TorchProvider(args.model, max_new_tokens=args.max_new_tokens)
    engine = LLMAgentEngine(
        provider, mode=args.mode, examples=examples, prompt_version=PROMPT_VERSION
    )

    t0 = time.time()
    y_pred = engine.predict(test.X)
    elapsed = time.time() - t0

    y_true = np.asarray([str(v) for v in test.y.tolist()], dtype=object)
    y_pred = np.asarray([str(v) for v in y_pred.tolist()], dtype=object)
    metrics = classification_metrics(y_true, y_pred)
    ci = bootstrap_ci_metric(y_true, y_pred, macro_f1, seed=args.seed, n_boot=1000)
    valid = float(np.mean([0 if o.abstain else 1 for o in engine.outputs]))

    summary = {
        "model": args.model,
        "mode": args.mode,
        "prompt_version": PROMPT_VERSION,
        "n_per_class": args.n_per_class,
        "n_samples": int(len(y_true)),
        "seed": args.seed,
        "json_validity_rate": valid,
        "macro_f1": metrics["macro_f1"],
        "macro_f1_ci": ci,
        "accuracy": metrics["accuracy"],
        "balanced_accuracy": metrics["balanced_accuracy"],
        "per_class": metrics.get("per_class"),
        "seconds_total": round(elapsed, 2),
        "seconds_per_sample": round(elapsed / max(1, len(y_true)), 3),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    out_dir = Path(args.results_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out) if args.out else out_dir / "llm_agent_summary.json"
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    slug = args.model.replace("/", "_")
    raw_path = out_dir / f"llm_agent_raw_{slug}_{args.mode}_{args.n_per_class}.jsonl"
    with raw_path.open("w", encoding="utf-8") as fh:
        for true, pred, output in zip(y_true.tolist(), y_pred.tolist(), engine.outputs):
            fh.write(
                json.dumps(
                    {"y_true": true, "y_pred": pred, "output": output.to_dict()},
                    ensure_ascii=False,
                )
                + "\n"
            )
    print(f"escrito: {out_path} e {raw_path}")


if __name__ == "__main__":
    main()
