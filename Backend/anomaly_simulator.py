import random
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from Backend.models import Host, CheckResult, SNMPMetric, Alert
from Backend.metrics import (
    compute_health,
    calc_sla_rolling_ping,
    calc_jitter_ping,
    calc_sla_rolling_tcp_ports,
    calc_jitter_tcp_ports,
    calc_sla_rolling_http,
    calc_jitter_http,
    calc_latency_trend_ping,
    classify_trend,
    calc_latency_trend_http,
    classify_trend_http,
    refine_severity,
)

logger = logging.getLogger("noc_lite.anomaly_simulator")

# Dicionário global para guardar o estado das simulações em tempo real
# Formato: {host_id: {"anomaly_type": str, "expires_at": datetime}}
ACTIVE_SIMULATIONS = {}

def start_simulation(host_id: int, anomaly_type: str, duration_seconds: int = 300) -> dict:
    """
    Inicia uma simulação de anomalia em tempo real para um determinado host.
    """
    expires_at = datetime.utcnow() + timedelta(seconds=duration_seconds)
    ACTIVE_SIMULATIONS[host_id] = {
        "anomaly_type": anomaly_type,
        "expires_at": expires_at,
        "started_at": datetime.utcnow()
    }
    logger.info(f"Simulação de anomalia '{anomaly_type}' iniciada para host ID={host_id} por {duration_seconds}s.")
    return ACTIVE_SIMULATIONS[host_id]

def stop_simulation(host_id: int) -> bool:
    """
    Interrompe a simulação ativa de um host.
    """
    if host_id in ACTIVE_SIMULATIONS:
        del ACTIVE_SIMULATIONS[host_id]
        logger.info(f"Simulação de anomalia encerrada para host ID={host_id}.")
        return True
    return False

def get_active_simulation(host_id: int) -> dict | None:
    """
    Retorna a simulação ativa se ela existir e não estiver expirada.
    """
    sim = ACTIVE_SIMULATIONS.get(host_id)
    if sim:
        if datetime.utcnow() > sim["expires_at"]:
            del ACTIVE_SIMULATIONS[host_id]
            logger.info(f"Simulação de anomalia expirou para host ID={host_id}.")
            return None
        return sim
    return None

def generate_simulated_metrics(anomaly_type: str, timestamp: datetime = None) -> dict:
    """
    Gera dados brutos de métricas baseados no tipo de anomalia para um instante específico.
    Tipos de anomalia suportados:
      - 'NORMAL'
      - 'DDOS_ATTACK'
      - 'PORT_SCAN'
      - 'HOST_DOWN'
      - 'DATA_EXFILTRATION'
      - 'NETWORK_CONGESTION'
    """
    if timestamp is None:
        timestamp = datetime.utcnow()

    # Padrão normal
    ping_success = True
    ping_latency = random.uniform(3.0, 10.0)
    tcp_success = True
    tcp_latency = random.uniform(4.0, 12.0)
    http_success = True
    http_latency = random.uniform(10.0, 25.0)
    http_status_code = 200

    cpu = random.uniform(5.0, 25.0)
    ram = random.uniform(30.0, 45.0)
    disk = random.uniform(50.0, 55.0)
    network_in = random.uniform(500_000.0, 2_000_000.0)    # 0.5 - 2 Mbps
    network_out = random.uniform(200_000.0, 1_000_000.0)   # 0.2 - 1 Mbps

    extra_tcp_checks = []

    if anomaly_type == "DDOS_ATTACK":
        # Sobrecarga de tráfego de entrada e CPU
        cpu = random.uniform(85.0, 99.0)
        ram = random.uniform(65.0, 80.0)
        network_in = random.uniform(80_000_000.0, 120_000_000.0) # 80 - 120 Mbps (DDoS)
        network_out = random.uniform(1_500_000.0, 4_000_000.0)
        
        # Latências sobem devido à carga
        ping_latency = random.uniform(15.0, 45.0)
        tcp_latency = random.uniform(30.0, 80.0)
        http_latency = random.uniform(80.0, 250.0)

    elif anomaly_type == "PORT_SCAN":
        # Muitas tentativas de conexões falhas, tráfego baixo
        cpu = random.uniform(15.0, 30.0)
        network_in = random.uniform(100_000.0, 500_000.0)  # Muito tráfego de controle pequeno
        network_out = random.uniform(50_000.0, 250_000.0)
        
        ping_latency = random.uniform(4.0, 12.0)
        tcp_success = False  # O check TCP primário falha ou varia
        tcp_latency = None
        
        # Simula varredura em 5 portas extras com falha
        for port in [21, 22, 23, 25, 443]:
            extra_tcp_checks.append({
                "port": port,
                "success": False,
                "latency": None,
                "error": "Connection refused"
            })

    elif anomaly_type == "HOST_DOWN":
        # Tudo cai, telemetria SNMP indisponível (None)
        ping_success = False
        ping_latency = None
        tcp_success = False
        tcp_latency = None
        http_success = False
        http_latency = None
        http_status_code = None
        
        cpu = None
        ram = None
        disk = None
        network_in = None
        network_out = None

    elif anomaly_type == "DATA_EXFILTRATION":
        # Muito tráfego de saída (upload), CPU e outros normais
        cpu = random.uniform(15.0, 35.0)
        network_out = random.uniform(85_000_000.0, 115_000_000.0) # 85 - 115 Mbps (upload massivo)
        network_in = random.uniform(500_000.0, 1_500_000.0)
        
        ping_latency = random.uniform(5.0, 15.0)
        tcp_latency = random.uniform(8.0, 20.0)
        http_latency = random.uniform(20.0, 45.0)

    elif anomaly_type == "NETWORK_CONGESTION":
        # Latência e Jitter nas nuvens, perda de pacotes parcial (25% de chance de falha)
        ping_success = random.random() > 0.25
        ping_latency = random.uniform(150.0, 350.0) if ping_success else None
        
        tcp_success = random.random() > 0.25
        tcp_latency = random.uniform(200.0, 450.0) if tcp_success else None
        
        http_success = random.random() > 0.25
        http_latency = random.uniform(300.0, 650.0) if http_success else None
        http_status_code = 200 if http_success else None
        
        cpu = random.uniform(10.0, 20.0)
        network_in = random.uniform(25_000_000.0, 40_000_000.0)  # Link saturando
        network_out = random.uniform(10_000_000.0, 20_000_000.0)

    return {
        "timestamp": timestamp,
        "ping_success": ping_success,
        "ping_latency": ping_latency,
        "tcp_success": tcp_success,
        "tcp_latency": tcp_latency,
        "http_success": http_success,
        "http_latency": http_latency,
        "http_status_code": http_status_code,
        "cpu": cpu,
        "ram": ram,
        "disk": disk,
        "network_in_bps": network_in,
        "network_out_bps": network_out,
        "extra_tcp_checks": extra_tcp_checks
    }

def run_simulated_check_cycle(host_id: int, anomaly_type: str, db: Session) -> None:
    """
    Executa um ciclo completo de monitoramento simulado para o host_id,
    injetando os dados fictícios coerentes com o tipo de anomalia na base de dados.
    """
    host = db.query(Host).filter(Host.id == host_id).first()
    if not host:
        return

    m = generate_simulated_metrics(anomaly_type)
    ts = m["timestamp"]

    # Atualiza IP fictício e data do check
    host.last_check = ts
    if not host.last_resolved_ip:
        host.last_resolved_ip = "192.168.100.99"

    # Salva o resultado do Ping
    db.add(CheckResult(
        host_id=host.id,
        host_name=host.name,
        check_type="ping",
        success=m["ping_success"],
        latency=m["ping_latency"],
        error=None if m["ping_success"] else "Simulated Ping Loss/Timeout",
        timestamp=ts
    ))

    # Salva o resultado do TCP
    db.add(CheckResult(
        host_id=host.id,
        host_name=host.name,
        check_type="tcp",
        success=m["tcp_success"],
        latency=m["tcp_latency"],
        error=None if m["tcp_success"] else "Simulated Connection Timeout",
        tcp_port=host.port or 80,
        timestamp=ts
    ))

    # Salva portas TCP extras de varreduras
    for extra in m["extra_tcp_checks"]:
        db.add(CheckResult(
            host_id=host.id,
            host_name=host.name,
            check_type="tcp",
            success=extra["success"],
            latency=extra["latency"],
            error=extra["error"],
            tcp_port=extra["port"],
            timestamp=ts
        ))

    # Salva o resultado HTTP se aplicável
    if host.http_enabled:
        db.add(CheckResult(
            host_id=host.id,
            host_name=host.name,
            check_type="http",
            success=m["http_success"],
            latency=m["http_latency"],
            error=None if m["http_success"] else "Simulated HTTP Error",
            status_code=m["http_status_code"],
            timestamp=ts
        ))

    # Atualiza as propriedades do host
    host.latency_ping = m["ping_latency"]
    host.latency_tcp = m["tcp_latency"]
    
    if host.http_enabled:
        host.http_latency = m["http_latency"]
        host.last_http_protocol = host.last_http_protocol or "HTTP"

    # Atualiza SNMP se habilitado ou simulável
    if m["cpu"] is not None:
        host.cpu_usage = m["cpu"]
        host.ram_usage = m["ram"]
        host.disk_usage = m["disk"]
        host.network_in_bps = m["network_in_bps"]
        host.network_out_bps = m["network_out_bps"]
        host.last_snmp_check = ts

        # Insere histórico SNMP
        db.add(SNMPMetric(
            host_id=host.id,
            cpu=m["cpu"],
            ram=m["ram"],
            disk=m["disk"],
            network_in_bps=m["network_in_bps"],
            network_out_bps=m["network_out_bps"],
            network_total_bps=m["network_in_bps"] + m["network_out_bps"],
            timestamp=ts
        ))
    else:
        # Se for HOST_DOWN
        host.cpu_usage = None
        host.ram_usage = None
        host.disk_usage = None
        host.network_in_bps = None
        host.network_out_bps = None

    # Recalcula as estatísticas do NOC Lite (SLA, Jitter, Tendências)
    db.flush()
    host.sla_rolling_ping = calc_sla_rolling_ping(db, host.id, 50)
    host.jitter_ms_ping = calc_jitter_ping(db, host.id, 10)

    active_tcp_ports = []
    if host.port:
        active_tcp_ports.append(host.port)
    host.sla_rolling_tcp = calc_sla_rolling_tcp_ports(db, host.id, active_tcp_ports, 50)
    host.jitter_ms_tcp = calc_jitter_tcp_ports(db, host.id, active_tcp_ports, 10)

    host.sla_rolling_http = calc_sla_rolling_http(db, host.id, 50)
    host.jitter_ms_http = calc_jitter_http(db, host.id, 10)

    host.slope = calc_latency_trend_ping(db, host.id, 10)
    host.trend = classify_trend(host.slope)

    host.slope_http = calc_latency_trend_http(db, host.id, 10)
    host.trend_http = classify_trend_http(host.slope_http)

    # Determina e atualiza severidade e status de forma clássica
    ping_res = {"success": m["ping_success"], "latency": m["ping_latency"]}
    tcp_res = {"success": m["tcp_success"], "latency": m["tcp_latency"]}
    http_res = {"success": m["http_success"], "latency": m["http_latency"]} if host.http_enabled else None
    
    score, severity = compute_health(ping_res, tcp_res, http_res)
    host.health_score = score
    host.severity = severity

    # Define o status operacional do Host
    if not m["ping_success"] and not m["tcp_success"] and (not http_res or not http_res["success"]):
        host.status = "DOWN"
        host.fail_streak = (host.fail_streak or 0) + 1
        host.success_streak = 0
    elif not m["ping_success"] or not m["tcp_success"] or (http_res and not http_res["success"]):
        host.status = "DEGRADED"
        host.fail_streak = (host.fail_streak or 0) + 1
        host.success_streak = 0
    else:
        host.status = "UP"
        host.success_streak = (host.success_streak or 0) + 1
        host.fail_streak = 0

    host.baseline_pending = False
    
    # Commit das alterações simuladas
    db.commit()
    logger.debug(f"Ciclo de check simulado concluído para host={host.name} com cenário={anomaly_type}")

def generate_historical_data(host_id: int, anomaly_type: str, records: int = 150) -> None:
    """
    Gera histórico retroativo (ex: registros a cada 20 segundos) para popular
    a base de dados com cenários de anomalia prontos para treinamento e visualização.
    """
    db: Session = SessionLocal()
    try:
        host = db.query(Host).filter(Host.id == host_id).first()
        if not host:
            logger.warning(f"Host ID={host_id} não encontrado para gerar histórico.")
            return

        base_time = datetime.utcnow()
        logger.info(f"Gerando {records} registros históricos de '{anomaly_type}' para host {host.name}...")
        
        # Adiciona registros em lote retroativos
        for i in range(records, 0, -1):
            time_offset = base_time - timedelta(seconds=i * 20)
            m = generate_simulated_metrics(anomaly_type, timestamp=time_offset)
            ts = m["timestamp"]

            # Insere CheckResult de Ping
            db.add(CheckResult(
                host_id=host.id,
                host_name=host.name,
                check_type="ping",
                success=m["ping_success"],
                latency=m["ping_latency"],
                error=None if m["ping_success"] else "Historical Simulated Ping Loss",
                timestamp=ts
            ))

            # Insere CheckResult de TCP
            db.add(CheckResult(
                host_id=host.id,
                host_name=host.name,
                check_type="tcp",
                success=m["tcp_success"],
                latency=m["tcp_latency"],
                error=None if m["tcp_success"] else "Historical Simulated TCP Timeout",
                tcp_port=host.port or 80,
                timestamp=ts
            ))

            for extra in m["extra_tcp_checks"]:
                db.add(CheckResult(
                    host_id=host.id,
                    host_name=host.name,
                    check_type="tcp",
                    success=extra["success"],
                    latency=extra["latency"],
                    error=extra["error"],
                    tcp_port=extra["port"],
                    timestamp=ts
                ))

            # Insere CheckResult de HTTP
            if host.http_enabled:
                db.add(CheckResult(
                    host_id=host.id,
                    host_name=host.name,
                    check_type="http",
                    success=m["http_success"],
                    latency=m["http_latency"],
                    error=None if m["http_success"] else "Historical Simulated HTTP Loss",
                    status_code=m["http_status_code"],
                    timestamp=ts
                ))

            # Insere SNMPMetric
            if m["cpu"] is not None:
                db.add(SNMPMetric(
                    host_id=host.id,
                    cpu=m["cpu"],
                    ram=m["ram"],
                    disk=m["disk"],
                    network_in_bps=m["network_in_bps"],
                    network_out_bps=m["network_out_bps"],
                    network_total_bps=m["network_in_bps"] + m["network_out_bps"],
                    timestamp=ts
                ))
        
        # Garante que o estado final do host reflita o último ciclo da simulação histórica
        db.commit()
        run_simulated_check_cycle(host_id, anomaly_type, db)
        logger.info(f"Histórico de '{anomaly_type}' para host {host.name} gerado com sucesso!")
    except Exception:
        logger.exception(f"Erro ao gerar histórico de anomalias para host ID={host_id}")
        db.rollback()
    finally:
        db.close()
