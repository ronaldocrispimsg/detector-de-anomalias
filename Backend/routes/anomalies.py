"""
Rotas RESTful para Simulação e Classificação de Anomalias de Sistema no NetSpot.
"""

import time
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

try:
    from Backend.services.anomaly_simulator import anomaly_simulator, SystemMetricsSample, SCENARIOS_META
    from Backend.services.anomaly_classifier import (
        anomaly_classifier, EnsembleResult, HeuristicResult, MLResult, GenAIResult
    )
except ImportError:
    from services.anomaly_simulator import anomaly_simulator, SystemMetricsSample, SCENARIOS_META
    from services.anomaly_classifier import (
        anomaly_classifier, EnsembleResult, HeuristicResult, MLResult, GenAIResult
    )

router = APIRouter(prefix="/anomalies", tags=["Simulador e Classificador de Anomalias"])


class SimulationRequest(BaseModel):
    scenario: str = Field(default="NORMAL", description="Nome do cenário de simulação")
    custom_params: Optional[Dict[str, Any]] = Field(default=None, description="Sobrescrita de métricas")


class ClassificationRequest(BaseModel):
    sample: Optional[SystemMetricsSample] = None
    scenario: Optional[str] = "NORMAL"
    custom_params: Optional[Dict[str, Any]] = None
    engine: str = Field(default="ensemble", description="Motor de classificação: 'heuristics', 'ml', 'genai', ou 'ensemble'")


class BenchmarkResponse(BaseModel):
    scenarios_tested: int
    total_samples: int
    execution_time_ms: float
    accuracy: Dict[str, float]
    results_matrix: List[Dict[str, Any]]


@router.get("/scenarios", summary="Lista os cenários de anomalia disponíveis")
def get_scenarios():
    return {
        "count": len(SCENARIOS_META),
        "scenarios": [
            {
                "key": key,
                "title": meta["title"],
                "description": meta["description"],
                "category": meta["category"]
            }
            for key, meta in SCENARIOS_META.items()
        ]
    }


@router.post("/simulate", response_model=SystemMetricsSample, summary="Gera amostra simulada de métricas")
def simulate_metrics(req: SimulationRequest):
    return anomaly_simulator.generate_sample(
        scenario=req.scenario,
        custom_params=req.custom_params
    )


@router.post("/classify", summary="Classifica anomalia via Heurística, ML, GenAI ou Ensemble")
async def classify_anomaly(req: ClassificationRequest):
    # Se a amostra não for enviada no corpo, gera com base no cenário/parâmetros
    if req.sample is None:
        sample = anomaly_simulator.generate_sample(
            scenario=req.scenario or "NORMAL",
            custom_params=req.custom_params
        )
    else:
        sample = req.sample

    engine = req.engine.lower()

    if engine == "heuristics":
        res = anomaly_classifier.heuristics_engine.classify(sample)
        return {"engine": "heuristics", "sample": sample, "result": res}
    elif engine == "ml":
        res = anomaly_classifier.ml_engine.classify(sample)
        return {"engine": "ml", "sample": sample, "result": res}
    elif engine == "genai":
        heur_sc = anomaly_classifier.heuristics_engine.classify(sample).predicted_scenario
        res = await anomaly_classifier.genai_engine.classify(sample, heur_scenario=heur_sc)
        return {"engine": "genai", "sample": sample, "result": res}
    else:
        res = await anomaly_classifier.classify(sample)
        return {"engine": "ensemble", "sample": sample, "result": res}


@router.post("/train", summary="Re-treina o modelo de Machine Learning")
def train_ml_model(samples_per_scenario: int = Query(50, ge=10, le=500)):
    res = anomaly_classifier.ml_engine.train_custom(samples_per_scenario=samples_per_scenario)
    return res


@router.get("/genai/status", summary="Verifica disponibilidade da IA Generativa Local (Ollama) e RAG ChromaDB")
async def get_genai_status():
    ollama_active = await anomaly_classifier.genai_engine.check_ollama_available()
    rag_ready = anomaly_classifier.genai_engine.rag_retriever.is_ready
    return {
        "ollama_available": ollama_active,
        "ollama_url": anomaly_classifier.genai_engine.ollama_url,
        "rag_enabled": rag_ready,
        "rag_engine": "ChromaDB Vector Store" if rag_ready else "Offline",
        "active_provider": "Ollama + RAG (Local LLM)" if ollama_active else "Engine Local GenAI com RAG (ChromaDB)",
        "status": "online" if ollama_active else "rag_fallback_ready"
    }



@router.post("/benchmark", response_model=BenchmarkResponse, summary="Executa teste comparativo de acurácia entre os motores")
async def run_benchmark(samples_per_scenario: int = Query(10, ge=2, le=50)):
    start_time = time.time()
    scenarios = list(SCENARIOS_META.keys())
    results_matrix = []

    heur_correct = 0
    ml_correct = 0
    genai_correct = 0
    ensemble_correct = 0
    total_samples = len(scenarios) * samples_per_scenario

    for sc in scenarios:
        samples = anomaly_simulator.generate_batch(scenario=sc, count=samples_per_scenario)
        for s in samples:
            heur_res = anomaly_classifier.heuristics_engine.classify(s)
            ml_res = anomaly_classifier.ml_engine.classify(s)
            genai_res = await anomaly_classifier.genai_engine.classify(s, heur_scenario=heur_res.predicted_scenario)
            ens_res = await anomaly_classifier.classify(s)

            if heur_res.predicted_scenario == sc:
                heur_correct += 1
            if ml_res.predicted_scenario == sc:
                ml_correct += 1
            if genai_res.predicted_scenario == sc:
                genai_correct += 1
            if ens_res.final_scenario == sc:
                ensemble_correct += 1

            results_matrix.append({
                "expected": sc,
                "heuristics": heur_res.predicted_scenario,
                "ml": ml_res.predicted_scenario,
                "genai": genai_res.predicted_scenario,
                "ensemble": ens_res.final_scenario,
                "is_match": ens_res.final_scenario == sc
            })

    exec_time = round((time.time() - start_time) * 1000, 2)

    return BenchmarkResponse(
        scenarios_tested=len(scenarios),
        total_samples=total_samples,
        execution_time_ms=exec_time,
        accuracy={
            "heuristics": round(heur_correct / total_samples, 4),
            "ml": round(ml_correct / total_samples, 4),
            "genai": round(genai_correct / total_samples, 4),
            "ensemble": round(ensemble_correct / total_samples, 4)
        },
        results_matrix=results_matrix[:30]  # Limita resposta do matrix aos primeiros 30 para brevidade
    )
