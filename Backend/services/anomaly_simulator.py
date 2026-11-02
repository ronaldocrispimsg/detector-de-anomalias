"""
Módulo Avançado de Simulação de Anomalias de Sistema e Rede para o NetSpot.
Gera vetores estocásticos realistas de telemetria (ICMP, TCP, HTTP, CPU, RAM, Disco e Vazão de Rede)
com suporte a coerência física de rede, não-linearidades, ajuste contínuo de severidade e séries temporais.
"""

import math
import random
import time
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
    """Gerador estocástico avançado de telemetria com coerência física de redes e sistemas."""

    @staticmethod
    def _clamp(value: float, min_val: float, max_val: float) -> float:
        return max(min_val, min(max_val, value))

    def _scenario_overrides(self, scenario: str, r: random.Random):
        """Calcula parâmetros de sobreposição com ruídos correlacionados de engenharia."""
        numeric: Dict[str, float] = {}
        categorical: Dict[str, Any] = {}

        if scenario == "DDOS_ATTACK":
            # Inundação SYN/UDP: banda de entrada massiva, conexões concorrentes e colapso de sockets
            base_in = r.gauss(520_000_000, 45_000_000)
            conns = int(r.gauss(4200, 350))
            # Latência e perda acopladas à saturação da fila de interface (Bufferbloat/Tail-drop)
            loss = r.gauss(38.0, 7.0)
            latency = r.gauss(290.0, 35.0) + (loss * 1.5)
            jitter = r.gauss(88.0, 18.0)
            cpu = r.gauss(94.0, 4.0)

            numeric.update(
                latency_ms=latency,
                packet_loss_pct=loss,
                jitter_ms=jitter,
                cpu_usage_pct=cpu,
                network_in_bps=base_in,
                network_out_bps=r.gauss(16_000_000, 3_000_000),
                http_response_time_ms=r.gauss(4600.0, 700.0),
                active_connections=conns,
            )
            categorical["http_status_code"] = r.choice([503, 504, 502])
            categorical["tcp_port_open"] = r.random() > 0.35

        elif scenario == "PORT_SCAN":
            # Varredura TCP SYN/FIN rápida: picos curtos de sockets com tráfego volumétrico baixo
            conns = int(r.gauss(1350, 220))
            numeric.update(
                latency_ms=r.gauss(36.0, 8.0),
                packet_loss_pct=r.gauss(3.5, 1.5),
                jitter_ms=r.gauss(14.0, 3.5),
                cpu_usage_pct=r.gauss(58.0, 8.0),
                active_connections=conns,
                network_in_bps=r.gauss(14_000_000, 2_500_000),
                network_out_bps=r.gauss(3_500_000, 800_000),
                http_response_time_ms=r.gauss(180.0, 35.0),
            )
            categorical["http_status_code"] = 200
            categorical["tcp_port_open"] = True

        elif scenario == "HOST_DOWN":
            # Parada total do host/interface
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
            # Exaustão de RAM acumulando swap/pressão no kernel (high minor page faults)
            ram = r.gauss(97.8, 1.2)
            cpu = r.gauss(76.0, 7.0)
            # Atraso na resposta HTTP por retenção de GC/lock de heap
            http_resp = r.gauss(2100.0, 350.0)
            numeric.update(
                ram_usage_pct=ram,
                cpu_usage_pct=cpu,
                latency_ms=r.gauss(42.0, 8.0),
                disk_usage_pct=r.gauss(68.0, 4.0),
                http_response_time_ms=http_resp,
            )
            categorical["http_status_code"] = 200 if r.random() > 0.3 else 500
            categorical["tcp_port_open"] = True

        elif scenario == "DATA_EXFILTRATION":
            # Upload não autorizado assimétrico (outbound >> inbound)
            outbound = r.gauss(380_000_000, 35_000_000)
            inbound = r.gauss(2_200_000, 400_000)
            numeric.update(
                network_in_bps=inbound,
                network_out_bps=outbound,
                active_connections=int(r.gauss(480, 60)),
                cpu_usage_pct=r.gauss(69.0, 6.0),
                latency_ms=r.gauss(38.0, 6.0),
            )
            categorical["http_status_code"] = 200
            categorical["tcp_port_open"] = True

        elif scenario == "DISK_EXHAUSTION":
            # Volume montado em 99% impedindo log/WAL write
            numeric.update(
                disk_usage_pct=r.gauss(98.8, 0.8),
                cpu_usage_pct=r.gauss(66.0, 6.0),
                http_response_time_ms=r.gauss(2400.0, 400.0),
            )
            categorical["http_status_code"] = r.choice([500, 503])
            categorical["tcp_port_open"] = True

        elif scenario == "SERVICE_OUTAGE":
            # Aplicação web/daemon em crash enquanto camada de rede opera regular
            numeric.update(
                latency_ms=r.gauss(18.0, 3.0),
                jitter_ms=r.gauss(2.5, 0.8),
                packet_loss_pct=0.0,
                cpu_usage_pct=r.gauss(32.0, 6.0),
                http_response_time_ms=r.gauss(3800.0, 600.0),
            )
            categorical["http_status_code"] = r.choice([500, 502, 503])
            categorical["tcp_port_open"] = r.random() > 0.5

        elif scenario == "COMBINED_FAULT":
            # Colapso multinível em cascata (recursos + rede + aplicação)
            numeric.update(
                cpu_usage_pct=r.gauss(96.5, 2.5),
                ram_usage_pct=r.gauss(95.5, 2.5),
                disk_usage_pct=r.gauss(94.0, 3.0),
                latency_ms=r.gauss(340.0, 40.0),
                packet_loss_pct=r.gauss(28.0, 5.0),
                jitter_ms=r.gauss(90.0, 15.0),
                http_response_time_ms=r.gauss(5200.0, 700.0),
                active_connections=int(r.gauss(2900, 300)),
            )
            categorical["http_status_code"] = 503
            categorical["tcp_port_open"] = False

        elif scenario == "NETWORK_CONGESTION":
            # Saturação de link/rota intermediária (alta latência e jitter sem estresse de hardware)
            lat = r.gauss(220.0, 30.0)
            jit = r.gauss(65.0, 14.0)
            numeric.update(
                latency_ms=lat,
                jitter_ms=jit,
                packet_loss_pct=r.gauss(18.0, 4.0),
                http_response_time_ms=lat * 4.5,
                cpu_usage_pct=r.gauss(34.0, 7.0),
                ram_usage_pct=r.gauss(46.0, 5.0),
            )
            categorical["http_status_code"] = 200
            categorical["tcp_port_open"] = True

        return numeric, categorical

    def generate_sample(
        self,
        scenario: str = "NORMAL",
        timestamp: Optional[float] = None,
        custom_params: Optional[Dict[str, Any]] = None,
        *,
        severity: float = 1.0,
        noise_scale: float = 1.0,
        rng: Optional[Any] = None,
    ) -> SystemMetricsSample:
        """
        Gera uma amostra de telemetria estocástica coerente.
        
        Args:
            scenario: Identificador do cenário catalogado.
            timestamp: Timestamp UNIX de coleta.
            custom_params: Sobrescrita explícita de métricas.
            severity: Fator contínuo de severidade (0.0=saudável, 1.0=pleno, >1.0=catastrófico).
            noise_scale: Multiplicador de dispersão estocástica (ruído).
            rng: Instância opcional de gerador pseudo-aleatório semeado.
        """
        scenario = scenario.upper()
        if scenario not in SCENARIOS_META:
            scenario = "NORMAL"

        r = rng if rng is not None else random
        severity = max(0.0, float(severity))
        ts = timestamp if timestamp is not None else time.time()
        c_params = custom_params or {}
        n_scale = max(0.1, float(noise_scale))

        # Baseline operacional de ambiente de produção saudável
        values: Dict[str, float] = {
            "latency_ms": r.gauss(15.0, 2.5 * n_scale),
            "packet_loss_pct": max(0.0, r.gauss(0.15, 0.08 * n_scale)) if r.random() > 0.88 else 0.0,
            "jitter_ms": r.gauss(2.0, 0.4 * n_scale),
            "cpu_usage_pct": r.gauss(27.0, 6.0 * n_scale),
            "ram_usage_pct": r.gauss(44.0, 4.0 * n_scale),
            "disk_usage_pct": r.gauss(39.0, 1.8 * n_scale),
            "network_in_bps": r.gauss(5_200_000, 800_000 * n_scale),
            "network_out_bps": r.gauss(2_100_000, 400_000 * n_scale),
            "http_response_time_ms": r.gauss(115.0, 18.0 * n_scale),
            "active_connections": int(r.gauss(48, 8 * n_scale)),
        }
        final_cat: Dict[str, Any] = {"http_status_code": 200, "tcp_port_open": True}

        numeric, categorical = self._scenario_overrides(scenario, r)
        if severity > 0.0:
            for key, anomalous in numeric.items():
                values[key] = values[key] + severity * (anomalous - values[key])
            for key, anomalous in categorical.items():
                final_cat[key] = anomalous

        # Coerência física entre métricas acopladas
        if values["packet_loss_pct"] > 50.0 and scenario != "HOST_DOWN":
            # Alta perda de pacotes gera retentativas TCP e elevação não linear do tempo de resposta
            values["http_response_time_ms"] *= (1.0 + (values["packet_loss_pct"] / 100.0) * 2.0)
            values["jitter_ms"] = max(values["jitter_ms"], values["latency_ms"] * 0.3)

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

        # Aplicação de sobrescritas manuais (Cenário CUSTOM ou tuning)
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

        # Clamping de segurança para valores válidos de engenharia
        return SystemMetricsSample(
            scenario=scenario,
            timestamp=ts,
            latency_ms=round(self._clamp(latency, 0.0, 5000.0), 2),
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
        noise_scale: float = 1.0,
        rng: Optional[Any] = None,
    ) -> List[SystemMetricsSample]:
        """Gera um lote de amostras do cenário selecionado."""
        samples = []
        base_ts = time.time() - (count * 10)
        for i in range(count):
            samples.append(
                self.generate_sample(
                    scenario=scenario,
                    timestamp=base_ts + (i * 10),
                    severity=severity,
                    noise_scale=noise_scale,
                    rng=rng,
                )
            )
        return samples

    def generate_time_series(
        self,
        scenario: str,
        steps: int = 30,
        interval_seconds: float = 10.0,
        onset_step: int = 10,
        target_severity: float = 1.0,
    ) -> List[SystemMetricsSample]:
        """
        Gera uma série temporal contínua simulando a incubação e eclosão de um incidente.
        
        Args:
            scenario: Cenário de anomalia a eclodir.
            steps: Quantidade total de pontos de telemetria.
            interval_seconds: Delta de tempo entre amostras.
            onset_step: Ponto de início da anomalia (antes opera em regime NORMAL).
            target_severity: Severidade máxima atingida no pico da falha.
        """
        series = []
        start_ts = time.time() - (steps * interval_seconds)

        for step in range(steps):
            cur_ts = start_ts + (step * interval_seconds)
            if step < onset_step:
                # Regime pré-incidente (saudável)
                sample = self.generate_sample(scenario="NORMAL", timestamp=cur_ts)
            else:
                # Rampa progressiva de severidade
                progress = (step - onset_step + 1) / max(1, (steps - onset_step))
                cur_severity = progress * target_severity
                sample = self.generate_sample(
                    scenario=scenario,
                    timestamp=cur_ts,
                    severity=cur_severity
                )
            series.append(sample)

        return series


anomaly_simulator = AnomalySimulator()
