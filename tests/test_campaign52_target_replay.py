from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research.harness.backtest_engine import run_backtest
from research.harness.campaign52_target_replay import (
    Campaign52ReplayError,
    TargetRecord,
    intent_to_signed_target,
    run_capture_or_replay,
    serialize_targets,
)
from research.harness.execution_model import ExecutionConfig
from research.strategies.contracts import Action, StrategyIntent


class SyntheticStrategy:
    STRATEGY_ID = "campaign52_synthetic"

    @staticmethod
    def generate_intent(df, ctx, closed_only=True):
        i = len(df) - 1
        schedule = {
            2: (Action.ENTER_LONG, 0.60),
            5: (Action.HOLD, 0.00),
            7: (Action.EXIT_LONG, 0.00),
            10: (Action.ENTER_SHORT, 0.40),
            13: (Action.HOLD, 0.00),
            15: (Action.EXIT_SHORT, 0.00),
        }
        action, exposure = schedule.get(i, (Action.HOLD, 0.00))
        return StrategyIntent(
            action=action,
            confidence=1.0,
            desired_exposure_frac=exposure,
            horizon_hours=1,
            reason=f"campaign52_replay:{action.value}",
            strategy_id=SyntheticStrategy.STRATEGY_ID,
        )


def synthetic_ohlcv(n=24):
    index = pd.date_range("2024-01-01", periods=n, freq="h")
    close = pd.Series(np.linspace(100.0, 112.0, n), index=index)
    return pd.DataFrame(
        {
            "open": close.shift(1).fillna(close.iloc[0]),
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1000.0,
        },
        index=index,
    )


def assert_economic_equivalence(left, right):
    pd.testing.assert_series_equal(left.equity_curve, right.equity_curve, check_exact=True)
    pd.testing.assert_series_equal(left.position_series, right.position_series, check_exact=True)
    pd.testing.assert_series_equal(left.regime_series, right.regime_series, check_exact=True)
    assert [asdict(t) for t in left.trades] == [asdict(t) for t in right.trades]


def test_intent_to_signed_target_long_short_flat_and_hold():
    def intent(action, desired=0.75):
        return StrategyIntent(action, 1.0, desired, 1, action.value, strategy_id="s")

    assert intent_to_signed_target(intent(Action.ENTER_LONG), 0.0, 0.5) == 0.5
    assert intent_to_signed_target(intent(Action.ENTER_SHORT), 0.0, 0.5) == -0.5
    assert intent_to_signed_target(intent(Action.FLAT), 0.3) == 0.0
    assert intent_to_signed_target(intent(Action.EXIT_LONG), 0.3) == 0.0
    assert intent_to_signed_target(intent(Action.HOLD, 0.0), -0.25) == -0.25


def test_capture_only_matches_canonical_engine_exactly():
    df = synthetic_ohlcv()
    cfg = ExecutionConfig(taker_fee_rate=0.0006, base_slippage_bps=3.0, cooldown_bars=2)
    cash_yield = pd.Series(0.00001, index=df.index)

    canonical = run_backtest(
        df=df,
        strategy_module=SyntheticStrategy,
        initial_capital=100000.0,
        exec_config=cfg,
        rebalance_threshold=0.02,
        asset="BTC",
        cash_yield_series=cash_yield,
    )
    captured = run_capture_or_replay(
        df=df,
        strategy_module=SyntheticStrategy,
        initial_capital=100000.0,
        exec_config=cfg,
        rebalance_threshold=0.02,
        asset="BTC",
        cash_yield_series=cash_yield,
    )
    assert_economic_equivalence(canonical, captured.result)
    assert len(captured.targets) == len(df)
    assert [r.timestamp for r in captured.targets] == list(df.index)


def test_unmodified_target_replay_matches_capture_exactly():
    df = synthetic_ohlcv()
    cfg = ExecutionConfig(taker_fee_rate=0.0006, base_slippage_bps=3.0, cooldown_bars=2)
    cash_yield = pd.Series(0.00001, index=df.index)
    captured = run_capture_or_replay(
        df=df,
        strategy_module=SyntheticStrategy,
        initial_capital=100000.0,
        exec_config=cfg,
        rebalance_threshold=0.02,
        asset="BTC",
        cash_yield_series=cash_yield,
        stage="development",
        fold="2024",
        sleeve_label="BTC_1H_trend",
        native_timeframe="1H",
    )
    replayed = run_capture_or_replay(
        df=df,
        strategy_module=None,
        target_records=captured.targets,
        initial_capital=100000.0,
        exec_config=cfg,
        rebalance_threshold=0.02,
        asset="BTC",
        cash_yield_series=cash_yield,
        stage="development",
        fold="2024",
        sleeve_label="BTC_1H_trend",
        native_timeframe="1H",
    )
    assert_economic_equivalence(captured.result, replayed.result)


def test_cooldown_threshold_cost_and_cash_yield_are_preserved():
    df = synthetic_ohlcv()
    cfg = ExecutionConfig(taker_fee_rate=0.001, base_slippage_bps=5.0, cooldown_bars=3)
    cash_yield = pd.Series(0.00002, index=df.index)
    captured = run_capture_or_replay(
        df=df,
        strategy_module=SyntheticStrategy,
        exec_config=cfg,
        rebalance_threshold=0.10,
        cash_yield_series=cash_yield,
    )
    replayed = run_capture_or_replay(
        df=df,
        strategy_module=None,
        target_records=captured.targets,
        exec_config=cfg,
        rebalance_threshold=0.10,
        cash_yield_series=cash_yield,
    )
    assert_economic_equivalence(captured.result, replayed.result)
    assert sum(t.fee_usd for t in replayed.result.trades) > 0
    assert sum(t.slippage_usd for t in replayed.result.trades) > 0


def test_malformed_or_cross_stage_stream_fails_closed():
    df = synthetic_ohlcv(8)
    captured = run_capture_or_replay(
        df=df,
        strategy_module=SyntheticStrategy,
        stage="development",
        fold="2024",
    )
    bad_stage = [replace(captured.targets[0], stage="validation"), *captured.targets[1:]]
    with pytest.raises(Campaign52ReplayError, match="TARGET_STAGE_FOLD_MISMATCH"):
        run_capture_or_replay(
            df=df,
            strategy_module=None,
            target_records=bad_stage,
            stage="development",
            fold="2024",
        )

    bad_sequence = [captured.targets[0], replace(captured.targets[1], sequence_number=4), *captured.targets[2:]]
    with pytest.raises(Campaign52ReplayError, match="TARGET_SEQUENCE_FAILURE"):
        run_capture_or_replay(
            df=df,
            strategy_module=None,
            target_records=bad_sequence,
            stage="development",
            fold="2024",
        )


def test_hold_target_may_preserve_realized_exposure_drift_above_one():
    df = synthetic_ohlcv(4)
    records = [
        TargetRecord("development", "2024", ts, "s", "BTC", "1H", "x", Action.HOLD.value, 0.0, 1.0004, i)
        for i, ts in enumerate(df.index)
    ]
    replayed = run_capture_or_replay(
        df=df,
        strategy_module=None,
        target_records=records,
        stage="development",
        fold="2024",
        sleeve_label="s",
        asset="BTC",
        native_timeframe="1H",
    )
    assert len(replayed.targets) == len(df)


def test_entry_target_outside_declared_range_still_fails_closed():
    df = synthetic_ohlcv(4)
    records = [
        TargetRecord("development", "2024", ts, "s", "BTC", "1H", "x", Action.HOLD.value, 0.0, 0.0, i)
        for i, ts in enumerate(df.index)
    ]
    records[0] = replace(
        records[0],
        action=Action.ENTER_LONG.value,
        desired_exposure_frac=1.0,
        signed_target_exposure=1.0004,
    )
    with pytest.raises(Campaign52ReplayError, match="TARGET_EXPOSURE_OUT_OF_RANGE"):
        run_capture_or_replay(
            df=df,
            strategy_module=None,
            target_records=records,
            stage="development",
            fold="2024",
            sleeve_label="s",
            asset="BTC",
            native_timeframe="1H",
        )


def test_target_serialization_is_deterministic(tmp_path: Path):
    df = synthetic_ohlcv(8)
    captured = run_capture_or_replay(
        df=df,
        strategy_module=SyntheticStrategy,
        stage="development",
        fold="2024",
    )
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    serialize_targets(captured.targets, first)
    serialize_targets(reversed(captured.targets), second)
    assert first.read_bytes() == second.read_bytes()
    text = first.read_text(encoding="utf-8")
    assert "2024-01-01T00:00:00Z" in text
    assert ",0.000000000000," in text
    assert "\r\n" not in text
