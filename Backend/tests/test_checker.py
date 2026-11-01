"""
Backend Test Suite - Testes dos Checadores de Rede (Ping, TCP, HTTP, DNS)
===============================================================================
Testa o comportamento assincrono dos checadores de protocolo em Backend.checker.
"""

import pytest
from Backend.checker import (
    resolve_dns_real_sync,
    resolve_dns_real,
    ping_host,
    tcp_check,
    http_check,
)


def test_resolve_dns_real_sync_google(monkeypatch):
    """Testa a resolucao sincrona de DNS (com fallback deterministico sem depender de rede externa)."""
    ips, ttl = resolve_dns_real_sync("127.0.0.1")
    assert isinstance(ips, list)
    assert "127.0.0.1" in ips
    assert ttl == 0


@pytest.mark.asyncio
async def test_resolve_dns_real_async_google():
    """Testa a resolucao assincrona de DNS (com fallback deterministico sem depender de rede externa)."""
    ips, ttl = await resolve_dns_real("127.0.0.1")
    assert isinstance(ips, list)
    assert "127.0.0.1" in ips
    assert ttl == 0


@pytest.mark.asyncio
async def test_ping_host_loopback():
    """Testa a checagem de Ping assincrona para o IP de loopback (127.0.0.1)."""
    res = await ping_host("127.0.0.1", count=1, timeout=2)
    assert isinstance(res, dict)
    assert "success" in res
    assert "latency" in res


@pytest.mark.asyncio
async def test_tcp_check_invalid_port():
    """Testa a checagem de porta TCP para uma porta fechada/invalida."""
    res = await tcp_check("127.0.0.1", 59999, timeout=1)
    assert isinstance(res, dict)
    assert res["success"] is False
    assert res["latency"] is None


@pytest.mark.asyncio
async def test_http_check_public_url(monkeypatch):
    """Testa a checagem HTTP assincrona de forma deterministica (mock de httpx.AsyncClient)."""
    import httpx

    class FakeResponse:
        status_code = 200

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def get(self, url, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    res = await http_check("https://www.google.com", timeout=5, retries=1)
    assert isinstance(res, dict)
    assert res["success"] is True
    assert res["status_code"] == 200
    assert res["protocol"] == "https"
    assert isinstance(res["latency"], float)
    assert isinstance(res["https_latency"], float)
