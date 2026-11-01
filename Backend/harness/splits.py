"""Construção de splits e guarda anti-vazamento.

Os splits de regime usam severidades disjuntas (parâmetros geradores
diferentes), de modo que o teste é um regime não visto no treino. A guarda
`assert_no_leakage` falha se o rótulo virar feature, se um grupo aparecer em
mais de um split, se houver linhas duplicadas entre splits ou se as faixas de
severidade se sobrepuserem.
"""

from __future__ import annotations

import itertools
from typing import Sequence

import numpy as np
from sklearn.model_selection import GroupKFold

from Backend.harness.datasets import (
    DatasetSplit,
    FEATURE_FIELDS,
    LABEL_FIELD,
    generate_regime_dataset,
)

# Faixas de severidade disjuntas por split (parâmetro gerador diferente).
#
# A dificuldade cresce de train para test: treina em anomalias claras
# (severidade alta) e testa em anomalias sutis (severidade baixa). Medição
# empírica: um RandomForest treinado em ~[0.6,0.85] cai de macro-F1 ~1.0
# (no próprio regime) para ~0.75 no regime sutil [0.25,0.40], enquanto testar
# em severidade maior satura em 1.0 e não mede generalização. A validação fica
# próxima do teste para calibrar no regime de interesse.
SPLIT_REGIMES: dict[str, tuple[float, float]] = {
    "train": (0.62, 0.86),
    "val": (0.42, 0.56),
    "test": (0.25, 0.40),
}


def make_regime_splits(
    *, n_per_class: int = 500, seed: int = 0, prefix: str = "regime"
) -> dict[str, DatasetSplit]:
    return {
        split: generate_regime_dataset(
            n_per_class=n_per_class,
            seed=seed + offset,
            severity_range=regime,
            name=f"{prefix}:{split}",
        )
        for offset, (split, regime) in enumerate(SPLIT_REGIMES.items())
    }


def temporal_split(
    dataset: DatasetSplit,
    *,
    train_frac: float = 0.6,
    val_frac: float = 0.2,
    name: str = "temporal",
) -> tuple[DatasetSplit, DatasetSplit, DatasetSplit]:
    """Divide por tempo preservando a ordem cronológica (sem embaralhar)."""
    order = np.argsort(dataset.times, kind="stable")
    n = len(order)
    n_train = int(n * train_frac)
    n_val = int(n * val_frac)
    slices = {
        f"{name}:train": order[:n_train],
        f"{name}:val": order[n_train : n_train + n_val],
        f"{name}:test": order[n_train + n_val :],
    }
    parts = {}
    for part_name, idx in slices.items():
        parts[part_name] = DatasetSplit(
            X=dataset.X[idx],
            y=dataset.y[idx],
            severity=dataset.severity[idx],
            groups=np.asarray(
                [f"{part_name}:{g}" for g in dataset.groups[idx]], dtype=object
            ),
            times=dataset.times[idx],
            feature_names=dataset.feature_names,
            meta={**dataset.meta, "name": part_name, "kind": "temporal"},
        )
    return parts[f"{name}:train"], parts[f"{name}:val"], parts[f"{name}:test"]


def group_kfold(
    dataset: DatasetSplit, *, n_splits: int = 5, seed: int = 0
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Validação cruzada por grupo (GrupoKFold). O seed fica reservado para
    reprodutibilidade de futuras variantes embaralhadas."""
    splitter = GroupKFold(n_splits=n_splits)
    dummy = np.zeros(len(dataset))
    return list(splitter.split(dataset.X, dummy, groups=dataset.groups))


def _severity_range(dataset: DatasetSplit) -> tuple[float, float] | None:
    mask = dataset.y != "NORMAL"
    values = dataset.severity[mask]
    if len(values) == 0:
        return None
    return float(values.min()), float(values.max())


def assert_no_leakage(*datasets: DatasetSplit) -> None:
    """Falha se houver vazamento entre os conjuntos informados."""
    if len(datasets) < 2:
        return
    for dataset in datasets:
        name = dataset.meta.get("name", "?")
        if LABEL_FIELD in dataset.feature_names:
            raise AssertionError(f"vazamento: rótulo '{LABEL_FIELD}' é feature em {name}")

    names = [d.meta.get("name", f"split{i}") for i, d in enumerate(datasets)]

    # Grupos não podem se repetir entre splits.
    group_owner: dict[str, str] = {}
    for name, dataset in zip(names, datasets):
        for group in set(dataset.groups.tolist()):
            if group in group_owner:
                raise AssertionError(
                    f"vazamento: grupo '{group}' aparece em {group_owner[group]} e {name}"
                )
            group_owner[group] = name

    # Nenhuma linha idêntica pode aparecer em dois splits.
    row_owner: dict[tuple[float, ...], str] = {}
    for name, dataset in zip(names, datasets):
        for row in np.round(dataset.X, 6):
            key = tuple(row.tolist())
            owner = row_owner.get(key)
            if owner is not None and owner != name:
                raise AssertionError(
                    f"vazamento: linha duplicada entre {owner} e {name}"
                )
            row_owner[key] = name

    # Faixas de severidade (classes anômalas) disjuntas entre splits.
    for (name_a, data_a), (name_b, data_b) in itertools.combinations(
        zip(names, datasets), 2
    ):
        # A severidade só separa regimes; em splits temporais/externos o eixo é
        # o tempo/origem, não a severidade.
        if data_a.meta.get("kind") != "regime" or data_b.meta.get("kind") != "regime":
            continue
        range_a = _severity_range(data_a)
        range_b = _severity_range(data_b)
        if range_a is None or range_b is None:
            continue
        (a_lo, a_hi), (b_lo, b_hi) = range_a, range_b
        if not (a_hi < b_lo or b_hi < a_lo):
            raise AssertionError(
                f"vazamento: severidades se sobrepõem entre {name_a} {range_a} e {name_b} {range_b}"
            )

    # Se todos forem temporais, as janelas de tempo não podem se sobrepor.
    if all(d.meta.get("kind") == "temporal" for d in datasets):
        ordered = sorted(zip(names, datasets), key=lambda pair: pair[1].times.min())
        for (name_a, data_a), (name_b, data_b) in zip(ordered, ordered[1:]):
            if data_a.times.max() > data_b.times.min():
                raise AssertionError(
                    f"vazamento temporal: {name_a} termina depois do início de {name_b}"
                )
