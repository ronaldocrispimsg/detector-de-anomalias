"""Testes da fase 01: dados, regimes e guarda anti-vazamento."""

from __future__ import annotations

import random
import statistics as st
from pathlib import Path

import numpy as np
import pytest

from Backend.harness.datasets import (
    DatasetSplit,
    generate_regime_dataset,
    load_labeled_csv,
    try_load_external,
)
from Backend.harness.splits import (
    SPLIT_REGIMES,
    assert_no_leakage,
    group_kfold,
    make_regime_splits,
    temporal_split,
)
from Backend.services.anomaly_simulator import AnomalySimulator


def _mean(samples, field):
    return st.mean(getattr(s, field) for s in samples)


def test_severity_interpolates_and_is_backward_compatible():
    sim = AnomalySimulator()
    rng = random.Random(7)
    healthy = [sim.generate_sample("DDOS_ATTACK", severity=0.0, rng=rng) for _ in range(400)]
    severe = [sim.generate_sample("DDOS_ATTACK", severity=1.0, rng=rng) for _ in range(400)]
    normal = [sim.generate_sample("NORMAL", severity=1.0, rng=rng) for _ in range(400)]

    # severidade 0 equivale ao regime saudável
    assert abs(_mean(healthy, "latency_ms") - _mean(normal, "latency_ms")) < 5.0
    # severidade 1 recupera o fenômeno pleno do simulador (média ~280 ms)
    assert 250.0 < _mean(severe, "latency_ms") < 310.0
    assert 85.0 < _mean(severe, "cpu_usage_pct") < 99.0
    # monotonicidade
    assert _mean(normal, "latency_ms") < _mean(healthy, "latency_ms") + 1e-9


def test_host_down_full_severity_is_absolute_failure():
    sim = AnomalySimulator()
    rng = random.Random(3)
    sample = sim.generate_sample("HOST_DOWN", severity=1.0, rng=rng)
    assert sample.packet_loss_pct == 100.0
    assert sample.cpu_usage_pct == 0.0
    assert sample.ram_usage_pct == 0.0
    assert sample.tcp_port_open is False


def test_regime_splits_have_disjoint_severity_and_pass_guard():
    splits = make_regime_splits(n_per_class=60, seed=0)
    assert_no_leakage(splits["train"], splits["val"], splits["test"])
    for name, (lo, hi) in SPLIT_REGIMES.items():
        severities = splits[name].severity[splits[name].y != "NORMAL"]
        assert severities.min() >= lo - 1e-9
        assert severities.max() < hi + 1e-9


def test_test_regime_is_harder_than_train_regime():
    # Teste em severidade menor (anomalias sutis) deve ser mais difícil que o
    # próprio treino (in-sample), justificando o desenho dos splits.
    from Backend.harness.baselines import _multiclass_baselines
    from Backend.harness.metrics import macro_f1

    splits = make_regime_splits(n_per_class=150, seed=1)
    model = _multiclass_baselines(0)[0].fit(splits["train"].X, splits["train"].y)
    train_score = macro_f1(splits["train"].y, model.predict(splits["train"].X))
    test_score = macro_f1(splits["test"].y, model.predict(splits["test"].X))
    assert test_score < train_score


def test_label_in_features_is_rejected():
    splits = make_regime_splits(n_per_class=20, seed=2)
    bad = DatasetSplit(
        X=splits["train"].X,
        y=splits["train"].y,
        severity=splits["train"].severity,
        groups=splits["train"].groups,
        times=splits["train"].times,
        feature_names=tuple(splits["train"].feature_names) + ("scenario",),
        meta={"name": "bad"},
    )
    with pytest.raises(AssertionError, match="rótulo"):
        assert_no_leakage(bad, splits["test"])


def test_shared_group_is_rejected():
    splits = make_regime_splits(n_per_class=20, seed=2)
    clone = DatasetSplit(
        X=splits["val"].X,
        y=splits["val"].y,
        severity=splits["val"].severity,
        groups=np.asarray(["shared"] * len(splits["val"]), dtype=object),
        times=splits["val"].times,
        meta={"name": "clone"},
    )
    other = DatasetSplit(
        X=splits["test"].X,
        y=splits["test"].y,
        severity=splits["test"].severity,
        groups=np.asarray(["shared"] * len(splits["test"]), dtype=object),
        times=splits["test"].times,
        meta={"name": "other"},
    )
    with pytest.raises(AssertionError, match="grupo"):
        assert_no_leakage(clone, other)


def test_duplicate_row_is_rejected():
    splits = make_regime_splits(n_per_class=20, seed=4)
    dup = DatasetSplit(
        X=splits["train"].X[:5].copy(),
        y=splits["train"].y[:5].copy(),
        severity=splits["train"].severity[:5].copy(),
        groups=np.asarray([f"d:{i}" for i in range(5)], dtype=object),
        times=splits["train"].times[:5].copy(),
        meta={"name": "dup"},
    )
    original = DatasetSplit(
        X=splits["train"].X[:5].copy(),
        y=splits["train"].y[:5].copy(),
        severity=splits["train"].severity[:5].copy(),
        groups=np.asarray([f"o:{i}" for i in range(5)], dtype=object),
        times=splits["train"].times[:5].copy(),
        meta={"name": "original"},
    )
    with pytest.raises(AssertionError, match="duplicada"):
        assert_no_leakage(dup, original)


def test_overlapping_severity_is_rejected():
    a = generate_regime_dataset(n_per_class=20, seed=5, severity_range=(0.5, 0.8), name="a")
    b = generate_regime_dataset(n_per_class=20, seed=6, severity_range=(0.7, 0.9), name="b")
    with pytest.raises(AssertionError, match="severidades"):
        assert_no_leakage(a, b)


def _write_csv(path: Path, rows: int = 40) -> None:
    header = "timestamp," + ",".join(
        [
            "latency_ms",
            "packet_loss_pct",
            "jitter_ms",
            "cpu_usage_pct",
            "ram_usage_pct",
            "disk_usage_pct",
            "network_in_bps",
            "network_out_bps",
            "http_status_code",
            "http_response_time_ms",
            "tcp_port_open",
            "active_connections",
            "scenario",
        ]
    )
    lines = [header]
    for i in range(rows):
        label = "NORMAL" if i % 2 == 0 else "DDOS_ATTACK"
        lines.append(
            f"{1000+i},{15+i%3},0.0,2.0,30.0,45.0,40.0,5000000,2000000,200,120.0,True,{40+i},{label}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_temporal_split_is_chronological_and_clean(tmp_path: Path):
    csv_path = tmp_path / "tiny.csv"
    _write_csv(csv_path)
    dataset = load_labeled_csv(csv_path)
    assert dataset.meta["kind"] == "csv"
    train, val, test = temporal_split(dataset, train_frac=0.5, val_frac=0.25)
    assert train.times.max() <= val.times.min() <= val.times.max() <= test.times.min()
    assert_no_leakage(train, val, test)
    assert len(train) + len(val) + len(test) == len(dataset)


def test_group_kfold_partitions_all_indices():
    splits = make_regime_splits(n_per_class=40, seed=7)
    folds = group_kfold(splits["train"], n_splits=5)
    assert len(folds) == 5
    covered = np.concatenate([val_idx for _, val_idx in folds])
    assert sorted(covered.tolist()) == list(range(len(splits["train"])))


def test_missing_external_dataset_returns_none(tmp_path: Path):
    assert try_load_external(tmp_path / "nope.csv", name="unsw") is None
