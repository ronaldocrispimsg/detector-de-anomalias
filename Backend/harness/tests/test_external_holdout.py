"""Fase 13: carregador e mapeamento do holdout externo."""

from __future__ import annotations

import pandas as pd
import pytest

from Backend.harness.datasets_external import (
    OTHER,
    load_external,
    map_label,
)
from Backend.services.agent.telemetry import CLASSES, FEATURE_FIELDS


def _canonical_frame() -> pd.DataFrame:
    rows = []
    labels = ["Normal", "DoS", "Reconnaissance", "Backdoor"]
    for i, label in enumerate(labels):
        row = {field: float(i + 1) for field in FEATURE_FIELDS}
        row["tcp_port_open"] = 1.0
        row["Label"] = label
        rows.append(row)
    return pd.DataFrame(rows)


def test_mapping_is_deterministic_and_case_insensitive():
    assert map_label("UNSW-NB15", "Normal") == "NORMAL"
    assert map_label("UNSW-NB15", "  dos ") == "DDOS_ATTACK"
    assert map_label("UNSW-NB15", "Reconnaissance") == "PORT_SCAN"
    assert map_label("UNSW-NB15", "Backdoor") == OTHER
    assert map_label("UNSW-NB15", "something-else") == OTHER

    assert map_label("CSE-CIC-IDS2018", "Benign") == "NORMAL"
    assert map_label("CSE-CIC-IDS2018", "DDOS attack-LOIC-UDP") == "DDOS_ATTACK"
    assert map_label("CSE-CIC-IDS2018", "Infilteration") == "DATA_EXFILTRATION"
    assert map_label("CSE-CIC-IDS2018", "Bot") == OTHER


def test_prefix_matching_covers_variants():
    assert map_label("CSE-CIC-IDS2018", "DoS attacks-Slowloris") == "DDOS_ATTACK"
    assert map_label("CSE-CIC-IDS2018", "Brute Force -Web") == OTHER


def test_load_canonical_frame_drops_other():
    load = load_external(_canonical_frame(), "UNSW-NB15")
    assert load.split.X.shape == (3, len(FEATURE_FIELDS))
    assert list(load.split.y) == ["NORMAL", "DDOS_ATTACK", "PORT_SCAN"]
    assert load.report["n_rows"] == 4
    assert load.report["n_used"] == 3
    assert load.report["dropped_other"] == 1
    assert load.report["missing_features"] == []
    assert load.dropped_labels == {"backdoor": 1}
    assert set(load.split.y).issubset(set(CLASSES))


def test_proxy_features_are_documented_and_missing_marked():
    frame = pd.DataFrame(
        [
            {"sload": 5000.0, "dload": 10.0, "sjit": 3.0, "ct_srv_src": 7.0, "Label": "Normal"},
            {"sload": 9_000_000.0, "dload": 10.0, "sjit": 5.0, "ct_srv_src": 40.0, "Label": "DoS"},
        ]
    )
    load = load_external(frame, "UNSW-NB15")
    source = load.report["feature_source"]
    assert source["network_in_bps"] == "sload"
    assert source["network_out_bps"] == "dload"
    assert source["jitter_ms"] == "sjit"
    assert source["active_connections"] == "ct_srv_src"
    assert source["latency_ms"] is None
    assert "latency_ms" in load.report["missing_features"]

    in_col = FEATURE_FIELDS.index("network_in_bps")
    assert load.split.X[1, in_col] == 9_000_000.0


def test_missing_label_column_raises():
    frame = pd.DataFrame([{"sload": 1.0}])
    with pytest.raises(KeyError):
        load_external(frame, "UNSW-NB15")


def test_loading_is_deterministic():
    first = load_external(_canonical_frame(), "UNSW-NB15")
    second = load_external(_canonical_frame(), "UNSW-NB15")
    assert (first.split.X == second.split.X).all()
    assert list(first.split.y) == list(second.split.y)
    assert first.report == second.report
