"""Gera o relatório HTML final a partir dos artefatos de experimento e do plano.

Uso:
    .venv/bin/python scripts/make_report_html.py
    make repro-report

Lê `Backend/harness/results/` e escreve `Backend/harness/results/report.html` com a
estrutura de um artigo curto para leitor externo: objetivos, metodologia, o que foi
construído, resultados com figuras, conclusão e trabalhos futuros. As frentes de
trabalho aparecem pelo que cobrem, sem numeração de fases.
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "Backend" / "harness" / "results"

# Frentes de trabalho do projeto, na ordem em que o relatório as apresenta.
WORKSTREAMS: dict[str, dict[str, str]] = {
    "00": {
        "name": "Infraestrutura de experimentos",
        "covers": "Configurações versionadas, sementes fixas, métricas com intervalo "
        "de confiança e reprodução determinística em um comando.",
    },
    "01": {
        "name": "Dados e divisões sem vazamento",
        "covers": "Treino, validação e teste em faixas de severidade separadas, com "
        "teste automático contra vazamento.",
    },
    "02": {
        "name": "Baselines com incerteza",
        "covers": "Heurística, Random Forest, gradient boosting, regressão logística "
        "e Isolation Forest no mesmo conjunto de teste.",
    },
    "03": {
        "name": "Agente de linguagem estruturado",
        "covers": "Saída em JSON validada por schema, prompt versionado e abstenção; "
        "medição com modelo local e alvo maior em GPU.",
    },
    "04": {
        "name": "Memória RAG sem vazamento",
        "covers": "Busca por similaridade em perfis anonimizados; ablação com e sem "
        "a memória e teste de McNemar.",
    },
    "05": {
        "name": "Ajuste fino LoRA e QLoRA",
        "covers": "Pares de treino supervisionado, configuração com guarda e "
        "comparativo entre modelos; treino real pendente de GPU.",
    },
    "06": {
        "name": "Decisão calibrada e mitigação",
        "covers": "Calibração de temperatura, combinação ponderada dos motores, "
        "abstenção por cobertura e ciclo fechado com reversão.",
    },
    "07": {
        "name": "Explicabilidade das justificativas",
        "covers": "Importância de atributos, conferência das evidências contra a "
        "telemetria e rubrica de qualidade.",
    },
    "08": {
        "name": "Reprodução e relatório",
        "covers": "Execução determinística, manifesto com hashes e relatório com "
        "figuras.",
    },
    "09": {
        "name": "Agente autônomo",
        "covers": "Catálogo de ações, planejamento e ciclo de aplicar, medir e "
        "manter ou reverter.",
    },
    "10": {
        "name": "Laboratório Kathará",
        "covers": "Ataques e falhas injetados em containers reais, coleta na vítima "
        "e mitigação de ponta a ponta.",
    },
    "11": {
        "name": "Antialucinação e verificação",
        "covers": "Schema estrito com retentativa, verificação de evidências, "
        "veredito independente e catálogo fechado de ações.",
    },
    "12": {
        "name": "Reprodução por anomalia",
        "covers": "Dez anomalias com semente fixa, artefatos por anomalia e este "
        "relatório.",
    },
    "13": {
        "name": "Conjuntos externos",
        "covers": "Transferência para UNSW-NB15 e CSE-CIC-IDS2018, com mapa de "
        "rótulos e preenchimento documentado de valores ausentes.",
    },
}

ENGINE_LABELS = {
    "majority": "Classe majoritária",
    "heuristic": "Heurística",
    "random_forest": "Random Forest",
    "hist_gradient_boosting": "Gradient boosting",
    "logistic_regression": "Regressão logística",
    "isolation_forest": "Isolation Forest",
}

SCENARIO_LABELS = {
    "NORMAL": "Operação normal",
    "DDOS_ATTACK": "Ataque DDoS",
    "PORT_SCAN": "Varredura de portas",
    "HOST_DOWN": "Host inacessível",
    "MEMORY_LEAK": "Vazamento de memória",
    "DATA_EXFILTRATION": "Exfiltração de dados",
    "DISK_EXHAUSTION": "Disco esgotado",
    "SERVICE_OUTAGE": "Falha de aplicação",
    "COMBINED_FAULT": "Falha combinada",
    "NETWORK_CONGESTION": "Congestionamento de rede",
}

VERDICT_LABELS = {
    "mitigated": "mitigada",
    "reverted": "revertida",
    "unverified": "não verificada",
    "noop": "sem ação",
}


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _read_jsonl(path: Path) -> list[Any]:
    rows = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return rows
    for line in text.splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _engine_label(name: Any) -> str:
    return ENGINE_LABELS.get(str(name), str(name))


def _scenario_label(name: Any) -> str:
    return SCENARIO_LABELS.get(str(name), str(name))


def _workstreams_table() -> str:
    rows = "".join(
        f"<tr><td>{html.escape(entry['name'])}</td>"
        f"<td>{html.escape(entry['covers'])}</td></tr>"
        for entry in WORKSTREAMS.values()
    )
    return (
        "<table><thead><tr><th>Frente de trabalho</th><th>O que cobre</th>"
        f"</tr></thead><tbody>{rows}</tbody></table>"
    )


def _baselines_table(rows: list[Any]) -> str:
    if not rows:
        return "<p class='muted'>sem baselines registrados</p>"
    body = ""
    for row in sorted(rows, key=lambda r: r.get("macro_f1", 0.0), reverse=True):
        ci = row.get("macro_f1_ci", {})
        ci_txt = f"{ci.get('lo', 0):.3f}–{ci.get('hi', 0):.3f}" if ci else "—"
        body += (
            f"<tr><td>{html.escape(_engine_label(row.get('engine')))}</td>"
            f"<td>{row.get('macro_f1', 0.0):.3f}</td><td>{ci_txt}</td>"
            f"<td>{row.get('accuracy', 0.0):.3f}</td></tr>"
        )
    return (
        "<table><thead><tr><th>Motor</th><th>macro-F1</th><th>IC 95%</th>"
        f"<th>Acurácia</th></tr></thead><tbody>{body}</tbody></table>"
    )


def _rag_section(rows: list[Any]) -> str:
    if not rows:
        return "<p class='muted'>sem ablação da memória RAG</p>"
    row = rows[0]
    off = row.get("without_rag", {})
    on = row.get("with_rag", {})
    mc = row.get("mcnemar", {})
    pval = mc.get("pvalue")
    p_txt = "—"
    if pval is not None:
        try:
            p_txt = f"{float(pval):.3f}"
        except (TypeError, ValueError):
            p_txt = str(pval)
    precision = row.get("retrieval_precision")
    precision_txt = f"{float(precision):.2f}" if precision is not None else "—"
    return (
        f"<p>Precisão da recuperação: {precision_txt}. Amostras: {row.get('n')}.</p>"
        "<table><thead><tr><th>Condição</th><th>macro-F1</th></tr></thead><tbody>"
        f"<tr><td>sem a memória</td><td>{off.get('macro_f1', 0):.3f}</td></tr>"
        f"<tr><td>com a memória</td><td>{on.get('macro_f1', 0):.3f}</td></tr>"
        "</tbody></table>"
        f"<p class='muted'>Teste de McNemar pareado: p = {p_txt}.</p>"
    )


def _calibration_section(data: Any) -> str:
    if not data:
        return "<p class='muted'>sem calibração registrada</p>"
    body = "".join(
        f"<tr><td>{html.escape(_engine_label(e.get('engine')))}</td>"
        f"<td>{e.get('ece_before', 0):.3f}</td><td>{e.get('ece_after', 0):.3f}</td>"
        f"<td>{e.get('temperature', 0):.3f}</td></tr>"
        for e in data.get("per_engine", [])
    )
    return (
        "<table><thead><tr><th>Motor</th><th>ECE antes</th><th>ECE depois</th>"
        f"<th>Temperatura</th></tr></thead><tbody>{body}</tbody></table>"
    )


def _xai_section(rows: list[Any]) -> str:
    rows = [r for r in rows if r.get("label")]
    if not rows:
        return "<p class='muted'>sem relatório de explicabilidade</p>"
    body = "".join(
        f"<tr><td>{html.escape(_scenario_label(r.get('label')))}</td>"
        f"<td>{r.get('n', 0)}</td>"
        f"<td>{r.get('mean_rubric', 0):.2f}</td>"
        f"<td>{r.get('evidence_agreement', 0) * 100:.0f}%</td></tr>"
        for r in rows
    )
    return (
        "<table><thead><tr><th>Cenário</th><th>n</th><th>Rubrica (0 a 3)</th>"
        f"<th>Evidências conferidas</th></tr></thead><tbody>{body}</tbody></table>"
    )


def _kathara_rows(results_dir: Path) -> list[dict[str, Any]]:
    from Backend.harness.kathara.repro_anomaly import verdict_from

    rows: dict[str, dict[str, Any]] = {}
    kathara_dir = results_dir / "kathara"
    if not kathara_dir.exists():
        return []
    for sub in sorted(p for p in kathara_dir.iterdir() if p.is_dir()):
        data = _read_json(sub / "before_after.json")
        if data:
            data = dict(data)
            data["verdict"] = verdict_from(
                data.get("outcome", data.get("verdict", "")),
                data.get("before"),
                data.get("after"),
            )
            rows[str(data.get("scenario", sub.name))] = data
    for path in sorted(kathara_dir.glob("*.json")):
        data = _read_json(path)
        if isinstance(data, dict) and "outcome" in data and "metric_before" in data:
            scenario = str(data.get("scenario", path.stem))
            rows.setdefault(
                scenario,
                {
                    "scenario": scenario,
                    "metric": data.get("metric"),
                    "before": data.get("metric_before"),
                    "after": data.get("metric_after"),
                    "verdict": verdict_from(
                        data.get("outcome", ""),
                        data.get("metric_before"),
                        data.get("metric_after"),
                    ),
                    "trajectory_hash": data.get("trajectory_hash"),
                },
            )
    return [rows[key] for key in sorted(rows)]


def _kathara_section(results_dir: Path) -> str:
    rows = _kathara_rows(results_dir)
    if not rows:
        return "<p class='muted'>sem execuções no laboratório Kathará</p>"
    body = ""
    for row in rows:
        before = row.get("before")
        after = row.get("after")
        fmt = lambda v: "—" if v is None else f"{v:,.0f}"
        raw_verdict = str(row.get("verdict", ""))
        verdict = VERDICT_LABELS.get(raw_verdict, raw_verdict or "—")
        cls = "ok" if raw_verdict == "mitigated" else "warn"
        body += (
            f"<tr><td>{html.escape(_scenario_label(row.get('scenario')))}</td>"
            f"<td>{html.escape(str(row.get('metric') or '—'))}</td>"
            f"<td>{fmt(before)}</td><td>{fmt(after)}</td>"
            f"<td class='{cls}'>{html.escape(verdict)}</td>"
            f"<td class='mono'>{html.escape(str(row.get('trajectory_hash', ''))[:12])}</td></tr>"
        )
    return (
        "<table><thead><tr><th>Anomalia</th><th>Métrica</th><th>Antes</th><th>Depois</th>"
        f"<th>Veredito</th><th>Trajetória</th></tr></thead><tbody>{body}</tbody></table>"
    )


_STYLE = """
:root { color-scheme: light dark; }
body { font-family: -apple-system, system-ui, sans-serif; margin: 0; padding: 2rem;
       line-height: 1.5; max-width: 1100px; margin-inline: auto; }
h1 { font-size: 1.6rem; } h2 { margin-top: 2.2rem; font-size: 1.25rem; }
h3 { margin-top: 1.6rem; font-size: 1.05rem; }
table { border-collapse: collapse; width: 100%; margin: .6rem 0 1.2rem; font-size: .92rem; }
th, td { border: 1px solid #8884; padding: .4rem .6rem; text-align: left; }
th { background: #8881; }
.muted { opacity: .65; } .mono { font-family: ui-monospace, monospace; font-size: .85rem; }
.figure { margin: 1rem 0 1.4rem; }
.figure img { max-width: 100%; height: auto; border: 1px solid #8884; border-radius: 6px; }
.figure figcaption { font-size: .85rem; opacity: .65; margin-top: .3rem; }
.ok { color: #15803d; font-weight: 600; } .warn { color: #b45309; font-weight: 600; }
"""

_QUESTIONS = [
    "Um modelo de linguagem open source é competitivo com métodos clássicos em "
    "dados que ele não viu no treino?",
    "O ajuste fino com LoRA e QLoRA melhora sobre a versão sem treino, e em quanto?",
    "A memória de casos agrega robustez sem vazar o rótulo do cenário?",
    "As saídas são calibradas, auditáveis e as justificativas fiéis à telemetria?",
]


def _figure(results_dir: Path, name: str, caption: str) -> str:
    if not (results_dir / name).exists():
        return ""
    return (
        f"<figure class='figure'><img src='{html.escape(name)}' "
        f"alt='{html.escape(caption)}'><figcaption>{html.escape(caption)}"
        "</figcaption></figure>"
    )


def build_report_html(results_dir: Path) -> str:
    baselines = _read_jsonl(results_dir / "baselines.jsonl")
    rag = _read_jsonl(results_dir / "rag_ablation.jsonl")
    calibration = _read_json(results_dir / "decision_calibration.json")
    xai = _read_jsonl(results_dir / "xai_report.jsonl")

    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NetSpot: classificação de anomalias de rede com modelos clássicos e LLMs open source</title>
<style>{_STYLE}</style></head><body>
<h1>NetSpot: classificação de anomalias de rede com modelos clássicos e LLMs open source</h1>
<p>O NetSpot monitora hosts por ICMP, TCP, HTTP/DNS e SNMP e classifica uma amostra
de telemetria em dez cenários de operação e falha, com justificativa e plano de
mitigação. O protótipo original media a si mesmo: treino e teste saíam do mesmo
simulador, o motor generativo lia o rótulo e o índice de recuperação guardava o
nome do cenário. Esta avaliação reconstrói o pipeline para medir generalização
sobre dados não vistos. Os artefatos brutos ficam em
<code>Backend/harness/results/</code>.</p>

<h2>Objetivos</h2>
<p>Quatro perguntas guiam o trabalho.</p>
<ol>{"".join(f"<li>{html.escape(q)}</li>" for q in _QUESTIONS)}</ol>

<h2>Metodologia</h2>
<p>O simulador gera telemetria para os dez cenários com faixas de severidade
separadas entre treino, validação e teste. O treino usa anomalias claras e o
teste usa anomalias sutis, o que mede generalização em vez de memorização. O CSV
real entra por divisão temporal, UNSW-NB15 e CSE-CIC-IDS2018 entram como holdout
externo e os cenários do laboratório Kathará servem de execução em rede emulada.
Um teste automático falha se o rótulo aparecer na entrada, na consulta de
recuperação ou no índice.</p>
<p>No mesmo conjunto de teste rodam heurística de NOC, Random Forest, gradient
boosting, regressão logística, Isolation Forest, agente de linguagem sem e com
exemplos, memória de casos, ajuste fino LoRA/QLoRA e combinação calibrada com
abstenção. Nenhum resultado de modelo de linguagem é reportado sem o baseline
clássico no mesmo split. As métricas são macro-F1, acurácia balanceada, precisão e
recall por classe, matriz de confusão, PR-AUC, erro de calibração esperado, curvas
de cobertura e risco, latência e taxa de JSON inválido. Toda métrica vem com
intervalo de confiança bootstrap de 95%, e a comparação entre motores usa McNemar
com correção de Holm-Bonferroni. A mitigação roda em ciclo fechado: o agente
escolhe ações de um catálogo fechado, simula antes de aplicar, mede o efeito na
vítima, reverte quando não há melhora e registra a trajetória com hash.</p>

<h3>O que foi construído</h3>
{_workstreams_table()}

<h2>Resultados e discussão</h2>

<h3>Baselines com incerteza</h3>
<p>Motores clássicos e heurística no mesmo conjunto de teste, com intervalo de
confiança bootstrap de 95%.</p>
{_baselines_table(baselines)}
{_figure(results_dir, "baselines.png", "macro-F1 por motor, com intervalo de confiança de 95%.")}

<h3>Memória de casos (ablação)</h3>
{_rag_section(rag)}

<h3>Calibração da confiança</h3>
<p>Erro de calibração esperado antes e depois do ajuste de temperatura.</p>
{_calibration_section(calibration)}
{_figure(results_dir, "coverage_risk.png", "Cobertura e risco com abstenção no conjunto de teste.")}

<h3>Qualidade das justificativas</h3>
<p>Rubrica de 0 a 3 e fração de evidências que conferem com a telemetria, por
cenário.</p>
{_xai_section(xai)}

<h3>Mitigação em laboratório (Kathar&aacute;)</h3>
<p>Cada anomalia é injetada no laboratório, mitigada pelo agente e medida antes e
depois. A trajetória identifica a execução.</p>
{_kathara_section(results_dir)}

<h2>Conclusão</h2>
<p>O ciclo fechado é o resultado mais sólido. O agente escolhe uma ação, aplica,
mede o efeito e reverte quando não há ganho, e isso foi comprovado em laboratório
real. A detecção clássica ainda ganha do modelo de linguagem pequeno, que erra por
falta de variedade nas respostas e é lento. O sistema está implementado e coberto
por testes, mas falta a evidência com o modelo de 7 bilhões de parâmetros e com os
adaptadores LoRA/QLoRA treinados, o que depende de uma máquina Linux com GPU. Até
lá, os números do agente são os do modelo local pequeno.</p>

<h2>Trabalhos futuros</h2>
<p>Rodar o modelo de 7 bilhões no Linux com GPU e repetir as medições para saber
se a memória de casos passa a ajudar. Treinar os adaptadores LoRA/QLoRA e comparar
com a versão sem treino. Executar por inteiro os conjuntos externos UNSW-NB15 e
CSE-CIC-IDS2018, cujo carregador já está pronto. Ampliar os cenários do
laboratório, que hoje cobrem congestionamento, host inacessível e exfiltração mas
não falhas de enlace. Também está em aberto trocar a ponte Ethernet por um
controlador SDN com OpenFlow.</p>
</body></html>
"""


def main() -> None:
    out = RESULTS / "report.html"
    out.write_text(build_report_html(RESULTS), encoding="utf-8")
    print(f"relatório escrito em {out}")


if __name__ == "__main__":
    main()
