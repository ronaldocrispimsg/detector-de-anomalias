import os
import json
import logging
import random
import pickle
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from Backend.models import Host, CheckResult, SNMPMetric

logger = logging.getLogger("noc_lite.anomaly_classifier")

# Classes de Anomalias suportadas
CLASSES = [
    "NORMAL",
    "DDOS_ATTACK",
    "PORT_SCAN",
    "HOST_DOWN",
    "DATA_EXFILTRATION",
    "NETWORK_CONGESTION"
]

# Caminho para persistir o modelo Decision Tree
MODEL_PATH = os.path.join(os.path.dirname(__file__), "decision_tree_model.pkl")

# Variáveis globais para guardar o modelo treinado em memória
_ML_MODEL = None
_ML_VECTORIZER = None # Se necessário, mas com features numéricas não precisa de vectorizer

def extract_features_from_db(host_id: int, db: Session, window_minutes: int = 5) -> dict:
    """
    Coleta dados e extrai um vetor de features consolidado das métricas recentes do host.
    """
    host = db.query(Host).filter(Host.id == host_id).first()
    if not host:
        return {}

    now = datetime.utcnow()
    since = now - timedelta(minutes=window_minutes)

    # Coleta checks recentes
    checks = db.query(CheckResult).filter(
        CheckResult.host_id == host_id,
        CheckResult.timestamp >= since
    ).all()

    # Coleta SNMP recente
    snmp_metrics = db.query(SNMPMetric).filter(
        SNMPMetric.host_id == host_id,
        SNMPMetric.timestamp >= since
    ).all()

    # Cálculo das features
    ping_checks = [c for c in checks if c.check_type == "ping"]
    ping_success_rate = sum(1 for c in ping_checks if c.success) / len(ping_checks) if ping_checks else 1.0
    ping_latencies = [c.latency for c in ping_checks if c.success and c.latency is not None]
    avg_ping_latency = sum(ping_latencies) / len(ping_latencies) if ping_latencies else 0.0

    tcp_checks = [c for c in checks if c.check_type == "tcp" and c.tcp_port == (host.port or 80)]
    tcp_success_rate = sum(1 for c in tcp_checks if c.success) / len(tcp_checks) if tcp_checks else 1.0

    # Contagem de portas TCP falhas que não sejam a porta principal (varredura de portas)
    failed_scan_checks = [
        c for c in checks 
        if c.check_type == "tcp" and not c.success and c.tcp_port != (host.port or 80)
    ]
    num_failed_tcp_ports = len(set(c.tcp_port for c in failed_scan_checks if c.tcp_port is not None))

    http_checks = [c for c in checks if c.check_type == "http"]
    http_success_rate = sum(1 for c in http_checks if c.success) / len(http_checks) if http_checks else 1.0
    http_latencies = [c.latency for c in http_checks if c.success and c.latency is not None]
    avg_http_latency = sum(http_latencies) / len(http_latencies) if http_latencies else 0.0

    # SNMP
    avg_cpu = sum(s.cpu for s in snmp_metrics) / len(snmp_metrics) if snmp_metrics else 0.0
    avg_ram = sum(s.ram for s in snmp_metrics) / len(snmp_metrics) if snmp_metrics else 0.0
    avg_net_in = sum(s.network_in_bps for s in snmp_metrics if s.network_in_bps is not None) / len(snmp_metrics) if snmp_metrics else 0.0
    avg_net_out = sum(s.network_out_bps for s in snmp_metrics if s.network_out_bps is not None) / len(snmp_metrics) if snmp_metrics else 0.0

    # Ajustes finos se não houver dados históricos mas o host tiver valores atuais
    if not snmp_metrics and host.status != "DOWN":
        avg_cpu = host.cpu_usage or 0.0
        avg_ram = host.ram_usage or 0.0
        avg_net_in = host.network_in_bps or 0.0
        avg_net_out = host.network_out_bps or 0.0
    
    if not ping_latencies and host.status != "DOWN":
        avg_ping_latency = host.latency_ping or 0.0
    if not http_latencies and host.status != "DOWN" and host.http_enabled:
        avg_http_latency = host.http_latency or 0.0

    # Se o host está marcado como DOWN
    if host.status == "DOWN" and not checks and not snmp_metrics:
        ping_success_rate = 0.0
        tcp_success_rate = 0.0
        http_success_rate = 0.0

    return {
        "cpu_usage": avg_cpu,
        "ram_usage": avg_ram,
        "network_in_bps": avg_net_in,
        "network_out_bps": avg_net_out,
        "ping_latency": avg_ping_latency,
        "ping_success_rate": ping_success_rate,
        "tcp_success_rate": tcp_success_rate,
        "http_success_rate": http_success_rate,
        "http_latency": avg_http_latency,
        "num_failed_tcp_ports": num_failed_tcp_ports
    }

def tokenise_metrics(features: dict, host_name: str) -> str:
    """
    Identifica as propriedades de aprendizado e organiza em tokens (texto estruturado)
    para consumo otimizado por modelos de IA Generativa.
    """
    tokens = [
        f"[NETWORK_HOST_SNAPSHOT] Name: {host_name}",
        f"PingSuccessRate: {features.get('ping_success_rate', 1.0):.2f}",
        f"AvgPingLatency: {features.get('ping_latency', 0.0):.1f} ms",
        f"TCPAvailability: {features.get('tcp_success_rate', 1.0):.2f}",
        f"HTTPAvailability: {features.get('http_success_rate', 1.0):.2f}",
        f"AvgHTTPLatency: {features.get('http_latency', 0.0):.1f} ms",
        f"CPUUsage: {features.get('cpu_usage', 0.0):.1f}%",
        f"RAMUsage: {features.get('ram_usage', 0.0):.1f}%",
        f"TrafficInbound: {features.get('network_in_bps', 0.0)/1_000_000.0:.2f} Mbps",
        f"TrafficOutbound: {features.get('network_out_bps', 0.0)/1_000_000.0:.2f} Mbps",
        f"FailedScanPorts: {features.get('num_failed_tcp_ports', 0)}"
    ]
    return " | ".join(tokens)

# ==========================================
# 1. CLASSIFICADOR HEURÍSTICO (Baseline 1)
# ==========================================
def classify_heuristic(features: dict) -> dict:
    """
    Classificação baseada em regras de threshold estáticas.
    """
    # 1. HOST_DOWN: Sem conectividade
    if features.get("ping_success_rate", 1.0) == 0.0 and features.get("tcp_success_rate", 1.0) == 0.0:
        return {
            "classification": "HOST_DOWN",
            "confidence": 1.0,
            "explanation": "Queda completa do host confirmada por 100% de perda de pacotes e indisponibilidade de portas."
        }

    # 2. DDOS_ATTACK: Alta CPU + Altíssimo tráfego de entrada
    if features.get("network_in_bps", 0.0) > 50_000_000.0 and features.get("cpu_usage", 0.0) > 75.0:
        return {
            "classification": "DDOS_ATTACK",
            "confidence": 0.9,
            "explanation": f"Uso de CPU elevado ({features.get('cpu_usage'):.1f}%) acompanhado de tráfego de entrada massivo ({features.get('network_in_bps')/1_000_000.0:.1f} Mbps)."
        }

    # 3. DATA_EXFILTRATION: Tráfego de saída extremo com CPU baixa/média
    if features.get("network_out_bps", 0.0) > 50_000_000.0:
        return {
            "classification": "DATA_EXFILTRATION",
            "confidence": 0.85,
            "explanation": f"Tráfego de upload extremo ({features.get('network_out_bps')/1_000_000.0:.1f} Mbps) inconsistente com o padrão de tráfego normal."
        }

    # 4. PORT_SCAN: Falhas de conexões em portas não oficiais
    if features.get("num_failed_tcp_ports", 0) >= 3:
        return {
            "classification": "PORT_SCAN",
            "confidence": 0.8,
            "explanation": f"Múltiplas conexões TCP recusadas ({features.get('num_failed_tcp_ports')} portas distintas) em curto período de tempo."
        }

    # 5. NETWORK_CONGESTION: Latência/Jitter alto + alguma perda de pacote + tráfego médio
    if features.get("ping_latency", 0.0) > 120.0 or (features.get("ping_success_rate", 1.0) < 0.9 and features.get("ping_success_rate", 1.0) > 0.0):
        return {
            "classification": "NETWORK_CONGESTION",
            "confidence": 0.75,
            "explanation": f"Latência de ping elevada ({features.get('ping_latency'):.1f} ms) ou perda parcial de pacotes ({100 - features.get('ping_success_rate')*100:.1f}%)."
        }

    # 6. NORMAL
    return {
        "classification": "NORMAL",
        "confidence": 0.95,
        "explanation": "Todas as métricas de latência, CPU, memória e tráfego de rede operam dentro dos limites operacionais normais."
    }

# ==========================================
# 2. CLASSIFICADOR MACHINE LEARNING (Baseline 2)
# ==========================================
def load_ml_model():
    """
    Carrega o modelo do arquivo pickle se existir.
    """
    global _ML_MODEL
    if _ML_MODEL is not None:
        return _ML_MODEL

    if os.path.exists(MODEL_PATH):
        try:
            with open(MODEL_PATH, "rb") as f:
                _ML_MODEL = pickle.load(f)
            logger.info("Modelo de Árvore de Decisão carregado com sucesso.")
            return _ML_MODEL
        except Exception:
            logger.exception("Erro ao desserializar modelo de ML.")
    return None

def train_decision_tree_baseline() -> str:
    """
    Gera um dataset de treino sintético de forma dinâmica e treina o classificador
    de Árvore de Decisão tradicional do scikit-learn.
    """
    try:
        from sklearn.tree import DecisionTreeClassifier
        import numpy as np
    except ImportError:
        logger.warning("scikit-learn não está instalado. Treinamento da árvore de decisão ignorado.")
        return "Erro: scikit-learn não instalado."

    from Backend.anomaly_simulator import generate_simulated_metrics

    # Gerar dataset sintético representativo (150 amostras por classe)
    X = []
    y = []

    for label_idx, scenario in enumerate(CLASSES):
        for _ in range(200):
            m = generate_simulated_metrics(scenario)
            
            # Formata vetor de features na mesma ordem que extraímos do banco
            feat_vector = [
                m["cpu"] if m["cpu"] is not None else 0.0,
                m["ram"] if m["ram"] is not None else 0.0,
                m["network_in_bps"] if m["network_in_bps"] is not None else 0.0,
                m["network_out_bps"] if m["network_out_bps"] is not None else 0.0,
                m["ping_latency"] if m["ping_latency"] is not None else 0.0,
                1.0 if m["ping_success"] else 0.0,
                1.0 if m["tcp_success"] else 0.0,
                1.0 if m["http_success"] else 0.0,
                m["http_latency"] if m["http_latency"] is not None else 0.0,
                len(m["extra_tcp_checks"])
            ]
            X.append(feat_vector)
            y.append(label_idx)

    # Treina o modelo
    clf = DecisionTreeClassifier(max_depth=5, random_state=42)
    clf.fit(X, y)

    # Salva o modelo
    global _ML_MODEL
    _ML_MODEL = clf
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(clf, f)

    logger.info("Modelo de Árvore de Decisão treinado e salvo com sucesso.")
    return "Modelo treinado com sucesso!"

def classify_ml(features: dict) -> dict:
    """
    Classifica as métricas usando a Árvore de Decisão treinada.
    """
    clf = load_ml_model()
    if clf is None:
        # Se não houver modelo salvo, tenta treinar se possível
        res = train_decision_tree_baseline()
        clf = load_ml_model()
        if clf is None:
            # Fallback para heurística
            heur = classify_heuristic(features)
            heur["explanation"] = "[ML Fallback] " + heur["explanation"]
            return heur

    # Vetor de features ordenado
    feat_vector = [
        features.get("cpu_usage", 0.0),
        features.get("ram_usage", 0.0),
        features.get("network_in_bps", 0.0),
        features.get("network_out_bps", 0.0),
        features.get("ping_latency", 0.0),
        features.get("ping_success_rate", 1.0),
        features.get("tcp_success_rate", 1.0),
        features.get("http_success_rate", 1.0),
        features.get("http_latency", 0.0),
        features.get("num_failed_tcp_ports", 0)
    ]

    try:
        probs = clf.predict_proba([feat_vector])[0]
        prediction_idx = clf.predict([feat_vector])[0]
        predicted_class = CLASSES[prediction_idx]
        confidence = float(probs[prediction_idx])

        # Explicar baseado na árvore (heurística textual simplificada da árvore)
        explanations = {
            "HOST_DOWN": "Classificado como HOST_DOWN pela árvore devido a falta de sucesso nos pings e conexões de rede.",
            "DDOS_ATTACK": "Classificado como DDOS_ATTACK devido a combinação crítica de tráfego de entrada e alta CPU.",
            "PORT_SCAN": "Classificado como PORT_SCAN devido ao elevado número de portas TCP com conexão recusada.",
            "DATA_EXFILTRATION": "Classificado como DATA_EXFILTRATION devido ao pico desproporcional de tráfego de saída (upload).",
            "NETWORK_CONGESTION": "Classificado como NETWORK_CONGESTION devido a latências instáveis e/ou perdas de pacotes.",
            "NORMAL": "Classificado como NORMAL pelo modelo de ML, todas as métricas estão na faixa saudável de tráfego."
        }

        return {
            "classification": predicted_class,
            "confidence": confidence,
            "explanation": explanations.get(predicted_class, "Classificação do modelo ML tradicional.")
        }
    except Exception as e:
        logger.error(f"Erro na inferência ML: {e}")
        return classify_heuristic(features)

# ==========================================
# 3. PIPELINE IA GENERATIVA (Google Gemini)
# ==========================================
def classify_generative_ai(features: dict, tokenized_text: str) -> dict:
    """
    Classifica as métricas enviando o snapshot tokenizado para o Google Gemini.
    Caso a API Key não exista ou ocorra um erro, aciona o fallback heurístico de segurança.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY não configurada no ambiente. Usando heurística de fallback.")
        heur = classify_heuristic(features)
        heur["explanation"] = "[IA Fallback (API Key Ausente)] " + heur["explanation"]
        return heur

    try:
        import google.generativeai as genai
    except ImportError:
        logger.warning("Biblioteca google-generativeai não instalada. Usando heurística de fallback.")
        heur = classify_heuristic(features)
        heur["explanation"] = "[IA Fallback (Biblioteca Ausente)] " + heur["explanation"]
        return heur

    # Configura o cliente do Gemini
    try:
        genai.configure(api_key=api_key)
        
        # Usamos o modelo rápido e eficaz para tarefas de classificação
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        prompt = f"""
Você é um especialista em redes de computadores e inteligência artificial atuando no NOC Lite.
Sua tarefa é analisar o snapshot de telemetria de rede de um host e classificá-lo em EXATAMENTE um dos seguintes fenômenos anômalos:
- NORMAL: Operação regular.
- DDOS_ATTACK: Ataque DoS/DDoS (Altíssimo tráfego de entrada + CPU elevada).
- PORT_SCAN: Varredura de portas (Múltiplas falhas em portas TCP ativas).
- HOST_DOWN: Queda total do host (100% de perda de pacotes e indisponibilidade).
- DATA_EXFILTRATION: Exfiltração de dados (Tráfego de upload/saída muito alto, CPU normal).
- NETWORK_CONGESTION: Congestionamento (Latência/jitter alto e perda de pacote parcial).

Você DEVE responder EXATAMENTE no formato JSON válido abaixo, sem qualquer outro texto adicional antes ou depois do JSON:
{{
  "classification": "NOME_DO_FENOMENO",
  "confidence": 0.99,
  "explanation": "Uma explicação concisa em português justificando sua decisão com base nos dados fornecidos."
}}

Aqui está o snapshot de telemetria tokenizado do host:
{tokenized_text}
"""
        response = model.generate_content(prompt)
        
        # Limpeza básica do JSON de saída do modelo
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        data = json.loads(text)
        
        # Garante que a classificação está na lista permitida
        if data.get("classification") in CLASSES:
            return {
                "classification": data["classification"],
                "confidence": float(data.get("confidence", 0.8)),
                "explanation": data.get("explanation", "Classificado pelo Gemini 1.5 Flash.")
            }
        else:
            logger.warning(f"Gemini retornou classe inválida: {data.get('classification')}. Usando heurística.")
            return classify_heuristic(features)

    except Exception as e:
        logger.error(f"Erro na execução da IA Generativa (Gemini): {e}")
        heur = classify_heuristic(features)
        heur["explanation"] = f"[IA Fallback (Erro API: {str(e)})] " + heur["explanation"]
        return heur
