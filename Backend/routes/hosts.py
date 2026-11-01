from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import asyncio
import ipaddress
import json
import os
import re
import socket
import subprocess
import xml.etree.ElementTree as ET
import psutil
from Backend.database import get_db
from Backend.metrics import total_downtime, total_incidents, availability_last_10_min, compute_health, calculate_availability_from_incidents
from Backend.models import CheckResult, Host, Alert, Incident, User, SNMPMetric
from Backend.checker import ping_host, tcp_check, http_check, resolve_dns_cached_sync
from Backend.notifications import telegram_health_check
from Backend.services.circuit_breaker import circuit_breaker
from Backend.snmp_engine import reset_snmp_backoff
from Backend.mq_manager import mq_manager
from Backend.schemas import (
    HostCreate,
    HostUpdate,
    LoginRequest,
    PasswordChangeRequest,
    NetworkDiscoveryRequest,
    NetworkImportRequest,
    BulkDeactivateRequest,
)
from Backend.utils import (
    is_ip,
    reverse_dns,
    resolve_http_url,
    extract_ips_from_dns_result,
    get_last_check,
    calculate_availability_points,
    parse_incident_type,
    strip_incident_prefix,
)
from Backend.dependencies import get_current_user, get_current_admin
from Backend.security import verify_password, create_access_token, hash_password

router = APIRouter()

_RFC1918_RANGES = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
)
_IGNORED_INTERFACE_PREFIXES = (
    "lo",
    "docker",
    "br-",
    "veth",
    "virbr",
    "tun",
    "tap",
)
_MAX_DISCOVERY_ADDRESSES = 4096


def _apply_snmp_policy(host: Host, snmp_enabled: bool | None, snmp_community: str | None = None) -> None:
    if snmp_enabled is not None:
        host.snmp_enabled = bool(snmp_enabled)
    comm = (snmp_community or getattr(host, "snmp_community", "netspot") or "netspot").strip()
    if not comm:
        comm = "netspot"
    host.snmp_community = comm


def _apply_http_policy(host: Host, http_enabled: bool | None, selected_http: str | None) -> None:
    if http_enabled is not None:
        host.http_enabled = bool(http_enabled)

    host.http_url = resolve_http_url(host.address, selected_http, host.port)

    if not bool(getattr(host, "http_enabled", True)):
        host.last_http_protocol = None
        host.http_latency = None
        host.https_latency = None
        host.web_tcp_port = None
        host.web_tcp_port_latency = None
        host.tcp_http_port_ok = None
        host.tcp_http_port_latency = None
        host.tcp_https_port_ok = None
        host.tcp_https_port_latency = None
        host.sla_rolling_http = None
        host.jitter_ms_http = None
        host.slope_http = None
        host.trend_http = "UNKNOWN"


def _normalize_ports(raw_ports, fallback_port: int | None = None) -> list[int]:
    candidates = []
    if raw_ports:
        candidates.extend(raw_ports)
    elif fallback_port is not None:
        candidates.append(fallback_port)

    cleaned = []
    seen = set()
    for value in candidates:
        if value in (None, ""):
            continue
        try:
            port = int(value)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=f"Porta inválida: {value}")

        if port < 1 or port > 65535:
            raise HTTPException(status_code=400, detail=f"Porta fora da faixa permitida: {port}")
        if port in seen:
            continue
        seen.add(port)
        cleaned.append(port)

    cleaned.sort()
    return cleaned


def _store_host_ports(host: Host, ports: list[int]) -> None:
    host.port = ports[0] if ports else None
    host.tcp_ports = json.dumps(ports) if ports else None


def _host_ports(host: Host) -> list[int]:
    if host.tcp_ports:
        try:
            parsed = json.loads(host.tcp_ports)
            if isinstance(parsed, list):
                normalized = _normalize_ports(parsed, None)
                if normalized:
                    return normalized
        except Exception:
            pass

    if host.port is not None:
        return _normalize_ports([host.port], None)
    return []


def _resolve_http_input(data) -> str | None:
    preferred = (data.url or "").strip() if hasattr(data, "url") else ""
    legacy = (data.http_url or "").strip() if hasattr(data, "http_url") else ""
    return preferred or legacy or None


def _slug_ip_name(ip_value: str) -> str:
    safe = re.sub(r"[^0-9a-zA-Z]+", "-", str(ip_value)).strip("-")
    return f"auto-{safe}" if safe else "auto-host"


def _is_rfc1918_private(network: ipaddress.IPv4Network | ipaddress.IPv6Network) -> bool:
    return any(network.subnet_of(rng) for rng in _RFC1918_RANGES)


def _validate_private_subnet(subnet: str) -> str:
    raw = (subnet or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="Subnet é obrigatória")

    try:
        network = ipaddress.ip_network(raw, strict=False)
    except ValueError:
        raise HTTPException(status_code=400, detail="Subnet inválida. Use formato CIDR, ex: 192.168.0.0/24")

    if not _is_rfc1918_private(network):
        raise HTTPException(status_code=400, detail="Subnet deve ser privada RFC1918")

    if network.num_addresses > _MAX_DISCOVERY_ADDRESSES:
        raise HTTPException(status_code=400, detail="Subnet muito grande para varredura automática")

    return str(network)


def _interface_ignored(interface_name: str) -> bool:
    lowered = (interface_name or "").strip().lower()
    return any(lowered.startswith(prefix) for prefix in _IGNORED_INTERFACE_PREFIXES)


def _run_nmap_discovery(subnet: str) -> str:
    try:
        # Calibração dinâmica consciente do tamanho da sub-rede (CIDR-Aware Timing):
        # 1. Redes de pequeno e médio porte (até /22 ou 1.024 endereços, caso de 99% das LANs e do Kathará):
        #    Prioriza 100% de assertividade no 1º ciclo, mitigando a latência de resolução ARP a frio
        #    (cold ARP cache) e prevenindo o descarte prematuro por estouro de fila do kernel (unres_qlen).
        # 2. Redes massivas (/21 e /20, 2.048 a 4.096 IPs):
        #    Prioriza throughput e velocidade para assegurar conclusão bem abaixo do timeout de 120s da API.
        try:
            net = ipaddress.ip_network(subnet, strict=False)
            num_ips = net.num_addresses
        except Exception:
            num_ips = 256

        if num_ips <= 1024:
            min_rate = "150"
            initial_rtt = "300ms"
            max_rtt = "800ms"
            max_retries = "2"
        else:
            min_rate = "350"
            initial_rtt = "200ms"
            max_rtt = "500ms"
            max_retries = "1"

        # Varredura ágil e pura de conectividade ICMP (Echo Request -PE), desativando probes de portas TCP
        # e desativando resolução reversa de DNS (-n) para garantir máxima velocidade e estabilidade
        # sem travamentos por portas fechadas ou DNS indisponível, suportando faixas de até /20 (4.096 IPs).
        nmap_args = [
            "nmap",
            "-sn",
            "-PE",
            "-n",
            "-T4",
            "--min-rate",
            min_rate,
            "--initial-rtt-timeout",
            initial_rtt,
            "--max-rtt-timeout",
            max_rtt,
            "--max-retries",
            max_retries,
            subnet,
            "-oX",
            "-",
        ]

        result = subprocess.run(
            nmap_args,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Nmap não está instalado no servidor")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Descoberta de rede excedeu o tempo limite")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha ao executar descoberta: {exc}")

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise HTTPException(
            status_code=500,
            detail=f"Nmap retornou erro ({result.returncode}): {stderr or 'erro desconhecido'}",
        )

    return result.stdout or ""


def _parse_nmap_hosts(xml_text: str) -> list[dict]:
    if not xml_text.strip():
        return []

    try:
        # XML gerado exclusivamente pelo subprocess local nmap -oX -
        root = ET.fromstring(xml_text)  # nosec B314
    except ET.ParseError:
        raise HTTPException(status_code=500, detail="Resposta XML do Nmap inválida")

    hosts = []
    for host_node in root.findall("host"):
        status = host_node.find("status")
        if status is None or status.attrib.get("state") != "up":
            continue

        ipv4 = None
        for addr in host_node.findall("address"):
            if addr.attrib.get("addrtype") == "ipv4":
                ipv4 = (addr.attrib.get("addr") or "").strip()
                break

        if not ipv4:
            continue

        hostname_value = None
        hostnames = host_node.find("hostnames")
        if hostnames is not None:
            hn = hostnames.find("hostname")
            if hn is not None:
                hostname_value = (hn.attrib.get("name") or "").strip() or None

        hosts.append({
            "address": ipv4,
            "hostname": hostname_value,
        })

    return hosts


def _build_unique_name(base_name: str, used_names: set[str]) -> str:
    candidate = base_name
    suffix = 2
    while candidate in used_names:
        candidate = f"{base_name}-{suffix}"
        suffix += 1
    used_names.add(candidate)
    return candidate


def _is_tcp_port_open(ip: str, port: int = 53, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except Exception:
        return False


def _discover_local_dns_servers(subnet: str, active_ips: list[str]) -> list[str]:
    """
    Descobre dinamicamente quais IPs ativos na rede (ou gateways da sub-rede/tabela de rotas)
    possuem o serviço DNS (porta 53) aberto, sem assumir um gateway fixo (.1).
    """
    from concurrent.futures import ThreadPoolExecutor

    candidates: list[str] = []
    seen: set[str] = set()

    def _add(ip_val: str | None) -> None:
        val = (ip_val or "").strip()
        if val and val not in seen:
            seen.add(val)
            candidates.append(val)

    # 1. Todos os IPs ativos descobertos no scan (inclui roteadores em .1, .254 ou servidores DNS como 10.0.3.7)
    for ip in active_ips:
        _add(ip)

    # 2. Gateways candidatos da sub-rede (.1 e último IP utilizável .254), caso bloqueiem ICMP mas aceitem DNS
    try:
        net = ipaddress.ip_network(subnet, strict=False)
        if isinstance(net, ipaddress.IPv4Network) and net.num_addresses >= 4:
            _add(str(net.network_address + 1))
            _add(str(net.broadcast_address - 1))
    except Exception:
        pass

    # 3. Gateways configurados na tabela de roteamento do sistema operacional
    try:
        route_out = subprocess.run(
            ["ip", "route"],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=False,
        ).stdout or ""
        for match in re.findall(r"\bvia\s+(\d+\.\d+\.\d+\.\d+)\b", route_out):
            _add(match)
    except Exception:
        pass

    if not candidates:
        return []

    max_workers = min(len(candidates), 20)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        flags = list(pool.map(_is_tcp_port_open, candidates))

    return [ip for ip, is_open in zip(candidates, flags) if is_open]


def _query_snmp_sysname_sync(ip: str, community: str = "netspot", timeout: float = 0.6) -> str | None:
    """Consulta de forma rápida o OID sysName.0 (1.3.6.1.2.1.1.5.0) via SNMPv2c."""
    import asyncio
    from pysnmp.hlapi.v3arch.asyncio import (
        SnmpEngine,
        CommunityData,
        UdpTransportTarget,
        ContextData,
        ObjectType,
        ObjectIdentity,
        get_cmd,
    )

    async def _fetch() -> str | None:
        snmp_engine = SnmpEngine()
        try:
            comm = (community or "netspot").strip() or "netspot"
            error_indication, error_status, _, var_binds = await get_cmd(
                snmp_engine,
                CommunityData(comm, mpModel=1),
                await UdpTransportTarget.create((ip, 161), timeout=timeout, retries=0),
                ContextData(),
                ObjectType(ObjectIdentity("1.3.6.1.2.1.1.5.0")),
            )
            if error_indication or error_status or not var_binds:
                return None
            val_str = str(var_binds[0][1]).strip()
            if not val_str or "No Such" in val_str:
                return None
            return val_str
        except Exception:
            return None
        finally:
            snmp_engine.close_dispatcher()

    try:
        return asyncio.run(_fetch())
    except Exception:
        return None


def _resolve_single_discovered_hostname(ip: str, dns_servers: list[str]) -> str | None:
    """
    Resolve o nome do dispositivo combinando:
    1) DNS reverso nos servidores DNS/gateways descobertos dinamicamente na LAN;
    2) DNS reverso padrão do sistema;
    3) SNMP sysName.0 (1.3.6.1.2.1.1.5.0) direto no dispositivo.
    """
    import dns.resolver
    import dns.reversename

    # 1. DNS Reverso nos servidores DNS locais descobertos na sub-rede/rotas
    if dns_servers:
        try:
            rev_name = dns.reversename.from_address(ip)
            resolver = dns.resolver.Resolver(configure=False)
            resolver.nameservers = dns_servers
            resolver.timeout = 0.4
            resolver.lifetime = 0.6
            answers = resolver.resolve(rev_name, "PTR")
            for rdata in answers:
                target = str(rdata.target).rstrip(".").strip()
                if target:
                    return target
        except Exception:
            pass

    # 2. DNS Reverso padrão do sistema
    sys_rdns = reverse_dns(ip, timeout=0.5)
    if sys_rdns:
        clean_rdns = str(sys_rdns).rstrip(".").strip()
        if clean_rdns and clean_rdns != ip:
            return clean_rdns

    # 3. Fallback SNMP sysName.0 (1.3.6.1.2.1.1.5.0) direto no host
    snmp_name = _query_snmp_sysname_sync(ip, timeout=0.6)
    if snmp_name:
        return snmp_name

    return None


_DISCOVERY_SERVICE_PORTS = (
    22,    # SSH
    53,    # DNS
    80,    # HTTP
    443,   # HTTPS
    3000,  # Web / Frontend Dev / Grafana
    3306,  # MySQL / MariaDB
    5432,  # PostgreSQL
    5672,  # RabbitMQ / AMQP
    6379,  # Redis
    8000,  # API HTTP / Microserviço
    8080,  # App Server / Tomcat / Admin HTTP
    8443,  # HTTPS Alternativo / Gateway
    9187,  # Prometheus Exporter
)
_DISCOVERY_WEB_PORTS = (80, 443, 8443, 8080, 8000, 3000)


def _infer_http_policy_from_ports(address: str, open_ports: list[int]) -> tuple[bool, str | None]:
    if not open_ports:
        return False, None
    port_set = set(open_ports)
    if 80 in port_set and 443 in port_set:
        return True, None
    if 443 in port_set:
        return True, f"https://{address}"
    if 80 in port_set:
        return True, f"http://{address}"
    for wp in (8443, 8080, 8000, 3000):
        if wp in port_set:
            scheme = "https" if wp == 8443 else "http"
            return True, f"{scheme}://{address}:{wp}"
    return False, None


def _discover_open_ports_batch(
    ips: list[str],
    ports: tuple[int, ...] = _DISCOVERY_SERVICE_PORTS,
    timeout: float = 0.25,
) -> dict[str, list[int]]:
    clean_ips = sorted({str(ip or "").strip() for ip in ips if str(ip or "").strip()})
    if not clean_ips:
        return {}

    import asyncio

    async def _run_batch() -> dict[str, list[int]]:
        sem = asyncio.Semaphore(256)
        result_map: dict[str, list[int]] = {ip: [] for ip in clean_ips}

        async def _probe(ip: str, port: int) -> None:
            async with sem:
                try:
                    _, writer = await asyncio.wait_for(
                        asyncio.open_connection(ip, port),
                        timeout=timeout,
                    )
                    writer.close()
                    try:
                        await writer.wait_closed()
                    except Exception:
                        pass
                    result_map[ip].append(port)
                except Exception:
                    pass

        await asyncio.gather(
            *[_probe(ip, p) for ip in clean_ips for p in ports],
            return_exceptions=True,
        )
        for ip in result_map:
            result_map[ip].sort()
        return result_map

    try:
        return asyncio.run(_run_batch())
    except Exception:
        return {ip: [] for ip in clean_ips}


def _enrich_discovered_hostnames(raw_hosts: list[dict], subnet: str) -> list[dict]:
    if not raw_hosts:
        return []

    from concurrent.futures import ThreadPoolExecutor

    active_ips = [str(item.get("address") or "").strip() for item in raw_hosts if item.get("address")]
    dns_servers = _discover_local_dns_servers(subnet, active_ips)
    open_ports_by_ip = _discover_open_ports_batch(active_ips)

    def _enrich_item(item: dict) -> dict:
        addr = str(item.get("address") or "").strip()
        existing_hn = (item.get("hostname") or "").strip() or None
        open_ports = item.get("ports") if item.get("ports") is not None else open_ports_by_ip.get(addr, [])
        http_enabled, http_url = _infer_http_policy_from_ports(addr, open_ports)
        if existing_hn or not addr:
            return {
                "address": addr,
                "hostname": existing_hn,
                "ports": open_ports,
                "http_enabled": http_enabled,
                "http_url": http_url,
            }
        resolved_hn = _resolve_single_discovered_hostname(addr, dns_servers)
        return {
            "address": addr,
            "hostname": resolved_hn,
            "ports": open_ports,
            "http_enabled": http_enabled,
            "http_url": http_url,
        }

    max_workers = min(len(raw_hosts), 20)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        return list(pool.map(_enrich_item, raw_hosts))


def _prepare_discovery_result(db: Session, raw_hosts: list[dict]) -> list[dict]:
    if not raw_hosts:
        return []

    addresses = sorted({str(item.get("address") or "").strip() for item in raw_hosts if item.get("address")})
    existing_hosts = db.query(Host).filter(Host.address.in_(addresses), Host.active.is_(True)).all()
    existing_ip_set = {h.address for h in existing_hosts}
    used_names = {str(row[0]).strip() for row in db.query(Host.name).filter(Host.active.is_(True)).all() if row[0]}
    seen_ips = set()

    prepared = []
    temp_idx = 1
    for item in raw_hosts:
        address = str(item.get("address") or "").strip()
        if not address or address in seen_ips:
            continue
        seen_ips.add(address)

        hostname = item.get("hostname")
        base_name = str(hostname).strip() if hostname else _slug_ip_name(address)
        safe_name = _build_unique_name(base_name, used_names)
        open_ports = _normalize_ports(item.get("ports"), None) if item.get("ports") else []
        inferred_http_enabled, inferred_http_url = _infer_http_policy_from_ports(address, open_ports)
        http_enabled = (
            bool(item["http_enabled"])
            if item.get("http_enabled") is not None
            else inferred_http_enabled
        )
        http_url = item.get("http_url") if item.get("http_url") is not None else inferred_http_url

        prepared.append({
            "id": f"temp-{temp_idx}",
            "name": safe_name,
            "address": address,
            "hostname": hostname,
            "ports": open_ports,
            "http_enabled": http_enabled,
            "http_url": http_url,
            "already_exists": address in existing_ip_set,
        })
        temp_idx += 1

    return prepared


def _detect_local_network() -> str:
    # 1. Prioridade máxima: Configuração explícita via variável de ambiente
    configured = (os.getenv("NETSPOT_DEFAULT_SUBNET") or os.getenv("DEFAULT_DISCOVERY_SUBNET") or "").strip()
    if configured:
        try:
            net = ipaddress.ip_network(configured, strict=False)
            if _is_rfc1918_private(net) and net.num_addresses <= _MAX_DISCOVERY_ADDRESSES:
                return str(net)
        except ValueError:
            pass

    outbound_ip = None
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            outbound_ip = sock.getsockname()[0]
    except Exception:
        outbound_ip = None

    try:
        stats_by_iface = psutil.net_if_stats()
    except Exception:
        stats_by_iface = {}

    try:
        interfaces = psutil.net_if_addrs().items()
    except Exception:
        interfaces = []

    candidates = []
    for iface, addrs in interfaces:
        if _interface_ignored(iface):
            continue
        iface_stats = stats_by_iface.get(iface)
        if iface_stats is not None and not iface_stats.isup:
            continue

        for addr in addrs:
            if addr.family != socket.AF_INET:
                continue

            ip = (addr.address or "").strip()
            netmask = (addr.netmask or "").strip()
            if not ip or ip.startswith("127.") or not netmask:
                continue

            try:
                network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
            except ValueError:
                continue

            if not _is_rfc1918_private(network):
                continue

            # Rejeita redes que excedem o teto operacional de varredura (ex.: /16 com 65.536 hosts)
            if network.num_addresses > _MAX_DISCOVERY_ADDRESSES:
                continue

            # Rejeita faixas do pool de bridge interna do Docker (172.16.0.0/12)
            if any(network.subnet_of(rng) for rng in (ipaddress.ip_network("172.16.0.0/12"),)):
                continue

            candidates.append({
                "iface": iface,
                "ip": ip,
                "cidr": str(network),
            })

    if candidates:
        if outbound_ip:
            for candidate in candidates:
                if candidate["ip"] == outbound_ip:
                    return candidate["cidr"]
        return candidates[0]["cidr"]

    # Fallback seguro para LAN padrão (evita capturar bridge interna do Docker 172.20.0.0/16)
    return "192.168.1.0/24"


def _reset_host_operational_state(host: Host) -> None:
    host.baseline_pending = True
    host.status = "UNKNOWN"
    host.status_ping = None
    host.status_tcp = None
    host.last_check = None
    host.latency_ping = None
    host.latency_tcp = None
    host.fail_streak = 0
    host.success_streak = 0
    host.last_resolved_ip = None
    host.hostname_resolved = None
    host.dns_ttl = None
    host.dns_ttl_remaining = None
    host.last_ttl_alert = None
    host.health_score = 0
    host.severity = "UNKNOWN"
    host.last_preventive_alert = None

    host.cpu_usage = None
    host.ram_usage = None
    host.disk_usage = None
    host.disk_remaining = None
    host.network_traffic = None
    host.network_in_bps = None
    host.network_out_bps = None
    host.last_net_in_octets = None
    host.last_net_out_octets = None
    host.last_net_check = None
    host.last_snmp_check = None

    host.sla_rolling_ping = None
    host.sla_rolling_tcp = None
    host.sla_rolling_http = None
    host.jitter_ms_ping = None
    host.jitter_ms_tcp = None
    host.jitter_ms_http = None
    host.slope = None
    host.trend = "UNKNOWN"
    host.slope_http = None
    host.trend_http = "UNKNOWN"
    host.last_http_protocol = None
    host.http_latency = None
    host.https_latency = None
    host.web_tcp_port = None
    host.web_tcp_port_latency = None
    host.tcp_http_port_ok = None
    host.tcp_http_port_latency = None
    host.tcp_https_port_ok = None
    host.tcp_https_port_latency = None


def _deactivate_host_entity(host: Host) -> None:
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    host.active = False
    host.active_time = now_utc
    host.deleted_at = now_utc
    circuit_breaker.clear_host(host.id)
    reset_snmp_backoff(host.id)


def _is_icmp_blocked_but_service_up(
    host: Host,
    last_ping: CheckResult | None,
    last_tcp: CheckResult | None,
    last_http: CheckResult | None,
) -> bool:
    if not last_ping or last_ping.success:
        return False

    has_tcp_ports = bool(_host_ports(host))
    tcp_ok = has_tcp_ports and bool(last_tcp and last_tcp.success)
    http_ok = bool(last_http and last_http.success)
    return tcp_ok or http_ok

def infer_probable_cause(db: Session, host: Host) -> str:
    # 1. Caminho rápido antecipado para hosts comprovadamente saudáveis:
    is_healthy = host.status == "UP" and host.severity in ("HEALTHY", "UNKNOWN", None)
    cpu_val = getattr(host, "cpu_usage", None)
    ram_val = getattr(host, "ram_usage", None)
    disk_val = getattr(host, "disk_usage", None)
    jitter_ping = getattr(host, "jitter_ms_ping", None)
    jitter_tcp = getattr(host, "jitter_ms_tcp", None)
    jitter_http = getattr(host, "jitter_ms_http", None)
    sla_ping = getattr(host, "sla_rolling_ping", None)
    sla_tcp = getattr(host, "sla_rolling_tcp", None)
    sla_http = getattr(host, "sla_rolling_http", None)

    has_normal_resources = (
        (cpu_val is None or cpu_val < 85)
        and (ram_val is None or ram_val < 85)
        and (disk_val is None or disk_val < 90)
        and (jitter_ping is None or jitter_ping < 80)
        and (jitter_tcp is None or jitter_tcp < 80)
        and (jitter_http is None or jitter_http < 80)
        and (sla_ping is None or sla_ping >= 95)
        and (sla_tcp is None or sla_tcp >= 95)
        and (sla_http is None or sla_http >= 95)
    )
    if is_healthy and has_normal_resources and getattr(host, "status_ping", None) == "UP":
        host.icmp_blocked_but_service_up = False
        return "Operação normal"

    if (
        host.status == "UNKNOWN"
        and getattr(host, "baseline_pending", False)
        and getattr(host, "last_check", None) is None
        and has_normal_resources
    ):
        host.icmp_blocked_but_service_up = False
        return "Operação normal"

    last_dns = get_last_check(db, host.id, "dns")
    last_ping = get_last_check(db, host.id, "ping")
    last_tcp = get_last_check(db, host.id, "tcp")
    last_http = get_last_check(db, host.id, "http") if bool(getattr(host, "http_enabled", True)) else None
    icmp_blocked_but_service_up = _is_icmp_blocked_but_service_up(
        host,
        last_ping,
        last_tcp,
        last_http,
    )
    host.icmp_blocked_but_service_up = icmp_blocked_but_service_up

    if icmp_blocked_but_service_up:
        return "ICMP bloqueado por firewall (Serviços TCP/Web operando normalmente)"

    configured_ports = _host_ports(host)
    primary_port = configured_ports[0] if configured_ports else host.port

    if host.status == "DOWN":
        if last_dns and not last_dns.success:
            return "Falha na resolução DNS (servidor não respondeu)"
        if last_http and not last_http.success and (last_http.status_code or 0) >= 500:
            return f"Serviço HTTP indisponível (HTTP {last_http.status_code})"
        if primary_port is not None and last_tcp and not last_tcp.success:
            return f"Porta TCP {primary_port} indisponível (conexão recusada/timeout)"
        if last_ping and not last_ping.success:
            return "Host sem resposta ICMP (offline ou inalcançável)"
        return "Indisponibilidade geral do host"

    # Diagnóstico detalhado e pontual de causas de degradação:
    causes = []

    # 1. Telemetria de Hardware (SNMP)
    if host.disk_usage is not None:
        if host.disk_usage >= 97:
            causes.append(f"Disco crítico ({host.disk_usage:.1f}%)")
        elif host.disk_usage >= 90:
            causes.append(f"Disco elevado ({host.disk_usage:.1f}%)")

    if host.ram_usage is not None:
        if host.ram_usage >= 95:
            causes.append(f"RAM crítica ({host.ram_usage:.1f}%)")
        elif host.ram_usage >= 85:
            causes.append(f"RAM elevada ({host.ram_usage:.1f}%)")

    if host.cpu_usage is not None:
        if host.cpu_usage >= 95:
            causes.append(f"CPU crítica ({host.cpu_usage:.1f}%)")
        elif host.cpu_usage >= 85:
            causes.append(f"CPU elevada ({host.cpu_usage:.1f}%)")

    # 2. Variação de Latência (Jitter)
    if host.jitter_ms_ping is not None and host.jitter_ms_ping >= 80:
        if host.jitter_ms_ping >= 150:
            causes.append(f"Jitter crítico no Ping ({host.jitter_ms_ping:.1f} ms)")
        else:
            causes.append(f"Jitter alto no Ping ({host.jitter_ms_ping:.1f} ms)")

    if host.jitter_ms_tcp is not None and host.jitter_ms_tcp >= 80:
        if host.jitter_ms_tcp >= 150:
            causes.append(f"Jitter crítico em portas TCP ({host.jitter_ms_tcp:.1f} ms)")
        else:
            causes.append(f"Jitter alto em portas TCP ({host.jitter_ms_tcp:.1f} ms)")

    if bool(getattr(host, "http_enabled", True)) and host.jitter_ms_http is not None and host.jitter_ms_http >= 80:
        if host.jitter_ms_http >= 150:
            causes.append(f"Jitter crítico na aplicação Web ({host.jitter_ms_http:.1f} ms)")
        else:
            causes.append(f"Jitter alto na aplicação Web ({host.jitter_ms_http:.1f} ms)")

    # 3. Taxa de Sucesso / SLA Móvel
    if host.sla_rolling_ping is not None and host.sla_rolling_ping < 95:
        if host.sla_rolling_ping < 85:
            causes.append(f"SLA instável no Ping ({host.sla_rolling_ping:.1f}%)")
        else:
            causes.append(f"Queda de sucesso no Ping ({host.sla_rolling_ping:.1f}%)")

    if host.sla_rolling_tcp is not None and host.sla_rolling_tcp < 95:
        if host.sla_rolling_tcp < 85:
            causes.append(f"SLA instável em portas TCP ({host.sla_rolling_tcp:.1f}%)")
        else:
            causes.append(f"Falhas pontuais em portas TCP ({host.sla_rolling_tcp:.1f}%)")

    if bool(getattr(host, "http_enabled", True)) and host.sla_rolling_http is not None and host.sla_rolling_http < 95:
        if host.sla_rolling_http < 85:
            causes.append(f"SLA instável na aplicação Web ({host.sla_rolling_http:.1f}%)")
        else:
            causes.append(f"Falhas pontuais na aplicação Web ({host.sla_rolling_http:.1f}%)")

    # 4. Tendências de Piora Contínua
    if host.trend in ("DEGRADING", "FAST_DEGRADING"):
        causes.append("Latência em tendência de piora contínua (Ping)")

    if bool(getattr(host, "http_enabled", True)) and host.trend_http in ("DEGRADING", "CRITICAL"):
        causes.append("Tempo de resposta web degradando progressivamente")

    # 5. Respostas de Aplicação Web ou Portas
    if last_http and not last_http.success and (last_http.status_code or 0) >= 400:
        causes.append(f"Aplicação web respondendo HTTP {last_http.status_code}")

    if primary_port is not None and last_tcp and not last_tcp.success:
        causes.append(f"Porta TCP {primary_port} com falha intermitente")

    if causes:
        return " | ".join(causes[:2])

    if host.severity in ("WARNING", "DEGRADED", "CRITICAL"):
        return f"Métrica preventiva em estado {host.severity}"

    return "Operação normal"

@router.post("/host/create")
def create_host(data: HostCreate, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    normalized_name = (data.name or "").strip()
    if not normalized_name:
        raise HTTPException(status_code=400, detail="Nome do host é obrigatório")

    normalized_address = (data.address or "").strip()
    if not normalized_address:
        raise HTTPException(status_code=400, detail="Endereço do host é obrigatório")

    existing_host = db.query(Host).filter(Host.name == normalized_name).first()
    resolved = None

    if is_ip(normalized_address):
        resolved = reverse_dns(normalized_address)
    else:
        dns_result = resolve_dns_cached_sync(normalized_address, db)  # Verifica se o endereço é válido
        ips = extract_ips_from_dns_result(dns_result)
        
        if not ips:
            raise HTTPException(status_code=400, detail="Endereço inválido")
                   
    if existing_host:
        if not existing_host.active:
            existing_host.active = True
            existing_host.active_time = None
            existing_host.deleted_at = None
            circuit_breaker.clear_host(existing_host.id)
            reset_snmp_backoff(existing_host.id)
            existing_ports = _host_ports(existing_host)
            if data.ports is None and data.port is None:
                ports = existing_ports
            else:
                ports = _normalize_ports(data.ports, data.port)
            existing_host.address = normalized_address
            _store_host_ports(existing_host, ports)
            _reset_host_operational_state(existing_host)
            existing_host.hostname_resolved = resolved

            selected_http = _resolve_http_input(data)
            _apply_http_policy(existing_host, data.http_enabled, selected_http)
            _apply_snmp_policy(existing_host, data.snmp_enabled, getattr(data, "snmp_community", "netspot"))

            db.commit()
            db.refresh(existing_host)
            if not existing_host.active:
                raise HTTPException(status_code=500, detail="Falha ao reativar host")
            mq_manager.publish_host_checks_sync([existing_host.id])
            return existing_host
        else:
            raise HTTPException(status_code=409, detail="Host com esse nome já existe")

    else:
        ports = _normalize_ports(data.ports, data.port)
        selected_http = _resolve_http_input(data)
        comm = (getattr(data, "snmp_community", "netspot") or "netspot").strip() or "netspot"
        host = Host(
            name=normalized_name,
            address=normalized_address,
            active=True,
            active_time=None,
            deleted_at=None,
            baseline_pending=True,
            status="UNKNOWN",
            status_ping="UNKNOWN",
            status_tcp="UNKNOWN",
            http_enabled=bool(data.http_enabled),
            last_http_protocol=None,
            snmp_enabled=bool(data.snmp_enabled),
            snmp_community=comm,
            hostname_resolved=resolved,
        )
        _store_host_ports(host, ports)

        _apply_http_policy(host, data.http_enabled, selected_http)
        _apply_snmp_policy(host, data.snmp_enabled, comm)

        db.add(host)
        db.commit()
        db.refresh(host)
        if not host.active:
            raise HTTPException(status_code=500, detail="Falha ao ativar host recém-criado")

        mq_manager.publish_host_checks_sync([host.id])
        return host



@router.post("/network/discover")
def network_discover(
    data: NetworkDiscoveryRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_admin),
):
    subnet = _validate_private_subnet(data.subnet)
    xml_result = _run_nmap_discovery(subnet)
    parsed_hosts = _parse_nmap_hosts(xml_result)
    enriched_hosts = _enrich_discovered_hostnames(parsed_hosts, subnet)
    hosts = _prepare_discovery_result(db, enriched_hosts)

    return {
        "subnet": subnet,
        "found": len(hosts),
        "hosts": hosts,
    }


@router.get("/network/default-subnet")
def network_default_subnet(user: str = Depends(get_current_user)):
    subnet = _detect_local_network()
    return {"subnet": subnet or None}


@router.post("/network/import")
def network_import(
    data: NetworkImportRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_admin),
):
    requested_hosts = list(data.hosts or [])
    results = []

    existing_ip_set = {row[0] for row in db.query(Host.address).all() if row[0]}
    used_names = {row[0] for row in db.query(Host.name).all() if row[0]}
    seen_addresses_in_request = set()
    created_count = 0
    skipped_count = 0
    new_or_reactivated_hosts = []

    ips_needing_probe = [
        str(it.address or "").strip()
        for it in requested_hosts
        if getattr(it, "ports", None) is None and str(it.address or "").strip()
    ]
    probed_ports_by_ip = _discover_open_ports_batch(ips_needing_probe) if ips_needing_probe else {}

    for item in requested_hosts:
        address = str(item.address or "").strip()
        raw_name = str(item.name or "").strip()

        if not address:
            skipped_count += 1
            results.append({
                "name": raw_name or None,
                "address": address,
                "created": False,
                "reason": "invalid_address",
            })
            continue

        try:
            ipaddress.ip_address(address)
        except ValueError:
            skipped_count += 1
            results.append({
                "name": raw_name or None,
                "address": address,
                "created": False,
                "reason": "invalid_address",
            })
            continue

        if address in seen_addresses_in_request:
            skipped_count += 1
            results.append({
                "name": raw_name or _slug_ip_name(address),
                "address": address,
                "created": False,
                "reason": "duplicate_in_request",
            })
            continue
        seen_addresses_in_request.add(address)

        target_snmp_enabled = bool(
            getattr(item, "snmp_enabled", None) if getattr(item, "snmp_enabled", None) is not None
            else (data.snmp_enabled if data.snmp_enabled is not None else True)
        )
        target_snmp_community = (
            getattr(item, "snmp_community", None) or getattr(data, "snmp_community", "netspot") or "netspot"
        ).strip() or "netspot"

        raw_item_ports = getattr(item, "ports", None)
        if raw_item_ports is None:
            raw_item_ports = probed_ports_by_ip.get(address, [])
        detected_ports = _normalize_ports(raw_item_ports, None) if raw_item_ports else []
        inferred_http_enabled, inferred_http_url = _infer_http_policy_from_ports(address, detected_ports)
        target_http_enabled = (
            bool(getattr(item, "http_enabled"))
            if getattr(item, "http_enabled", None) is not None
            else inferred_http_enabled
        )
        target_http_url = (
            getattr(item, "http_url")
            if getattr(item, "http_url", None) is not None
            else inferred_http_url
        )

        if address in existing_ip_set:
            existing_host = db.query(Host).filter(Host.address == address).first()
            if existing_host and not existing_host.active:
                existing_host.active = True
                existing_host.active_time = None
                existing_host.deleted_at = None
                _reset_host_operational_state(existing_host)
                if detected_ports:
                    _store_host_ports(existing_host, detected_ports)
                if target_http_enabled or getattr(item, "http_enabled", None) is not None:
                    _apply_http_policy(existing_host, target_http_enabled, target_http_url)
                _apply_snmp_policy(existing_host, target_snmp_enabled, target_snmp_community)
                circuit_breaker.clear_host(existing_host.id)
                reset_snmp_backoff(existing_host.id)
                created_count += 1
                new_or_reactivated_hosts.append(existing_host)
                results.append({
                    "name": existing_host.name,
                    "address": address,
                    "created": True,
                    "reactivated": True,
                })
                continue

            skipped_count += 1
            results.append({
                "name": existing_host.name if existing_host else (raw_name or _slug_ip_name(address)),
                "address": address,
                "created": False,
                "reason": "already_exists",
            })
            continue

        base_name = raw_name or _slug_ip_name(address)
        final_name = _build_unique_name(base_name, used_names)

        host = Host(
            name=final_name,
            address=address,
            port=None,
            tcp_ports=None,
            active=True,
            active_time=None,
            deleted_at=None,
            baseline_pending=True,
            status="UNKNOWN",
            status_ping="UNKNOWN",
            status_tcp="UNKNOWN",
            http_url=None,
            http_enabled=target_http_enabled,
            last_http_protocol=None,
            snmp_enabled=target_snmp_enabled,
            snmp_community=target_snmp_community,
        )
        _store_host_ports(host, detected_ports)
        _apply_http_policy(host, target_http_enabled, target_http_url)

        db.add(host)
        new_or_reactivated_hosts.append(host)
        existing_ip_set.add(address)
        created_count += 1
        results.append({
            "name": final_name,
            "address": address,
            "created": True,
        })

    db.flush()
    host_ids_to_check = [
        h.id for h in new_or_reactivated_hosts if getattr(h, "id", None) is not None
    ]
    db.commit()
    mq_manager.publish_host_checks_sync(host_ids_to_check)

    return {
        "requested": len(requested_hosts),
        "created": created_count,
        "skipped": skipped_count,
        "results": results,
    }


@router.get("/hosts/list")
def list_hosts(db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    hosts = db.query(Host).filter(Host.active.is_(True)).all()
    open_incident_hosts = {
        row[0]
        for row in db.query(Incident.host_name)
        .filter(Incident.status == "OPEN")
        .all()
    }

    # Batch de incidentes recentes (últimos 10 min) para eliminar N+1 queries de availability
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    since = now - timedelta(minutes=10)
    recent_incidents = (
        db.query(Incident)
        .filter(
            Incident.started_time <= now,
            (Incident.ended_time == None) | (Incident.ended_time >= since)
        )
        .all()
    )
    incidents_by_host = {}
    for inc in recent_incidents:
        incidents_by_host.setdefault(inc.host_name, []).append(inc)

    # Métricas em tempo real no objeto antes de enviar
    for h in hosts:
        h.ports = _host_ports(h)
        h.url = h.http_url
        h.http_protocol = h.last_http_protocol
        host_incidents = incidents_by_host.get(h.name)
        if host_incidents:
            h.availability_10m = calculate_availability_from_incidents(host_incidents, now, since)
        else:
            h.availability_10m = 100.0
        h.probable_cause = infer_probable_cause(db, h)
        h.icmp_blocked_but_service_up = bool(getattr(h, "icmp_blocked_but_service_up", False))
        h.has_open_incident = h.name in open_incident_hosts

    return hosts


@router.post("/host/check/{host_name}")
async def check_host(host_name: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):

    host = db.query(Host).filter(Host.name == host_name).first()

    if not host:
        raise HTTPException(status_code=404, detail="Host não encontrado")

    dns_result = resolve_dns_cached_sync(host.address, db)
    ips = extract_ips_from_dns_result(dns_result)

    if not ips:
        raise HTTPException(400, "DNS fail")

    ip = ips[0]
    host.last_resolved_ip = ip

    ports_to_check = _host_ports(host)

    async def _probe_tcp(p: int) -> dict:
        res = await tcp_check(ip, p)
        res["port"] = p
        return res

    http_is_active = bool(getattr(host, "http_enabled", True)) and bool(host.http_url)
    ping_task = ping_host(ip)
    tcp_task = asyncio.gather(*(_probe_tcp(p) for p in ports_to_check)) if ports_to_check else None
    http_task = http_check(host.http_url, verify_tls=False) if http_is_active else None

    ping_result = await ping_task
    tcp_results = list(await tcp_task) if tcp_task is not None else []
    http_result = await http_task if http_task is not None else None

    tcp_result = None
    if tcp_results:
        successes = [r for r in tcp_results if r.get("success")]
        if successes:
            best = min(successes, key=lambda r: r.get("latency") if r.get("latency") is not None else float("inf"))
            tcp_result = {"success": True, "latency": best.get("latency"), "error": None}
        else:
            tcp_result = {
                "success": False,
                "latency": None,
                "error": "; ".join(filter(None, [r.get("error") for r in tcp_results])) or "tcp_failed",
            }

    icmp_blocked_but_service_up = (
        not ping_result["success"] and (
            (tcp_result is not None and tcp_result.get("success")) or
            (http_result is not None and http_result.get("success"))
        )
    )

    host.status_ping = "UP" if ping_result["success"] else "DOWN"
    host.latency_ping = ping_result["latency"]
    
    if tcp_result is not None:
        host.status_tcp = "UP" if tcp_result["success"] else "DOWN"
        host.latency_tcp = tcp_result["latency"]
    else:
        host.status_tcp = None
        host.latency_tcp = None

    host.last_check = datetime.now(timezone.utc).replace(tzinfo=None)

    if icmp_blocked_but_service_up:
        host.status = "UP"
    elif host.status_ping == "DOWN":
        host.status = "DOWN"
    elif host.status_tcp == "DOWN" or (http_result is not None and not http_result.get("success")):
        host.status = "DEGRADED"
    else:
        host.status = "UP"

    score, severity = compute_health(ping_result, tcp_result, http_result)
    if host.status == "DOWN":
        score = 0
        severity = "CRITICAL"
    elif host.status == "DEGRADED" and severity not in ("CRITICAL", "DEGRADED"):
        severity = "DEGRADED"
        if score > 60:
            score = 60
    host.health_score = score
    host.severity = severity

    db.commit()

    return {
    "host": host.name,
    "address": host.address,
    "status": host.status,
    "icmp_blocked_but_service_up": icmp_blocked_but_service_up,
    "ping": {
        "status": host.status_ping,
        "latency": host.latency_ping
    },

    "tcp": {
        "status": host.status_tcp,
        "latency": host.latency_tcp
    }
}

@router.get("/host/history/{host_name}")
def host_history(host_name: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    host = db.query(Host).filter(Host.name == host_name).first()

    if not host:
        raise HTTPException(status_code=404, detail="Host não encontrado")

    checks = (
        db.query(CheckResult)
        .filter(CheckResult.host_id == host.id)
        .order_by(CheckResult.timestamp.desc())
        .limit(200)
        .all()
    )

    return {
        "host": host.name,
        "address": host.address,
        "checks": [
            {
                "type": c.check_type,
                "success": c.success,
                "latency": c.latency,
                "error": c.error,
                "status_code": c.status_code,
                "tcp_port": c.tcp_port,
                "timestamp": c.timestamp.isoformat()
            }
            for c in checks
        ]
    }

@router.get("/hosts/trash")
def list_hosts_trash(db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    hosts = (
        db.query(Host)
        .filter(Host.active.is_(False))
        .order_by(Host.deleted_at.desc(), Host.name.asc())
        .all()
    )
    return hosts


@router.post("/hosts/{host_id}/deactivate")
def deactivate_host(
    host_id: int,
    host_name: str = Query(...),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    target_name = (host_name or "").strip()
    host = db.query(Host).filter(Host.id == host_id).first()

    if not host or host.name != target_name:
        host_by_name = db.query(Host).filter(Host.name == target_name).first() if target_name else None
        if host_by_name:
            host = host_by_name
        elif not host:
            raise HTTPException(status_code=404, detail="Host não encontrado")
        else:
            raise HTTPException(
                status_code=409,
                detail=f"Conflito de identificação: id={host_id} pertence a '{host.name}', não a '{target_name}'",
            )

    if not host.active:
        return {"detail": "Host já está na lixeira"}

    _deactivate_host_entity(host)
    db.commit()

    return {"detail": "Host movido para a lixeira com sucesso"}


@router.post("/hosts/bulk-deactivate")
def bulk_deactivate_hosts(
    data: BulkDeactivateRequest,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    raw_ids = [int(i) for i in (data.host_ids or []) if i is not None]
    raw_names = [str(n).strip() for n in (data.host_names or []) if n and str(n).strip()]

    if not raw_ids and not raw_names:
        raise HTTPException(status_code=400, detail="Nenhum host selecionado para mover para a lixeira")

    query = db.query(Host).filter(Host.active.is_(True))
    if raw_ids and raw_names:
        query = query.filter((Host.id.in_(raw_ids)) | (Host.name.in_(raw_names)))
    elif raw_ids:
        query = query.filter(Host.id.in_(raw_ids))
    else:
        query = query.filter(Host.name.in_(raw_names))

    hosts_to_deactivate = query.all()
    if not hosts_to_deactivate:
        return {
            "detail": "Nenhum host ativo encontrado para os itens selecionados",
            "deactivated_count": 0,
            "deactivated_names": [],
        }

    deactivated_names = []
    for h in hosts_to_deactivate:
        _deactivate_host_entity(h)
        deactivated_names.append(h.name)

    db.commit()
    return {
        "detail": f"{len(deactivated_names)} host(s) movido(s) para a lixeira com sucesso",
        "deactivated_count": len(deactivated_names),
        "deactivated_names": deactivated_names,
    }


@router.post("/hosts/{host_id}/restore")
def restore_host(
    host_id: int,
    host_name: str = Query(...),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    target_name = (host_name or "").strip()
    host = db.query(Host).filter(Host.id == host_id).first()

    if not host or host.name != target_name:
        host_by_name = db.query(Host).filter(Host.name == target_name).first() if target_name else None
        if host_by_name:
            host = host_by_name
        elif not host:
            raise HTTPException(status_code=404, detail="Host não encontrado")
        else:
            raise HTTPException(
                status_code=409,
                detail=f"Conflito de identificação: id={host_id} pertence a '{host.name}', não a '{target_name}'",
            )

    if host.active:
        return {"detail": "Host já está ativo"}

    host.active = True
    host.active_time = None
    host.deleted_at = None
    circuit_breaker.clear_host(host.id)
    reset_snmp_backoff(host.id)
    _reset_host_operational_state(host)

    db.commit()
    mq_manager.publish_host_checks_sync([host.id])
    return {"detail": "Host restaurado com sucesso"}


@router.delete("/hosts/{host_id}/hard-delete")
def hard_delete_host(
    host_id: int,
    host_name: str = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_admin),
):
    target_name = (host_name or "").strip()
    host = db.query(Host).filter(Host.id == host_id).first()

    if not host or host.name != target_name:
        host_by_name = db.query(Host).filter(Host.name == target_name).first() if target_name else None
        if host_by_name:
            host = host_by_name
        elif not host:
            raise HTTPException(status_code=404, detail="Host não encontrado")
        else:
            raise HTTPException(
                status_code=409,
                detail=f"Conflito de identificação: id={host_id} pertence a '{host.name}', não a '{target_name}'",
            )

    if host.active:
        raise HTTPException(
            status_code=409,
            detail="Host ativo não pode ser removido permanentemente. Mova para lixeira antes.",
        )

    db.query(CheckResult).filter(CheckResult.host_id == host.id).delete(synchronize_session=False)
    db.query(Alert).filter(Alert.host_id == host.id).delete(synchronize_session=False)
    db.query(SNMPMetric).filter(SNMPMetric.host_id == host.id).delete(synchronize_session=False)
    db.query(Incident).filter(Incident.host_name == host.name).delete(synchronize_session=False)
    circuit_breaker.clear_host(host.id)
    reset_snmp_backoff(host.id)
    db.delete(host)
    db.commit()

    return {"detail": "Host removido permanentemente"}


@router.delete("/hosts/trash/empty")
def empty_trash(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_admin),
):
    trash_hosts = db.query(Host).filter(Host.active.is_(False)).all()
    if not trash_hosts:
        return {"detail": "Lixeira já está vazia", "deleted_count": 0}

    trash_ids = [h.id for h in trash_hosts]
    trash_names = [h.name for h in trash_hosts]

    db.query(CheckResult).filter(CheckResult.host_id.in_(trash_ids)).delete(synchronize_session=False)
    db.query(Alert).filter(Alert.host_id.in_(trash_ids)).delete(synchronize_session=False)
    db.query(SNMPMetric).filter(SNMPMetric.host_id.in_(trash_ids)).delete(synchronize_session=False)
    db.query(Incident).filter(Incident.host_name.in_(trash_names)).delete(synchronize_session=False)

    for h in trash_hosts:
        circuit_breaker.clear_host(h.id)
        reset_snmp_backoff(h.id)
        db.delete(h)

    db.commit()
    return {
        "detail": f"{len(trash_hosts)} host(s) removido(s) permanentemente da lixeira",
        "deleted_count": len(trash_hosts),
    }


@router.delete("/host/delete/{host_name}")
def delete_host(host_name: str, db: Session = Depends(get_db), user: User = Depends(get_current_admin)):
    host = db.query(Host).filter(Host.name == host_name).first()

    if not host:
        raise HTTPException(status_code=404, detail="Host não encontrado")

    if not host.active:
        return {"detail": "Host já está na lixeira"}

    _deactivate_host_entity(host)
    db.commit()

    return {"detail": "Host movido para a lixeira com sucesso"}

@router.put("/host/update/{host_name}")
def update_host(
    host_name: str,
    data: HostUpdate,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    clean_host_name = (host_name or "").strip()
    host = db.query(Host).filter(Host.name == clean_host_name).first()
    if not host and clean_host_name != host_name:
        host = db.query(Host).filter(Host.name == host_name).first()

    if not host:
        raise HTTPException(status_code=404, detail="Host não encontrado")

    # 1. Renomeação do host com validação de unicidade
    target_name = (data.name or "").strip() if getattr(data, "name", None) else None
    old_name = host.name
    if target_name and target_name != host.name:
        existing_other = db.query(Host).filter(Host.name == target_name, Host.id != host.id).first()
        if existing_other:
            raise HTTPException(status_code=409, detail=f"Já existe outro host com o nome '{target_name}'")
        host.name = target_name
        # Atualiza referências relacionais em Incident e CheckResult
        db.query(Incident).filter(Incident.host_name == old_name).update(
            {Incident.host_name: target_name}, synchronize_session=False
        )
        db.query(CheckResult).filter(CheckResult.host_id == host.id).update(
            {CheckResult.host_name: target_name}, synchronize_session=False
        )

    # 2. Endereço e validação ágil (reutiliza cache imediato se o endereço não mudou)
    normalized_address = (data.address or "").strip()
    if not normalized_address:
        raise HTTPException(status_code=400, detail="Endereço do host é obrigatório")

    resolved = host.hostname_resolved
    if normalized_address != host.address:
        if is_ip(normalized_address):
            resolved = None  # IP direto: não trava requisição com PTR reverso bloqueante
        else:
            dns_result = resolve_dns_cached_sync(normalized_address, db)
            ips = extract_ips_from_dns_result(dns_result)

            if not ips:
                raise HTTPException(status_code=400, detail="Endereço inválido")
            resolved = normalized_address

    # 3. Portas
    if data.ports is None and data.port is None:
        ports = _host_ports(host)
    else:
        ports = _normalize_ports(data.ports, data.port)

    host.address = normalized_address
    _store_host_ports(host, ports)
    host.hostname_resolved = resolved

    # 4. Políticas HTTP e SNMP
    selected_http = _resolve_http_input(data)
    _apply_http_policy(host, data.http_enabled, selected_http)

    if data.snmp_enabled is not None or getattr(data, "snmp_community", None) is not None:
        _apply_snmp_policy(host, data.snmp_enabled, getattr(data, "snmp_community", None))

    circuit_breaker.clear_host(host.id)
    reset_snmp_backoff(host.id)
    db.commit()

    return {
        "detail": "Host atualizado com sucesso",
        "old_name": old_name,
        "name": host.name,
    }

@router.get("/alerts/list")
def list_alerts(db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    rows = (
        db.query(Alert, Host)
        .join(Host, Host.id == Alert.host_id)
        .order_by(Alert.timestamp.desc())
        .limit(50)
        .all()
    )

    avail_cache = {}
    cause_cache = {}
    result = []
    for alert, host in rows:
        if host.name not in avail_cache:
            avail_cache[host.name] = availability_last_10_min(db, host.name)
        availability_10m = avail_cache[host.name]

        if host.id not in cause_cache:
            cause_cache[host.id] = infer_probable_cause(db, host)
        probable_cause = cause_cache[host.id]

        icmp_blocked_but_service_up = bool(getattr(host, "icmp_blocked_but_service_up", False))

        result.append({
            "host_id": alert.host_id,
            "host_name": host.name,
            "host_address": host.address,
            "host_port": host.port,
            "alert_type": alert.alert_type,
            "old_status": alert.old_status,
            "new_status": alert.new_status,
            "timestamp": alert.timestamp.isoformat(),
            "status": host.status,
            "severity": host.severity,
            "health_score": host.health_score,
            "availability_10m": availability_10m,
            "sla_rolling_ping": host.sla_rolling_ping,
            "sla_rolling_tcp": host.sla_rolling_tcp,
            "sla_rolling_http": host.sla_rolling_http,
            "jitter_ms_ping": host.jitter_ms_ping,
            "jitter_ms_tcp": host.jitter_ms_tcp,
            "jitter_ms_http": host.jitter_ms_http,
            "trend_http": host.trend_http,
            "cpu_usage": host.cpu_usage,
            "ram_usage": host.ram_usage,
            "disk_usage": host.disk_usage,
            "network_traffic": host.network_traffic,
            "network_in_bps": host.network_in_bps,
            "network_out_bps": host.network_out_bps,
            "last_check": host.last_check.isoformat() if host.last_check else None,
            "last_snmp_check": host.last_snmp_check.isoformat() if host.last_snmp_check else None,
            "probable_cause": probable_cause,
            "icmp_blocked_but_service_up": icmp_blocked_but_service_up,
        })

    return result

@router.get("/hosts/metrics/{host_name}")
def host_metrics(host_name: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return {
        "total_incidents": total_incidents(db, host_name),
        "total_downtime_seconds": total_downtime(db, host_name),
        "availability_10m_percent": availability_last_10_min(db, host_name),
    }

@router.get("/hosts/metrics/availability/type/{host_name}")
def availability_type(host_name: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):

    host = db.query(Host).filter_by(name=host_name).first()
    if not host:
        return {"ping": [], "tcp": [], "http": []}

    return {
        "ping": calculate_availability_points(db, host.id, "ping"),
        "tcp": calculate_availability_points(db, host.id, "tcp"),
        "http": calculate_availability_points(db, host.id, "http")
    }
    
@router.get("/hosts/metrics/availability/host/{host_name}")
def availability_host(host_name: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    window_start = now - timedelta(minutes=60)

    # Otimização de performance: 1 única query para carregar os incidentes da janela em vez de 60 queries
    incidents = (
        db.query(Incident)
        .filter(
            Incident.host_name == host_name,
            Incident.started_time <= now,
            (Incident.ended_time.is_(None)) | (Incident.ended_time >= window_start)
        )
        .all()
    )

    points = []
    for i in range(60):
        end = now - timedelta(minutes=i)
        start = end - timedelta(minutes=1)
        avail = calculate_availability_from_incidents(incidents, end, start, total_period=60)
        points.append({
            "timestamp": start.isoformat(),
            "availability": round(avail, 2)
        })

    return list(reversed(points))

@router.get("/hosts/metrics/{host_name}/downtime")
def downtime_history(host_name: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    since = now - timedelta(hours=1)

    incidents = (
        db.query(Incident)
        .filter(
            Incident.host_name == host_name,
            (Incident.ended_time.is_(None)) | (Incident.ended_time >= since)
        )
        .order_by(Incident.started_time.desc())
        .all()
    )

    return [
        {
            "start": i.started_time.isoformat(),
            "end": (i.ended_time or now).isoformat(),
            "duration_seconds": i.duration_seconds if i.duration_seconds is not None else int((now - i.started_time).total_seconds())
        }
        for i in incidents
    ]

@router.post("/auth/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    username = data.username.strip()
    password = data.password
    user = db.query(User).filter(User.username == username).first()

    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    if user and user.locked:
        if user.locked_until and user.locked_until <= now_utc:
            user.locked = False
            user.locked_until = None
            user.attempts = 0
            db.commit()
        else:
            raise HTTPException(status_code=403, detail="Conta bloqueada. Tente novamente mais tarde.")

    if not user or not verify_password(password, user.password_hash):
        if user:
            user.attempts = (user.attempts or 0) + 1
            if user.attempts >= 5:
                user.locked = True
                user.locked_until = now_utc + timedelta(minutes=1)
                db.commit()
                raise HTTPException(status_code=403, detail="Conta bloqueada após 5 tentativas. Aguarde 1 minuto.")
            db.commit()
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    user.attempts = 0
    user.locked = False
    user.locked_until = None
    db.commit()

    # Aqui geramos o token JWT
    token = create_access_token({"sub": user.username})

    return {
        "access_token": token,
        "token_type": "bearer",
        "must_change_password": user.must_change_password
    }

@router.post("/auth/first-password")
def first_change_password(data: PasswordChangeRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):

    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    if not user.must_change_password:
        raise HTTPException(
            status_code=400,
            detail="A troca inicial de senha já foi realizada. Utilize a rota padrão de alteração de senha (/auth/change-password)."
        )

    if not data.new_password or len(data.new_password.strip()) < 4:
        raise HTTPException(status_code=400, detail="A nova senha deve conter pelo menos 4 caracteres")

    if len(data.new_password.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="A nova senha não pode exceder 72 bytes")

    user.password_hash = hash_password(data.new_password)
    user.must_change_password = False
    user.attempts = 0

    db.commit()

    return {"message": "Senha alterada com sucesso",
            "logout": True
    }

@router.post("/auth/change-password")
def change_password(data: PasswordChangeRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):

    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    # Verifica se conta está bloqueada (com desbloqueio automático após expiração)
    if user.locked:
        if user.locked_until and user.locked_until <= now_utc:
            user.locked = False
            user.locked_until = None
            user.attempts = 0
            db.commit()
        else:
            raise HTTPException(status_code=403, detail="Conta bloqueada por muitas tentativas")

    # Verifica senha atual
    if not data.current_password:
        raise HTTPException(status_code=400, detail="Senha atual é obrigatória")

    if not data.new_password or len(data.new_password.strip()) < 4:
        raise HTTPException(status_code=400, detail="A nova senha deve conter pelo menos 4 caracteres")

    if len(data.new_password.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="A nova senha não pode exceder 72 bytes")

    if not verify_password(data.current_password, user.password_hash):

        user.attempts = (user.attempts or 0) + 1

        if user.attempts >= 5:
            user.locked = True
            user.locked_until = now_utc + timedelta(minutes=1)
            db.commit()
            raise HTTPException(status_code=403, detail="Conta bloqueada após 5 tentativas. Aguarde 1 minuto.")

        db.commit()

        raise HTTPException(
            status_code=401,
            detail=f"Senha atual incorreta ({user.attempts}/5)"
        )

    # Senha correta → reseta tentativas e bloqueio
    user.attempts = 0
    user.locked = False
    user.locked_until = None
    user.password_hash = hash_password(data.new_password)
    user.must_change_password = False

    db.commit()

    return {"message": "Senha alterada com sucesso"}

@router.get("/incidents/latest")
def get_latest_incidents(db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    incidents = (
        db.query(Incident)
        .order_by(Incident.started_time.desc())
        .limit(25)
        .all()
    )
    
    return [
        {
            "id": i.id,
            "host_name": i.host_name,
            "status": i.status,
            "reason": i.reason,
            "incident_type": parse_incident_type(i.reason),
            "reason_text": strip_incident_prefix(i.reason),
            "started_time": i.started_time.isoformat() if i.started_time else None,
            "ended_time": i.ended_time.isoformat() if i.ended_time else None,
            "duration": i.duration_seconds
        }
        for i in incidents
    ]

@router.get("/metrics/snmp/{host_name}")
def get_snmp_history(host_name: str, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    host = db.query(Host).filter(Host.name == host_name, Host.active == True).first()

    if not host:
        raise HTTPException(status_code=404, detail="Host não encontrado")

    rows = (
        db.query(SNMPMetric)
        .filter(SNMPMetric.host_id == host.id)
        .order_by(SNMPMetric.timestamp.desc())
        .limit(180)
        .all()
    )
    rows.reverse()

    return {
        "host": host.name,
        "points": [
            {
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                "cpu": r.cpu,
                "ram": r.ram,
                "disk": r.disk,
                "network_in_bps": r.network_in_bps,
                "network_out_bps": r.network_out_bps,
                "network_total_bps": r.network_total_bps
            }
            for r in rows
        ]
    }

@router.get("/dashboard/summary")
def dashboard_summary(db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    statuses = [r[0] for r in db.query(Host.status).filter(Host.active.is_(True)).all()]

    total_hosts = len(statuses)
    up = statuses.count("UP")
    degraded = statuses.count("DEGRADED")
    down = statuses.count("DOWN")

    open_incidents = (
        db.query(Incident)
        .filter(Incident.status == "OPEN")
        .count()
    )
    closed_incidents = (
        db.query(Incident)
        .filter(Incident.status == "CLOSED")
        .count()
    )

    return {
        "total_hosts": total_hosts,
        "up": up,
        "degraded": degraded,
        "down": down,
        "open_incidents": open_incidents,
        "closed_incidents": closed_incidents
    }

@router.get("/health/telegram")
def check_telegram(user: User = Depends(get_current_user)):
    return telegram_health_check()
