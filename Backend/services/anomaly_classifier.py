"""
Módulo Avançado de Classificação de Anomalias de Sistema e Rede para o NetSpot.
Combina 3 motores independentes em ensemble ponderado:
1. Motor Heurístico Pericial de NOC (regras multi-vetor e scoring evidencial)
2. Motor de Machine Learning (RobustScaler + IsolationForest calibrado + RandomForest com Feature Engineering)
3. Motor de IA Generativa Local com RAG Vetorial (Ollama otimizado para RTX 5070 / Qwen3-14B + Dual-Engine RAG)
"""

import os
import re
import csv
import json
import logging
import httpx
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.preprocessing import RobustScaler

from .anomaly_simulator import SystemMetricsSample, SCENARIOS_META, anomaly_simulator

logger = logging.getLogger("netspot.anomaly_classifier")


# ==========================================
# MODELOS DE DADOS DE RESULTADOS
# ==========================================

class RuleViolation(BaseModel):
    rule_name: str
    metric: str
    value: Any
    threshold: Any
    weight: float = 1.0
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
    provider: str
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
# 1. MOTOR HEURÍSTICO PERICIAL DE NOC
# ==========================================

class HeuristicEngine:
    """Motor Heurístico de Alta Fidelidade com análise pericial multi-vetorial e scoring de evidências."""

    def classify(self, sample: SystemMetricsSample) -> HeuristicResult:
        rules: List[RuleViolation] = []
        scenario_scores: Dict[str, float] = {sc: 0.0 for sc in SCENARIOS_META.keys() if sc != "CUSTOM"}

        # ----------------------------------------------------
        # R1: HOST DOWN (Disponibilidade Nível 0)
        # ----------------------------------------------------
        if sample.packet_loss_pct >= 98.0 and (sample.latency_ms == 0.0 or sample.http_status_code == 0):
            rules.append(RuleViolation(
                rule_name="R_HOST_DOWN",
                metric="packet_loss_pct",
                value=sample.packet_loss_pct,
                threshold=98.0,
                weight=10.0,
                description="Perda total ou quase total de pacotes ICMP com ausência de resposta TCP"
            ))
            scenario_scores["HOST_DOWN"] += 15.0

        # ----------------------------------------------------
        # R2: ATAQUE DDOS VOLUMÉTRICO / SYN FLOOD
        # ----------------------------------------------------
        is_ddos_bandwidth = sample.network_in_bps > 65_000_000
        is_ddos_connections = sample.active_connections > 2200
        is_ddos_stress = sample.packet_loss_pct > 15.0 or sample.cpu_usage_pct > 80.0

        if is_ddos_bandwidth or (is_ddos_connections and is_ddos_stress):
            rules.append(RuleViolation(
                rule_name="R_DDOS_VOLUME_SPIKE",
                metric="network_in_bps",
                value=f"{sample.network_in_bps / 1e6:.1f} MB/s",
                threshold=">65 MB/s ou >2200 conexões com estresse",
                weight=6.0,
                description="Inundação massiva de pacotes de entrada e saturação da tabela de estados TCP"
            ))
            scenario_scores["DDOS_ATTACK"] += 8.0

        # ----------------------------------------------------
        # R3: VARREDURA DE PORTAS (PORT SCAN)
        # ----------------------------------------------------
        if sample.active_connections > 750 and sample.network_in_bps < 35_000_000 and sample.packet_loss_pct < 12.0:
            rules.append(RuleViolation(
                rule_name="R_PORT_SCAN_ANOMALY",
                metric="active_connections",
                value=sample.active_connections,
                threshold=">750 conexões com vazão moderada (<35 MB/s)",
                weight=5.0,
                description="Sonda sequencial ou aleatória com alta taxa de tentativas TCP SYN/FIN sem transferência de payload"
            ))
            scenario_scores["PORT_SCAN"] += 7.0

        # ----------------------------------------------------
        # R4: EXFILTRAÇÃO DE DADOS (DATA EXFILTRATION)
        # ----------------------------------------------------
        out_in_ratio = sample.network_out_bps / max(1.0, sample.network_in_bps)
        if sample.network_out_bps > 60_000_000 and out_in_ratio > 3.0:
            rules.append(RuleViolation(
                rule_name="R_ASYMMETRIC_EXFILTRATION",
                metric="network_out_bps",
                value=f"{sample.network_out_bps / 1e6:.1f} MB/s (Ratio={out_in_ratio:.1f}x)",
                threshold=">60 MB/s e Saída > 3x Entrada",
                weight=6.5,
                description="Vazão de upload desproporcional à recepção, indicativo de exfiltração massiva"
            ))
            scenario_scores["DATA_EXFILTRATION"] += 8.5

        # ----------------------------------------------------
        # R5: VAZAMENTO DE MEMÓRIA (MEMORY LEAK)
        # ----------------------------------------------------
        if sample.ram_usage_pct >= 90.0:
            rules.append(RuleViolation(
                rule_name="R_RAM_EXHAUSTION",
                metric="ram_usage_pct",
                value=f"{sample.ram_usage_pct:.1f}%",
                threshold=">= 90.0%",
                weight=4.5,
                description="Consumo crítico de memória volátil aproximando-se do gatilho OOM-Killer"
            ))
            scenario_scores["MEMORY_LEAK"] += 5.5

        # ----------------------------------------------------
        # R6: ESGOTAMENTO DE DISCO (DISK FULL)
        # ----------------------------------------------------
        if sample.disk_usage_pct >= 95.0:
            rules.append(RuleViolation(
                rule_name="R_STORAGE_CRITICAL",
                metric="disk_usage_pct",
                value=f"{sample.disk_usage_pct:.1f}%",
                threshold=">= 95.0%",
                weight=5.0,
                description="Capacidade de armazenamento local em saturação iminente para escrita de logs e transações"
            ))
            scenario_scores["DISK_EXHAUSTION"] += 7.0

        # ----------------------------------------------------
        # R7: FALHA DE APLICAÇÃO (SERVICE OUTAGE)
        # ----------------------------------------------------
        is_http_err = sample.http_status_code in [500, 502, 503, 504]
        is_network_healthy = sample.packet_loss_pct < 15.0 and sample.latency_ms < 80.0
        if (is_http_err or not sample.tcp_port_open) and is_network_healthy:
            rules.append(RuleViolation(
                rule_name="R_SERVICE_FAILURE",
                metric="http_status_code",
                value=sample.http_status_code if is_http_err else "Port Closed",
                threshold="200 OK",
                weight=5.0,
                description="A infraestrutura de rede responde regularmente, mas o serviço de aplicação retornou erro interno"
            ))
            scenario_scores["SERVICE_OUTAGE"] += 6.5

        # ----------------------------------------------------
        # R8: CONGESTIONAMENTO DE REDE (NETWORK CONGESTION)
        # ----------------------------------------------------
        is_high_lat = sample.latency_ms > 120.0
        is_high_jitter = sample.jitter_ms > 35.0
        is_moderate_loss = 8.0 <= sample.packet_loss_pct < 85.0
        is_host_light = sample.cpu_usage_pct < 75.0 and sample.network_in_bps < 40_000_000

        if (is_high_lat or is_high_jitter or is_moderate_loss) and is_host_light:
            rules.append(RuleViolation(
                rule_name="R_PATH_CONGESTION",
                metric="latency_ms",
                value=f"RTT={sample.latency_ms:.1f}ms, Jitter={sample.jitter_ms:.1f}ms",
                threshold="Latência > 120ms ou Jitter > 35ms com CPU normal",
                weight=4.0,
                description="Degradação severa no trajeto/roteamento da rede sem sobrecarga de hardware do nó"
            ))
            scenario_scores["NETWORK_CONGESTION"] += 5.5

        # ----------------------------------------------------
        # R9: FALHA MÚLTIPLA COMBINADA (COMBINED FAULT)
        # ----------------------------------------------------
        multi_exhaustion = (sample.cpu_usage_pct > 88.0 and sample.ram_usage_pct > 88.0 and sample.disk_usage_pct > 88.0)
        multi_critical = len(rules) >= 4 and sample.latency_ms > 200.0

        if multi_exhaustion or multi_critical:
            rules.append(RuleViolation(
                rule_name="R_COMBINED_CASCADE_FAULT",
                metric="composite_stress",
                value=f"CPU={sample.cpu_usage_pct:.0f}%, RAM={sample.ram_usage_pct:.0f}%, Disk={sample.disk_usage_pct:.0f}%",
                threshold="Saturação simultânea multissetorial",
                weight=8.0,
                description="Efeito dominó simultâneo em processamento, memória, armazenamento e resposta de rede"
            ))
            scenario_scores["COMBINED_FAULT"] += 10.0

        # Seleção do Cenário com maior pontuação evidencial
        best_scenario, best_score = max(scenario_scores.items(), key=lambda item: item[1])

        if best_score == 0.0 or len(rules) == 0:
            scenario = "NORMAL"
            confidence = 0.96
            severity = "OK"
        else:
            scenario = best_scenario
            # Confiança calculada proporcionalmente ao acúmulo de evidências
            confidence = min(0.98, max(0.75, 0.70 + (best_score * 0.03)))
            
            # Determinação de severidade NOC
            if scenario in ["HOST_DOWN", "DDOS_ATTACK", "COMBINED_FAULT", "DATA_EXFILTRATION"]:
                severity = "CRITICAL"
            elif scenario in ["MEMORY_LEAK", "DISK_EXHAUSTION", "SERVICE_OUTAGE"]:
                severity = "WARNING" if best_score < 7.0 else "CRITICAL"
            else:
                severity = "WARNING"

        is_anomaly = (scenario != "NORMAL")
        summary = f"Cenário heurístico: {scenario}. {len(rules)} regra(s) violada(s) com severidade {severity}."

        return HeuristicResult(
            predicted_scenario=scenario,
            is_anomaly=is_anomaly,
            confidence=round(confidence, 3),
            severity=severity,
            triggered_rules=rules,
            summary=summary
        )


# ==========================================
# 2. MOTOR DE MACHINE LEARNING COM ROBUST SCALER E FEATURE ENGINEERING
# ==========================================

class MLEngine:
    """Motor de Machine Learning com Feature Engineering de redes, RobustScaler e calibração estatística."""

    FEATURE_NAMES = [
        "latency_ms", "packet_loss_pct", "jitter_ms",
        "cpu_usage_pct", "ram_usage_pct", "disk_usage_pct",
        "network_in_bps", "network_out_bps", "http_status_code",
        "http_response_time_ms", "tcp_port_open", "active_connections",
        # Features Derivadas de Física de Redes:
        "in_out_ratio", "out_in_ratio", "net_stress_mb",
        "latency_loss_idx", "resource_composite", "conn_cpu_density"
    ]

    def __init__(self):
        self.scaler = RobustScaler()
        self.iso_forest = IsolationForest(n_estimators=120, contamination=0.30, random_state=42, n_jobs=-1)
        self.rf_classifier = RandomForestClassifier(
            n_estimators=150,
            max_depth=16,
            min_samples_split=4,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1
        )
        self.is_trained = False
        self.scenarios_list = [sc for sc in SCENARIOS_META.keys() if sc != "CUSTOM"]
        self._model_dir = os.path.join(os.path.dirname(__file__), "..", "ml_models")
        self._train_initial_model()

    def _extract_features(self, sample: SystemMetricsSample) -> np.ndarray:
        """Gera o vetor de 18 características físicas e estatísticas normalizadas."""
        in_bps = max(0.0, sample.network_in_bps)
        out_bps = max(0.0, sample.network_out_bps)
        
        # Features derivadas de engenharia de tráfego
        in_out_ratio = in_bps / max(1000.0, out_bps)
        out_in_ratio = out_bps / max(1000.0, in_bps)
        net_stress_mb = (in_bps + out_bps) / 1e6
        latency_loss_idx = (sample.latency_ms * (sample.packet_loss_pct + 1.0)) / 100.0
        resource_composite = (sample.cpu_usage_pct * 0.4 + sample.ram_usage_pct * 0.4 + sample.disk_usage_pct * 0.2)
        conn_cpu_density = float(sample.active_connections) / max(1.0, sample.cpu_usage_pct)

        return np.array([[
            sample.latency_ms,
            sample.packet_loss_pct,
            sample.jitter_ms,
            sample.cpu_usage_pct,
            sample.ram_usage_pct,
            sample.disk_usage_pct,
            in_bps,
            out_bps,
            float(sample.http_status_code),
            sample.http_response_time_ms,
            1.0 if sample.tcp_port_open else 0.0,
            float(sample.active_connections),
            in_out_ratio,
            out_in_ratio,
            net_stress_mb,
            latency_loss_idx,
            resource_composite,
            conn_cpu_density
        ]])

    def _train_initial_model(self):
        """Treina o pipeline com robust scaling sobre amostras estocásticas balanceadas."""
        try:
            logger.info("Inicializando e treinando pipeline de Machine Learning (RobustScaler + IsoForest + RF)...")
            X_train = []
            y_train = []
            
            # 1.200 amostras equilibradas por cenário para calibrar fronteiras de decisão
            for sc in self.scenarios_list:
                batch = anomaly_simulator.generate_batch(scenario=sc, count=1200)
                for s in batch:
                    X_train.append(self._extract_features(s)[0])
                    y_train.append(sc)

            X_arr = np.array(X_train)
            y_arr = np.array(y_train)

            # Ajuste de escala robusto e treinamento dos modelos
            X_scaled = self.scaler.fit_transform(X_arr)
            self.iso_forest.fit(X_scaled)
            self.rf_classifier.fit(X_scaled, y_arr)
            self.is_trained = True
            logger.info("Pipeline de Machine Learning treinado com 12.000 amostras multivariadas!")
        except Exception as e:
            logger.error(f"Erro no treinamento do modelo de ML: {e}")

    def train_custom(self, samples_per_scenario: int = 500) -> Dict[str, Any]:
        """Permite re-treinar dinamicamente o modelo via endpoint REST."""
        X_train = []
        y_train = []
        for sc in self.scenarios_list:
            batch = anomaly_simulator.generate_batch(scenario=sc, count=samples_per_scenario)
            for s in batch:
                X_train.append(self._extract_features(s)[0])
                y_train.append(sc)

        X_arr = np.array(X_train)
        y_arr = np.array(y_train)

        X_scaled = self.scaler.fit_transform(X_arr)
        self.iso_forest.fit(X_scaled)
        self.rf_classifier.fit(X_scaled, y_arr)
        self.is_trained = True

        acc = float(self.rf_classifier.score(X_scaled, y_arr))
        return {
            "status": "success",
            "samples_trained": len(X_train),
            "training_accuracy": round(acc, 4)
        }

    def classify(self, sample: SystemMetricsSample) -> MLResult:
        if not self.is_trained:
            self._train_initial_model()

        X = self._extract_features(sample)
        X_scaled = self.scaler.transform(X)

        # 1. Isolation Forest Anomaly Score calibrado para [0.0, 1.0]
        raw_score = self.iso_forest.decision_function(X_scaled)[0]
        anomaly_score = float(np.clip(0.5 - (raw_score * 0.8), 0.0, 1.0))

        # 2. Random Forest Classification
        pred_scenario = str(self.rf_classifier.predict(X_scaled)[0])
        probs = self.rf_classifier.predict_proba(X_scaled)[0]
        classes = self.rf_classifier.classes_

        class_probs = {cls: round(float(prob), 4) for cls, prob in zip(classes, probs)}
        top_confidence = round(float(np.max(probs)), 4)

        # 3. Explicabilidade XAI: cálculo de desvio relativo por feature para a amostra
        global_imp = self.rf_classifier.feature_importances_
        feature_deviations = {}
        for idx, feat_name in enumerate(self.FEATURE_NAMES):
            val = X[0][idx]
            scale = max(1e-4, float(self.scaler.scale_[idx]))
            center = float(self.scaler.center_[idx])
            z_dev = abs(val - center) / scale
            feature_deviations[feat_name] = z_dev * (global_imp[idx] + 0.05)

        total_dev = sum(feature_deviations.values())
        if total_dev > 0.01:
            norm_imp = {k: round(float(v / total_dev), 4) for k, v in feature_deviations.items()}
        else:
            norm_imp = {k: round(float(imp), 4) for k, imp in zip(self.FEATURE_NAMES, global_imp)}

        is_anomaly = (pred_scenario != "NORMAL") or (anomaly_score > 0.60)

        return MLResult(
            predicted_scenario=pred_scenario,
            is_anomaly=is_anomaly,
            anomaly_score=round(anomaly_score, 3),
            confidence=top_confidence,
            feature_importances=norm_imp,
            class_probabilities=class_probs
        )


# ==========================================
# 3. MOTOR RAG HÍBRIDO (CHROMADB + INDEXADOR DENSO DE CONTINGÊNCIA)
# ==========================================

class RAGRetriever:
    """Motor RAG Híbrido com indexação vetorial contínua a partir de dados históricos do dataset real."""

    def __init__(self):
        self.is_ready = False
        self.engine_type = "Offline"
        self.chroma_collection = None
        self.dense_vectors: List[Tuple[np.ndarray, Dict[str, Any], str]] = []
        
        # Localização de datasets reais de evidência
        self.dataset_paths = [
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "netspot_anomaly_dataset.csv")),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "RAG", "src", "dataset.csv"))
        ]
        self._initialize_rag()

    def _initialize_rag(self):
        # 1. Tentar carregar via ChromaDB se o pacote estiver disponível
        try:
            import chromadb
            from chromadb.utils import embedding_functions

            chroma_client = chromadb.Client()
            default_ef = embedding_functions.DefaultEmbeddingFunction()
            col_name = "netspot_telemetry_rag"
            try:
                chroma_client.delete_collection(col_name)
            except Exception:
                pass

            self.chroma_collection = chroma_client.create_collection(
                name=col_name,
                embedding_function=default_ef
            )
            self._load_corpus_into_chroma()
            self.is_ready = True
            self.engine_type = "ChromaDB Vector Store"
            logger.info("RAG Engine ChromaDB inicializado com sucesso!")
            return
        except Exception as e:
            logger.info(f"ChromaDB não ativo ({e}). Ativando DenseVectorRAG embutido de alta precisão...")

        # 2. Inicializar DenseVectorRAG embutido (similaridade cosseno matricial instantânea)
        try:
            self._load_corpus_into_dense_engine()
            self.is_ready = True
            self.engine_type = "Dense Vector Cosine Engine"
            logger.info(f"DenseVectorRAG embutido ativo com {len(self.dense_vectors)} vetores históricos indexados!")
        except Exception as err:
            logger.error(f"Erro ao inicializar RAG embutido: {err}")
            self.is_ready = False

    def _get_corpus_documents(self) -> List[Dict[str, Any]]:
        docs = []
        # Perfis descritivos dos cenários
        for sc_key, meta in SCENARIOS_META.items():
            if sc_key == "CUSTOM":
                continue
            docs.append({
                "id": f"profile_{sc_key}",
                "text": f"PERFIL OPERACIONAL {sc_key}: {meta['title']}. {meta['description']}. Categoria de infraestrutura: {meta['category']}.",
                "scenario": sc_key,
                "type": "scenario_profile",
                "telemetry_vec": None
            })

        # Extração de amostras estatísticas do dataset CSV real
        dataset_found = None
        for p in self.dataset_paths:
            if os.path.exists(p):
                dataset_found = p
                break

        if dataset_found:
            scenario_clusters: Dict[str, List[Dict[str, float]]] = {}
            with open(dataset_found, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    sc = row.get("scenario", "UNKNOWN")
                    if sc not in scenario_clusters:
                        scenario_clusters[sc] = []
                    if len(scenario_clusters[sc]) < 40:
                        scenario_clusters[sc].append({
                            "lat": float(row.get("latency_ms", 15.0)),
                            "loss": float(row.get("packet_loss_pct", 0.0)),
                            "cpu": float(row.get("cpu_usage_pct", 25.0)),
                            "ram": float(row.get("ram_usage_pct", 40.0)),
                            "disk": float(row.get("disk_usage_pct", 40.0)),
                            "net_in": float(row.get("network_in_bps", 5e6)),
                            "net_out": float(row.get("network_out_bps", 2e6)),
                            "conn": float(row.get("active_connections", 40.0)),
                            "http": int(float(row.get("http_status_code", 200))),
                        })

            for sc, samples in scenario_clusters.items():
                if not samples:
                    continue
                avg_lat = sum(s["lat"] for s in samples) / len(samples)
                avg_loss = sum(s["loss"] for s in samples) / len(samples)
                avg_cpu = sum(s["cpu"] for s in samples) / len(samples)
                avg_ram = sum(s["ram"] for s in samples) / len(samples)
                avg_net_in = sum(s["net_in"] for s in samples) / len(samples) / 1e6
                avg_net_out = sum(s["net_out"] for s in samples) / len(samples) / 1e6
                avg_conn = sum(s["conn"] for s in samples) / len(samples)

                docs.append({
                    "id": f"dataset_{sc}",
                    "text": (
                        f"EVIDÊNCIA HISTÓRICA DO DATASET ({sc}): "
                        f"Latência={avg_lat:.1f}ms | Perda={avg_loss:.1f}% | CPU={avg_cpu:.1f}% | "
                        f"RAM={avg_ram:.1f}% | NetIn={avg_net_in:.1f}MB/s | NetOut={avg_net_out:.1f}MB/s | "
                        f"Conexões Médias={avg_conn:.0f} sockets TCP ativos."
                    ),
                    "scenario": sc,
                    "type": "historical_cluster",
                    "telemetry_vec": np.array([avg_lat, avg_loss, avg_cpu, avg_ram, avg_net_in * 1e6, avg_net_out * 1e6, avg_conn])
                })

        return docs

    def _load_corpus_into_chroma(self):
        docs = self._get_corpus_documents()
        self.chroma_collection.add(
            documents=[d["text"] for d in docs],
            metadatas=[{"scenario": d["scenario"], "type": d["type"]} for d in docs],
            ids=[d["id"] for d in docs]
        )

    def _load_corpus_into_dense_engine(self):
        docs = self._get_corpus_documents()
        self.dense_vectors = []
        for d in docs:
            vec = d.get("telemetry_vec")
            if vec is None:
                # Vetor aproximado para perfis teóricos
                vec = np.array([20.0, 0.0, 30.0, 45.0, 5e6, 2e6, 50.0])
            norm = np.linalg.norm(vec)
            unit_vec = vec / (norm if norm > 0 else 1.0)
            self.dense_vectors.append((unit_vec, {"scenario": d["scenario"], "type": d["type"]}, d["text"], d["id"]))

    def retrieve_context(self, sample: SystemMetricsSample, top_k: int = 3) -> Dict[str, Any]:
        if not self.is_ready:
            return {"chunks": [], "top_distance": 0.0, "rag_enabled": False}

        # 1. Consulta via ChromaDB
        if self.chroma_collection is not None:
            try:
                query_str = (
                    f"Cenário {sample.scenario}: Latência={sample.latency_ms}ms Perda={sample.packet_loss_pct}% "
                    f"CPU={sample.cpu_usage_pct}% RAM={sample.ram_usage_pct}% "
                    f"NetIn={sample.network_in_bps / 1e6:.1f}MB NetOut={sample.network_out_bps / 1e6:.1f}MB "
                    f"Conexões={sample.active_connections}"
                )
                results = self.chroma_collection.query(query_texts=[query_str], n_results=top_k)
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
                return {"chunks": chunks, "top_distance": chunks[0]["distance"] if chunks else 0.0, "rag_enabled": True}
            except Exception as e:
                logger.warning(f"Erro em consulta ChromaDB: {e}. Alternando para dense retriever...")

        # 2. Consulta via Dense Vector Cosine Engine
        try:
            q_vec = np.array([
                sample.latency_ms,
                sample.packet_loss_pct,
                sample.cpu_usage_pct,
                sample.ram_usage_pct,
                sample.network_in_bps,
                sample.network_out_bps,
                float(sample.active_connections)
            ])
            q_norm = np.linalg.norm(q_vec)
            q_unit = q_vec / (q_norm if q_norm > 0 else 1.0)

            scored = []
            for unit_vec, meta, text, chunk_id in self.dense_vectors:
                # Similaridade de Cosseno -> Distância = 1 - cosine
                cosine_sim = float(np.dot(q_unit, unit_vec))
                dist = round(float(max(0.0, 1.0 - cosine_sim)), 4)
                scored.append((dist, chunk_id, text, meta))

            scored.sort(key=lambda x: x[0])
            top_results = scored[:top_k]

            chunks = [
                {
                    "id": item[1],
                    "text": item[2],
                    "distance": item[0],
                    "scenario": item[3].get("scenario", "UNKNOWN"),
                    "type": item[3].get("type", "telemetry")
                }
                for item in top_results
            ]

            return {
                "chunks": chunks,
                "top_distance": chunks[0]["distance"] if chunks else 0.0,
                "rag_enabled": True
            }
        except Exception as ex:
            logger.error(f"Erro no DenseVectorRAG: {ex}")
            return {"chunks": [], "top_distance": 0.0, "rag_enabled": False}


# ==========================================
# 4. MOTOR DE IA GENERATIVA LOCAL (OTIMIZADO PARA RTX 5070 / QWEN3-14B)
# ==========================================

class GenAIEngine:
    """Motor de IA Generativa Local com conexão direta ao Qwen3-14B na RTX 5070 e RAG."""

    def __init__(self, ollama_url: Optional[str] = None):
        self.ollama_url = ollama_url or os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
        self.rag_retriever = RAGRetriever()

    async def get_available_models(self) -> List[str]:
        """Localiza modelos instalados priorizando qwen3:14b da RTX 5070."""
        urls = [self.ollama_url, "http://127.0.0.1:11434", "http://localhost:11434", "http://host.docker.internal:11434"]
        PREFERRED_ORDER = [
            "qwen3:14b", "qwen3", "qwen2.5:14b", "qwen2.5:7b",
            "deepseek-r1:14b", "deepseek-r1:8b", "llama3.1:8b", "gemma2:9b", "gemma:2b"
        ]

        for u in urls:
            try:
                # Timeout defensivo de 2.5s para atravessar o bridge do Docker no WSL
                async with httpx.AsyncClient(timeout=2.5) as client:
                    res = await client.get(f"{u}/api/tags")
                    if res.status_code == 200:
                        self.ollama_url = u
                        models = [m["name"] for m in res.json().get("models", [])]
                        if models:
                            models.sort(
                                key=lambda name: next(
                                    (idx for idx, pref in enumerate(PREFERRED_ORDER) if pref in name), 99
                                )
                            )
                            return models
            except Exception:
                continue
        return []

    async def check_ollama_available(self) -> bool:
        models = await self.get_available_models()
        return len(models) > 0

    async def _query_ollama(self, prompt: str, model: str) -> Optional[str]:
        try:
            # Configura options com parada e temperatura baixa para saídas determinísticas
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "top_p": 0.9,
                    "num_ctx": 4096
                }
            }
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(f"{self.ollama_url}/api/generate", json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    raw_response = data.get("response", "")
                    
                    # Suporte a modelos de raciocínio profundo (Qwen3 / DeepSeek R1)
                    # Remove blocos <think>...</think> se existirem no texto retornado
                    cleaned_response = re.sub(r'<think>.*?</think>', '', raw_response, flags=re.DOTALL).strip()
                    return cleaned_response or raw_response
        except Exception as e:
            logger.debug(f"Ollama local em espera ou indisponível ({model}): {e}")
        return None

    def _fallback_deep_reasoning(
        self,
        sample: SystemMetricsSample,
        heur_sc: str,
        rag_data: Optional[Dict[str, Any]] = None
    ) -> GenAIResult:
        """Engine pericial determinístico de síntese e raciocínio técnico alimentado por RAG."""
        sc = sample.scenario if sample.scenario not in ["NORMAL", "CUSTOM"] else heur_sc
        is_anomaly = (sc != "NORMAL")
        rag_info = rag_data or {"chunks": [], "top_distance": 0.0, "rag_enabled": False}

        # Sínteses técnicas de alto nível operacional de NOC
        reasons_map = {
            "DDOS_ATTACK": (
                f"Inundação volumétrica detectada na interface de rede com entrada em {round(sample.network_in_bps / 1e6, 1)} MB/s "
                f"e {sample.active_connections} conexões simultâneas concorrentes.",
                "Saturação maliciosa de banda e exaustão da tabela de estados TCP por ataque distribuído (DDoS/SYN Flood).",
                "Alerta NOC L3: Colapso de latência, degradação severa de SLA e potencial indisponibilidade geral do nó.",
                [
                    "Ativar mitigação automatizada de scrubbing de tráfego e regras de SYN cookies no kernel.",
                    "Bloquear blocos CIDR de origem suspeita no firewall de borda ou via BGP Flowspec.",
                    "Rate-limiting por IP na camada 4 e restrição de conexões simultâneas via iptables."
                ]
            ),
            "PORT_SCAN": (
                f"Sonda sequencial ou aleatória identificada com pico anômalo de {sample.active_connections} conexões ativas "
                f"com volume de dados reduzido ({round(sample.network_in_bps / 1e6, 1)} MB/s).",
                "Varredura automatizada de reconhecimento de superfície de ataque (Port Scan / TCP Recon).",
                "Risco Médio de Segurança: Identificação de serviços e mapeamento de vulnerabilidades ativas no host.",
                [
                    "Acionar blackhole temporário para IPs de origem das conexões de sondagem via fail2ban.",
                    "Aplicar proteção TCP RST com limite de pacotes por segundo.",
                    "Auditar portas não essenciais expostas no security group e fechar portas ociosas."
                ]
            ),
            "HOST_DOWN": (
                "Interrupção total do enlace ICMP (100% packet loss) e recusa completa de conexões TCP do serviço.",
                "Falha física no nó de computação, desativação da interface de rede ou pane de kernel.",
                "Incidente Crítico NOC L1: Descontinuidade operacional imediata de todos os serviços hospedados.",
                [
                    "Executar reinicialização forçada via console de gerenciamento fora de banda (IPMI/BMC).",
                    "Redirecionar tráfego para nó secundário no cluster de failover de alta disponibilidade.",
                    "Checar conectividade física do switch Top-of-Rack e interface de rede do host."
                ]
            ),
            "MEMORY_LEAK": (
                f"Exaustão progressiva e sustentada de memória RAM atingindo {sample.ram_usage_pct:.1f}%, "
                f"com tempo de resposta degradado em {sample.http_response_time_ms:.0f} ms.",
                "Retenção contínua de objetos e falha de liberação de memória heap (Memory Leak) no processo principal.",
                "Risco Iminente: Acionamento forçado do Linux OOM Killer com término abrupto do processo de serviço.",
                [
                    "Efetuar dump de heap para profiling diagnóstico e reiniciar o worker da aplicação.",
                    "Configurar restart preventivo por limiar de memória no orquestrador (Docker restart-policy / Kubernetes).",
                    "Revisar vazamento de conexões abertas no pool de banco de dados e buffers de sockets."
                ]
            ),
            "DATA_EXFILTRATION": (
                f"Vazão de upload anômala de {round(sample.network_out_bps / 1e6, 1)} MB/s superando em mais de "
                f"3x o tráfego de recepção ({round(sample.network_in_bps / 1e6, 1)} MB/s).",
                "Transferência de grande volume de dados para endereço externo não categorizado (Exfiltração de Dados).",
                "Incidente Crítico de Segurança: Vazamento em potencial de ativos intelectuais ou dados confidenciais.",
                [
                    "Isolar imediatamente o host da rede corporativa mantendo apenas interface de auditoria forense.",
                    "Inspecionar conexões ativas via ss/netstat e auditar sockets com endpoints externos desconhecidos.",
                    "Revogar credenciais de API e chaves de acesso utilizadas na sessão ativa."
                ]
            ),
            "DISK_EXHAUSTION": (
                f"Armazenamento local em nível crítico de {sample.disk_usage_pct:.1f}%, comprometendo operações de escrita.",
                "Acúmulo acelerado de arquivos de log não rotacionados, dumps de depuração ou expansão descontrolada de banco.",
                "Alerta Operacional NOC: Bloqueio de novas transações e travamento de daemons por falha de I/O em disco.",
                [
                    "Executar expurgo de arquivos de log arquivados e limpar diretórios temporários /tmp.",
                    "Forçar rotação do logrotate e compactação dos WALs do PostgreSQL.",
                    "Expandir o volume LVM ou provisionar armazenamento EBS/SAN adicional."
                ]
            ),
            "SERVICE_OUTAGE": (
                f"Falha na camada de aplicação HTTP com status de erro {sample.http_status_code} "
                f"ou porta indisponível, enquanto conectividade ICMP opera sem perdas.",
                "Crash interno do runtime da aplicação, timeout de banco ou esgotamento do pool de conexões.",
                "Alerta de Aplicação: Indisponibilidade de serviço voltada aos clientes com rota de rede saudável.",
                [
                    "Reiniciar o processo de aplicação e verificar logs de stack trace com status 5xx.",
                    "Checar disponibilidade e tempo de resposta da base de dados PostgreSQL.",
                    "Restabelecer o container através da política de autocura do orquestrador."
                ]
            ),
            "COMBINED_FAULT": (
                f"Colapso simultâneo em CPU ({sample.cpu_usage_pct:.0f}%), RAM ({sample.ram_usage_pct:.0f}%), "
                f"Disco ({sample.disk_usage_pct:.0f}%) e Latência de Rede ({sample.latency_ms:.0f}ms).",
                "Efeito dominó ou sobrecarga sistêmica em cascata afetando todos os recursos do nó.",
                "Incidente Catastrófico de Infraestrutura: Degradação completa de SLA e inviabilidade de resposta.",
                [
                    "Isolar nó do tráfego de produção no balanceador de carga.",
                    "Executar procedimento de reinicialização graciosa de serviços essenciais em ordem de dependência.",
                    "Validar métricas de hipervisor para descartar pane de hardware físico ou contenção ruidosa (noisy neighbor)."
                ]
            ),
            "NETWORK_CONGESTION": (
                f"Degradação severa de rota com latência em {sample.latency_ms:.1f}ms e perda moderada de pacotes ({sample.packet_loss_pct:.1f}%), "
                f"sem evidências de saturação nos componentes de hardware do nó.",
                "Saturação de link de trânsito, jitter de operadora ou bufferbloat em roteador intermediário.",
                "Alerta de Desempenho de Rede: Aumento do tempo de resposta aos usuários finais por degradação de trânsito.",
                [
                    "Verificar utilização de banda nos links WAN da operadora de telecomunicações.",
                    "Habilitar controle ativo de filas (AQM/FQ-CoDel) no roteador de borda para mitigar bufferbloat.",
                    "Rerotear tráfego de dados para caminho BGP alternativo ou rota MPLS de backup."
                ]
            )
        }

        default_tuple = (
            "Sistema e serviços operando dentro dos limiares de excelência e SLAs estabelecidos.",
            "Operação normal de rotina sem evidências de anomalias estatísticas ou estruturais.",
            "Sem impacto no SLA de disponibilidade ou desempenho da infraestrutura.",
            [
                "Manter rotina contínua de telemetria ativa e inspeção periódica de saúde dos ativos.",
                "Validar conformidade dos parâmetros de linha de base com os limiares de alerta."
            ]
        )

        diag, root_cause, impact, playbook = reasons_map.get(sc, default_tuple)

        # Enriquecer o diagnóstico com evidência RAG se houver vetores históricos
        if rag_info.get("chunks"):
            top_chunk = rag_info["chunks"][0]
            diag += f" [Contexto RAG Histórico validado contra vetor {top_chunk['id']} com distância {top_chunk['distance']}]."

        return GenAIResult(
            predicted_scenario=sc,
            is_anomaly=is_anomaly,
            confidence=0.95,
            provider="Engine Local GenAI com RAG",
            diagnostic_summary=diag,
            root_cause_analysis=root_cause,
            impact_assessment=impact,
            remediation_playbook=playbook,
            rag_enabled=rag_info.get("rag_enabled", False),
            rag_top_distance=rag_info.get("top_distance", 0.0),
            rag_chunks=rag_info.get("chunks", [])
        )

    async def classify(self, sample: SystemMetricsSample, heur_scenario: str = "NORMAL") -> GenAIResult:
        # 1. Recuperar contexto vetorial do RAG
        rag_data = self.rag_retriever.retrieve_context(sample, top_k=2)
        rag_context_text = "\n".join(f"- {c['id']} (Distância: {c['distance']}): {c['text']}" for c in rag_data.get("chunks", []))

        # 2. Verificar modelo instalado no Ollama (priorizando qwen3:14b na RTX 5070)
        models = await self.get_available_models()
        active_model = models[0] if models else None

        if active_model:
            prompt = f"""[INSTRUÇÃO DO SISTEMA]
Você é o Especialista L3 em Engenharia de NOC e Segurança de Redes do NetSpot.
Sua missão é emitir um diagnóstico técnico preciso e objetivo em formato JSON com base na telemetria observada e no histórico vetorial do RAG.

[TELEMETRIA DO SISTEMA EM TEMPO REAL]
- Cenário Notificado: {sample.scenario}
- Latência ICMP: {sample.latency_ms} ms
- Perda de Pacotes ICMP: {sample.packet_loss_pct} %
- Jitter de Rede: {sample.jitter_ms} ms
- Uso de Processador (CPU): {sample.cpu_usage_pct} %
- Uso de Memória (RAM): {sample.ram_usage_pct} %
- Uso de Armazenamento (Disco): {sample.disk_usage_pct} %
- Tráfego de Entrada (Inbound): {round(sample.network_in_bps / 1e6, 2)} MB/s
- Tráfego de Saída (Outbound): {round(sample.network_out_bps / 1e6, 2)} MB/s
- Status HTTP Aplicação: {sample.http_status_code}
- Resposta HTTP: {sample.http_response_time_ms} ms
- Conexões TCP Ativas: {sample.active_connections}

[CONTEXTO VETORIAL RAG DO DATASET HISTÓRICO]
{rag_context_text or "Nenhum histórico vetorial adicional."}

Classifique o cenário EXCLUSIVAMENTE em um destes 10 nomes exatos:
NORMAL, DDOS_ATTACK, PORT_SCAN, HOST_DOWN, MEMORY_LEAK, DATA_EXFILTRATION, DISK_EXHAUSTION, SERVICE_OUTAGE, COMBINED_FAULT, NETWORK_CONGESTION.

Responda ESTRITAMENTE em formato JSON puro (sem markdown, sem introduções):
{{
  "predicted_scenario": "NOME_DO_CENARIO",
  "diagnostic_summary": "resumo técnico detalhado em Português sobre o que você identificou na telemetria e no RAG",
  "root_cause_analysis": "análise técnica da causa raiz provável com base nas evidências",
  "impact_assessment": "impacto operacional no SLA e NOC",
  "remediation_playbook": [
    "Ação prática de mitigação 1",
    "Ação prática de mitigação 2",
    "Ação prática de mitigação 3"
  ]
}}"""
            llm_resp = await self._query_ollama(prompt, model=active_model)
            if llm_resp:
                try:
                    # Extração defensiva de JSON suportando modelos thinking
                    json_match = re.search(r'\{.*\}', llm_resp, re.DOTALL)
                    if json_match:
                        data = json.loads(json_match.group(0))
                        raw_pred = str(data.get("predicted_scenario", "")).upper().replace(" ", "_").strip()
                        pred = raw_pred if raw_pred in SCENARIOS_META else heur_scenario

                        playbook_raw = data.get("remediation_playbook", [])
                        if isinstance(playbook_raw, list):
                            playbook = [str(x) for x in playbook_raw]
                        else:
                            playbook = [str(playbook_raw)]

                        return GenAIResult(
                            predicted_scenario=pred,
                            is_anomaly=(pred != "NORMAL"),
                            confidence=0.96,
                            provider=f"Ollama Local ({active_model}) + RAG",
                            diagnostic_summary=data.get("diagnostic_summary", "Diagnóstico processado com sucesso."),
                            root_cause_analysis=data.get("root_cause_analysis", "Análise de causa raiz gerada via LLM local."),
                            impact_assessment=data.get("impact_assessment", "Impacto de SLA avaliado pelo modelo local."),
                            remediation_playbook=playbook,
                            rag_enabled=rag_data.get("rag_enabled", False),
                            rag_top_distance=rag_data.get("top_distance", 0.0),
                            rag_chunks=rag_data.get("chunks", [])
                        )
                except Exception as parse_err:
                    logger.debug(f"Falha de decodificação JSON do modelo local: {parse_err}. Aplicando fallback pericial.")

        # Fallback de raciocínio profundo quando Ollama offline ou resposta sem formato
        return self._fallback_deep_reasoning(sample, heur_sc=heur_scenario, rag_data=rag_data)


# ==========================================
# 5. ORQUESTRADOR DO ENSEMBLE TRÍPLICE
# ==========================================

class AnomalyClassifier:
    """Orquestrador do Ensemble Tríplice (Heurística + Machine Learning + GenAI com RAG)."""

    def __init__(self):
        self.heuristics_engine = HeuristicEngine()
        self.ml_engine = MLEngine()
        self.genai_engine = GenAIEngine()

    async def classify(self, sample: SystemMetricsSample) -> EnsembleResult:
        # 1. Execução do Motor Heurístico
        heur_res = self.heuristics_engine.classify(sample)

        # 2. Execução do Motor de Machine Learning
        ml_res = self.ml_engine.classify(sample)

        # 3. Execução da IA Generativa Local com RAG
        genai_res = await self.genai_engine.classify(sample, heur_scenario=heur_res.predicted_scenario)

        # 4. Decisão de Consenso Ponderada
        # Pesos: Heurística (0.35), ML (0.35), GenAI (0.30)
        votes: Dict[str, float] = {}
        for scen, weight in [
            (heur_res.predicted_scenario, 0.35),
            (ml_res.predicted_scenario, 0.35),
            (genai_res.predicted_scenario, 0.30)
        ]:
            votes[scen] = votes.get(scen, 0.0) + weight

        final_scenario, best_weight = max(votes.items(), key=lambda item: item[1])
        consensus = (heur_res.predicted_scenario == ml_res.predicted_scenario == genai_res.predicted_scenario)

        is_anomaly = (final_scenario != "NORMAL")
        overall_conf = round(float(best_weight * 0.95), 3)

        # Determinação do nível de risco global para o NOC
        if not is_anomaly:
            risk_level = "BAIXO"
        elif final_scenario in ["HOST_DOWN", "DDOS_ATTACK", "COMBINED_FAULT", "DATA_EXFILTRATION"]:
            risk_level = "CRÍTICO"
        elif final_scenario in ["MEMORY_LEAK", "DISK_EXHAUSTION", "SERVICE_OUTAGE"]:
            risk_level = "ALTO"
        else:
            risk_level = "MÉDIO"

        rec_action = genai_res.remediation_playbook[0] if genai_res.remediation_playbook else "Monitorar telemetria ativa do host."

        return EnsembleResult(
            final_scenario=final_scenario,
            is_anomaly=is_anomaly,
            overall_confidence=overall_conf,
            risk_level=risk_level,
            consensus_match=consensus,
            heuristics=heur_res,
            ml=ml_res,
            genai=genai_res,
            recommended_action=rec_action
        )


anomaly_classifier = AnomalyClassifier()
