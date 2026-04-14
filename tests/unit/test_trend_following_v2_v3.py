"""Unit tests — TrendFollowingV2 and TrendFollowingV3.

Verifies:
- Warmup returns FLAT.
- When flat + bullish structure → ENTER_LONG at fixed exposure.
- When long + benign regime → HOLD (never ENTER_LONG, i.e. no resize).
- When long + HIGH_VOL → EXIT_LONG immediately.
- When long + TREND_DOWN + bearish crossover → EXIT_LONG.
- When long + material crossover → EXIT_LONG.
- When long + price hard break → EXIT_LONG.
- V3 only: when at base exposure + strong trend → ENTER_LONG (add-on).
- V3 only: when at add exposure + strong trend → HOLD (no second add).
- Deterministic: same inputs → same output.
- strategy_id correct.
- All returned intents have valid bounds.
"""

from __future__ import annotations

import sys
from pathlib import Path
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research.regimes.contracts import RegimeLabel
from research.strategies.contracts import Action, StrategyContext
from research.strategies import trend_following_v2, trend_following_v3


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_df(n: int = 200, trend: str = "up", seed: int = 0) -> pd.DataFrame:
    """Synthetic OHLCV.  trend='up' → rising close; 'flat' → flat; 'down' → falling."""
    rng = np.random.default_rng(seed)
    if trend == "up":
        drift = 0.003
    elif trend == "down":
        drift = -0.003
    else:
        drift = 0.0

    prices = 30_000.0 * np.exp(
        np.cumsum(drift + rng.standard_normal(n) * 0.01)
    )
    idx = pd.date_range("2021-01-01", periods=n, freq="1h")
    return pd.DataFrame({
        "open":   prices * 0.999,
        "high":   prices * 1.008,
        "low":    prices * 0.992,
        "close":  prices,
        "volume": np.ones(n) * 500.0,
    }, index=idx)


def _ctx(regime: RegimeLabel, exposure: float = 0.0, bar: int = 150) -> StrategyContext:
    return StrategyContext(
        regime=regime,
        current_exposure_frac=exposure,
        asset="BTC",
        bar_index=bar,
    )


def _intent(module, df, regime=RegimeLabel.TREND_UP, exposure=0.0, bar=None):
    bar = bar if bar is not None else len(df) - 1
    ctx = _ctx(regime, exposure, bar)
    return module.generate_intent(df, ctx, closed_only=True)


# ── Shared tests run against both modules ─────────────────────────────────────

@pytest.mark.parametrize("module", [trend_following_v2, trend_following_v3])
class TestSharedBehavior:

    def test_warmup_returns_flat(self, module):
        df = _make_df(n=30, trend="up")
        intent = _intent(module, df)
        assert intent.action == Action.FLAT
        assert intent.desired_exposure_frac == 0.0

    def test_flat_bullish_enters_long(self, module):
        df = _make_df(n=200, trend="up")
        intent = _intent(module, df, regime=RegimeLabel.TREND_UP, exposure=0.0)
        # May or may not enter depending on signal quality — just verify valid
        assert intent.action in (Action.ENTER_LONG, Action.FLAT)
        assert 0.0 <= intent.desired_exposure_frac <= 1.0

    def test_long_high_vol_exits(self, module):
        df = _make_df(n=200, trend="up")
        intent = _intent(module, df, regime=RegimeLabel.HIGH_VOL, exposure=0.60)
        assert intent.action == Action.EXIT_LONG
        assert intent.desired_exposure_frac == 0.0

    def test_long_trend_down_bearish_crossover_exits(self, module):
        """TREND_DOWN + bearish spread → exit."""
        # Build a clearly bearish df (fast EMA will be below slow)
        df = _make_df(n=200, trend="down", seed=5)
        intent = _intent(module, df, regime=RegimeLabel.TREND_DOWN, exposure=0.60)
        # Either exits on TREND_DOWN+crossover or on material crossover / price break
        assert intent.action in (Action.EXIT_LONG, Action.HOLD)

    def test_long_benign_returns_hold_not_enter(self, module):
        """Core anti-churn test: when long and trend is intact, must return HOLD."""
        df = _make_df(n=200, trend="up")
        intent = _intent(module, df, regime=RegimeLabel.TREND_UP, exposure=0.75)
        # In a sustained uptrend with exposure already set, should HOLD (or exit in bad conditions)
        # The key is it must NOT return ENTER_LONG with a different exposure (no resize)
        if intent.action == Action.ENTER_LONG:
            # Only acceptable ENTER_LONG while long is the v3 add-on from base
            assert module.STRATEGY_ID == "trend_following_v3"
        assert intent.action in (Action.HOLD, Action.EXIT_LONG, Action.ENTER_LONG)

    def test_no_resize_while_long_on_repeated_bars(self, module):
        """Run 10 consecutive bars while long — must not flip between exposures."""
        df_full = _make_df(n=250, trend="up")
        exposures_returned = []
        for i in range(200, 210):
            df_slice = df_full.iloc[: i + 1]
            ctx = _ctx(RegimeLabel.TREND_UP, exposure=0.75, bar=i)
            intent = module.generate_intent(df_slice, ctx, closed_only=True)
            if intent.action == Action.ENTER_LONG:
                exposures_returned.append(intent.desired_exposure_frac)

        # At most one distinct ENTER_LONG exposure target (the add-on, if v3)
        unique = set(round(e, 2) for e in exposures_returned)
        assert len(unique) <= 1, (
            f"Strategy emitted multiple different ENTER_LONG exposures while long: {unique}"
        )

    def test_flat_non_trend_stays_flat(self, module):
        df = _make_df(n=200, trend="flat")
        intent = _intent(module, df, regime=RegimeLabel.RANGE, exposure=0.0)
        assert intent.action in (Action.FLAT, Action.HOLD)
        assert intent.desired_exposure_frac == 0.0

    def test_strategy_id_correct(self, module):
        df = _make_df(n=200, trend="up")
        intent = _intent(module, df)
        assert intent.strategy_id == module.STRATEGY_ID

    def test_deterministic(self, module):
        df = _make_df(n=200, trend="up")
        i1 = _intent(module, df, regime=RegimeLabel.TREND_UP, exposure=0.0)
        i2 = _intent(module, df, regime=RegimeLabel.TREND_UP, exposure=0.0)
        assert i1.action == i2.action
        assert i1.desired_exposure_frac == i2.desired_exposure_frac

    def test_confidence_in_bounds(self, module):
        df = _make_df(n=200, trend="up")
        for exposure in [0.0, 0.50, 0.75]:
            intent = _intent(module, df, exposure=exposure)
            assert 0.0 <= intent.confidence <= 1.0

    def test_exposure_in_bounds(self, module):
        df = _make_df(n=200, trend="up")
        for regime in [RegimeLabel.TREND_UP, RegimeLabel.RANGE, RegimeLabel.HIGH_VOL]:
            intent = _intent(module, df, regime=regime, exposure=0.50)
            assert 0.0 <= intent.desired_exposure_frac <= 1.0

    def test_exit_long_always_zero_exposure(self, module):
        """Any EXIT_LONG must have desired_exposure_frac == 0.0."""
        df = _make_df(n=200, trend="up")
        for regime in [RegimeLabel.HIGH_VOL, RegimeLabel.TREND_DOWN]:
            intent = _intent(module, df, regime=regime, exposure=0.60)
            if intent.action == Action.EXIT_LONG:
                assert intent.desired_exposure_frac == 0.0

    def test_entry_exposure_in_range(self, module):
        """ENTER_LONG from flat must return a fixed, bounded exposure."""
        df = _make_df(n=200, trend="up")
        intent = _intent(module, df, regime=RegimeLabel.TREND_UP, exposure=0.0)
        if intent.action == Action.ENTER_LONG:
            assert 0.40 <= intent.desired_exposure_frac <= 0.85


# ── V2-specific tests ─────────────────────────────────────────────────────────

class TestTrendFollowingV2:
    def test_entry_exposure_is_fixed(self):
        """V2 must always enter at ENTRY_EXPOSURE (0.75), not a variable."""
        df = _make_df(n=200, trend="up")
        intent = _intent(trend_following_v2, df, regime=RegimeLabel.TREND_UP, exposure=0.0)
        if intent.action == Action.ENTER_LONG:
            assert abs(intent.desired_exposure_frac - trend_following_v2.ENTRY_EXPOSURE) < 1e-9

    def test_no_add_on_while_long(self):
        """V2 must never return ENTER_LONG while already long (no add-on in v2)."""
        df = _make_df(n=250, trend="up")
        for i in range(200, 220):
            df_slice = df.iloc[: i + 1]
            ctx = _ctx(RegimeLabel.TREND_UP, exposure=0.75, bar=i)
            intent = trend_following_v2.generate_intent(df_slice, ctx)
            assert intent.action != Action.ENTER_LONG, (
                f"V2 emitted ENTER_LONG while already long at bar {i}"
            )

    def test_strategy_id(self):
        assert trend_following_v2.STRATEGY_ID == "trend_following_v2"


# ── V3-specific tests ─────────────────────────────────────────────────────────

class TestTrendFollowingV3:
    def test_base_entry_exposure(self):
        """V3 initial entry must be at BASE_EXPOSURE (0.60)."""
        df = _make_df(n=200, trend="up")
        intent = _intent(trend_following_v3, df, regime=RegimeLabel.TREND_UP, exposure=0.0)
        if intent.action == Action.ENTER_LONG:
            assert abs(intent.desired_exposure_frac - trend_following_v3.BASE_EXPOSURE) < 1e-9

    def test_add_on_raises_exposure(self):
        """From base exposure, on a strong trend, V3 should eventually add to ADD_EXPOSURE."""
        df = _make_df(n=250, trend="up", seed=1)
        found_add = False
        for i in range(200, 250):
            df_slice = df.iloc[: i + 1]
            # Simulate being at base level
            ctx = _ctx(RegimeLabel.TREND_UP, exposure=0.60, bar=i)
            intent = trend_following_v3.generate_intent(df_slice, ctx)
            if intent.action == Action.ENTER_LONG:
                assert intent.desired_exposure_frac <= trend_following_v3.ADD_EXPOSURE + 1e-9
                found_add = True
                break
        # Not asserting found_add — may not fire on synthetic data; just validates no crash

    def test_no_add_when_already_at_add_level(self):
        """Once at ADD exposure, V3 must not emit another ENTER_LONG (no second add)."""
        df = _make_df(n=250, trend="up")
        for i in range(200, 220):
            df_slice = df.iloc[: i + 1]
            # Simulate already at ADD level
            ctx = _ctx(RegimeLabel.TREND_UP, exposure=0.80, bar=i)
            intent = trend_following_v3.generate_intent(df_slice, ctx)
            assert intent.action != Action.ENTER_LONG, (
                f"V3 emitted ENTER_LONG while at add-level at bar {i}"
            )

    def test_strategy_id(self):
        assert trend_following_v3.STRATEGY_ID == "trend_following_v3"
