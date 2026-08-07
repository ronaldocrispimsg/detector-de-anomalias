#!/usr/bin/env python3
"""
Ferramenta CLI de Simulação e Classificação de Anomalias de Sistema do NetSpot.
Permite executar simulações interativas no terminal e comparar os resultados dos 3 motores:
- 📐 Heurística
- 🤖 Machine Learning
- 🧠 IA Generativa Local
"""

import sys
import os
import asyncio
import argparse
from typing import Dict, Any

# Ajustar PYTHONPATH para incluir diretório raiz do NetSpot
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../Backend")))

from Backend.services.anomaly_simulator import anomaly_simulator, SCENARIOS_META, SystemMetricsSample
from Backend.services.anomaly_classifier import anomaly_classifier


def print_banner():
    print("=" * 80)
    print(" 🚀 NETSPOT - SIMULADOR & CLASSIFICADOR INTELIGENTE DE ANOMALIAS DE REDE/SISTEMA")
    print("=" * 80)


def print_sample_table(sample: SystemMetricsSample):
    print(f"\n📊 Telemetria do Sistema Simulada [{sample.scenario}]:")
    print("-" * 60)
    print(f"  • Latência ICMP:         {sample.latency_ms:>7} ms   | Perda Pacotes: {sample.packet_loss_pct:>5}%")
    print(f"  • Jitter:                {sample.jitter_ms:>7} ms   | Conexões:      {sample.active_connections:>5}")
    print(f"  • Uso de CPU:            {sample.cpu_usage_pct:>7}%    | Uso de RAM:    {sample.ram_usage_pct:>5}%")
    print(f"  • Uso de Disco:          {sample.disk_usage_pct:>7}%    | Status HTTP:   {sample.http_status_code:>5}")
    print(f"  • Banda Entrada (Bps):   {round(sample.network_in_bps / 1e6, 2):>7} MB/s | Saída (Bps):  {round(sample.network_out_bps / 1e6, 2):>5} MB/s")
    print(f"  • Resposta HTTP:         {sample.http_response_time_ms:>7} ms   | Porta TCP:     {'ABERTA' if sample.tcp_port_open else 'FECHADA'}")
    print("-" * 60)


async def run_simulation_cli(scenario: str):
    print_banner()
    sample = anomaly_simulator.generate_sample(scenario=scenario)
    print_sample_table(sample)

    print("\n🔍 EXECUTANDO CLASSIFICAÇÃO EM PARALELO NOS 3 MOTORES DE IA/REGRAS...\n")
    res = await anomaly_classifier.classify(sample)

    print("┌" + "─" * 78 + "┐")
    print(f"│ 🎯 VEREDITO FINAL DO ENSEMBLE: {res.final_scenario:<25} | RISCO: {res.risk_level:<8} │")
    print(f"│    Confiança Geral: {res.overall_confidence * 100:.1f}% | Consenso dos Motores: {'SIM' if res.consensus_match else 'DIVERGENTE':<10}      │")
    print("└" + "─" * 78 + "┘")

    # 1. Heurística
    h = res.heuristics
    print("\n📐 [MOTOR 1: HEURÍSTICA BASEADA EM REGRAS]")
    print(f"   • Cenário Detectado: {h.predicted_scenario} (Confiança: {h.confidence * 100:.0f}%, Severidade: {h.severity})")
    if h.triggered_rules:
        print("   • Regras Violadas:")
        for r in h.triggered_rules:
            print(f"     - [{r.rule_name}] Metric: {r.metric}={r.value} (Limiar: {r.threshold}) -> {r.description}")

    # 2. Machine Learning
    ml = res.ml
    print("\n🤖 [MOTOR 2: MACHINE LEARNING (RandomForest + IsolationForest)]")
    print(f"   • Cenário Predito:   {ml.predicted_scenario} (Probabilidade: {ml.confidence * 100:.0f}%)")
    print(f"   • Score de Anomalia: {ml.anomaly_score:.3f} / 1.000 (IsolationForest Score)")
    top_features = sorted(ml.feature_importances.items(), key=lambda x: x[1], reverse=True)[:4]
    print("   • Principais Métricas Determinantes:")
    for feat, imp in top_features:
        print(f"     - {feat:<22}: {imp * 100:.1f}% importância")

    # 3. Local GenAI
    g = res.genai
    print(f"\n🧠 [MOTOR 3: IA GENERATIVA LOCAL - {g.provider}]")
    print(f"   • Cenário LLM:       {g.predicted_scenario}")
    print(f"   • Diagnóstico:       {g.diagnostic_summary}")
    print(f"   • Causa Raiz:        {g.root_cause_analysis}")
    print(f"   • Impacto NOC:       {g.impact_assessment}")
    print("   • Playbook de Mitigação:")
    for i, step in enumerate(g.remediation_playbook, 1):
        print(f"     {i}. {step}")

    print("\n" + "=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Simulador e Classificador de Anomalias NetSpot")
    parser.add_argument(
        "--scenario",
        type=str,
        default="NORMAL",
        choices=list(SCENARIOS_META.keys()),
        help="Cenário de anomalia a simular (Default: NORMAL)"
    )
    args = parser.parse_args()

    asyncio.run(run_simulation_cli(args.scenario))


if __name__ == "__main__":
    main()
