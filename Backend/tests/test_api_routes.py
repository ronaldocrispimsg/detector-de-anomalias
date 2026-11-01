"""
Backend Test Suite - Testes de Integracao das Rotas da API RESTful
===============================================================================
Testa os endpoints HTTP publicos e protegidos do FastAPI em Backend.routes.
"""

import pytest


@pytest.mark.asyncio
async def test_get_dashboard_summary(api_client):
    """Testa a rota GET /dashboard/summary."""
    response = await api_client.get("/dashboard/summary")
    # Se autenticacao for exigida retorna 401 ou 200 com resumo
    assert response.status_code in [200, 401]
    if response.status_code == 200:
        data = response.json()
        assert "total_hosts" in data or "hosts" in data or "summary" in data


@pytest.mark.asyncio
async def test_get_hosts_list(api_client):
    """Testa a rota GET /hosts/list."""
    response = await api_client.get("/hosts/list")
    assert response.status_code in [200, 401]
    if response.status_code == 200:
        data = response.json()
        assert isinstance(data, list)


@pytest.mark.asyncio
async def test_get_alerts_list(api_client):
    """Testa a rota GET /alerts/list."""
    response = await api_client.get("/alerts/list")
    assert response.status_code in [200, 401]
    if response.status_code == 200:
        data = response.json()
        assert isinstance(data, list)


@pytest.mark.asyncio
async def test_get_host_history_debian(api_client):
    """Testa a rota GET /host/history/Debian."""
    response = await api_client.get("/host/history/Debian")
    assert response.status_code in [200, 401, 404]
    if response.status_code == 200:
        data = response.json()
        assert isinstance(data, (dict, list))


def test_get_current_admin_authorization():
    """Testa a regra de autorizacao de administrador na camada de dependencias."""
    from fastapi import HTTPException
    from Backend.dependencies import get_current_admin
    from unittest.mock import MagicMock

    # 1. Usuario comum sem flag is_admin
    user_regular = MagicMock()
    user_regular.username = "operador"
    user_regular.is_admin = False

    with pytest.raises(HTTPException) as exc_info:
        get_current_admin(user_regular)
    assert exc_info.value.status_code == 403

    # 2. Superusuario admin oficial
    user_admin = MagicMock()
    user_admin.username = "admin"
    user_admin.is_admin = False
    assert get_current_admin(user_admin) == user_admin

    # 3. Usuario com flag is_admin explicita
    user_with_flag = MagicMock()
    user_with_flag.username = "auditor"
    user_with_flag.is_admin = True
    assert get_current_admin(user_with_flag) == user_with_flag
