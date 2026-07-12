import time
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from Backend.database import get_db
from Backend.models import Host
from Backend.dependencies import get_current_user
from Backend.anomaly_simulator import (
    start_simulation,
    stop_simulation,
    get_active_simulation,
    generate_historical_data
)
from Backend.anomaly_classifier import (
    extract_features_from_db,
    tokenise_metrics,
    classify_heuristic,
    classify_ml,
    classify_generative_ai,
    train_decision_tree_baseline,
    CLASSES
)

router = APIRouter(prefix="/api/anomalies", tags=["Anomalias"])
logger = logging.getLogger("noc_lite.routes.anomalies")

@router.post("/simulator/start")
def api_start_simulation(
    host_id: int,
    anomaly_type: str,
    duration_seconds: int = 300,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    """
    Inicia uma simulação de anomalia em tempo real para um host específico.
    """
    host = db.query(Host).filter(Host.id == host_id).first()
    if not host:
        raise HTTPException(status_code=404, detail="Host não encontrado.")

    if anomaly_type not in CLASSES:
        raise HTTPException(
            status_code=400, 
            detail=f"Tipo de anomalia inválido. Escolha entre: {CLASSES}"
        )

    sim = start_simulation(host_id, anomaly_type, duration_seconds)
    return {
        "status": "success",
        "message": f"Simulação de '{anomaly_type}' iniciada para o host {host.name}.",
        "expires_at": sim["expires_at"].isoformat()
    }

@router.post("/simulator/stop")
def api_stop_simulation(
    host_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    """
    Para uma simulação de anomalia ativa.
    """
    host = db.query(Host).filter(Host.id == host_id).first()
    if not host:
        raise HTTPException(status_code=404, detail="Host não encontrado.")

    stopped = stop_simulation(host_id)
    if not stopped:
        return {"status": "info", "message": "Nenhuma simulação ativa para parar."}
        
    return {"status": "success", "message": f"Simulação de anomalias para {host.name} parada."}

@router.get("/simulator/status")
def api_simulator_status(
    host_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    """
    Verifica se existe simulação ativa para o host.
    """
    sim = get_active_simulation(host_id)
    if not sim:
        return {"active": False, "anomaly_type": None}
    
    return {
        "active": True,
        "anomaly_type": sim["anomaly_type"],
        "expires_at": sim["expires_at"].isoformat(),
        "started_at": sim["started_at"].isoformat()
    }

@router.post("/simulator/generate-history")
def api_generate_history(
    host_id: int,
    anomaly_type: str,
    records: int = 150,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    """
    Gera um histórico retroativo de métricas anômalas no banco.
    """
    host = db.query(Host).filter(Host.id == host_id).first()
    if not host:
        raise HTTPException(status_code=404, detail="Host não encontrado.")

    if anomaly_type not in CLASSES:
        raise HTTPException(
            status_code=400, 
            detail=f"Tipo de anomalia inválido. Escolha entre: {CLASSES}"
        )

    # Executa a geração em background/thread para não travar a chamada HTTP
    import threading
    threading.Thread(
        target=generate_historical_data, 
        args=(host_id, anomaly_type, records)
    ).start()

    return {
        "status": "success", 
        "message": f"Geração de histórico de '{anomaly_type}' para o host {host.name} iniciada em background."
    }

@router.get("/classify")
def api_classify_host(
    host_id: int,
    window_minutes: int = 5,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    """
    Executa a classificação nos 3 modelos (IA, Heurística e ML) e retorna a comparação
    com os tempos de resposta de cada classificador.
    """
    host = db.query(Host).filter(Host.id == host_id).first()
    if not host:
        raise HTTPException(status_code=404, detail="Host não encontrado.")

    features = extract_features_from_db(host_id, db, window_minutes)
    if not features:
        raise HTTPException(status_code=400, detail="Sem métricas suficientes no host para analisar.")

    tokenized_text = tokenise_metrics(features, host.name)

    # 1. Classificação Heurística
    t0 = time.perf_counter()
    heur_result = classify_heuristic(features)
    t_heur = (time.perf_counter() - t0) * 1000.0 # ms

    # 2. Classificação Machine Learning (Decision Tree)
    t0 = time.perf_counter()
    ml_result = classify_ml(features)
    t_ml = (time.perf_counter() - t0) * 1000.0 # ms

    # 3. Classificação IA Generativa (Gemini)
    t0 = time.perf_counter()
    ai_result = classify_generative_ai(features, tokenized_text)
    t_ai = (time.perf_counter() - t0) * 1000.0 # ms

    return {
        "host": {
            "id": host.id,
            "name": host.name,
            "status": host.status
        },
        "features": features,
        "tokenized_text": tokenized_text,
        "classifications": {
            "generative_ai": {
                "result": ai_result["classification"],
                "confidence": ai_result["confidence"],
                "explanation": ai_result["explanation"],
                "latency_ms": round(t_ai, 2)
            },
            "heuristic": {
                "result": heur_result["classification"],
                "confidence": heur_result["confidence"],
                "explanation": heur_result["explanation"],
                "latency_ms": round(t_heur, 2)
            },
            "machine_learning": {
                "result": ml_result["classification"],
                "confidence": ml_result["confidence"],
                "explanation": ml_result["explanation"],
                "latency_ms": round(t_ml, 2)
            }
        }
    }

@router.post("/train")
def api_train_model(
    user: str = Depends(get_current_user)
):
    """
    Treina o modelo de árvore de decisão baseline usando dados de treino sintéticos.
    """
    result = train_decision_tree_baseline()
    if "Erro" in result:
        raise HTTPException(status_code=500, detail=result)
    
    return {"status": "success", "message": result}
