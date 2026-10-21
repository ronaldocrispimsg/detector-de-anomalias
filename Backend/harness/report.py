"""Relatório científico: markdown + figuras a partir dos artefatos de resultado."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_json(path: str | Path) -> dict[str, Any] | None:
    path = Path(path)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def render_baselines_table(records: list[dict[str, Any]]) -> str:
    lines = [
        "| Motor | macro-F1 | IC95 | acurácia | balanceada |",
        "|---|---|---|---|---|",
    ]
    for r in sorted(records, key=lambda x: -x.get("macro_f1", 0.0)):
        ci = r.get("macro_f1_ci") or {}
        ci_text = f"[{ci.get('lo', 0):.3f}, {ci.get('hi', 0):.3f}]" if ci else "—"
        lines.append(
            f"| {r['engine']} | {r.get('macro_f1', 0):.3f} | {ci_text} | "
            f"{r.get('accuracy', 0):.3f} | {r.get('balanced_accuracy', 0):.3f} |"
        )
    return "\n".join(lines)


def plot_baselines(records: list[dict[str, Any]], path: str | Path) -> Path | None:
    if not records:
        return None
    ordered = sorted(records, key=lambda x: x.get("macro_f1", 0.0))
    names = [r["engine"] for r in ordered]
    values = [r.get("macro_f1", 0.0) for r in ordered]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.barh(names, values, color="#3b6fb6")
    ax.set_xlabel("macro-F1 (regime de teste sutil)")
    ax.set_xlim(0, 1)
    fig.tight_layout()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def plot_coverage_risk(points: list[dict[str, Any]], path: str | Path) -> Path | None:
    if not points:
        return None
    coverages = [p["coverage"] for p in points]
    risks = [p["risk"] for p in points]
    fig, ax = plt.subplots(figsize=(6, 4.5))
    ax.plot(coverages, risks, marker="o", color="#b6463b")
    ax.set_xlabel("cobertura")
    ax.set_ylabel("risco (erro entre respondidas)")
    ax.set_ylim(0, 1)
    ax.set_xlim(0, 1)
    fig.tight_layout()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def build_report(
    results_dir: str | Path,
    manifest: dict[str, Any],
    *,
    write: bool = True,
) -> str:
    results = Path(results_dir)
    baselines = load_jsonl(results / "baselines.jsonl")
    llm = load_json(results / "llm_agent_summary.json")
    rag = load_jsonl(results / "rag_ablation.jsonl")
    calibration = load_json(results / "decision_calibration.json")
    coverage = load_jsonl(results / "coverage_risk.jsonl")
    xai = load_jsonl(results / "xai_report.jsonl")

    baselines_png = plot_baselines(baselines, results / "baselines.png")
    coverage_png = plot_coverage_risk(coverage, results / "coverage_risk.png")

    parts: list[str] = [
        "# Relatório — agente de anomalias NetSpot",
        "",
        "## Manifesto",
        "```json",
        json.dumps(manifest, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Baselines",
        render_baselines_table(baselines) if baselines else "_sem dados_",
    ]
    if baselines_png:
        parts += ["", f"![baselines]({baselines_png.name})"]

    parts += ["", "## Agente LLM (zero-shot)"]
    if llm:
        parts += [
            f"- modelo: `{llm.get('model')}` ({llm.get('mode')})",
            f"- JSON válido: {llm.get('json_validity_rate', 0):.3f}",
            f"- macro-F1: {llm.get('macro_f1', 0):.3f} "
            f"(IC {llm.get('macro_f1_ci', {}).get('lo', 0):.3f}-"
            f"{llm.get('macro_f1_ci', {}).get('hi', 0):.3f})",
            f"- latência/amostra: {llm.get('seconds_per_sample', 0):.2f} s",
        ]
    else:
        parts.append("_sem dados_")

    parts += ["", "## Ablação RAG"]
    if rag:
        for entry in rag:
            parts.append(
                f"- k={entry.get('k')}: sem RAG {entry['without_rag']['macro_f1']:.3f} "
                f"vs com RAG {entry['with_rag']['macro_f1']:.3f}; "
                f"McNemar p={entry.get('mcnemar', {}).get('pvalue')}; "
                f"precisão retrieval {entry.get('retrieval_precision', 0):.3f}"
            )
    else:
        parts.append("_sem dados_")

    parts += ["", "## Decisão e abstenção"]
    if calibration:
        parts.append("```json")
        parts.append(json.dumps(calibration, indent=2, ensure_ascii=False))
        parts.append("```")
    if coverage_png:
        parts += ["", f"![cobertura-risco]({coverage_png.name})"]
    if not calibration and not coverage:
        parts.append("_sem dados_")

    parts += ["", "## Explicabilidade"]
    if xai:
        for entry in xai:
            if "label" in entry:
                parts.append(
                    f"- {entry['label']}: rubrica {entry.get('mean_rubric', 0):.2f}, "
                    f"aderência de evidência {entry.get('evidence_agreement', 0):.2f}"
                )
    else:
        parts.append("_sem dados_")

    parts += [
        "",
        "## Ameaças à validade",
        "- Simulador único é circular: o holdout externo (Kathará/datasets públicos) "
        "ainda não foi executado; resultados refletem o simulador.",
        "- O teste sutil (severidade 0.25-0.40) é um regime não visto no treino; "
        "modelos clássicos saturam no regime fácil, não aqui.",
        "- Medições do LLM usam um proxy pequeno (1.5B) no Mac; o alvo 7B roda em "
        "Linux/GPU e ainda não tem número.",
        "- PEFT está implementado e testado, mas o treino/comparativo real pendem de "
        "GPU; H1/H2 ainda sem número.",
        "",
    ]

    text = "\n".join(parts)
    if write:
        (results / "report.md").write_text(text, encoding="utf-8")
    return text
