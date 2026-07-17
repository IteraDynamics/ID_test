from __future__ import annotations

from argparse import Namespace
from datetime import UTC
from pathlib import Path

import pandas as pd
import pytest

import scripts.run_core_v1_jump_risk_replay as replay


def _scored() -> pd.DataFrame:
    index = pd.date_range("2025-01-01 01:00:00", periods=3, freq="1h", tz=UTC)
    return pd.DataFrame(
        {
            "medium_up_probability": [0.20, 0.96, 0.10],
            "medium_up_threshold": [0.95, 0.95, 0.95],
            "extended_up_probability": [0.20, 0.20, 0.97],
            "extended_up_threshold": [0.95, 0.95, 0.95],
        },
        index=index,
    )


def test_replay_is_deterministic_and_uses_only_prior_bars() -> None:
    first = replay.replay_asset("BTC", _scored())
    second = replay.replay_asset("BTC", _scored())

    assert first["decision_digest"] == second["decision_digest"]
    assert first["boost_count"] == 2
    assert first["reason_counts"] == {"ALIGNED_UPSIDE_ACTIVE": 2, "BELOW_THRESHOLD": 1}
    for row in first["decisions"]:
        assert pd.Timestamp(row["source_bar_ts"]) < pd.Timestamp(row["decision_at"])


def test_score_asset_joins_locked_models_without_forward_fill() -> None:
    index = pd.date_range("2025-01-01", periods=3, freq="1h")

    def scorer(_ohlcv, _asset, model_name, *_args):
        frame = pd.DataFrame(
            {"probability": [0.1, 0.2, 0.3], "train_threshold": [0.9, 0.9, 0.9]},
            index=index,
        )
        return frame if model_name == "medium_up" else frame.iloc[1:]

    result = replay._score_asset(
        asset="ETH",
        ohlcv=pd.DataFrame(),
        oos_start="2025-01-01",
        oos_end="2025-12-31",
        jump_z=3.0,
        absolute_jump=0.05,
        risk_quantile=0.95,
        scorer=scorer,
    )
    assert list(result.index) == list(index[1:])
    assert set(result.columns) == {
        "medium_up_probability",
        "medium_up_threshold",
        "extended_up_probability",
        "extended_up_threshold",
    }


def test_score_asset_rejects_empty_overlap() -> None:
    def scorer(_ohlcv, _asset, model_name, *_args):
        hour = 0 if model_name == "medium_up" else 1
        index = pd.DatetimeIndex([pd.Timestamp("2025-01-01") + pd.Timedelta(hours=hour)])
        return pd.DataFrame({"probability": [0.5], "train_threshold": [0.9]}, index=index)

    with pytest.raises(RuntimeError, match="No overlapping"):
        replay._score_asset(
            asset="BTC",
            ohlcv=pd.DataFrame(),
            oos_start="2025-01-01",
            oos_end="2025-12-31",
            jump_z=3.0,
            absolute_jump=0.05,
            risk_quantile=0.95,
            scorer=scorer,
        )


def test_build_report_is_shadow_only_and_digest_stable(tmp_path: Path, monkeypatch) -> None:
    btc = tmp_path / "btc.csv"
    eth = tmp_path / "eth.csv"
    btc.write_text("placeholder", encoding="utf-8")
    eth.write_text("placeholder", encoding="utf-8")

    monkeypatch.setattr(replay, "read_ohlcv", lambda _path: pd.DataFrame())
    monkeypatch.setattr(replay, "_score_asset", lambda **_kwargs: _scored())
    args = Namespace(
        btc_data=str(btc),
        eth_data=str(eth),
        oos_start="2025-01-01",
        oos_end="2025-12-31",
        risk_quantile=0.95,
        jump_z=3.0,
        absolute_jump=0.05,
        out=str(tmp_path / "report.json"),
    )

    first = replay.build_replay_report(args)
    second = replay.build_replay_report(args)
    assert first["replay_digest"] == second["replay_digest"]
    assert first["guards"] == {
        "orders_mutated": False,
        "state_mutated": False,
        "nav_mutated": False,
        "future_bar_leakage_detected": False,
    }
    assert first["summary"]["BTC"]["boost_count"] == 2
    assert first["summary"]["ETH"]["boost_count"] == 2


def test_build_report_requires_canonical_inputs(tmp_path: Path) -> None:
    args = Namespace(
        btc_data=str(tmp_path / "missing-btc.csv"),
        eth_data=str(tmp_path / "missing-eth.csv"),
        oos_start="2025-01-01",
        oos_end="2025-12-31",
        risk_quantile=0.95,
        jump_z=3.0,
        absolute_jump=0.05,
        out=str(tmp_path / "report.json"),
    )
    with pytest.raises(FileNotFoundError, match="Missing canonical input"):
        replay.build_replay_report(args)
