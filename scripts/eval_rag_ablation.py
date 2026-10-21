"""Ablação RAG on/off com o agente LLM (Fase 04).

Uso:
    python scripts/eval_rag_ablation.py --model Qwen/Qwen2.5-1.5B-Instruct \
        --n-per-class 5 --k 3

Escreve `Backend/harness/results/rag_ablation.jsonl`.
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

warnings.filterwarnings("ignore")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Qwen/Qwen2.5-1.5B-Instruct")
    parser.add_argument("--n-per-class", type=int, default=5)
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--max-new-tokens", type=int, default=160)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--results-dir", default="Backend/harness/results")
    args = parser.parse_args()

    from Backend.harness.config import ExperimentConfig
    from Backend.harness.engines.llm_agent import LLMAgentEngine
    from Backend.harness.engines.rag_retriever import run_rag_ablation
    from Backend.harness.splits import make_regime_splits
    from Backend.services.agent.models import TorchProvider

    splits = make_regime_splits(n_per_class=args.n_per_class, seed=args.seed)
    provider = TorchProvider(args.model, max_new_tokens=args.max_new_tokens)

    config = ExperimentConfig(
        name="rag_ablation",
        dataset_id=f"regime:n{args.n_per_class}",
        split_id="test",
        engine="llm_agent",
        seed=args.seed,
        metrics=("macro_f1",),
    )

    def factory(retriever):
        return LLMAgentEngine(
            provider,
            context_fn=retriever.retrieve if retriever is not None else None,
            model_id=args.model,
        )

    result = run_rag_ablation(
        config, splits, factory, k=args.k, results_dir=args.results_dir, n_boot=1000
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
