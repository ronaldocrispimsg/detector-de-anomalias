from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from Backend.models import CheckResult, Incident

PING_WORSENING_TRENDS = ("DEGRADING", "FAST_DEGRADING")
HTTP_WORSENING_TRENDS = ("DEGRADING", "CRITICAL")
# Amostras mínimas para considerar o SLA móvel confiável (evita falso alerta no início do monitoramento)
MIN_SLA_SAMPLES = 5


def compute_health(ping_result, tcp_result, http_result):
    icmp_blocked_like = (
        not ping_result["success"] and (
            (tcp_result is not None and tcp_result.get("success")) or
            (http_result is not None and http_result.get("success"))
        )
    )

    ping_effective_success = ping_result["success"] or icmp_blocked_like
    ping_effective_latency = ping_result.get("latency")
    if ping_effective_latency is None and icmp_blocked_like:
        # Não há RTT ICMP real quando firewall bloqueia; usa valor neutro para não penalizar saúde.
        ping_effective_latency = 80

    raw_score = 0.0
    max_score = 0.0

    # ---------- 1. Ping ----------
    max_score += 45.0
    if ping_effective_success:
        raw_score += 30.0
        lat = ping_effective_latency if ping_effective_latency is not None else 9999
        if lat < 100:
            raw_score += 15.0
        elif lat < 300:
            raw_score += 8.0

    # ---------- 2. TCP (se configurado) ----------
    if tcp_result is not None:
        max_score += 30.0
        if tcp_result.get("success"):
            raw_score += 30.0

    # ---------- 3. HTTP (se configurado) ----------
    if http_result is not None:
        max_score += 35.0
        status_code = http_result.get("status_code")

        if http_result.get("success"):
            raw_score += 25.0
            http_lat = http_result.get("latency")
            if http_lat is not None and http_lat < 500:
                raw_score += 10.0
        elif status_code and 500 <= status_code < 600:
            raw_score -= 20.0
        elif status_code and 400 <= status_code < 500:
            raw_score -= 10.0

    if max_score > 0:
        normalized = (raw_score / max_score) * 100.0
    else:
        normalized = 0.0

    score = int(round(max(0.0, min(100.0, normalized))))

    # ---------- Severidade ----------
    if score >= 85:
        severity = "HEALTHY"
    elif score >= 65:
        severity = "WARNING"
    elif score >= 40:
        severity = "DEGRADED"
    else:
        severity = "CRITICAL"

    return score, severity

def calc_sla_rolling_ping(db, host_id, window=50):
    rows = (
        db.query(CheckResult)
        .filter(CheckResult.host_id == host_id,
                CheckResult.check_type == "ping")
        .order_by(CheckResult.timestamp.desc())
        .limit(window)
        .all()
    )

    if len(rows) < MIN_SLA_SAMPLES:
        return None

    ok = sum(1 for r in rows if r.success)
    return round(ok / len(rows) * 100, 2)

def calc_sla_rolling_tcp(db, host_id, window=50):
    rows = (
        db.query(CheckResult)
        .filter(
            CheckResult.host_id == host_id,
            CheckResult.check_type == "tcp"
        )
        .order_by(CheckResult.timestamp.desc())
        .limit(window)
        .all()
    )

    if len(rows) < MIN_SLA_SAMPLES:
        return None

    ok = sum(1 for r in rows if r.success)
    return round(ok / len(rows) * 100, 2)

def calc_sla_rolling_http(db, host_id, window=50):

    rows = (
        db.query(CheckResult)
        .filter(
            CheckResult.host_id == host_id,
            CheckResult.check_type == "http"
        )
        .order_by(CheckResult.timestamp.desc())
        .limit(window)
        .all()
    )

    if len(rows) < MIN_SLA_SAMPLES:
        return None

    success_count = sum(1 for r in rows if r.success)

    return round((success_count / len(rows)) * 100, 2)

def calc_jitter_ping(db, host_id, window=10):

    rows = (
        db.query(CheckResult)
        .filter(CheckResult.host_id == host_id,
                CheckResult.check_type == "ping",
                CheckResult.latency != None)
        .order_by(CheckResult.timestamp.desc())
        .limit(window)
        .all()
    )

    if len(rows) < 2:
        return None

    values = [r.latency for r in rows]
    values.reverse()

    diffs = [
        abs(values[i] - values[i-1])
        for i in range(1, len(values))
    ]

    return round(sum(diffs)/len(diffs), 2)

def calc_jitter_tcp(db, host_id, window=10):
    rows = (
        db.query(CheckResult)
        .filter(
            CheckResult.host_id == host_id,
            CheckResult.check_type == "tcp",
            CheckResult.latency != None
        )
        .order_by(CheckResult.timestamp.desc())
        .limit(window)
        .all()
    )

    if len(rows) < 2:
        return None

    values = [r.latency for r in rows]
    values.reverse()

    diffs = [
        abs(values[i] - values[i-1])
        for i in range(1, len(values))
    ]

    return round(sum(diffs)/len(diffs), 2)


def calc_sla_rolling_tcp_ports(db, host_id, tcp_ports, window=50):
    ports = [int(p) for p in (tcp_ports or []) if p is not None]
    if not ports:
        return None

    rows = (
        db.query(CheckResult)
        .filter(
            CheckResult.host_id == host_id,
            CheckResult.check_type == "tcp",
            CheckResult.tcp_port.in_(ports),
        )
        .order_by(CheckResult.timestamp.desc())
        .limit(window)
        .all()
    )

    if len(rows) < MIN_SLA_SAMPLES:
        return None

    ok = sum(1 for r in rows if r.success)
    return round(ok / len(rows) * 100, 2)


def calc_jitter_tcp_ports(db, host_id, tcp_ports, window=10):
    ports = [int(p) for p in (tcp_ports or []) if p is not None]
    if not ports:
        return None

    rows = (
        db.query(CheckResult)
        .filter(
            CheckResult.host_id == host_id,
            CheckResult.check_type == "tcp",
            CheckResult.tcp_port.in_(ports),
            CheckResult.latency != None,
        )
        .order_by(CheckResult.timestamp.desc())
        .limit(window)
        .all()
    )

    if len(rows) < 2:
        return None

    values = [r.latency for r in rows]
    values.reverse()
    diffs = [abs(values[i] - values[i - 1]) for i in range(1, len(values))]
    return round(sum(diffs) / len(diffs), 2)

def calc_jitter_http(db, host_id, window=10):

    rows = (
        db.query(CheckResult)
        .filter(
            CheckResult.host_id == host_id,
            CheckResult.check_type == "http",
            CheckResult.success == True,
            CheckResult.latency != None
        )
        .order_by(CheckResult.timestamp.desc())
        .limit(window)
        .all()
    )

    if len(rows) < 3:
        return None

    latencies = [r.latency for r in rows]
    latencies.reverse()

    diffs = [abs(latencies[i] - latencies[i-1]) for i in range(1, len(latencies))]

    return round(sum(diffs) / len(diffs), 2)

def refine_severity(
    base_severity,
    sla_ping=None,
    sla_tcp=None,
    sla_http=None,
    jitter_ping=None,
    jitter_tcp=None,
    jitter_http=None,
    ignore_ping_metrics: bool = False
):
    
    sev = base_severity

    # ---------- SLA pior manda ----------
    sla_ping_effective = None if ignore_ping_metrics else sla_ping
    slas = [s for s in (sla_ping_effective, sla_tcp, sla_http) if s is not None]

    if slas:
        worst_sla = min(slas)

        if worst_sla < 50:
            sev = "CRITICAL"
        elif worst_sla < 75 and sev not in ("CRITICAL",):
            sev = "DEGRADED"
        elif worst_sla < 90 and sev not in ("CRITICAL", "DEGRADED"):
            sev = "WARNING"

    # ---------- Jitter pior manda ----------
    jitter_ping_effective = None if ignore_ping_metrics else jitter_ping
    jitters = [j for j in (jitter_ping_effective, jitter_tcp, jitter_http) if j is not None]

    if jitters:
        worst_jitter = max(jitters)

        if worst_jitter > 400:
            return "CRITICAL"
        elif worst_jitter > 200 and sev not in ("CRITICAL",):
            sev = "DEGRADED"
        elif worst_jitter > 120 and sev not in ("CRITICAL", "DEGRADED"):
            sev = "WARNING"

    return sev

def calc_latency_trend_ping(db, host_id, window=10):

    rows = (
        db.query(CheckResult)
        .filter(
            CheckResult.host_id == host_id,
            CheckResult.check_type == "ping",
            CheckResult.success == True,
            CheckResult.latency != None
        )
        .order_by(CheckResult.timestamp.desc())
        .limit(window)
        .all()
    )

    if len(rows) < 5:
        return None

    values = [r.latency for r in rows]
    values.reverse()

    # slope simples
    x = list(range(len(values)))

    x_mean = sum(x)/len(x)
    y_mean = sum(values)/len(values)

    num = sum((xi-x_mean)*(yi-y_mean) for xi, yi in zip(x, values))
    den = sum((xi-x_mean)**2 for xi in x)

    if den == 0:
        return 0

    slope = num / den

    return round(slope, 2)

def calc_latency_trend_http(db, host_id, window=10):

    rows = (
        db.query(CheckResult)
        .filter(
            CheckResult.host_id == host_id,
            CheckResult.check_type == "http",
            CheckResult.success == True,
            CheckResult.latency != None
        )
        .order_by(CheckResult.timestamp.desc())
        .limit(window)
        .all()
    )

    if len(rows) < 5:
        return None

    values = [r.latency for r in rows]
    values.reverse()

    x = list(range(len(values)))

    x_mean = sum(x) / len(x)
    y_mean = sum(values) / len(values)

    num = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, values))
    den = sum((xi - x_mean) ** 2 for xi in x)

    if den == 0:
        return 0

    return round(num / den, 2)

def classify_trend(slope):

    if slope is None:
        return "UNKNOWN"

    if slope > 40:
        return "FAST_DEGRADING"

    if slope > 15:
        return "DEGRADING"

    if slope < -15:
        return "IMPROVING"

    return "STABLE"

def classify_trend_http(slope):

    if slope is None:
        return "UNKNOWN"

    if slope < 10:
        return "STABLE"
    elif slope < 40:
        return "RISING"
    elif slope < 80:
        return "DEGRADING"
    else:
        return "CRITICAL"

def total_incidents(db, host_name):
    return (
        db.query(Incident)
        .filter(Incident.host_name == host_name)
        .count()
    )

def total_downtime(db, host_name):
    incidents = (
        db.query(Incident)
        .filter(
            Incident.host_name == host_name,
            Incident.status == "CLOSED",
            Incident.duration_seconds != None
        )
        .all()
    )

    return sum(i.duration_seconds for i in incidents)

def calculate_availability_from_incidents(incidents, now, since, total_period: int = 600) -> float:
    if total_period <= 0:
        return 100.0

    raw_intervals = []
    for incident in incidents:
        start = incident.started_time
        end = incident.ended_time or now

        overlap_start = max(start, since)
        overlap_end = min(end, now)

        if overlap_end > overlap_start:
            raw_intervals.append((overlap_start, overlap_end))

    if not raw_intervals:
        return 100.0

    # Algoritmo de União de Intervalos: mescla sobreposições para evitar dupla contagem de downtime
    raw_intervals.sort(key=lambda item: item[0])
    merged = []
    for s, e in raw_intervals:
        if not merged:
            merged.append([s, e])
        else:
            prev_s, prev_e = merged[-1]
            if s <= prev_e:
                merged[-1][1] = max(prev_e, e)
            else:
                merged.append([s, e])

    downtime = sum((e - s).total_seconds() for s, e in merged)
    availability = ((total_period - downtime) / total_period) * 100
    return round(max(0.0, min(100.0, availability)), 4)

def availability_last_10_min(db, host_name):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    since = now - timedelta(minutes=10)

    incidents = (
        db.query(Incident)
        .filter(
            Incident.host_name == host_name,
            Incident.started_time <= now,
            (Incident.ended_time == None) | (Incident.ended_time >= since)
        )
        .all()
    )

    return calculate_availability_from_incidents(incidents, now, since)

def apply_preventive_logic(host, snmp_data=None, ignore_ping_metrics: bool = False):
    reasons = []
    preventive_severity = "HEALTHY"

    # Se já caiu, não é preventivo: é crítico operacional
    if host.status == "DOWN":
        return "CRITICAL", ["Host indisponível"]

    if host.status == "DEGRADED":
        preventive_severity = "DEGRADED"
        reasons.append("Serviço degradado")

    # ---------- SLA ----------
    sla_ping = None if ignore_ping_metrics else host.sla_rolling_ping
    http_is_active = bool(getattr(host, "http_enabled", True))
    sla_http = host.sla_rolling_http if http_is_active else None
    sla_values = [
        sla_ping,
        host.sla_rolling_tcp,
        sla_http
    ]

    valid_slas = [v for v in sla_values if v is not None]

    if any(v < 95 for v in valid_slas):
        preventive_severity = max_severity(preventive_severity, "WARNING")
        reasons.append("Queda de taxa de sucesso")

    if any(v < 85 for v in valid_slas):
        preventive_severity = max_severity(preventive_severity, "DEGRADED")
        reasons.append("SLA instável")

    # ---------- Jitter ----------
    jitter_ping = None if ignore_ping_metrics else host.jitter_ms_ping
    jitter_http = host.jitter_ms_http if http_is_active else None
    jitter_values = [
        jitter_ping,
        host.jitter_ms_tcp,
        jitter_http
    ]

    valid_jitters = [v for v in jitter_values if v is not None]

    if any(v > 80 for v in valid_jitters):
        preventive_severity = max_severity(preventive_severity, "WARNING")
        reasons.append("Alta variação de latência")

    if any(v > 150 for v in valid_jitters):
        preventive_severity = max_severity(preventive_severity, "DEGRADED")
        reasons.append("Jitter crítico")

    # ---------- Tendência ----------
    # Rótulos reais: classify_trend -> DEGRADING/FAST_DEGRADING;
    # classify_trend_http -> DEGRADING/CRITICAL (RISING é ignorado para evitar ruído).
    if not ignore_ping_metrics and host.trend in PING_WORSENING_TRENDS:
        preventive_severity = max_severity(preventive_severity, "WARNING")
        reasons.append("Tendência de piora no ping")

    if http_is_active and host.trend_http in HTTP_WORSENING_TRENDS:
        preventive_severity = max_severity(preventive_severity, "WARNING")
        reasons.append("Tendência de piora no HTTP")

    # ---------- SNMP ----------
    if snmp_data:
        cpu = snmp_data.get("cpu")
        ram = snmp_data.get("ram")
        disk = snmp_data.get("disk")

        if cpu is not None and cpu >= 85:
            preventive_severity = max_severity(preventive_severity, "WARNING")
            reasons.append(f"CPU alta ({cpu}%)")

        if cpu is not None and cpu >= 95:
            preventive_severity = max_severity(preventive_severity, "CRITICAL")
            reasons.append(f"CPU crítica ({cpu}%)")

        if ram is not None and ram >= 85:
            preventive_severity = max_severity(preventive_severity, "WARNING")
            reasons.append(f"RAM alta ({ram}%)")

        if ram is not None and ram >= 95:
            preventive_severity = max_severity(preventive_severity, "CRITICAL")
            reasons.append(f"RAM crítica ({ram}%)")

        if disk is not None and disk >= 90:
            preventive_severity = max_severity(preventive_severity, "WARNING")
            reasons.append(f"Disco alto ({disk}%)")

        if disk is not None and disk >= 97:
            preventive_severity = max_severity(preventive_severity, "CRITICAL")
            reasons.append(f"Disco crítico ({disk}%)")

    return preventive_severity, reasons

def max_severity(current, new):
    order = {
        "HEALTHY": 0,
        "WARNING": 1,
        "DEGRADED": 2,
        "CRITICAL": 3
    }
    return new if order[new] > order[current] else current


async def calc_sla_rolling_ping_async(db, host_id, window=50):
    stmt = (
        select(CheckResult)
        .filter(CheckResult.host_id == host_id, CheckResult.check_type == "ping")
        .order_by(CheckResult.timestamp.desc())
        .limit(window)
    )
    res = await db.execute(stmt)
    rows = res.scalars().all()
    if len(rows) < MIN_SLA_SAMPLES:
        return None
    ok = sum(1 for r in rows if r.success)
    return round(ok / len(rows) * 100, 2)


async def calc_sla_rolling_tcp_ports_async(db, host_id, tcp_ports, window=50):
    ports = [int(p) for p in (tcp_ports or []) if p is not None]
    if not ports:
        return None
    stmt = (
        select(CheckResult)
        .filter(
            CheckResult.host_id == host_id,
            CheckResult.check_type == "tcp",
            CheckResult.tcp_port.in_(ports),
        )
        .order_by(CheckResult.timestamp.desc())
        .limit(window)
    )
    res = await db.execute(stmt)
    rows = res.scalars().all()
    if len(rows) < MIN_SLA_SAMPLES:
        return None
    ok = sum(1 for r in rows if r.success)
    return round(ok / len(rows) * 100, 2)


async def calc_sla_rolling_http_async(db, host_id, window=50):
    stmt = (
        select(CheckResult)
        .filter(CheckResult.host_id == host_id, CheckResult.check_type == "http")
        .order_by(CheckResult.timestamp.desc())
        .limit(window)
    )
    res = await db.execute(stmt)
    rows = res.scalars().all()
    if len(rows) < MIN_SLA_SAMPLES:
        return None
    success_count = sum(1 for r in rows if r.success)
    return round((success_count / len(rows)) * 100, 2)


async def calc_jitter_ping_async(db, host_id, window=10):
    stmt = (
        select(CheckResult)
        .filter(
            CheckResult.host_id == host_id,
            CheckResult.check_type == "ping",
            CheckResult.latency != None,
        )
        .order_by(CheckResult.timestamp.desc())
        .limit(window)
    )
    res = await db.execute(stmt)
    rows = res.scalars().all()
    if len(rows) < 2:
        return None
    values = [r.latency for r in rows]
    values.reverse()
    diffs = [abs(values[i] - values[i - 1]) for i in range(1, len(values))]
    return round(sum(diffs) / len(diffs), 2)


async def calc_jitter_tcp_ports_async(db, host_id, tcp_ports, window=10):
    ports = [int(p) for p in (tcp_ports or []) if p is not None]
    if not ports:
        return None
    stmt = (
        select(CheckResult)
        .filter(
            CheckResult.host_id == host_id,
            CheckResult.check_type == "tcp",
            CheckResult.tcp_port.in_(ports),
            CheckResult.latency != None,
        )
        .order_by(CheckResult.timestamp.desc())
        .limit(window)
    )
    res = await db.execute(stmt)
    rows = res.scalars().all()
    if len(rows) < 2:
        return None
    values = [r.latency for r in rows]
    values.reverse()
    diffs = [abs(values[i] - values[i - 1]) for i in range(1, len(values))]
    return round(sum(diffs) / len(diffs), 2)


async def calc_jitter_http_async(db, host_id, window=10):
    stmt = (
        select(CheckResult)
        .filter(
            CheckResult.host_id == host_id,
            CheckResult.check_type == "http",
            CheckResult.success == True,
            CheckResult.latency != None,
        )
        .order_by(CheckResult.timestamp.desc())
        .limit(window)
    )
    res = await db.execute(stmt)
    rows = res.scalars().all()
    if len(rows) < 3:
        return None
    latencies = [r.latency for r in rows]
    latencies.reverse()
    diffs = [abs(latencies[i] - latencies[i - 1]) for i in range(1, len(latencies))]
    return round(sum(diffs) / len(diffs), 2)


async def calc_latency_trend_ping_async(db, host_id, window=10):
    stmt = (
        select(CheckResult)
        .filter(
            CheckResult.host_id == host_id,
            CheckResult.check_type == "ping",
            CheckResult.success == True,
            CheckResult.latency != None,
        )
        .order_by(CheckResult.timestamp.desc())
        .limit(window)
    )
    res = await db.execute(stmt)
    rows = res.scalars().all()
    if len(rows) < 5:
        return None
    values = [r.latency for r in rows]
    values.reverse()
    x = list(range(len(values)))
    x_mean = sum(x) / len(x)
    y_mean = sum(values) / len(values)
    num = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, values))
    den = sum((xi - x_mean) ** 2 for xi in x)
    if den == 0:
        return 0
    slope = num / den
    return round(slope, 2)


async def calc_latency_trend_http_async(db, host_id, window=10):
    stmt = (
        select(CheckResult)
        .filter(
            CheckResult.host_id == host_id,
            CheckResult.check_type == "http",
            CheckResult.success == True,
            CheckResult.latency != None,
        )
        .order_by(CheckResult.timestamp.desc())
        .limit(window)
    )
    res = await db.execute(stmt)
    rows = res.scalars().all()
    if len(rows) < 5:
        return None
    values = [r.latency for r in rows]
    values.reverse()
    x = list(range(len(values)))
    x_mean = sum(x) / len(x)
    y_mean = sum(values) / len(values)
    num = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, values))
    den = sum((xi - x_mean) ** 2 for xi in x)
    if den == 0:
        return 0
    slope = num / den
    return round(slope, 2)
