/**
 * Teste da lógica pura do tema dos gráficos (sem navegador).
 * Execução: node scripts/test_chart_theme.js
 */
global.window = { Chart: { register(p) { global.reg = p; }, defaults: { font: {} } } };
global.document = {};
require("../Frontend/js/chart-theme.js");

const assert = require("assert");
const T = window.NetSpotChartTheme;

assert.equal(global.reg.id, "thresholdBands");
assert.equal(T.hexToRgba("#ff0000", 0.5), "rgba(255,0,0,0.5)");

// Pontos sem dado (null/undefined/texto) não podem virar zero nas estatísticas.
const s = T.summarize([10, null, 20, "x", 30]);
assert.deepEqual([s.last, s.avg, s.min, s.max], [30, 20, 10, 30]);
assert.equal(T.summarize([]), null);
assert.equal(T.summarize([null, undefined]), null);

const ls = T.lineStyle("#1e8e3e", { fill: false, yAxisID: "y_bps" });
assert.equal(ls.fill, false);
assert.equal(ls.yAxisID, "y_bps");
assert.equal(ls.pointRadius, 0);
assert.equal(typeof T.lineStyle("#fff").backgroundColor, "function");

// Plugin de faixas: desenha as faixas dentro do eixo e ignora as fora dele.
const calls = [];
const chart = {
    chartArea: { left: 0, right: 100, top: 0, bottom: 100 },
    ctx: { save() {}, restore() {}, fillRect: (...a) => calls.push(a), set fillStyle(v) {} },
    scales: { y: { min: 0, max: 100, getPixelForValue: (v) => 100 - v } },
};
global.reg.beforeDatasetsDraw(chart, {}, T.thresholdBands("y", T.percentBands(80, 95)));
assert.equal(calls.length, 2);
assert.deepEqual(calls[0], [0, 5, 100, 15]);
global.reg.beforeDatasetsDraw(chart, {}, { axis: "y", bands: [{ from: 120, to: 130, color: "x" }] });
assert.equal(calls.length, 2);

console.log("TEMA_OK");
