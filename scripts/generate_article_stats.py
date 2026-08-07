#!/usr/bin/env python3
"""
Gera estatísticas resumidas para o artigo a partir do projeto atual.

Saídas:
- CSV com resultados por amostra
- JSON com resumo estatístico
- PNG com figura compacta para a metodologia/resultados
"""

from __future__ import annotations

import asyncio
import csv
import json
import math
import random
import statistics
import time
from dataclasses import dataclass, asdict
from pathlib import Path
import sys
import types

import numpy as np
from sklearn.metrics import accuracy_score, f1_score

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if "pydantic" not in sys.modules:
    shim = types.ModuleType("pydantic")

    class BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

        def model_dump(self):
            return dict(self.__dict__)

    def Field(default=None, **_kwargs):
        return default

    shim.BaseModel = BaseModel
    shim.Field = Field
    sys.modules["pydantic"] = shim

if "httpx" not in sys.modules:
    shim_httpx = types.ModuleType("httpx")

    class _DummyResponse:
        status_code = 503

        def json(self):
            return {}

    class AsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, *args, **kwargs):
            raise RuntimeError("httpx unavailable")

        async def post(self, *args, **kwargs):
            return _DummyResponse()

    shim_httpx.AsyncClient = AsyncClient
    sys.modules["httpx"] = shim_httpx

from Backend.services.anomaly_simulator import anomaly_simulator, SCENARIOS_META
from Backend.services.anomaly_classifier import anomaly_classifier


OUTPUT_DIR = Path("output/article_stats")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SCENARIOS = [s for s in SCENARIOS_META.keys() if s != "CUSTOM"]


@dataclass
class SampleResult:
    scenario: str
    heuristic_pred: str
    ml_pred: str
    genai_pred: str
    ensemble_pred: str
    heuristic_correct: int
    ml_correct: int
    genai_correct: int
    ensemble_correct: int
    heuristic_latency_ms: float
    ml_latency_ms: float
    genai_latency_ms: float
    ensemble_latency_ms: float
    heuristic_confidence: float
    ml_confidence: float
    genai_confidence: float
    ensemble_confidence: float


def ci95(values: list[float]) -> tuple[float, float]:
    if len(values) < 2:
        return (values[0], values[0]) if values else (0.0, 0.0)
    mean = statistics.fmean(values)
    stdev = statistics.stdev(values)
    margin = 1.96 * (stdev / math.sqrt(len(values)))
    return (mean - margin, mean + margin)


def summarize_metric(values: list[float]) -> dict:
    return {
        "mean": round(statistics.fmean(values), 4),
        "std": round(statistics.stdev(values), 4) if len(values) > 1 else 0.0,
        "ci95_low": round(ci95(values)[0], 4),
        "ci95_high": round(ci95(values)[1], 4),
    }


def bootstrap_metric(y_true: list[str], y_pred: list[str], metric_name: str, n_boot: int = 500) -> dict:
    rng = np.random.default_rng(42)
    n = len(y_true)
    scores = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        yt = [y_true[i] for i in idx]
        yp = [y_pred[i] for i in idx]
        if metric_name == "accuracy":
            scores.append(accuracy_score(yt, yp))
        elif metric_name == "f1_macro":
            scores.append(f1_score(yt, yp, average="macro", labels=SCENARIOS, zero_division=0))
        else:
            raise ValueError(metric_name)
    return {
        "mean": round(float(np.mean(scores)), 4),
        "std": round(float(np.std(scores, ddof=1)), 4) if len(scores) > 1 else 0.0,
        "ci95_low": round(float(np.percentile(scores, 2.5)), 4),
        "ci95_high": round(float(np.percentile(scores, 97.5)), 4),
    }


async def evaluate() -> list[SampleResult]:
    random.seed(42)
    np.random.seed(42)

    reps_per_scenario = 20
    rows: list[SampleResult] = []

    print(f"Gerando {reps_per_scenario} amostras por cenário...")
    for sc in SCENARIOS:
        for _ in range(reps_per_scenario):
            sample = anomaly_simulator.generate_sample(scenario=sc)

            t0 = time.perf_counter()
            heur = anomaly_classifier.heuristics_engine.classify(sample)
            t_heur = (time.perf_counter() - t0) * 1000.0

            t0 = time.perf_counter()
            ml = anomaly_classifier.ml_engine.classify(sample)
            t_ml = (time.perf_counter() - t0) * 1000.0

            t0 = time.perf_counter()
            genai = await anomaly_classifier.genai_engine.classify(
                sample,
                heur_scenario=heur.predicted_scenario,
            )
            t_genai = (time.perf_counter() - t0) * 1000.0

            t0 = time.perf_counter()
            ensemble = await anomaly_classifier.classify(sample)
            t_ens = (time.perf_counter() - t0) * 1000.0

            rows.append(
                SampleResult(
                    scenario=sc,
                    heuristic_pred=heur.predicted_scenario,
                    ml_pred=ml.predicted_scenario,
                    genai_pred=genai.predicted_scenario,
                    ensemble_pred=ensemble.final_scenario,
                    heuristic_correct=int(heur.predicted_scenario == sc),
                    ml_correct=int(ml.predicted_scenario == sc),
                    genai_correct=int(genai.predicted_scenario == sc),
                    ensemble_correct=int(ensemble.final_scenario == sc),
                    heuristic_latency_ms=round(t_heur, 3),
                    ml_latency_ms=round(t_ml, 3),
                    genai_latency_ms=round(t_genai, 3),
                    ensemble_latency_ms=round(t_ens, 3),
                    heuristic_confidence=round(float(heur.confidence), 4),
                    ml_confidence=round(float(ml.confidence), 4),
                    genai_confidence=round(float(genai.confidence), 4),
                    ensemble_confidence=round(float(ensemble.overall_confidence), 4),
                )
            )

    return rows


def build_summary(rows: list[SampleResult]) -> dict:
    y_true = [r.scenario for r in rows]
    metrics = {}
    for name in ["heuristic", "ml", "genai", "ensemble"]:
        y_pred = [getattr(r, f"{name}_pred") for r in rows]
        correct = [getattr(r, f"{name}_correct") for r in rows]
        latency = [getattr(r, f"{name}_latency_ms") for r in rows]
        conf = [getattr(r, f"{name}_confidence") for r in rows]

        metrics[name] = {
            "accuracy": bootstrap_metric(y_true, y_pred, "accuracy"),
            "f1_macro": bootstrap_metric(y_true, y_pred, "f1_macro"),
            "latency_ms": summarize_metric(latency),
            "confidence": summarize_metric(conf),
        }

    return metrics


def save_csv(rows: list[SampleResult]) -> Path:
    path = OUTPUT_DIR / "article_benchmark_samples.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))
    return path


def save_summary(summary: dict) -> Path:
    path = OUTPUT_DIR / "article_benchmark_summary.json"
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def save_figure(summary: dict) -> Path:
    labels = ["Heurística", "ML", "GenAI", "Ensemble"]
    keys = ["heuristic", "ml", "genai", "ensemble"]
    metrics = {
        "Acurácia (%)": [summary[k]["accuracy"]["mean"] * 100 for k in keys],
        "F1-macro (%)": [summary[k]["f1_macro"]["mean"] * 100 for k in keys],
        "Latência (ms)": [summary[k]["latency_ms"]["mean"] for k in keys],
    }
    errors = {
        "Acurácia (%)": [(summary[k]["accuracy"]["ci95_high"] - summary[k]["accuracy"]["mean"]) * 100 for k in keys],
        "F1-macro (%)": [(summary[k]["f1_macro"]["ci95_high"] - summary[k]["f1_macro"]["mean"]) * 100 for k in keys],
        "Latência (ms)": [summary[k]["latency_ms"]["ci95_high"] - summary[k]["latency_ms"]["mean"] for k in keys],
    }
    y_max = {
        "Acurácia (%)": 100,
        "F1-macro (%)": 100,
        "Latência (ms)": max(v + e for v, e in zip(metrics["Latência (ms)"], errors["Latência (ms)"])) * 1.18,
    }
    width, height = 1600, 540
    margin = 60
    gap = 36
    panel_w = (width - margin * 2 - gap * 2) / 3
    panel_h = height - 120

    def esc(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f7f7fb"/>',
        '<text x="50%" y="34" text-anchor="middle" font-family="Arial, sans-serif" font-size="24" font-weight="700" fill="#172033">NetSpot: comparação estatística dos classificadores</text>',
    ]

    colors = ["#335C67", "#5F0F40", "#9A031E", "#0B6E4F"]
    for i, (metric_name, values) in enumerate(metrics.items()):
        x0 = margin + i * (panel_w + gap)
        y0 = 80
        svg.append(f'<rect x="{x0}" y="{y0}" width="{panel_w}" height="{panel_h}" rx="14" fill="#ffffff" stroke="#d9dde8"/>')
        svg.append(f'<text x="{x0 + panel_w/2}" y="{y0 + 28}" text-anchor="middle" font-family="Arial, sans-serif" font-size="18" font-weight="700" fill="#1f2937">{esc(metric_name)}</text>')

        chart_x = x0 + 42
        chart_y = y0 + 52
        chart_w = panel_w - 64
        chart_h = panel_h - 94
        svg.append(f'<line x1="{chart_x}" y1="{chart_y + chart_h}" x2="{chart_x + chart_w}" y2="{chart_y + chart_h}" stroke="#94a3b8" stroke-width="1"/>')
        bar_w = chart_w / 5.0
        for j, (label, value) in enumerate(zip(labels, values)):
            err = errors[metric_name][j]
            maxv = y_max[metric_name]
            bar_h = max(2, chart_h * (value / maxv))
            x = chart_x + 20 + j * (bar_w * 0.95)
            y = chart_y + chart_h - bar_h
            svg.append(f'<rect x="{x}" y="{y}" width="{bar_w*0.6}" height="{bar_h}" fill="{colors[j]}" rx="4"/>')
            if metric_name == "Latência (ms)":
                top = chart_y + chart_h - chart_h * ((value + err) / maxv)
                bottom = chart_y + chart_h - chart_h * (max((value - err), 0) / maxv)
                mid = x + bar_w * 0.3
                svg.append(f'<line x1="{mid}" y1="{top}" x2="{mid}" y2="{bottom}" stroke="#111827" stroke-width="2"/>')
                svg.append(f'<line x1="{mid - 8}" y1="{top}" x2="{mid + 8}" y2="{top}" stroke="#111827" stroke-width="2"/>')
                svg.append(f'<line x1="{mid - 8}" y1="{bottom}" x2="{mid + 8}" y2="{bottom}" stroke="#111827" stroke-width="2"/>')
            else:
                top = chart_y + chart_h - chart_h * ((value + err) / maxv)
                bottom = chart_y + chart_h - chart_h * ((max(value - err, 0)) / maxv)
                mid = x + bar_w * 0.3
                svg.append(f'<line x1="{mid}" y1="{top}" x2="{mid}" y2="{bottom}" stroke="#111827" stroke-width="2"/>')
                svg.append(f'<line x1="{mid - 8}" y1="{top}" x2="{mid + 8}" y2="{top}" stroke="#111827" stroke-width="2"/>')
                svg.append(f'<line x1="{mid - 8}" y1="{bottom}" x2="{mid + 8}" y2="{bottom}" stroke="#111827" stroke-width="2"/>')

            svg.append(f'<text x="{x + bar_w*0.3}" y="{chart_y + chart_h + 18}" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#374151">{esc(label)}</text>')
            value_text = f"{value:.1f}" if metric_name == "Latência (ms)" else f"{value:.1f}%"
            svg.append(f'<text x="{x + bar_w*0.3}" y="{y - 6}" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#111827">{value_text}</text>')

    svg.append("</svg>")
    path = OUTPUT_DIR / "article_benchmark_comparison.svg"
    path.write_text("\n".join(svg), encoding="utf-8")
    return path


def main() -> None:
    rows = asyncio.run(evaluate())
    summary = build_summary(rows)
    csv_path = save_csv(rows)
    json_path = save_summary(summary)
    fig_path = save_figure(summary)

    print(f"CSV salvo em: {csv_path}")
    print(f"Resumo salvo em: {json_path}")
    print(f"Figura salva em: {fig_path}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
