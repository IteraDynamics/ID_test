"""Unit tests for Equity Book SPY/QQQ SMA Band v1."""

from __future__ import annotations

import pandas as pd
import pytest

from research.regimes.contracts import RegimeLabel
from research.strategies.contracts import Action, StrategyContext
from research.strategies import equity_spy_qqq_sma_band_v1 as strategy
from research.strategies import REGISTRY


def _ctx(exposure: float = 0.0) -> StrategyContext:
    return StrategyContext(
        regime=RegimeLabel.UNKNOWN,
        current_exposure_frac=exposure,
        asset="EQUITY_BOOK",
        bar_index=0,
        meta={},
    )


def _wide_df(spy_values: list[float], qqq_values: list[float]) -> pd.DataFrame:
    idx = pd.date_range("2020-01-01", periods=len(spy_values), freq="D")
    return pd.DataFrame({"spy_close": spy_values, "qqq_close": qqq_values}, index=idx)


def test_strategy_registered():
    assert "equity_spy_qqq_sma_band_v1" in REGISTRY
    assert REGISTRY["equity_spy_qqq_sma_band_v1"] is strategy


def test_warmup_returns_cash_only_hold():
    df = _wide_df([100.0, 101.0, 102.0], [200.0, 201.0, 202.0])

    signal = strategy.compute_signal(df, sma_window=5)
    intent = strategy.generate_intent(df, _ctx(), sma_window=5)

    assert signal.warmup is True
    assert signal.target_weights == {"SPY": 0.0, "QQQ": 0.0, "cash": 1.0}
    assert intent.action == Action.HOLD
    assert intent.confidence == 0.0
    assert intent.desired_exposure_frac == 0.0
    assert intent.meta["target_weights"] == {"SPY": 0.0, "QQQ": 0.0, "cash": 1.0}


def test_both_assets_active_when_close_above_sma():
    df = _wide_df(
        [100.0, 100.0, 100.0, 100.0, 110.0],
        [200.0, 200.0, 200.0, 200.0, 220.0],
    )

    signal = strategy.compute_signal(df, sma_window=5)
    intent = strategy.generate_intent(df, _ctx(exposure=0.0), sma_window=5)

    assert signal.warmup is False
    assert signal.spy_active is True
    assert signal.qqq_active is True
    assert signal.target_weights == {"SPY": 0.5, "QQQ": 0.5, "cash": 0.0}
    assert signal.gross_exposure == pytest.approx(1.0)
    assert intent.action == Action.ENTER_LONG
    assert intent.desired_exposure_frac == pytest.approx(1.0)
    assert intent.meta["target_effective_next_bar"] is True


def test_single_asset_active_allocates_other_sleeve_to_cash():
    df = _wide_df(
        [100.0, 100.0, 100.0, 100.0, 110.0],
        [200.0, 200.0, 200.0, 200.0, 190.0],
    )

    signal = strategy.compute_signal(df, sma_window=5)
    intent = strategy.generate_intent(df, _ctx(exposure=1.0), sma_window=5)

    assert signal.spy_active is True
    assert signal.qqq_active is False
    assert signal.target_weights == {"SPY": 0.5, "QQQ": 0.0, "cash": 0.5}
    assert signal.gross_exposure == pytest.approx(0.5)
    assert intent.action == Action.HOLD
    assert intent.desired_exposure_frac == pytest.approx(0.5)
    assert intent.meta["target_weights"] == {"SPY": 0.5, "QQQ": 0.0, "cash": 0.5}


def test_both_assets_inactive_exits_to_cash():
    df = _wide_df(
        [100.0, 100.0, 100.0, 100.0, 90.0],
        [200.0, 200.0, 200.0, 200.0, 190.0],
    )

    signal = strategy.compute_signal(df, sma_window=5)
    intent = strategy.generate_intent(df, _ctx(exposure=1.0), sma_window=5)

    assert signal.spy_active is False
    assert signal.qqq_active is False
    assert signal.target_weights == {"SPY": 0.0, "QQQ": 0.0, "cash": 1.0}
    assert intent.action == Action.EXIT_LONG
    assert intent.desired_exposure_frac == 0.0


def test_signal_uses_latest_closed_bar_and_not_future_bar():
    base = _wide_df(
        [100.0, 100.0, 100.0, 100.0, 90.0],
        [200.0, 200.0, 200.0, 200.0, 190.0],
    )
    with_future = pd.concat(
        [
            base,
            pd.DataFrame(
                {"spy_close": [500.0], "qqq_close": [500.0]},
                index=[base.index[-1] + pd.Timedelta(days=1)],
            ),
        ]
    )

    signal_without_future = strategy.compute_signal(base, sma_window=5)
    signal_with_future = strategy.compute_signal(with_future.iloc[:-1], sma_window=5)

    assert signal_without_future.target_weights == signal_with_future.target_weights
    assert signal_without_future.target_weights == {"SPY": 0.0, "QQQ": 0.0, "cash": 1.0}


def test_rejects_invalid_sma_window():
    df = _wide_df([100.0, 101.0], [200.0, 201.0])
    with pytest.raises(ValueError, match="sma_window"):
        strategy.compute_signal(df, sma_window=1)


def test_accepts_uppercase_asset_columns():
    idx = pd.date_range("2020-01-01", periods=5, freq="D")
    df = pd.DataFrame(
        {
            "SPY_close": [100.0, 100.0, 100.0, 100.0, 110.0],
            "QQQ_close": [200.0, 200.0, 200.0, 200.0, 220.0],
        },
        index=idx,
    )

    signal = strategy.compute_signal(df, sma_window=5)

    assert signal.target_weights == {"SPY": 0.5, "QQQ": 0.5, "cash": 0.0}
