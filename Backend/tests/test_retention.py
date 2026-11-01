"""
Backend Test Suite - Testes da Politica de Retencao e Purga de Dados
===============================================================================
Testa a leitura de dias de retencao no .env, calculo de data de corte e
desativacao quando NETSPOT_RETENTION_DAYS=0.
"""

from unittest.mock import AsyncMock, MagicMock
import os
import pytest
from Backend.services.retention_service import get_retention_days, purge_old_data


@pytest.fixture
def mock_async_db():
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 10
    session.execute.return_value = mock_result
    return session


def test_get_retention_days_default():
    """Testa valor padrao de retencao quando nao configurado."""
    if "NETSPOT_RETENTION_DAYS" in os.environ:
        old_val = os.environ.pop("NETSPOT_RETENTION_DAYS")
    else:
        old_val = None

    try:
        assert get_retention_days() == 30
    finally:
        if old_val is not None:
            os.environ["NETSPOT_RETENTION_DAYS"] = old_val


def test_get_retention_days_custom():
    """Testa leitura de valor customizado no .env."""
    os.environ["NETSPOT_RETENTION_DAYS"] = "60"
    assert get_retention_days() == 60

    os.environ["NETSPOT_RETENTION_DAYS"] = "0"
    assert get_retention_days() == 0


@pytest.mark.asyncio
async def test_purge_old_data_disabled(mock_async_db):
    """Testa se NETSPOT_RETENTION_DAYS=0 desativa a purga sem deletar registros."""
    os.environ["NETSPOT_RETENTION_DAYS"] = "0"
    res = await purge_old_data(mock_async_db)

    assert res["status"] == "disabled"
    assert res["check_results"] == 0
    assert res["snmp_metrics"] == 0
    assert not mock_async_db.execute.called


@pytest.mark.asyncio
async def test_purge_old_data_enabled(mock_async_db):
    """Testa a execucao da purga quando NETSPOT_RETENTION_DAYS > 0."""
    os.environ["NETSPOT_RETENTION_DAYS"] = "30"
    res = await purge_old_data(mock_async_db)

    assert res["status"] == "enabled"
    assert res.get("status") != "error"
    assert res["retention_days"] == 30
    assert "cutoff_date" in res
    assert res["check_results"] == 10
    assert res["snmp_metrics"] == 10
    assert res["alerts"] == 10
    assert res["incidents"] == 10
    assert mock_async_db.commit.called


@pytest.mark.asyncio
async def test_purge_old_data_handles_database_error():
    """Testa se excecao na execucao aciona rollback e retorna status error."""
    os.environ["NETSPOT_RETENTION_DAYS"] = "30"
    failing_db = AsyncMock()
    failing_db.execute.side_effect = RuntimeError("Conexao perdida")

    res = await purge_old_data(failing_db)

    assert res["status"] == "error"
    assert "Conexao perdida" in res["error"]
    assert failing_db.rollback.called
