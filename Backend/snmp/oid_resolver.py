"""
Backend SNMP - Motor de Auto-Resolução e Auto-Correção de OIDs
===============================================================================
Orquestrador inteligente de OIDs que implementa o fluxo de resiliência:
Cache -> Teste -> Auto-Correção por Banco -> Auto-Descoberta (SNMP WALK) -> Update Cache/DB -> Log.
"""

import logging
from typing import Optional, Dict, Any, Tuple

from Backend.snmp.snmp_client import get_snmp_value, walk_snmp, DEFAULT_SNMP_COMMUNITY
from Backend.snmp.oid_cache import get_cached_oids, set_cached_oid
from Backend.snmp.oid_database import (
    KNOWN_OIDS_CPU,
    KNOWN_OIDS_RAM,
    KNOWN_OIDS_STORAGE,
    KNOWN_OIDS_NETWORK,
)
from Backend.snmp.snmp_discovery import discover_device_oids

logger = logging.getLogger("netspot.snmp.resolver")


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        val_str = str(value).strip()
        if not val_str:
            return None
        return float(val_str)
    except (TypeError, ValueError):
        return None


async def resolve_cpu_usage(host_id: int, ip: str, community: Optional[str]) -> Optional[float]:
    """
    Resolve a porcentagem de uso da CPU (0 a 100%) testando MIBs Linux (UCD-Idle),
    Windows (hrProcessorLoad), Cisco, Mikrotik, Fortinet, Juniper e Huawei.
    """
    comm = (community or DEFAULT_SNMP_COMMUNITY).strip() or DEFAULT_SNMP_COMMUNITY

    # 1. Testar UCD-SNMP ssCpuIdle (Linux)
    idle_val = _to_float(await get_snmp_value(ip, comm, "1.3.6.1.4.1.2021.11.11.0"))
    if idle_val is not None:
        return round(max(0.0, min(100.0, 100.0 - idle_val)), 2)

    # 2. Testar HOST-RESOURCES hrProcessorLoad (Windows/Linux)
    cpu_cores = await walk_snmp(ip, comm, "1.3.6.1.2.1.25.3.3.1.2")
    if cpu_cores:
        core_vals = []
        for _, val in cpu_cores:
            flt = _to_float(val)
            if flt is not None and 0.0 <= flt <= 100.0:
                core_vals.append(flt)
        if core_vals:
            return round(sum(core_vals) / len(core_vals), 2)

    # 3. Testar OIDs adicionais de switches e roteadores (Mikrotik, Cisco, Fortinet, etc.)
    additional_cpu_oids = [
        "1.3.6.1.4.1.14988.1.1.1.3.1.0",        # Mikrotik RouterOS v7
        "1.3.6.1.4.1.14988.1.1.1.3.0",          # Mikrotik RouterOS v6
        "1.3.6.1.4.1.9.9.109.1.1.1.1.5.1",      # Cisco cpmCPUTotal5secRev
        "1.3.6.1.4.1.9.2.1.58.0",               # Cisco avgBusy5
        "1.3.6.1.4.1.12356.101.4.1.3.0",        # Fortinet fgSysCpuUsage
        "1.3.6.1.4.1.2636.3.1.13.1.8.9.1.0.0",  # Juniper JunOS
        "1.3.6.1.4.1.2011.6.3.4.1.2.0.0.0",    # Huawei VRP
        "1.3.6.1.4.1.11.2.14.11.5.1.9.6.1.0",  # HP ProCurve
    ]
    for oid in additional_cpu_oids:
        val = _to_float(await get_snmp_value(ip, comm, oid))
        if val is not None and 0.0 <= val <= 100.0:
            return round(val, 2)

    # 4. Executar SNMP WALK para descoberta heurística
    discovered = await discover_device_oids(ip, comm)
    if "cpu_oid" in discovered:
        val = _to_float(await get_snmp_value(ip, comm, discovered["cpu_oid"]))
        if val is not None:
            if discovered.get("cpu_type") == "ucd_idle":
                return round(max(0.0, min(100.0, 100.0 - val)), 2)
            return round(max(0.0, min(100.0, val)), 2)

    return None


async def resolve_ram_usage(host_id: int, ip: str, community: Optional[str]) -> Optional[float]:
    """
    Resolve a porcentagem de uso de memória RAM (0 a 100%) testando MIBs Linux (UCD-Memory),
    Windows (Physical Memory), Cisco Memory Pool, Fortinet, Huawei e Juniper.
    """
    comm = (community or DEFAULT_SNMP_COMMUNITY).strip() or DEFAULT_SNMP_COMMUNITY

    # 1. UCD-SNMP Memory (Linux) com suporte resiliente a buffer e cache
    ram_tot = _to_float(await get_snmp_value(ip, comm, "1.3.6.1.4.1.2021.4.5.0"))
    ram_free = _to_float(await get_snmp_value(ip, comm, "1.3.6.1.4.1.2021.4.6.0"))
    ram_buf = _to_float(await get_snmp_value(ip, comm, "1.3.6.1.4.1.2021.4.14.0"))
    ram_cache = _to_float(await get_snmp_value(ip, comm, "1.3.6.1.4.1.2021.4.15.0"))

    if ram_tot is not None and ram_free is not None and ram_tot > 0:
        buf = ram_buf or 0.0
        cch = ram_cache or 0.0
        used = max(0.0, ram_tot - ram_free - buf - cch)
        return round((used / ram_tot) * 100.0, 2)

    # 2. HOST-RESOURCES Physical Memory (Windows/Linux/Mikrotik)
    rows = await walk_snmp(ip, comm, "1.3.6.1.2.1.25.2.3.1.3")
    ram_idx = None
    keywords = (
        "physical memory", "memória física", "memoria fisica", "ram",
        "system memory", "main memory", "real memory", "memoria principal"
    )
    for oid, descr in rows:
        clean = descr.strip('"').strip().lower()
        if any(kw in clean for kw in keywords):
            ram_idx = oid.split(".")[-1]
            break

    if ram_idx:
        tot_units = _to_float(await get_snmp_value(ip, comm, f"1.3.6.1.2.1.25.2.3.1.5.{ram_idx}"))
        used_units = _to_float(await get_snmp_value(ip, comm, f"1.3.6.1.2.1.25.2.3.1.6.{ram_idx}"))
        if tot_units is not None and used_units is not None and tot_units > 0:
            return round((used_units / tot_units) * 100.0, 2)

    # 3. Cisco Memory Pool
    cisco_used = _to_float(await get_snmp_value(ip, comm, "1.3.6.1.4.1.9.9.48.1.1.1.5.1"))
    cisco_free = _to_float(await get_snmp_value(ip, comm, "1.3.6.1.4.1.9.9.48.1.1.1.6.1"))
    if cisco_used is not None and cisco_free is not None and (cisco_used + cisco_free) > 0:
        return round((cisco_used / (cisco_used + cisco_free)) * 100.0, 2)

    # 4. OIDs de Memória Direta em %
    additional_ram_oids = [
        "1.3.6.1.4.1.12356.101.4.1.4.0",        # Fortinet fgSysMemUsage
        "1.3.6.1.4.1.2011.6.3.5.1.1.2.0.0.0",    # Huawei hwMemoryDevDuty
        "1.3.6.1.4.1.2636.3.1.13.1.11.9.1.0.0",  # Juniper JunOS Buffer
    ]
    for oid in additional_ram_oids:
        val = _to_float(await get_snmp_value(ip, comm, oid))
        if val is not None and 0.0 <= val <= 100.0:
            return round(val, 2)

    return None
