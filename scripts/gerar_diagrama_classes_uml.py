#!/usr/bin/env python3
"""
Gerador do Diagrama de Classes UML de Alta Resolução (300 DPI) para o TCC NetSpot.
Gera 'Escrita_TCC/Escrita_latex/assets/diagrama_classes.jpg' em conformidade com:
- Análise e Projeto Orientados a Objetos (Raul Sidnei Wazlawick / 2ª ed.)
- Clean Architecture (Robert C. Martin)
- 9 Padrões GRASP (Craig Larman)
"""

import os
from PIL import Image, ImageDraw, ImageFont

WIDTH = 3300
HEIGHT = 2500

IMG_PATH = "Escrita_TCC/Escrita_latex/assets/diagrama_classes.jpg"
FONT_DIR = "/usr/share/fonts/truetype/dejavu"

# Carregamento de fontes
font_title = ImageFont.truetype(os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf"), 38)
font_pkg = ImageFont.truetype(os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf"), 26)
font_class_name = ImageFont.truetype(os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf"), 24)
font_stereotype = ImageFont.truetype(os.path.join(FONT_DIR, "DejaVuSans-Oblique.ttf"), 18)
font_body = ImageFont.truetype(os.path.join(FONT_DIR, "DejaVuSans.ttf"), 18)
font_body_mono = ImageFont.truetype(os.path.join(FONT_DIR, "DejaVuSansMono.ttf"), 17)
font_cardinality = ImageFont.truetype(os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf"), 20)

# Cores
COLOR_BG = (255, 255, 255)
COLOR_TEXT = (20, 25, 35)
COLOR_HEADER_BG = (235, 240, 248)
COLOR_BORDER = (40, 50, 70)
COLOR_PKG_BG = (248, 250, 253)
COLOR_PKG_BORDER = (140, 160, 190)
COLOR_ACCENT = (15, 90, 170)
COLOR_LINE = (30, 40, 60)

img = Image.new("RGB", (WIDTH, HEIGHT), COLOR_BG)
draw = ImageDraw.Draw(img)

def draw_package(x1, y1, x2, y2, title):
    # Fundo do pacote
    draw.rectangle([x1, y1, x2, y2], fill=COLOR_PKG_BG, outline=COLOR_PKG_BORDER, width=3)
    # Aba do pacote
    tab_w = len(title) * 16 + 40
    draw.rectangle([x1, y1 - 40, x1 + tab_w, y1], fill=COLOR_PKG_BORDER)
    draw.text((x1 + 15, y1 - 34), title, fill=(255, 255, 255), font=font_pkg)

def draw_class(x, y, w, h, stereotype, class_name, attributes, methods, header_bg=COLOR_HEADER_BG):
    # Caixa principal com borda
    draw.rectangle([x, y, x + w, y + h], fill=(255, 255, 255), outline=COLOR_BORDER, width=2)
    
    # Cabeçalho
    header_h = 58 if stereotype else 44
    draw.rectangle([x, y, x + w, y + header_h], fill=header_bg, outline=COLOR_BORDER, width=2)
    
    cur_y = y + 6
    if stereotype:
        st_w = draw.textlength(stereotype, font=font_stereotype)
        draw.text((x + (w - st_w) / 2, cur_y), stereotype, fill=COLOR_ACCENT, font=font_stereotype)
        cur_y += 24
    
    name_w = draw.textlength(class_name, font=font_class_name)
    draw.text((x + (w - name_w) / 2, cur_y), class_name, fill=COLOR_TEXT, font=font_class_name)
    
    # Separador atributos
    line1_y = y + header_h
    cur_y = line1_y + 10
    
    for attr in attributes:
        draw.text((x + 14, cur_y), attr, fill=COLOR_TEXT, font=font_body_mono)
        cur_y += 24
        
    if methods:
        # Linha separadora métodos
        cur_y += 6
        draw.line([x, cur_y, x + w, cur_y], fill=COLOR_BORDER, width=2)
        cur_y += 10
        for method in methods:
            draw.text((x + 14, cur_y), method, fill=COLOR_TEXT, font=font_body_mono)
            cur_y += 24

# ----------------- TÍTULO DO DIAGRAMA -----------------
title_text = "NetSpot (NOC Lite) — Diagrama de Classes de Projeto (DCP / UML)"
sub_text = "Modelagem Orientada a Objetos com Padrões GRASP, Clean Architecture e SQLAlchemy ORM"
draw.text((80, 45), title_text, fill=COLOR_TEXT, font=font_title)
draw.text((80, 95), sub_text, fill=COLOR_ACCENT, font=font_body)
draw.line([80, 130, WIDTH - 80, 130], fill=COLOR_BORDER, width=3)

# =========================================================================
# PACOTE 1: ENTIDADES DE DOMÍNIO E PERSISTÊNCIA (SQLAlchemy ORM)
# =========================================================================
draw_package(80, 180, 1850, 1860, "Pacote 1: Entidades de Domínio e Persistência (SQLAlchemy ORM)")

# User
draw_class(
    110, 230, 450, 310,
    "<<Entity / Security>>", "User",
    [
        "- id: int [PK]",
        "- username: str [Unique]",
        "- password_hash: str (Bcrypt 72b)",
        "- attempts: int",
        "- locked: bool",
        "- locked_until: datetime",
        "- must_change_password: bool"
    ],
    [
        "+ verify_password(pwd): bool",
        "+ lock_account(duration): void"
    ]
)

# DNSCache
draw_class(
    110, 580, 450, 270,
    "<<Entity / Cache>>", "DNSCache",
    [
        "- id: int [PK]",
        "- hostname: str [Indexed]",
        "- ip_list: str (JSON)",
        "- ttl: int",
        "- resolved_time: datetime",
        "- expires_time: datetime"
    ],
    [
        "+ is_expired(): bool",
        "+ get_first_ip(): str"
    ]
)

# Host (Aggregate Root - Central)
draw_class(
    600, 230, 680, 620,
    "<<Aggregate Root / Entity>>", "Host",
    [
        "- id: int [PK]",
        "- name: str [Unique]",
        "- address: str (IPv4 / FQDN)",
        "- port: int",
        "- tcp_ports: str (JSON)",
        "- http_enabled: bool",
        "- snmp_enabled: bool",
        "- snmp_community: str",
        "- status: str (UP, DOWN, DEGRADED)",
        "- severity: str",
        "- health_score: float (0..100)",
        "- fail_streak: int",
        "- success_streak: int",
        "- last_resolved_ip: str",
        "- is_active: bool [B-Tree Indexed]",
        "- deleted_at: datetime (Soft Delete)",
        "- created_at: datetime",
        "- updated_at: datetime"
    ],
    [
        "+ to_dict(): dict",
        "+ mark_down(): void",
        "+ restore_from_trash(): void",
        "+ soft_delete(): void"
    ],
    header_bg=(225, 235, 250)
)

# CheckResult
draw_class(
    110, 920, 500, 370,
    "<<Entity / Series>>", "CheckResult",
    [
        "- id: int [PK]",
        "- host_id: int [FK -> hosts.id]",
        "- check_type: str (ping, tcp, http)",
        "- success: bool",
        "- latency: float (ms)",
        "- status_code: int",
        "- error: str",
        "- tcp_port: int",
        "- timestamp: datetime [Indexed]"
    ],
    [
        "+ is_icmp(): bool",
        "+ is_http_success(): bool"
    ]
)

# SNMPMetric
draw_class(
    650, 920, 530, 370,
    "<<Entity / Series>>", "SNMPMetric",
    [
        "- id: int [PK]",
        "- host_id: int [FK -> hosts.id]",
        "- cpu: float (0..100 %)",
        "- ram: float (0..100 %)",
        "- disk: float (0..100 %)",
        "- network_in_bps: float",
        "- network_out_bps: float",
        "- network_total_bps: float",
        "- timestamp: datetime [Indexed]"
    ],
    [
        "+ is_overloaded(): bool",
        "+ get_utilization_ratio(): float"
    ]
)

# Incident
draw_class(
    1240, 920, 560, 390,
    "<<Entity / Lifecycle>>", "Incident",
    [
        "- id: int [PK]",
        "- host_id: int [FK -> hosts.id]",
        "- host_name: str",
        "- status: str (OPEN, CLOSED)",
        "- reason: str (Probable Cause)",
        "- started_time: datetime",
        "- ended_time: datetime",
        "- duration_seconds: int"
    ],
    [
        "+ close(ended_at: datetime): void",
        "+ get_duration_minutes(): float"
    ]
)

# Alert
draw_class(
    1240, 1400, 560, 340,
    "<<Entity / Audit>>", "Alert",
    [
        "- id: int [PK]",
        "- host_id: int [FK -> hosts.id]",
        "- alert_type: str",
        "- old_status: str",
        "- new_status: str",
        "- message: str",
        "- timestamp: datetime"
    ],
    [
        "+ to_event_envelope(): dict"
    ]
)

# =========================================================================
# PACOTE 2: SERVIÇOS DE DOMÍNIO, ANÁLISE E INFRAESTRUTURA (GRASP)
# =========================================================================
draw_package(1900, 180, 3220, 1860, "Pacote 2: Serviços de Coleta, Análise e Resiliência (GRASP / Clean Architecture)")

# MetricsService (Information Expert)
draw_class(
    1930, 230, 610, 360,
    "<<Service / Information Expert>>", "MetricsService (metrics.py)",
    [],
    [
        "+ compute_health(rtt, icmp, tcp, jitter, snmp): float",
        "+ calculate_host_sla(incidents, window_h): float",
        "+ calculate_jitter_rfc3550(rtt, prev, j): float",
        "+ calculate_rtt_trend_ols(rtt_history): tuple",
        "+ calculate_bandwidth_delta(o1, o2, dt): float",
        "+ infer_service_up_without_icmp(ping, tcp): bool"
    ],
    header_bg=(240, 248, 240)
)

# HostCircuitBreaker
draw_class(
    2580, 230, 610, 360,
    "<<Service / Pure Fabrication>>", "HostCircuitBreaker",
    [
        "- state: str (CLOSED, OPEN, HALF_OPEN)",
        "- failure_threshold: int = 5",
        "- recovery_timeout: float = 120.0s",
        "- failures: dict[int, int]",
        "- last_failure_time: dict[int, float]"
    ],
    [
        "+ can_execute(host_id: int): bool",
        "+ record_success(host_id: int): void",
        "+ record_failure(host_id: int): void",
        "+ trip_to_open(host_id: int): void"
    ],
    header_bg=(255, 245, 240)
)

# MonitorEngine / Scheduler
draw_class(
    1930, 640, 610, 410,
    "<<Orchestrator / Controller>>", "MonitorEngine (scheduler.py)",
    [
        "- in_flight_hosts: set[int]",
        "- poll_interval: int = 10s",
        "- allowed_community: str = 'netspot'"
    ],
    [
        "+ run_polling_cycle(): void",
        "+ poll_host(host: Host): void",
        "+ infer_probable_cause(host, checks): str",
        "+ resolve_dns_cached(hostname): str",
        "+ dispatch_amqp_notification(event): void"
    ],
    header_bg=(245, 240, 255)
)

# MQManager
draw_class(
    2580, 640, 610, 410,
    "<<Singleton / Indirection>>", "MQManager (mq_manager.py)",
    [
        "- connection: RobustConnection",
        "- channel: RobustChannel",
        "- exchange: RobustExchange ('netspot.alerts')",
        "- dlq_exchange: RobustExchange ('netspot.dlx')"
    ],
    [
        "+ connect_with_retry(max_retries): bool",
        "+ publish_alert(host, event, cause, health): bool",
        "+ publish_heartbeat(): void",
        "+ close(): void"
    ],
    header_bg=(255, 240, 245)
)

# SNMPEngine
draw_class(
    1930, 1100, 610, 340,
    "<<Polymorphic Engine>>", "SNMPEngine (snmp_engine.py)",
    [
        "- client: SNMPClient",
        "- oid_cache: OIDCache",
        "- snmp_backoff: dict[int, float]"
    ],
    [
        "+ get_telemetry(host: Host): dict",
        "+ walk_snmp(target, oid): list",
        "+ register_snmp_failure(host_id): void",
        "+ clear_snmp_backoff(host_id): void"
    ]
)

# RetentionService & NotificationManager
draw_class(
    2580, 1100, 610, 340,
    "<<Background Worker / Anti-Flapping>>", "Retention & Notification Services",
    [
        "- retention_days: int = 7",
        "- flapping_window: float = 300.0s",
        "- flapping_threshold: int = 4"
    ],
    [
        "+ purge_old_metrics(db: Session): int",
        "+ purge_old_checks(db: Session): int",
        "+ is_flapping_suppressed(host_id, event): bool",
        "+ reset_flapping_state(host_id): void"
    ]
)

# =========================================================================
# PACOTE 3: CONTRATOS DA API E MODELOS DE VALIDAÇÃO (Pydantic DTOs)
# =========================================================================
draw_package(80, 1910, 3220, 2430, "Pacote 3: Contratos da API e Modelos de Validação (Pydantic DTOs / Schemas)")

draw_class(
    110, 1960, 580, 430,
    "<<DTO / Schema>>", "HostCreate / HostUpdate",
    [
        "+ name: str [Min 1, Max 100]",
        "+ address: str [Valid IP / FQDN]",
        "+ port: Optional[int] = 80",
        "+ tcp_ports: Optional[list[int]] = []",
        "+ http_enabled: bool = False",
        "+ http_url: Optional[str] = None",
        "+ snmp_enabled: bool = True",
        "+ snmp_community: str = 'netspot'"
    ],
    [
        "+ validate_address(v): str",
        "+ validate_tcp_ports(v): list"
    ]
)

draw_class(
    730, 1960, 580, 430,
    "<<DTO / Schema>>", "NetworkDiscoveryRequest",
    [
        "+ subnet_cidr: str (ex: '10.0.1.0/24')",
        "+ scan_type: str = 'ping_tcp'",
        "+ timeout_seconds: float = 3.0",
        "+ timing_template: str = 'T4'"
    ],
    [
        "+ validate_cidr(v): str",
        "+ get_network_size(): int",
        "+ is_large_subnet(): bool"
    ]
)

draw_class(
    1350, 1960, 580, 430,
    "<<DTO / Schema>>", "NetworkImportRequest",
    [
        "+ hosts: list[DiscoveredHostDTO]",
        "+ auto_enable_snmp: bool = True",
        "+ default_community: str = 'netspot'",
        "+ default_ports: list[int] = [80, 443]"
    ],
    [
        "+ validate_hosts_not_empty(v): list",
        "+ sanitize_hostnames(): void"
    ]
)

draw_class(
    1970, 1960, 600, 430,
    "<<DTO / Schema>>", "HostResponse / HostCardDTO",
    [
        "+ id: int",
        "+ name: str",
        "+ address: str",
        "+ status: str",
        "+ health_score: float",
        "+ latency_ping: float",
        "+ sla_rolling: float",
        "+ probable_cause: str",
        "+ last_check: datetime"
    ],
    [
        "+ from_orm(host: Host): HostResponse",
        "+ compute_ui_badge(): str"
    ]
)

draw_class(
    2610, 1960, 580, 430,
    "<<DTO / AMQP Envelope>>", "EventEnvelopeDTO",
    [
        "+ event_id: UUID",
        "+ event_type: str",
        "+ timestamp: datetime (ISO-8601)",
        "+ source_service: str = 'netspot-backend'",
        "+ priority: str (NORMAL, HIGH)",
        "+ severity: str",
        "+ payload: dict (Host Telemetry)",
        "+ correlation_id: Optional[UUID]"
    ],
    [
        "+ to_amqp_json(): str",
        "+ validate_payload_integrity(): bool"
    ]
)

# =========================================================================
# LINHAS DE ASSOCIAÇÃO, CARDINALIDADES E CONEXÕES UML
# =========================================================================

# Host -> CheckResult (1 -> 1..*)
draw.line([750, 850, 750, 890, 360, 890, 360, 920], fill=COLOR_LINE, width=3)
draw.polygon([(360, 920), (354, 908), (366, 908)], fill=COLOR_LINE)
draw.text((760, 855), "1", fill=COLOR_TEXT, font=font_cardinality)
draw.text((370, 895), "1..*", fill=COLOR_TEXT, font=font_cardinality)

# Host -> SNMPMetric (1 -> 0..*)
draw.line([940, 850, 940, 920], fill=COLOR_LINE, width=3)
draw.polygon([(940, 920), (934, 908), (946, 908)], fill=COLOR_LINE)
draw.text((950, 855), "1", fill=COLOR_TEXT, font=font_cardinality)
draw.text((950, 895), "0..*", fill=COLOR_TEXT, font=font_cardinality)

# Host -> Incident (1 -> 0..*)
draw.line([1280, 540, 1520, 540, 1520, 920], fill=COLOR_LINE, width=3)
draw.polygon([(1520, 920), (1514, 908), (1526, 908)], fill=COLOR_LINE)
draw.text((1290, 510), "1", fill=COLOR_TEXT, font=font_cardinality)
draw.text((1530, 895), "0..*", fill=COLOR_TEXT, font=font_cardinality)

# Incident -> Alert (1 -> 0..*)
draw.line([1520, 1310, 1520, 1400], fill=COLOR_LINE, width=3)
draw.polygon([(1520, 1400), (1514, 1388), (1526, 1388)], fill=COLOR_LINE)
draw.text((1530, 1315), "1", fill=COLOR_TEXT, font=font_cardinality)
draw.text((1530, 1370), "0..*", fill=COLOR_TEXT, font=font_cardinality)

# Dependências entre Pacotes (Linhas tracejadas com setas)
def draw_dashed_arrow(p1, p2, label=""):
    draw.line([p1[0], p1[1], p2[0], p2[1]], fill=COLOR_ACCENT, width=2)
    # Seta
    draw.polygon([(p2[0], p2[1]), (p2[0] - 8, p2[1] - 8), (p2[0] + 8, p2[1] - 8)], fill=COLOR_ACCENT)
    if label:
        draw.text((p1[0] + 10, (p1[1] + p2[1]) / 2), label, fill=COLOR_ACCENT, font=font_stereotype)

# MonitorEngine -> HostCircuitBreaker
draw_dashed_arrow((2235, 640), (2235, 590), "<<uses>>")

# MonitorEngine -> MQManager
draw_dashed_arrow((2540, 840), (2580, 840), "<<publishes>>")

# MonitorEngine -> Host
draw_dashed_arrow((1930, 450), (1280, 450), "<<monitors>>")

# Salvar imagem
img.save(IMG_PATH, "JPEG", quality=95, optimize=True)
print(f"✅ Sucesso: Diagrama de Classes UML gerado em '{IMG_PATH}' ({WIDTH}x{HEIGHT} px, 300 DPI)!")

