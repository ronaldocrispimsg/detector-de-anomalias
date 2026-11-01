"""Coleta das 12 features de telemetria dentro do laboratório.

O agente lê o mesmo vetor do `agent/telemetry.py`, só que medido de verdade. A
coleta roda um probe shell numa máquina e devolve `chave=valor`, que
`parse_metrics` normaliza para o schema canônico.
"""

from __future__ import annotations

from typing import Any

from Backend.services.agent.telemetry import FEATURE_FIELDS, Telemetry

# `__SERVER__` é substituído pelo IP do servidor. Roda em uma máquina qualquer.
PROBE = r"""
SRV=__SERVER__
PING=$(ping -c 3 -W 1 "$SRV" 2>/dev/null || true)
lat=$(echo "$PING" | awk -F'/' '/rtt|round-trip/{print $5}')
mdev=$(echo "$PING" | awk -F'/' '/rtt|round-trip/{print $7}')
loss=$(echo "$PING" | awk '/packet loss/{for(i=1;i<=NF;i++) if($i=="loss,"){print $(i-1); exit}}' | tr -d '%')
[ -z "$lat" ] && lat=0
[ -z "$mdev" ] && mdev=0
[ -z "$loss" ] && loss=100
CPU=$(top -bn1 2>/dev/null | awk '/Cpu\(s\)|%Cpu/{for(i=1;i<=NF;i++) if($i ~ /id/){gsub(/[^0-9.]/,"",$i); printf "%.1f", 100-$i; exit}}')
[ -z "$CPU" ] && CPU=0
MEM=$(awk '/MemTotal/{t=$2}/MemAvailable/{a=$2}END{if(t>0)printf "%.1f",(t-a)*100/t; else print 0}' /proc/meminfo)
DISK=$(df / | awk 'NR==2{gsub("%","",$5); print $5}')
R1=$(awk 'NR>2{sub(/^[ \t]*/,"");split($0,p,":");n=split(p[2],f," ");i+=f[1];o+=f[9]}END{print i+0" "o+0}' /proc/net/dev)
sleep 1
R2=$(awk 'NR>2{sub(/^[ \t]*/,"");split($0,p,":");n=split(p[2],f," ");i+=f[1];o+=f[9]}END{print i+0" "o+0}' /proc/net/dev)
IN=$(echo "$R1 $R2" | awk '{print ($3-$1)*8}')
OUT=$(echo "$R1 $R2" | awk '{print ($4-$2)*8}')
[ -z "$IN" ] && IN=0
[ -z "$OUT" ] && OUT=0
CONN=$(ss -tan 2>/dev/null | grep -c ESTAB || true)
[ -z "$CONN" ] && CONN=0
HTTP=$(curl -s -o /dev/null -m 3 -w "%{http_code} %{time_total}" "http://$SRV/" 2>/dev/null || true)
code=$(echo "$HTTP" | awk '{print $1}')
t=$(echo "$HTTP" | awk '{print $2}')
[ -z "$code" ] && code=0
[ -z "$t" ] && t=0
PORT=0
if command -v nc >/dev/null 2>&1; then nc -z -w1 "$SRV" 80 2>/dev/null && PORT=1; else (echo >"/dev/tcp/$SRV/80") >/dev/null 2>&1 && PORT=1; fi
echo "latency_ms=$lat"
echo "packet_loss_pct=$loss"
echo "jitter_ms=$mdev"
echo "cpu_usage_pct=$CPU"
echo "ram_usage_pct=$MEM"
echo "disk_usage_pct=$DISK"
echo "network_in_bps=$IN"
echo "network_out_bps=$OUT"
echo "http_status_code=$code"
echo "http_response_time_ms=$(awk -v s=$t 'BEGIN{printf "%.1f", s*1000}')"
echo "tcp_port_open=$PORT"
echo "active_connections=$CONN"
"""


def probe_script(server: str = "10.0.0.1") -> str:
    return PROBE.replace("__SERVER__", server)


def parse_metrics(text: str) -> dict[str, Any]:
    """Converte a saída `chave=valor` no vetor canônico de 12 features."""
    raw: dict[str, str] = {}
    for line in (text or "").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            raw[key.strip()] = value.strip()

    def number(key: str) -> float:
        try:
            return float(raw.get(key, "0") or 0.0)
        except ValueError:
            return 0.0

    mapping: dict[str, Any] = {
        "latency_ms": number("latency_ms"),
        "packet_loss_pct": number("packet_loss_pct"),
        "jitter_ms": number("jitter_ms"),
        "cpu_usage_pct": number("cpu_usage_pct"),
        "ram_usage_pct": number("ram_usage_pct"),
        "disk_usage_pct": number("disk_usage_pct"),
        "network_in_bps": number("network_in_bps"),
        "network_out_bps": number("network_out_bps"),
        "http_status_code": int(round(number("http_status_code"))),
        "http_response_time_ms": number("http_response_time_ms"),
        "tcp_port_open": bool(int(round(number("tcp_port_open")))),
        "active_connections": int(round(number("active_connections"))),
    }
    return Telemetry.from_mapping(mapping).to_mapping()


def collect(runner, machine: str, *, server: str = "10.0.0.1") -> dict[str, Any]:
    """Roda o probe numa máquina via `runner(machine, command) -> stdout:str`."""
    text = runner(machine, probe_script(server))
    return parse_metrics(text)


def sh_wrap(command: str) -> list[str]:
    """Empacota um comando shell para o `exec` do Kathará (que faz shlex.split)."""
    return ["sh", "-c", command]
