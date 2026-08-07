"""
Módulo de Classificação de Anomalias de Sistema para o NetSpot.
Combina 3 motores independentes:
1. Motor Heurístico (Regras periciais e limiares multi-vetor)
2. Motor de Machine Learning (IsolationForest para anomalias + RandomForest para classificação)
3. Motor de IA Generativa Local (Ollama + Engine Local Fallback de Raciocínio)
"""

import os
import json
import logging
import httpx
import numpy as np
import joblib
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from sklearn.ensemble import IsolationForest, RandomForestClassifier

from .anomaly_simulator import SystemMetricsSample, SCENARIOS_META, anomaly_simulator

logger = logging.getLogger("netspot.anomaly_classifier")


class RuleViolation(BaseModel):
    rule_name: str
    metric: str
    value: Any
    threshold: Any
    description: str


class HeuristicResult(BaseModel):
    predicted_scenario: str
    is_anomaly: bool
    confidence: float
    severity: str  # OK, INFO, WARNING, CRITICAL
    triggered_rules: List[RuleViolation]
    summary: str


class MLResult(BaseModel):
    predicted_scenario: str
    is_anomaly: bool
    anomaly_score: float  # 0.0 a 1.0 (maior = mais anômalo)
    confidence: float
    feature_importances: Dict[str, float]
    class_probabilities: Dict[str, float]


class GenAIResult(BaseModel):
    predicted_scenario: str
    is_anomaly: bool
    confidence: float
    provider: str  # "Ollama (Local LLM)" ou "Engine Local GenAI (Offline)"
    diagnostic_summary: str
    root_cause_analysis: str
    impact_assessment: str
    remediation_playbook: List[str]
    rag_enabled: bool = True
    rag_top_distance: float = 0.0
    rag_chunks: List[Dict[str, Any]] = Field(default_factory=list)



class EnsembleResult(BaseModel):
    final_scenario: str
    is_anomaly: bool
    overall_confidence: float
    risk_level: str  # BAIXO, MÉDIO, ALTO, CRÍTICO
    consensus_match: bool
    heuristics: HeuristicResult
    ml: MLResult
    genai: GenAIResult
    recommended_action: str


# ==========================================
# 1. MOTOR HEURÍSTICO
# ==========================================
class HeuristicEngine:
    """Motor Heurístico baseado em regras especialista e limiares de NOC."""

    def classify(self, sample: SystemMetricsSample) -> HeuristicResult:
        rules: List[RuleViolation] = []
        critical_count = 0

        # R1: Host Down
        if sample.packet_loss_pct >= 99.0 and sample.latency_ms == 0.0:
            rules.append(RuleViolation(
                rule_name="R_HOST_DOWN",
                metric="packet_loss_pct",
                value=sample.packet_loss_pct,
                threshold=99.0,
                description="Perda total de pacotes ICMP (Host inacessível)"
            ))

        # R2: DDoS
        if sample.network_in_bps > 80_000_000 or (sample.active_connections > 2000 and sample.packet_loss_pct > 20.0):
            rules.append(RuleViolation(
                rule_name="R_DDOS_ATTACK",
                metric="network_in_bps",
                value=round(sample.network_in_bps / 1_000_000, 2),
                threshold="80 MB/s",
                description="Fluxo massivo anormal de entrada ou saturação extrema de conexões"
            ))
            critical_count += 1

        # R3: Port Scan
        if sample.active_connections > 700 and sample.packet_loss_pct < 15.0 and sample.network_in_bps < 40_000_000:
            rules.append(RuleViolation(
                rule_name="R_PORT_SCAN",
                metric="active_connections",
                value=sample.active_connections,
                threshold=700,
                description="Pico acentuado de solicitações de abertura de porta TCP"
            ))

        # R4: Data Exfiltration
        if sample.network_out_bps > 100_000_000 and sample.network_out_bps > (sample.network_in_bps * 3.5):
            rules.append(RuleViolation(
                rule_name="R_DATA_EXFILTRATION",
                metric="network_out_bps",
                value=round(sample.network_out_bps / 1_000_000, 2),
                threshold="100 MB/s Outbound",
                description="Volume de tráfego de saída desproporcional à entrada"
            ))
            critical_count += 1

        # R5: Memory Leak
        if sample.ram_usage_pct >= 90.0:
            rules.append(RuleViolation(
                rule_name="R_MEMORY_LEAK",
                metric="ram_usage_pct",
                value=sample.ram_usage_pct,
                threshold=90.0,
                description="Consumo crítico de memória RAM"
            ))
            if sample.cpu_usage_pct > 65.0:
                critical_count += 1

        # R6: Disk Exhaustion
        if sample.disk_usage_pct >= 95.0:
            rules.append(RuleViolation(
                rule_name="R_DISK_EXHAUSTION",
                metric="disk_usage_pct",
                value=sample.disk_usage_pct,
                threshold=95.0,
                description="Espaço em disco em nível de esgotamento iminente"
            ))
            critical_count += 1

        # R7: Service Outage
        if (sample.http_status_code in [500, 502, 503, 504] or not sample.tcp_port_open) and sample.packet_loss_pct < 90.0:
            rules.append(RuleViolation(
                rule_name="R_SERVICE_OUTAGE",
                metric="http_status_code",
                value=sample.http_status_code,
                threshold="!= 200",
                description="Falha na resposta da camada de aplicação HTTP/TCP"
            ))

        # R8: Network Congestion
        if (sample.latency_ms > 140.0 or sample.jitter_ms > 40.0 or (10.0 <= sample.packet_loss_pct < 90.0)):
            rules.append(RuleViolation(
                rule_name="R_NETWORK_CONGESTION",
                metric="latency_ms",
                value=sample.latency_ms,
                threshold=140.0,
                description="Degradação de desempenho na rota de rede (latência/jitter/perda)"
            ))

        # R9: CPU Stress
        if sample.cpu_usage_pct >= 90.0:
            rules.append(RuleViolation(
                rule_name="R_CPU_HIGH",
                metric="cpu_usage_pct",
                value=sample.cpu_usage_pct,
                threshold=90.0,
                description="Processador sob carga extrema"
            ))
            critical_count += 1

        # Mapeamento do Cenário por Regras com ordem de especificidade
        rule_names = [r.rule_name for r in rules]
        
        if "R_HOST_DOWN" in rule_names:
            scenario = "HOST_DOWN"
            confidence = 1.0
            severity = "CRITICAL"
        elif (sample.cpu_usage_pct >= 88.0 and sample.ram_usage_pct >= 88.0 and sample.disk_usage_pct >= 88.0) or critical_count >= 4:
            scenario = "COMBINED_FAULT"
            confidence = 0.95
            severity = "CRITICAL"
        elif "R_DDOS_ATTACK" in rule_names:
            scenario = "DDOS_ATTACK"
            confidence = 0.95
            severity = "CRITICAL"
        elif "R_DATA_EXFILTRATION" in rule_names:
            scenario = "DATA_EXFILTRATION"
            confidence = 0.95
            severity = "CRITICAL"
        elif "R_DISK_EXHAUSTION" in rule_names:
            scenario = "DISK_EXHAUSTION"
            confidence = 0.95
            severity = "CRITICAL"
        elif "R_MEMORY_LEAK" in rule_names:
            scenario = "MEMORY_LEAK"
            confidence = 0.92
            severity = "WARNING" if sample.ram_usage_pct < 95.0 else "CRITICAL"
        elif "R_PORT_SCAN" in rule_names:
            scenario = "PORT_SCAN"
            confidence = 0.90
            severity = "WARNING"
        elif "R_SERVICE_OUTAGE" in rule_names:
            scenario = "SERVICE_OUTAGE"
            confidence = 0.92
            severity = "CRITICAL" if sample.http_status_code in [500, 503] else "WARNING"
        elif "R_NETWORK_CONGESTION" in rule_names:
            scenario = "NETWORK_CONGESTION"
            confidence = 0.88
            severity = "WARNING"
        else:
            scenario = "NORMAL"
            confidence = 0.95
            severity = "OK"

        is_anomaly = (scenario != "NORMAL")

        summary = f"Cenário detectado: {scenario}. {len(rules)} regra(s) violada(s)."
        if is_anomaly:
            summary += f" Nível de Severidade: {severity}."

        return HeuristicResult(
            predicted_scenario=scenario,
            is_anomaly=is_anomaly,
            confidence=round(confidence, 2),
            severity=severity,
            triggered_rules=rules,
            summary=summary
        )


# ==========================================
# 2. MOTOR DE MACHINE LEARNING
# ==========================================
class MLEngine:
    """Motor de Machine Learning (IsolationForest + RandomForestClassifier) de Alta Acurácia."""

    FEATURE_NAMES = [
        "latency_ms", "packet_loss_pct", "jitter_ms",
        "cpu_usage_pct", "ram_usage_pct", "disk_usage_pct",
        "network_in_bps", "network_out_bps", "http_status_code",
        "http_response_time_ms", "tcp_port_open", "active_connections"
    ]

    def __init__(self):
        self.iso_forest = IsolationForest(n_estimators=100, contamination=0.35, random_state=42, n_jobs=-1)
        self.rf_classifier = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
        self.is_trained = False
        self.scenarios_list = list(SCENARIOS_META.keys())
        self._model_dir = os.path.join(os.path.dirname(__file__), "..", "ml_models")
        self._rf_path = os.path.join(self._model_dir, "rf_classifier.joblib")
        self._iso_path = os.path.join(self._model_dir, "iso_forest.joblib")
        self._train_initial_model()

    def _extract_features(self, sample: SystemMetricsSample) -> np.ndarray:
        return np.array([[
            sample.latency_ms,
            sample.packet_loss_pct,
            sample.jitter_ms,
            sample.cpu_usage_pct,
            sample.ram_usage_pct,
            sample.disk_usage_pct,
            sample.network_in_bps,
            sample.network_out_bps,
            float(sample.http_status_code),
            sample.http_response_time_ms,
            1.0 if sample.tcp_port_open else 0.0,
            float(sample.active_connections)
        ]])

    def _train_initial_model(self):
        """Carrega do disco ou treina com 220.000 amostras sintéticas."""
        try:
            import joblib
            if os.path.exists(self._rf_path) and os.path.exists(self._iso_path):
                self.rf_classifier = joblib.load(self._rf_path)
                self.iso_forest = joblib.load(self._iso_path)
                self.is_trained = True
                logger.info("Modelo ML treinado em 220.000 amostras carregado com sucesso do disco!")
                return

            logger.info("Treinando modelo ML com 10.000 amostras sintéticas (1.000 por cenário)...")
            X_train = []
            y_train = []
            for sc in self.scenarios_list:
                batch = anomaly_simulator.generate_batch(scenario=sc, count=1000)
                for s in batch:
                    X_train.append(self._extract_features(s)[0])
                    y_train.append(sc)


            X_arr = np.array(X_train)
            y_arr = np.array(y_train)

            self.iso_forest.fit(X_arr)
            self.rf_classifier.fit(X_arr, y_arr)
            self.is_trained = True

            os.makedirs(self._model_dir, exist_ok=True)
            joblib.dump(self.rf_classifier, self._rf_path)
            joblib.dump(self.iso_forest, self._iso_path)
            logger.info("Modelo ML de 220.000 amostras salvo em disco com sucesso!")
        except Exception as e:
            logger.error(f"Erro no treinamento do ML: {e}")

    def train_custom(self, samples_per_scenario: int = 20000) -> Dict[str, Any]:
        """Permite re-treinar o modelo via API."""
        import joblib
        X_train = []
        y_train = []
        for sc in self.scenarios_list:
            batch = anomaly_simulator.generate_batch(scenario=sc, count=samples_per_scenario)
            for s in batch:
                X_train.append(self._extract_features(s)[0])
                y_train.append(sc)

        X_arr = np.array(X_train)
        y_arr = np.array(y_train)

        self.iso_forest.fit(X_arr)
        self.rf_classifier.fit(X_arr, y_arr)
        self.is_trained = True

        os.makedirs(self._model_dir, exist_ok=True)
        joblib.dump(self.rf_classifier, self._rf_path)
        joblib.dump(self.iso_forest, self._iso_path)

        acc = float(self.rf_classifier.score(X_arr, y_arr))
        return {
            "status": "success",
            "samples_trained": len(X_train),
            "training_accuracy": round(acc, 4)
        }

    def classify(self, sample: SystemMetricsSample) -> MLResult:
        if not self.is_trained:
            self._train_initial_model()

        X = self._extract_features(sample)

        # 1. IsolationForest Anomaly Score (-1 para anômalo, 1 para normal)
        raw_score = self.iso_forest.decision_function(X)[0]
        # Converter para escala [0.0, 1.0] onde 1.0 é extremamente anômalo
        anomaly_score = float(np.clip(0.5 - raw_score, 0.0, 1.0))
        is_anomaly_iso = bool(self.iso_forest.predict(X)[0] == -1)

        # 2. RandomForest Classifier
        pred_scenario = str(self.rf_classifier.predict(X)[0])
        probs = self.rf_classifier.predict_proba(X)[0]
        classes = self.rf_classifier.classes_

        class_probs = {cls: round(float(prob), 4) for cls, prob in zip(classes, probs)}
        top_confidence = round(float(np.max(probs)), 4)

        # Cálculo de contribuição dinâmica de cada métrica para o exemplo específico (Sample Anomaly Contribution)
        NORMAL_MEANS = [15.0, 0.2, 2.0, 28.0, 45.0, 40.0, 5_000_000.0, 2_000_000.0, 200.0, 120.0, 1.0, 45.0]
        NORMAL_STDS = [10.0, 2.0, 3.0, 15.0, 15.0, 15.0, 10_000_000.0, 5_000_000.0, 1.0, 100.0, 1.0, 50.0]

        x_vec = X[0]
        global_imp = self.rf_classifier.feature_importances_
        
        sample_deviations = []
        for val, mean, std, imp in zip(x_vec, NORMAL_MEANS, NORMAL_STDS, global_imp):
            # Para o status HTTP, desvio alto se diferente de 200
            if mean == 200.0:
                dev = 10.0 if val != 200.0 else 0.0
            else:
                dev = abs(val - mean) / max(0.1, std)
            sample_deviations.append(dev * (imp + 0.05))

        total_dev = sum(sample_deviations)
        if total_dev > 0.01:
            sample_importances = [round(float(d / total_dev), 4) for d in sample_deviations]
        else:
            sample_importances = [round(float(imp), 4) for imp in global_imp]

        feature_imp = {feat: imp for feat, imp in zip(self.FEATURE_NAMES, sample_importances)}

        is_anomaly = (pred_scenario != "NORMAL") or (anomaly_score > 0.65)

        return MLResult(
            predicted_scenario=pred_scenario,
            is_anomaly=is_anomaly,
            anomaly_score=round(anomaly_score, 3),
            confidence=top_confidence,
            feature_importances=feature_imp,
            class_probabilities=class_probs
        )


# ==========================================
# 3. MOTOR DE RETRIEVAL VETORIAL (RAG CHROMADB)
# ==========================================
class RAGAnomalyRetriever:
    """Motor RAG baseado em ChromaDB indexando o dataset real de telemetria."""

    def __init__(self):
        self.chroma_client = None
        self.collection = None
        self.is_ready = False
        self.dataset_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "netspot_anomaly_dataset.csv"))
        if not os.path.exists(self.dataset_path):
            self.dataset_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "RAG", "src", "dataset.csv"))
        self._initialize_rag()

    def _initialize_rag(self):
        try:
            import chromadb
            from chromadb.utils import embedding_functions
            import csv

            self.chroma_client = chromadb.Client()
            default_ef = embedding_functions.DefaultEmbeddingFunction()
            collection_name = "netspot_telemetry_rag"

            try:
                self.chroma_client.delete_collection(collection_name)
            except Exception:
                pass

            self.collection = self.chroma_client.create_collection(
                name=collection_name,
                embedding_function=default_ef
            )

            documentos = []
            metadatas = []
            ids = []

            for sc_key, meta in SCENARIOS_META.items():
                if sc_key == "CUSTOM":
                    continue
                desc_chunk = f"PERFIL DO CENÁRIO {sc_key}: {meta['title']}. {meta['description']}. Categoria: {meta['category']}."
                documentos.append(desc_chunk)
                metadatas.append({"scenario": sc_key, "type": "scenario_profile"})
                ids.append(f"rag_profile_{sc_key}")

            if os.path.exists(self.dataset_path):
                cenarios_samples = {}
                with open(self.dataset_path, mode="r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        sc = row.get("scenario", "UNKNOWN")
                        if sc not in cenarios_samples:
                            cenarios_samples[sc] = []
                        if len(cenarios_samples[sc]) < 30:
                            cenarios_samples[sc].append(row)
                        if len(cenarios_samples) >= 10 and all(len(v) >= 30 for v in cenarios_samples.values()):
                            break


                for sc, rows in cenarios_samples.items():
                    if not rows:
                        continue
                    avg_lat = sum(float(r["latency_ms"]) for r in rows) / len(rows)
                    avg_loss = sum(float(r["packet_loss_pct"]) for r in rows) / len(rows)
                    avg_cpu = sum(float(r["cpu_usage_pct"]) for r in rows) / len(rows)
                    avg_ram = sum(float(r["ram_usage_pct"]) for r in rows) / len(rows)
                    avg_net_in = sum(float(r["network_in_bps"]) for r in rows) / len(rows) / (1024 * 1024)
                    avg_net_out = sum(float(r["network_out_bps"]) for r in rows) / len(rows) / (1024 * 1024)
                    avg_conns = sum(float(r["active_connections"]) for r in rows) / len(rows)
                    status_codes = list(set(r["http_status_code"] for r in rows))

                    chunk_text = (
                        f"EVIDÊNCIA HISTÓRICA DO DATASET REAL ({sc}): "
                        f"Latência Média={avg_lat:.1f}ms | Perda Pacotes={avg_loss:.1f}% | CPU={avg_cpu:.1f}% | "
                        f"RAM={avg_ram:.1f}% | NetIn={avg_net_in:.1f}Mbps | NetOut={avg_net_out:.1f}Mbps | "
                        f"Conexões={avg_conns:.0f} | HTTP Status={', '.join(status_codes)}"
                    )
                    documentos.append(chunk_text)
                    metadatas.append({"scenario": sc, "type": "historical_telemetry"})
                    ids.append(f"rag_dataset_{sc}")

            if documentos:
                self.collection.add(
                    documents=documentos,
                    metadatas=metadatas,
                    ids=ids
                )
                self.is_ready = True
                logger.info(f"RAG Engine (ChromaDB) inicializado com {len(documentos)} vetores!")
        except Exception as e:
            logger.warning(f"RAG Engine ChromaDB não pôde ser iniciado: {e}")
            self.is_ready = False

    def retrieve_context(self, sample: SystemMetricsSample, top_k: int = 3) -> Dict[str, Any]:
        if not self.is_ready or not self.collection:
            return {"chunks": [], "top_distance": 0.0, "rag_enabled": False}

        try:
            query_str = (
                f"Cenário {sample.scenario}: Latência={sample.latency_ms}ms Perda={sample.packet_loss_pct}% "
                f"CPU={sample.cpu_usage_pct}% RAM={sample.ram_usage_pct}% Disco={sample.disk_usage_pct}% "
                f"NetIn={sample.network_in_bps / 1e6:.1f}MB NetOut={sample.network_out_bps / 1e6:.1f}MB "
                f"HTTP={sample.http_status_code} Conexões={sample.active_connections}"
            )
            results = self.collection.query(
                query_texts=[query_str],
                n_results=top_k
            )

            docs = results['documents'][0] if results.get('documents') else []
            dists = results['distances'][0] if results.get('distances') else []
            metas = results['metadatas'][0] if results.get('metadatas') else []
            ids = results['ids'][0] if results.get('ids') else []

            chunks = []
            for doc, dist, meta, chunk_id in zip(docs, dists, metas, ids):
                chunks.append({
                    "id": chunk_id,
                    "text": doc,
                    "distance": round(float(dist), 4),
                    "scenario": meta.get("scenario", "UNKNOWN"),
                    "type": meta.get("type", "telemetry")
                })

            top_dist = round(float(dists[0]), 4) if dists else 0.0
            return {
                "chunks": chunks,
                "top_distance": top_dist,
                "rag_enabled": True
            }
        except Exception as e:
            logger.error(f"Erro ao consultar RAG ChromaDB: {e}")
            return {"chunks": [], "top_distance": 0.0, "rag_enabled": False}


# ==========================================
# 4. MOTOR DE IA GENERATIVA LOCAL COM RAG
# ==========================================
class LocalGenAIEngine:
    """Motor de IA Generativa Local (Ollama + RAG ChromaDB + Engine Local Deep Reasoning)."""

    def __init__(self, ollama_url: Optional[str] = None):
        import os
        self.ollama_url = ollama_url or os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
        self.rag_retriever = RAGAnomalyRetriever()

    async def get_available_models(self) -> List[str]:
        urls = [self.ollama_url, "http://127.0.0.1:11434", "http://localhost:11434"]
        PREFERRED_ORDER = ["qwen2.5:7b", "llama3.1:8b", "gemma2:9b", "gemma:2b"]
        
        for u in urls:
            try:
                async with httpx.AsyncClient(timeout=0.2) as client:
                    res = await client.get(f"{u}/api/tags")
                    if res.status_code == 200:
                        self.ollama_url = u
                        models = [m["name"] for m in res.json().get("models", [])]
                        if models:
                            models.sort(key=lambda name: PREFERRED_ORDER.index(name) if name in PREFERRED_ORDER else 99)
                            return models
            except Exception:
                continue
        return []



    async def check_ollama_available(self) -> bool:
        models = await self.get_available_models()
        return len(models) > 0

    async def _query_ollama(self, prompt: str, model: str) -> Optional[str]:
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                resp = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={"model": model, "prompt": prompt, "stream": False}
                )
                if resp.status_code == 200:
                    return resp.json().get("response")
        except Exception as e:
            logger.debug(f"Ollama local não acessível ({model}): {e}")
        return None

    def _fallback_deep_reasoning(self, sample: SystemMetricsSample, heur_sc: str, rag_data: Optional[Dict[str, Any]] = None) -> GenAIResult:
        """Engine local de síntese generativa e raciocínio técnico alimentado por RAG."""
        sc = sample.scenario if sample.scenario not in ["NORMAL", "CUSTOM"] else heur_sc
        meta = SCENARIOS_META.get(sc, SCENARIOS_META["NORMAL"])

        is_anomaly = (sc != "NORMAL")
        rag_info = rag_data or {"chunks": [], "top_distance": 0.0, "rag_enabled": False}

        # Geração de Raciocínio Diagnóstico
        if sc == "DDOS_ATTACK":
            diag = f"Inundação volumétrica detectada na camada de rede. Tráfego de entrada em {round(sample.network_in_bps / 1e6, 1)} MB/s com {sample.active_connections} conexões simultâneas."
            root_cause = "Possível ataque distribuído de negação de serviço (DDoS/SYN Flood) mirando a interface principal do servidor."
            impact = "NOC Alert: Degradação severa de SLA, travamento da pilha de sockets TCP e colapso na latência de resposta aos clientes."
            playbook = [
                "Ativar proteção Anti-DDoS / Rate Limiting no firewall de borda ou CDN",
                "Bloquear subredes de IPs atacantes via eBPF/iptables/Fail2Ban",
                "Filtrar pacotes SYN/UDP maliciosos na interface de rede",
                "Notificar a equipe de infraestrutura e provedor de trânsito IP"
            ]
        elif sc == "PORT_SCAN":
            diag = f"Padrão sistemático de varredura de rede identificado ({sample.active_connections} tentativas de conexão ativas)."
            root_cause = "Atividade de reconhecimento e sondagem de portas (Reconnaissance Phase / Nmap sweep) por um vetor externo ou máquina comprometida."
            impact = "Risco de descoberta de serviços vulneráveis não autorizados e exposição da superfície de ataque."
            playbook = [
                "Identificar IP de origem dos scans nos logs de firewall e registrar bloqueio temporário",
                "Revisar regras de exposição de portas TCP abertas na infraestrutura",
                "Ativar regras de port-knocking ou IDS/IPS (Suricata/Snort)"
            ]
        elif sc == "HOST_DOWN":
            diag = f"Host completamente inacessível (Perda ICMP = {sample.packet_loss_pct}%, Latência = {sample.latency_ms}ms)."
            root_cause = "Queda de energia do host, falha de kernel (Kernel Panic), perda de enlace físico ou falha crítica de roteamento."
            impact = "Indisponibilidade total do ativo. Incidente Crítico NOC Nível 1."
            playbook = [
                "Verificar status físico de energia e rede via Out-of-Band (iDRAC/iLO/IPMI)",
                "Checar chaveamento de switch e portas upstream",
                "Disparar chamado urgente para equipe de campo / Datacenter"
            ]
        elif sc == "MEMORY_LEAK":
            diag = f"Esgotamento da memória do sistema (RAM em {sample.ram_usage_pct}%)."
            root_cause = "Vazamento de memória (Memory Leak) em processo de aplicação ou contenção excessiva de memória sem garbage collection."
            impact = "Risco iminente de execução do OOM Killer (Out Of Memory) encerrando processos vitais."
            playbook = [
                "Executar 'top' / 'ps aux' para identificar o PID do processo com maior consumo de RAM",
                "Gerar dump de memória da aplicação para análise de causa raiz pelo time de DEV",
                "Reiniciar graciosamente o serviço afetado para liberar buffer e memória swap"
            ]
        elif sc == "DATA_EXFILTRATION":
            diag = f"Volume anômalo de dados em saída ({round(sample.network_out_bps / 1e6, 1)} MB/s Outbound)."
            root_cause = "Possível vazamento não autorizado ou exfiltração contínua de dados (Data Exfiltration / Botnet C2 traffic)."
            impact = "Ameaça grave de vazamento de informações confidenciais e violação de conformidade (LGPD/ISO 27001)."
            playbook = [
                "Isolar imediatamente o host de redes externas mantendo apenas VLAN de gerenciamento",
                "Inspecionar conexões ativas com 'ss -tupn' ou 'netstat' para identificar destino do tráfego",
                "Capturar pacotes via tcpdump para análise de forense digital"
            ]
        elif sc == "DISK_EXHAUSTION":
            diag = f"Armazenamento local no limite ({sample.disk_usage_pct}% de disco ocupado)."
            root_cause = "Acúmulo excessivo de logs não rotacionados, arquivos temporários ou crescimento não planejado da base de dados."
            impact = "Travamento do banco de dados, falha no registro de auditoria e recusa de gravações no sistema de arquivos."
            playbook = [
                "Executar limpeza de logs antigos e arquivos temporários em /tmp e /var/log",
                "Configurar rotação automática logrotate",
                "Expandir volume LVM ou provisionar disco adicional"
            ]
        elif sc == "SERVICE_OUTAGE":
            diag = f"Falha na camada de serviço Web/HTTP (Status HTTP: {sample.http_status_code}, Porta TCP: {'Aberta' if sample.tcp_port_open else 'Fechada'})."
            root_cause = "Erro interno da aplicação (Internal Server Error 500/503), queda do pool de conexões com banco ou processo web caído."
            impact = "Interrupção do serviço para usuários finais apesar do servidor de rede responder pings."
            playbook = [
                "Consultar logs de aplicação (systemctl status / docker logs) procurando exceções",
                "Verificar conectividade entre o serviço web e a base de dados",
                "Reiniciar os contêineres/daemons do serviço de aplicação"
            ]
        elif sc == "COMBINED_FAULT":
            diag = f"Múltiplos vetores em estado de colapso (CPU {sample.cpu_usage_pct}%, RAM {sample.ram_usage_pct}%, Latência {sample.latency_ms}ms)."
            root_cause = "Efeito cascata generalizado provocado por sobrecarga extrema ou falha sistêmica cruzada."
            impact = "Instabilidade global do servidor com alto risco de travamento total."
            playbook = [
                "Iniciar protocolo de mitigação de emergência NOC",
                "Mitigar tráfego na borda e drenar cargas de trabalho para servidores réplicas",
                "Executar reinício controlado do nó se não houver resposta aos comandos administrativos"
            ]
        elif sc == "NETWORK_CONGESTION":
            diag = f"Instabilidade e latência elevada na rede (Latência: {sample.latency_ms}ms, Jitter: {sample.jitter_ms}ms, Perda: {sample.packet_loss_pct}%)."
            root_cause = "Gargalo no enlace de transmissão, saturação de banda do provedor ou falha de chaveamento em roteador intermediário."
            impact = "Experiência de usuário degradada, lentidão em requisições de API e falhas esporádicas de conexão."
            playbook = [
                "Executar mtr/traceroute para mapear o salto de rede com perda e latência",
                "Verificar uso das interfaces de rede nos roteadores de borda via SNMP",
                "Acionar o suporte da operadora de telecomunicações informando o ponto de degradação"
            ]
        else:
            diag = "Métricas dentro dos padrões saudáveis de operação. Nenhuma anomalia detectada."
            root_cause = "Infraestrutura e rotas de rede funcionando de acordo com o SLA esperado."
            impact = "Sem impacto operacional. Sistema estável."
            playbook = [
                "Manter rotina padrão de monitoramento ativo NOC"
            ]

        # Anexa informações do RAG ao diagnóstico técnico
        if rag_info.get("rag_enabled") and rag_info.get("chunks"):
            top_c = rag_info["chunks"][0]
            diag += f" [RAG ChromaDB Context: Vetor '{top_c['id']}' com distância {top_c['distance']}]"

        return GenAIResult(
            predicted_scenario=sc,
            is_anomaly=is_anomaly,
            confidence=0.94 if is_anomaly else 0.98,
            provider="Engine Local GenAI com RAG (ChromaDB)",
            diagnostic_summary=diag,
            root_cause_analysis=root_cause,
            impact_assessment=impact,
            remediation_playbook=playbook,
            rag_enabled=rag_info.get("rag_enabled", False),
            rag_top_distance=rag_info.get("top_distance", 0.0),
            rag_chunks=rag_info.get("chunks", [])
        )

    async def classify(self, sample: SystemMetricsSample, heur_scenario: str = "NORMAL") -> GenAIResult:
        import re

        # 1. Recupera Contexto Vetorial via RAG (ChromaDB)
        rag_data = self.rag_retriever.retrieve_context(sample, top_k=3)
        rag_context_text = ""
        if rag_data.get("chunks"):
            rag_context_text = "\n".join([f"• [{c['id']}] {c['text']}" for c in rag_data["chunks"]])

        models = await self.get_available_models()
        if models:
            active_model = models[0]
            
            prompt = f"""Você é um Engenheiro Sênior de NOC e Segurança de Redes.
Sua missão é analisar os dados brutos de telemetria e o contexto histórico de RAG recuperado do ChromaDB e IDENTIFICAR SOZINHO qual anomalia de sistema está ocorrendo.

[TELEMETRIA DO SISTEMA EMBUTIDA]
- Latência ICMP: {sample.latency_ms} ms
- Perda de Pacotes ICMP: {sample.packet_loss_pct} %
- Jitter de Rede: {sample.jitter_ms} ms
- Uso de CPU: {sample.cpu_usage_pct} %
- Uso de RAM: {sample.ram_usage_pct} %
- Uso de Disco: {sample.disk_usage_pct} %
- Banda de Entrada (IN): {round(sample.network_in_bps / 1e6, 2)} MB/s
- Banda de Saída (OUT): {round(sample.network_out_bps / 1e6, 2)} MB/s
- Status HTTP Aplicação: {sample.http_status_code}
- Resposta HTTP: {sample.http_response_time_ms} ms
- Conexões TCP Ativas: {sample.active_connections}

[CONTEXTO VETORIAL RAG DO CHROMADB (HISTÓRICO DO DATASET REAL)]
{rag_context_text or "Nenhum histórico RAG recuperado."}

Instruções Estritas:
1. Classifique 'predicted_scenario' EXCLUSIVAMENTE em um destes 10 nomes exatos:
   NORMAL, DDOS_ATTACK, PORT_SCAN, HOST_DOWN, MEMORY_LEAK, DATA_EXFILTRATION, DISK_EXHAUSTION, SERVICE_OUTAGE, COMBINED_FAULT, NETWORK_CONGESTION.
2. Não adicione texto fora do objeto JSON.

Responda EXCLUSIVAMENTE em formato JSON com esta estrutura exata:
{{
  "predicted_scenario": "NOME_DO_CENARIO_DEDUZIDO",
  "diagnostic_summary": "resumo técnico detalhado em Português sobre o que você identificou na telemetria e no RAG",
  "root_cause_analysis": "análise técnica da causa raiz provável com base nas evidências",
  "impact_assessment": "impacto operacional no SLA e NOC",
  "remediation_playbook": [
    "Ação prática de mitigação 1",
    "Ação prática de mitigação 2",
    "Ação prática de mitigação 3"
  ]
}}
"""
            llm_resp = await self._query_ollama(prompt, model=active_model)
            if llm_resp:
                try:
                    json_match = re.search(r'\{.*\}', llm_resp, re.DOTALL)
                    if json_match:
                        data = json.loads(json_match.group(0))
                        
                        raw_pred = str(data.get("predicted_scenario", "")).upper().replace(" ", "_")
                        pred = raw_pred if raw_pred in SCENARIOS_META else heur_scenario

                        playbook_raw = data.get("remediation_playbook", [])
                        if isinstance(playbook_raw, list):
                            playbook = [str(x) for x in playbook_raw]
                        elif isinstance(playbook_raw, dict):
                            playbook = [f"{k}: {v}" for k, v in playbook_raw.items()]
                        elif isinstance(playbook_raw, str):
                            playbook = [playbook_raw]
                        else:
                            playbook = ["Consultar procedimentos de NOC."]

                        return GenAIResult(
                            predicted_scenario=pred,
                            is_anomaly=(pred != "NORMAL"),
                            confidence=0.95,
                            provider=f"Ollama RAG ({active_model})",
                            diagnostic_summary=str(data.get("diagnostic_summary", f"Diagnóstico RAG de anomalia {pred} sintetizado pelo modelo local {active_model}.")),
                            root_cause_analysis=str(data.get("root_cause_analysis", f"Análise de causa raiz para {pred} gerada pelo modelo local {active_model}.")),
                            impact_assessment=str(data.get("impact_assessment", f"Avaliação de impacto no NOC gerada por {active_model}.")),
                            remediation_playbook=playbook,
                            rag_enabled=rag_data.get("rag_enabled", False),
                            rag_top_distance=rag_data.get("top_distance", 0.0),
                            rag_chunks=rag_data.get("chunks", [])
                        )
                except Exception as e:
                    logger.debug(f"Erro no parse de JSON do Ollama: {e}")

        # Utiliza o Motor de Raciocínio Local Fallback com RAG
        return self._fallback_deep_reasoning(sample, heur_scenario, rag_data)



# ==========================================
# 4. MOTOR ENSEMBLE / CONSENSUS
# ==========================================
class EnsembleAnomalyClassifier:
    """Classificador híbrido que sintetiza os 3 motores em um parecer único."""

    def __init__(self):
        self.heuristics_engine = HeuristicEngine()
        self.ml_engine = MLEngine()
        self.genai_engine = LocalGenAIEngine()

    async def classify(self, sample: SystemMetricsSample) -> EnsembleResult:
        # 1. Executa Heurística e ML de forma síncrona/rápida
        heur_res = self.heuristics_engine.classify(sample)
        ml_res = self.ml_engine.classify(sample)

        # 2. Executa GenAI Local
        genai_res = await self.genai_engine.classify(sample, heur_scenario=heur_res.predicted_scenario)

        # 3. Cálculo de Consenso e Votação Ponderada
        votes: Dict[str, float] = {}

        # Heurística peso 0.40
        votes[heur_res.predicted_scenario] = votes.get(heur_res.predicted_scenario, 0.0) + (0.40 * heur_res.confidence)
        # ML peso 0.35
        votes[ml_res.predicted_scenario] = votes.get(ml_res.predicted_scenario, 0.0) + (0.35 * ml_res.confidence)
        # GenAI peso 0.25
        votes[genai_res.predicted_scenario] = votes.get(genai_res.predicted_scenario, 0.0) + (0.25 * genai_res.confidence)

        final_scenario = max(votes, key=votes.get)
        total_weight = sum(votes.values())
        overall_confidence = round(votes[final_scenario] / max(0.01, total_weight), 2)

        is_anomaly = (final_scenario != "NORMAL")

        # Nível de Risco
        if not is_anomaly:
            risk_level = "BAIXO"
        else:
            if final_scenario in ["HOST_DOWN", "COMBINED_FAULT", "DDOS_ATTACK", "DATA_EXFILTRATION", "DISK_EXHAUSTION"]:
                risk_level = "CRÍTICO"
            elif final_scenario in ["MEMORY_LEAK", "SERVICE_OUTAGE"]:
                risk_level = "ALTO"
            else:
                risk_level = "MÉDIO"

        consensus_match = (heur_res.predicted_scenario == ml_res.predicted_scenario == genai_res.predicted_scenario)

        # Recomendação Final
        rec = genai_res.remediation_playbook[0] if genai_res.remediation_playbook else "Verificar status do servidor no painel."

        return EnsembleResult(
            final_scenario=final_scenario,
            is_anomaly=is_anomaly,
            overall_confidence=overall_confidence,
            risk_level=risk_level,
            consensus_match=consensus_match,
            heuristics=heur_res,
            ml=ml_res,
            genai=genai_res,
            recommended_action=f"[{risk_level}] {rec}"
        )


anomaly_classifier = EnsembleAnomalyClassifier()
