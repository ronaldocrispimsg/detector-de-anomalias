"""
Script de Benchmark e Comparativo de Desempenho do Modelo ML (NetSpot).
Avalia 400 amostras, 220.000 amostras e 10.000.000 amostras com métricas completas de Acurácia, Precisão, Recall e F1-Score.
"""

import time
import os
import gc
import numpy as np
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from sklearn.ensemble import RandomForestClassifier, IsolationForest, HistGradientBoostingClassifier

from Backend.services.anomaly_simulator import anomaly_simulator, SCENARIOS_META

scenarios = [s for s in SCENARIOS_META.keys() if s != 'CUSTOM']
feature_names = [
    "latency_ms", "packet_loss_pct", "jitter_ms",
    "cpu_usage_pct", "ram_usage_pct", "disk_usage_pct",
    "network_in_bps", "network_out_bps", "http_status_code",
    "http_response_time_ms", "tcp_port_open", "active_connections"
]

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

def evaluate_dataset_scale(samples_per_scenario: int, name: str, use_hist_gb: bool = False):
    print(f"\n==================================================")
    print(f"🚀 INICIANDO BENCHMARK DO DATASET DE {name} ({samples_per_scenario * len(scenarios):,} amostras)")
    print(f"==================================================")
    
    # 1. Geração do Dataset
    t0 = time.time()
    X_train, y_train = [], []
    for sc in scenarios:
        batch = anomaly_simulator.generate_batch(scenario=sc, count=samples_per_scenario)
        for s in batch:
            X_train.append(extract_features(s))
            y_train.append(sc)
            
    X_arr = np.array(X_train, dtype=np.float32)
    y_arr = np.array(y_train)
    t_gen = time.time() - t0
    print(f"🟢 Geração de {len(X_arr):,} amostras sintéticas concluída em {t_gen:.2f}s")
    
    # 2. Geração de Test Set Independente (1.000 amostras por classe = 10.000 amostras)
    X_test, y_test = [], []
    for sc in scenarios:
        batch = anomaly_simulator.generate_batch(scenario=sc, count=1000)
        for s in batch:
            X_test.append(extract_features(s))
            y_test.append(sc)
    X_test_arr = np.array(X_test, dtype=np.float32)
    y_test_arr = np.array(y_test)
    
    # 3. Treinamento do Modelo
    t0_train = time.time()
    if use_hist_gb:
        model = HistGradientBoostingClassifier(max_iter=100, random_state=42)
    else:
        model = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
        
    model.fit(X_arr, y_arr)
    t_train = time.time() - t0_train
    print(f"⚡ Treinamento do Modelo ML concluído em {t_train:.2f}s")
    
    # 4. Avaliação e Predição
    t0_eval = time.time()
    y_pred = model.predict(X_test_arr)
    t_eval = time.time() - t0_eval
    
    acc = accuracy_score(y_test_arr, y_pred)
    prec, rec, f1, _ = precision_recall_fscore_support(y_test_arr, y_pred, average='macro')
    
    print(f"\n📊 RESULTADOS DAS MÉTRICAS ({name}):")
    print(f"   • Total Amostras Treino: {len(X_arr):,}")
    print(f"   • Total Amostras Teste:  {len(X_test_arr):,}")
    print(f"   • Tempo Treinamento:     {t_train:.4f} s")
    print(f"   • Tempo Predição Teste:  {t_eval:.4f} s")
    print(f"   🎯 ACURÁCIA (Accuracy):   {acc * 100:.2f}%")
    print(f"   🎯 PRECISÃO (Precision):  {prec * 100:.2f}%")
    print(f"   🎯 RECALL (Sensibilidade):{rec * 100:.2f}%")
    print(f"   🎯 F1-SCORE (Macro):     {f1 * 100:.2f}%")
    
    del X_arr, y_arr, X_train, y_train
    gc.collect()
    
    return {
        "scale_name": name,
        "train_samples": len(X_test),
        "total_train_samples": samples_per_scenario * len(scenarios),
        "train_time_sec": round(t_train, 4),
        "eval_time_sec": round(t_eval, 4),
        "accuracy": round(acc, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1_score": round(f1, 4)
    }

if __name__ == "__main__":
    res_400 = evaluate_dataset_scale(40, "400 Amostras (Pequeno)")
    res_220k = evaluate_dataset_scale(20000, "220.000 Amostras (Médio)")
    res_10m = evaluate_dataset_scale(1000000, "10.000.000 Amostras (Giga Dataset / HistGB)", use_hist_gb=True)
    
    print("\n\n==================================================")
    print("🏆 RESUMO COMPARATIVO FINAL DAS MÉTRICAS DOS 3 DATASETS")
    print("==================================================")
    print(f"{'Dataset Scale':<30} | {'Treino (s)':<10} | {'Acurácia':<10} | {'Precisão':<10} | {'Recall':<10} | {'F1-Score':<10}")
    print("-" * 95)
    for r in [res_400, res_220k, res_10m]:
        print(f"{r['scale_name']:<30} | {r['train_time_sec']:<10.2f} | {r['accuracy']*100:<9.2f}% | {r['precision']*100:<9.2f}% | {r['recall']*100:<9.2f}% | {r['f1_score']*100:<9.2f}%")
