import os
import subprocess
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "Frontend")
ASSETS_DIR = os.path.join(BASE_DIR, "Escrita_TCC", "Escrita_latex", "assets")
os.makedirs(ASSETS_DIR, exist_ok=True)

# 1. HTML do Dashboard
dashboard_html = """<!DOCTYPE html>
<html lang="pt-br" class="dark-theme">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NetSpot - Dashboard</title>
    <link rel="stylesheet" href="../Frontend/css/style.css">
    <style>
        body { background: #0c1017; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 0; }
        .chart-mock {
            width: 100%; height: 60px; display: flex; align-items: flex-end; gap: 4px; padding: 6px 0;
        }
        .chart-bar {
            flex: 1; background: linear-gradient(180deg, #38bdf8 0%, rgba(56, 189, 248, 0.2) 100%);
            border-radius: 2px 2px 0 0;
        }
        .chart-bar.ram {
            background: linear-gradient(180deg, #fbbf24 0%, rgba(251, 191, 36, 0.2) 100%);
        }
    </style>
</head>
<body>
<header class="app-topbar">
    <div class="app-topbar-inner">
        <button class="topbar-action-btn account-btn" type="button">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                <circle cx="12" cy="7" r="4"></circle>
            </svg>
            <span class="topbar-btn-text">Admin</span>
        </button>
        <div class="hero-copy app-topbar-title">
            <a href="#" class="app-logo-link">
                <img src="../Frontend/images/logo/Prancheta 2.png" alt="NetSpot" class="app-logo logo-dark" style="display:block; height:32px;">
            </a>
        </div>
        <div class="topbar-right-group">
            <button class="theme-switch-pill" type="button" title="Tema Escuro Ativo">
                <span class="theme-switch-thumb" style="transform: translateX(20px);">
                    <svg viewBox="0 0 24 24" width="14" height="14" fill="#38bdf8"><path d="M12 3a9 9 0 109 9 9.75 9.75 0 00-.67-3.4 6.78 6.78 0 01-7.93-7.93A9.75 9.75 0 0012 3z"/></svg>
                </span>
            </button>
            <a class="topbar-action-btn incidents-btn" href="#">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                    <line x1="12" y1="9" x2="12" y2="13"></line>
                    <line x1="12" y1="17" x2="12.01" y2="17"></line>
                </svg>
                <span class="topbar-btn-text">Incidentes (1)</span>
            </a>
        </div>
    </div>
</header>

<main class="container app-content" style="max-width: 1600px; margin: 20px auto; padding: 0 24px;">
    <!-- Resumo da Rede / Overview KPIs -->
    <section class="panel-section" style="margin-bottom: 24px;">
        <article class="overview-card">
            <h2>Resumo da Rede (NOC Overview)</h2>
            <div class="summary-grid">
                <div class="summary-item"><span class="summary-label">Total de Hosts</span><strong class="summary-value">40</strong></div>
                <div class="summary-item"><span class="summary-label">Online</span><strong class="summary-value" style="color: #4ade80;">38</strong></div>
                <div class="summary-item"><span class="summary-label">Degradados</span><strong class="summary-value" style="color: #fbbf24;">1</strong></div>
                <div class="summary-item"><span class="summary-label">Offline</span><strong class="summary-value" style="color: #f87171;">1</strong></div>
                <div class="summary-item"><span class="summary-label">Disponibilidade Geral</span><strong class="summary-value" style="color: #38bdf8;">98.7%</strong></div>
                <div class="summary-item"><span class="summary-label">Incidentes Abertos</span><strong class="summary-value" style="color: #f87171; animation: pulse 2s infinite;">1</strong></div>
            </div>
        </article>
    </section>

    <!-- Controles de Filtro e Busca -->
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
        <div style="display: flex; gap: 12px; align-items: center;">
            <input type="text" placeholder="Buscar por host, IP ou serviço..." value="" style="background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.15); color: #fff; border-radius: 8px; padding: 8px 16px; width: 320px;">
            <div class="status-chips" style="display: flex; gap: 6px;">
                <button class="status-chip active" style="padding: 6px 14px; border-radius: 20px; font-size: 13px;">Todos (40)</button>
                <button class="status-chip" style="padding: 6px 14px; border-radius: 20px; font-size: 13px;">Online (38)</button>
                <button class="status-chip" style="padding: 6px 14px; border-radius: 20px; font-size: 13px;">Degradados (1)</button>
                <button class="status-chip" style="padding: 6px 14px; border-radius: 20px; font-size: 13px;">Offline (1)</button>
            </div>
        </div>
        <div style="display: flex; gap: 10px;">
            <button class="refresh-pill-btn" style="padding: 6px 14px; border-radius: 8px; font-size: 13px;">+ Cadastrar Host</button>
            <button class="refresh-pill-btn" style="padding: 6px 14px; border-radius: 8px; font-size: 13px; background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid #38bdf8;">⚡ LAN Discovery</button>
        </div>
    </div>

    <!-- Grid de Flip Cards 3D (4 Colunas com as 3 Faces em Destaque) -->
    <div id="hosts" style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px;">

        <!-- Card 1: Face 1 (Resumo Operacional) - Router Core UP -->
        <article class="card card-state-up" style="background: rgba(20, 27, 41, 0.85); border: 1px solid rgba(74, 222, 128, 0.35); border-radius: 12px; padding: 16px;">
            <div class="host-card-header">
                <div class="host-top-line" style="display: flex; justify-content: space-between; align-items: center;">
                    <div class="host-title-wrap" style="display: flex; align-items: center; gap: 8px;">
                        <span class="status-indicator bg-success" style="width: 10px; height: 10px; border-radius: 50%; background: #4ade80; box-shadow: 0 0 8px #4ade80;"></span>
                        <strong style="color: #fff; font-size: 15px;">router_core</strong>
                        <small style="color: #94a3b8;">(10.0.0.1)</small>
                    </div>
                    <span class="host-monitor-flag" style="background: rgba(74, 222, 128, 0.15); color: #4ade80; font-size: 11px; padding: 2px 8px; border-radius: 12px;">ATIVO</span>
                </div>
                <div class="host-meta-grid" style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin: 12px 0; background: rgba(255,255,255,0.03); padding: 8px; border-radius: 8px;">
                    <div><small style="color:#64748b; display:block;">Saúde</small><strong style="color:#4ade80; font-size:16px;">100%</strong></div>
                    <div><small style="color:#64748b; display:block;">Disponibilidade</small><strong style="color:#38bdf8; font-size:16px;">100%</strong></div>
                </div>
            </div>
            <div class="face-nav" style="display: flex; gap: 4px; margin-bottom: 12px; background: rgba(0,0,0,0.2); padding: 2px; border-radius: 6px;">
                <button class="face-pill active" style="flex:1; background:#38bdf8; color:#0f172a; border:none; border-radius:4px; font-size:11px; font-weight:bold; padding:4px;">Face 1: Resumo</button>
                <button class="face-pill" style="flex:1; background:transparent; color:#94a3b8; border:none; font-size:11px; padding:4px;">Rede</button>
                <button class="face-pill" style="flex:1; background:transparent; color:#94a3b8; border:none; font-size:11px; padding:4px;">SNMP</button>
            </div>
            <div style="font-size: 12px; color: #cbd5e1; line-height: 1.6;">
                <div>📡 <strong>ICMP Ping:</strong> 0.8 ms <span style="color:#4ade80;">(Jitter 0.2 ms)</span></div>
                <div>🔌 <strong>Portas TCP:</strong> SSH :22 (1.1 ms), BGP :179</div>
                <div style="margin-top: 8px; padding: 6px 10px; background: rgba(74, 222, 128, 0.1); border-left: 3px solid #4ade80; border-radius: 4px;">
                    <small style="color:#4ade80; font-weight:600;">Diagnóstico: Operação normal</small>
                </div>
            </div>
        </article>

        <!-- Card 2: Face 1 (Incidente Aberto) - Web Server DEGRADED -->
        <article class="card card-state-degraded" style="background: rgba(20, 27, 41, 0.85); border: 1px solid rgba(251, 191, 36, 0.5); border-radius: 12px; padding: 16px;">
            <div class="host-card-header">
                <div class="host-top-line" style="display: flex; justify-content: space-between; align-items: center;">
                    <div class="host-title-wrap" style="display: flex; align-items: center; gap: 8px;">
                        <span class="status-indicator bg-warning" style="width: 10px; height: 10px; border-radius: 50%; background: #fbbf24; box-shadow: 0 0 8px #fbbf24;"></span>
                        <strong style="color: #fff; font-size: 15px;">web_server1</strong>
                        <small style="color: #94a3b8;">(10.0.1.10)</small>
                    </div>
                    <span class="incident-badge" style="background: #ef4444; color: #fff; font-size: 10px; font-weight: bold; padding: 2px 8px; border-radius: 12px;">INCIDENTE</span>
                </div>
                <div class="host-meta-grid" style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin: 12px 0; background: rgba(255,255,255,0.03); padding: 8px; border-radius: 8px;">
                    <div><small style="color:#64748b; display:block;">Saúde</small><strong style="color:#fbbf24; font-size:16px;">54%</strong></div>
                    <div><small style="color:#64748b; display:block;">Disponibilidade</small><strong style="color:#f87171; font-size:16px;">91.2%</strong></div>
                </div>
            </div>
            <div class="face-nav" style="display: flex; gap: 4px; margin-bottom: 12px; background: rgba(0,0,0,0.2); padding: 2px; border-radius: 6px;">
                <button class="face-pill active" style="flex:1; background:#fbbf24; color:#0f172a; border:none; border-radius:4px; font-size:11px; font-weight:bold; padding:4px;">Face 1: Resumo</button>
                <button class="face-pill" style="flex:1; background:transparent; color:#94a3b8; border:none; font-size:11px; padding:4px;">Rede</button>
                <button class="face-pill" style="flex:1; background:transparent; color:#94a3b8; border:none; font-size:11px; padding:4px;">SNMP</button>
            </div>
            <div style="font-size: 12px; color: #cbd5e1; line-height: 1.6;">
                <div>📡 <strong>ICMP Ping:</strong> 14.2 ms <span style="color:#cbd5e1;">(OK)</span></div>
                <div>🌐 <strong>HTTP Web:</strong> <span style="color:#f87171; font-weight:bold;">503 Service Unavailable</span></div>
                <div>🔌 <strong>Portas:</strong> HTTP :80 (OK), HTTPS :443 (Falha)</div>
                <div style="margin-top: 8px; padding: 6px 10px; background: rgba(239, 68, 68, 0.15); border-left: 3px solid #ef4444; border-radius: 4px;">
                    <small style="color:#fca5a5; font-weight:600;">Causa: Serviço HTTP instável (HTTP 5xx)</small>
                </div>
            </div>
        </article>

        <!-- Card 3: Face 2 (Métricas de Rede e SLA) - DB Server -->
        <article class="card card-state-up" style="background: rgba(20, 27, 41, 0.85); border: 1px solid rgba(56, 189, 248, 0.4); border-radius: 12px; padding: 16px;">
            <div class="host-card-header">
                <div class="host-top-line" style="display: flex; justify-content: space-between; align-items: center;">
                    <div class="host-title-wrap" style="display: flex; align-items: center; gap: 8px;">
                        <span class="status-indicator bg-success" style="width: 10px; height: 10px; border-radius: 50%; background: #4ade80;"></span>
                        <strong style="color: #fff; font-size: 15px;">db_server1</strong>
                        <small style="color: #94a3b8;">(10.0.3.15)</small>
                    </div>
                    <span class="host-monitor-flag" style="background: rgba(74, 222, 128, 0.15); color: #4ade80; font-size: 11px; padding: 2px 8px; border-radius: 12px;">ATIVO</span>
                </div>
                <div class="host-meta-grid" style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin: 12px 0; background: rgba(255,255,255,0.03); padding: 8px; border-radius: 8px;">
                    <div><small style="color:#64748b; display:block;">Saúde</small><strong style="color:#4ade80; font-size:16px;">96%</strong></div>
                    <div><small style="color:#64748b; display:block;">Disponibilidade</small><strong style="color:#38bdf8; font-size:16px;">99.8%</strong></div>
                </div>
            </div>
            <div class="face-nav" style="display: flex; gap: 4px; margin-bottom: 12px; background: rgba(0,0,0,0.2); padding: 2px; border-radius: 6px;">
                <button class="face-pill" style="flex:1; background:transparent; color:#94a3b8; border:none; font-size:11px; padding:4px;">Resumo</button>
                <button class="face-pill active" style="flex:1; background:#38bdf8; color:#0f172a; border:none; border-radius:4px; font-size:11px; font-weight:bold; padding:4px;">Face 2: Rede / SLA</button>
                <button class="face-pill" style="flex:1; background:transparent; color:#94a3b8; border:none; font-size:11px; padding:4px;">SNMP</button>
            </div>
            <div style="font-size: 12px; color: #cbd5e1; line-height: 1.6;">
                <div style="display:flex; justify-content:space-between;"><span>SLA Ping (50 amostras):</span><strong style="color:#4ade80;">99.8%</strong></div>
                <div style="display:flex; justify-content:space-between;"><span>Jitter ICMP (RFC 3550):</span><strong>0.4 ms</strong></div>
                <div style="display:flex; justify-content:space-between;"><span>SLA TCP :5432 (Postgres):</span><strong style="color:#4ade80;">99.5%</strong></div>
                <div style="display:flex; justify-content:space-between;"><span>SLA TCP :22 (SSH):</span><strong style="color:#4ade80;">100.0%</strong></div>
                <div style="margin-top: 8px; font-size: 11px; color: #94a3b8; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 6px;">
                    Interval Merging: 0 duplicidades em falhas concorrentes
                </div>
            </div>
        </article>

        <!-- Card 4: Face 3 (Hardware SNMP e Telemetria) - App Server -->
        <article class="card card-state-up" style="background: rgba(20, 27, 41, 0.85); border: 1px solid rgba(168, 85, 247, 0.4); border-radius: 12px; padding: 16px;">
            <div class="host-card-header">
                <div class="host-top-line" style="display: flex; justify-content: space-between; align-items: center;">
                    <div class="host-title-wrap" style="display: flex; align-items: center; gap: 8px;">
                        <span class="status-indicator bg-success" style="width: 10px; height: 10px; border-radius: 50%; background: #4ade80;"></span>
                        <strong style="color: #fff; font-size: 15px;">app_server1</strong>
                        <small style="color: #94a3b8;">(10.0.2.20)</small>
                    </div>
                    <span class="host-monitor-flag" style="background: rgba(168, 85, 247, 0.15); color: #c084fc; font-size: 11px; padding: 2px 8px; border-radius: 12px;">SNMP v2c</span>
                </div>
                <div class="host-meta-grid" style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin: 12px 0; background: rgba(255,255,255,0.03); padding: 8px; border-radius: 8px;">
                    <div><small style="color:#64748b; display:block;">Saúde</small><strong style="color:#4ade80; font-size:16px;">92%</strong></div>
                    <div><small style="color:#64748b; display:block;">Disponibilidade</small><strong style="color:#38bdf8; font-size:16px;">99.4%</strong></div>
                </div>
            </div>
            <div class="face-nav" style="display: flex; gap: 4px; margin-bottom: 12px; background: rgba(0,0,0,0.2); padding: 2px; border-radius: 6px;">
                <button class="face-pill" style="flex:1; background:transparent; color:#94a3b8; border:none; font-size:11px; padding:4px;">Resumo</button>
                <button class="face-pill" style="flex:1; background:transparent; color:#94a3b8; border:none; font-size:11px; padding:4px;">Rede</button>
                <button class="face-pill active" style="flex:1; background:#a855f7; color:#fff; border:none; border-radius:4px; font-size:11px; font-weight:bold; padding:4px;">Face 3: SNMP</button>
            </div>
            <div style="font-size: 12px; color: #cbd5e1;">
                <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                    <span>CPU: <strong>38%</strong></span>
                    <span>RAM: <strong>64%</strong></span>
                    <span>Disco: <strong>45%</strong></span>
                </div>
                <div style="display:flex; gap: 4px; height: 6px; background:rgba(255,255,255,0.1); border-radius:3px; overflow:hidden; margin-bottom:8px;">
                    <div style="width: 38%; background: #4ade80;"></div>
                    <div style="width: 26%; background: #fbbf24;"></div>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:11px; color:#94a3b8; margin-bottom:6px;">
                    <span>📥 RX: 4.2 Mbps</span>
                    <span>📤 TX: 1.8 Mbps</span>
                </div>
                <!-- Gráfico histórico simulado -->
                <div class="chart-mock">
                    <div class="chart-bar" style="height: 30%;"></div>
                    <div class="chart-bar" style="height: 45%;"></div>
                    <div class="chart-bar" style="height: 40%;"></div>
                    <div class="chart-bar" style="height: 55%;"></div>
                    <div class="chart-bar" style="height: 38%;"></div>
                    <div class="chart-bar ram" style="height: 60%;"></div>
                    <div class="chart-bar ram" style="height: 64%;"></div>
                    <div class="chart-bar ram" style="height: 62%;"></div>
                </div>
            </div>
        </article>

    </div>
</main>
</body>
</html>
"""

# 2. HTML dos Incidentes
incidents_html = """<!DOCTYPE html>
<html lang="pt-br" class="dark-theme">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NetSpot - Incidentes</title>
    <link rel="stylesheet" href="../Frontend/css/style.css">
    <style>
        body { background: #0c1017; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 0; }
        .incident-card-custom {
            background: rgba(20, 27, 41, 0.85); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 24px;
        }
        .incident-item {
            background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 14px 18px; margin-bottom: 12px;
            display: grid; grid-template-columns: 220px 1fr 200px 100px; align-items: center; gap: 16px;
        }
        .incident-item.open {
            border-left: 4px solid #ef4444; background: rgba(239, 68, 68, 0.05);
        }
        .incident-item.closed {
            border-left: 4px solid #4ade80;
        }
    </style>
</head>
<body>
<header class="app-topbar">
    <div class="app-topbar-inner">
        <div class="hero-copy app-topbar-title">
            <a href="#" class="app-logo-link">
                <img src="../Frontend/images/logo/Prancheta 2.png" alt="NetSpot" class="app-logo logo-dark" style="display:block; height:32px;">
            </a>
            <span class="page-subtitle" style="color: #38bdf8; font-weight: 600; margin-left: 12px;">/ Central de Incidentes NOC</span>
        </div>
        <div class="topbar-right-group">
            <a class="topbar-action-btn" href="#" style="text-decoration:none;">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M19 12H5M12 19l-7-7 7-7"/>
                </svg>
                <span class="topbar-btn-text">Voltar ao Dashboard</span>
            </a>
        </div>
    </div>
</header>

<main class="container app-content" style="max-width: 1600px; margin: 24px auto; padding: 0 24px;">
    <!-- Resumo dos Incidentes -->
    <section class="panel-section" style="margin-bottom: 24px;">
        <article class="overview-card">
            <h2>Métricas de Confiabilidade e MTTR</h2>
            <div class="summary-grid">
                <div class="summary-item"><span class="summary-label">Total Histórico</span><strong class="summary-value">12</strong></div>
                <div class="summary-item"><span class="summary-label">Incidentes Abertos</span><strong class="summary-value" style="color: #ef4444;">1</strong></div>
                <div class="summary-item"><span class="summary-label">Incidentes Resolvidos</span><strong class="summary-value" style="color: #4ade80;">11</strong></div>
                <div class="summary-item"><span class="summary-label">MTTR Médio</span><strong class="summary-value" style="color: #38bdf8;">8m 24s</strong></div>
                <div class="summary-item"><span class="summary-label">Taxa de Autocura</span><strong class="summary-value" style="color: #4ade80;">100%</strong></div>
                <div class="summary-item"><span class="summary-label">Alertas Telegram</span><strong class="summary-value" style="color: #a855f7;">24 despachados</strong></div>
            </div>
        </article>
    </section>

    <!-- Toolbar e Filtros -->
    <article class="incident-card-custom">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
            <div style="display: flex; gap: 12px; align-items: center;">
                <input type="text" placeholder="Buscar por host, causa ou protocolo..." style="background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.15); color: #fff; border-radius: 8px; padding: 8px 16px; width: 360px;">
                <div class="status-chips" style="display: flex; gap: 6px;">
                    <button class="status-chip active" style="padding: 6px 14px; border-radius: 20px; font-size: 13px;">Todos (12)</button>
                    <button class="status-chip chip-open" style="padding: 6px 14px; border-radius: 20px; font-size: 13px; color: #ef4444;">Abertos (1)</button>
                    <button class="status-chip chip-closed" style="padding: 6px 14px; border-radius: 20px; font-size: 13px; color: #4ade80;">Fechados (11)</button>
                </div>
            </div>
            <span style="font-size: 13px; color: #94a3b8;">Ordenado por: Mais recentes primeiro</span>
        </div>

        <!-- Lista de Incidentes -->
        <div class="incidents-list">

            <!-- Incidente 1: ABERTO -->
            <div class="incident-item open">
                <div>
                    <strong style="color: #fff; font-size: 15px; display: block;">web_server1</strong>
                    <small style="color: #94a3b8;">10.0.1.10 • LAN 1 Servidores</small>
                </div>
                <div>
                    <div style="color: #fca5a5; font-weight: 600; font-size: 13px;">Serviço HTTP instável (HTTP 503) + Timeout HTTPS :443</div>
                    <small style="color: #94a3b8;">Alerta despachado via RabbitMQ -> N8N -> Telegram</small>
                </div>
                <div style="font-size: 12px; color: #cbd5e1;">
                    <div>Início: 25/10/2026 21:45:10</div>
                    <div>Duração: <strong style="color: #ef4444;">14m 32s (Ativo)</strong></div>
                </div>
                <div>
                    <span style="background: #ef4444; color: #fff; font-size: 11px; font-weight: bold; padding: 4px 10px; border-radius: 12px; display: inline-block;">OPEN</span>
                </div>
            </div>

            <!-- Incidente 2: FECHADO -->
            <div class="incident-item closed">
                <div>
                    <strong style="color: #fff; font-size: 15px; display: block;">pc14_devops</strong>
                    <small style="color: #94a3b8;">10.0.2.14 • LAN 2 Estações</small>
                </div>
                <div>
                    <div style="color: #e2e8f0; font-weight: 500; font-size: 13px;">Sobrecarga de recursos locais (CPU: 98% / RAM: 94%)</div>
                    <small style="color: #94a3b8;">Detectado via telemetria SNMP MIB-II / Host Resources</small>
                </div>
                <div style="font-size: 12px; color: #cbd5e1;">
                    <div>Início: 25/10/2026 20:12:00</div>
                    <div>Duração: 16m 45s</div>
                </div>
                <div>
                    <span style="background: rgba(74, 222, 128, 0.15); color: #4ade80; font-size: 11px; font-weight: bold; padding: 4px 10px; border-radius: 12px; display: inline-block;">CLOSED</span>
                </div>
            </div>

            <!-- Incidente 3: FECHADO -->
            <div class="incident-item closed">
                <div>
                    <strong style="color: #fff; font-size: 15px; display: block;">router_lab2</strong>
                    <small style="color: #94a3b8;">10.0.2.1 • Gateway Laboratório</small>
                </div>
                <div>
                    <div style="color: #e2e8f0; font-weight: 500; font-size: 13px;">Host sem resposta ICMP / Queda transitória de link físico</div>
                    <small style="color: #94a3b8;">Disjuntor Circuit Breaker atuou silenciando tempestade de pacotes</small>
                </div>
                <div style="font-size: 12px; color: #cbd5e1;">
                    <div>Início: 25/10/2026 18:30:10</div>
                    <div>Duração: 4m 12s</div>
                </div>
                <div>
                    <span style="background: rgba(74, 222, 128, 0.15); color: #4ade80; font-size: 11px; font-weight: bold; padding: 4px 10px; border-radius: 12px; display: inline-block;">CLOSED</span>
                </div>
            </div>

            <!-- Incidente 4: FECHADO -->
            <div class="incident-item closed">
                <div>
                    <strong style="color: #fff; font-size: 15px; display: block;">db_server2</strong>
                    <small style="color: #94a3b8;">10.0.3.16 • PostgreSQL Réplica</small>
                </div>
                <div>
                    <div style="color: #e2e8f0; font-weight: 500; font-size: 13px;">Porta 5432 recusada / Conexão recusada no handshake</div>
                    <small style="color: #94a3b8;">Reinício automático do container via Docker Healthcheck</small>
                </div>
                <div style="font-size: 12px; color: #cbd5e1;">
                    <div>Início: 25/10/2026 15:10:00</div>
                    <div>Duração: 5m 30s</div>
                </div>
                <div>
                    <span style="background: rgba(74, 222, 128, 0.15); color: #4ade80; font-size: 11px; font-weight: bold; padding: 4px 10px; border-radius: 12px; display: inline-block;">CLOSED</span>
                </div>
            </div>

        </div>
    </article>
</main>
</body>
</html>
"""

# Salvar os arquivos HTML de captura
dash_path = os.path.join(BASE_DIR, "scripts", "capture_dashboard.html")
inc_path = os.path.join(BASE_DIR, "scripts", "capture_incidents.html")

with open(dash_path, "w", encoding="utf-8") as f:
    f.write(dashboard_html)
print(f"Salvo: {dash_path}")

with open(inc_path, "w", encoding="utf-8") as f:
    f.write(incidents_html)
print(f"Salvo: {inc_path}")

