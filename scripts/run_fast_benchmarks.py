"""
Script de Benchmark de Alta Performance para Avaliar 400, 220.000 e 10.000.000 Amostras.
Calcula Acurácia, Precisão, Sensibilidade (Recall) e F1-Score em Português sem fórmulas LaTeX.
"""

import time
import numpy as np
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import SGDClassifier

from Backend.services.anomaly_simulator import anomaly_simulator, SCENARIOS_META

scenarios = [s for s in SCENARIOS_META.keys() if s != 'CUSTOM']

def extract_features(sample):
    return [
        sample.latency_ms,
        sample.packet_loss_pct,
        sample.jitter_ms,
        sample.cpu_usage_pct,
        sample.ram_usage_pct,
        sample.disk_usage_pct,
        sample.network_in_bps,
        sample.network_out_bps,
        float(sample.http_status_code),
        sample.http_response_time_ms,
        1.0 if sample.tcp_port_open else 0.0,
        float(sample.active_connections)
    ]

def generate_dataset(samples_per_scenario):
    X, y = [], []
    for sc in scenarios:
        batch = anomaly_simulator.generate_batch(scenario=sc, count=samples_per_scenario)
        for s in batch:
            X.append(extract_features(s))
            y.append(sc)
    return np.array(X, dtype=np.float32), np.array(y)

def run_benchmarks():
    print("=" * 70)
    print("⚡ RELATÓRIO DE AVALIAÇÃO DE DESEMPENHO E MÉTRICAS DE MACHINE LEARNING")
    print("=" * 70)

    # Conjunto de Teste Fixo e Independente (10.000 amostras)
    print("\n📦 Gerando Conjunto de Teste Independente (10.000 amostras)...")
    X_test, y_test = generate_dataset(1000)

    results = []

    # ----------------------------------------------------
    # 1. TESTE COM 400 AMOSTRAS
    # ----------------------------------------------------
    print("\n--- [TESTE 1: 400 AMOSTRAS] ---")
    t0_gen = time.time()
    X_train_400, y_train_400 = generate_dataset(40)
    t_gen_400 = time.time() - t0_gen

    t0_tr = time.time()
    rf_400 = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    rf_400.fit(X_train_400, y_train_400)
    t_tr_400 = time.time() - t0_tr

    t0_ev = time.time()
    y_pred_400 = rf_400.predict(X_test)
    t_ev_400 = time.time() - t0_ev

    acc_400 = accuracy_score(y_test, y_pred_400)
    prec_400, rec_400, f1_400, _ = precision_recall_fscore_support(y_test, y_pred_400, average='macro')
    
    results.append({
        "dataset": "400 Amostras (Pequeno)",
        "samples": len(X_train_400),
        "gen_time": t_gen_400,
        "train_time": t_tr_400,
        "eval_time": t_ev_400,
        "accuracy": acc_400,
        "precision": prec_400,
        "recall": rec_400,
        "f1_score": f1_400
    })

    # ----------------------------------------------------
    # 2. TESTE COM 220.000 AMOSTRAS
    # ----------------------------------------------------
    print("\n--- [TESTE 2: 220.000 AMOSTRAS] ---")
    t0_gen = time.time()
    X_train_220k, y_train_220k = generate_dataset(22000)
    t_gen_220k = time.time() - t0_gen

    t0_tr = time.time()
    rf_220k = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    rf_220k.fit(X_train_220k, y_train_220k)
    t_tr_220k = time.time() - t0_tr

    t0_ev = time.time()
    y_pred_220k = rf_220k.predict(X_test)
    t_ev_220k = time.time() - t0_ev

    acc_220k = accuracy_score(y_test, y_pred_220k)
    prec_220k, rec_220k, f1_220k, _ = precision_recall_fscore_support(y_test, y_pred_220k, average='macro')

    results.append({
        "dataset": "220.000 Amostras (Médio / Produção)",
        "samples": len(X_train_220k),
        "gen_time": t_gen_220k,
        "train_time": t_tr_220k,
        "eval_time": t_ev_220k,
        "accuracy": acc_220k,
        "precision": prec_220k,
        "recall": rec_220k,
        "f1_score": f1_220k
    })

    # ----------------------------------------------------
    # 3. TESTE E TREINAMENTO COM 10.000.000 AMOSTRAS (10 MILHÕES)
    # ----------------------------------------------------
    print("\n--- [TESTE 3: 10.000.000 AMOSTRAS (10 MILHÕES VIA SGD CLASSIFIER / PARALLEL SGD)] ---")
    t0_gen = time.time()
    
    sgd_10m = SGDClassifier(loss='log_loss', max_iter=20, random_state=42, n_jobs=-1)
    classes_list = np.array(scenarios)
    
    total_10m_samples = 0
    # Treinamento por Batches Incrementais de 1.000.000 amostras (10 épocas/lotes de 1M)
    for batch_num in range(10):
        X_batch, y_batch = generate_dataset(100000) # 1.000.000 por lote
        if batch_num == 0:
            sgd_10m.partial_fit(X_batch, y_batch, classes=classes_list)
        else:
            sgd_10m.partial_fit(X_batch, y_batch)
        total_10m_samples += len(X_batch)
        print(f"   🟢 Lote {batch_num + 1}/10 ({total_10m_samples:,} amostras processadas)...")

    t_tr_10m = time.time() - t0_gen

    t0_ev = time.time()
    y_pred_10m = sgd_10m.predict(X_test)
    t_ev_10m = time.time() - t0_ev

    acc_10m = accuracy_score(y_test, y_pred_10m)
    prec_10m, rec_10m, f1_10m, _ = precision_recall_fscore_support(y_test, y_pred_10m, average='macro')

    results.append({
        "dataset": "10.000.000 Amostras (10 Milhões / Lote Incremental)",
        "samples": total_10m_samples,
        "gen_time": 0.0,
        "train_time": t_tr_10m,
        "eval_time": t_ev_10m,
        "accuracy": acc_10m,
        "precision": prec_10m,
        "recall": rec_10m,
        "f1_score": f1_10m
    })

    # IMPRESSÃO DA TABELA COMPARATIVA FINAL
    print("\n" + "=" * 90)
    print("🏆 TABELA COMPARATIVA FINAL DE MÉTRICAS DOS MODELOS")
    print("=" * 90)
    print(f"{'Tamanho do Dataset':<36} | {'Treino (s)':<10} | {'Acurácia':<10} | {'Precisão':<10} | {'Recall':<10} | {'F1-Score':<10}")
    print("-" * 90)
    for r in results:
        print(f"{r['dataset']:<36} | {r['train_time']:<10.2f} | {r['accuracy']*100:<9.2f}% | {r['precision']*100:<9.2f}% | {r['recall']*100:<9.2f}% | {r['f1_score']*100:<9.2f}%")

if __name__ == "__main__":
    run_benchmarks()
