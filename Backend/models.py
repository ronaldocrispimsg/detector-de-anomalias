from sqlalchemy import Boolean, Column, Float, Integer, String, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from Backend.database import Base


def _utcnow_naive():
    """Retorna datetime UTC sem tzinfo para persistência segura em banco."""
    return datetime.now(timezone.utc).replace(tzinfo=None)



class Host(Base):
    __tablename__ = "hosts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    address = Column(String)
    port = Column(Integer, nullable=True)
    tcp_ports = Column(String, nullable=True)
    http_url = Column(String, nullable=True)
    http_enabled = Column(Boolean, default=True, nullable=False)
    last_http_protocol = Column(String, nullable=True)
    http_latency = Column(Float, nullable=True)
    https_latency = Column(Float, nullable=True)
    web_tcp_port = Column(Integer, nullable=True)
    web_tcp_port_latency = Column(Float, nullable=True)
    tcp_http_port_latency = Column(Float, nullable=True)
    tcp_https_port_latency = Column(Float, nullable=True)
    tcp_http_port_ok = Column(Boolean, nullable=True)
    tcp_https_port_ok = Column(Boolean, nullable=True)

    active = Column(Boolean, default=True)
    active_time = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    baseline_pending = Column(Boolean, default=True, nullable=False)

    last_resolved_ip = Column(String, nullable=True)
    hostname_resolved = Column(String, nullable=True)

    status = Column(String)
    status_ping = Column(String)
    status_tcp = Column(String)

    fail_streak = Column(Integer, default=0)
    success_streak = Column(Integer, default=0)
    dns_ttl = Column(Integer, nullable=True)
    dns_ttl_remaining = Column(Integer, nullable=True)
    last_ttl_alert = Column(DateTime, nullable=True)

    latency_ping = Column(Float, nullable=True)
    latency_tcp = Column(Float, nullable=True)

    last_check = Column(DateTime)

    checks = relationship("CheckResult", back_populates="host")
    health_score = Column(Integer, default=0)
    severity = Column(String, default="UNKNOWN")
    last_preventive_alert = Column(DateTime, nullable=True)

    cpu_usage = Column(Float, nullable=True)
    ram_usage = Column(Float, nullable=True)
    disk_usage = Column(Float, nullable=True)
    disk_remaining = Column(Float, nullable=True)
    network_traffic = Column(Float, nullable=True)
    network_in_bps = Column(Float, nullable=True)
    network_out_bps = Column(Float, nullable=True)

    last_net_in_octets = Column(Float, nullable=True)
    last_net_out_octets = Column(Float, nullable=True)
    last_net_check = Column(DateTime, nullable=True)
    snmp_enabled = Column(Boolean, default=False, nullable=False)
    snmp_community = Column(String, nullable=False, default="netspot")
    last_snmp_check = Column(DateTime, nullable=True)

    sla_rolling_ping = Column(Float, nullable=True)
    sla_rolling_tcp = Column(Float, nullable=True)
    sla_rolling_http = Column(Float, nullable=True)

    jitter_ms_ping = Column(Float, nullable=True)
    jitter_ms_tcp = Column(Float, nullable=True)
    jitter_ms_http = Column(Float, nullable=True)
    
    slope = Column(Float, nullable=True)
    trend = Column(String, default="UNKNOWN")

    slope_http = Column(Float, nullable=True)
    trend_http = Column(String, default="UNKNOWN")



class CheckResult(Base):
    __tablename__ = "checks"
    __table_args__ = (
        Index("ix_checks_host_type_ts", "host_id", "check_type", "timestamp"),
        Index("ix_checks_host_ts", "host_id", "timestamp"),
    )

    id = Column(Integer, primary_key=True, index=True)

    host_id = Column(Integer, ForeignKey("hosts.id"), index=True)
    host_name = Column(String)

    check_type = Column(String)

    success = Column(Boolean)
    latency = Column(Float, nullable=True)
    error = Column(String, nullable=True)
    status_code = Column(Integer, nullable=True)
    tcp_port = Column(Integer, nullable=True)
    
    timestamp = Column(DateTime, default=_utcnow_naive, index=True)

    host = relationship("Host", back_populates="checks")

class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_host_ts", "host_id", "timestamp"),
    )

    id = Column(Integer, primary_key=True)
    host_id = Column(Integer, index=True)
    alert_type = Column(String)

    old_status = Column(String)
    new_status = Column(String)

    timestamp = Column(DateTime, default=_utcnow_naive, index=True)

class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        Index("ix_incidents_status_started", "status", "started_time"),
    )

    id = Column(Integer, primary_key=True, index=True)
    host_name = Column(String, index=True)
    status = Column(String, default="OPEN", index=True)
    reason = Column(String)
    started_time = Column(DateTime, default=_utcnow_naive, index=True)
    ended_time = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)

class DNSCache(Base):
    __tablename__ = "dns_cache"

    id = Column(Integer, primary_key=True)
    hostname = Column(String, unique=True, index=True)

    ip_list = Column(String)
    ttl = Column(Integer)

    resolved_time = Column(DateTime)
    expires_time = Column(DateTime)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    attempts = Column(Integer, default=0)
    locked = Column(Boolean, default=False)
    must_change_password = Column(Boolean, default=True)
    locked_until = Column(DateTime, nullable=True)

class SNMPMetric(Base):
    __tablename__ = "snmp_metrics"
    __table_args__ = (
        Index("ix_snmp_metrics_host_ts", "host_id", "timestamp"),
    )

    id = Column(Integer, primary_key=True)

    host_id = Column(Integer, index=True)
    cpu = Column(Float)
    ram = Column(Float)
    disk = Column(Float)
    network_in_bps = Column(Float, nullable=True)
    network_out_bps = Column(Float, nullable=True)
    network_total_bps = Column(Float, nullable=True)

    timestamp = Column(DateTime, default=_utcnow_naive, index=True)
