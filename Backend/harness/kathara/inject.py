"""Injeção de falha no laboratório (o "gerador" físico).

Cada cenário vira uma lista de comandos `(máquina, comando)` para reproduzir a
anomalia, e uma lista de limpeza. Usa `tc netem`, `brctl`, `ping -f`, `/dev/tcp`
e `dd`, tudo disponível na imagem base.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Injection:
    scenario: str
    setup: list[tuple[str, str]] = field(default_factory=list)
    cleanup: list[tuple[str, str]] = field(default_factory=list)


_ENET = "tc qdisc del dev eth0 root 2>/dev/null; true"
_BNET = "tc qdisc del dev br0 root 2>/dev/null; true"

INJECTIONS: dict[str, Injection] = {
    "NORMAL": Injection("NORMAL"),
    "DDOS_ATTACK": Injection(
        "DDOS_ATTACK",
        setup=[
            ("h2", "(ping -f 10.0.0.1 >/dev/null 2>&1 &) ; sleep 2; true"),
        ],
        cleanup=[("h2", "pkill -f 'ping -f' 2>/dev/null; true")],
    ),
    "PORT_SCAN": Injection(
        "PORT_SCAN",
        setup=[
            ("h2", "for p in $(seq 1 1024); do (echo >/dev/tcp/10.0.0.1/$p) 2>/dev/null; done; true"),
        ],
    ),
    "HOST_DOWN": Injection(
        "HOST_DOWN",
        setup=[("h1", "ip link set eth0 down")],
        cleanup=[("h1", "ip link set eth0 up")],
    ),
    "SERVICE_OUTAGE": Injection(
        "SERVICE_OUTAGE",
        setup=[("h1", "pkill -f 'python3 -m http.server' 2>/dev/null; true")],
        cleanup=[("h1", "python3 -m http.server 80 >/dev/null 2>&1 & true")],
    ),
    "DISK_EXHAUSTION": Injection(
        "DISK_EXHAUSTION",
        setup=[("h1", "dd if=/dev/zero of=/tmp/fill bs=1M count=60 status=none; true")],
        cleanup=[("h1", "rm -f /tmp/fill")],
    ),
    "MEMORY_LEAK": Injection(
        "MEMORY_LEAK",
        setup=[
            ("h1", "(python3 -c 'x=bytearray(120*1024*1024); import time; time.sleep(120)' >/dev/null 2>&1 &) ; true"),
        ],
        cleanup=[("h1", "pkill -f bytearray 2>/dev/null; true")],
    ),
    "NETWORK_CONGESTION": Injection(
        "NETWORK_CONGESTION",
        setup=[("bridge", "tc qdisc add dev eth0 root netem delay 200ms")],
        cleanup=[("bridge", _ENET)],
    ),
    "DATA_EXFILTRATION": Injection(
        "DATA_EXFILTRATION",
        setup=[
            ("h3", "(python3 -c \"import socket; s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); s.bind(('0.0.0.0',9999)); s.listen(5)\nwhile True:\n c,_=s.accept()\n while c.recv(65536):\n  pass\" >/dev/null 2>&1 &) ; sleep 1; true"),
            ("h2", "(dd if=/dev/zero 2>/dev/null | nc -w60 10.0.0.3 9999 >/dev/null 2>&1 &) ; sleep 2; true"),
        ],
        cleanup=[
            ("h2", "pkill -f 'nc -w2' 2>/dev/null; true"),
            ("h3", "pkill -f 'socket.socket' 2>/dev/null; true"),
        ],
    ),
    "COMBINED_FAULT": Injection(
        "COMBINED_FAULT",
        setup=[
            ("h1", "ip link set eth0 down"),
            ("bridge", "tc qdisc add dev eth0 root netem delay 200ms"),
        ],
        cleanup=[("h1", "ip link set eth0 up"), ("bridge", _ENET)],
    ),
}


def injection_for(scenario: str) -> Injection:
    return INJECTIONS.get(scenario, Injection(scenario))


def start_server(scenario_server_host: str = "h1") -> list[tuple[str, str]]:
    return [(scenario_server_host, "python3 -m http.server 80 >/dev/null 2>&1 & true")]
