"""
Benchmark ultra-rápido do modelo ML para os datasets de 400, 220.000 e 10.000.000 amostras.
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
        sample.latency_ms, sample.packet_loss_pct, sample.jitter_ms,
        sample.cpu_usage_pct, sample.ram_usage_pct, sample.disk_usage_pct,
        sample.network_in_bps, sample.network_out_bps, float(sample.http_status_code),
        sample.http_response_time_ms, 1.0 if sample.tcp_port_open else 0.0,
        float(sample.active_connections)
    ]

def get_data(count_per_sc):
    X, y = [], []
    for sc in scenarios:
        batch = anomaly_simulator.generate_batch(scenario=sc, count=count_per_sc)
        for s in batch:
            X.append(extract_features(s))
            y.append(sc)
    return np.array(X, dtype=np.float32), np.array(y)

print("📦 Gerando conjunto de teste independente (10.000 amostras)...")
X_test, y_test = get_data(1000)

# 1. TESTE 400 AMOSTRAS
print("\n⚡ Avaliando Dataset de 400 Amostras...")
X_400, y_400 = get_data(40)
t0 = time.time()
rf_400 = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
rf_400.fit(X_400, y_400)
t_400 = time.time() - t0
p_400 = rf_400.predict(X_test)
acc_400 = accuracy_score(y_test, p_400)
pr_400, rec_400, f1_400, _ = precision_recall_fscore_support(y_test, p_400, average='macro')

# 2. TESTE 220.000 AMOSTRAS
print("⚡ Avaliando Dataset de 220.000 Amostras...")
X_220k, y_220k = get_data(22000)
t0 = time.time()
rf_220k = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
rf_220k.fit(X_220k, y_220k)
t_220k = time.time() - t0
p_220k = rf_220k.predict(X_test)
acc_220k = accuracy_score(y_test, p_220k)
pr_220k, rec_220k, f1_220k, _ = precision_recall_fscore_support(y_test, p_220k, average='macro')

# 3. TESTE 10.000.000 AMOSTRAS (10 MILHÕES VIA SGD ONLINE)
print("⚡ Treinando Dataset de 10.000.000 Amostras (10 Milhões)...")
t0 = time.time()
sgd_10m = SGDClassifier(loss='log_loss', max_iter=10, random_state=42, n_jobs=-1)
classes_arr = np.array(scenarios)
for i in range(10):
    X_b, y_b = get_data(100000)
    if i == 0:
        sgd_10m.partial_fit(X_b, y_b, classes=classes_arr)
    else:
        sgd_10m.partial_fit(X_b, y_b)
t_10m = time.time() - t0
p_10m = sgd_10m.predict(X_test)
acc_10m = accuracy_score(y_test, p_10m)
pr_10m, rec_10m, f1_10m, _ = precision_recall_fscore_support(y_test, p_10m, average='macro')

print("\n" + "=" * 95)
print("🏆 TABELA COMPARATIVA DE DESEMPENHO E MÉTRICAS DOS MODELOS ML")
print("=" * 95)
print(f"{'Tamanho do Dataset':<35} | {'Treino (s)':<10} | {'Acurácia':<10} | {'Precisão':<10} | {'Recall':<10} | {'F1-Score':<10}")
print("-" * 95)
print(f"{'400 Amostras (Pequeno)':<35} | {t_400:<10.4f} | {acc_400*100:<9.2f}% | {pr_400*100:<9.2f}% | {rec_400*100:<9.2f}% | {f1_400*100:<9.2f}%")
print(f"{'220.000 Amostras (Médio / Produção)':<35} | {t_220k:<10.4f} | {acc_220k*100:<9.2f}% | {pr_220k*100:<9.2f}% | {rec_220k*100:<9.2f}% | {f1_220k*100:<9.2f}%")
print(f"{'10.000.000 Amostras (10 Milhões)':<35} | {t_10m:<10.4f} | {acc_10m*100:<9.2f}% | {pr_10m*100:<9.2f}% | {rec_10m*100:<9.2f}% | {f1_10m*100:<9.2f}%")
print("=" * 95)
