"""
Backend Test Suite - Testes da Lógica de Alertas e Ciclo de Vida de Incidentes
===============================================================================
Encapsula os cenários do checklist de alertas em asserções formais do Pytest.
Testa:
- Detecção e supressão de incidentes em caso de ICMP bloqueado com HTTP ativo;
- Abertura de incidente degradado (SERVICE_DEGRADED);
- Abertura de incidente indisponível (SERVICE_DOWN);
- Incidentes de falha de DNS (DNS_FAILURE);
- Recuperação automática e despacho de evento de encerramento;
- Cooldown de alertas (Anti-Spam / Anti-Flapping);
- Prevenção de duplicidade de incidentes abertos.
"""

from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from Backend.models import Base, Host, CheckResult, Incident
import Backend.utils as utils
import Backend.scheduler as scheduler
from Backend.routes.hosts import infer_probable_cause


@pytest.fixture
def sqlite_db():
    """Cria uma sessão isolada em SQLite in-memory para testes de incidentes."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=True, bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def mock_telegram():
    """Captura mensagens de alerta sem tráfego de rede."""
    messages = []
    original_func = utils.send_telegram_alert
    utils.send_telegram_alert = lambda message: messages.append(message) or True
    scheduler._ALERT_COOLDOWN_STATE.clear()
    yield messages
    utils.send_telegram_alert = original_func
    scheduler._ALERT_COOLDOWN_STATE.clear()


def make_test_host(name: str, address: str, port: int | None = None, http_url: str | None = None) -> Host:
    return Host(
        name=name,
        address=address,
        port=port,
        http_url=http_url,
        active=True,
        status="UNKNOWN",
        status_ping="UNKNOWN",
        status_tcp="UNKNOWN",
        last_check=datetime.now(timezone.utc),
        health_score=100,
        severity="HEALTHY",
        fail_streak=0,
        success_streak=0,
    )


def count_open_incidents(db, host_name: str, incident_type: str | None = None) -> int:
    rows = db.query(Incident).filter(Incident.host_name == host_name, Incident.status == "OPEN").all()
    if incident_type is None:
        return len(rows)
    return sum(1 for i in rows if utils.parse_incident_type(i.reason) == incident_type)


def test_icmp_blocked_does_not_open_incident(sqlite_db, mock_telegram):
    """Cenário 1: ICMP com falha mas HTTP/TCP com sucesso indica firewall, não host DOWN."""
    h = make_test_host("host-icmp", "icmp.example", port=80, http_url="http://icmp.example")
    sqlite_db.add(h)
    sqlite_db.flush()

    sqlite_db.add(CheckResult(host_id=h.id, host_name=h.name, check_type="ping", success=False, latency=None, error="timeout"))
    sqlite_db.add(CheckResult(host_id=h.id, host_name=h.name, check_type="tcp", success=True, latency=20, error=None))
    sqlite_db.add(CheckResult(host_id=h.id, host_name=h.name, check_type="http", success=True, latency=120, error=None, status_code=200))
    sqlite_db.commit()

    h.status = "UP"
    state, primary, icmp_blocked = scheduler.determine_operational_state(
        h,
        {"success": False, "latency": None},
        {"success": True, "latency": 20},
        {"success": True, "latency": 120, "status_code": 200},
    )
    cause = infer_probable_cause(sqlite_db, h)

    assert state == "UP"
    assert primary == "HTTP"
    assert icmp_blocked is True
    assert "ICMP bloqueado por firewall" in cause
    assert count_open_incidents(sqlite_db, h.name) == 0


def test_service_degraded_opens_incident(sqlite_db, mock_telegram):
    """Cenário 2: HTTP com erro 503 e latência alta abre incidente DEGRADED."""
    h = make_test_host("host-degraded", "degraded.example", port=80, http_url="http://degraded.example")
    sqlite_db.add(h)
    sqlite_db.flush()

    state, primary, _ = scheduler.determine_operational_state(
        h,
        {"success": False, "latency": None},
        {"success": True, "latency": 30},
        {"success": False, "latency": 900, "status_code": 503},
    )
    assert state == "DEGRADED"

    utils.open_incident(
        sqlite_db,
        h,
        "Instabilidade detectada no serviço HTTP",
        incident_type=utils.INCIDENT_TYPE_SERVICE_DEGRADED,
        check_used=primary,
        auto_commit=False,
    )
    sqlite_db.commit()

    assert count_open_incidents(sqlite_db, h.name, utils.INCIDENT_TYPE_SERVICE_DEGRADED) == 1


def test_service_unavailable_opens_down_incident(sqlite_db, mock_telegram):
    """Cenário 3: Falha total de todos os checks abre incidente SERVICE_DOWN."""
    h = make_test_host("host-down", "down.example", port=80, http_url="http://down.example")
    sqlite_db.add(h)
    sqlite_db.flush()

    state, primary, _ = scheduler.determine_operational_state(
        h,
        {"success": False, "latency": None},
        {"success": False, "latency": None},
        {"success": False, "latency": None, "status_code": None},
    )
    assert state == "DOWN"

    utils.open_incident(
        sqlite_db,
        h,
        "Serviço HTTP indisponível",
        incident_type=utils.INCIDENT_TYPE_SERVICE_DOWN,
        check_used=primary,
        auto_commit=False,
    )
    sqlite_db.commit()

    assert count_open_incidents(sqlite_db, h.name, utils.INCIDENT_TYPE_SERVICE_DOWN) == 1


def test_dns_failure_opens_dns_incident(sqlite_db, mock_telegram):
    """Cenário 4: Falha na resolução de nomes abre incidente DNS_FAILURE."""
    h = make_test_host("host-dns", "dns.example")
    sqlite_db.add(h)
    sqlite_db.flush()

    utils.open_incident(
        sqlite_db,
        h,
        "Falha na resolução DNS",
        incident_type=utils.INCIDENT_TYPE_DNS_FAILURE,
        check_used="DNS",
        auto_commit=False,
    )
    sqlite_db.commit()

    assert count_open_incidents(sqlite_db, h.name, utils.INCIDENT_TYPE_DNS_FAILURE) == 1


def test_incident_recovery_closes_and_notifies(sqlite_db, mock_telegram):
    """Cenário 5: Resolução do incidente fecha registro e dispara evento de encerramento."""
    h = make_test_host("host-rec", "rec.example", port=80, http_url="http://rec.example")
    sqlite_db.add(h)
    sqlite_db.flush()

    utils.open_incident(
        sqlite_db,
        h,
        "Serviço HTTP indisponível",
        incident_type=utils.INCIDENT_TYPE_SERVICE_DOWN,
        check_used="HTTP",
        auto_commit=False,
    )
    sqlite_db.commit()
    assert count_open_incidents(sqlite_db, h.name, utils.INCIDENT_TYPE_SERVICE_DOWN) == 1

    utils.close_incident(sqlite_db, h.name, incident_type=utils.INCIDENT_TYPE_SERVICE_DOWN, auto_commit=False)
    sqlite_db.commit()

    assert count_open_incidents(sqlite_db, h.name, utils.INCIDENT_TYPE_SERVICE_DOWN) == 0
    assert any(
        isinstance(m, dict) and m.get("event") == "incident_closed" and m.get("incident_type") == utils.INCIDENT_TYPE_SERVICE_DOWN
        for m in mock_telegram
    )


def test_alert_cooldown_prevents_flapping(sqlite_db, mock_telegram):
    """Cenário 6: Tentativas sucessivas do mesmo evento dentro da janela sofrem cooldown."""
    first = scheduler._alert_cooldown_passed(999, "DNS_CHANGE", 60, "x->y")
    second = scheduler._alert_cooldown_passed(999, "DNS_CHANGE", 60, "x->y")
    assert first is True
    assert second is False


def test_duplicate_incident_prevention(sqlite_db, mock_telegram):
    """Cenário 7: Abrir o mesmo tipo de incidente repetidas vezes não duplica registros."""
    h = make_test_host("host-dup", "dup.example", port=443, http_url="https://dup.example")
    sqlite_db.add(h)
    sqlite_db.flush()

    utils.open_incident(
        sqlite_db,
        h,
        "Serviço HTTP indisponível",
        incident_type=utils.INCIDENT_TYPE_SERVICE_DOWN,
        check_used="HTTP",
        auto_commit=False,
    )
    utils.open_incident(
        sqlite_db,
        h,
        "Serviço HTTP indisponível",
        incident_type=utils.INCIDENT_TYPE_SERVICE_DOWN,
        check_used="HTTP",
        auto_commit=False,
    )
    sqlite_db.commit()

    assert count_open_incidents(sqlite_db, h.name, utils.INCIDENT_TYPE_SERVICE_DOWN) == 1
