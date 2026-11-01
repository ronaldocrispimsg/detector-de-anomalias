/**
 * NetSpot - Tema compartilhado dos gráficos (Fase 0/1 do plano visual).
 * Fonte única de: gradientes, estilo de linha, faixas de limiar e mini cards de resumo.
 * Depende de Chart.js (js/vendor/chart.umd.min.js, v4.4.7) carregado antes.
 */
(function () {
    "use strict";

    function hexToRgba(hex, alpha) {
        const m = /^#?([0-9a-f]{6})$/i.exec(String(hex || "").trim());
        if (!m) return `rgba(100,116,139,${alpha})`;
        const n = parseInt(m[1], 16);
        return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${alpha})`;
    }

    // Preenchimento em degradê vertical (função "scriptable" do Chart.js).
    function gradientFill(hex, topAlpha = 0.32, bottomAlpha = 0.02) {
        return (context) => {
            const chart = context.chart;
            const area = chart.chartArea;
            if (!area) return hexToRgba(hex, topAlpha);
            const g = chart.ctx.createLinearGradient(0, area.top, 0, area.bottom);
            g.addColorStop(0, hexToRgba(hex, topAlpha));
            g.addColorStop(1, hexToRgba(hex, bottomAlpha));
            return g;
        };
    }

    // Estilo padrão de série: linha fina, sem pontos (só no hover) e área em degradê.
    function lineStyle(color, { fill = true, yAxisID } = {}) {
        const style = {
            borderColor: color,
            backgroundColor: fill ? gradientFill(color) : hexToRgba(color, 0.15),
            borderWidth: 2,
            fill,
            tension: 0.35,
            cubicInterpolationMode: "monotone",
            pointRadius: 0,
            pointHoverRadius: 4,
            pointHoverBorderWidth: 2,
            pointHoverBackgroundColor: "#ffffff",
            pointHitRadius: 10,
            spanGaps: true,
        };
        if (yAxisID) style.yAxisID = yAxisID;
        return style;
    }

    // Plugin: faixas de limiar no fundo (ex.: 80-95% atenção, 95-100% crítico).
    // Uso: options.plugins.thresholdBands = { axis: "y", bands: [{from, to, color}] }
    const thresholdBandsPlugin = {
        id: "thresholdBands",
        beforeDatasetsDraw(chart, _args, opts) {
            if (!opts || !Array.isArray(opts.bands) || !chart.chartArea) return;
            const scale = chart.scales[opts.axis || "y"];
            if (!scale) return;
            const { ctx, chartArea } = chart;
            ctx.save();
            for (const band of opts.bands) {
                const top = scale.getPixelForValue(Math.min(band.to, scale.max));
                const bottom = scale.getPixelForValue(Math.max(band.from, scale.min));
                if (!(bottom > top)) continue;
                ctx.fillStyle = band.color;
                ctx.fillRect(chartArea.left, top, chartArea.right - chartArea.left, bottom - top);
            }
            ctx.restore();
        },
    };

    function thresholdBands(axis, bands) {
        return { axis, bands };
    }

    const percentBands = (warn = 80, crit = 95) => [
        { from: warn, to: crit, color: "rgba(249,171,0,0.10)" },
        { from: crit, to: 100, color: "rgba(217,48,37,0.12)" },
    ];

    function summarize(values) {
        const nums = (values || [])
            .filter((v) => v !== null && v !== undefined && v !== "")
            .map(Number)
            .filter((v) => Number.isFinite(v));
        if (!nums.length) return null;
        const sum = nums.reduce((a, b) => a + b, 0);
        return {
            last: nums[nums.length - 1],
            avg: sum / nums.length,
            min: Math.min(...nums),
            max: Math.max(...nums),
        };
    }

    // Garante um wrapper ao redor do canvas, para que o resumo fique acima sem
    // alterar o tamanho que o Chart.js enxerga.
    function ensureCanvasWrap(canvas) {
        const parent = canvas.parentElement;
        if (parent && parent.classList.contains("chart-canvas-wrap")) return parent;
        const wrap = document.createElement("div");
        wrap.className = "chart-canvas-wrap";
        parent.insertBefore(wrap, canvas);
        wrap.appendChild(canvas);
        return wrap;
    }

    // Mini cards: atual / média / máximo (por série). items: [{label, color, values, fmt}]
    function renderSummary(canvas, items) {
        if (!canvas) return;
        const wrap = ensureCanvasWrap(canvas);
        const box = wrap.parentElement;
        let el = box.querySelector(":scope > .chart-summary");
        if (!el) {
            el = document.createElement("div");
            el.className = "chart-summary";
            box.insertBefore(el, wrap);
        }
        el.textContent = "";
        for (const item of items) {
            const s = summarize(item.values);
            if (!s) continue;
            const fmt = item.fmt || ((v) => v.toFixed(1));
            const chip = document.createElement("div");
            chip.className = "chart-summary-chip";
            chip.style.setProperty("--chip-color", item.color);

            const name = document.createElement("span");
            name.className = "chart-summary-label";
            name.textContent = item.label;

            const now = document.createElement("strong");
            now.className = "chart-summary-value";
            now.textContent = fmt(s.last);

            const detail = document.createElement("small");
            detail.className = "chart-summary-detail";
            detail.textContent = `méd ${fmt(s.avg)} · máx ${fmt(s.max)}`;

            chip.append(name, now, detail);
            el.appendChild(chip);
        }
        el.classList.toggle("hidden", !el.children.length);
    }

    if (window.Chart) {
        window.Chart.register(thresholdBandsPlugin);
        window.Chart.defaults.font.family = "'Open Sans', 'Roboto', sans-serif";
    }

    window.NetSpotChartTheme = {
        hexToRgba,
        gradientFill,
        lineStyle,
        thresholdBands,
        percentBands,
        renderSummary,
        summarize,
    };
})();
