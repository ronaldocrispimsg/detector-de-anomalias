"""
Backend SNMP - Motor de Auto-Descoberta via SNMP WALK
===============================================================================
Executa a descoberta profunda da arvore MIB do dispositivo quando nenhum OID
conhecido do catalogo responde, mapeando automaticamente novos OIDs de CPU, RAM,
Armazenamento e Redes para Linux, Windows, Cisco, Mikrotik, Fortinet, etc.
"""

import logging
from typing import Dict, Any, Optional

from Backend.snmp.snmp_client import walk_snmp, get_snmp_value

logger = logging.getLogger("netspot.snmp.discovery")


async def discover_device_oids(ip: str, community: Optional[str]) -> Dict[str, Any]:
    """
    Executa varredura profunda no dispositivo e descobre OIDs funcionais.
    Retorna dicionario com os OIDs resolvidos para o dispositivo.
    """
    logger.info("[SNMP DISCOVERY] Iniciando auto-descoberta SNMP WALK para ip=%s", ip)
    discovered: Dict[str, Any] = {}

    # 1. Testar UCD-SNMP CPU Idle (Linux)
    val_ucd_cpu = await get_snmp_value(ip, community, "1.3.6.1.4.1.2021.11.11.0")
    if val_ucd_cpu is not None:
        try:
            float(val_ucd_cpu)
            discovered["cpu_oid"] = "1.3.6.1.4.1.2021.11.11.0"
            discovered["cpu_type"] = "ucd_idle"
            logger.info("[SNMP DISCOVERY] CPU OID descoberto (UCD-Idle): %s", discovered["cpu_oid"])
        except ValueError:
            pass

    # 2. Se UCD falhar, tentar Host-Resources Processors (Windows/Linux)
    if "cpu_oid" not in discovered:
        hr_cpus = await walk_snmp(ip, community, "1.3.6.1.2.1.25.3.3.1.2")
        if hr_cpus:
            discovered["cpu_oid"] = hr_cpus[0][0]
            discovered["cpu_type"] = "hr_load"
            logger.info("[SNMP DISCOVERY] CPU OID descoberto (HR-Processor): %s", discovered["cpu_oid"])

    # 3. Se ainda falhar, testar fabricantes específicos (Mikrotik, Cisco, Fortinet, Juniper, Huawei, HP)
    if "cpu_oid" not in discovered:
        multivendor_cpu = [
            ("1.3.6.1.4.1.14988.1.1.1.3.1.0", "direct", "Mikrotik v7"),
            ("1.3.6.1.4.1.14988.1.1.1.3.0", "direct", "Mikrotik v6"),
            ("1.3.6.1.4.1.9.9.109.1.1.1.1.5.1", "direct", "Cisco cpmCPU"),
            ("1.3.6.1.4.1.9.2.1.58.0", "direct", "Cisco avgBusy5"),
            ("1.3.6.1.4.1.12356.101.4.1.3.0", "direct", "Fortinet fgCpu"),
            ("1.3.6.1.4.1.2636.3.1.13.1.8.9.1.0.0", "direct", "Juniper CPU"),
            ("1.3.6.1.4.1.2011.6.3.4.1.2.0.0.0", "direct", "Huawei CPU"),
            ("1.3.6.1.4.1.11.2.14.11.5.1.9.6.1.0", "direct", "HP ProCurve CPU"),
        ]
        for oid, ctype, label in multivendor_cpu:
            val = await get_snmp_value(ip, community, oid)
            if val is not None:
                try:
                    fval = float(val)
                    if 0.0 <= fval <= 100.0:
                        discovered["cpu_oid"] = oid
                        discovered["cpu_type"] = ctype
                        logger.info("[SNMP DISCOVERY] CPU OID descoberto (%s): %s", label, oid)
                        break
                except (ValueError, TypeError):
                    pass

    # 4. Testar UCD-SNMP RAM
    ram_tot = await get_snmp_value(ip, community, "1.3.6.1.4.1.2021.4.5.0")
    ram_free = await get_snmp_value(ip, community, "1.3.6.1.4.1.2021.4.6.0")
    if ram_tot is not None and ram_free is not None:
        discovered["ram_type"] = "ucd"
        logger.info("[SNMP DISCOVERY] RAM MIB descoberta (UCD-SNMP Real Memory)")

    # 5. Descobrir indice de armazenamento (Disco) em Host-Resources com suporte multivendor
    storages = await walk_snmp(ip, community, "1.3.6.1.2.1.25.2.3.1.3")
    storage_keywords = (
        "/", "c:", "c:\\", "c:/", "d:", "d:\\", "fixed disk", "disco local",
        "rootfs", "root", "storage", "flash", "hard disk", "volume", "system", "data"
    )
    for oid, descr in storages:
        clean_descr = descr.strip('"').strip().lower()
        if any(clean_descr == kw or clean_descr.startswith(kw) for kw in storage_keywords):
            idx = oid.split(".")[-1]
            discovered["storage_index"] = idx
            logger.info("[SNMP DISCOVERY] Storage Index descoberto: index=%s (%s)", idx, clean_descr)
            break

    # 6. Descobrir melhor interface de rede
    ifaces_64 = await walk_snmp(ip, community, "1.3.6.1.2.1.31.1.1.1.1")
    candidates = []
    for oid, name_val in ifaces_64:
        if_name = name_val.strip('"')
        idx = oid.split(".")[-1]
        if if_name == "lo" or if_name.startswith("docker") or if_name.startswith("veth") or if_name.startswith("br-"):
            continue
        candidates.append((idx, if_name))

    preferred_prefixes = ("enp", "eth", "ens", "wlp", "wlan", "Ethernet", "ether", "GigabitEthernet", "FastEthernet", "ge-", "xe-")
    selected_iface_idx = None
    for prefix in preferred_prefixes:
        for idx, name in candidates:
            if name.startswith(prefix) or prefix.lower() in name.lower():
                selected_iface_idx = idx
                break
        if selected_iface_idx:
            break

    if not selected_iface_idx and candidates:
        selected_iface_idx = candidates[0][0]

    if selected_iface_idx:
        discovered["iface_index"] = selected_iface_idx
        logger.info("[SNMP DISCOVERY] Interface de Rede descoberta: index=%s", selected_iface_idx)

    logger.info("[SNMP DISCOVERY] Auto-descoberta finalizada para ip=%s | total_itens=%s", ip, len(discovered))
    return discovered
