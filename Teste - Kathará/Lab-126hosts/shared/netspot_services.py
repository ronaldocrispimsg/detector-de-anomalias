#!/usr/bin/env python3
"""
Daemon multiprotocolo leve para simulação de serviços e portas no laboratório Kathará (126 hosts).
Suporta servidores HTTP (200 OK), HTTPS/TLS autoassinado (200 OK) e listeners TCP (PostgreSQL, MySQL, Redis, AMQP).
"""
import argparse
import asyncio
import json
import os
import socket
import ssl
import subprocess
import sys

CERT_FILE = "/tmp/netspot_lab_cert.pem"
KEY_FILE = "/tmp/netspot_lab_key.pem"


def ensure_self_signed_cert() -> ssl.SSLContext:
    if not (os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE)):
        subprocess.run(
            [
                "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                "-keyout", KEY_FILE, "-out", CERT_FILE, "-days", "365",
                "-subj", f"/CN={socket.gethostname()}/O=NetSpotLab"
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)
    return ctx


async def handle_http(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, port: int, scheme: str) -> None:
    try:
        await asyncio.wait_for(reader.read(1024), timeout=2.0)
        payload = json.dumps({
            "status": "UP",
            "hostname": socket.gethostname(),
            "protocol": scheme,
            "port": port,
            "service": "NetSpot Kathara 126-Host Lab"
        }).encode("utf-8")
        headers = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(payload)}\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).encode("ascii")
        writer.write(headers + payload)
        await writer.drain()
    except Exception:
        pass
    finally:
        writer.close()


async def handle_tcp(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, port: int) -> None:
    try:
        banner = f"NETSPOT-TCP-SERVICE port={port} host={socket.gethostname()} READY\r\n".encode("ascii")
        writer.write(banner)
        await writer.drain()
        await asyncio.wait_for(reader.read(256), timeout=0.5)
    except Exception:
        pass
    finally:
        writer.close()


async def main_async(http_ports: list[int], https_ports: list[int], tcp_ports: list[int]) -> None:
    servers = []
    ssl_ctx = ensure_self_signed_cert() if https_ports else None

    for p in set(http_ports):
        srv = await asyncio.start_server(
            lambda r, w, port=p: handle_http(r, w, port, "http"),
            host="0.0.0.0",
            port=p,
        )
        servers.append(srv)

    for p in set(https_ports):
        srv = await asyncio.start_server(
            lambda r, w, port=p: handle_http(r, w, port, "https"),
            host="0.0.0.0",
            port=p,
            ssl=ssl_ctx,
        )
        servers.append(srv)

    for p in set(tcp_ports):
        srv = await asyncio.start_server(
            lambda r, w, port=p: handle_tcp(r, w, port),
            host="0.0.0.0",
            port=p,
        )
        servers.append(srv)

    if not servers:
        return
    await asyncio.gather(*(s.serve_forever() for s in servers))


def daemonize() -> None:
    if os.fork() > 0:
        sys.exit(0)
    os.setsid()
    if os.fork() > 0:
        sys.exit(0)
    sys.stdout.flush()
    sys.stderr.flush()
    with open("/dev/null", "rb", 0) as devnull_in, open("/var/log/netspot_services.log", "ab", 0) as log_out:
        os.dup2(devnull_in.fileno(), sys.stdin.fileno())
        os.dup2(log_out.fileno(), sys.stdout.fileno())
        os.dup2(log_out.fileno(), sys.stderr.fileno())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--http", type=int, action="append", default=[])
    parser.add_argument("--https", type=int, action="append", default=[])
    parser.add_argument("--tcp", type=int, action="append", default=[])
    parser.add_argument("--daemon", action="store_true")
    args = parser.parse_args()
    if args.daemon:
        daemonize()
    asyncio.run(main_async(args.http, args.https, args.tcp))
