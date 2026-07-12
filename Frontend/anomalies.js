const API = "http://127.0.0.1:8000";

let selectedHostId = null;
let classificationInterval = null;
let simulationCheckInterval = null;

// Inicialização
document.addEventListener("DOMContentLoaded", () => {
    // Verifica Autenticação
    const token = localStorage.getItem("token");
    if (!token) {
        localStorage.clear();
        window.location.href = "login.html";
        return;
    }

    loadHosts();

    // Setup Listeners
    document.getElementById("hostSelect").addEventListener("change", (e) => {
        const val = e.target.value;
        if (val) {
            selectedHostId = parseInt(val);
            startPolling();
        } else {
            selectedHostId = null;
            stopPolling();
            resetUI();
        }
    });

    document.getElementById("startSimBtn").addEventListener("click", triggerStartSimulation);
    document.getElementById("stopSimBtn").addEventListener("click", triggerStopSimulation);
    document.getElementById("genHistoryBtn").addEventListener("click", triggerGenerateHistory);
    document.getElementById("trainMLBtn").addEventListener("click", triggerTrainModel);
});

// Toast Notification System
function ensureToastContainer() {
    let container = document.getElementById("toastContainer");
    if (!container) {
        container = document.createElement("div");
        container.id = "toastContainer";
        container.className = "toast-container";
        document.body.appendChild(container);
    }
    return container;
}

function showToast(type, message, duration = 3200) {
    const container = ensureToastContainer();
    const toast = document.createElement("div");
    toast.className = `toast toast-${type || "info"}`;
    toast.textContent = message;
    container.appendChild(toast);

    requestAnimationFrame(() => toast.classList.add("show"));

    setTimeout(() => {
        toast.classList.remove("show");
        toast.classList.add("hide");
        setTimeout(() => toast.remove(), 240);
    }, duration);
}

// Fetch helper autenticado
async function fetchWithAuth(url, options = {}) {
    const token = localStorage.getItem("token");
    const headers = {
        "Content-Type": "application/json",
        ...options.headers,
        "Authorization": `Bearer ${token}`
    };
    
    try {
        const response = await fetch(url, { ...options, headers });
        if (response.status === 401) {
            showToast("warning", "Sessão expirada. Redirecionando...", 1500);
            localStorage.clear();
            setTimeout(() => {
                window.location.href = "login.html";
            }, 1000);
            return null;
        }
        return response;
    } catch (e) {
        console.error("Erro na chamada de API:", e);
        return null;
    }
}

// Carregar Hosts ativos no Select
async function loadHosts() {
    const res = await fetchWithAuth(`${API}/hosts/list`);
    if (!res) return;

    try {
        const hosts = await res.json();
        const select = document.getElementById("hostSelect");
        select.innerHTML = '<option value="">Selecione um host...</option>';
        
        hosts.forEach(host => {
            if (host.active) {
                const opt = document.createElement("option");
                opt.value = host.id;
                opt.textContent = `${host.name} (${host.address})`;
                select.appendChild(opt);
            }
        });
    } catch (e) {
        console.error("Erro ao carregar lista de hosts", e);
        showToast("danger", "Erro ao carregar hosts.");
    }
}

// Polling do Status da Simulação e Classificação de Anomalias
function startPolling() {
    stopPolling();
    
    // Executa imediatamente
    pollSimulationStatus();
    pollClassifications();
    
    // Configura os intervalos
    simulationCheckInterval = setInterval(pollSimulationStatus, 3000);
    classificationInterval = setInterval(pollClassifications, 5000);
}

function stopPolling() {
    if (simulationCheckInterval) clearInterval(simulationCheckInterval);
    if (classificationInterval) clearInterval(classificationInterval);
}

// Poll de simulação em tempo real
async function pollSimulationStatus() {
    if (!selectedHostId) return;

    const res = await fetchWithAuth(`${API}/api/anomalies/simulator/status?host_id=${selectedHostId}`);
    if (!res) return;

    try {
        const data = await res.json();
        const simStatusSection = document.getElementById("simStatusSection");
        const simBadge = document.getElementById("simBadge");
        const simTimer = document.getElementById("simTimer");
        const stopSimBtn = document.getElementById("stopSimBtn");

        simStatusSection.style.display = "block";

        if (data.active) {
            simBadge.className = "status-badge badge-active";
            simBadge.textContent = `Em simulação: ${data.anomaly_type}`;
            stopSimBtn.removeAttribute("disabled");

            // Calcula tempo restante
            const expires = new Date(data.expires_at);
            const now = new Date();
            const diffSec = Math.max(0, Math.floor((expires - now) / 1000));
            
            if (diffSec > 0) {
                const min = Math.floor(diffSec / 60);
                const sec = diffSec % 60;
                simTimer.textContent = `(${min}:${sec.toString().padStart(2, "0")})`;
            } else {
                simTimer.textContent = "(Expirando...)";
            }
        } else {
            simBadge.className = "status-badge badge-inactive";
            simBadge.textContent = "Inativa";
            simTimer.textContent = "";
            stopSimBtn.setAttribute("disabled", "true");
        }
    } catch (e) {
        console.error(e);
    }
}

// Poll do Pipeline de Classificações
async function pollClassifications() {
    if (!selectedHostId) return;

    const res = await fetchWithAuth(`${API}/api/anomalies/classify?host_id=${selectedHostId}`);
    if (!res) return;

    if (res.status === 400) {
        // Métricas insuficientes
        document.getElementById("noDataPlaceholder").style.display = "block";
        document.getElementById("noDataPlaceholder").innerHTML = `
            <h3>Métricas insuficientes</h3>
            <p>Aguarde alguns segundos ou inicie o simulador de rede para gerar métricas ricas de telemetria.</p>
        `;
        document.getElementById("analysisContent").style.display = "none";
        return;
    }

    try {
        const data = await res.json();
        
        // Exibe seção principal
        document.getElementById("noDataPlaceholder").style.display = "none";
        document.getElementById("analysisContent").style.display = "block";

        // 1. Atualiza painel de métricas (Features)
        updateFeaturesUI(data.features);

        // 2. Atualiza os cards das classificações
        const classes = data.classifications;

        // Card AI
        updateModelCard(
            "AI", 
            classes.generative_ai.result, 
            classes.generative_ai.confidence, 
            classes.generative_ai.explanation, 
            classes.generative_ai.latency_ms
        );

        // Card Heurística
        updateModelCard(
            "Heur", 
            classes.heuristic.result, 
            classes.heuristic.confidence, 
            classes.heuristic.explanation, 
            classes.heuristic.latency_ms
        );

        // Card ML
        updateModelCard(
            "ML", 
            classes.machine_learning.result, 
            classes.machine_learning.confidence, 
            classes.machine_learning.explanation, 
            classes.machine_learning.latency_ms
        );

        // 3. Atualiza prompt de tokens
        document.getElementById("tokenizedText").textContent = data.tokenized_text;

    } catch (e) {
        console.error(e);
    }
}

// Atualizar o painel de Features
function updateFeaturesUI(feats) {
    const grid = document.getElementById("featuresGrid");
    grid.innerHTML = "";

    const addCard = (label, val, unit = "") => {
        const card = document.createElement("div");
        card.className = "feature-card";
        card.innerHTML = `
            <div class="feature-label">${label}</div>
            <div class="feature-value">${val}${unit}</div>
        `;
        grid.appendChild(card);
    };

    addCard("Uso de CPU", feats.cpu_usage.toFixed(1), "%");
    addCard("Uso de RAM", feats.ram_usage.toFixed(1), "%");
    
    // Converte tráfego para Mbps ou Kbps
    const trafficIn = feats.network_in_bps / 1_000_000.0;
    if (trafficIn >= 1.0) {
        addCard("Tráfego Entrada", trafficIn.toFixed(2), " Mbps");
    } else {
        addCard("Tráfego Entrada", (feats.network_in_bps / 1000.0).toFixed(1), " Kbps");
    }

    const trafficOut = feats.network_out_bps / 1_000_000.0;
    if (trafficOut >= 1.0) {
        addCard("Tráfego Saída", trafficOut.toFixed(2), " Mbps");
    } else {
        addCard("Tráfego Saída", (feats.network_out_bps / 1000.0).toFixed(1), " Kbps");
    }

    addCard("Ping Latency", feats.ping_latency.toFixed(1), " ms");
    addCard("Ping Sucesso", (feats.ping_success_rate * 100).toFixed(0), "%");
    addCard("TCP Sucesso", (feats.tcp_success_rate * 100).toFixed(0), "%");
    addCard("HTTP Sucesso", (feats.http_success_rate * 100).toFixed(0), "%");
    addCard("HTTP Latency", feats.http_latency.toFixed(1), " ms");
    addCard("Portas Escaneadas", feats.num_failed_tcp_ports);
}

// Atualizar individualmente cada Card de classificação
function updateModelCard(prefix, result, confidence, explanation, latency) {
    const resEl = document.getElementById(`res${prefix}`);
    const confFillEl = document.getElementById(`confFill${prefix}`);
    const confValEl = document.getElementById(`confVal${prefix}`);
    const expEl = document.getElementById(`exp${prefix}`);
    const latEl = document.getElementById(`lat${prefix}`);

    resEl.textContent = result.replace("_", " ");
    resEl.className = `model-result class-${result}`;
    
    const confPct = Math.round(confidence * 100);
    confFillEl.style.width = `${confPct}%`;
    confValEl.textContent = `${confPct}%`;
    
    expEl.textContent = explanation;
    latEl.textContent = `Inferência: ${latency} ms`;
}

// Disparar uma simulação em tempo real
async function triggerStartSimulation() {
    if (!selectedHostId) {
        showToast("warning", "Selecione um host primeiro!");
        return;
    }

    const anomalyType = document.getElementById("scenarioSelect").value;
    const btn = document.getElementById("startSimBtn");
    
    btn.setAttribute("disabled", "true");
    btn.textContent = "Disparando...";

    const res = await fetchWithAuth(
        `${API}/api/anomalies/simulator/start?host_id=${selectedHostId}&anomaly_type=${anomalyType}&duration_seconds=300`,
        { method: "POST" }
    );

    btn.removeAttribute("disabled");
    btn.textContent = "Disparar Sim";

    if (res && res.ok) {
        showToast("success", `Cenário de ${anomalyType} ativado com sucesso!`);
        pollSimulationStatus();
        pollClassifications();
    } else {
        showToast("danger", "Falha ao disparar cenário de anomalia.");
    }
}

// Parar uma simulação ativa
async function triggerStopSimulation() {
    if (!selectedHostId) return;

    const btn = document.getElementById("stopSimBtn");
    btn.setAttribute("disabled", "true");

    const res = await fetchWithAuth(
        `${API}/api/anomalies/simulator/stop?host_id=${selectedHostId}`,
        { method: "POST" }
    );

    if (res && res.ok) {
        showToast("success", "Simulador desativado, retornando ao monitoramento real.");
        pollSimulationStatus();
        pollClassifications();
    } else {
        showToast("danger", "Erro ao parar a simulação.");
        btn.removeAttribute("disabled");
    }
}

// Gerar histórico de treino
async function triggerGenerateHistory() {
    if (!selectedHostId) {
        showToast("warning", "Selecione um host primeiro!");
        return;
    }

    const anomalyType = document.getElementById("scenarioSelect").value;
    const btn = document.getElementById("genHistoryBtn");

    btn.setAttribute("disabled", "true");
    btn.textContent = "Gerando dados...";

    const res = await fetchWithAuth(
        `${API}/api/anomalies/simulator/generate-history?host_id=${selectedHostId}&anomaly_type=${anomalyType}&records=150`,
        { method: "POST" }
    );

    btn.removeAttribute("disabled");
    btn.textContent = "Gerar Histórico de Treino";

    if (res && res.ok) {
        showToast("success", `Iniciada geração em background de dados históricos para '${anomalyType}'.`);
    } else {
        showToast("danger", "Erro ao disparar geração de histórico.");
    }
}

// Treinar Modelo de ML Baseline
async function triggerTrainModel() {
    const btn = document.getElementById("trainMLBtn");
    btn.setAttribute("disabled", "true");
    btn.textContent = "Treinando...";

    const res = await fetchWithAuth(`${API}/api/anomalies/train`, { method: "POST" });
    
    btn.removeAttribute("disabled");
    btn.textContent = "Treinar Baseline ML (Decision Tree)";

    if (res && res.ok) {
        showToast("success", "Árvore de Decisão tradicional (DecisionTreeClassifier) treinada com sucesso!");
        if (selectedHostId) pollClassifications();
    } else {
        showToast("danger", "Erro ao treinar modelo. Verifique se pandas/scikit-learn estão instalados.");
    }
}

// Limpar tela caso nenhum host esteja selecionado
function resetUI() {
    document.getElementById("simStatusSection").style.display = "none";
    document.getElementById("noDataPlaceholder").style.display = "block";
    document.getElementById("noDataPlaceholder").innerHTML = `
        <h3>Nenhum host selecionado</h3>
        <p>Selecione um host no painel esquerdo para obter análises com IA Generativa, heurística clássica e baseline de Machine Learning.</p>
    `;
    document.getElementById("analysisContent").style.display = "none";
    document.getElementById("featuresGrid").innerHTML = `
        <div style="grid-column: 1/-1; color: var(--text-soft); font-size: 0.85rem; text-align: center; padding: 20px 0;">
            Selecione um host para carregar as métricas atuais.
        </div>
    `;
}
