"""Estatística para comparação honesta de motores.

Intervalos de confiança bootstrap, teste de McNemar pareado e correção de
Holm-Bonferroni. Tudo com seed fixa para ser reproduzível.
"""

from __future__ import annotations

from typing import Callable, Sequence

import numpy as np
from scipy import stats


def bootstrap_ci_values(
    values: Sequence[float],
    stat_fn: Callable[[np.ndarray], float] = np.mean,
    n_boot: int = 1000,
    alpha: float = 0.05,
    seed: int = 0,
) -> dict[str, float]:
    values = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    n = len(values)
    stats_boot = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, n, size=n)
        stats_boot[b] = stat_fn(values[idx])
    lo, hi = np.percentile(stats_boot, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {"point": float(stat_fn(values)), "lo": float(lo), "hi": float(hi)}


def bootstrap_ci_metric(
    y_true: Sequence[object],
    y_pred: Sequence[object],
    metric_fn: Callable[[Sequence[object], Sequence[object]], float],
    n_boot: int = 1000,
    alpha: float = 0.05,
    seed: int = 0,
) -> dict[str, float]:
    y_true = np.asarray(y_true, dtype=object)
    y_pred = np.asarray(y_pred, dtype=object)
    rng = np.random.default_rng(seed)
    n = len(y_true)
    stats_boot = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, n, size=n)
        stats_boot[b] = metric_fn(y_true[idx], y_pred[idx])
    lo, hi = np.percentile(stats_boot, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {"point": float(metric_fn(y_true, y_pred)), "lo": float(lo), "hi": float(hi)}


def mcnemar(
    y_true: Sequence[object],
    pred_a: Sequence[object],
    pred_b: Sequence[object],
    exact_max: int = 25,
) -> dict[str, object]:
    """Teste de McNemar pareado entre dois motores.

    b = A acerta e B erra; c = A erra e B acerta. Usa binom exato quando
    b + c < exact_max, senão chi2 com correção de continuidade.
    """
    y_true = np.asarray(y_true, dtype=object)
    correct_a = np.asarray(pred_a, dtype=object) == y_true
    correct_b = np.asarray(pred_b, dtype=object) == y_true
    b = int(np.sum(correct_a & ~correct_b))
    c = int(np.sum(~correct_a & correct_b))
    n = b + c
    if n == 0:
        return {"b": 0, "c": 0, "statistic": 0.0, "pvalue": 1.0, "method": "none"}
    if n < exact_max:
        result = stats.binomtest(min(b, c), n, 0.5)
        pvalue = min(1.0, float(result.pvalue) * 2)
        return {"b": b, "c": c, "statistic": float(min(b, c)), "pvalue": pvalue, "method": "exact"}
    statistic = (abs(b - c) - 1) ** 2 / n
    pvalue = float(stats.chi2.sf(statistic, df=1))
    return {"b": b, "c": c, "statistic": float(statistic), "pvalue": pvalue, "method": "chi2"}


def holm_bonferroni(pvalues: dict[str, float]) -> dict[str, float]:
    """Corrige múltiplas comparações. Devolve p-valores ajustados por chave."""
    if not pvalues:
        return {}
    items = sorted(pvalues.items(), key=lambda kv: kv[1])
    m = len(items)
    adjusted: dict[str, float] = {}
    running_max = 0.0
    for rank, (key, p) in enumerate(items, start=1):
        value = min(1.0, p * (m - rank + 1))
        running_max = max(running_max, value)
        adjusted[key] = running_max
    return adjusted
