"""
Backend SNMP - Catálogo Completo e Robusto de OIDs e MIBs Multivendor
===============================================================================
Este módulo mantém o catálogo universal de OIDs conhecidos para CPU, RAM,
Armazenamento/Disco e Interfaces de Rede, cobrindo:
- Linux (UCD-SNMP, NET-SNMP, HOST-RESOURCES-MIB)
- Windows (HOST-RESOURCES-MIB multilingual)
- Cisco Systems (IOS, IOS-XE, NX-OS, ASA)
- Mikrotik (RouterOS v6 e v7)
- Fortinet (FortiGate fgSystem MIB)
- Juniper Networks (JunOS jnxOperating MIB)
- Huawei (VRP hwDev MIB)
- HP / Aruba (ProCurve e Comware MIB)
- Ubiquiti (EdgeMAX, UniFi e AirOS)
- Padrões universais MIB-II e IF-MIB
"""

from typing import Dict, List, Any

# ===============================================================================
# 1. OIDs de CPU por Fabricante e MIB
# ===============================================================================
KNOWN_OIDS_CPU: List[Dict[str, str]] = [
    # Linux UCD-SNMP ssCpuIdle (% idle -> usage = 100 - idle)
    {
        "oid": "1.3.6.1.4.1.2021.11.11.0",
        "type": "ucd_cpu_idle",
        "descr": "Linux UCD-SNMP ssCpuIdle (% idle, uso = 100 - idle)"
    },
    # Windows e Linux HOST-RESOURCES-MIB hrProcessorLoad (Média por núcleos)
    {
        "oid": "1.3.6.1.2.1.25.3.3.1.2",
        "type": "hr_processor_load",
        "descr": "HOST-RESOURCES-MIB hrProcessorLoad (Windows/Linux/Mikrotik)"
    },
    # Linux UCD-SNMP ssCpuUser + ssCpuSystem (Uso direto de CPU)
    {
        "oid": "1.3.6.1.4.1.2021.11.9.0",
        "type": "ucd_cpu_user",
        "descr": "Linux UCD-SNMP ssCpuUser (% tempo usuario)"
    },
    # Cisco Systems cpmCPUTotal5secRev / cpmCPUTotal1minRev
    {
        "oid": "1.3.6.1.4.1.9.9.109.1.1.1.1.5.1",
        "type": "cisco_cpu",
        "descr": "Cisco cpmCPUTotal5secRev (5 segundos)"
    },
    {
        "oid": "1.3.6.1.4.1.9.9.109.1.1.1.1.8.1",
        "type": "cisco_cpu",
        "descr": "Cisco cpmCPUTotal1minRev (1 minuto)"
    },
    {
        "oid": "1.3.6.1.4.1.9.2.1.58.0",
        "type": "cisco_cpu",
        "descr": "Cisco avgBusy5 (IOS legado 5 min)"
    },
    # Mikrotik RouterOS
    {
        "oid": "1.3.6.1.4.1.14988.1.1.1.3.1.0",
        "type": "mikrotik_cpu",
        "descr": "Mikrotik RouterOS mtxrHlProcessorLoad"
    },
    {
        "oid": "1.3.6.1.4.1.14988.1.1.1.3.0",
        "type": "mikrotik_cpu",
        "descr": "Mikrotik mtxRxCpuLoad"
    },
    # Fortinet FortiGate fgSysCpuUsage
    {
        "oid": "1.3.6.1.4.1.12356.101.4.1.3.0",
        "type": "direct_percent",
        "descr": "Fortinet FortiGate fgSysCpuUsage (%)"
    },
    # Juniper Networks jnxOperatingCPU
    {
        "oid": "1.3.6.1.4.1.2636.3.1.13.1.8.9.1.0.0",
        "type": "direct_percent",
        "descr": "Juniper JunOS Routing Engine CPU (%)"
    },
    # Huawei VRP hwCpuDevDuty
    {
        "oid": "1.3.6.1.4.1.2011.6.3.4.1.2.0.0.0",
        "type": "direct_percent",
        "descr": "Huawei VRP hwCpuDevDuty (%)"
    },
    # HP / Aruba ProCurve Switch CPU
    {
        "oid": "1.3.6.1.4.1.11.2.14.11.5.1.9.6.1.0",
        "type": "direct_percent",
        "descr": "HP/Aruba Switch hpSwitchCpuStat (%)"
    },
    # Ubiquiti EdgeMAX / UniFi
    {
        "oid": "1.3.6.1.4.1.41112.1.4.1.1.4.1",
        "type": "direct_percent",
        "descr": "Ubiquiti UniFi/EdgeMAX CPU Load (%)"
    }
]

# ===============================================================================
# 2. OIDs de Memória RAM por Fabricante e MIB
# ===============================================================================
KNOWN_OIDS_RAM: List[Dict[str, Any]] = [
    # Linux UCD-SNMP Memory (Real Memory com suporte resiliente a buffer e cache)
    {
        "total_oid": "1.3.6.1.4.1.2021.4.5.0",      # memTotalReal
        "free_oid": "1.3.6.1.4.1.2021.4.6.0",       # memAvailReal
        "buffer_oid": "1.3.6.1.4.1.2021.4.14.0",    # memBuffer
        "cache_oid": "1.3.6.1.4.1.2021.4.15.0",     # memCached
        "alt_free_oid": "1.3.6.1.4.1.2021.4.11.0",  # memTotalFree
        "type": "ucd_memory",
        "descr": "Linux UCD-SNMP Real Memory"
    },
    # Windows e Linux HOST-RESOURCES-MIB (Busca multilingual de descrições)
    {
        "descr_oid": "1.3.6.1.2.1.25.2.3.1.3",
        "size_oid": "1.3.6.1.2.1.25.2.3.1.5",
        "used_oid": "1.3.6.1.2.1.25.2.3.1.6",
        "match_keywords": [
            "physical memory",
            "memória física",
            "memoria fisica",
            "ram",
            "system memory",
            "main memory",
            "real memory",
            "memoria principal"
        ],
        "type": "hr_memory",
        "descr": "HOST-RESOURCES-MIB Physical Memory (Windows/Linux/Mikrotik)"
    },
    # Cisco Systems Memory Pool
    {
        "used_oid": "1.3.6.1.4.1.9.9.48.1.1.1.5.1",
        "free_oid": "1.3.6.1.4.1.9.9.48.1.1.1.6.1",
        "type": "cisco_memory",
        "descr": "Cisco Memory Pool (Processor Memory)"
    },
    # Fortinet FortiGate fgSysMemUsage (uso direto em %)
    {
        "direct_oid": "1.3.6.1.4.1.12356.101.4.1.4.0",
        "type": "direct_percent",
        "descr": "Fortinet FortiGate fgSysMemUsage (%)"
    },
    # Huawei VRP hwMemoryDevDuty (uso direto em %)
    {
        "direct_oid": "1.3.6.1.4.1.2011.6.3.5.1.1.2.0.0.0",
        "type": "direct_percent",
        "descr": "Huawei VRP hwMemoryDevDuty (%)"
    },
    # Juniper Networks Operating Buffer
    {
        "direct_oid": "1.3.6.1.4.1.2636.3.1.13.1.11.9.1.0.0",
        "type": "direct_percent",
        "descr": "Juniper JunOS Memory Buffer Used (%)"
    }
]

# ===============================================================================
# 3. OIDs de Armazenamento / Partição de Disco
# ===============================================================================
KNOWN_OIDS_STORAGE: Dict[str, Any] = {
    "descr_oid": "1.3.6.1.2.1.25.2.3.1.3",
    "type_oid": "1.3.6.1.2.1.25.2.3.1.2",
    "size_oid": "1.3.6.1.2.1.25.2.3.1.5",
    "used_oid": "1.3.6.1.2.1.25.2.3.1.6",
    "units_oid": "1.3.6.1.2.1.25.2.3.1.4",
    "fixed_disk_type": "1.3.6.1.2.1.25.2.1.4",
    "mount_keywords": [
        "/",
        "c:",
        "c:\\",
        "c:/",
        "d:",
        "d:\\",
        "fixed disk",
        "disco local",
        "rootfs",
        "root",
        "storage",
        "flash",
        "hard disk",
        "volume",
        "system",
        "data"
    ],
    "descr": "HOST-RESOURCES-MIB hrStorageTable Universal"
}

# ===============================================================================
# 4. OIDs de Interfaces de Rede (32-bit e 64-bit High Capacity)
# ===============================================================================
KNOWN_OIDS_NETWORK: Dict[str, Any] = {
    "if_oper_status": "1.3.6.1.2.1.2.2.1.8",
    "if_admin_status": "1.3.6.1.2.1.2.2.1.7",
    "if_name_64": "1.3.6.1.2.1.31.1.1.1.1",
    "if_descr_32": "1.3.6.1.2.1.2.2.1.2",
    "if_alias": "1.3.6.1.2.1.31.1.1.1.18",
    "if_speed": "1.3.6.1.2.1.2.2.1.5",
    "if_high_speed": "1.3.6.1.2.1.31.1.1.1.15",
    "in_octets_64": "1.3.6.1.2.1.31.1.1.1.6",
    "out_octets_64": "1.3.6.1.2.1.31.1.1.1.10",
    "in_octets_32": "1.3.6.1.2.1.2.2.1.10",
    "out_octets_32": "1.3.6.1.2.1.2.2.1.16",
    "in_errors": "1.3.6.1.2.1.2.2.1.14",
    "out_errors": "1.3.6.1.2.1.2.2.1.20",
    "in_discards": "1.3.6.1.2.1.2.2.1.13",
    "out_discards": "1.3.6.1.2.1.2.2.1.19",
    "descr": "IF-MIB & RFC 2863 Network Interfaces (64-bit HC & 32-bit Standard)"
}

# ===============================================================================
# 5. OIDs Globais de Identificação e Uptime
# ===============================================================================
KNOWN_OIDS_UPTIME: List[str] = [
    "1.3.6.1.2.1.1.3.0",        # sysUpTimeInstance
    "1.3.6.1.2.1.25.1.1.0"      # hrSystemUptime
]

KNOWN_OIDS_HOSTNAME: List[str] = [
    "1.3.6.1.2.1.1.5.0",        # sysName
    "1.3.6.1.2.1.1.1.0"         # sysDescr
]
