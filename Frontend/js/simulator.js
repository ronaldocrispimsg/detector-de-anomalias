/**
 * NetSpot - Lógica Front-End do Simulador & Classificador Visual de Anomalias (1 Clique & Personalizável)
 */

const API_BASE = "/api/anomalies";
let activeScenario = "NORMAL";
let currentMetrics = {
    scenario: "NORMAL",
    timestamp: Date.now() / 1000,
    latency_ms: 15,
    packet_loss_pct: 0,
    jitter_ms: 2,
    cpu_usage_pct: 28,
    ram_usage_pct: 45,
    disk_usage_pct: 40,
    network_in_bps: 5000000,
    network_out_bps: 2000000,
    http_status_code: 200,
    http_response_time_ms: 120,
    tcp_port_open: true,
    active_connections: 45
};

const SCENARIO_ICONS = {
    "NORMAL": "🟢",
    "DDOS_ATTACK": "🌊",
    "PORT_SCAN": "🔍",
    "HOST_DOWN": "❌",
    "MEMORY_LEAK": "🚨",
    "DATA_EXFILTRATION": "📤",
    "DISK_EXHAUSTION": "💾",
    "SERVICE_OUTAGE": "⚠️",
    "COMBINED_FAULT": "💥",
    "NETWORK_CONGESTION": "🐢",
    "CUSTOM": "🎛️"
};

document.addEventListener("DOMContentLoaded", () => {
    checkGenAIStatus();
    loadVisualScenarioCards();
    setupThemeToggle();
    document.getElementById("runBenchmarkBtn").addEventListener("click", runBenchmark);
});

async function checkGenAIStatus() {
    const badge = document.getElementById("genaiStatusBadge");
    try {
        const resp = await fetch(`${API_BASE}/genai/status`);
        if (resp.ok) {
            const data = await resp.json();
            if (data.ollama_available) {
                badge.style.background = "rgba(16, 185, 129, 0.2)";
                badge.style.color = "#34d399";
                badge.textContent = "🧠 Ollama Local LLM On";
            } else {
                badge.style.background = "rgba(168, 85, 247, 0.2)";
                badge.style.color = "#c084fc";
                badge.textContent = "⚡ Engine GenAI Local Ready";
            }
        }
    } catch (e) {
        badge.style.background = "rgba(245, 158, 11, 0.2)";
        badge.style.color = "#fbbf24";
        badge.textContent = "⚡ Engine GenAI Ready";
    }
}

async function loadVisualScenarioCards() {
    const container = document.getElementById("scenarioCardsContainer");
    try {
        const resp = await fetch(`${API_BASE}/scenarios`);
        if (resp.ok) {
            const data = await resp.json();
            container.innerHTML = "";

            data.scenarios.forEach(sc => {
                const icon = SCENARIO_ICONS[sc.key] || "⚠️";
                const card = document.createElement("div");
                card.className = `scenario-card ${sc.key === activeScenario ? "active" : ""}`;
                card.dataset.scenario = sc.key;

                card.innerHTML = `
                    <div>
                        <div class="scenario-card-header">
                            <span class="scenario-icon">${icon}</span>
                            <span class="scenario-cat-tag cat-${sc.category.split(' ')[0]}">${sc.category}</span>
                        </div>
                        <h4>${sc.title}</h4>
                        <p>${sc.description}</p>
                    </div>
                `;

                card.onclick = () => selectScenarioCard(sc.key);
                container.appendChild(card);
            });

            // Carrega o primeiro cenário (NORMAL) por padrão
            selectScenarioCard("NORMAL");
        }
    } catch (e) {
        console.error("Erro ao carregar cenários:", e);
    }
}

async function selectScenarioCard(key) {
    activeScenario = key;

    // Atualiza estados visuais dos cards
    document.querySelectorAll(".scenario-card").forEach(c => {
        if (c.dataset.scenario === key) c.classList.add("active");
        else c.classList.remove("active");
    });

    document.getElementById("activeScenarioTag").textContent = key;

    if (key === "CUSTOM") {
        openCustomModal();
        return;
    }

    try {
        const resp = await fetch(`${API_BASE}/simulate`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ scenario: key })
        });
        if (resp.ok) {
            currentMetrics = await resp.json();
            syncModalInputs(currentMetrics);
            updateVisualTelemetryMeters(currentMetrics);
            runClassification(currentMetrics);
        }
    } catch (e) {
        console.error("Erro ao simular cenário:", e);
    }
}

function openCustomModal() {
    syncModalInputs(currentMetrics);
    document.getElementById("customTuningModal").classList.remove("hidden");
}

function closeCustomModal() {
    document.getElementById("customTuningModal").classList.add("hidden");
}

function syncModalInputs(sample) {
    document.getElementById("input_latency").value = sample.latency_ms;
    document.getElementById("val_latency").textContent = sample.latency_ms;

    document.getElementById("input_loss").value = sample.packet_loss_pct;
    document.getElementById("val_loss").textContent = sample.packet_loss_pct;

    document.getElementById("input_jitter").value = sample.jitter_ms;
    document.getElementById("val_jitter").textContent = sample.jitter_ms;

    document.getElementById("input_cpu").value = sample.cpu_usage_pct;
    document.getElementById("val_cpu").textContent = sample.cpu_usage_pct;

    document.getElementById("input_ram").value = sample.ram_usage_pct;
    document.getElementById("val_ram").textContent = sample.ram_usage_pct;

    document.getElementById("input_disk").value = sample.disk_usage_pct;
    document.getElementById("val_disk").textContent = sample.disk_usage_pct;

    const netInMb = (sample.network_in_bps / 1e6).toFixed(1);
    document.getElementById("input_net_in").value = netInMb;
    document.getElementById("val_net_in").textContent = netInMb;

    const netOutMb = (sample.network_out_bps / 1e6).toFixed(1);
    document.getElementById("input_net_out").value = netOutMb;
    document.getElementById("val_net_out").textContent = netOutMb;

    document.getElementById("input_conn").value = sample.active_connections;
    document.getElementById("val_conn").textContent = sample.active_connections;

    document.getElementById("input_http_code").value = sample.http_status_code;
    document.getElementById("val_http_code").textContent = sample.http_status_code;
}

function updateVal(param, val) {
    const num = parseFloat(val);
    if (!currentMetrics) currentMetrics = {};
    currentMetrics.scenario = "CUSTOM";

    if (param === 'latency') currentMetrics.latency_ms = num;
    else if (param === 'loss') currentMetrics.packet_loss_pct = num;
    else if (param === 'jitter') currentMetrics.jitter_ms = num;
    else if (param === 'cpu') currentMetrics.cpu_usage_pct = num;
    else if (param === 'ram') currentMetrics.ram_usage_pct = num;
    else if (param === 'disk') currentMetrics.disk_usage_pct = num;
    else if (param === 'net_in') currentMetrics.network_in_bps = num * 1e6;
    else if (param === 'net_out') currentMetrics.network_out_bps = num * 1e6;
    else if (param === 'conn') currentMetrics.active_connections = parseInt(num);
    else if (param === 'http_code') {
        currentMetrics.http_status_code = parseInt(num);
        currentMetrics.tcp_port_open = (parseInt(num) !== 0);
    }

    const valElem = document.getElementById(`val_${param}`);
    if (valElem) valElem.textContent = val;
}

function randomizeCustomNoise() {
    currentMetrics.latency_ms = Math.max(0, Math.round(currentMetrics.latency_ms + (Math.random() * 20 - 10)));
    currentMetrics.cpu_usage_pct = Math.min(100, Math.max(0, Math.round(currentMetrics.cpu_usage_pct + (Math.random() * 14 - 7))));
    currentMetrics.ram_usage_pct = Math.min(100, Math.max(0, Math.round(currentMetrics.ram_usage_pct + (Math.random() * 10 - 5))));
    syncModalInputs(currentMetrics);
}

function applyCustomScenarioAndClassify() {
    closeCustomModal();
    updateVisualTelemetryMeters(currentMetrics);
    runClassification(currentMetrics);
}

function updateVisualTelemetryMeters(sample) {
    // 1. CPU
    const cpu = sample.cpu_usage_pct;
    document.getElementById("meterCpuVal").textContent = `${cpu}%`;
    const cpuBar = document.getElementById("meterCpuBar");
    cpuBar.style.width = `${cpu}%`;
    cpuBar.style.backgroundColor = cpu > 85 ? "#ef4444" : (cpu > 65 ? "#f59e0b" : "#10b981");

    // 2. RAM
    const ram = sample.ram_usage_pct;
    document.getElementById("meterRamVal").textContent = `${ram}%`;
    const ramBar = document.getElementById("meterRamBar");
    ramBar.style.width = `${ram}%`;
    ramBar.style.backgroundColor = ram > 85 ? "#ef4444" : (ram > 65 ? "#f59e0b" : "#3b82f6");

    // 3. DISK
    const disk = sample.disk_usage_pct;
    document.getElementById("meterDiskVal").textContent = `${disk}%`;
    const diskBar = document.getElementById("meterDiskBar");
    diskBar.style.width = `${disk}%`;
    diskBar.style.backgroundColor = disk > 90 ? "#ef4444" : "#8b5cf6";

    // 4. LATÊNCIA & PERDA ICMP
    const lat = sample.latency_ms;
    document.getElementById("meterLatencyVal").textContent = `${lat} ms`;
    document.getElementById("meterLossVal").textContent = `${sample.packet_loss_pct}%`;
    document.getElementById("meterJitterVal").textContent = `${sample.jitter_ms} ms`;
    const latBar = document.getElementById("meterLatencyBar");
    const latPct = Math.min(100, Math.round((lat / 400) * 100));
    latBar.style.width = `${latPct}%`;
    latBar.style.backgroundColor = lat > 200 || sample.packet_loss_pct > 20 ? "#ef4444" : "#10b981";

    // 5. BANDA ENTRADA (IN)
    const netInMb = (sample.network_in_bps / 1e6).toFixed(1);
    document.getElementById("meterNetInVal").textContent = `${netInMb} MB/s`;
    const netInPct = Math.min(100, Math.round((sample.network_in_bps / 600e6) * 100));
    document.getElementById("meterNetInBar").style.width = `${netInPct}%`;

    // 6. BANDA SAÍDA (OUT)
    const netOutMb = (sample.network_out_bps / 1e6).toFixed(1);
    document.getElementById("meterNetOutVal").textContent = `${netOutMb} MB/s`;
    const netOutPct = Math.min(100, Math.round((sample.network_out_bps / 600e6) * 100));
    document.getElementById("meterNetOutBar").style.width = `${netOutPct}%`;

    // 7. APLICAÇÃO HTTP
    const httpCode = sample.http_status_code;
    const httpBadge = document.getElementById("meterHttpBadge");
    httpBadge.textContent = httpCode === 0 ? "0 REFUSED" : `${httpCode} HTTP`;
    httpBadge.className = `risk-badge ${httpCode === 200 ? 'risk-BAIXO' : 'risk-CRÍTICO'}`;
    document.getElementById("meterHttpRespVal").textContent = `${sample.http_response_time_ms} ms`;

    // 8. CONEXÕES TCP
    const conn = sample.active_connections;
    document.getElementById("meterConnVal").textContent = conn;
    const connPct = Math.min(100, Math.round((conn / 4000) * 100));
    document.getElementById("meterConnBar").style.width = `${connPct}%`;
}

async function runClassification(sample) {
    // Feedback visual de carregamento no Motor 3 enquanto o Gemma 2B processa a inferência
    document.getElementById("genaiScenario").textContent = "ANALISANDO...";
    document.getElementById("genaiMeta").textContent = "🧠 Gemma 2B Raciocinando em Tempo Real...";
    document.getElementById("genaiSummaryText").textContent = "Aguardando síntese do modelo generativo local...";

    try {
        const resp = await fetch(`${API_BASE}/classify`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                sample: sample,
                engine: "ensemble"
            })
        });

        if (resp.ok) {
            const data = await resp.json();
            renderResults(data.result);
        }
    } catch (e) {
        console.error("Erro na classificação:", e);
    }
}

function renderResults(res) {
    // Banner Veredito Final
    document.getElementById("finalScenarioTitle").textContent = `CENÁRIO DETECTADO: ${res.final_scenario}`;
    document.getElementById("finalScenarioMeta").textContent = `Confiança do Ensemble: ${(res.overall_confidence * 100).toFixed(0)}% | Consenso dos Motores: ${res.consensus_match ? "SIM (Unânime)" : "DIVERGENTE"}`;
    
    const riskBadge = document.getElementById("riskLevelBadge");
    riskBadge.textContent = `RISCO ${res.risk_level}`;
    riskBadge.className = `risk-badge risk-${res.risk_level}`;

    // Motor 1: Heurística
    const h = res.heuristics;
    document.getElementById("heurScenario").textContent = h.predicted_scenario;
    document.getElementById("heurMeta").textContent = `Confiança: ${(h.confidence * 100).toFixed(0)}% | Severidade: ${h.severity}`;
    
    const rulesList = document.getElementById("heurRulesList");
    rulesList.innerHTML = "";
    if (h.triggered_rules.length === 0) {
        rulesList.innerHTML = "<li>Nenhuma violação de regra.</li>";
    } else {
        h.triggered_rules.forEach(r => {
            const li = document.createElement("li");
            li.innerHTML = `<strong style="color:#f87171;">[${r.rule_name}]</strong> ${r.description}`;
            rulesList.appendChild(li);
        });
    }

    // Motor 2: Machine Learning (contribuição por amostra)
    const ml = res.ml;
    document.getElementById("mlScenario").textContent = ml.predicted_scenario;
    document.getElementById("mlMeta").textContent = `IsolationForest Anomaly Score: ${ml.anomaly_score.toFixed(3)}`;

    const featuresList = document.getElementById("mlFeaturesList");
    featuresList.innerHTML = "";
    const sortedFeats = Object.entries(ml.feature_importances).sort((a, b) => b[1] - a[1]).slice(0, 4);
    sortedFeats.forEach(([feat, imp]) => {
        const li = document.createElement("li");
        li.innerHTML = `<strong>${feat}</strong>: ${(imp * 100).toFixed(1)}% desvio determinante`;
        featuresList.appendChild(li);
    });

    // Motor 3: GenAI Local
    const g = res.genai;
    document.getElementById("genaiScenario").textContent = g.predicted_scenario;
    document.getElementById("genaiMeta").textContent = `Provedor: ${g.provider}`;
    document.getElementById("genaiSummaryText").textContent = g.diagnostic_summary;

    // Diagnóstico e Playbook
    document.getElementById("genaiRootCause").innerHTML = `<strong>Causa Raiz:</strong> ${g.root_cause_analysis}`;
    document.getElementById("genaiImpact").innerHTML = `<strong>Impacto NOC:</strong> ${g.impact_assessment}`;

    const playbookList = document.getElementById("genaiPlaybookList");
    playbookList.innerHTML = "";
    g.remediation_playbook.forEach(step => {
        const li = document.createElement("li");
        li.textContent = step;
        playbookList.appendChild(li);
    });
}

async function runBenchmark() {
    const btn = document.getElementById("runBenchmarkBtn");
    btn.textContent = "⚡ Executando Benchmark...";
    btn.disabled = true;

    try {
        const resp = await fetch(`${API_BASE}/benchmark?samples_per_scenario=10`, { method: "POST" });
        if (resp.ok) {
            const data = await resp.json();
            document.getElementById("benchHeurAcc").textContent = `${(data.accuracy.heuristics * 100).toFixed(0)}%`;
            document.getElementById("benchMLAcc").textContent = `${(data.accuracy.ml * 100).toFixed(0)}%`;
            document.getElementById("benchGenAIAcc").textContent = `${(data.accuracy.genai * 100).toFixed(0)}%`;
            document.getElementById("benchEnsAcc").textContent = `${(data.accuracy.ensemble * 100).toFixed(0)}%`;

            const table = document.getElementById("benchMatrixTable");
            table.innerHTML = "";
            data.results_matrix.forEach(r => {
                const tr = document.createElement("tr");
                tr.style.borderBottom = "1px solid rgba(255,255,255,0.05)";
                tr.innerHTML = `
                    <td style="padding:6px 0;"><strong>${r.expected}</strong></td>
                    <td style="color:${r.heuristics === r.expected ? '#34d399' : '#f87171'}">${r.heuristics}</td>
                    <td style="color:${r.ml === r.expected ? '#34d399' : '#f87171'}">${r.ml}</td>
                    <td style="color:${r.genai === r.expected ? '#34d399' : '#f87171'}">${r.genai}</td>
                    <td style="color:${r.ensemble === r.expected ? '#34d399' : '#f87171'}; font-weight:bold;">${r.ensemble}</td>
                `;
                table.appendChild(tr);
            });

            document.getElementById("benchmarkModal").classList.remove("hidden");
        }
    } catch (e) {
        console.error("Erro no benchmark:", e);
    } finally {
        btn.textContent = "⚡ Benchmark (10 Cenários)";
        btn.disabled = false;
    }
}

function closeBenchmarkModal() {
    document.getElementById("benchmarkModal").classList.add("hidden");
}

function setupThemeToggle() {
    const themeBtn = document.getElementById("themeToggleBtn");
    if (themeBtn) {
        themeBtn.onclick = () => {
            const isDark = document.documentElement.classList.toggle("dark-theme");
            localStorage.setItem("theme", isDark ? "dark" : "light");
        };
    }
}
