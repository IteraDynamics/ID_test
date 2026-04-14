"""Test fixtures — synthetic OHLCV data and common test objects."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from research.harness.data_loader import make_synthetic_ohlcv
from research.regimes.baseline_engine import BaselineRegimeEngine
from research.regimes.contracts import RegimeLabel
from research.strategies.contracts import StrategyContext


def make_df(n: int = 500, seed: int = 42, trend: str = "up") -> pd.DataFrame:
    """Return a synthetic OHLCV DataFrame with a configurable trend direction."""
    df = make_synthetic_ohlcv(n_bars=n, seed=seed)
    if trend == "down":
        # Flip close prices to create a downtrend
        df["close"] = df["close"].iloc[0] * (2 - df["close"] / df["close"].iloc[0])
        df["open"] = df["close"].shift(1).fillna(df["close"])
        df["high"] = df[["open", "close"]].max(axis=1) * 1.005
        df["low"] = df[["open", "close"]].min(axis=1) * 0.995
    return df


def make_flat_df(n: int = 300, seed: int = 99) -> pd.DataFrame:
    """Return a ranging / low-volatility DataFrame."""
    rng = np.random.default_rng(seed)
    price = 20000.0
    closes = price + rng.uniform(-300, 300, size=n)
    idx = pd.date_range("2022-06-01", periods=n, freq="1h")
    high = closes + rng.uniform(20, 80, size=n)
    low = closes - rng.uniform(20, 80, size=n)
    return pd.DataFrame(
        {"open": closes, "high": high, "low": low, "close": closes, "volume": rng.uniform(100, 500, size=n)},
        index=idx,
    )


def make_ctx(
    regime: RegimeLabel = RegimeLabel.TREND_UP,
    exposure: float = 0.0,
    asset: str = "BTC",
    bar_index: int = 100,
) -> StrategyContext:
    return StrategyContext(
        regime=regime,
        current_exposure_frac=exposure,
        asset=asset,
        bar_index=bar_index,
    )


@pytest.fixture
def df_trending():
    return make_df(n=500, seed=42, trend="up")


@pytest.fixture
def df_flat():
    return make_flat_df(n=300)


@pytest.fixture
def df_downtrend():
    return make_df(n=500, seed=42, trend="down")


@pytest.fixture
def regime_engine():
    return BaselineRegimeEngine()
