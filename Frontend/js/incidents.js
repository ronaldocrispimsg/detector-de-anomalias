const API = (window.location.protocol === "file:" || window.location.port === "5500" || window.location.port === "3000")
    ? "http://127.0.0.1:8000"
    : "/api";

async function fetchWithAuth(url, options = {}) {
    const token = localStorage.getItem("token");
    if (!token) {
        window.location.href = "login.html";
        return null;
    }

    const headers = {
        "Content-Type": "application/json",
        ...options.headers,
        "Authorization": `Bearer ${token}`,
    };

    try {
        const response = await fetch(url, { ...options, headers });
        if (response.status === 401) {
            localStorage.clear();
            window.location.href = "login.html";
            return null;
        }
        return response;
    } catch (error) {
        console.error("Erro de conexão:", error);
        return null;
    }
}

function formatDateTime(value) {
    if (!value) return "N/A";
    const dt = new Date(value);
    if (Number.isNaN(dt.getTime())) return "N/A";
    return dt.toLocaleString("pt-BR");
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

let incidentsCache = [];

function setIncidentsState(message, type = "info") {
    const box = document.getElementById("incidentsList");
    if (!box) return;
    box.innerHTML = `<div class="ui-state ui-state-${escapeHtml(type)}">${escapeHtml(message)}</div>`;
}

function renderIncidents(items) {
    const box = document.getElementById("incidentsList");
    if (!box) return;

    if (!items.length) {
        const searchTerm = document.getElementById("incidentsSearch")?.value || "";
        const isFiltered = Boolean(searchTerm.trim()) || currentFilter !== "all";
        box.innerHTML = `
            <div class="empty-state-box">
                <div class="empty-state-icon">
                    <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <circle cx="12" cy="12" r="10"></circle>
                        <line x1="12" y1="8" x2="12" y2="12"></line>
                        <line x1="12" y1="16" x2="12.01" y2="16"></line>
                    </svg>
                </div>
                <h3 class="empty-state-title">${isFiltered ? "Nenhum incidente encontrado" : "Sem incidentes registrados"}</h3>
                <p class="empty-state-desc">${isFiltered ? "Nenhum incidente corresponde ao filtro ou termo pesquisado." : "Todos os dispositivos monitorados operaram com estabilidade."}</p>
                ${isFiltered ? `<button type="button" class="btn-clear-filter" onclick="clearIncidentFilters()">Limpar filtros</button>` : ""}
            </div>
        `;
        return;
    }

    box.innerHTML = items.map((inc) => {
        const isClosed = String(inc.status || "").toUpperCase() === "CLOSED";
        const stateClass = isClosed ? "incident-closed" : "incident-open";
        const statusLabel = isClosed ? "Fechado" : "Aberto";
        const durationFormatted = inc.duration
            ? `${Math.max(1, Math.round(inc.duration / 60))} min`
            : "Em andamento";
        return `
        <div class="incident-row ${stateClass}">
            <div class="incident-row-main">
                <strong>${escapeHtml(inc.host_name || "Host")}</strong>
                <small class="incident-status-tag ${stateClass}">${statusLabel} • ${escapeHtml(inc.incident_type || "GENERIC")}</small>
            </div>
            <div class="incident-row-meta">
                <small>Início: ${escapeHtml(formatDateTime(inc.started_time))}</small>
                <small>Fim: ${escapeHtml(formatDateTime(inc.ended_time))}</small>
                <small>Duração: ${escapeHtml(durationFormatted)}</small>
            </div>
            <div class="incident-row-reason">${escapeHtml(inc.reason_text || inc.reason || "Sem descrição")}</div>
        </div>
    `}).join("");
}

let currentFilter = "all";

function updateChipCounts() {
    const total = incidentsCache.length;
    const openCount = incidentsCache.filter((inc) => String(inc.status || "").toUpperCase() === "OPEN").length;
    const closedCount = incidentsCache.filter((inc) => String(inc.status || "").toUpperCase() === "CLOSED").length;

    const countAllEl = document.getElementById("countAll");
    if (countAllEl) countAllEl.textContent = total;
    const countOpenEl = document.getElementById("countOpen");
    if (countOpenEl) countOpenEl.textContent = openCount;
    const countClosedEl = document.getElementById("countClosed");
    if (countClosedEl) countClosedEl.textContent = closedCount;
}

function applyFilters() {
    const term = String(document.getElementById("incidentsSearch")?.value || "").toLowerCase().trim();

    let filtered = incidentsCache;

    if (currentFilter === "open") {
        filtered = filtered.filter((inc) => String(inc.status || "").toUpperCase() === "OPEN");
    } else if (currentFilter === "closed") {
        filtered = filtered.filter((inc) => String(inc.status || "").toUpperCase() === "CLOSED");
    }

    if (term) {
        filtered = filtered.filter((inc) =>
            String(inc.host_name || "").toLowerCase().includes(term) ||
            String(inc.reason_text || inc.reason || "").toLowerCase().includes(term) ||
            String(inc.incident_type || "").toLowerCase().includes(term)
        );
    }

    renderIncidents(filtered);
}

function initStatusChips() {
    const chipsContainer = document.getElementById("incidentStatusChips");
    if (!chipsContainer) return;

    chipsContainer.addEventListener("click", (e) => {
        const btn = e.target.closest(".status-chip");
        if (!btn) return;
        const status = btn.getAttribute("data-status");
        if (!status) return;

        currentFilter = status;

        chipsContainer.querySelectorAll(".status-chip").forEach((chip) => {
            chip.classList.toggle("active", chip === btn);
        });

        applyFilters();
    });
}

async function loadIncidents(silent = false) {
    const refreshBtn = document.getElementById("refreshIncidentsBtn");
    const refreshIcon = refreshBtn?.querySelector(".refresh-icon");
    if (refreshIcon) refreshIcon.classList.add("spin");

    if (!silent) {
        setIncidentsState("Carregando incidentes...", "info");
    }

    try {
        const res = await fetchWithAuth(`${API}/incidents/latest`);
        if (!res || !res.ok) {
            if (!silent) {
                setIncidentsState("Não foi possível carregar os incidentes.", "error");
            }
            return;
        }
        const data = await res.json();
        incidentsCache = Array.isArray(data) ? data : [];
        updateChipCounts();
        applyFilters();
    } finally {
        if (refreshIcon) {
            setTimeout(() => refreshIcon.classList.remove("spin"), 400);
        }
    }
}

function clearIncidentFilters() {
    const searchInput = document.getElementById("incidentsSearch");
    if (searchInput) searchInput.value = "";
    currentFilter = "all";
    const chipsContainer = document.getElementById("incidentStatusChips");
    if (chipsContainer) {
        chipsContainer.querySelectorAll(".status-chip").forEach((chip) => {
            chip.classList.toggle("active", chip.getAttribute("data-status") === "all");
        });
    }
    applyFilters();
}

window.addEventListener("DOMContentLoaded", async () => {
    initStatusChips();

    // Lê parâmetros de URL caso venha do dashboard (ex.: ?status=open ou ?status=closed)
    const urlParams = new URLSearchParams(window.location.search);
    const initialStatus = urlParams.get("status");
    if (initialStatus && ["all", "open", "closed"].includes(initialStatus)) {
        currentFilter = initialStatus;
        const chipsContainer = document.getElementById("incidentStatusChips");
        if (chipsContainer) {
            chipsContainer.querySelectorAll(".status-chip").forEach((chip) => {
                chip.classList.toggle("active", chip.getAttribute("data-status") === initialStatus);
            });
        }
    }

    const searchInput = document.getElementById("incidentsSearch");
    if (searchInput) searchInput.addEventListener("input", applyFilters);

    const refreshBtn = document.getElementById("refreshIncidentsBtn");
    if (refreshBtn) {
        refreshBtn.addEventListener("click", () => loadIncidents(false));
    }

    await loadIncidents();

    // Auto-refresh padronizado a cada 10 segundos em segundo plano (se a aba estiver visível)
    setInterval(() => {
        if (!document.hidden) {
            loadIncidents(true);
        }
    }, 10000);
});

/* ==========================================================================
   THEME TOGGLER MANAGER (LIGHT / DARK THEME)
   ========================================================================== */
(function initThemeManager() {
    const themeToggleBtn = document.getElementById("themeToggleBtn");
    
    // Ler o estado atual do tema
    const savedTheme = localStorage.getItem("theme");
    const isDark = savedTheme === "dark";
    
    if (isDark) {
        document.documentElement.classList.add("dark-theme");
        document.body.classList.add("dark-theme");
    }

    // Atualizar o ícone de carregamento inicial
    updateThemeIcon(isDark);
    
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener("click", () => {
            const currentIsDark = document.documentElement.classList.toggle("dark-theme");
            document.body.classList.toggle("dark-theme", currentIsDark);
            localStorage.setItem("theme", currentIsDark ? "dark" : "light");
            updateThemeIcon(currentIsDark);
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
})();
