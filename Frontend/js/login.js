/**
 * NetSpot - Módulo de Login e Primeiro Acesso
 * Isolamento leve para a tela de autenticação, prevenindo o carregamento desnecessário
 * do bundle completo do dashboard NOC (4400+ linhas).
 */
(function () {
    "use strict";

    const API = "/api";
    const token = localStorage.getItem("token");

    // Redireciona para o dashboard se já estiver autenticado
    if (token) {
        window.location.href = "dashboard.html";
        return;
    }

    // ==========================================
    // NOTIFICAÇÕES (TOASTS)
    // ==========================================
    const VALID_TOAST_TYPES = new Set(["info", "success", "warning", "error"]);

    function ensureToastContainer() {
        let container = document.getElementById("toastContainer");
        if (!container) {
            container = document.createElement("div");
            container.id = "toastContainer";
            container.className = "toast-container";
            container.setAttribute("aria-live", "polite");
            document.body.appendChild(container);
        }
        return container;
    }

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

    // ==========================================
    // HELPERS DE BOTÃO
    // ==========================================
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

    // ==========================================
    // ACESSIBILIDADE E GESTÃO DE MODAIS
    // ==========================================
    let lastFocusedElementBeforeModal = null;

    function openAppModal(modalEl) {
        if (!modalEl) return;
        lastFocusedElementBeforeModal = document.activeElement;
        modalEl.classList.remove("hidden");
        modalEl.setAttribute("aria-hidden", "false");

        const focusable = modalEl.querySelector("input:not([disabled]), select:not([disabled]), textarea:not([disabled]), button:not([disabled]), [tabindex]:not([tabindex='-1'])");
        if (focusable) {
            setTimeout(() => {
                try { focusable.focus(); } catch (_) {}
            }, 50);
        }
    }

    function closeAppModal(modalEl) {
        if (!modalEl) return;
        modalEl.classList.add("hidden");
        modalEl.setAttribute("aria-hidden", "true");
        if (lastFocusedElementBeforeModal && typeof lastFocusedElementBeforeModal.focus === "function") {
            try { lastFocusedElementBeforeModal.focus(); } catch (_) {}
        }
    }

    window.closeAppModal = closeAppModal;

    // Fechamento de modal com Escape e aprisionamento de foco (Focus Trap)
    window.addEventListener("keydown", (event) => {
        const activeModal = document.querySelector(".modal:not(.hidden)");
        if (!activeModal) return;

        if (event.key === "Escape") {
            event.preventDefault();
            closeAppModal(activeModal);
            return;
        }

        if (event.key === "Tab") {
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

    // ==========================================
    // ALTERNADOR DE VISIBILIDADE DE SENHA
    // ==========================================
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
    window.togglePasswordVisibility = togglePasswordVisibility;

    // ==========================================
    // TEMA (CLARO / ESCURO)
    // ==========================================
    (function initThemeManager() {
        const themeToggleBtn = document.getElementById("themeToggleBtn");
        const savedTheme = localStorage.getItem("theme");
        const isDark = savedTheme === "dark";

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
            if (themeToggleBtn) {
                themeToggleBtn.setAttribute("aria-pressed", isDarkState ? "true" : "false");
            }
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

    // ==========================================
    // SUBMISSÃO DE LOGIN
    // ==========================================
    const loginForm = document.getElementById("loginForm");
    if (loginForm) {
        loginForm.onsubmit = async function (e) {
            e.preventDefault();
            const userVal = (document.getElementById("username")?.value || "").trim();
            const passVal = document.getElementById("password")?.value || "";
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
                    body: JSON.stringify({ username: userVal, password: passVal }),
                });

                const data = await response.json().catch(() => ({}));

                if (response.ok && data.access_token) {
                    localStorage.setItem("token", data.access_token);
                    localStorage.setItem("username", userVal);

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

    // ==========================================
    // TROCA DE SENHA OBRIGATÓRIA (PRIMEIRO ACESSO)
    // ==========================================
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

        const activeToken = localStorage.getItem("token");

        try {
            const res = await fetch(`${API}/auth/first-password`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + activeToken,
                },
                body: JSON.stringify({
                    new_password: newPwd,
                }),
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
    window.submitChangePassword = submitChangePassword;

    // Submissão ao pressionar Enter dentro do modal de troca de senha
    const pwdModalEl = document.getElementById("pwdModal");
    if (pwdModalEl) {
        pwdModalEl.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && e.target.tagName === "INPUT") {
                e.preventDefault();
                submitChangePassword();
            }
        });
    }
})();
