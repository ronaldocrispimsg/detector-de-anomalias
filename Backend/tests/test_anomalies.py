"""
Suíte de Testes Automatizados para o Simulador e Classificador de Anomalias de Sistema.
"""

import pytest
import asyncio
from fastapi.testclient import TestClient

try:
    from Backend.main import app
    from Backend.services.anomaly_simulator import anomaly_simulator, SystemMetricsSample, SCENARIOS_META
    from Backend.services.anomaly_classifier import anomaly_classifier
except ImportError:
    from main import app
    from services.anomaly_simulator import anomaly_simulator, SystemMetricsSample, SCENARIOS_META
    from services.anomaly_classifier import anomaly_classifier


client = TestClient(app)


def test_scenarios_meta_coverage():
    """Garante que os 10 cenários solicitados estão catalogados."""
    expected_scenarios = [
        "NORMAL", "DDOS_ATTACK", "PORT_SCAN", "HOST_DOWN",
        "MEMORY_LEAK", "DATA_EXFILTRATION", "DISK_EXHAUSTION",
        "SERVICE_OUTAGE", "COMBINED_FAULT", "NETWORK_CONGESTION"
    ]
    for sc in expected_scenarios:
        assert sc in SCENARIOS_META
        assert "title" in SCENARIOS_META[sc]
        assert "description" in SCENARIOS_META[sc]


def test_anomaly_simulator_generation():
    """Testa se a geração de métricas simuladas produz amostras válidas."""
    for sc in SCENARIOS_META.keys():
        sample = anomaly_simulator.generate_sample(scenario=sc)
        assert isinstance(sample, SystemMetricsSample)
        assert sample.scenario == sc
        assert 0.0 <= sample.cpu_usage_pct <= 100.0
        assert 0.0 <= sample.ram_usage_pct <= 100.0
        assert 0.0 <= sample.disk_usage_pct <= 100.0
        assert 0.0 <= sample.packet_loss_pct <= 100.0


def test_heuristic_classifier_rules():
    """Valida se o motor de heurística detecta corretamente regras chaves."""
    # Teste Host Down
    hd_sample = SystemMetricsSample(
        scenario="HOST_DOWN",
        timestamp=1000.0,
        latency_ms=0.0,
        packet_loss_pct=100.0,
        jitter_ms=0.0,
        cpu_usage_pct=0.0,
        ram_usage_pct=0.0,
        disk_usage_pct=0.0,
        network_in_bps=0.0,
        network_out_bps=0.0,
        http_status_code=0,
        http_response_time_ms=0.0,
        tcp_port_open=False,
        active_connections=0
    )
    heur_res = anomaly_classifier.heuristics_engine.classify(hd_sample)
    assert heur_res.predicted_scenario == "HOST_DOWN"
    assert heur_res.is_anomaly is True
    assert heur_res.severity == "CRITICAL"

    # Teste Disk Full
    disk_sample = SystemMetricsSample(
        scenario="DISK_EXHAUSTION",
        timestamp=1000.0,
        latency_ms=10.0,
        packet_loss_pct=0.0,
        jitter_ms=1.0,
        cpu_usage_pct=40.0,
        ram_usage_pct=50.0,
        disk_usage_pct=98.5,
        network_in_bps=1000.0,
        network_out_bps=1000.0,
        http_status_code=200,
        http_response_time_ms=100.0,
        tcp_port_open=True,
        active_connections=20
    )
    disk_res = anomaly_classifier.heuristics_engine.classify(disk_sample)
    assert disk_res.predicted_scenario == "DISK_EXHAUSTION"
    assert disk_res.is_anomaly is True


def test_ml_classifier_training_and_inference():
    """Valida o treinamento inicial e predição do motor de Machine Learning."""
    sample = anomaly_simulator.generate_sample(scenario="DDOS_ATTACK")
    ml_res = anomaly_classifier.ml_engine.classify(sample)
    
    assert hasattr(ml_res, "predicted_scenario")
    assert hasattr(ml_res, "anomaly_score")
    assert 0.0 <= ml_res.anomaly_score <= 1.0
    assert len(ml_res.feature_importances) > 0


@pytest.mark.asyncio
async def test_genai_local_engine():
    """Valida o motor de IA Generativa Local (com fallback offline)."""
    sample = anomaly_simulator.generate_sample(scenario="MEMORY_LEAK")
    genai_res = await anomaly_classifier.genai_engine.classify(sample, heur_scenario="MEMORY_LEAK")
    
    assert genai_res.predicted_scenario in SCENARIOS_META
    assert genai_res.is_anomaly is True
    assert len(genai_res.diagnostic_summary) > 0
    assert len(genai_res.remediation_playbook) > 0


@pytest.mark.asyncio
async def test_ensemble_consensus():
    """Valida a combinação híbrida dos 3 motores no ensemble."""
    sample = anomaly_simulator.generate_sample(scenario="DATA_EXFILTRATION")
    ens_res = await anomaly_classifier.classify(sample)
    
    assert ens_res.final_scenario in SCENARIOS_META
    assert ens_res.risk_level in ["BAIXO", "MÉDIO", "ALTO", "CRÍTICO"]
    assert ens_res.heuristics is not None
    assert ens_res.ml is not None
    assert ens_res.genai is not None


def test_api_scenarios_endpoint():
    """Testa GET /api/anomalies/scenarios e rota direta /anomalies/scenarios"""
    resp = client.get("/api/anomalies/scenarios")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 11
    assert len(data["scenarios"]) == 11

    # Rota direta sem prefixo /api (atendida via proxy reverso Nginx)
    resp_direct = client.get("/anomalies/scenarios")
    assert resp_direct.status_code == 200
    assert resp_direct.json()["count"] == 11


def test_api_genai_status_endpoint():
    """Testa GET /api/anomalies/genai/status e /anomalies/genai/status"""
    resp = client.get("/api/anomalies/genai/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "ollama_available" in data
    assert "rag_enabled" in data
    assert "status" in data

    resp_direct = client.get("/anomalies/genai/status")
    assert resp_direct.status_code == 200


def test_api_simulate_endpoint():
    """Testa POST /api/anomalies/simulate e rota direta /anomalies/simulate"""
    resp = client.post("/api/anomalies/simulate", json={"scenario": "PORT_SCAN"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["scenario"] == "PORT_SCAN"
    assert "latency_ms" in data

    resp_direct = client.post("/anomalies/simulate", json={"scenario": "PORT_SCAN"})
    assert resp_direct.status_code == 200
    assert resp_direct.json()["scenario"] == "PORT_SCAN"


def test_api_classify_endpoint():
    """Testa POST /api/anomalies/classify"""
    resp = client.post("/api/anomalies/classify", json={"scenario": "NETWORK_CONGESTION", "engine": "ensemble"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["engine"] == "ensemble"
    assert "result" in data
    assert "final_scenario" in data["result"]


def test_api_benchmark_endpoint():
    """Testa POST /api/anomalies/benchmark com volume reduzido para teste unitário"""
    resp = client.post("/api/anomalies/benchmark?samples_per_scenario=2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["scenarios_tested"] == 11
    assert "accuracy" in data
    assert "results_matrix" in data


def test_all_10_scenarios_classification_accuracy():
    """Garante que todos os 10 cenários são classificados com precisão pelos motores."""
    for sc in SCENARIOS_META.keys():
        if sc == "CUSTOM":
            continue
        sample = anomaly_simulator.generate_sample(scenario=sc)
        heur_res = anomaly_classifier.heuristics_engine.classify(sample)
        assert heur_res.predicted_scenario == sc, f"Heurística falhou para {sc}: obteve {heur_res.predicted_scenario}"
