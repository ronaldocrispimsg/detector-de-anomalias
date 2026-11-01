"""
Módulo de Simulação de Anomalias de Sistema para o NetSpot.
Gera vetores de métricas realistas (ICMP, TCP, HTTP, CPU, RAM, Disco, Banda)
para cenários operacionais normais e anômalos.
"""

import random
import math
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class SystemMetricsSample(BaseModel):
    scenario: str = Field(description="Nome do cenário simulado")
    timestamp: float = Field(description="Timestamp UNIX da coleta")
    latency_ms: float = Field(description="Latência ICMP em milissegundos")
    packet_loss_pct: float = Field(description="Taxa de perda de pacotes em %")
    jitter_ms: float = Field(description="Variação de latência em milissegundos")
    cpu_usage_pct: float = Field(description="Uso de CPU em %")
    ram_usage_pct: float = Field(description="Uso de RAM em %")
    disk_usage_pct: float = Field(description="Uso de Disco em %")
    network_in_bps: float = Field(description="Tráfego de entrada em Bytes/s")
    network_out_bps: float = Field(description="Tráfego de saída em Bytes/s")
    http_status_code: int = Field(description="Código HTTP retornado (ex: 200, 500, 503, 0)")
    http_response_time_ms: float = Field(description="Tempo de resposta HTTP em ms")
    tcp_port_open: bool = Field(description="Indica se porta de serviço principal respondeu")
    active_connections: int = Field(description="Número de conexões TCP ativas")


SCENARIOS_META = {
    "NORMAL": {
        "title": "Operação Normal",
        "description": "Infraestrutura saudável com métricas dentro dos parâmetros ideais de desempenho e SLA.",
        "category": "SAUDÁVEL"
    },
    "DDOS_ATTACK": {
        "title": "Ataque Volumétrico (DDoS)",
        "description": "Inundação massiva de pacotes provocando alta perda de pacotes, saturação da banda de entrada e colapso de latência.",
        "category": "SEGURANÇA / REDE"
    },
    "PORT_SCAN": {
        "title": "Varredura de Portas (Port Scan)",
        "description": "Sonda sequencial/aleatória de portas TCP ativas com picos de conexões e instabilidade leve ICMP.",
        "category": "SEGURANÇA"
    },
    "HOST_DOWN": {
        "title": "Host Inacessível (Host Down)",
        "description": "Queda total da máquina/ativo. 100% perda ICMP, recusa de conexões TCP e tempo limite zerado.",
        "category": "DISPONIBILIDADE"
    },
    "MEMORY_LEAK": {
        "title": "Vazamento de Memória (Memory Leak)",
        "description": "Crescimento contínuo e descontrolado da memória RAM (>95%) acumulando paginação em disco.",
        "category": "RECURSOS"
    },
    "DATA_EXFILTRATION": {
        "title": "Exfiltração de Dados (Data Exfiltration)",
        "description": "Tráfego anormal de saída de rede muito superior ao de entrada (ex: upload massivo suspeito).",
        "category": "SEGURANÇA"
    },
    "DISK_EXHAUSTION": {
        "title": "Esgotamento de Disco (Disk Full)",
        "description": "Espaço de armazenamento esgotado (>98%) travando escrita de logs e operações de sistema.",
        "category": "RECURSOS"
    },
    "SERVICE_OUTAGE": {
        "title": "Falha de Aplicação (Service Outage)",
        "description": "Rede e servidor acessíveis, porém serviço Web/API retornando erros HTTP 500/503 ou porta TCP fechada.",
        "category": "APLICAÇÃO"
    },
    "COMBINED_FAULT": {
        "title": "Falha Múltipla Combinada",
        "description": "Efeito dominó simultâneo em CPU, RAM, Latência de Rede e Erro na Aplicação.",
        "category": "CRÍTICO"
    },
    "NETWORK_CONGESTION": {
        "title": "Congestionamento de Rede",
        "description": "Degradação grave da rota com alta latência, elevado jitter e perda moderada de pacotes.",
        "category": "REDE"
    },
    "CUSTOM": {
        "title": "Cenário Personalizado (Custom)",
        "description": "Métricas configuradas sob medida com sliders interativos para testes de hipóteses.",
        "category": "PERSONALIZADO"
    }
}


class AnomalySimulator:
    """Gerador estocástico de métricas simuladas de sistema e rede."""

    @staticmethod
    def _clamp(value: float, min_val: float, max_val: float) -> float:
        return max(min_val, min(max_val, value))

    def _scenario_overrides(self, scenario: str, r: random.Random):
        """Valores anômalos do cenário (severidade 1.0) e categóricos.

        Separa o "quanto" (valores anômalos) do "grau" (severidade), permitindo
        gerar regimes distintos sem alterar a semântica do fenômeno. Em
        severidade 1.0 o resultado coincide com a geração original.
        """
        numeric: Dict[str, float] = {}
        categorical: Dict[str, Any] = {}

        if scenario == "DDOS_ATTACK":
            numeric.update(
                latency_ms=r.gauss(280.0, 40.0),
                packet_loss_pct=r.gauss(38.0, 8.0),
                jitter_ms=r.gauss(85.0, 20.0),
                cpu_usage_pct=r.gauss(92.0, 5.0),
                network_in_bps=r.gauss(500_000_000, 50_000_000),
                network_out_bps=r.gauss(15_000_000, 3_000_000),
                http_response_time_ms=r.gauss(4500.0, 800.0),
                active_connections=int(r.gauss(3800, 400)),
            )
            categorical["http_status_code"] = r.choice([503, 504, 200])
            if r.random() > 0.4:
                categorical["tcp_port_open"] = False

        elif scenario == "PORT_SCAN":
            numeric.update(
                latency_ms=r.gauss(35.0, 10.0),
                packet_loss_pct=r.gauss(4.0, 2.0),
                jitter_ms=r.gauss(12.0, 4.0),
                cpu_usage_pct=r.gauss(55.0, 10.0),
                active_connections=int(r.gauss(1200, 250)),
                network_in_bps=r.gauss(12_000_000, 2_000_000),
            )

        elif scenario == "HOST_DOWN":
            numeric.update(
                latency_ms=0.0,
                packet_loss_pct=100.0,
                jitter_ms=0.0,
                cpu_usage_pct=0.0,
                ram_usage_pct=0.0,
                disk_usage_pct=0.0,
                network_in_bps=0.0,
                network_out_bps=0.0,
                http_response_time_ms=0.0,
                active_connections=0,
            )
            categorical.update(http_status_code=0, tcp_port_open=False)

        elif scenario == "MEMORY_LEAK":
            numeric.update(
                ram_usage_pct=r.gauss(97.5, 1.5),
                cpu_usage_pct=r.gauss(78.0, 8.0),
                latency_ms=r.gauss(45.0, 10.0),
                disk_usage_pct=r.gauss(65.0, 5.0),
                http_response_time_ms=r.gauss(1800.0, 300.0),
            )

        elif scenario == "DATA_EXFILTRATION":
            numeric.update(
                network_in_bps=r.gauss(2_000_000, 400_000),
                network_out_bps=r.gauss(350_000_000, 40_000_000),
                active_connections=int(r.gauss(450, 80)),
                cpu_usage_pct=r.gauss(68.0, 7.0),
            )

        elif scenario == "DISK_EXHAUSTION":
            numeric.update(
                disk_usage_pct=r.gauss(98.8, 0.8),
                cpu_usage_pct=r.gauss(65.0, 12.0),
                http_response_time_ms=r.gauss(2200.0, 500.0),
            )
            categorical["http_status_code"] = r.choice([500, 200])

        elif scenario == "SERVICE_OUTAGE":
            numeric.update(
                http_response_time_ms=r.gauss(3500.0, 600.0),
                latency_ms=r.gauss(18.0, 4.0),
            )
            categorical["http_status_code"] = r.choice([500, 502, 503])
            categorical["tcp_port_open"] = r.choice([True, False])

        elif scenario == "COMBINED_FAULT":
            numeric.update(
                cpu_usage_pct=r.gauss(96.0, 1.5),
                ram_usage_pct=r.gauss(95.0, 1.5),
                disk_usage_pct=r.gauss(94.0, 1.5),
                latency_ms=r.gauss(320.0, 40.0),
                packet_loss_pct=r.gauss(25.0, 4.0),
                jitter_ms=r.gauss(75.0, 10.0),
                http_response_time_ms=r.gauss(5000.0, 500.0),
            )
            categorical.update(http_status_code=503, tcp_port_open=False)

        elif scenario == "NETWORK_CONGESTION":
            numeric.update(
                latency_ms=r.gauss(210.0, 35.0),
                packet_loss_pct=r.gauss(16.0, 4.0),
                jitter_ms=r.gauss(65.0, 12.0),
                http_response_time_ms=r.gauss(1400.0, 250.0),
            )

        return numeric, categorical

    def generate_sample(
        self,
        scenario: str = "NORMAL",
        timestamp: Optional[float] = None,
        custom_params: Optional[Dict[str, Any]] = None,
        *,
        severity: float = 1.0,
        rng: Optional[Any] = None,
    ) -> SystemMetricsSample:
        """Gera uma amostra do cenário.

        `severity` interpola linearmente entre o estado saudável (0.0) e o
        fenômeno pleno (1.0) para as métricas numéricas do cenário. O padrão
        (1.0) reproduz a geração original. `rng` permite uma fonte de
        aleatoriedade semeada para reprodutibilidade; por padrão usa o módulo
        global `random`.
        """
        scenario = scenario.upper()
        if scenario not in SCENARIOS_META:
            scenario = "NORMAL"

        r = rng if rng is not None else random
        severity = float(severity)
        import time
        ts = timestamp if timestamp is not None else time.time()
        c_params = custom_params or {}

        # Valores base saudáveis
        values: Dict[str, float] = {
            "latency_ms": r.gauss(15.0, 3.0),
            "packet_loss_pct": max(0.0, r.gauss(0.2, 0.1)) if r.random() > 0.85 else 0.0,
            "jitter_ms": r.gauss(2.0, 0.5),
            "cpu_usage_pct": r.gauss(28.0, 8.0),
            "ram_usage_pct": r.gauss(45.0, 5.0),
            "disk_usage_pct": r.gauss(40.0, 2.0),
            "network_in_bps": r.gauss(5_000_000, 1_000_000),
            "network_out_bps": r.gauss(2_000_000, 500_000),
            "http_response_time_ms": r.gauss(120.0, 20.0),
            "active_connections": int(r.gauss(45, 10)),
        }
        final_cat: Dict[str, Any] = {"http_status_code": 200, "tcp_port_open": True}

        numeric, categorical = self._scenario_overrides(scenario, r)
        if severity > 0.0:
            for key, anomalous in numeric.items():
                values[key] = values[key] + severity * (anomalous - values[key])
            for key, anomalous in categorical.items():
                final_cat[key] = anomalous

        latency = values["latency_ms"]
        packet_loss = values["packet_loss_pct"]
        jitter = values["jitter_ms"]
        cpu = values["cpu_usage_pct"]
        ram = values["ram_usage_pct"]
        disk = values["disk_usage_pct"]
        net_in = values["network_in_bps"]
        net_out = values["network_out_bps"]
        http_resp = values["http_response_time_ms"]
        active_conn = values["active_connections"]
        http_code = final_cat["http_status_code"]
        tcp_open = final_cat["tcp_port_open"]

        # Aplicar parâmetros customizados se informados
        if "latency_ms" in c_params:
            latency = float(c_params["latency_ms"])
        if "packet_loss_pct" in c_params:
            packet_loss = float(c_params["packet_loss_pct"])
        if "jitter_ms" in c_params:
            jitter = float(c_params["jitter_ms"])
        if "cpu_usage_pct" in c_params:
            cpu = float(c_params["cpu_usage_pct"])
        if "ram_usage_pct" in c_params:
            ram = float(c_params["ram_usage_pct"])
        if "disk_usage_pct" in c_params:
            disk = float(c_params["disk_usage_pct"])
        if "network_in_bps" in c_params:
            net_in = float(c_params["network_in_bps"])
        if "network_out_bps" in c_params:
            net_out = float(c_params["network_out_bps"])
        if "http_status_code" in c_params:
            http_code = int(c_params["http_status_code"])
        if "http_response_time_ms" in c_params:
            http_resp = float(c_params["http_response_time_ms"])
        if "tcp_port_open" in c_params:
            tcp_open = bool(c_params["tcp_port_open"])
        if "active_connections" in c_params:
            active_conn = int(c_params["active_connections"])

        return SystemMetricsSample(
            scenario=scenario,
            timestamp=ts,
            latency_ms=round(self._clamp(latency, 0.0, 10000.0), 2),
            packet_loss_pct=round(self._clamp(packet_loss, 0.0, 100.0), 2),
            jitter_ms=round(self._clamp(jitter, 0.0, 2000.0), 2),
            cpu_usage_pct=round(self._clamp(cpu, 0.0, 100.0), 2),
            ram_usage_pct=round(self._clamp(ram, 0.0, 100.0), 2),
            disk_usage_pct=round(self._clamp(disk, 0.0, 100.0), 2),
            network_in_bps=round(max(0.0, net_in), 2),
            network_out_bps=round(max(0.0, net_out), 2),
            http_status_code=http_code,
            http_response_time_ms=round(max(0.0, http_resp), 2),
            tcp_port_open=tcp_open,
            active_connections=max(0, int(active_conn))
        )

    def generate_batch(
        self,
        scenario: str = "NORMAL",
        count: int = 50,
        *,
        severity: float = 1.0,
        rng: Optional[Any] = None,
    ) -> List[SystemMetricsSample]:
        samples = []
        import time
        base_ts = time.time() - (count * 10)
        for i in range(count):
            samples.append(
                self.generate_sample(
                    scenario=scenario,
                    timestamp=base_ts + (i * 10),
                    severity=severity,
                    rng=rng,
                )
            )
        return samples


anomaly_simulator = AnomalySimulator()
