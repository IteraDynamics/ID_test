"""Unit tests — CrashShortV2 strategy module.

Verifies:
- Warmup returns FLAT with confidence=0.0.
- All calls return a StrategyIntent that satisfies the Layer 2 contract.
- Strategy stays flat when entry gates are not met.
- ATR persistence gate: transient spikes do not trigger entry.
- Exit signals fire correctly on covered short positions.
- Determinism: identical inputs → identical outputs.
- No side effects on the DataFrame.
- strategy_id is correctly propagated.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research.regimes.contracts import RegimeLabel
from research.strategies.contracts import Action, StrategyContext, StrategyIntent
from research.strategies import crash_short_v2

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_downtrend_df(n: int, seed: int = 7, start_price: float = 60_000.0) -> pd.DataFrame:
    """Sustained downtrend with elevated ATR — designed to eventually pass all entry gates."""
    rng = np.random.default_rng(seed)
    price = start_price
    rows = []
    dates = pd.date_range("2019-01-01", periods=n, freq="1h")
    for i in range(n):
        ret = rng.normal(-0.004, 0.025)
        price = max(100.0, price * (1 + ret))
        spread = price * rng.uniform(0.005, 0.025)
        rows.append({
            "open":   price * (1 + rng.uniform(-0.002, 0.002)),
            "high":   price + spread,
            "low":    max(1.0, price - spread),
            "close":  price,
            "volume": rng.uniform(100, 500),
        })
    return pd.DataFrame(rows, index=dates)


def _make_flat_df(n: int, seed: int = 99, price: float = 20_000.0) -> pd.DataFrame:
    """Low-volatility ranging market — ATR well below VOL_COMPRESS_ATR."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2019-01-01", periods=n, freq="1h")
    closes = price + rng.uniform(-150, 150, size=n)
    return pd.DataFrame(
        {
            "open":   closes,
            "high":   closes + rng.uniform(20, 60, size=n),
            "low":    closes - rng.uniform(20, 60, size=n),
            "close":  closes,
            "volume": rng.uniform(100, 500, size=n),
        },
        index=dates,
    )


def _make_uptrend_df(n: int, seed: int = 42, start_price: float = 20_000.0) -> pd.DataFrame:
    """Sustained uptrend — no crash conditions present."""
    rng = np.random.default_rng(seed)
    price = start_price
    rows = []
    dates = pd.date_range("2019-01-01", periods=n, freq="1h")
    for i in range(n):
        ret = rng.normal(0.004, 0.010)
        price = max(100.0, price * (1 + ret))
        spread = price * rng.uniform(0.002, 0.008)
        rows.append({
            "open":   price * (1 + rng.uniform(-0.001, 0.001)),
            "high":   price + spread,
            "low":    max(1.0, price - spread),
            "close":  price,
            "volume": rng.uniform(100, 500),
        })
    return pd.DataFrame(rows, index=dates)


def _ctx(
    regime: RegimeLabel = RegimeLabel.TREND_DOWN,
    exposure: float = 0.0,
    signed_exposure: float = 0.0,
    bar_index: int = 0,
) -> StrategyContext:
    return StrategyContext(
        regime=regime,
        current_exposure_frac=exposure,
        asset="BTC",
        bar_index=bar_index,
        meta={"signed_exposure": signed_exposure},
    )


def _assert_valid_intent(intent: StrategyIntent) -> None:
    assert isinstance(intent, StrategyIntent)
    assert isinstance(intent.action, Action)
    assert 0.0 <= intent.confidence <= 1.0
    assert 0.0 <= intent.desired_exposure_frac <= 1.0
    assert intent.horizon_hours >= 0
    assert isinstance(intent.reason, str) and len(intent.reason) > 0
    assert isinstance(intent.strategy_id, str) and len(intent.strategy_id) > 0
    if intent.action in (Action.EXIT_SHORT, Action.EXIT_LONG, Action.FLAT):
        assert intent.desired_exposure_frac == 0.0


# Minimum bars for the strategy to exit warmup
_MIN_BARS = crash_short_v2.DRAWDOWN_LOOKBACK + max(
    crash_short_v2.SLOW_EMA, crash_short_v2.MACRO_EMA, crash_short_v2.ATR_PERIOD
) + crash_short_v2.CONFIRM_BARS + crash_short_v2.MOMENTUM_LOOKBACK + 10


# ── Warmup ────────────────────────────────────────────────────────────────────

class TestCrashShortV2Warmup:
    def test_warmup_returns_flat_with_zero_confidence(self):
        df = _make_downtrend_df(n=100)
        intent = crash_short_v2.generate_intent(df, _ctx())
        assert intent.action == Action.FLAT
        assert intent.confidence == 0.0

    def test_warmup_boundary(self):
        df = _make_downtrend_df(n=_MIN_BARS - 1)
        intent = crash_short_v2.generate_intent(df, _ctx())
        assert intent.action == Action.FLAT
        assert intent.confidence == 0.0

    def test_warmup_strategy_id_still_set(self):
        df = _make_downtrend_df(n=50)
        intent = crash_short_v2.generate_intent(df, _ctx())
        assert intent.strategy_id == crash_short_v2.STRATEGY_ID


# ── Contract validity ─────────────────────────────────────────────────────────

class TestCrashShortV2Contract:
    def setup_method(self):
        self.df_down = _make_downtrend_df(n=_MIN_BARS + 200)
        self.df_flat = _make_flat_df(n=_MIN_BARS + 200)
        self.df_up   = _make_uptrend_df(n=_MIN_BARS + 200)

    def test_valid_intent_downtrend_context(self):
        intent = crash_short_v2.generate_intent(self.df_down, _ctx(regime=RegimeLabel.TREND_DOWN))
        _assert_valid_intent(intent)

    def test_valid_intent_uptrend_context(self):
        intent = crash_short_v2.generate_intent(self.df_up, _ctx(regime=RegimeLabel.TREND_UP))
        _assert_valid_intent(intent)

    def test_valid_intent_flat_data(self):
        intent = crash_short_v2.generate_intent(self.df_flat, _ctx(regime=RegimeLabel.RANGE))
        _assert_valid_intent(intent)

    def test_strategy_id(self):
        intent = crash_short_v2.generate_intent(self.df_down, _ctx())
        assert intent.strategy_id == crash_short_v2.STRATEGY_ID

    def test_exposure_zero_on_flat(self):
        intent = crash_short_v2.generate_intent(self.df_up, _ctx(regime=RegimeLabel.TREND_UP))
        assert intent.desired_exposure_frac == 0.0

    def test_enter_short_exposure_within_bounds(self):
        df = _make_downtrend_df(n=_MIN_BARS + 200)
        intent = crash_short_v2.generate_intent(df, _ctx(regime=RegimeLabel.TREND_DOWN))
        if intent.action == Action.ENTER_SHORT:
            assert 0.0 < intent.desired_exposure_frac <= 1.0

    def test_atr_cap_raised_vs_v1(self):
        """v2 entry ATR cap must be strictly higher than v1's 6.0%."""
        from research.strategies import crash_short_v1
        assert crash_short_v2.ENTRY_ATR_CAP > crash_short_v1.ENTRY_ATR_CAP

    def test_atr_persist_bars_configured(self):
        assert isinstance(crash_short_v2.ATR_PERSIST_BARS, int)
        assert crash_short_v2.ATR_PERSIST_BARS >= 2


# ── Entry gate behaviour ──────────────────────────────────────────────────────

class TestCrashShortV2EntryGates:
    def setup_method(self):
        self.df_down = _make_downtrend_df(n=_MIN_BARS + 200)
        self.df_up   = _make_uptrend_df(n=_MIN_BARS + 200)

    def test_no_entry_on_trend_up_regime(self):
        intent = crash_short_v2.generate_intent(
            self.df_up, _ctx(regime=RegimeLabel.TREND_UP, exposure=0.0)
        )
        assert intent.action in (Action.FLAT, Action.HOLD)
        assert intent.desired_exposure_frac == 0.0

    def test_no_entry_on_high_vol_regime(self):
        intent = crash_short_v2.generate_intent(
            self.df_down, _ctx(regime=RegimeLabel.HIGH_VOL, exposure=0.0)
        )
        assert intent.action in (Action.FLAT, Action.HOLD)

    def test_no_entry_on_range_regime(self):
        intent = crash_short_v2.generate_intent(
            self.df_down, _ctx(regime=RegimeLabel.RANGE, exposure=0.0)
        )
        assert intent.action in (Action.FLAT, Action.HOLD)

    def test_flat_bias_in_uptrend_data(self):
        for regime in (RegimeLabel.TREND_UP, RegimeLabel.RANGE, RegimeLabel.VOL_COMPRESSION):
            intent = crash_short_v2.generate_intent(
                self.df_up, _ctx(regime=regime, exposure=0.0)
            )
            assert intent.action in (Action.FLAT, Action.HOLD), (
                f"Unexpected entry in uptrend with regime={regime}"
            )

    def test_atr_persistence_gate_blocks_transient_spikes(self):
        """A single bar with ATR in range surrounded by out-of-range bars → still flat.

        Construct a DataFrame where the last bar's ATR is in the acceptable
        window but earlier bars are not, confirming the persistence gate fires.
        """
        # Use flat data (very low ATR) then append one volatile bar — the
        # persistence gate should block entry because prior bars are below MIN_ATR_PCT.
        rng = np.random.default_rng(123)
        n = _MIN_BARS + 10
        dates = pd.date_range("2019-01-01", periods=n, freq="1h")

        # Start from a high price so drawdown gate would otherwise not block
        price = 100_000.0
        rows = []
        for i in range(n - 1):
            # Strong downtrend, low ATR (below MIN_ATR_PCT)
            ret = -0.003
            price = max(100.0, price * (1 + ret))
            spread = price * 0.001  # tiny spread → ATR well below 2.5%
            rows.append({
                "open":  price,
                "high":  price + spread,
                "low":   max(1.0, price - spread),
                "close": price,
                "volume": 200.0,
            })
        # Last bar: ATR-compatible spike
        spike_spread = price * 0.035  # ~3.5% spread → ATR in range
        rows.append({
            "open":  price,
            "high":  price + spike_spread,
            "low":   max(1.0, price - spike_spread),
            "close": price * 0.97,
            "volume": 500.0,
        })
        df = pd.DataFrame(rows, index=dates)

        intent = crash_short_v2.generate_intent(df, _ctx(regime=RegimeLabel.TREND_DOWN))
        # ATR persistence gate should block entry — prior bars had ATR below MIN_ATR_PCT
        assert intent.action in (Action.FLAT, Action.HOLD)


# ── Exit / cover behaviour ────────────────────────────────────────────────────

class TestCrashShortV2Exits:
    def setup_method(self):
        self.df_flat = _make_flat_df(n=_MIN_BARS + 50)
        self.df_up   = _make_uptrend_df(n=_MIN_BARS + 50)

    def _short_ctx(self, regime: RegimeLabel) -> StrategyContext:
        return _ctx(regime=regime, exposure=0.5, signed_exposure=-0.5)

    def test_cover_on_vol_compression_low_atr(self):
        intent = crash_short_v2.generate_intent(
            self.df_flat, self._short_ctx(RegimeLabel.VOL_COMPRESSION)
        )
        assert intent.action == Action.EXIT_SHORT
        assert intent.desired_exposure_frac == 0.0

    def test_cover_on_range_low_atr(self):
        intent = crash_short_v2.generate_intent(
            self.df_flat, self._short_ctx(RegimeLabel.RANGE)
        )
        assert intent.action == Action.EXIT_SHORT

    def test_cover_on_vol_collapse_in_any_regime(self):
        for regime in (RegimeLabel.TREND_DOWN, RegimeLabel.RANGE, RegimeLabel.TREND_UP):
            intent = crash_short_v2.generate_intent(
                self.df_flat, self._short_ctx(regime)
            )
            assert intent.action == Action.EXIT_SHORT, (
                f"Expected EXIT_SHORT on low-ATR flat data, got {intent.action} for regime={regime}"
            )

    def test_hold_in_active_bear(self):
        df = _make_downtrend_df(n=_MIN_BARS + 50)
        intent = crash_short_v2.generate_intent(
            df, self._short_ctx(RegimeLabel.TREND_DOWN)
        )
        _assert_valid_intent(intent)
        if intent.action == Action.HOLD:
            assert intent.desired_exposure_frac > 0.0


# ── Determinism & side effects ────────────────────────────────────────────────

class TestCrashShortV2Determinism:
    def setup_method(self):
        self.df = _make_downtrend_df(n=_MIN_BARS + 100)
        self.ctx = _ctx(regime=RegimeLabel.TREND_DOWN)

    def test_deterministic_on_same_input(self):
        i1 = crash_short_v2.generate_intent(self.df, self.ctx)
        i2 = crash_short_v2.generate_intent(self.df, self.ctx)
        assert i1.action == i2.action
        assert i1.confidence == i2.confidence
        assert i1.desired_exposure_frac == i2.desired_exposure_frac
        assert i1.reason == i2.reason

    def test_no_dataframe_mutation(self):
        df_copy = self.df.copy()
        crash_short_v2.generate_intent(self.df, self.ctx)
        crash_short_v2.generate_intent(self.df, self.ctx)
        pd.testing.assert_frame_equal(self.df, df_copy)
