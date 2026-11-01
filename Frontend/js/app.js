const API = (window.location.protocol === "file:" || window.location.port === "5500" || window.location.port === "3000")
    ? "http://127.0.0.1:8000"
    : "/api";
const charts = {};
const MAX_POINTS_PER_SERIES = 100;
let authRedirectScheduled = false;
let lastUserInteractionAt = 0;

//

const POLLING_INTERVALS = {
    visible: { lightMs: 10000, heavyMs: 30000 },
    hidden: { lightMs: 30000, heavyMs: 60000 }
};

const pollingState = {
    lightTimer: null,
    heavyTimer: null,
    runningTasks: new Set()
};

const recentAlertCache = new Map();
const ALERT_DEDUP_WINDOW_MS = 45000;
const SEEN_ALERTS_STORAGE_KEY = "netspot_seen_alerts_v1";
const MAX_SEEN_ALERTS = 200;
const INCIDENT_TYPE_LABELS = {
    DNS_FAILURE: "Falha DNS",
    SERVICE_DEGRADED: "Serviço degradado",
    SERVICE_DOWN: "Serviço indisponível",
    GENERIC: "Incidente operacional"
};
const ALERT_TYPE_LABELS = {
    DNS_TTL_LOW: "TTL DNS baixo",
    DNS_CHANGE: "Mudança de DNS",
    HEALTH_CRITICAL: "Saúde crítica",
    STATUS_CHANGE: "Mudança de status",
    UP_RECOVERED: "Recuperação",
    DNS_FAILURE: "Falha DNS",
    SERVICE_DOWN: "Serviço indisponível",
    SERVICE_DEGRADED: "Serviço degradado"
};

function loadSeenAlertKeys() {
    try {
        const raw = localStorage.getItem(SEEN_ALERTS_STORAGE_KEY);
        if (!raw) return [];
        const parsed = JSON.parse(raw);
        if (!Array.isArray(parsed)) return [];
        return parsed.filter((v) => typeof v === "string").slice(-MAX_SEEN_ALERTS);
    } catch (err) {
        return [];
    }
}

let seenAlertKeysList = loadSeenAlertKeys();
const seenAlertKeysSet = new Set(seenAlertKeysList);
let seenAlertsBootstrapped = seenAlertKeysList.length > 0;

function persistSeenAlertKeys() {
    try {
        localStorage.setItem(SEEN_ALERTS_STORAGE_KEY, JSON.stringify(seenAlertKeysList.slice(-MAX_SEEN_ALERTS)));
    } catch (err) {
        // Ignora falha de storage para não quebrar o fluxo de alertas.
    }
}

function rememberSeenAlert(alertKey) {
    if (seenAlertKeysSet.has(alertKey)) return;
    seenAlertKeysSet.add(alertKey);
    seenAlertKeysList.push(alertKey);
    if (seenAlertKeysList.length > MAX_SEEN_ALERTS) {
        const overflow = seenAlertKeysList.length - MAX_SEEN_ALERTS;
        const removed = seenAlertKeysList.splice(0, overflow);
        removed.forEach((k) => seenAlertKeysSet.delete(k));
    }
}

if (typeof window !== "undefined" && "Notification" in window && Notification.permission === "default") {
    try {
        const permPromise = Notification.requestPermission();
        if (permPromise && typeof permPromise.catch === "function") {
            permPromise.catch(() => {});
        }
    } catch (_) {
        // Ignora bloqueio de Notification API em contextos sem suporte (ex.: Safari iOS / WebViews)
    }
}

const token = localStorage.getItem("token");
const isLoginPage = window.location.pathname.includes("login.html");

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

const VALID_TOAST_TYPES = new Set(["success", "error", "warning", "info"]);

function showToast(type, message, duration = 3200) {
    if (!VALID_TOAST_TYPES.has(type) && VALID_TOAST_TYPES.has(message)) {
        const tmp = type;
        type = message;
        message = tmp;
    }
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

function getButtonLabel(btn, fallback = "") {
    if (!btn) return fallback;
    const span = btn.querySelector("span");
    return span ? span.textContent : btn.textContent;
}

function setButtonLabel(btn, text) {
    if (!btn) return;
    const span = btn.querySelector("span");
    if (span) {
        span.textContent = text;
    } else {
        btn.textContent = text;
    }
}

function setInlineState(element, message, type = "info") {
    if (!element) return;
    element.className = `ui-state ui-state-${type}`;
    element.textContent = message;
}

function touchUserInteraction() {
    lastUserInteractionAt = Date.now();
}

function isUserActivelyInteracting(windowMs = 3500) {
    return Date.now() - lastUserInteractionAt < windowMs;
}

function hasBlockingUiOpen() {
    const openModal = document.querySelector(".modal:not(.hidden)");
    return Boolean(openModal);
}

function shouldDeferHeavyRefresh() {
    return hasBlockingUiOpen() || isUserActivelyInteracting();
}

async function runTaskOnce(taskName, taskFn) {
    if (pollingState.runningTasks.has(taskName)) return;
    pollingState.runningTasks.add(taskName);
    try {
        await taskFn();
    } finally {
        pollingState.runningTasks.delete(taskName);
    }
}

async function runLightRefresh() {
    await Promise.all([
        runTaskOnce("hosts", loadHosts),
        runTaskOnce("alerts", checkAlerts),
        runTaskOnce("summary", loadDashboardSummary)
    ]);
}

async function runHeavyRefresh() {
    if (shouldDeferHeavyRefresh()) return;
    const trashModal = document.getElementById("trashModal");
    if (trashModal && !trashModal.classList.contains("hidden")) {
        await runTaskOnce("trash", loadTrashHosts);
    }
}

function clearDashboardPolling() {
    if (pollingState.lightTimer) {
        clearInterval(pollingState.lightTimer);
        pollingState.lightTimer = null;
    }
    if (pollingState.heavyTimer) {
        clearInterval(pollingState.heavyTimer);
        pollingState.heavyTimer = null;
    }
}

function startDashboardPolling() {
    if (isLoginPage) return;
    clearDashboardPolling();

    const visibilityMode = document.hidden ? "hidden" : "visible";
    const config = POLLING_INTERVALS[visibilityMode];

    pollingState.lightTimer = setInterval(runLightRefresh, config.lightMs);
    pollingState.heavyTimer = setInterval(runHeavyRefresh, config.heavyMs);
}

function stopDashboardPolling() {
    clearDashboardPolling();
}

function resumeDashboardPolling() {
    startDashboardPolling();
}

// se estiver logado e abrir login → vai pro dashboard
if (token && isLoginPage) {
    window.location.href = "dashboard.html";
}

// se NÃO estiver logado e tentar acessar sistema → volta pro login
if (!token && !isLoginPage) {
    window.location.href = "login.html";
}

// ======================
// Helper: Requisições Autenticadas
// ======================
async function fetchWithAuth(url, options = {}) {
    const token = localStorage.getItem("token");
    if (!token) {
        if (!isLoginPage) {
            localStorage.clear();
            window.location.href = "login.html";
        }
        return null;
    }

    const headers = {
        "Content-Type": "application/json",
        ...options.headers,
        "Authorization": `Bearer ${token}`
    };

    try {
        const response = await fetch(url, { ...options, headers });
        
        if (!response || response.status === 401) {
            if (!isLoginPage && !authRedirectScheduled) {
                authRedirectScheduled = true;
                showToast("warning", "Sessão expirada. Faça login novamente.", 1400);
                localStorage.clear();
                setTimeout(() => {
                    window.location.href = "login.html";
                }, 900);
            } else if (!isLoginPage) {
                localStorage.clear();
                window.location.href = "login.html";
            }
            return null;
        }
        
        return response;
    } catch (error) {
        console.error("Erro de conexão:", error);
        // Opcional: mostrar um aviso visual discreto na tela
        return null;
    }
}

// ======================
// Login
// ======================
const loginForm = document.getElementById("loginForm");

if (loginForm) {
    loginForm.onsubmit = async function(e) {
        e.preventDefault();
        const userVal = document.getElementById("username").value;
        const passVal = document.getElementById("password").value;
        const submitBtn = loginForm.querySelector('button[type="submit"]');
        const originalBtnText = getButtonLabel(submitBtn, "Entrar");

        if (submitBtn) {
            submitBtn.disabled = true;
            setButtonLabel(submitBtn, "Entrando...");
            submitBtn.classList.add("is-loading");
        }

        try {
            const response = await fetch(`${API}/auth/login`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username: userVal, password: passVal })
            });

            const data = await response.json();

            if (response.ok && data.access_token) {
                localStorage.setItem("token", data.access_token);
                localStorage.setItem("username", userVal); // Guardamos para usar na troca

                // VERIFICA SE PRECISA TROCAR SENHA
                if (data.must_change_password) {
                    showToast("info", "Troca de senha obrigatória para continuar.");
                    const pwdModal = document.getElementById("pwdModal");
                    if (pwdModal) openAppModal(pwdModal);
                } else {
                    showToast("success", "Login realizado com sucesso.");
                    setTimeout(() => {
                        window.location.href = "dashboard.html";
                    }, 600);
                }
            } else {
                const detail = String(data.detail || "Credenciais inválidas");
                if (detail.toLowerCase().includes("bloquead")) {
                    showToast("error", detail);
                } else {
                    showToast("error", "Credenciais inválidas.");
                }
            }
        } catch (err) {
            showToast("error", "Não foi possível conectar ao servidor.");
        } finally {
            if (submitBtn) {
                submitBtn.disabled = false;
                setButtonLabel(submitBtn, originalBtnText);
                submitBtn.classList.remove("is-loading");
            }
        }
    };
}

async function submitChangePassword() {
    const newPwd = (document.getElementById("new-pwd")?.value || "").trim();
    const confirmPwd = (document.getElementById("confirm-pwd")?.value || "").trim();

    if (!newPwd) {
        showToast("warning", "Informe a nova senha.");
        return;
    }

    if (newPwd.length < 4) {
        showToast("warning", "A nova senha deve possuir no mínimo 4 caracteres.");
        return;
    }

    if (newPwd !== confirmPwd) {
        showToast("warning", "As senhas não coincidem.");
        return;
    }

    const token = localStorage.getItem("token");

    try {
        const res = await fetch(`${API}/auth/first-password`, {
            method: "POST",
            headers: { 
                "Content-Type": "application/json",
                "Authorization": "Bearer " + token
            },
            body: JSON.stringify({
                new_password: newPwd
            })
        });

        if (res.ok) {
            showToast("success", "Senha alterada com sucesso.");
            setTimeout(() => {
                window.location.href = "dashboard.html";
            }, 700);
        } else {
            const errData = await res.json().catch(() => null);
            const detailMsg = (errData && errData.detail) ? errData.detail : "Erro ao alterar senha.";
            showToast("error", detailMsg);
        }
    } catch (error) {
        showToast("error", "Não foi possível conectar ao servidor.");
    }
}

async function changePassword() {
    const currentPwd = (document.getElementById("current-pwd")?.value || "").trim();
    const newPwd = (document.getElementById("new-pwd")?.value || "").trim();
    const confirmPwd = (document.getElementById("confirm-pwd")?.value || "").trim();

    if (!currentPwd) {
        showToast("warning", "Informe a senha atual.");
        return;
    }

    if (!newPwd) {
        showToast("warning", "Informe a nova senha.");
        return;
    }

    if (newPwd.length < 4) {
        showToast("warning", "A nova senha deve possuir no mínimo 4 caracteres.");
        return;
    }

    if (newPwd !== confirmPwd) {
        showToast("warning", "As senhas não coincidem.");
        return;
    }

    const token = localStorage.getItem("token");

    try {
        const res = await fetch(`${API}/auth/change-password`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": "Bearer " + token
            },
            body: JSON.stringify({
                current_password: currentPwd,
                new_password: newPwd
            })
        });

        if (res.status === 403) {
            const errData = await res.json().catch(() => null);
            showToast("error", (errData && errData.detail) || "Conta bloqueada por excesso de tentativas.");
            return;
        }

        if (res.ok) {
            showToast("success", "Senha alterada com sucesso. Faça login novamente.");
            localStorage.removeItem("token");
            setTimeout(() => {
                window.location.href = "login.html";
            }, 700);
        } else {
            const errData = await res.json().catch(() => null);
            const detailMsg = (errData && errData.detail) ? errData.detail : "Erro ao alterar senha.";
            showToast("error", detailMsg);
        }
    } catch (error) {
        showToast("error", "Não foi possível conectar ao servidor.");
    }

}
// ======================
// Cadastrar Host (POST)
// ======================
const currentHostsMap = new Map();
const pendingDeletedHostNames = new Set();
let hostsListRequestId = 0;
const hostForm = document.getElementById("hostForm");
const portsContainer = document.getElementById("portsContainer");
const addPortBtn = document.getElementById("addPortBtn");

function addPortInput(container, value = "", removable = true, placeholder = "Porta (ex: 80)") {
    if (!container) return;
    const row = document.createElement("div");
    row.className = "port-input-row";

    const input = document.createElement("input");
    input.type = "number";
    input.min = "1";
    input.max = "65535";
    input.placeholder = placeholder;
    input.className = "port-input";
    input.title = "Porta TCP (1 a 65535)";
    input.setAttribute("aria-label", "Porta TCP (1 a 65535)");
    input.value = value === null || value === undefined ? "" : String(value);
    row.appendChild(input);

    if (removable) {
        const removeBtn = document.createElement("button");
        removeBtn.type = "button";
        removeBtn.className = "remove-port-btn";
        removeBtn.title = "Remover porta";
        removeBtn.setAttribute("aria-label", "Remover porta");
        removeBtn.innerHTML = `<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>`;
        removeBtn.addEventListener("click", () => row.remove());
        row.appendChild(removeBtn);
    }

    container.appendChild(row);
}

function resetCreatePorts() {
    if (!portsContainer) return;
    portsContainer.innerHTML = "";
    addPortInput(portsContainer, "", true, "Porta (opcional)");
}

function setModalPorts(ports) {
    const container = document.getElementById("modalPortsContainer");
    if (!container) return;
    container.innerHTML = "";

    const normalized = Array.isArray(ports)
        ? ports
            .map((p) => Number(p))
            .filter((p) => Number.isInteger(p) && p >= 1 && p <= 65535)
        : [];

    if (normalized.length === 0) {
        addPortInput(container, "", true, "Porta (opcional)");
        return;
    }

    normalized.forEach((value) => addPortInput(container, value, true, "Porta"));
}

function collectPorts(container) {
    if (!container) return [];
    const raw = Array.from(container.querySelectorAll(".port-input"))
        .map((input) => String(input.value || "").trim())
        .filter((value) => value !== "");

    const seen = new Set();
    const valid = [];
    for (const value of raw) {
        const port = Number(value);
        if (!Number.isInteger(port) || port < 1 || port > 65535) {
            throw new Error(`Porta inválida: ${value}`);
        }
        if (seen.has(port)) continue;
        seen.add(port);
        valid.push(port);
    }
    valid.sort((a, b) => a - b);
    return valid;
}

function parseHostPorts(host) {
    if (Array.isArray(host?.ports)) {
        return host.ports
            .map((p) => Number(p))
            .filter((p) => Number.isInteger(p) && p >= 1 && p <= 65535);
    }

    if (typeof host?.tcp_ports === "string" && host.tcp_ports.trim()) {
        try {
            const parsed = JSON.parse(host.tcp_ports);
            if (Array.isArray(parsed)) {
                return parsed
                    .map((p) => Number(p))
                    .filter((p) => Number.isInteger(p) && p >= 1 && p <= 65535);
            }
        } catch (_err) {}
    }

    const singlePort = Number(host?.port);
    if (Number.isInteger(singlePort) && singlePort >= 1 && singlePort <= 65535) {
        return [singlePort];
    }

    return [];
}

if (addPortBtn && portsContainer) {
    addPortBtn.addEventListener("click", () => addPortInput(portsContainer, "", true));
    resetCreatePorts();
}

if (hostForm) {
    hostForm.addEventListener("submit", async (e) => {
        e.preventDefault();

        const nameInput = document.getElementById("name");
        const addressInput = document.getElementById("address");
        const httpUrlInput = document.getElementById("http_url");
        const httpEnabledInput = document.getElementById("http_enabled");
        const snmpEnabledInput = document.getElementById("snmp_enabled");
        const snmpCommunityInput = document.getElementById("snmp_community");
        let ports = [];
        try {
            ports = collectPorts(portsContainer);
        } catch (err) {
            showToast("error", err.message || "Lista de portas inválida.");
            return;
        }

        const data = {
            name: nameInput.value,
            address: addressInput.value,
            ports,
            port: ports.length ? ports[0] : null,
            url: httpUrlInput.value || null,
            http_url: httpUrlInput.value || null,
            http_enabled: !!httpEnabledInput?.checked,
            snmp_enabled: !!snmpEnabledInput?.checked,
            snmp_community: (snmpCommunityInput?.value || "").trim() || "netspot"
        };

        const submitBtn = hostForm.querySelector('button[type="submit"]');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.classList.add("is-loading");
        }

        try {
            const response = await fetchWithAuth(`${API}/host/create`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(data)
            });

            if (!response) return;

            if (response.ok) {
                nameInput.value = "";
                addressInput.value = "";
                httpUrlInput.value = "";
                if (httpEnabledInput) httpEnabledInput.checked = true;
                if (snmpEnabledInput) snmpEnabledInput.checked = false;
                resetCreatePorts();
                loadHosts();
                loadTrashHosts();
                showToast("success", "Host cadastrado com sucesso.");
            } else {
                const errorData = await response.json();
                showToast("error", "Erro ao cadastrar: " + (errorData.detail || "Erro desconhecido"));
            }
        } catch (err) {
            console.error("Erro na requisição:", err);
            showToast("error", "Não foi possível conectar ao servidor.");
        } finally {
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.classList.remove("is-loading");
            }
        }
    });
}

let discoveredLanHosts = [];

function updateDiscoverySelectAllUI(allChecked) {
    const selectAllBtn = document.getElementById("selectAllDiscoveryBtn");
    if (!selectAllBtn) return;
    const iconSvg = allChecked
        ? `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="9" y1="9" x2="15" y2="15"></line><line x1="15" y1="9" x2="9" y2="15"></line></svg>`
        : `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><polyline points="9 11 12 14 22 4"></polyline></svg>`;
    selectAllBtn.innerHTML = `${iconSvg}<span>${allChecked ? "Desmarcar todos" : "Selecionar todos"}</span>`;
}

function renderDiscoveredLanHosts() {
    const listBox = document.getElementById("networkDiscoveryList");
    const infoBox = document.getElementById("networkDiscoveryInfo");
    const selectAllBtn = document.getElementById("selectAllDiscoveryBtn");
    if (!listBox || !infoBox) return;

    if (!Array.isArray(discoveredLanHosts) || discoveredLanHosts.length === 0) {
        infoBox.textContent = "";
        listBox.innerHTML = "<small>Nenhum host encontrado.</small>";
        if (selectAllBtn) selectAllBtn.style.display = "none";
        return;
    }

    const selectableCount = discoveredLanHosts.filter((h) => !h.already_exists).length;
    infoBox.textContent = `${discoveredLanHosts.length} host(s) encontrado(s) • ${selectableCount} disponível(is) para importação`;
    if (selectAllBtn) {
        selectAllBtn.style.display = selectableCount > 0 ? "inline-flex" : "none";
        updateDiscoverySelectAllUI(selectableCount > 0);
    }
    listBox.innerHTML = discoveredLanHosts.map((host) => {
        const disabled = host.already_exists ? "disabled" : "";
        const checked = host.already_exists ? "" : "checked";
        const hostnameText = host.hostname ? ` • ${escapeHtml(host.hostname)}` : "";
        const portsList = Array.isArray(host.ports) && host.ports.length ? host.ports.join(", ") : "";
        const portsText = portsList ? ` • Portas: ${escapeHtml(portsList)}` : "";
        const safeName = escapeHtml(host.name);
        const safeAddr = escapeHtml(host.address);
        const safeId = escapeHtml(host.id);
        return `
            <label class="network-discovery-item">
                <div class="network-discovery-meta">
                    <strong>${safeName}</strong>
                    <small>${safeAddr}${hostnameText}${portsText}</small>
                </div>
                <div>
                    ${host.already_exists ? '<span class="network-exists-badge">já cadastrado</span>' : ""}
                    <input type="checkbox" class="discover-host-check" data-id="${safeId}" ${disabled} ${checked}>
                </div>
            </label>
        `;
    }).join("");
}

async function discoverNetworkHosts() {
    const subnetInput = document.getElementById("discoverSubnet");
    const discoverBtn = document.getElementById("discoverBtn");
    const resultBox = document.getElementById("networkImportResult");
    if (!subnetInput || !discoverBtn) return;

    const subnet = String(subnetInput.value || "").trim();
    if (!subnet) {
        if (resultBox) setInlineState(resultBox, "Informe uma subnet no formato CIDR.", "warning");
        showToast("warning", "Informe uma subnet no formato CIDR.");
        return;
    }

    const originalDiscoverText = getButtonLabel(discoverBtn, "Descobrir rede");
    discoverBtn.disabled = true;
    setButtonLabel(discoverBtn, "Descobrindo...");
    if (resultBox) setInlineState(resultBox, "Executando descoberta...", "info");

    try {
        const res = await fetchWithAuth(`${API}/network/discover`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ subnet })
        });
        if (!res) return;

        const data = await res.json();
        if (!res.ok) {
            if (resultBox) setInlineState(resultBox, data.detail || "Erro na descoberta de rede.", "error");
            showToast("error", data.detail || "Erro na descoberta de rede.");
            return;
        }

        discoveredLanHosts = Array.isArray(data.hosts) ? data.hosts : [];
        renderDiscoveredLanHosts();
        if (resultBox) setInlineState(resultBox, "Descoberta concluída. Selecione os hosts para importar.", "success");
        showToast("success", `Descoberta concluída: ${data.found ?? discoveredLanHosts.length} host(s).`);
    } catch (err) {
        console.error("Erro na descoberta de rede:", err);
        if (resultBox) setInlineState(resultBox, "Falha ao executar descoberta de rede.", "error");
        showToast("error", "Falha ao executar descoberta de rede.");
    } finally {
        discoverBtn.disabled = false;
        setButtonLabel(discoverBtn, originalDiscoverText);
    }
}

function isValidIpv4Cidr(value) {
    const text = String(value || "").trim();
    const [ip, prefix] = text.split("/");
    if (!ip || prefix === undefined || text.split("/").length !== 2) return false;
    const prefixNum = Number(prefix);
    if (!Number.isInteger(prefixNum) || prefixNum < 0 || prefixNum > 32) return false;
    const octets = ip.split(".");
    if (octets.length !== 4) return false;
    return octets.every((octet) => {
        if (!/^\d{1,3}$/.test(octet)) return false;
        const n = Number(octet);
        return n >= 0 && n <= 255;
    });
}

async function preloadDiscoverySubnet() {
    const subnetInput = document.getElementById("discoverSubnet");
    if (!subnetInput) return;
    if (String(subnetInput.value || "").trim()) return;

    try {
        const res = await fetchWithAuth(`${API}/network/default-subnet`);
        if (!res || !res.ok) {
            console.warn("Não foi possível detectar subnet automática.");
            if (!String(subnetInput.value || "").trim()) {
                subnetInput.value = "192.168.1.0/24";
            }
            return;
        }
        const data = await res.json();
        const subnet = String(data?.subnet || "").trim();
        const isOversizedOrDocker = (s) => {
            const parts = s.split("/");
            if (parts.length !== 2) return false;
            const prefix = Number(parts[1]);
            if (prefix < 20) return true;
            if (s.startsWith("172.") && prefix <= 16) return true;
            return false;
        };

        if (isValidIpv4Cidr(subnet) && !isOversizedOrDocker(subnet) && !String(subnetInput.value || "").trim()) {
            subnetInput.value = subnet;
        } else if (!String(subnetInput.value || "").trim()) {
            subnetInput.value = "192.168.1.0/24";
        }
    } catch (err) {
        console.warn("Falha no preload da subnet automática:", err);
        if (!String(subnetInput.value || "").trim()) {
            subnetInput.value = "192.168.1.0/24";
        }
    }
}

async function importSelectedLanHosts() {
    const communityInput = document.getElementById("snmp_community") || document.getElementById("modal-snmp-community");
    const communityVal = communityInput ? communityInput.value.trim() : "netspot";

    const checks = Array.from(document.querySelectorAll(".discover-host-check:checked"));
    const selected = checks
        .map((check) => {
            const id = check.getAttribute("data-id");
            return discoveredLanHosts.find((h) => h.id === id);
        })
        .filter(Boolean)
        .map((host) => ({
            name: host.name,
            address: host.address,
            ports: Array.isArray(host.ports) ? host.ports : null,
            http_enabled: typeof host.http_enabled === "boolean" ? host.http_enabled : null,
            http_url: host.http_url || null,
            snmp_enabled: true,
            snmp_community: communityVal || "netspot"
        }));

    if (!selected.length) {
        showToast("warning", "Selecione ao menos um host para importar.");
        return;
    }

    const importBtn = document.getElementById("importSelectedBtn");
    const originalImportText = getButtonLabel(importBtn, "Adicionar selecionados");
    const resultBox = document.getElementById("networkImportResult");
    if (importBtn) {
        importBtn.disabled = true;
        setButtonLabel(importBtn, "Importando...");
    }

    try {
        const res = await fetchWithAuth(`${API}/network/import`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                hosts: selected,
                snmp_enabled: true,
                snmp_community: communityVal || "netspot"
            })
        });
        if (!res) return;

        const data = await res.json();
        if (!res.ok) {
            showToast("error", data.detail || "Erro ao importar hosts selecionados.");
            return;
        }

        if (resultBox) {
            setInlineState(
                resultBox,
                `Solicitados: ${data.requested} • Criados: ${data.created} • Ignorados: ${data.skipped}`,
                "success"
            );
        }

        const createdAddresses = new Set(
            (Array.isArray(data.results) ? data.results : [])
                .filter((r) => r.created)
                .map((r) => r.address)
        );
        discoveredLanHosts = discoveredLanHosts.map((host) =>
            createdAddresses.has(host.address) ? { ...host, already_exists: true } : host
        );
        renderDiscoveredLanHosts();
        await loadHosts();
        showToast("success", `${data.created} host(s) importado(s) com sucesso.`);
    } catch (err) {
        console.error("Erro ao importar hosts:", err);
        showToast("error", "Falha ao importar hosts selecionados.");
    } finally {
        if (importBtn) {
            importBtn.disabled = false;
            setButtonLabel(importBtn, originalImportText);
        }
    }
}

// ======================
// Listar e Atualizar Hosts
// ======================
function formatHostAddressLabel(h) {
    const addr = String(h?.address || "").trim();
    const resolvedIp = String(h?.last_resolved_ip || "").trim();
    if (resolvedIp && resolvedIp !== addr) {
        return `${addr} → ${resolvedIp}`;
    }
    return addr;
}

function buildResolvedIpSummaryLine(h) {
    const addr = String(h?.address || "").trim();
    const resolvedIp = String(h?.last_resolved_ip || "").trim();
    if (!resolvedIp || resolvedIp === addr) {
        return "";
    }
    const ttlSuffix = h?.dns_ttl != null ? ` (TTL ${h.dns_ttl}s)` : "";
    return `<small><b>IP resolvido (DNS):</b> ${escapeHtml(resolvedIp)}${escapeHtml(ttlSuffix)}</small>`;
}

function isSnmpConfigured(h) {
    return [
        h.cpu_usage,
        h.ram_usage,
        h.disk_usage,
        h.network_traffic,
        h.network_in_bps,
        h.network_out_bps
    ].some((value) => value !== null && value !== undefined);
}

function buildSnmpSectionMarkup(h) {
    const totalTrafficBps = Number(h.network_traffic) || 0;
    const downloadTrafficBps = Number(h.network_in_bps) || 0;
    const uploadTrafficBps = Number(h.network_out_bps) || 0;
    const maxTrafficBps = Math.max(totalTrafficBps, downloadTrafficBps, uploadTrafficBps, 1);
    const totalTrafficBar = calcRelativeBarWidth(totalTrafficBps, maxTrafficBps);
    const downloadTrafficBar = calcRelativeBarWidth(downloadTrafficBps, maxTrafficBps);
    const uploadTrafficBar = calcRelativeBarWidth(uploadTrafficBps, maxTrafficBps);

    return `
                <div class="metrics-section snmp-section">
                    <div class="snmp-header">
                        <div class="snmp-title">SNMP</div>
                        <div class="snmp-subtitle">Métricas estimadas via OIDs</div>
                    </div>
                    <div class="snmp-kpi-grid">
                        <div class="snmp-kpi-card">
                            <div class="snmp-kpi-head">
                                <small class="snmp-kpi-label" title="CPU">CPU</small>
                                <small class="snmp-kpi-value ${metricClass(h.cpu_usage)}">${metricPercent(h.cpu_usage)}</small>
                            </div>
                            <div class="snmp-kpi-bar"><span class="snmp-kpi-fill ${metricClass(h.cpu_usage)}" style="width:${metricBarWidth(h.cpu_usage)}%"></span></div>
                        </div>
                        <div class="snmp-kpi-card">
                            <div class="snmp-kpi-head">
                                <small class="snmp-kpi-label" title="RAM">RAM</small>
                                <small class="snmp-kpi-value ${metricClass(h.ram_usage)}">${metricPercent(h.ram_usage)}</small>
                            </div>
                            <div class="snmp-kpi-bar"><span class="snmp-kpi-fill ${metricClass(h.ram_usage)}" style="width:${metricBarWidth(h.ram_usage)}%"></span></div>
                        </div>
                        <div class="snmp-kpi-card">
                            <div class="snmp-kpi-head">
                                <small class="snmp-kpi-label" title="Disco">Disco</small>
                                <small class="snmp-kpi-value ${metricClass(h.disk_usage)}">${metricPercent(h.disk_usage)}</small>
                            </div>
                            <div class="snmp-kpi-bar"><span class="snmp-kpi-fill ${metricClass(h.disk_usage)}" style="width:${metricBarWidth(h.disk_usage)}%"></span></div>
                        </div>
                    </div>
                    <div class="snmp-traffic-panel">
                        <div class="snmp-traffic-row">
                            <small class="snmp-traffic-label" title="Tráfego de Rede">Tráfego de Rede</small>
                            <div class="snmp-mini-bar"><span style="width:${totalTrafficBar}%"></span></div>
                            <small class="snmp-traffic-value">${formatBps(h.network_traffic)}</small>
                        </div>
                        <div class="snmp-traffic-row">
                            <small class="snmp-traffic-label" title="Download (RX)">Download (RX)</small>
                            <div class="snmp-mini-bar"><span style="width:${downloadTrafficBar}%"></span></div>
                            <small class="snmp-traffic-value">${formatBps(h.network_in_bps)}</small>
                        </div>
                        <div class="snmp-traffic-row">
                            <small class="snmp-traffic-label" title="Upload (TX)">Upload (TX)</small>
                            <div class="snmp-mini-bar"><span style="width:${uploadTrafficBar}%"></span></div>
                            <small class="snmp-traffic-value">${formatBps(h.network_out_bps)}</small>
                        </div>
                    </div>
                </div>
    `;
}

function buildHostCardHTML(h) {
    const hostPorts = parseHostPorts(h);
    const hostAddressLabel = formatHostAddressLabel(h);
    const resolvedIpLineHtml = buildResolvedIpSummaryLine(h);
    const tcpPortsLabel = hostPorts.length ? hostPorts.join(", ") : "Nenhuma";
    const httpEnabled = !!h.http_enabled;
    const webCheckBadge = httpEnabled
        ? `<span class="web-check-badge web-check-on">Ativo</span>`
        : `<span class="web-check-badge web-check-off">Inativo</span>`;
    const httpProtocolLabel = httpEnabled
        ? (h.http_protocol ? String(h.http_protocol).toUpperCase() : "Aguardando")
        : "-";
    const monitorFlag = hostMonitorFlag(h);
    const causeClass = probableCauseClass(h);
    const incidentBadgeHtml = h.has_open_incident
        ? `<span class="incident-badge" title="Existe incidente aberto para este host">INCIDENTE ABERTO</span>`
        : "";

    let statusColor = "bg-secondary";
    if (h.status === "UP") statusColor = "bg-success";
    else if (h.status === "DOWN") statusColor = "bg-danger";
    else if (h.status === "DEGRADED") statusColor = "bg-warning";
    
    let sevClass = "sev-unknown";
    if (h.severity === "HEALTHY") sevClass = "sev-healthy";
    else if (h.severity === "WARNING") sevClass = "sev-warning";
    else if (h.severity === "DEGRADED") sevClass = "sev-degraded";
    else if (h.severity === "CRITICAL") sevClass = "sev-critical";
    const severityIndicatorHtml = h.icmp_blocked_but_service_up
        ? ""
        : `<span class="severity-indicator ${sevClass}" aria-hidden="true">✚</span>`;

    const availability10m = h.availability_10m != null
        ? h.availability_10m.toFixed(2)
        : "N/A";
    const snmpConfigured = isSnmpConfigured(h);
    const snmpStatusHtml = !snmpConfigured
        ? `<small class="snmp-tag snmp-tag-off snmp-empty-message">SNMP: não configurado</small>`
        : "";
    const snmpSectionHtml = snmpConfigured ? buildSnmpSectionMarkup(h) : "";
    const snmpChartBoxHtml = snmpConfigured ? `
        <div id="snmp-chart-box-${escapeHtml(h.name)}" class="chart-box hidden" style="margin-top: 10px;">
            <div class="chart-title">Histórico SNMP</div>
            <canvas id="snmp-chart-${escapeHtml(h.name)}" height="120" role="img" aria-label="Histórico de métricas SNMP do host ${escapeHtml(h.name)}">Gráfico de métricas SNMP indisponível em modo texto.</canvas>
        </div>
    ` : "";

    return `
        <!-- Header: identificação + indicadores rápidos -->
        <div class="host-card-header">
            <div class="host-top-line">
                <div class="host-title-wrap">
                    <span class="status-indicator ${statusColor}"></span>
                    <strong class="host-title">
                        ${escapeHtml(h.name)}
                        <small class="host-addr">(${escapeHtml(hostAddressLabel)})</small>
                        <button
                            class="copy-addr-btn"
                            type="button"
                            title="Copiar endereço (${escapeHtml(h.address)})"
                            aria-label="Copiar endereço (${escapeHtml(h.address)})"
                            onclick='copyHostAddress(${escapeJsSingleQuotedAttr(h.address)}, this, event)'
                        >
                            <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                                <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"></path>
                            </svg>
                        </button>
                    </strong>
                </div>
                <div class="host-top-actions">
                    <span class="host-monitor-flag ${monitorFlag.className}" title="Estado de monitoramento">${monitorFlag.label}</span>
                    ${incidentBadgeHtml}
                    <button
                        class="host-delete-btn"
                        type="button"
                        title="Excluir host"
                        aria-label="Excluir host"
                        onclick='softDeleteHost(${Number(h.id)}, ${escapeJsSingleQuotedAttr(h.name)})'
                    ><span aria-hidden="true">✕</span></button>
                </div>
            </div>

            <div class="host-meta-grid">
                <div class="host-meta-item"><small>Saúde</small><strong>${healthMeterHtml(h, severityIndicatorHtml)}</strong></div>
                <div class="host-meta-item"><small>Disponibilidade</small><strong>${availability10m}%</strong></div>
                <div class="host-meta-item"><small>Último check</small><strong>${formatCheckTime(h.last_check)}</strong></div>
                <div class="host-meta-item"><small>Último SNMP</small><strong>${formatCheckTime(h.last_snmp_check)}</strong></div>
            </div>
        </div>

        <div class="face-nav">
            <div class="face-segmented-control" role="tablist" aria-label="Faces do card de monitoramento">
                <button type="button" class="face-pill active" data-face-num="1" role="tab" aria-selected="true" title="Face 1: Resumo do host" onclick='setHostFace(${escapeJsSingleQuotedAttr(h.name)}, 1)'>Resumo</button>
                <button type="button" class="face-pill" data-face-num="2" role="tab" aria-selected="false" title="Face 2: Métricas de rede e SLA" onclick='setHostFace(${escapeJsSingleQuotedAttr(h.name)}, 2)'>Rede</button>
                <button type="button" class="face-pill" data-face-num="3" role="tab" aria-selected="false" title="Face 3: Hardware e telemetria SNMP" onclick='setHostFace(${escapeJsSingleQuotedAttr(h.name)}, 3)'>SNMP</button>
            </div>
            <div class="icon-actions">
                <button class="icon-btn" type="button" title="Histórico recente" aria-label="Histórico recente" onclick='toggleHistory(${escapeJsSingleQuotedAttr(h.name)})'>${iconSvg("history")}</button>
                <button class="icon-btn" type="button" title="Gráfico de latência" aria-label="Gráfico de latência" onclick='toggleLatencyChart(${escapeJsSingleQuotedAttr(h.name)})'>${iconSvg("latency")}</button>
                ${snmpConfigured ? `<button class="icon-btn" type="button" title="Gráfico SNMP" aria-label="Gráfico SNMP" onclick='toggleSnmpChart(${escapeJsSingleQuotedAttr(h.name)})'>${iconSvg("snmp")}</button>` : ""}
                <button class="icon-btn" type="button" title="Disponibilidade por tipo" aria-label="Disponibilidade por tipo" onclick='toggleAvailabilityChartType(${escapeJsSingleQuotedAttr(h.name)})'>${iconSvg("availability_type")}</button>
                <button class="icon-btn" type="button" title="Disponibilidade geral" aria-label="Disponibilidade geral" onclick='toggleAvailabilityChart(${escapeJsSingleQuotedAttr(h.name)})'>${iconSvg("availability")}</button>
                <button class="icon-btn" type="button" title="Editar host" aria-label="Editar host" onclick='openEditModal(${escapeJsSingleQuotedAttr(h.name)})'>${iconSvg("edit")}</button>
            </div>
        </div>

        <!-- Body: três colunas (Resumo | Rede | SNMP) -->
        <div class="host-card-body compact host-faces-wrap">
            <div class="host-col host-col-summary host-face active" data-face="1">
                <div class="host-section-card">
                    <div class="metrics-title">Resumo</div>
                    <div class="host-summary-list">
                        ${resolvedIpLineHtml}
                        <small><b>Portas TCP monitoradas:</b> ${tcpPortsLabel}</small>
                        <small><b>Check Web:</b> ${webCheckBadge}</small>
                        <small><b>Protocolo resolvido:</b> ${httpProtocolLabel}</small>
                        <small><b>Saúde:</b> ${h.health_score ?? "N/A"}%</small>
                        <small><b>Disponibilidade:</b> ${availability10m}%</small>
                        <small><b>Tendência HTTP:</b> ${trendIcon(h.trend_http)} ${h.trend_http ?? "N/A"}</small>
                        <small><b>Causa provável:</b></small>
                        <small class="cause-pill ${causeClass}">${escapeHtml(h.probable_cause ?? "Operação normal")}</small>
                    </div>
                </div>
            </div>

            <div class="host-col host-col-network host-face" data-face="2">
                <div class="host-section-card">
                    <div class="metrics-title">Rede</div>
                    <div class="network-split">
                        <div class="network-col">
                            <small><b>Taxa de sucesso</b></small>
                            <small>Ping: ${h.sla_rolling_ping ?? "N/A"}%</small>
                            <small>TCP: ${h.sla_rolling_tcp ?? "N/A"}%</small>
                            <small>HTTP: ${h.http_enabled === false ? "Inativo" : (h.sla_rolling_http !== null && h.sla_rolling_http !== undefined ? `${h.sla_rolling_http}%` : "N/A")}</small>
                        </div>
                        <div class="network-col">
                            <small><b>Variação na latência</b></small>
                            <small>Ping: ${h.jitter_ms_ping ?? "N/A"} ms</small>
                            <small>TCP: ${h.jitter_ms_tcp ?? "N/A"} ms</small>
                            <small>HTTP: ${h.http_enabled === false ? "Inativo" : (h.jitter_ms_http !== null && h.jitter_ms_http !== undefined ? `${h.jitter_ms_http} ms` : "N/A")}</small>
                        </div>
                    </div>
                    <div class="host-checks-section">
                        <div class="metrics-title">Últimos checks</div>
                        <div id="result-${escapeHtml(h.name)}" class="host-last-checks">
                            <i>Atualizando...</i>
                        </div>
                    </div>
                    <div class="tcp-ports-section">
                        <div class="metrics-title">Portas TCP monitoradas</div>
                        <div id="tcp-ports-status-${escapeHtml(h.name)}" class="tcp-ports-status">
                            <small class="tcp-ports-empty">Atualizando...</small>
                        </div>
                    </div>
                </div>
            </div>

            <div class="host-col host-col-snmp host-face" data-face="3">
                ${snmpConfigured ? snmpSectionHtml : `
                    <div class="host-section-card snmp-section snmp-empty">
                        <div class="snmp-header">
                            <div class="snmp-title">SNMP</div>
                            <div class="snmp-subtitle">Métricas estimadas via OIDs</div>
                        </div>
                        <div class="snmp-empty-body">
                            ${snmpStatusHtml}
                        </div>
                    </div>
                `}
            </div>
        </div>

        <div id="chart-container-${escapeHtml(h.name)}" class="chart-box hidden" style="margin-top: 10px;">
            <div class="chart-title">Latência dos checks</div>
            <canvas id="chart-${escapeHtml(h.name)}" height="120" role="img" aria-label="Histórico de latência e ping do host ${escapeHtml(h.name)}">Gráfico de latência indisponível em modo texto.</canvas>
        </div>
        ${snmpChartBoxHtml}
        <div id="availability-chart-type-box-${escapeHtml(h.name)}" class="chart-box hidden">
            <div class="chart-title">Disponibilidade por tipo</div>
            <canvas id="availability-chart-type-${escapeHtml(h.name)}" height="120" role="img" aria-label="Disponibilidade por protocolo de ${escapeHtml(h.name)}">Gráfico de disponibilidade por protocolo indisponível em modo texto.</canvas>
        </div>
        <div id="availability-chart-box-${escapeHtml(h.name)}" class="chart-box hidden">
            <div class="chart-title">Disponibilidade geral</div>
            <canvas id="availability-chart-${escapeHtml(h.name)}" height="120" role="img" aria-label="Disponibilidade geral dos últimos 10 minutos de ${escapeHtml(h.name)}">Gráfico de disponibilidade geral indisponível em modo texto.</canvas>
        </div>
        <div id="history-${escapeHtml(h.name)}" class="history-box hidden"></div>
    `;
}

function updateHostCardInPlace(card, h) {
    const visualState = hostVisualState(h);
    const monitorFlag = hostMonitorFlag(h);
    const causeClass = probableCauseClass(h);
    const hostPorts = parseHostPorts(h);
    const tcpPortsLabel = hostPorts.length ? hostPorts.join(", ") : "Nenhuma";
    const httpEnabled = !!h.http_enabled;
    const webCheckBadge = httpEnabled
        ? `<span class="web-check-badge web-check-on">Ativo</span>`
        : `<span class="web-check-badge web-check-off">Inativo</span>`;
    const httpProtocolLabel = httpEnabled
        ? (h.http_protocol ? String(h.http_protocol).toUpperCase() : "Aguardando")
        : "-";

    const availability10m = h.availability_10m != null
        ? h.availability_10m.toFixed(2)
        : "N/A";

    let statusColor = "bg-secondary";
    if (h.status === "UP") statusColor = "bg-success";
    else if (h.status === "DOWN") statusColor = "bg-danger";
    else if (h.status === "DEGRADED") statusColor = "bg-warning";

    let sevClass = "sev-unknown";
    if (h.severity === "HEALTHY") sevClass = "sev-healthy";
    else if (h.severity === "WARNING") sevClass = "sev-warning";
    else if (h.severity === "DEGRADED") sevClass = "sev-degraded";
    else if (h.severity === "CRITICAL") sevClass = "sev-critical";

    const severityIndicatorHtml = h.icmp_blocked_but_service_up
        ? ""
        : `<span class="severity-indicator ${sevClass}" aria-hidden="true">✚</span>`;

    // 1. Preservar o estado da face ativa e atualizar a classe visual do card
    const currentFace = card.dataset.face || "1";
    card.className = `card ${visualState.cardClass}`;
    card.dataset.face = currentFace;

    // 2. Indicador de status (bolinha verde/vermelha/amarela) e endereço/IP resolvido
    const statusIndicator = card.querySelector(".status-indicator");
    if (statusIndicator) {
        statusIndicator.className = `status-indicator ${statusColor}`;
    }
    const addrEl = card.querySelector(".host-addr");
    if (addrEl) {
        addrEl.textContent = `(${formatHostAddressLabel(h)})`;
    }

    // 3. Flag de monitoramento (MONITORANDO / PAUSADO / OFFLINE)
    const flagEl = card.querySelector(".host-monitor-flag");
    if (flagEl) {
        flagEl.className = `host-monitor-flag ${monitorFlag.className}`;
        flagEl.textContent = monitorFlag.label;
    }

    // 4. Badge de Incidente Aberto
    let incidentBadgeEl = card.querySelector(".incident-badge");
    if (h.has_open_incident) {
        if (!incidentBadgeEl) {
            const actionsWrap = card.querySelector(".host-top-actions");
            if (actionsWrap) {
                const badgeSpan = document.createElement("span");
                badgeSpan.className = "incident-badge";
                badgeSpan.title = "Existe incidente aberto para este host";
                badgeSpan.textContent = "INCIDENTE ABERTO";
                const deleteBtn = actionsWrap.querySelector(".host-delete-btn");
                if (deleteBtn) {
                    actionsWrap.insertBefore(badgeSpan, deleteBtn);
                } else {
                    actionsWrap.appendChild(badgeSpan);
                }
            }
        }
    } else if (incidentBadgeEl) {
        incidentBadgeEl.remove();
    }

    // 5. Grid de Metadados do Header (Saúde, Disponibilidade, Último Check, Último SNMP)
    const metaGrid = card.querySelector(".host-meta-grid");
    if (metaGrid) {
        const items = metaGrid.querySelectorAll(".host-meta-item strong");
        if (items.length >= 4) {
            items[0].innerHTML = healthMeterHtml(h, severityIndicatorHtml);
            items[1].textContent = `${availability10m}%`;
            items[2].textContent = formatCheckTime(h.last_check);
            items[3].textContent = formatCheckTime(h.last_snmp_check);
        }
    }

    // 6. Resumo na Face 1
    const summaryList = card.querySelector(".host-summary-list");
    if (summaryList) {
        const resolvedIpLineHtml = buildResolvedIpSummaryLine(h);
        summaryList.innerHTML = `
            ${resolvedIpLineHtml}
            <small><b>Portas TCP monitoradas:</b> ${tcpPortsLabel}</small>
            <small><b>Check Web:</b> ${webCheckBadge}</small>
            <small><b>Protocolo resolvido:</b> ${httpProtocolLabel}</small>
            <small><b>Saúde:</b> ${h.health_score ?? "N/A"}%</small>
            <small><b>Disponibilidade:</b> ${availability10m}%</small>
            <small><b>Tendência HTTP:</b> ${trendIcon(h.trend_http)} ${h.trend_http ?? "N/A"}</small>
            <small><b>Causa provável:</b></small>
            <small class="cause-pill ${causeClass}">${escapeHtml(h.probable_cause ?? "Operação normal")}</small>
        `;
    }

    // 7. Métricas de Rede na Face 2 (SLAs e Jitters)
    const networkSplit = card.querySelector(".network-split");
    if (networkSplit) {
        const netCols = networkSplit.querySelectorAll(".network-col");
        if (netCols.length >= 2) {
            netCols[0].innerHTML = `
                <small><b>Taxa de sucesso</b></small>
                <small>Ping: ${h.sla_rolling_ping ?? "N/A"}%</small>
                <small>TCP: ${h.sla_rolling_tcp ?? "N/A"}%</small>
                <small>HTTP: ${h.http_enabled === false ? "Inativo" : (h.sla_rolling_http !== null && h.sla_rolling_http !== undefined ? `${h.sla_rolling_http}%` : "N/A")}</small>
            `;
            netCols[1].innerHTML = `
                <small><b>Variação na latência</b></small>
                <small>Ping: ${h.jitter_ms_ping ?? "N/A"} ms</small>
                <small>TCP: ${h.jitter_ms_tcp ?? "N/A"} ms</small>
                <small>HTTP: ${h.http_enabled === false ? "Inativo" : (h.jitter_ms_http !== null && h.jitter_ms_http !== undefined ? `${h.jitter_ms_http} ms` : "N/A")}</small>
            `;
        }
    }

    // 8. Métricas SNMP na Face 3 (KPIs de CPU, RAM, Disco e Tráfego)
    const snmpConfigured = isSnmpConfigured(h);
    let snmpKpiGrid = card.querySelector(".snmp-kpi-grid");

    if (snmpConfigured && !snmpKpiGrid) {
        const snmpCol = card.querySelector(".host-col-snmp");
        if (snmpCol) {
            snmpCol.innerHTML = buildSnmpSectionMarkup(h);
        }
        const iconActions = card.querySelector(".icon-actions");
        if (iconActions && !iconActions.querySelector('button[title="Gráfico SNMP"]')) {
            const snmpBtn = document.createElement("button");
            snmpBtn.className = "icon-btn";
            snmpBtn.type = "button";
            snmpBtn.title = "Gráfico SNMP";
            snmpBtn.setAttribute("aria-label", "Gráfico SNMP");
            snmpBtn.onclick = () => toggleSnmpChart(h.name);
            snmpBtn.innerHTML = iconSvg("snmp");
            const latBtn = iconActions.querySelector('button[title="Gráfico de latência"]');
            if (latBtn && latBtn.nextSibling) {
                iconActions.insertBefore(snmpBtn, latBtn.nextSibling);
            } else {
                iconActions.appendChild(snmpBtn);
            }
        }
        if (!document.getElementById(`snmp-chart-box-${h.name}`)) {
            const chartBox = document.createElement("div");
            chartBox.id = `snmp-chart-box-${h.name}`;
            chartBox.className = "chart-box hidden";
            chartBox.style.marginTop = "10px";
            chartBox.innerHTML = `
                <div class="chart-title">Histórico SNMP</div>
                <canvas id="snmp-chart-${escapeHtml(h.name)}" height="120" role="img" aria-label="Histórico de métricas SNMP do host ${escapeHtml(h.name)}">Gráfico de métricas SNMP indisponível em modo texto.</canvas>
            `;
            const latBox = document.getElementById(`chart-container-${h.name}`);
            if (latBox && latBox.parentNode) {
                latBox.parentNode.insertBefore(chartBox, latBox.nextSibling);
            } else {
                card.appendChild(chartBox);
            }
        }
        return;
    }

    const totalTrafficBps = Number(h.network_traffic) || 0;
    const downloadTrafficBps = Number(h.network_in_bps) || 0;
    const uploadTrafficBps = Number(h.network_out_bps) || 0;
    const maxTrafficBps = Math.max(totalTrafficBps, downloadTrafficBps, uploadTrafficBps, 1);
    const totalTrafficBar = calcRelativeBarWidth(totalTrafficBps, maxTrafficBps);
    const downloadTrafficBar = calcRelativeBarWidth(downloadTrafficBps, maxTrafficBps);
    const uploadTrafficBar = calcRelativeBarWidth(uploadTrafficBps, maxTrafficBps);

    if (snmpKpiGrid) {
        const kpiCards = snmpKpiGrid.querySelectorAll(".snmp-kpi-card");
        if (kpiCards.length >= 3) {
            updateKpiCardInPlace(kpiCards[0], h.cpu_usage);
            updateKpiCardInPlace(kpiCards[1], h.ram_usage);
            updateKpiCardInPlace(kpiCards[2], h.disk_usage);
        }
    }

    const trafficPanel = card.querySelector(".snmp-traffic-panel");
    if (trafficPanel) {
        const rows = trafficPanel.querySelectorAll(".snmp-traffic-row");
        if (rows.length >= 3) {
            updateTrafficRowInPlace(rows[0], formatBps(h.network_traffic), totalTrafficBar);
            updateTrafficRowInPlace(rows[1], formatBps(h.network_in_bps), downloadTrafficBar);
            updateTrafficRowInPlace(rows[2], formatBps(h.network_out_bps), uploadTrafficBar);
        }
    }
}

function updateKpiCardInPlace(kpiCard, value) {
    const valEl = kpiCard.querySelector(".snmp-kpi-value");
    const fillEl = kpiCard.querySelector(".snmp-kpi-fill");
    if (valEl) {
        valEl.className = `snmp-kpi-value ${metricClass(value)}`;
        valEl.textContent = metricPercent(value);
    }
    if (fillEl) {
        fillEl.className = `snmp-kpi-fill ${metricClass(value)}`;
        fillEl.style.width = `${metricBarWidth(value)}%`;
    }
}

function updateTrafficRowInPlace(row, formattedValue, barWidth) {
    const valEl = row.querySelector(".snmp-traffic-value");
    const barEl = row.querySelector(".snmp-mini-bar span");
    if (valEl) valEl.textContent = formattedValue;
    if (barEl) barEl.style.width = `${barWidth}%`;
}

function refreshVisibleChartsForHost(hostName) {
    const historyBox = document.getElementById("history-" + hostName);
    if (historyBox && !historyBox.classList.contains("hidden")) {
        loadHistory(hostName, true);
    }

    const availBox = document.getElementById("availability-chart-box-" + hostName);
    if (availBox && !availBox.classList.contains("hidden")) {
        loadAvailability(hostName);
    }

    const latencyBox = document.getElementById("chart-container-" + hostName);
    if (latencyBox && !latencyBox.classList.contains("hidden")) {
        loadLatencyChart(hostName);
    }

    const snmpBox = document.getElementById("snmp-chart-box-" + hostName);
    if (snmpBox && !snmpBox.classList.contains("hidden")) {
        loadSnmpChart(hostName);
    }

    const availTypeBox = document.getElementById("availability-chart-type-box-" + hostName);
    if (availTypeBox && !availTypeBox.classList.contains("hidden")) {
        loadAvailabilityChartType(hostName);
    }
}

// ============================================================================
// VISUALIZAÇÃO EM ALTA DENSIDADE (FASE 3: CARDS 3D VS TABELA NOC)
// ============================================================================

let currentViewMode = "cards";
try {
    currentViewMode = localStorage.getItem("netspot_view_mode") || "cards";
} catch (_) {
    currentViewMode = "cards";
}

function setViewMode(mode) {
    if (mode !== "cards" && mode !== "table") mode = "cards";
    currentViewMode = mode;
    try {
        localStorage.setItem("netspot_view_mode", mode);
    } catch (_) {}

    const cardsContainer = document.getElementById("hosts");
    const tableContainer = document.getElementById("hostsTableView");
    const btnCards = document.getElementById("viewCardsBtn");
    const btnTable = document.getElementById("viewTableBtn");

    if (cardsContainer) {
        cardsContainer.classList.toggle("hidden", mode !== "cards");
    }
    if (tableContainer) {
        tableContainer.classList.toggle("hidden", mode !== "table");
    }
    if (btnCards) {
        btnCards.classList.toggle("active", mode === "cards");
        btnCards.setAttribute("aria-pressed", mode === "cards" ? "true" : "false");
    }
    if (btnTable) {
        btnTable.classList.toggle("active", mode === "table");
        btnTable.setAttribute("aria-pressed", mode === "table" ? "true" : "false");
    }
}

function initViewMode() {
    let saved = "cards";
    try {
        saved = localStorage.getItem("netspot_view_mode") || "cards";
    } catch (_) {}
    setViewMode(saved);

    const btnCards = document.getElementById("viewCardsBtn");
    const btnTable = document.getElementById("viewTableBtn");
    if (btnCards && !btnCards.dataset.listenerBound) {
        btnCards.addEventListener("click", () => setViewMode("cards"));
        btnCards.dataset.listenerBound = "true";
    }
    if (btnTable && !btnTable.dataset.listenerBound) {
        btnTable.addEventListener("click", () => setViewMode("table"));
        btnTable.dataset.listenerBound = "true";
    }
}

function focusHostCard(hostName) {
    setViewMode("cards");
    setTimeout(() => {
        const card = document.getElementById(`card-${hostName}`);
        if (!card) return;
        card.scrollIntoView({ behavior: "smooth", block: "center" });
        card.classList.add("card-highlight-pulse");
        setTimeout(() => card.classList.remove("card-highlight-pulse"), 2200);
    }, 60);
}

function buildNocTableRowHTML(h) {
    const visualState = hostVisualState(h);
    const causeClass = probableCauseClass(h);
    const hostAddressLabel = formatHostAddressLabel(h);

    let statusDot = "bg-secondary";
    if (h.status === "UP") statusDot = "bg-success";
    else if (h.status === "DOWN") statusDot = "bg-danger";
    else if (h.status === "DEGRADED") statusDot = "bg-warning";

    let sevClass = "sev-unknown";
    if (h.severity === "HEALTHY") sevClass = "sev-healthy";
    else if (h.severity === "WARNING") sevClass = "sev-warning";
    else if (h.severity === "DEGRADED") sevClass = "sev-degraded";
    else if (h.severity === "CRITICAL") sevClass = "sev-critical";
    const severityIndicatorHtml = h.icmp_blocked_but_service_up
        ? ""
        : `<span class="severity-indicator ${sevClass}" aria-hidden="true">✚</span>`;

    const availability10m = h.availability_10m != null
        ? h.availability_10m.toFixed(2)
        : "N/A";

    const availNum = Number(h.availability_10m);
    let availClass = "sla-high";
    if (Number.isFinite(availNum)) {
        if (availNum < 90) availClass = "sla-low";
        else if (availNum < 98) availClass = "sla-mid";
    }

    // Ping check
    let pingText = "sem dados";
    let pingDot = "bg-secondary";
    if (h.icmp_blocked_but_service_up) {
        pingText = "ICMP Bloq.";
        pingDot = "bg-secondary";
    } else if (h.status_ping === "UP") {
        pingText = h.latency_ping != null ? `${h.latency_ping} ms` : "OK";
        pingDot = "bg-success";
    } else if (h.status_ping === "DOWN") {
        pingText = "Timeout";
        pingDot = "bg-danger";
    }

    // Web check
    let webHtml = `<span class="noc-badge-off">Inativo</span>`;
    if (h.http_enabled) {
        const proto = h.http_protocol ? String(h.http_protocol).toUpperCase() : "HTTP";
        const lat = h.http_latency ?? h.https_latency;
        const latText = lat != null ? `${lat} ms` : "Aguardando";
        const isOk = lat != null;
        webHtml = `<span class="noc-badge-proto ${isOk ? "proto-ok" : "proto-err"}">${escapeHtml(proto)} <small>(${escapeHtml(latText)})</small></span>`;
    }

    // Portas TCP
    const ports = parseHostPorts(h);
    let tcpHtml = `<span class="noc-empty-text">—</span>`;
    if (ports.length > 0) {
        tcpHtml = `<div class="noc-ports-wrap">${ports.map((p) => `<span class="noc-port-pill">${p}</span>`).join("")}</div>`;
    }

    const incidentHtml = h.has_open_incident
        ? `<span class="noc-incident-dot" title="Existe incidente em aberto para este host" aria-label="Incidente em aberto"><span aria-hidden="true">!</span></span>`
        : "";

    return `
      <tr id="row-${escapeHtml(h.name)}" class="noc-row ${visualState.cardClass}" data-host-name="${escapeHtml(h.name)}">
        <td class="noc-col-status">
          <div class="noc-status-cell">
            <span class="status-indicator ${statusDot}"></span>
            <span class="noc-status-label ${visualState.badgeClass}">${visualState.label}</span>
            ${incidentHtml}
          </div>
        </td>
        <td class="noc-col-device">
          <div class="noc-device-cell">
            <strong class="noc-device-name">${escapeHtml(h.name)}</strong>
            <span class="noc-device-addr">
              ${escapeHtml(hostAddressLabel)}
              <button
                class="copy-addr-btn"
                type="button"
                title="Copiar endereço (${escapeHtml(h.address)})"
                aria-label="Copiar endereço (${escapeHtml(h.address)})"
                onclick='copyHostAddress(${escapeJsSingleQuotedAttr(h.address)}, this, event)'
              >
                <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                  <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"></path>
                </svg>
              </button>
            </span>
          </div>
        </td>
        <td class="noc-col-health">
          <div class="noc-health-cell">
            ${healthMeterHtml(h, severityIndicatorHtml)}
          </div>
        </td>
        <td class="noc-col-sla">
          <span class="noc-sla-badge ${availClass}">${availability10m}%</span>
        </td>
        <td class="noc-col-ping">
          <span class="noc-ping-cell">
            <span class="status-indicator ${pingDot}"></span>
            <span>${escapeHtml(pingText)}</span>
          </span>
        </td>
        <td class="noc-col-web">
          ${webHtml}
        </td>
        <td class="noc-col-tcp">
          ${tcpHtml}
        </td>
        <td class="noc-col-cause">
          <span class="cause-pill ${causeClass}">${escapeHtml(h.probable_cause ?? "Operação normal")}</span>
        </td>
        <td class="noc-col-actions">
          <div class="noc-actions-cell">
            <button class="noc-action-btn" type="button" title="Focar no Card 3D" aria-label="Focar no Card 3D" onclick='focusHostCard(${escapeJsSingleQuotedAttr(h.name)})'>
              <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
            </button>
            <button class="noc-action-btn" type="button" title="Editar host" aria-label="Editar host" onclick='openEditModal(${escapeJsSingleQuotedAttr(h.name)})'>
              ${iconSvg("edit")}
            </button>
            <button class="noc-action-btn noc-btn-danger" type="button" title="Mover para lixeira" aria-label="Mover para lixeira" onclick='softDeleteHost(${Number(h.id)}, ${escapeJsSingleQuotedAttr(h.name)})'>
              ${iconSvg("trash")}
            </button>
          </div>
        </td>
      </tr>
    `;
}

function renderNocTable(hosts) {
    const tbody = document.getElementById("nocTableBody");
    if (!tbody) return;

    if (!Array.isArray(hosts) || hosts.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" class="noc-table-empty">Nenhum host monitorado no momento.</td></tr>';
        return;
    }

    tbody.innerHTML = hosts.map(buildNocTableRowHTML).join("");
}

function buildSkeletonCardsHTML() {
    const card = `
        <div class="skeleton-card" aria-hidden="true">
            <div class="skeleton-header">
                <div class="skeleton-line skeleton-title"></div>
                <div class="skeleton-pill"></div>
            </div>
            <div class="skeleton-meta-grid">
                <div class="skeleton-meta-box"></div>
                <div class="skeleton-meta-box"></div>
                <div class="skeleton-meta-box"></div>
                <div class="skeleton-meta-box"></div>
            </div>
            <div class="skeleton-tabs">
                <div class="skeleton-tab"></div>
                <div class="skeleton-tab"></div>
                <div class="skeleton-tab"></div>
            </div>
            <div class="skeleton-body">
                <div class="skeleton-line"></div>
                <div class="skeleton-line short"></div>
                <div class="skeleton-bar"></div>
            </div>
        </div>
    `;
    return `<div class="skeleton-wrap" aria-busy="true" aria-label="Carregando lista de hosts...">${card.repeat(6)}</div>`;
}

function buildSkeletonTableRowsHTML() {
    return Array(6).fill(0).map(() => `
        <tr class="skeleton-row" aria-hidden="true">
            <td><div class="skeleton-dot"></div></td>
            <td><div class="skeleton-line" style="width: 130px;"></div></td>
            <td><div class="skeleton-bar" style="width: 85px;"></div></td>
            <td><div class="skeleton-line" style="width: 55px;"></div></td>
            <td><div class="skeleton-line" style="width: 50px;"></div></td>
            <td><div class="skeleton-line" style="width: 65px;"></div></td>
            <td><div class="skeleton-line" style="width: 75px;"></div></td>
            <td><div class="skeleton-line" style="width: 120px;"></div></td>
            <td><div class="skeleton-line" style="width: 65px; margin-left: auto;"></div></td>
        </tr>
    `).join("");
}

async function loadHosts() {
    const div = document.getElementById("hosts");
    const tbody = document.getElementById("nocTableBody");
    if (!div) return;

    if (!div.querySelector(".card") && !div.querySelector(".skeleton-wrap") && !div.querySelector(".ui-state")) {
        div.innerHTML = buildSkeletonCardsHTML();
    }
    if (tbody && tbody.children.length === 0) {
        tbody.innerHTML = buildSkeletonTableRowsHTML();
    }

    const thisRequestId = ++hostsListRequestId;

    try {
        const res = await fetchWithAuth(`${API}/hosts/list`);
        if (!res) {
            if (!div.querySelector(".card")) {
                div.innerHTML = "<div class='ui-state ui-state-warning'>Não foi possível carregar os hosts.</div>";
            }
            return;
        }

        const rawHosts = await res.json();
        // Se uma requisição mais recente já foi iniciada, descarta a resposta obsoleta (previne race conditions)
        if (thisRequestId !== hostsListRequestId) return;

        if (!Array.isArray(rawHosts)) {
            return;
        }

        // Blindagem contra race conditions: filtra imediatamente qualquer host com exclusão pendente
        const hosts = rawHosts.filter((h) => !pendingDeletedHostNames.has(h.name));

        if (hosts.length === 0) {
            const existingCardNodes = Array.from(div.querySelectorAll(".card"));
            for (const cardNode of existingCardNodes) {
                const cardHostName = cardNode.id.replace("card-", "");
                destroyChartsForHost(cardHostName);
                cardNode.remove();
            }
            currentHostsMap.clear();
            div.innerHTML = "<div class='ui-state ui-state-empty'>Nenhum host cadastrado ainda.</div>";
            const tbody = document.getElementById("nocTableBody");
            if (tbody) tbody.innerHTML = '<tr><td colspan="9" class="noc-table-empty">Nenhum host monitorado no momento.</td></tr>';
            const countBadge = document.getElementById("hostsCountBadge");
            if (countBadge) {
                countBadge.textContent = "0 hosts";
                countBadge.classList.remove("is-filtered");
            }
            updateStatusChipCounts();
            return;
        }

        if (div.querySelector(".ui-state") || div.querySelector(".skeleton-wrap")) {
            div.innerHTML = "";
        }

        const activeHostNames = new Set(hosts.map((h) => h.name));
        currentHostsMap.clear();
        for (const h of hosts) {
            currentHostsMap.set(h.name, h);
        }

        // 1. Remover apenas cards de hosts que foram efetivamente excluídos e liberar instâncias Chart.js
        const existingCardNodes = Array.from(div.querySelectorAll(".card"));
        for (const cardNode of existingCardNodes) {
            const cardHostName = cardNode.id.replace("card-", "");
            if (!activeHostNames.has(cardHostName) || pendingDeletedHostNames.has(cardHostName)) {
                destroyChartsForHost(cardHostName);
                cardNode.remove();
            }
        }

        // 2. Criar ou Atualizar cirurgicamente (in-place) cada card de host
        for (const h of hosts) {
            if (pendingDeletedHostNames.has(h.name)) continue;

            let card = document.getElementById(`card-${h.name}`);
            const isNewCard = !card;

            if (isNewCard) {
                card = document.createElement("div");
                card.className = `card ${hostVisualState(h).cardClass}`;
                card.id = `card-${h.name}`;
                card.dataset.face = "1";
                card.innerHTML = buildHostCardHTML(h);
                div.appendChild(card);
                updateHostFace(h.name, 1);
            } else {
                updateHostCardInPlace(card, h);
            }

            // Atualiza checks de Ping / TCP em tempo real
            loadLastResult(
                h.name,
                parseHostPorts(h),
                !!h.http_enabled,
                h.http_protocol,
                h.http_latency ?? h.https_latency,
                h.tcp_http_port_latency,
                h.tcp_https_port_latency,
                h.tcp_http_port_ok,
                h.tcp_https_port_ok,
                h.status_ping,
                h.latency_ping,
                !!h.icmp_blocked_but_service_up,
                h.status_tcp,
                h.latency_tcp
            );

            // Atualiza gráficos ativos sem piscar
            refreshVisibleChartsForHost(h.name);
        }

        // 3. Renderiza tabela NOC em alta densidade (Fase 3)
        renderNocTable(hosts);

        // Sincroniza busca, filtros e badge de contagem
        filterHosts();
        updateStatusChipCounts();
    } catch (err) {
        console.error("Erro ao carregar lista de hosts:", err);
        if (div.querySelector(".skeleton-wrap")) {
            div.innerHTML = "<div class='ui-state ui-state-warning'>Não foi possível carregar os hosts.</div>";
        }
        const tbody = document.getElementById("nocTableBody");
        if (tbody && tbody.querySelector(".skeleton-row")) {
            tbody.innerHTML = '<tr><td colspan="9" class="noc-table-empty">Não foi possível carregar os dados da tabela.</td></tr>';
        }
    }
}

async function loadHostsQuick() {
    await loadHosts();
}

function tcpFailureLabel(error) {
    const text = String(error || "").toLowerCase();
    if (!text) return "falha";
    if (text.includes("timeout")) return "timeout";
    if (text.includes("refused") || text.includes("unreachable")) return "indisponível";
    return "falha";
}

function renderTcpPortsStatus(hostName, checks, expectedPorts = []) {
    const box = document.getElementById(`tcp-ports-status-${hostName}`);
    if (!box) return;

    const tcpChecks = Array.isArray(checks) ? checks.filter((c) => c.type === "tcp") : [];
    const latestByPort = new Map();
    for (const item of tcpChecks) {
        const port = Number(item.tcp_port);
        if (!Number.isInteger(port)) continue;
        if (!latestByPort.has(port)) latestByPort.set(port, item);
    }

    const ports = Array.from(
        new Set(expectedPorts.filter((p) => Number.isInteger(Number(p))).map((p) => Number(p)))
    ).sort((a, b) => a - b);

    if (!ports.length) {
        box.innerHTML = "<small class='tcp-ports-empty'>Sem portas TCP configuradas.</small>";
        return;
    }

    box.innerHTML = ports.map((port) => {
        const item = latestByPort.get(port);
        const ok = !!item?.success;
        const dot = ok ? "bg-success" : "bg-danger";
        const rightText = item
            ? (ok ? `${item.latency ?? "N/A"} ms` : tcpFailureLabel(item.error))
            : "sem dados";
        return `
            <div class="tcp-port-item">
                <span class="status-indicator ${dot}"></span>
                <span class="tcp-port-label">TCP ${port}:</span>
                <span class="tcp-port-meta">${rightText}</span>
            </div>
        `;
    }).join("");
}

async function loadLastResult(
    name,
    expectedPorts = [],
    httpEnabled = true,
    httpProtocol = null,
    httpLatency = null,
    tcpHttpPortLatency = null,
    tcpHttpsPortLatency = null,
    tcpHttpPortOk = null,
    tcpHttpsPortOk = null,
    statusPing = null,
    latencyPing = null,
    icmpBlocked = false,
    statusTcp = null,
    latencyTcp = null
) {
    const box = document.getElementById("result-" + name);
    if (!box) return;

    let lastPing = null;
    let lastHttp = null;

    if (statusPing === "UP" || statusPing === "DOWN") {
        lastPing = {
            success: statusPing === "UP",
            latency: latencyPing,
            error: statusPing === "DOWN" ? "timeout" : null,
        };
    }
    if (httpEnabled) {
        lastHttp = {
            success: httpLatency !== null && httpLatency !== undefined,
            latency: httpLatency,
        };
    }

    const normalizedPorts = Array.isArray(expectedPorts)
        ? Array.from(new Set(expectedPorts.map((p) => Number(p)).filter((p) => Number.isInteger(p))))
        : [];

    if (normalizedPorts.length > 0) {
        const canSynthesizeSingle =
            normalizedPorts.length === 1 && (statusTcp === "UP" || statusTcp === "DOWN");
        const canSynthesizeWebPorts =
            normalizedPorts.every(
                (p) =>
                    (p === 80 && tcpHttpPortOk !== null && tcpHttpPortOk !== undefined) ||
                    (p === 443 && tcpHttpsPortOk !== null && tcpHttpsPortOk !== undefined)
            );

        if (canSynthesizeSingle) {
            const syntheticChecks = [{
                type: "tcp",
                tcp_port: normalizedPorts[0],
                success: statusTcp === "UP",
                latency: latencyTcp,
                error: statusTcp === "DOWN" ? "timeout" : null,
            }];
            renderTcpPortsStatus(name, syntheticChecks, normalizedPorts);
        } else if (canSynthesizeWebPorts) {
            const syntheticChecks = normalizedPorts.map((p) => {
                const ok = p === 80 ? !!tcpHttpPortOk : !!tcpHttpsPortOk;
                const lat = p === 80 ? tcpHttpPortLatency : tcpHttpsPortLatency;
                return {
                    type: "tcp",
                    tcp_port: p,
                    success: ok,
                    latency: lat,
                    error: ok ? null : "timeout",
                };
            });
            renderTcpPortsStatus(name, syntheticChecks, normalizedPorts);
        } else {
            const res = await fetchWithAuth(`${API}/host/history/${encodeURIComponent(name)}`);
            if (!res || !res.ok) return;
            const data = await res.json();
            renderTcpPortsStatus(name, data.checks, normalizedPorts);
            if (!lastPing) {
                lastPing = data.checks.find(c => c.type === "ping");
            }
            if (httpEnabled && !lastHttp) {
                lastHttp = data.checks.find(c => c.type === "http");
            }
        }
    } else {
        renderTcpPortsStatus(name, [], []);
    }

    const pingLikelyFirewallBlocked =
        icmpBlocked ||
        (!!lastPing &&
        !lastPing.success &&
        (!!lastHttp && lastHttp.success));

    const pingDot = pingLikelyFirewallBlocked
        ? "bg-secondary"
        : (lastPing?.success ? "bg-success" : "bg-danger");
    const webDot = httpEnabled
        ? (lastHttp?.success ? "bg-success" : "bg-danger")
        : "bg-secondary";

    const pingLatencyText = pingLikelyFirewallBlocked
        ? "indisponível"
        : (lastPing ? (lastPing.success ? `${lastPing?.latency ?? "sem dados"} ms` : tcpFailureLabel(lastPing.error)) : "sem dados");
    const resolvedProtocol = String(httpProtocol || "").toUpperCase();
    const protocolLabel = resolvedProtocol === "HTTPS" || resolvedProtocol === "HTTP"
        ? resolvedProtocol
        : "Web";
    const protocolValue = !httpEnabled
        ? "inativo"
        : (httpLatency !== null && httpLatency !== undefined
            ? `${httpLatency} ms`
            : "Aguardando");

    box.innerHTML = `
        <div>
            <span class="status-indicator ${pingDot}"></span>
            Ping: ${escapeHtml(pingLatencyText)}
        </div>
        <div>
            <span class="status-indicator ${webDot}"></span>
            ${escapeHtml(httpEnabled ? protocolLabel : "Web")}: ${escapeHtml(httpEnabled ? protocolValue : "Inativo")}
        </div>
    `;
}

async function loadHistory(name, isRefresh = false) {
    const box = document.getElementById("history-" + name);
    if (!box) return;
    if (!isRefresh && !box.querySelector(".history-line")) {
        box.innerHTML = "<div class='ui-state ui-state-info'>Carregando histórico...</div>";
    }

    try {
        const res = await fetchWithAuth(`${API}/host/history/${encodeURIComponent(name)}`);

        if (!res || !res.ok) return;

        const data = await res.json();

        const checks = Array.isArray(data.checks) ? data.checks.slice(0, 20) : [];

        if (!checks.length) {
            box.innerHTML = "<div class='ui-state ui-state-empty'>Sem histórico ainda</div>";
            return;
        }

        const linesHtml = checks.map(c => {
            const statusClass = c.success ? "line-success" : "line-error";
            const statusText = c.success ? "OK" : "FAIL";
            const typeLabel = c.type === "tcp" && c.tcp_port
                ? `TCP ${c.tcp_port}`
                : String(c.type || "").toUpperCase();
            const detailParts = [];
            if (c.status_code) detailParts.push(`HTTP ${c.status_code}`);
            if (c.error) detailParts.push(c.error);
            detailParts.push(c.latency !== null ? `${c.latency} ms` : "---");
            const detailText = detailParts.join(" • ");
            return `
                <div class="history-line ${statusClass}">
                    <div class="history-line-top">
                        <span class="type-badge">${escapeHtml(typeLabel)}</span>
                        <span class="history-status">${statusText}</span>
                        <small class="history-time">${formatApiTime(c.timestamp)}</small>
                    </div>
                    <div class="history-line-bottom">
                        <span class="history-detail">${escapeHtml(detailText)}</span>
                    </div>
                </div>
            `;
        }).join("");

        box.innerHTML = `<div class="host-history-scroll">${linesHtml}</div>`;

    } catch {
        if (!isRefresh) {
            box.innerHTML = "<div class='ui-state ui-state-error'>Erro ao carregar histórico</div>";
        }
    }
}

async function toggleHistory(name) {
    const box = document.getElementById("history-" + name);

    if (!box.classList.contains("hidden")) {
        box.classList.add("hidden");
        return;
    }

    closeHostExpandedPanels(name, box.id);
    box.classList.remove("hidden");
    await loadHistory(name);
}

async function toggleLatencyChart(name) {
    const container = document.getElementById("chart-container-" + name);
    if (!container) return;

    if (container.classList.contains("hidden")) {
        closeHostExpandedPanels(name, container.id);
        container.classList.remove("hidden");
        await loadLatencyChart(name);
    } else {
        container.classList.add("hidden");
    }
}

async function toggleSnmpChart(name) {
    const box = document.getElementById("snmp-chart-box-" + name);
    if (!box) return;

    if (box.classList.contains("hidden")) {
        closeHostExpandedPanels(name, box.id);
        box.classList.remove("hidden");
        await loadSnmpChart(name);
    } else {
        box.classList.add("hidden");
    }
}

async function toggleAvailabilityChartType(name) {

    const box = document.getElementById("availability-chart-type-box-" + name);

    if (!box) return;

    if (!box.classList.contains("hidden")) {
        box.classList.add("hidden");
        return;
    }

    closeHostExpandedPanels(name, box.id);
    box.classList.remove("hidden");
    loadAvailabilityChartType(name);
}

let currentEditHost = null;

let lastFocusedElementBeforeModal = null;

function openAppModal(modalEl) {
    if (!modalEl) return;
    lastFocusedElementBeforeModal = document.activeElement;
    modalEl.classList.remove("hidden");
    modalEl.setAttribute("aria-hidden", "false");

    const focusable = modalEl.querySelector("input:not([disabled]), select:not([disabled]), textarea:not([disabled]), button:not([disabled]), [tabindex]:not([tabindex='-1'])");
    if (focusable) {
        setTimeout(() => {
            try { focusable.focus(); } catch (e) {}
        }, 50);
    }
}

function closeAppModal(modalEl) {
    if (!modalEl) return;
    modalEl.classList.add("hidden");
    modalEl.setAttribute("aria-hidden", "true");
    if (lastFocusedElementBeforeModal && typeof lastFocusedElementBeforeModal.focus === "function") {
        try { lastFocusedElementBeforeModal.focus(); } catch (e) {}
    }
}

function openEditModal(name, ip, ports = [], httpUrl, httpEnabled = true, snmpEnabled = false, snmpCommunity = "netspot") {
    currentEditHost = name;

    const cached = currentHostsMap.get(name);
    if (cached) {
        ip = cached.address || ip;
        ports = parseHostPorts(cached);
        httpUrl = cached.http_url !== undefined ? (cached.http_url || "") : (httpUrl || "");
        httpEnabled = cached.http_enabled !== false;
        snmpEnabled = !!cached.snmp_enabled;
        snmpCommunity = cached.snmp_community || "netspot";
    }

    const nameInput = document.getElementById("modal-name");
    if (nameInput) nameInput.value = name;
    const ipInput = document.getElementById("modal-ip");
    if (ipInput) ipInput.value = ip || "";
    const httpInput = document.getElementById("modal-http-url");
    if (httpInput) httpInput.value = httpUrl || "";
    const modalHttpEnabled = document.getElementById("modal-http-enabled");
    if (modalHttpEnabled) modalHttpEnabled.checked = !!httpEnabled;
    const modalSnmpEnabled = document.getElementById("modal-snmp-enabled");
    if (modalSnmpEnabled) modalSnmpEnabled.checked = !!snmpEnabled;
    const modalSnmpCommunity = document.getElementById("modal-snmp-community");
    if (modalSnmpCommunity) modalSnmpCommunity.value = snmpCommunity || "netspot";

    setModalPorts(ports);

    const modal = document.getElementById("editModal");
    if (modal) openAppModal(modal);
}

function closeModal() {
    closeAppModal(document.getElementById("editModal"));
}


function formatBps(value) {
    if (value === null || value === undefined) return "N/A";

    const bps = Number(value);

    if (bps < 1000) return `${bps.toFixed(2)} bps`;
    if (bps < 1000_000) return `${(bps / 1000).toFixed(2)} Kbps`;
    if (bps < 1000_000_000) return `${(bps / 1000_000).toFixed(2)} Mbps`;

    return `${(bps / 1000_000_000).toFixed(2)} Gbps`;
}

function escapeHtml(str) {
    if (str === null || str === undefined) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function escapeJsSingleQuotedAttr(val) {
    return escapeHtml(JSON.stringify(val));
}

// Score de saúde + indicador + barra de progresso colorida pela severidade.
function healthMeterHtml(h, severityIndicatorHtml = "") {
    const score = Number(h.health_score);
    const valid = h.health_score !== null && h.health_score !== undefined && Number.isFinite(score);
    const pct = valid ? Math.max(0, Math.min(100, score)) : 0;
    const sevMap = { HEALTHY: "sev-healthy", WARNING: "sev-warning", DEGRADED: "sev-degraded", CRITICAL: "sev-critical" };
    const sev = sevMap[h.severity] || "sev-unknown";
    return `${valid ? score : "N/A"}% ${severityIndicatorHtml}`
        + `<span class="health-meter" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${pct}">`
        + `<span class="health-meter-fill ${sev}" style="width:${pct}%"></span></span>`;
}

function calcRelativeBarWidth(value, maxValue) {
    const current = Number(value);
    const max = Number(maxValue);
    if (!Number.isFinite(current) || current <= 0 || !Number.isFinite(max) || max <= 0) return 0;
    const ratio = (current / max) * 100;
    return Math.max(8, Math.min(100, ratio));
}

// Classificação visual para métricas percentuais (CPU/RAM/Disco): 0-59, 60-79, 80-100.
function metricClass(value, warn = 60, critical = 80) {
    if (value === null || value === undefined) return "metric-neutral";
    if (value >= critical) return "metric-critical";
    if (value >= warn) return "metric-warn";
    return "metric-ok";
}

function metricPercent(value) {
    if (value === null || value === undefined) return "N/A";
    const n = Number(value);
    if (Number.isNaN(n)) return "N/A";
    return `${n.toFixed(1)}%`;
}

function metricBarWidth(value) {
    if (value === null || value === undefined) return 0;
    const n = Number(value);
    if (Number.isNaN(n)) return 0;
    return Math.max(0, Math.min(100, n));
}

function takeLast(items, limit = MAX_POINTS_PER_SERIES) {
    if (!Array.isArray(items)) return [];
    if (items.length <= limit) return items;
    return items.slice(items.length - limit);
}

function chartCommonOptions(yMin = null, yMax = null, yLabel = "") {
    const isDark = document.body.classList.contains("dark-theme") || document.documentElement.classList.contains("dark-theme");
    const textColor = isDark ? "#cbd5e1" : "#64748b";
    const gridColor = isDark ? "rgba(255, 255, 255, 0.08)" : "rgba(15, 23, 42, 0.06)";
    const titleColor = isDark ? "#f8fafc" : "#0f172a";
    
    const yScale = {
        title: {
            display: !!yLabel,
            text: yLabel,
            color: titleColor,
            font: {
                family: "'Open Sans', 'Roboto', sans-serif",
                size: 11,
                weight: '600'
            }
        },
        grid: {
            color: gridColor,
            drawBorder: false,
            borderColor: gridColor
        },
        ticks: {
            color: textColor,
            font: {
                family: "'Open Sans', 'Roboto', sans-serif",
                size: 10
            }
        }
    };
    if (yMin !== null && yMin !== undefined) yScale.min = yMin;
    if (yMax !== null && yMax !== undefined) yScale.max = yMax;

    return {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
            legend: {
                labels: {
                    color: textColor,
                    font: {
                        family: "'Open Sans', 'Roboto', sans-serif",
                        size: 11,
                        weight: '500'
                    },
                    boxWidth: 8,
                    usePointStyle: true,
                    padding: 15
                }
            },
            tooltip: {
                backgroundColor: isDark ? "#2d2e30" : "#ffffff",
                titleColor: isDark ? "#e8eaed" : "#202124",
                bodyColor: isDark ? "#9aa0a6" : "#5f6368",
                borderColor: isDark ? "#3c4043" : "#dadce0",
                borderWidth: 1,
                padding: 10,
                titleFont: {
                    family: "'Open Sans', 'Roboto', sans-serif",
                    size: 12,
                    weight: '600'
                },
                bodyFont: {
                    family: "'Open Sans', 'Roboto', sans-serif",
                    size: 11
                },
                cornerRadius: 6
            }
        },
        scales: {
            y: yScale,
            x: {
                grid: {
                    color: gridColor,
                    drawBorder: false,
                    borderColor: gridColor
                },
                ticks: {
                    color: textColor,
                    font: {
                        family: "'Open Sans', 'Roboto', sans-serif",
                        size: 10
                    }
                }
            }
        }
    };
}

function showChartEmpty(boxId, canvasId, message) {
    const box = document.getElementById(boxId);
    const canvas = document.getElementById(canvasId);
    if (!box || !canvas) return;

    canvas.style.display = "none";
    let empty = box.querySelector(".chart-empty");
    if (!empty) {
        empty = document.createElement("div");
        empty.className = "chart-empty";
        box.appendChild(empty);
    }
    empty.textContent = message;
}

function clearChartEmpty(boxId, canvasId) {
    const box = document.getElementById(boxId);
    const canvas = document.getElementById(canvasId);
    if (!box || !canvas) return;

    const empty = box.querySelector(".chart-empty");
    if (empty) empty.remove();
    canvas.style.display = "block";
}

function getDatasetHiddenMap(chart) {
    const map = {};
    (chart.data?.datasets || []).forEach((ds, i) => {
        const meta = chart.getDatasetMeta(i);
        map[ds.label] = meta?.hidden === true || ds.hidden === true;
    });
    return map;
}

function updateOrCreateChart(chartKey, canvasEl, config) {
    const current = charts[chartKey];

    if (!current) {
        charts[chartKey] = new Chart(canvasEl, config);
        return;
    }

    if (current.canvas !== canvasEl) {
        current.destroy();
        charts[chartKey] = new Chart(canvasEl, config);
        return;
    }

    const hiddenMap = getDatasetHiddenMap(current);
    (config.data.datasets || []).forEach((ds) => {
        if (Object.prototype.hasOwnProperty.call(hiddenMap, ds.label)) {
            ds.hidden = hiddenMap[ds.label];
        }
    });

    current.config.type = config.type;
    current.config.plugins = config.plugins || [];
    current.data.labels = config.data.labels || [];
    current.data.datasets = config.data.datasets || [];
    current.options = config.options || {};
    current.update("none");
}

function destroyChartsForHost(name) {
    if (!name) return;
    const suffix = `-${name}`;
    for (const key of Object.keys(charts)) {
        if (key.endsWith(suffix) || key === name) {
            try {
                if (typeof charts[key]?.destroy === "function") {
                    charts[key].destroy();
                }
            } catch (e) {
                console.warn("Erro ao destruir gráfico do host:", name, e);
            }
            delete charts[key];
        }
    }
}

function parseApiDate(value) {
    if (!value) return null;

    if (typeof value === "string") {
        const hasTimezone = /[zZ]|[+\-]\d{2}:\d{2}$/.test(value);
        const normalized = hasTimezone ? value : `${value}Z`;
        const dt = new Date(normalized);
        if (!Number.isNaN(dt.getTime())) return dt;
    }

    const dt = new Date(value);
    if (Number.isNaN(dt.getTime())) return null;
    return dt;
}

function formatApiTime(value) {
    const dt = parseApiDate(value);
    if (!dt) return "N/A";
    return dt.toLocaleTimeString("pt-BR");
}

function formatApiDateTime(value) {
    const dt = parseApiDate(value);
    if (!dt) return "N/A";
    return dt.toLocaleString("pt-BR");
}

function formatCheckTime(value) {
    return formatApiTime(value);
}

function trendIcon(trend) {
    if (trend === "UP") return "↑";
    if (trend === "DOWN") return "↓";
    return "→";
}

function formatMetric(value, suffix = "", digits = 2) {
    if (value === null || value === undefined) return "N/A";
    const num = Number(value);
    if (Number.isNaN(num)) return "N/A";
    return `${num.toFixed(digits)}${suffix}`;
}

async function submitModalEdit() {
    if (!currentEditHost) return;
    const nameInput = document.getElementById("modal-name");
    const ipInput = document.getElementById("modal-ip");
    const httpInput = document.getElementById("modal-http-url");
    const httpEnabledInput = document.getElementById("modal-http-enabled");
    const snmpEnabledInput = document.getElementById("modal-snmp-enabled");
    const modalSnmpCommInput = document.getElementById("modal-snmp-community");
    const modalPortsContainer = document.getElementById("modalPortsContainer");

    const newName = (nameInput?.value || "").trim();
    if (!newName) {
        showToast("warning", "O nome do host é obrigatório.");
        return;
    }

    const newIp = (ipInput?.value || "").trim();
    if (!newIp) {
        showToast("warning", "O endereço/IP é obrigatório.");
        return;
    }

    const newHttp = (httpInput?.value || "").trim();
    const newHttpEnabled = !!httpEnabledInput?.checked;
    const newSnmpEnabled = !!snmpEnabledInput?.checked;
    const newSnmpComm = (modalSnmpCommInput?.value || "").trim() || "netspot";

    let ports = [];
    try {
        ports = collectPorts(modalPortsContainer);
    } catch (err) {
        showToast("error", err.message || "Lista de portas inválida.");
        return;
    }

    const saveBtn = document.querySelector("#editModal .modal-actions button.modal-btn-primary")
        || document.querySelector("#editModal .modal-actions button:first-child");
    const originalText = getButtonLabel(saveBtn, "Salvar");
    if (saveBtn) {
        saveBtn.disabled = true;
        setButtonLabel(saveBtn, "Salvando...");
    }

    const oldHostName = currentEditHost;

    try {
        const res = await fetchWithAuth(`${API}/host/update/${encodeURIComponent(oldHostName)}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                name: newName,
                address: newIp,
                ports,
                port: ports.length ? ports[0] : null,
                url: newHttp || null,
                http_url: newHttp || null,
                http_enabled: newHttpEnabled,
                snmp_enabled: newSnmpEnabled,
                snmp_community: newSnmpComm
            })
        });

        if (res && res.ok) {
            closeModal();
            showToast("success", "Host atualizado com sucesso.");
            // Se o nome foi alterado, limpa os gráficos associados e remove o cartão antigo
            if (newName !== oldHostName) {
                destroyChartsForHost(oldHostName);
                const oldCard = document.getElementById(`card-${oldHostName}`);
                if (oldCard) oldCard.remove();
                currentHostsMap.delete(oldHostName);
            }
            await loadHosts();
        } else {
            const errData = res ? await res.json().catch(() => ({})) : {};
            showToast("error", errData.detail || "Erro ao salvar alterações do host.");
        }
    } catch (err) {
        showToast("error", "Não foi possível conectar ao servidor.");
    } finally {
        if (saveBtn) {
            saveBtn.disabled = false;
            setButtonLabel(saveBtn, originalText);
        }
    }
}

async function loadLatencyChart(name) {
    const chartKey = `latency-${name}`;
    const res = await fetchWithAuth(`${API}/host/history/${encodeURIComponent(name)}`);
    
    if (!res || !res.ok) return;

    const data = await res.json();
    const ctx = document.getElementById("chart-" + name);
    const containerId = "chart-container-" + name;
    const canvasId = "chart-" + name;

    if (!ctx) return;

    const checks = Array.isArray(data.checks) ? data.checks : [];
    const latencyChecks = checks.filter((c) => c.latency !== null && c.latency !== undefined);
    if (!latencyChecks.length) {
        showChartEmpty(containerId, canvasId, "Sem dados de latência para este host.");
        return;
    }
    clearChartEmpty(containerId, canvasId);

    const perSeries = new Map();
    for (const check of latencyChecks) {
        const type = String(check.type || "").toLowerCase();
        if (type === "tcp") {
            const tcpPort = Number(check.tcp_port);
            if (!Number.isInteger(tcpPort)) continue;
            const key = `tcp:${tcpPort}`;
            const label = `TCP ${tcpPort}`;
            if (!perSeries.has(key)) perSeries.set(key, { label, points: [] });
            perSeries.get(key).points.push(check);
            continue;
        }
        if (type === "ping") {
            if (!perSeries.has("ping")) perSeries.set("ping", { label: "Ping", points: [] });
            perSeries.get("ping").points.push(check);
            continue;
        }
        if (type === "http") {
            if (!perSeries.has("http")) perSeries.set("http", { label: "HTTP", points: [] });
            perSeries.get("http").points.push(check);
        }
    }

    const timestampKeys = Array.from(
        new Set(
            Array.from(perSeries.values()).flatMap((series) =>
                series.points.map((p) => String(p.timestamp))
            )
        )
    ).sort();

    const labels = timestampKeys.map((ts) => formatApiTime(ts));
    const colorByLabel = (label) => {
        if (label === "Ping") return { line: "#22c55e", fill: "#22c55e33" };
        if (label === "HTTP") return { line: "#f59e0b", fill: "#f59e0b33" };
        return { line: "#3b82f6", fill: "#3b82f633" };
    };

    const orderedSeries = Array.from(perSeries.values()).sort((a, b) => {
        const aTcp = a.label.startsWith("TCP ");
        const bTcp = b.label.startsWith("TCP ");
        if (aTcp && bTcp) {
            return Number(a.label.replace("TCP ", "")) - Number(b.label.replace("TCP ", ""));
        }
        if (aTcp) return 1;
        if (bTcp) return -1;
        return a.label.localeCompare(b.label);
    });

    const datasets = orderedSeries.map((series) => {
        const byTs = new Map(series.points.map((p) => [String(p.timestamp), p.latency]));
        const values = timestampKeys.map((ts) => (byTs.has(ts) ? byTs.get(ts) : null));
        const colors = colorByLabel(series.label);
        return {
            label: series.label,
            data: values,
            ...window.NetSpotChartTheme.lineStyle(colors.line, { fill: orderedSeries.length === 1 }),
        };
    });

    window.NetSpotChartTheme.renderSummary(ctx, datasets.map((ds) => ({
        label: ds.label,
        color: ds.borderColor,
        values: ds.data,
        fmt: (v) => `${v.toFixed(1)} ms`,
    })));

    updateOrCreateChart(chartKey, ctx, {
        type: "line",
        data: {
            labels: labels,
            datasets
        },
        options: chartCommonOptions(null, null, "Latência (ms)")
    });
}

async function loadSnmpChart(name) {
    const chartKey = `snmp-${name}`;

    const res = await fetchWithAuth(`${API}/metrics/snmp/${encodeURIComponent(name)}`);
    if (!res || !res.ok) return;

    const data = await res.json();
    const points = takeLast(data.points || []);
    const boxId = "snmp-chart-box-" + name;
    const canvasId = "snmp-chart-" + name;

    if (!points.length) {
        showChartEmpty(boxId, canvasId, "Sem histórico SNMP para este host.");
        return;
    }
    clearChartEmpty(boxId, canvasId);

    const isDark = document.body.classList.contains("dark-theme") || document.documentElement.classList.contains("dark-theme");
    const cpuColor = isDark ? "#f28b82" : "#ea4335";
    const ramColor = isDark ? "#fde293" : "#fbbc05";
    const diskColor = isDark ? "#ffad70" : "#fa7b17";
    const rxColor = isDark ? "#8ab4f8" : "#1a73e8";
    const txColor = isDark ? "#81c995" : "#34a853";

    const labels = points.map(p => formatApiTime(p.timestamp));
    const cpu = points.map(p => p.cpu);
    const ram = points.map(p => p.ram);
    const disk = points.map(p => p.disk);
    const rx = points.map(p => p.network_in_bps);
    const tx = points.map(p => p.network_out_bps);

    const ctx = document.getElementById("snmp-chart-" + name);
    if (!ctx) return;

    const T = window.NetSpotChartTheme;

    const hasCpu = cpu.some(v => v !== null && v !== undefined);
    const hasRam = ram.some(v => v !== null && v !== undefined);
    const hasDisk = disk.some(v => v !== null && v !== undefined);
    const hasRx = rx.some(v => v !== null && v !== undefined);
    const hasTx = tx.some(v => v !== null && v !== undefined);

    const datasets = [];
    const summaryItems = [];

    if (hasCpu) {
        datasets.push({ label: "CPU (%)", data: cpu, ...T.lineStyle(cpuColor, { yAxisID: "y_percent" }) });
        summaryItems.push({ label: "CPU", color: cpuColor, values: cpu, fmt: metricPercent });
    }
    if (hasRam) {
        datasets.push({ label: "RAM (%)", data: ram, ...T.lineStyle(ramColor, { fill: false, yAxisID: "y_percent" }) });
        summaryItems.push({ label: "RAM", color: ramColor, values: ram, fmt: metricPercent });
    }
    if (hasDisk) {
        datasets.push({ label: "Disco (%)", data: disk, ...T.lineStyle(diskColor, { fill: false, yAxisID: "y_percent" }) });
        summaryItems.push({ label: "Disco", color: diskColor, values: disk, fmt: metricPercent });
    }
    if (hasRx) {
        datasets.push({ label: "Download (RX)", data: rx, ...T.lineStyle(rxColor, { fill: false, yAxisID: "y_bps" }) });
        summaryItems.push({ label: "Download", color: rxColor, values: rx, fmt: formatBps });
    }
    if (hasTx) {
        datasets.push({ label: "Upload (TX)", data: tx, ...T.lineStyle(txColor, { fill: false, yAxisID: "y_bps" }) });
        summaryItems.push({ label: "Upload", color: txColor, values: tx, fmt: formatBps });
    }

    T.renderSummary(ctx, summaryItems);

    // Eixos: % (esquerda, com faixas de limiar) e bps (direita, agora visível e legível).
    const opts = chartCommonOptions();
    const axisTitle = opts.scales.y.title;
    const axisTicks = opts.scales.y.ticks;
    opts.scales = {
        x: opts.scales.x,
        y_percent: {
            ...opts.scales.y,
            type: "linear",
            position: "left",
            min: 0,
            max: 100,
            title: { ...axisTitle, display: true, text: "Uso (%)" },
        },
        y_bps: {
            type: "linear",
            position: "right",
            min: 0,
            grid: { drawOnChartArea: false },
            title: { ...axisTitle, display: true, text: "Rede" },
            ticks: { ...axisTicks, callback: (v) => formatBps(v) },
        },
    };
    opts.plugins.thresholdBands = T.thresholdBands("y_percent", T.percentBands(80, 95));
    opts.plugins.tooltip.callbacks = {
        label: (c) => {
            if (c.dataset.yAxisID === "y_percent") {
                const value = Number(c.parsed.y);
                return `${c.dataset.label}: ${Number.isFinite(value) ? value.toFixed(2) : "N/A"}%`;
            }
            return `${c.dataset.label}: ${formatBps(c.parsed.y)}`;
        }
    };

    updateOrCreateChart(chartKey, ctx, {
        type: "line",
        data: {
            labels,
            datasets
        },
        options: opts
    });
}

async function loadAvailabilityChartType(name) {

    const res = await fetchWithAuth(`${API}/hosts/metrics/availability/type/${encodeURIComponent(name)}`);
    if (!res || !res.ok) return;

    const data = await res.json();

    const ping = takeLast(data.ping || []);
    const tcp  = takeLast(data.tcp || []);
    const http = takeLast(data.http || []);

    const ctx = document.getElementById("availability-chart-type-" + name);
    if (!ctx) return;

    const chartKey = `availability-type-${name}`;

    // Apenas protocolos que realmente possuem dados monitorados para este host
    const activeSeries = [];
    if (ping.length) activeSeries.push({ key: "ping", label: "Ping", points: ping });
    if (tcp.length)  activeSeries.push({ key: "tcp",  label: "TCP",  points: tcp });
    if (http.length) activeSeries.push({ key: "http", label: "HTTP", points: http });

    if (!activeSeries.length) {
        showChartEmpty(
            "availability-chart-type-box-" + name,
            "availability-chart-type-" + name,
            "Sem dados de disponibilidade por tipo."
        );
        return;
    }
    clearChartEmpty("availability-chart-type-box-" + name, "availability-chart-type-" + name);

    // Unifica e ordena cronologicamente todos os timestamps das séries ativas
    const timestampSet = new Set();
    activeSeries.forEach((s) => {
        s.points.forEach((p) => {
            if (p.timestamp) timestampSet.add(p.timestamp);
        });
    });
    const sortedTimestamps = Array.from(timestampSet).sort();

    const labels = sortedTimestamps.map((ts) => formatApiTime(ts));

    const isDark = document.body.classList.contains("dark-theme") || document.documentElement.classList.contains("dark-theme");
    const colorMap = {
        ping: isDark ? "#81c995" : "#1e8e3e",
        tcp:  isDark ? "#8ab4f8" : "#1a73e8",
        http: isDark ? "#fde293" : "#f9ab00",
    };

    const T = window.NetSpotChartTheme;
    const datasets = [];
    const summaryItems = [];

    activeSeries.forEach((s) => {
        const color = colorMap[s.key] || "#8ab4f8";
        const mapByTs = new Map(s.points.map((p) => [p.timestamp, p.availability]));
        const alignedValues = sortedTimestamps.map((ts) => (mapByTs.has(ts) ? mapByTs.get(ts) : null));
        const rawValues = s.points.map((p) => p.availability);

        datasets.push({
            label: `Disponibilidade ${s.label} (%)`,
            data: alignedValues,
            spanGaps: true,
            ...T.lineStyle(color, { fill: false })
        });

        summaryItems.push({
            label: s.label,
            color: color,
            values: rawValues,
            fmt: (v) => `${Number(v).toFixed(1)}%`
        });
    });

    T.renderSummary(ctx, summaryItems);

    const availOpts = chartCommonOptions(0, 100, "Disponibilidade (%)");
    availOpts.plugins.thresholdBands = T.thresholdBands("y", [
        { from: 0, to: 85, color: "rgba(217,48,37,0.08)" },
        { from: 85, to: 95, color: "rgba(249,171,0,0.09)" },
    ]);

    updateOrCreateChart(chartKey, ctx, {
        type: "line",
        data: {
            labels: labels,
            datasets: datasets
        },
        options: availOpts
    });
}

function formatStatusLabel(status) {
    const normalized = String(status || "").toUpperCase();
    if (normalized === "UP" || normalized === "UP_RECOVERED") return "Online";
    if (normalized === "DOWN") return "Offline";
    if (normalized === "DEGRADED") return "Degradado";
    if (normalized === "CRITICAL") return "Crítico";
    if (normalized === "UNKNOWN") return "Desconhecido";
    return status ?? "Desconhecido";
}

function hostVisualState(host) {
    if (host?.icmp_blocked_but_service_up) {
        return { cardClass: "card-state-up", badgeClass: "state-up", label: "UP" };
    }

    const status = String(host?.status || "").toUpperCase();
    const severity = String(host?.severity || "").toUpperCase();

    if (severity === "CRITICAL") {
        return { cardClass: "card-state-critical", badgeClass: "state-critical", label: "CRITICAL" };
    }
    if (status === "DOWN") {
        return { cardClass: "card-state-down", badgeClass: "state-down", label: "DOWN" };
    }
    if (status === "DEGRADED" || severity === "DEGRADED") {
        return { cardClass: "card-state-degraded", badgeClass: "state-degraded", label: "DEGRADED" };
    }
    if (severity === "WARNING") {
        return { cardClass: "card-state-degraded", badgeClass: "state-degraded", label: "WARNING" };
    }
    return { cardClass: "card-state-up", badgeClass: "state-up", label: "UP" };
}

function probableCauseClass(host) {
    if (host?.icmp_blocked_but_service_up) return "cause-normal";

    const status = String(host?.status || "").toUpperCase();
    const severity = String(host?.severity || "").toUpperCase();
    if (severity === "CRITICAL" || status === "DOWN") return "cause-critical";
    if (status === "DEGRADED" || severity === "DEGRADED" || severity === "WARNING") return "cause-warning";
    return "cause-normal";
}

function hostMonitorFlag(host) {
    if (host?.active === false) return { label: "Pausado", className: "paused" };
    const status = String(host?.status || "").toUpperCase();
    if (status === "DOWN") return { label: "Em falha", className: "down" };
    if (status === "DEGRADED") return { label: "Degradado", className: "degraded" };
    return { label: "Monitorando", className: "running" };
}

function iconSvg(name) {
    const icons = {
        history: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 8v5l3 2M4 12a8 8 0 1 0 2.3-5.7M4 4v4h4"/></svg>`,
        latency: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 18h16M6 16l3-5 3 3 4-7 2 3"/></svg>`,
        snmp: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12h16M7 8h10M7 16h10"/></svg>`,
        availability_type: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 18V8M12 18V6M19 18v-4"/></svg>`,
        availability: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 17l4-5 4 3 6-8"/></svg>`,
        edit: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20l4-1 9-9-3-3-9 9-1 4zm10-13l3 3"/></svg>`,
        trash: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 4h6l1 2h4v2H4V6h4l1-2zm-2 6h2v8H7v-8zm4 0h2v8h-2v-8zm4 0h2v8h-2v-8z"/></svg>`,
        arrow_left: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 6l-6 6 6 6"/></svg>`,
        arrow_right: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10 6l6 6-6 6"/></svg>`,
        close: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>`,
    };
    return icons[name] || "";
}

function closeHostExpandedPanels(hostName, exceptId = null) {
    const panelIds = [
        `history-${hostName}`,
        `chart-container-${hostName}`,
        `snmp-chart-box-${hostName}`,
        `availability-chart-type-box-${hostName}`,
        `availability-chart-box-${hostName}`
    ];

    panelIds.forEach((panelId) => {
        if (exceptId && panelId === exceptId) return;
        const panel = document.getElementById(panelId);
        if (!panel) return;
        panel.classList.add("hidden");
    });
}

function setHostFace(hostName, faceNumber) {
    updateHostFace(hostName, faceNumber);
}

function updateHostFace(hostName, faceNumber) {
    const card = document.getElementById(`card-${hostName}`);
    if (!card) return;
    const faces = card.querySelectorAll(".host-face");
    if (!faces.length) return;

    const safeFace = Math.max(1, Math.min(3, Number(faceNumber) || 1));
    card.dataset.face = String(safeFace);

    const FACE_NAMES = {
        1: "Resumo e status",
        2: "Métricas de rede e latência",
        3: "Hardware e tráfego SNMP"
    };

    faces.forEach((face) => {
        const n = Number(face.getAttribute("data-face"));
        face.classList.toggle("active", n === safeFace);
    });

    // Atualiza pílulas segmentadas de navegação
    card.querySelectorAll(".face-pill").forEach((pill) => {
        const pNum = Number(pill.getAttribute("data-face-num"));
        const isActive = pNum === safeFace;
        pill.classList.toggle("active", isActive);
        pill.setAttribute("aria-selected", isActive ? "true" : "false");
    });
}

function nextHostFace(hostName) {
    const card = document.getElementById(`card-${hostName}`);
    const current = Number(card?.dataset?.face || 1);
    updateHostFace(hostName, current + 1);
}

function prevHostFace(hostName) {
    const card = document.getElementById(`card-${hostName}`);
    const current = Number(card?.dataset?.face || 1);
    updateHostFace(hostName, current - 1);
}

async function copyHostAddress(address, btnEl, event) {
    if (event) event.stopPropagation();
    if (!address) return;
    try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(address);
        } else {
            const ta = document.createElement("textarea");
            ta.value = address;
            document.body.appendChild(ta);
            ta.select();
            document.execCommand("copy");
            document.body.removeChild(ta);
        }

        if (btnEl) {
            btnEl.classList.add("copied");
            const originalSvg = btnEl.innerHTML;
            btnEl.innerHTML = `<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
            setTimeout(() => {
                btnEl.classList.remove("copied");
                btnEl.innerHTML = originalSvg;
            }, 1400);
        }
        showToast("success", `Endereço "${address}" copiado!`);
    } catch (err) {
        showToast("error", `Não foi possível copiar: ${err}`);
    }
}

function togglePasswordVisibility(inputId, btnEl) {
    const input = document.getElementById(inputId);
    if (!input) return;

    const isPassword = input.type === "password";
    input.type = isPassword ? "text" : "password";

    if (btnEl) {
        const eyeOpen = btnEl.querySelector(".eye-open");
        const eyeClosed = btnEl.querySelector(".eye-closed");
        if (eyeOpen && eyeClosed) {
            eyeOpen.classList.toggle("hidden", isPassword);
            eyeClosed.classList.toggle("hidden", !isPassword);
        }
        const label = isPassword ? "Ocultar senha" : "Mostrar senha";
        btnEl.title = label;
        btnEl.setAttribute("aria-label", label);
        btnEl.setAttribute("aria-pressed", isPassword ? "true" : "false");
    }
}

function alertSeverityClass(severity) {
    const normalized = String(severity || "").toUpperCase();
    if (normalized === "HEALTHY") return "alert-sev-healthy";
    if (normalized === "WARNING") return "alert-sev-warning";
    if (normalized === "DEGRADED") return "alert-sev-degraded";
    if (normalized === "CRITICAL") return "alert-sev-critical";
    return "alert-sev-unknown";
}

function incidentTypeLabel(incidentType) {
    const key = String(incidentType || "GENERIC").toUpperCase();
    return INCIDENT_TYPE_LABELS[key] || "Incidente operacional";
}

function alertTypeLabel(alertType) {
    const key = String(alertType || "").toUpperCase();
    return ALERT_TYPE_LABELS[key] || (alertType || "Alerta");
}

function alertDedupeKey(alert) {
    return [
        String(alert.host_name || "").toLowerCase(),
        String(alert.alert_type || "").toUpperCase(),
        String(alert.old_status || "").toUpperCase(),
        String(alert.new_status || "").toUpperCase()
    ].join("|");
}

function alertSeenKey(alert) {
    return [
        String(alert.host_name || "").toLowerCase(),
        String(alert.alert_type || "").toUpperCase(),
        String(alert.timestamp || ""),
        String(alert.old_status || "").toUpperCase(),
        String(alert.new_status || "").toUpperCase()
    ].join("|");
}

function shouldRenderAlertCard(alert) {
    const key = alertDedupeKey(alert);
    const now = Date.now();
    const lastShownAt = recentAlertCache.get(key) || 0;

    if (now - lastShownAt < ALERT_DEDUP_WINDOW_MS) {
        return false;
    }

    recentAlertCache.set(key, now);

    if (recentAlertCache.size > 250) {
        for (const [cacheKey, ts] of recentAlertCache.entries()) {
            if (now - ts > ALERT_DEDUP_WINDOW_MS * 3) {
                recentAlertCache.delete(cacheKey);
            }
        }
    }
    return true;
}

function showAlertCard(alert) {
    const box = document.getElementById("alert-container");
    if (!box) return;

    const card = document.createElement("div");
    card.className = `alert-card ${alertSeverityClass(alert.severity)}`;

    const fromValue = alert.old_status ?? "N/A";
    const toValue = alert.new_status ?? "N/A";
    const fromLabel = formatStatusLabel(fromValue);
    const toLabel = formatStatusLabel(toValue);
    const transitionText = `${fromLabel} → ${toLabel}`;
    const rawTransitionText = `${fromValue} → ${toValue}`;
    const showRawTransition = String(fromValue).includes(".") || String(toValue).includes(".") || String(alert.alert_type || "").toUpperCase() === "DNS_CHANGE";

    card.innerHTML = `
        <div class="alert-header">
            <strong>${escapeHtml(alert.host_name)}</strong>
        </div>
        <div class="alert-subtitle">
            ${escapeHtml(showRawTransition ? rawTransitionText : transitionText)}
        </div>
        <div class="alert-subtitle">
            ${escapeHtml(alert.host_address)}${alert.host_port ? `:${escapeHtml(alert.host_port)}` : ""} | ${escapeHtml(alertTypeLabel(alert.alert_type ?? "STATUS_CHANGE"))}
        </div>
        <div class="alert-subtitle">
            ${formatApiDateTime(alert.timestamp)}
        </div>
    `;

    box.appendChild(card);

    setTimeout(() => {
        card.remove();
    }, 12000);
}

function triggerAllFrontendAlerts() {
    const nowIso = new Date().toISOString();
    const samples = [
        {
            host_name: "youtube",
            host_address: "youtube.com",
            host_port: 443,
            alert_type: "DNS_CHANGE",
            old_status: "172.217.29.174",
            new_status: "['172.217.30.142']",
            severity: "HEALTHY",
            timestamp: nowIso
        },
        {
            host_name: "ifnmg",
            host_address: "ifnmg.edu.br",
            host_port: 443,
            alert_type: "DNS_TTL_LOW",
            old_status: "ttl",
            new_status: "45",
            severity: "WARNING",
            timestamp: nowIso
        },
        {
            host_name: "google",
            host_address: "google.com",
            host_port: 443,
            alert_type: "STATUS_CHANGE",
            old_status: "UP",
            new_status: "DEGRADED",
            severity: "DEGRADED",
            timestamp: nowIso
        },
        {
            host_name: "Meu PC",
            host_address: "192.168.0.10",
            host_port: 80,
            alert_type: "HEALTH_CRITICAL",
            old_status: "DEGRADED",
            new_status: "DOWN",
            severity: "CRITICAL",
            timestamp: nowIso
        },
        {
            host_name: "gateway",
            host_address: "10.0.0.1",
            host_port: null,
            alert_type: "UP_RECOVERED",
            old_status: "DOWN",
            new_status: "UP_RECOVERED",
            severity: "HEALTHY",
            timestamp: nowIso
        }
    ];

    samples.forEach((sample, idx) => {
        setTimeout(() => showAlertCard(sample), idx * 450);
    });
}

window.triggerAllFrontendAlerts = triggerAllFrontendAlerts;

let lastAlertTime = null;

async function checkAlerts() {
    const res = await fetchWithAuth(`${API}/alerts/list`);
    if (!res) return;

    const alerts = await res.json();
    if (!Array.isArray(alerts) || alerts.length === 0) return;

    if (!seenAlertsBootstrapped) {
        alerts.forEach((a) => rememberSeenAlert(alertSeenKey(a)));
        persistSeenAlertKeys();
        seenAlertsBootstrapped = true;
        lastAlertTime = alerts[0]?.timestamp || lastAlertTime;
        return;
    }

    const ordered = [...alerts].reverse();
    let newestSeen = lastAlertTime;
    let storageChanged = false;

    ordered.forEach((a) => {
        const seenKey = alertSeenKey(a);
        if (!newestSeen || a.timestamp > newestSeen) {
            newestSeen = a.timestamp;
        }
        if (seenAlertKeysSet.has(seenKey)) return;
        if (!shouldRenderAlertCard(a)) {
            rememberSeenAlert(seenKey);
            storageChanged = true;
            return;
        }
        showAlertCard(a);
        rememberSeenAlert(seenKey);
        storageChanged = true;
    });

    if (storageChanged) {
        persistSeenAlertKeys();
    }

    if (newestSeen && (!lastAlertTime || newestSeen > lastAlertTime)) {
        lastAlertTime = newestSeen;
    }
}

async function softDeleteHost(hostId, hostName) {
    if (!hostName) return;
    if (pendingDeletedHostNames.has(hostName)) return; // Previne cliques duplicados
    if (!confirm(`Mover host "${hostName}" para a lixeira?`)) return;

    // Registra como exclusão pendente imediatamente para blindar contra respostas concorrentes de polling
    pendingDeletedHostNames.add(hostName);
    currentHostsMap.delete(hostName);

    // Destrói gráficos ativos para liberar memória
    destroyChartsForHost(hostName);

    // Remoção visual imediata/otimista do card e linha da tabela NOC
    const cardNode = document.getElementById(`card-${hostName}`);
    if (cardNode) {
        cardNode.style.transition = "opacity 0.2s ease, transform 0.2s ease";
        cardNode.style.opacity = "0";
        cardNode.style.transform = "scale(0.95)";
        setTimeout(() => {
            if (cardNode.parentNode) {
                cardNode.remove();
                const hostsDiv = document.getElementById("hosts");
                if (hostsDiv && !hostsDiv.querySelector(".card")) {
                    hostsDiv.innerHTML = "<div class='ui-state ui-state-empty'>Nenhum host cadastrado ainda.</div>";
                }
            }
        }, 200);
    }
    const rowNode = document.getElementById(`row-${hostName}`);
    if (rowNode) {
        rowNode.style.transition = "opacity 0.2s ease";
        rowNode.style.opacity = "0";
        setTimeout(() => {
            if (rowNode.parentNode) rowNode.remove();
        }, 200);
    }

    try {
        const res = await fetchWithAuth(`${API}/hosts/${hostId}/deactivate?host_name=${encodeURIComponent(hostName)}`, {
            method: "POST"
        });

        if (!res || !res.ok) {
            const err = res ? await res.json() : {};
            pendingDeletedHostNames.delete(hostName);
            showToast("error", "Erro ao mover para lixeira: " + (err.detail || "erro"));
            await loadHosts();
            return;
        }

        selectedBulkDeactivateNames.delete(hostName);
        showToast("success", "Host movido para a lixeira.");
        await Promise.all([
            loadHosts(),
            loadTrashHosts(),
            loadBulkDeactivateHosts(),
            loadDashboardSummary()
        ]);

        // Mantém proteção de 2 segundos para drenar qualquer resposta de rede concorrente defasada
        setTimeout(() => {
            pendingDeletedHostNames.delete(hostName);
        }, 2000);

    } catch (e) {
        pendingDeletedHostNames.delete(hostName);
        showToast("error", "Falha de conexão com a API.");
        await loadHosts();
    }
}

async function loadTrashHosts() {
    const box = document.getElementById("trashHostsList");
    const emptyBtn = document.getElementById("emptyTrashBtn");
    if (!box) return;

    try {
        const res = await fetchWithAuth(`${API}/hosts/trash`);
        if (!res || !res.ok) {
            box.innerHTML = "<small>Não foi possível carregar a lixeira.</small>";
            if (emptyBtn) emptyBtn.disabled = true;
            return;
        }

        const hosts = await res.json();
        if (!Array.isArray(hosts) || hosts.length === 0) {
            box.innerHTML = "<div class='ui-state ui-state-empty' style='text-align: center; padding: 20px; margin: 8px 0;'>A lixeira está vazia.</div>";
            if (emptyBtn) emptyBtn.disabled = true;
            return;
        }

        if (emptyBtn) emptyBtn.disabled = false;

        box.innerHTML = hosts.map((host) => `
            <div class="trash-item">
                <div class="trash-meta">
                    <strong>${escapeHtml(host.name)}</strong>
                    <small>${escapeHtml(host.address)}${host.port ? `:${escapeHtml(host.port)}` : ""}</small>
                    <small>Desativado em: ${formatApiDateTime(host.deleted_at)}</small>
                </div>
                <div class="trash-actions">
                    <button onclick='restoreHost(${Number(host.id)}, ${escapeJsSingleQuotedAttr(String(host.name))})'>Restaurar</button>
                    <button class="danger-btn" onclick='hardDeleteHost(${Number(host.id)}, ${escapeJsSingleQuotedAttr(String(host.name))})'>Excluir permanentemente</button>
                </div>
            </div>
        `).join("");
    } catch (err) {
        box.innerHTML = "<small>Erro ao carregar lixeira.</small>";
        if (emptyBtn) emptyBtn.disabled = true;
    }
}

let bulkDeactivateHostsCache = [];
const selectedBulkDeactivateNames = new Set();

function updateBulkDeactivateSelectionUI() {
    const checkboxes = Array.from(document.querySelectorAll("#bulkDeactivateHostsList .bulk-deactivate-check:not(:disabled)"));
    const selectAllBtn = document.getElementById("selectAllBulkDeactivateBtn");
    const actionBtn = document.getElementById("bulkDeactivateSelectedBtn");
    const infoEl = document.getElementById("bulkDeactivateSelectionInfo");

    const totalActive = bulkDeactivateHostsCache.length;
    const selectedCount = selectedBulkDeactivateNames.size;

    if (infoEl) {
        infoEl.textContent = `${selectedCount} selecionado(s) de ${totalActive} host(s)`;
    }
    if (actionBtn) {
        actionBtn.disabled = selectedCount === 0;
        const trashIconSvg = `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 4h6l1 2h4v2H4V6h4l1-2zm-2 6h2v8H7v-8zm4 0h2v8h-2v-8zm4 0h2v8h-2v-8z"/></svg>`;
        const actionLabel = selectedCount > 0
            ? `Mover selecionados (${selectedCount})`
            : "Mover selecionados para lixeira";
        actionBtn.innerHTML = `${trashIconSvg}<span>${actionLabel}</span>`;
    }
    if (selectAllBtn) {
        selectAllBtn.disabled = checkboxes.length === 0;
        const allVisibleChecked = checkboxes.length > 0 && checkboxes.every((cb) => cb.checked);
        const iconSvg = allVisibleChecked
            ? `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="9" y1="9" x2="15" y2="15"></line><line x1="15" y1="9" x2="9" y2="15"></line></svg>`
            : `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><polyline points="9 11 12 14 22 4"></polyline></svg>`;
        selectAllBtn.innerHTML = `${iconSvg}<span>${allVisibleChecked ? "Desmarcar todos" : "Selecionar todos"}</span>`;
    }
}

function renderBulkDeactivateHostsList() {
    const box = document.getElementById("bulkDeactivateHostsList");
    const searchInput = document.getElementById("bulkDeactivateSearchInput");
    if (!box) return;

    const query = String(searchInput?.value || "").trim().toLowerCase();
    const activeNamesSet = new Set(bulkDeactivateHostsCache.map((h) => h.name));
    for (const name of Array.from(selectedBulkDeactivateNames)) {
        if (!activeNamesSet.has(name)) {
            selectedBulkDeactivateNames.delete(name);
        }
    }

    if (bulkDeactivateHostsCache.length === 0) {
        box.innerHTML = "<div class='ui-state ui-state-empty' style='text-align: center; padding: 20px; margin: 8px 0;'>Nenhum host ativo no momento.</div>";
        updateBulkDeactivateSelectionUI();
        return;
    }

    const filtered = bulkDeactivateHostsCache.filter((h) => {
        if (!query) return true;
        const nameStr = String(h.name || "").toLowerCase();
        const addrStr = String(h.address || "").toLowerCase();
        const resolvedStr = String(h.last_resolved_ip || "").toLowerCase();
        return nameStr.includes(query) || addrStr.includes(query) || resolvedStr.includes(query);
    });

    if (filtered.length === 0) {
        box.innerHTML = "<div class='ui-state ui-state-empty' style='text-align: center; padding: 20px; margin: 8px 0;'>Nenhum host encontrado para esse filtro.</div>";
        updateBulkDeactivateSelectionUI();
        return;
    }

    box.innerHTML = filtered.map((host) => {
        const isChecked = selectedBulkDeactivateNames.has(host.name) ? "checked" : "";
        let statusDot = "bg-secondary";
        if (host.status === "UP") statusDot = "bg-success";
        else if (host.status === "DOWN") statusDot = "bg-danger";
        else if (host.status === "DEGRADED") statusDot = "bg-warning";

        const addrLabel = formatHostAddressLabel(host);
        return `
            <label class="trash-item bulk-select-item">
                <div class="bulk-select-left">
                    <input
                        type="checkbox"
                        class="bulk-deactivate-check"
                        data-id="${Number(host.id)}"
                        data-name="${escapeHtml(String(host.name))}"
                        ${isChecked}
                    >
                    <div class="trash-meta">
                        <strong>
                            <span class="status-indicator ${statusDot}" style="display:inline-block; margin-right:6px;"></span>${escapeHtml(host.name)}
                        </strong>
                        <small>${escapeHtml(addrLabel)}</small>
                    </div>
                </div>
                <div class="trash-actions">
                    <button
                        type="button"
                        class="danger-btn"
                        onclick='event.preventDefault(); event.stopPropagation(); softDeleteHost(${Number(host.id)}, ${escapeJsSingleQuotedAttr(String(host.name))})'
                    >Mover 1 para lixeira</button>
                </div>
            </label>
        `;
    }).join("");

    updateBulkDeactivateSelectionUI();
}

async function loadBulkDeactivateHosts() {
    const box = document.getElementById("bulkDeactivateHostsList");
    if (!box) return;

    try {
        const res = await fetchWithAuth(`${API}/hosts/list`);
        if (!res || !res.ok) {
            box.innerHTML = "<small>Não foi possível carregar os hosts ativos.</small>";
            return;
        }
        const rawHosts = await res.json();
        bulkDeactivateHostsCache = Array.isArray(rawHosts)
            ? rawHosts.filter((h) => !pendingDeletedHostNames.has(h.name))
            : [];
        renderBulkDeactivateHostsList();
    } catch (err) {
        box.innerHTML = "<small>Erro ao carregar hosts ativos.</small>";
    }
}

async function bulkDeactivateSelectedHosts() {
    const selectedHosts = bulkDeactivateHostsCache.filter((h) => selectedBulkDeactivateNames.has(h.name));
    if (selectedHosts.length === 0) {
        showToast("warning", "Selecione pelo menos um host para enviar à lixeira.");
        return;
    }

    if (!confirm(`Mover ${selectedHosts.length} host(s) selecionado(s) para a lixeira?`)) {
        return;
    }

    const hostIds = selectedHosts.map((h) => Number(h.id)).filter((id) => Number.isFinite(id));
    const hostNames = selectedHosts.map((h) => String(h.name));

    const actionBtn = document.getElementById("bulkDeactivateSelectedBtn");
    if (actionBtn) {
        actionBtn.disabled = true;
        setButtonLabel(actionBtn, "Movendo...");
    }

    // Remoção visual imediata no Dashboard e proteção contra race condition de polling
    for (const hostName of hostNames) {
        pendingDeletedHostNames.add(hostName);
        destroyChartsForHost(hostName);
        currentHostsMap.delete(hostName);
        const cardNode = document.getElementById(`card-${hostName}`);
        if (cardNode) cardNode.remove();
        const rowNode = document.getElementById(`row-${hostName}`);
        if (rowNode) rowNode.remove();
    }
    const hostsDiv = document.getElementById("hosts");
    if (hostsDiv && !hostsDiv.querySelector(".card")) {
        hostsDiv.innerHTML = "<div class='ui-state ui-state-empty'>Nenhum host cadastrado ainda.</div>";
    }
    updateStatusChipCounts();

    try {
        const res = await fetchWithAuth(`${API}/hosts/bulk-deactivate`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                host_ids: hostIds,
                host_names: hostNames
            })
        });

        if (!res || !res.ok) {
            const err = res ? await res.json().catch(() => ({})) : {};
            for (const hostName of hostNames) {
                pendingDeletedHostNames.delete(hostName);
            }
            showToast("error", "Erro ao mover hosts para lixeira: " + (err.detail || "erro"));
            await Promise.all([loadHosts(), loadBulkDeactivateHosts()]);
            return;
        }

        const data = await res.json().catch(() => ({}));
        for (const hostName of hostNames) {
            selectedBulkDeactivateNames.delete(hostName);
        }

        showToast("success", data.detail || `${hostNames.length} host(s) movido(s) para a lixeira.`);
        await Promise.all([
            loadHosts(),
            loadTrashHosts(),
            loadBulkDeactivateHosts(),
            loadDashboardSummary()
        ]);

        setTimeout(() => {
            for (const hostName of hostNames) {
                pendingDeletedHostNames.delete(hostName);
            }
        }, 2000);
    } catch (err) {
        for (const hostName of hostNames) {
            pendingDeletedHostNames.delete(hostName);
        }
        showToast("error", "Falha de conexão com a API.");
        await Promise.all([loadHosts(), loadBulkDeactivateHosts()]);
    } finally {
        updateBulkDeactivateSelectionUI();
    }
}

function switchTrashModalTab(tab) {
    const tabDeactivateBtn = document.getElementById("tabBulkDeactivateBtn");
    const tabTrashBtn = document.getElementById("tabTrashItemsBtn");
    const panelDeactivate = document.getElementById("trashTabDeactivate");
    const panelTrash = document.getElementById("trashTabItems");
    const modalTitle = document.getElementById("trashModalTitle");

    const isDeactivate = tab === "deactivate";

    if (tabDeactivateBtn) {
        tabDeactivateBtn.classList.toggle("active", isDeactivate);
        tabDeactivateBtn.setAttribute("aria-selected", isDeactivate ? "true" : "false");
    }
    if (tabTrashBtn) {
        tabTrashBtn.classList.toggle("active", !isDeactivate);
        tabTrashBtn.setAttribute("aria-selected", !isDeactivate ? "true" : "false");
    }
    if (panelDeactivate) {
        panelDeactivate.classList.toggle("hidden", !isDeactivate);
    }
    if (panelTrash) {
        panelTrash.classList.toggle("hidden", isDeactivate);
    }
    if (modalTitle) {
        modalTitle.textContent = isDeactivate ? "Enviar Hosts para a Lixeira" : "Itens na Lixeira";
    }

    if (isDeactivate) {
        runTaskOnce("bulk-deactivate", loadBulkDeactivateHosts);
    } else {
        runTaskOnce("trash", loadTrashHosts);
    }
}

function openBulkDeactivateModal() {
    const modal = document.getElementById("trashModal");
    if (!modal) return;
    openAppModal(modal);
    switchTrashModalTab("deactivate");
}

function openTrashModal() {
    const modal = document.getElementById("trashModal");
    if (!modal) return;
    openAppModal(modal);
    switchTrashModalTab("trash");
}

function closeTrashModal() {
    const modal = document.getElementById("trashModal");
    if (!modal) return;
    closeAppModal(modal);
}

function openConfirmEmptyTrashModal() {
    const modal = document.getElementById("confirmEmptyTrashModal");
    if (modal) openAppModal(modal);
}

function closeConfirmEmptyTrashModal() {
    const modal = document.getElementById("confirmEmptyTrashModal");
    if (modal) closeAppModal(modal);
}


async function confirmEmptyTrash() {
    const confirmBtn = document.getElementById("confirmEmptyTrashBtn");
    const originalText = getButtonLabel(confirmBtn, "Sim, Excluir Todos");
    if (confirmBtn) {
        confirmBtn.disabled = true;
        setButtonLabel(confirmBtn, "Excluindo...");
    }

    try {
        const res = await fetchWithAuth(`${API}/hosts/trash/empty`, {
            method: "DELETE"
        });

        if (res && res.ok) {
            const data = await res.json().catch(() => ({}));
            closeConfirmEmptyTrashModal();
            showToast("success", data.detail || "Lixeira esvaziada com sucesso.");
            await Promise.all([
                loadTrashHosts(),
                loadDashboardSummary()
            ]);
        } else {
            const err = res ? await res.json().catch(() => ({})) : {};
            showToast("error", err.detail || "Erro ao esvaziar lixeira.");
        }
    } catch (err) {
        showToast("error", "Não foi possível conectar ao servidor.");
    } finally {
        if (confirmBtn) {
            confirmBtn.disabled = false;
            setButtonLabel(confirmBtn, originalText);
        }
    }
}

function openSidebarMenu() {
    const menu = document.getElementById("sidebarMenu");
    const overlay = document.getElementById("sidebarOverlay");
    if (!menu || !overlay) return;
    menu.classList.remove("hidden");
    menu.setAttribute("aria-hidden", "false");
    overlay.classList.remove("hidden");
    const openBtn = document.getElementById("openMenuBtn");
    if (openBtn) openBtn.setAttribute("aria-expanded", "true");
}

function closeSidebarMenu() {
    const menu = document.getElementById("sidebarMenu");
    const overlay = document.getElementById("sidebarOverlay");
    if (!menu || !overlay) return;
    menu.classList.add("hidden");
    menu.setAttribute("aria-hidden", "true");
    overlay.classList.add("hidden");
    const openBtn = document.getElementById("openMenuBtn");
    if (openBtn) openBtn.setAttribute("aria-expanded", "false");
}

async function restoreHost(hostId, hostName) {
    if (!confirm(`Restaurar o host "${hostName}" da lixeira?`)) return;

    try {
        const res = await fetchWithAuth(`${API}/hosts/${hostId}/restore?host_name=${encodeURIComponent(hostName)}`, {
            method: "POST"
        });
        if (!res || !res.ok) {
            const err = res ? await res.json() : {};
            showToast("error", "Erro ao restaurar: " + (err.detail || "erro"));
            return;
        }

        showToast("success", "Host restaurado com sucesso.");
        await Promise.all([
            loadHosts(),
            loadTrashHosts(),
            loadBulkDeactivateHosts(),
            loadDashboardSummary()
        ]);
    } catch (err) {
        showToast("error", "Falha de conexão com a API.");
    }
}

async function hardDeleteHost(hostId, hostName) {
    if (!hostName) return;
    if (!confirm(`Excluir permanentemente o host "${hostName}"?\nEssa ação não pode ser desfeita.`)) return;

    destroyChartsForHost(hostName);
    const cardNode = document.getElementById(`card-${hostName}`);
    if (cardNode) {
        cardNode.remove();
        const hostsDiv = document.getElementById("hosts");
        if (hostsDiv && !hostsDiv.querySelector(".card")) {
            hostsDiv.innerHTML = "<div class='ui-state ui-state-empty'>Nenhum host cadastrado ainda.</div>";
        }
    }

    try {
        const res = await fetchWithAuth(`${API}/hosts/${hostId}/hard-delete?host_name=${encodeURIComponent(hostName)}`, {
            method: "DELETE"
        });
        if (!res || !res.ok) {
            const err = res ? await res.json() : {};
            showToast("error", "Erro na exclusão permanente: " + (err.detail || "erro"));
            await loadHosts();
            await loadTrashHosts();
            return;
        }

        showToast("success", "Host excluído permanentemente.");
        await Promise.all([
            loadHosts(),
            loadTrashHosts(),
            loadDashboardSummary()
        ]);
    } catch (err) {
        showToast("error", "Falha de conexão com a API.");
        await loadHosts();
    }
}

async function toggleAvailabilityChart(name) {
    const box = document.getElementById(`availability-chart-box-${name}`);
    if (!box) return;

    if (box.classList.contains("hidden")) {
        closeHostExpandedPanels(name, box.id);
        box.classList.remove("hidden");
        await loadAvailability(name);
    } else {
        box.classList.add("hidden");
    }
}

async function loadAvailability(name) {
    const chartId = `availability-chart-${name}`;
    const ctx = document.getElementById(chartId);
    if (!ctx) return;

    try {
        const response = await fetchWithAuth(`${API}/hosts/metrics/availability/host/${encodeURIComponent(name)}`);
        
        if (!response || !response.ok) return;

        const data = await response.json();

        const limited = takeLast(data);
        const labels = limited.map(p => formatApiTime(p.timestamp));
        const values = limited.map(p => p.availability);

        const chartKey = `availability-${name}`;

        if (!labels.length) {
            showChartEmpty(
                "availability-chart-box-" + name,
                "availability-chart-" + name,
                "Sem dados de disponibilidade."
            );
            return;
        }
        clearChartEmpty("availability-chart-box-" + name, "availability-chart-" + name);

        const isDark = document.body.classList.contains("dark-theme") || document.documentElement.classList.contains("dark-theme");
        const availColor = isDark ? "#81c995" : "#1e8e3e";

        const T = window.NetSpotChartTheme;
        T.renderSummary(ctx, [
            { label: "Disponibilidade", color: availColor, values, fmt: (v) => `${v.toFixed(2)}%` },
        ]);

        const availOpts = chartCommonOptions(0, 100, "Disponibilidade (%)");
        availOpts.plugins.thresholdBands = T.thresholdBands("y", [
            { from: 0, to: 85, color: "rgba(217,48,37,0.08)" },
            { from: 85, to: 95, color: "rgba(249,171,0,0.09)" },
        ]);

        updateOrCreateChart(chartKey, ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Disponibilidade Host (%)',
                    data: values,
                    ...T.lineStyle(availColor)
                }]
            },
            options: availOpts
        });
    } catch (err) {
        console.error("Erro ao carregar disponibilidade:", err);
    }
}

async function loadTimeline() {
    const container = document.getElementById("incidentTimeline");
    if (!container) return;

    try {
        const res = await fetchWithAuth(`${API}/incidents/latest`);
        if (!res || !res.ok) return;

        const incidents = await res.json();
        if (!Array.isArray(incidents) || incidents.length === 0) {
            container.innerHTML = `<div class="timeline-empty">Sem incidentes recentes.</div>`;
            return;
        }

        const ordered = [...incidents].sort(
            (a, b) => new Date(b.started_time).getTime() - new Date(a.started_time).getTime()
        );

        container.innerHTML = ordered.map((inc) => {
            const isClosed = String(inc.status || "").toUpperCase() === "CLOSED";
            const incidentType = String(inc.incident_type || "").toUpperCase();
            let statusLabel = incidentTypeLabel(incidentType);
            if (!isClosed) {
                statusLabel = incidentTypeLabel(incidentType);
            } else {
                statusLabel = "Recuperado";
            }
            const badgeClass = isClosed ? "timeline-badge-closed" : "timeline-badge-open";
            const itemClass = isClosed ? "timeline-item-closed" : "timeline-item-open";
            const startedAt = formatApiDateTime(inc.started_time);
            const endedAt = inc.ended_time ? formatApiDateTime(inc.ended_time) : "Em andamento";
            const durationText = inc.duration
                ? `${Math.max(1, Math.round(inc.duration / 60))} min`
                : "Em andamento";
            const reasonText = inc.reason_text || inc.reason || "Sem causa provável informada.";

            return `
                <div class="timeline-item ${itemClass}">
                    <div class="timeline-item-top">
                        <strong class="timeline-host">${escapeHtml(inc.host_name)}</strong>
                        <span class="timeline-badge ${badgeClass}">${escapeHtml(statusLabel)}</span>
                    </div>
                    <div class="timeline-item-meta">
                        <small>Início: ${startedAt}</small>
                        <small>Fim: ${endedAt}</small>
                        <small>Duração: ${durationText}</small>
                    </div>
                    <p class="timeline-reason">${escapeHtml(reasonText)}</p>
                </div>
            `;
        }).join("");
    } catch (err) {
        console.error("Erro ao carregar timeline:", err);
    }
}

async function loadDashboardSummary() {
    const box = document.getElementById("dashboardSummary");
    if (!box) return;

    const res = await fetchWithAuth(`${API}/dashboard/summary`);
    if (!res || !res.ok) return;

    const data = await res.json();

    if (box.querySelectorAll(".summary-card").length !== 6) {
        const defs = [
            ["Hosts monitorados", "summary-total", "all", "Exibir todos os hosts"],
            ["Online", "summary-ok", "bg-success", "Filtrar apenas hosts Online"],
            ["Degradados", "summary-warn", "bg-warning", "Filtrar apenas hosts Degradados"],
            ["Offline", "summary-bad", "bg-danger", "Filtrar apenas hosts Offline"],
            ["Incidentes abertos", "summary-bad", "incidents-open", "Ver incidentes abertos no histórico"],
            ["Incidentes fechados", "summary-muted", "incidents-closed", "Ver incidentes fechados no histórico"],
        ];
        box.innerHTML = defs.map(([label, cls, filterKey, titleText]) => `
            <div class="summary-card ${cls} summary-card-clickable" data-filter="${filterKey}" role="button" tabindex="0" title="${titleText}" aria-label="${titleText}">
                <small>${label}</small>
                <strong>0</strong>
            </div>`).join("") + `
            <div class="summary-bar" role="img">
                <span class="summary-bar-seg seg-ok"></span>
                <span class="summary-bar-seg seg-warn"></span>
                <span class="summary-bar-seg seg-bad"></span>
            </div>`;

        box.querySelectorAll(".summary-card-clickable").forEach((card) => {
            const trigger = () => handleSummaryCardClick(card.dataset.filter);
            card.addEventListener("click", trigger);
            card.addEventListener("keydown", (e) => {
                if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    trigger();
                }
            });
        });
    }

    const values = [
        data.total_hosts, data.up, data.degraded, data.down,
        data.open_incidents, data.closed_incidents,
    ];
    const strongs = box.querySelectorAll(".summary-card strong");
    values.forEach((v, i) => {
        if (strongs[i]) strongs[i].textContent = v ?? 0;
    });
    updateSummaryBar(box, data);
    syncSummaryCardHighlight();
}

function handleSummaryCardClick(filterKey) {
    if (!filterKey) return;
    if (filterKey === "incidents-open") {
        window.location.href = "incidents.html?status=open";
        return;
    }
    if (filterKey === "incidents-closed") {
        window.location.href = "incidents.html?status=closed";
        return;
    }

    const select = document.getElementById("statusFilter");
    if (!select) return;

    if (select.value === filterKey && filterKey !== "all") {
        select.value = "all";
    } else {
        select.value = filterKey;
    }

    syncStatusChips();
    syncSummaryCardHighlight();
    filterHosts();

    const labelMap = { "all": "Todos", "bg-success": "Online", "bg-warning": "Degradados", "bg-danger": "Offline" };
    showToast("info", `Filtro: ${labelMap[select.value] || select.value}`);
}

function syncSummaryCardHighlight() {
    const select = document.getElementById("statusFilter");
    const currentVal = select ? select.value : "all";
    const box = document.getElementById("dashboardSummary");
    if (!box) return;
    box.querySelectorAll(".summary-card-clickable").forEach((card) => {
        const filter = card.dataset.filter;
        if (filter === "incidents-open" || filter === "incidents-closed") return;
        card.classList.toggle("active-filter", filter === currentVal);
    });
}

// Barra proporcional Online / Degradado / Offline (soma = hosts monitorados).
function updateSummaryBar(box, data) {
    const bar = box.querySelector(".summary-bar");
    if (!bar) return;
    const up = Number(data.up) || 0;
    const degraded = Number(data.degraded) || 0;
    const down = Number(data.down) || 0;
    const total = Math.max(Number(data.total_hosts) || 0, up + degraded + down);
    const pct = (n) => (total > 0 ? (n / total) * 100 : 0);
    const segs = { ok: up, warn: degraded, bad: down };
    for (const [key, n] of Object.entries(segs)) {
        const seg = bar.querySelector(`.seg-${key}`);
        if (seg) seg.style.width = `${pct(n)}%`;
    }
    bar.setAttribute("aria-label", `Online ${up}, degradado ${degraded}, offline ${down} de ${total} hosts`);
    bar.title = bar.getAttribute("aria-label");
}

// ======================
// Chips de filtro por status (sincronizados com o <select id="statusFilter">)
// ======================
const STATUS_CHIPS = [
    ["all", "Todos"],
    ["bg-success", "Online"],
    ["bg-warning", "Degradado"],
    ["bg-danger", "Offline"],
];

function syncStatusChips() {
    const select = document.getElementById("statusFilter");
    const bar = document.getElementById("statusChips");
    if (!select || !bar) return;
    bar.querySelectorAll(".status-chip").forEach((chip) => {
        const active = chip.dataset.status === select.value;
        chip.classList.toggle("active", active);
        chip.setAttribute("aria-pressed", active ? "true" : "false");
    });
    syncSummaryCardHighlight();
}

function updateStatusChipCounts() {
    const bar = document.getElementById("statusChips");
    if (!bar) return;
    const counts = { all: 0, "bg-success": 0, "bg-warning": 0, "bg-danger": 0 };
    document.querySelectorAll("#hosts .card").forEach((card) => {
        counts.all += 1;
        const dot = card.querySelector(".status-indicator");
        if (!dot) return;
        for (const key of ["bg-success", "bg-warning", "bg-danger"]) {
            if (dot.classList.contains(key)) counts[key] += 1;
        }
    });
    bar.querySelectorAll(".status-chip").forEach((chip) => {
        const el = chip.querySelector(".status-chip-count");
        if (el) el.textContent = counts[chip.dataset.status] ?? 0;
    });
}

function initStatusChips() {
    const select = document.getElementById("statusFilter");
    const bar = document.getElementById("statusChips");
    if (!select || !bar) return;
    bar.innerHTML = STATUS_CHIPS.map(([value, label]) => `
        <button type="button" class="status-chip" data-status="${value}" aria-pressed="false">
            ${label}<span class="status-chip-count">0</span>
        </button>`).join("");
    bar.addEventListener("click", (event) => {
        const chip = event.target.closest(".status-chip");
        if (!chip) return;
        select.value = chip.dataset.status;
        syncStatusChips();
        syncSummaryCardHighlight();
        filterHosts();
    });
    select.addEventListener("change", () => {
        syncStatusChips();
        syncSummaryCardHighlight();
    });
    syncStatusChips();
}

function filterHosts() {
    const searchInput = document.getElementById("searchInput");
    const statusInput = document.getElementById("statusFilter");
    const emptyState = document.getElementById("hostsEmptyState");
    const countBadge = document.getElementById("hostsCountBadge");
    if (!searchInput || !statusInput) return;

    const searchTerm = String(searchInput.value || "").toLowerCase().trim();
    const statusFilter = String(statusInput.value || "all");
    const cards = document.querySelectorAll("#hosts .card");
    const rows = document.querySelectorAll("#nocTableBody tr.noc-row");

    let visibleCardsCount = 0;

    cards.forEach((card) => {
        const hostTitleEl = card.querySelector(".host-title");
        const hostAddrEl = card.querySelector(".host-addr");
        const indicator = card.querySelector(".status-indicator");
        if (!hostTitleEl || !hostAddrEl || !indicator) return;

        const hostName = hostTitleEl.innerText.toLowerCase();
        const hostAddr = hostAddrEl.innerText.toLowerCase();
        
        const matchesSearch = !searchTerm || hostName.includes(searchTerm) || hostAddr.includes(searchTerm);
        const matchesStatus = statusFilter === "all" || indicator.classList.contains(statusFilter);

        if (matchesSearch && matchesStatus) {
            card.style.display = "";
            visibleCardsCount++;
        } else {
            card.style.display = "none";
        }
    });

    rows.forEach((row) => {
        const hostNameEl = row.querySelector(".noc-device-name");
        const hostAddrEl = row.querySelector(".noc-device-addr");
        const indicator = row.querySelector(".status-indicator");
        if (!hostNameEl || !hostAddrEl || !indicator) return;

        const hostName = hostNameEl.innerText.toLowerCase();
        const hostAddr = hostAddrEl.innerText.toLowerCase();

        const matchesSearch = !searchTerm || hostName.includes(searchTerm) || hostAddr.includes(searchTerm);
        const matchesStatus = statusFilter === "all" || indicator.classList.contains(statusFilter);

        if (matchesSearch && matchesStatus) {
            row.style.display = "";
        } else {
            row.style.display = "none";
        }
    });

    const totalCount = cards.length > 0 ? cards.length : rows.length;
    if (countBadge) {
        if (searchTerm || statusFilter !== "all") {
            countBadge.textContent = `${visibleCardsCount} de ${totalCount} hosts`;
            countBadge.classList.add("is-filtered");
        } else {
            countBadge.textContent = `${totalCount} ${totalCount === 1 ? "host" : "hosts"}`;
            countBadge.classList.remove("is-filtered");
        }
    }

    if (emptyState) {
        if (visibleCardsCount === 0 && totalCount > 0) {
            emptyState.classList.remove("hidden");
        } else {
            emptyState.classList.add("hidden");
        }
    }
}

function clearHostFilters() {
    const searchInput = document.getElementById("searchInput");
    const statusInput = document.getElementById("statusFilter");
    if (searchInput) searchInput.value = "";
    if (statusInput) statusInput.value = "all";
    syncStatusChips();
    syncSummaryCardHighlight();
    filterHosts();
    showToast("info", "Filtros limpos");
}

// ======================
// Inicialização e Loop
// ======================

if (!isLoginPage) {
    const modalAddPortBtn = document.getElementById("modalAddPortBtn");
    const modalPortsContainer = document.getElementById("modalPortsContainer");
    if (modalAddPortBtn && modalPortsContainer) {
        modalAddPortBtn.addEventListener("click", () => addPortInput(modalPortsContainer, "", true));
    }

    const openBulkDeactivateBtn = document.getElementById("openBulkDeactivateBtn");
    if (openBulkDeactivateBtn) {
        openBulkDeactivateBtn.addEventListener("click", openBulkDeactivateModal);
    }

    const openTrashBtn = document.getElementById("openTrashBtn");
    if (openTrashBtn) {
        openTrashBtn.addEventListener("click", openTrashModal);
    }

    const refreshBtn = document.getElementById("refreshBtn");
    if (refreshBtn) {
        refreshBtn.addEventListener("click", async () => {
            const icon = refreshBtn.querySelector(".refresh-icon") || refreshBtn.querySelector("svg");
            if (icon) icon.classList.add("spin");
            try {
                await runTaskOnce("hosts-full", loadHosts);
                await runTaskOnce("summary", loadDashboardSummary);
            } finally {
                if (icon) setTimeout(() => icon.classList.remove("spin"), 450);
            }
        });
    }
    const refreshTrashBtn = document.getElementById("refreshTrashBtn");
    if (refreshTrashBtn) {
        refreshTrashBtn.addEventListener("click", () => runTaskOnce("trash", loadTrashHosts));
    }
    const refreshBulkDeactivateBtn = document.getElementById("refreshBulkDeactivateBtn");
    if (refreshBulkDeactivateBtn) {
        refreshBulkDeactivateBtn.addEventListener("click", () => runTaskOnce("bulk-deactivate", loadBulkDeactivateHosts));
    }
    const bulkDeactivateSelectedBtn = document.getElementById("bulkDeactivateSelectedBtn");
    if (bulkDeactivateSelectedBtn) {
        bulkDeactivateSelectedBtn.addEventListener("click", bulkDeactivateSelectedHosts);
    }
    const bulkDeactivateSearchInput = document.getElementById("bulkDeactivateSearchInput");
    if (bulkDeactivateSearchInput) {
        bulkDeactivateSearchInput.addEventListener("input", () => {
            renderBulkDeactivateHostsList();
        });
    }
    const selectAllBulkDeactivateBtn = document.getElementById("selectAllBulkDeactivateBtn");
    if (selectAllBulkDeactivateBtn) {
        selectAllBulkDeactivateBtn.addEventListener("click", () => {
            const checkboxes = Array.from(document.querySelectorAll("#bulkDeactivateHostsList .bulk-deactivate-check:not(:disabled)"));
            if (checkboxes.length === 0) return;
            const anyUnchecked = checkboxes.some((cb) => !cb.checked);
            checkboxes.forEach((cb) => {
                cb.checked = anyUnchecked;
                const hName = cb.getAttribute("data-name");
                if (!hName) return;
                if (anyUnchecked) {
                    selectedBulkDeactivateNames.add(hName);
                } else {
                    selectedBulkDeactivateNames.delete(hName);
                }
            });
            updateBulkDeactivateSelectionUI();
        });
    }
    const bulkDeactivateHostsList = document.getElementById("bulkDeactivateHostsList");
    if (bulkDeactivateHostsList) {
        bulkDeactivateHostsList.addEventListener("change", (e) => {
            if (e.target.classList.contains("bulk-deactivate-check")) {
                const hName = e.target.getAttribute("data-name");
                if (hName) {
                    if (e.target.checked) {
                        selectedBulkDeactivateNames.add(hName);
                    } else {
                        selectedBulkDeactivateNames.delete(hName);
                    }
                }
                updateBulkDeactivateSelectionUI();
            }
        });
    }
    const discoverBtn = document.getElementById("discoverBtn");
    if (discoverBtn) {
        discoverBtn.addEventListener("click", discoverNetworkHosts);
    }
    const importSelectedBtn = document.getElementById("importSelectedBtn");
    if (importSelectedBtn) {
        importSelectedBtn.addEventListener("click", importSelectedLanHosts);
    }
    const selectAllDiscoveryBtn = document.getElementById("selectAllDiscoveryBtn");
    if (selectAllDiscoveryBtn) {
        selectAllDiscoveryBtn.addEventListener("click", () => {
            const checkboxes = Array.from(document.querySelectorAll("#networkDiscoveryList .discover-host-check:not(:disabled)"));
            if (checkboxes.length === 0) return;
            const anyUnchecked = checkboxes.some(cb => !cb.checked);
            checkboxes.forEach(cb => { cb.checked = anyUnchecked; });
            updateDiscoverySelectAllUI(anyUnchecked);
        });
    }
    const discoveryList = document.getElementById("networkDiscoveryList");
    if (discoveryList) {
        discoveryList.addEventListener("change", (e) => {
            if (e.target.classList.contains("discover-host-check")) {
                const checkboxes = Array.from(document.querySelectorAll("#networkDiscoveryList .discover-host-check:not(:disabled)"));
                const allChecked = checkboxes.length > 0 && checkboxes.every(cb => cb.checked);
                updateDiscoverySelectAllUI(allChecked);
            }
        });
    }
    const openMenuBtn = document.getElementById("openMenuBtn");
    if (openMenuBtn) {
        openMenuBtn.addEventListener("click", openSidebarMenu);
    }
    const closeMenuBtn = document.getElementById("closeMenuBtn");
    if (closeMenuBtn) {
        closeMenuBtn.addEventListener("click", closeSidebarMenu);
    }
    const sidebarOverlay = document.getElementById("sidebarOverlay");
    if (sidebarOverlay) {
        sidebarOverlay.addEventListener("click", closeSidebarMenu);
    }

    document.addEventListener("visibilitychange", () => {
        if (document.hidden) {
            stopDashboardPolling();
            startDashboardPolling();
            return;
        }
        resumeDashboardPolling();
        runLightRefresh();
        runHeavyRefresh();
    });

    ["pointerdown", "keydown", "input", "touchstart"].forEach((eventName) => {
        document.addEventListener(eventName, touchUserInteraction, { passive: true });
    });

    window.addEventListener("DOMContentLoaded", async () => {
        touchUserInteraction();
        await preloadDiscoverySubnet();
        renderDiscoveredLanHosts();
        await runTaskOnce("summary", loadDashboardSummary);
        await runTaskOnce("hosts-full", loadHosts);
        await runTaskOnce("trash", loadTrashHosts);
        await runTaskOnce("alerts", checkAlerts);
        startDashboardPolling();
    });
}

window.addEventListener("click", (event) => {
    const editModal = document.getElementById("editModal");
    const trashModal = document.getElementById("trashModal");
    const sidebarOverlay = document.getElementById("sidebarOverlay");
    const changePwdModal = document.getElementById("changePwdModal");
    const confirmEmptyTrashModal = document.getElementById("confirmEmptyTrashModal");
    const pwdModal = document.getElementById("pwdModal");

    if (event.target === editModal) closeModal();
    if (event.target === trashModal) closeTrashModal();
    if (event.target === sidebarOverlay) closeSidebarMenu();
    if (event.target === changePwdModal) closeChangePwdModal();
    if (event.target === confirmEmptyTrashModal) closeConfirmEmptyTrashModal();
    if (event.target === pwdModal) closeAppModal(pwdModal);
});

window.addEventListener("keydown", (event) => {
    const activeModal = document.querySelector(".modal:not(.hidden)");

    if (event.key === "Escape") {
        if (activeModal) {
            event.preventDefault();
            closeModal();
            closeTrashModal();
            closeChangePwdModal();
            closeConfirmEmptyTrashModal();
            const pwdModal = document.getElementById("pwdModal");
            if (pwdModal) closeAppModal(pwdModal);
        }
        closeSidebarMenu();
        return;
    }

    // Gerenciamento de foco acessível (Focus Trap)
    if (event.key === "Tab" && activeModal) {
        const focusableSelectors = 'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
        const focusables = Array.from(activeModal.querySelectorAll(focusableSelectors)).filter(el => el.offsetParent !== null);
        if (focusables.length === 0) return;

        const firstElement = focusables[0];
        const lastElement = focusables[focusables.length - 1];

        if (event.shiftKey && document.activeElement === firstElement) {
            event.preventDefault();
            lastElement.focus();
        } else if (!event.shiftKey && document.activeElement === lastElement) {
            event.preventDefault();
            firstElement.focus();
        }
    }
});

const editModalEl = document.getElementById("editModal");
if (editModalEl) {
    editModalEl.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && e.target.tagName === "INPUT") {
            e.preventDefault();
            submitModalEdit();
        }
    });
}

const changePwdModalEl = document.getElementById("changePwdModal");
if (changePwdModalEl) {
    changePwdModalEl.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && e.target.tagName === "INPUT") {
            e.preventDefault();
            changePassword();
        }
    });
}

const changePwdBtn = document.getElementById("changePasswordBtn");

if (changePwdBtn) {
    changePwdBtn.onclick = () => {
        const modal = document.getElementById("changePwdModal");
        if (modal) openAppModal(modal);
    };
}

function closeChangePwdModal() {
    const modal = document.getElementById("changePwdModal");
    if (modal) closeAppModal(modal);
}


const logoutBtn = document.getElementById("logoutBtn");

if (logoutBtn) {
    logoutBtn.onclick = () => {
        showToast("info", "Sessão encerrada.");
        localStorage.removeItem("token");
        setTimeout(() => {
            window.location.href = "login.html";
        }, 250);
    };
};

/* ==========================================================================
   THEME TOGGLER MANAGER (LIGHT / DARK THEME)
   ========================================================================== */
(function initThemeManager() {
    const themeToggleBtn = document.getElementById("themeToggleBtn");
    
    // Ler o estado atual do tema
    const savedTheme = localStorage.getItem("theme");
    const isDark = savedTheme === "dark";
    
    // Atualizar o ícone de carregamento inicial
    updateThemeIcon(isDark);
    
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener("click", () => {
            const currentIsDark = document.documentElement.classList.toggle("dark-theme");
            document.body.classList.toggle("dark-theme", currentIsDark);
            localStorage.setItem("theme", currentIsDark ? "dark" : "light");
            updateThemeIcon(currentIsDark);
            updateAllChartsTheme();
        });
    }
    
    function updateThemeIcon(isDarkState) {
        const btn = document.getElementById("themeToggleBtn");
        if (btn) btn.setAttribute("aria-pressed", isDarkState ? "true" : "false");
        const icon = document.getElementById("themeToggleIcon");
        if (!icon) return;
        if (isDarkState) {
            icon.innerHTML = `<path d="M12 3a9 9 0 109 9 9.75 9.75 0 00-.67-3.4 6.78 6.78 0 01-7.93-7.93A9.75 9.75 0 0012 3z" fill="currentColor"/>`;
            icon.removeAttribute("stroke");
        } else {
            icon.innerHTML = `<circle cx="12" cy="12" r="4" fill="var(--warning)"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" stroke="var(--warning)" stroke-width="2" stroke-linecap="round"/>`;
        }
    }

    function updateAllChartsTheme() {
        if (typeof charts === "undefined" || !charts) return;
        const currentIsDark = document.body.classList.contains("dark-theme") || document.documentElement.classList.contains("dark-theme");
        const textColor = currentIsDark ? "#94a3b8" : "#64748b";
        const gridColor = currentIsDark ? "rgba(255, 255, 255, 0.08)" : "rgba(15, 23, 42, 0.06)";
        const titleColor = currentIsDark ? "#f9fafb" : "#0f172a";
        
        Object.values(charts).forEach(chart => {
            if (!chart) return;
            
            // Scales (suporta eixo único y e múltiplos eixos como y_percent e y_bps)
            const scales = chart.options.scales || {};
            Object.entries(scales).forEach(([scaleKey, scaleObj]) => {
                if (!scaleObj) return;
                if (scaleKey !== "x" && scaleObj.title) {
                    scaleObj.title.color = titleColor;
                }
                if (scaleObj.grid) {
                    scaleObj.grid.color = gridColor;
                    scaleObj.grid.borderColor = gridColor;
                }
                if (scaleObj.ticks) {
                    scaleObj.ticks.color = textColor;
                }
            });
            
            // Legend
            if (chart.options.plugins?.legend?.labels) {
                chart.options.plugins.legend.labels.color = textColor;
            }
            
            // Tooltip
            if (chart.options.plugins?.tooltip) {
                chart.options.plugins.tooltip.backgroundColor = currentIsDark ? "#1e293b" : "#ffffff";
                chart.options.plugins.tooltip.titleColor = currentIsDark ? "#f8fafc" : "#0f172a";
                chart.options.plugins.tooltip.bodyColor = currentIsDark ? "#94a3b8" : "#475569";
                chart.options.plugins.tooltip.borderColor = currentIsDark ? "#334155" : "#e2e8f0";
            }
            
            chart.update();
        });
    }
})();

if (!isLoginPage) {
    initStatusChips();
    initViewMode();
}
