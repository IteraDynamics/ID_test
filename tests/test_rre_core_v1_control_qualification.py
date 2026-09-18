from __future__ import annotations

from argparse import Namespace

import pytest

from scripts import run_rre_core_v1_control_qualification as q


def test_frozen_control_config() -> None:
    assert q.EXPECTED_CONFIG["trend_weight"] == 0.40
    assert q.EXPECTED_CONFIG["equity_weight"] == 0.35
    assert q.EXPECTED_CONFIG["gold_weight"] == 0.15
    assert q.EXPECTED_CONFIG["hedge_weight"] == 0.10
    assert q.EXPECTED_CONFIG["mr_weight"] == 0.00
    assert q.EXPECTED_CONFIG["oos_start"] == "2020-01-01"
    assert q.EXPECTED_CONFIG["oos_end"] == "2025-12-31"


def test_sleeve_inventory_is_deterministic_and_aggregated() -> None:
    payload = {"sleeves": [
        {"stage": "validation", "fold": "2023", "sleeve": "B", "target_rows": 2, "trade_rows": 1},
        {"stage": "development", "fold": "2020", "sleeve": "A", "target_rows": 5, "trade_rows": 3},
        {"stage": "validation", "fold": "2024", "sleeve": "A", "target_rows": 7, "trade_rows": 4},
    ]}
    assert q.sleeve_inventory(payload) == [
        {"sleeve": "A", "folds": 2, "target_rows": 12, "trade_rows": 7, "stages": ["development", "validation"]},
        {"sleeve": "B", "folds": 1, "target_rows": 2, "trade_rows": 1, "stages": ["validation"]},
    ]


def test_governed_default_drift_fails_closed(monkeypatch, tmp_path) -> None:
    fake = Namespace(
        btc_data="", eth_data="", spy_data="", qqq_data="", bil_data="", gld_data="",
        out_dir="", pass_workers=2, **q.EXPECTED_CONFIG
    )
    fake.fee = 0.123
    monkeypatch.setattr(q.governed, "build_args", lambda: fake)
    args = Namespace(
        btc_data="btc", eth_data="eth", spy_data="spy", qqq_data="qqq",
        bil_data="bil", gld_data="gld", pass_workers=2
    )
    with pytest.raises(q.ControlQualificationError, match="GOVERNED_DEFAULT_DRIFT:fee"):
        q.governed_args(args, tmp_path)
