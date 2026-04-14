"""Unit tests — Layer 2 Strategy Modules.

Verifies:
- StrategyIntent contract validity.
- All three strategies return valid intents.
- Intent fields are within contract bounds.
- Warmup period returns FLAT with 0.0 confidence.
- Exit logic triggers on adverse regimes.
- Strategies are side-effect-free (calling twice gives same result).
- strategy_id is correctly set.
"""

from __future__ import annotations

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.fixtures.data_factory import make_df, make_flat_df, make_ctx

from research.regimes.contracts import RegimeLabel
from research.strategies.contracts import Action, StrategyContext, StrategyIntent
from research.strategies import trend_following, volatility_breakout, mean_reversion


# ─────────────────────────────────────────────────────────────────────────────
# StrategyIntent / StrategyContext contract
# ─────────────────────────────────────────────────────────────────────────────

class TestStrategyContracts:
    def test_intent_confidence_bounds(self):
        with pytest.raises(ValueError, match="confidence"):
            StrategyIntent(
                action=Action.HOLD, confidence=1.5, desired_exposure_frac=0.5,
                horizon_hours=12, reason="test",
            )

    def test_intent_exposure_bounds(self):
        with pytest.raises(ValueError, match="desired_exposure_frac"):
            StrategyIntent(
                action=Action.ENTER_LONG, confidence=0.8, desired_exposure_frac=1.2,
                horizon_hours=12, reason="test",
            )

    def test_intent_negative_horizon(self):
        with pytest.raises(ValueError, match="horizon_hours"):
            StrategyIntent(
                action=Action.FLAT, confidence=0.5, desired_exposure_frac=0.0,
                horizon_hours=-1, reason="test",
            )

    def test_intent_is_entry_is_exit(self):
        entry = StrategyIntent(
            action=Action.ENTER_LONG, confidence=0.7, desired_exposure_frac=0.6,
            horizon_hours=24, reason="test",
        )
        assert entry.is_entry
        assert not entry.is_exit

        exit_ = StrategyIntent(
            action=Action.EXIT_LONG, confidence=0.7, desired_exposure_frac=0.0,
            horizon_hours=4, reason="test",
        )
        assert exit_.is_exit
        assert not exit_.is_entry

    def test_with_capped_exposure(self):
        intent = StrategyIntent(
            action=Action.ENTER_LONG, confidence=0.8, desired_exposure_frac=0.9,
            horizon_hours=24, reason="test", strategy_id="test",
        )
        capped = intent.with_capped_exposure(0.5)
        assert capped.desired_exposure_frac == 0.5
        assert capped.action == intent.action
        assert capped.strategy_id == intent.strategy_id

    def test_ctx_exposure_bounds(self):
        with pytest.raises(ValueError):
            StrategyContext(regime=RegimeLabel.RANGE, current_exposure_frac=1.5)


# ─────────────────────────────────────────────────────────────────────────────
# Common helper to validate all intents
# ─────────────────────────────────────────────────────────────────────────────

def assert_valid_intent(intent: StrategyIntent) -> None:
    assert isinstance(intent, StrategyIntent)
    assert isinstance(intent.action, Action)
    assert 0.0 <= intent.confidence <= 1.0
    assert 0.0 <= intent.desired_exposure_frac <= 1.0
    assert intent.horizon_hours >= 0
    assert isinstance(intent.reason, str) and len(intent.reason) > 0
    assert isinstance(intent.strategy_id, str) and len(intent.strategy_id) > 0

    # Exposure must be 0 on exit/flat
    if intent.action in (Action.EXIT_LONG, Action.FLAT):
        assert intent.desired_exposure_frac == 0.0, (
            f"Exit/Flat action but desired_exposure_frac={intent.desired_exposure_frac}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# TrendFollowingStrategy
# ─────────────────────────────────────────────────────────────────────────────

class TestTrendFollowingStrategy:
    def setup_method(self):
        self.df = make_df(n=500)
        self.ctx_flat = make_ctx(regime=RegimeLabel.TREND_UP, exposure=0.0)

    def test_warmup_returns_flat(self):
        short_df = self.df.iloc[:30]
        intent = trend_following.generate_intent(short_df, self.ctx_flat)
        assert intent.action == Action.FLAT
        assert intent.confidence == 0.0

    def test_valid_intent_post_warmup(self):
        intent = trend_following.generate_intent(self.df, self.ctx_flat)
        assert_valid_intent(intent)

    def test_strategy_id(self):
        intent = trend_following.generate_intent(self.df, self.ctx_flat)
        assert "trend_following" in intent.strategy_id

    def test_determinism(self):
        i1 = trend_following.generate_intent(self.df, self.ctx_flat)
        i2 = trend_following.generate_intent(self.df, self.ctx_flat)
        assert i1.action == i2.action
        assert i1.confidence == i2.confidence
        assert i1.desired_exposure_frac == i2.desired_exposure_frac

    def test_exit_on_trend_down_regime(self):
        ctx = make_ctx(regime=RegimeLabel.TREND_DOWN, exposure=0.6)
        intent = trend_following.generate_intent(self.df, ctx)
        assert intent.action == Action.EXIT_LONG
        assert intent.desired_exposure_frac == 0.0

    def test_exit_on_high_vol(self):
        ctx = make_ctx(regime=RegimeLabel.HIGH_VOL, exposure=0.5)
        intent = trend_following.generate_intent(self.df, ctx)
        assert intent.action == Action.EXIT_LONG

    def test_no_side_effects(self):
        """Calling strategy twice does not change the DataFrame."""
        import numpy as np
        df_copy = self.df.copy()
        trend_following.generate_intent(self.df, self.ctx_flat)
        trend_following.generate_intent(self.df, self.ctx_flat)
        assert (self.df.values == df_copy.values).all()


# ─────────────────────────────────────────────────────────────────────────────
# VolatilityBreakoutStrategy
# ─────────────────────────────────────────────────────────────────────────────

class TestVolBreakoutStrategy:
    def setup_method(self):
        self.df = make_df(n=600)
        self.ctx = make_ctx(regime=RegimeLabel.VOL_COMPRESSION, exposure=0.0)

    def test_warmup_returns_flat(self):
        short_df = self.df.iloc[:30]
        intent = volatility_breakout.generate_intent(short_df, self.ctx)
        assert intent.action == Action.FLAT
        assert intent.confidence == 0.0

    def test_valid_intent_post_warmup(self):
        intent = volatility_breakout.generate_intent(self.df, self.ctx)
        assert_valid_intent(intent)

    def test_strategy_id(self):
        intent = volatility_breakout.generate_intent(self.df, self.ctx)
        assert "vol_breakout" in intent.strategy_id

    def test_determinism(self):
        i1 = volatility_breakout.generate_intent(self.df, self.ctx)
        i2 = volatility_breakout.generate_intent(self.df, self.ctx)
        assert i1.action == i2.action
        assert i1.desired_exposure_frac == i2.desired_exposure_frac

    def test_exit_on_high_vol(self):
        ctx = make_ctx(regime=RegimeLabel.HIGH_VOL, exposure=0.4)
        intent = volatility_breakout.generate_intent(self.df, ctx)
        assert intent.action == Action.EXIT_LONG


# ─────────────────────────────────────────────────────────────────────────────
# MeanReversionStrategy
# ─────────────────────────────────────────────────────────────────────────────

class TestMeanReversionStrategy:
    def setup_method(self):
        self.df = make_flat_df(n=300)
        self.ctx = make_ctx(regime=RegimeLabel.RANGE, exposure=0.0)

    def test_warmup_returns_flat(self):
        short_df = self.df.iloc[:10]
        intent = mean_reversion.generate_intent(short_df, self.ctx)
        assert intent.action == Action.FLAT
        assert intent.confidence == 0.0

    def test_valid_intent_post_warmup(self):
        intent = mean_reversion.generate_intent(self.df, self.ctx)
        assert_valid_intent(intent)

    def test_strategy_id(self):
        intent = mean_reversion.generate_intent(self.df, self.ctx)
        assert "mean_reversion" in intent.strategy_id

    def test_determinism(self):
        i1 = mean_reversion.generate_intent(self.df, self.ctx)
        i2 = mean_reversion.generate_intent(self.df, self.ctx)
        assert i1.action == i2.action

    def test_exit_on_trend_regime(self):
        ctx = make_ctx(regime=RegimeLabel.TREND_DOWN, exposure=0.3)
        intent = mean_reversion.generate_intent(self.df, ctx)
        assert intent.action == Action.EXIT_LONG

    def test_flat_outside_range_regime(self):
        ctx = make_ctx(regime=RegimeLabel.TREND_UP, exposure=0.0)
        df = make_df(n=200)
        intent = mean_reversion.generate_intent(df, ctx)
        # With no existing position and not in RANGE/COMPRESSION, should be FLAT
        assert intent.action in (Action.FLAT, Action.HOLD)
