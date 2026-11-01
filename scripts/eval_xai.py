"""Relatório XAI real (Fase 07).

Reconstrói o split de teste determinístico e alinha as saídas cruas do agente
com as amostras, medindo aderência da evidência e rubrica. Também gera a
importância por permutação do RandomForest. Escreve `xai_report.jsonl`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from Backend.harness.splits import make_regime_splits
from Backend.services.agent.guardrails import AgentOutput
from Backend.services.agent.telemetry import Telemetry
from Backend.services.agent.xai import permutation_importance, xai_report

RAW = "Backend/harness/results/llm_agent_raw_Qwen_Qwen2.5-1.5B-Instruct_zero_shot_15.jsonl"


def _load_outputs(path: str) -> list[AgentOutput]:
    outputs = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            record = json.loads(line)
            outputs.append(AgentOutput(**record["output"]))
    return outputs


def main() -> None:
    splits = make_regime_splits(n_per_class=15, seed=0)
    test = splits["test"]
    outputs = _load_outputs(RAW)
    assert len(outputs) == len(test), (len(outputs), len(test))
    samples = [Telemetry.from_features(row) for row in test.X]
    y_true = [str(v) for v in test.y.tolist()]

    report = xai_report(outputs, samples, y_true)

    from sklearn.ensemble import RandomForestClassifier

    rf = RandomForestClassifier(n_estimators=200, random_state=0).fit(
        splits["train"].X, splits["train"].y
    )
    importance = permutation_importance(rf, test.X, test.y, n_repeats=5)

    out = Path("Backend/harness/results/xai_report.jsonl")
    with out.open("w", encoding="utf-8") as fh:
        for label, entry in sorted(report.items()):
            fh.write(json.dumps({"label": label, **entry}, ensure_ascii=False) + "\n")
        fh.write(json.dumps({"global_permutation_importance": importance}, ensure_ascii=False) + "\n")

    overall_agreement = float(
        np.mean([entry["evidence_agreement"] for entry in report.values()])
    )
    overall_rubric = float(np.mean([entry["mean_rubric"] for entry in report.values()]))
    print(json.dumps({
        "overall_evidence_agreement": overall_agreement,
        "overall_mean_rubric": overall_rubric,
        "per_class": report,
        "top_importance": dict(sorted(importance.items(), key=lambda kv: -kv[1])[:5]),
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
