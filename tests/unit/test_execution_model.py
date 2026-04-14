"""Unit tests — execution model.

Verifies:
- Fees reduce NAV correctly.
- Slippage increases with trade size.
- Slippage increases with volatility.
- Nonlinear penalty fires above large_trade_threshold.
- Spread cost is always >= min_spread.
- Effective price is always adverse (BUY higher, SELL lower) than mid.
- Zero notional / zero nav handled safely.
- Determinism: same inputs -> identical outputs.
- Maker fee used when use_maker_fees=True.
- Max slippage cap enforced.
- ATR series is causal (no lookahead).
"""

from __future__ import annotations

import sys
from pathlib import Path
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research.harness.execution_model import (
    ExecutionConfig,
    FillResult,
    compute_fill,
    compute_atr_pct_series,
    compute_atr_pct_scalar,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def default_cfg(**overrides) -> ExecutionConfig:
    cfg = ExecutionConfig()
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def fill(direction="BUY", notional=10_000.0, nav=100_000.0, atr_pct=0.02, **cfg_overrides):
    cfg = default_cfg(**cfg_overrides)
    return compute_fill(
        mid_price=50_000.0,
        notional=notional,
        nav=nav,
        atr_pct=atr_pct,
        direction=direction,
        config=cfg,
    )


# ── Fee tests ─────────────────────────────────────────────────────────────────

class TestFees:
    def test_taker_fee_applied(self):
        r = fill(taker_fee_rate=0.001)
        expected = 10_000.0 * 0.001
        assert abs(r.fee_usd - expected) < 0.01

    def test_maker_fee_used_when_flag_set(self):
        r_taker = fill(taker_fee_rate=0.001, maker_fee_rate=0.0002, use_maker_fees=False)
        r_maker = fill(taker_fee_rate=0.001, maker_fee_rate=0.0002, use_maker_fees=True)
        assert r_maker.fee_usd < r_taker.fee_usd
        assert abs(r_maker.fee_usd - 10_000.0 * 0.0002) < 0.01

    def test_zero_notional_fee_is_zero(self):
        r = fill(notional=0.0)
        assert r.fee_usd == 0.0

    def test_fee_reduces_total_cost(self):
        r_no_fee = fill(taker_fee_rate=0.0)
        r_fee = fill(taker_fee_rate=0.001)
        assert r_fee.total_cost_usd > r_no_fee.total_cost_usd


# ── Slippage tests ────────────────────────────────────────────────────────────

class TestSlippage:
    def test_slippage_increases_with_trade_size(self):
        r_small = fill(notional=1_000.0,  nav=100_000.0)
        r_large = fill(notional=50_000.0, nav=100_000.0)
        assert r_large.slippage_bps_applied > r_small.slippage_bps_applied

    def test_slippage_increases_with_volatility(self):
        r_calm = fill(atr_pct=0.005)
        r_vol  = fill(atr_pct=0.05)
        assert r_vol.slippage_bps_applied > r_calm.slippage_bps_applied

    def test_slippage_never_below_min(self):
        r = fill(atr_pct=0.0, notional=1.0, min_slippage_bps=2.0)
        assert r.slippage_bps_applied >= 2.0

    def test_slippage_never_above_max(self):
        # Enormous trade + high vol should still hit the cap
        r = fill(notional=200_000.0, nav=100_000.0, atr_pct=1.0, max_slippage_bps=30.0)
        assert r.slippage_bps_applied <= 30.0 + 1e-9

    def test_nonlinear_penalty_fires_above_threshold(self):
        """Above large_trade_threshold the total slippage bps exceed the linear model."""
        # A config with no nonlinear penalty (threshold > 100% NAV, i.e. never fires)
        r_linear = fill(notional=35_000.0, nav=100_000.0, large_trade_threshold=2.0)
        # Same config but threshold at 25% so nonlinear kicks in at 35k
        r_nonlinear = fill(notional=35_000.0, nav=100_000.0, large_trade_threshold=0.25)
        assert r_nonlinear.slippage_bps_applied > r_linear.slippage_bps_applied


# ── Spread tests ──────────────────────────────────────────────────────────────

class TestSpread:
    def test_spread_always_positive(self):
        r = fill(atr_pct=0.0)
        assert r.spread_usd >= 0.0

    def test_spread_at_least_min_spread(self):
        r = fill(atr_pct=0.0, min_spread_bps=2.0)
        half_spread_usd = 10_000.0 * (2.0 / 10_000.0)
        assert r.spread_usd >= half_spread_usd - 1e-9

    def test_spread_scales_with_volatility(self):
        r_calm = fill(atr_pct=0.001)
        r_vol  = fill(atr_pct=0.05)
        assert r_vol.spread_usd >= r_calm.spread_usd


# ── Effective price tests ─────────────────────────────────────────────────────

class TestEffectivePrice:
    MID = 50_000.0

    def test_buy_effective_price_above_mid(self):
        r = fill(direction="BUY")
        assert r.effective_price > self.MID

    def test_sell_effective_price_below_mid(self):
        r = fill(direction="SELL")
        assert r.effective_price < self.MID

    def test_mid_price_stored(self):
        r = fill()
        assert r.mid_price == self.MID

    def test_zero_atr_still_adverse(self):
        """Even with zero vol there is base slippage + min spread."""
        r_buy  = fill(direction="BUY",  atr_pct=0.0)
        r_sell = fill(direction="SELL", atr_pct=0.0)
        assert r_buy.effective_price > self.MID
        assert r_sell.effective_price < self.MID


# ── Cost bps tests ────────────────────────────────────────────────────────────

class TestCostBps:
    def test_cost_bps_positive(self):
        r = fill()
        assert r.cost_bps > 0.0

    def test_cost_bps_equals_components(self):
        r = fill(notional=10_000.0)
        expected = (r.fee_usd + r.slippage_usd + r.spread_usd) / 10_000.0 * 10_000.0
        assert abs(r.cost_bps - expected) < 1e-6

    def test_total_cost_equals_sum(self):
        r = fill()
        assert abs(r.total_cost_usd - (r.fee_usd + r.slippage_usd + r.spread_usd)) < 1e-9

    def test_zero_notional_cost_bps_is_zero(self):
        r = fill(notional=0.0)
        assert r.cost_bps == 0.0


# ── Determinism ───────────────────────────────────────────────────────────────

class TestDeterminism:
    def test_same_inputs_same_output(self):
        r1 = fill(direction="BUY", notional=15_000.0, atr_pct=0.03)
        r2 = fill(direction="BUY", notional=15_000.0, atr_pct=0.03)
        assert r1.effective_price == r2.effective_price
        assert r1.fee_usd == r2.fee_usd
        assert r1.cost_bps == r2.cost_bps

    def test_buy_and_sell_differ(self):
        r_buy  = fill(direction="BUY")
        r_sell = fill(direction="SELL")
        assert r_buy.effective_price != r_sell.effective_price


# ── ATR series ────────────────────────────────────────────────────────────────

class TestAtrSeries:
    @pytest.fixture
    def df(self):
        np.random.seed(42)
        n = 200
        prices = 30_000.0 * np.exp(np.cumsum(np.random.randn(n) * 0.02))
        idx = pd.date_range("2023-01-01", periods=n, freq="1h")
        return pd.DataFrame({
            "open":   prices * 0.999,
            "high":   prices * 1.005,
            "low":    prices * 0.995,
            "close":  prices,
            "volume": np.ones(n) * 100,
        }, index=idx)

    def test_series_length_matches_df(self, df):
        atr = compute_atr_pct_series(df)
        assert len(atr) == len(df)

    def test_all_values_non_negative(self, df):
        atr = compute_atr_pct_series(df)
        assert (atr >= 0).all()

    def test_scalar_matches_last_of_series(self, df):
        series = compute_atr_pct_series(df)
        scalar = compute_atr_pct_scalar(df)
        assert abs(scalar - float(series.iloc[-1])) < 1e-12

    def test_no_lookahead(self, df):
        """ATR at bar 50 must be the same whether computed on 51 bars or full df."""
        full = compute_atr_pct_series(df)
        short = compute_atr_pct_series(df.iloc[:51])
        assert abs(float(full.iloc[50]) - float(short.iloc[-1])) < 1e-10

    def test_empty_df_returns_zero(self):
        df = pd.DataFrame({"open": [], "high": [], "low": [], "close": [], "volume": []})
        scalar = compute_atr_pct_scalar(df)
        assert scalar == 0.0


# ── ExecutionConfig.from_env ──────────────────────────────────────────────────

class TestExecutionConfig:
    def test_defaults_are_sensible(self):
        cfg = ExecutionConfig()
        assert 0 < cfg.taker_fee_rate < 0.01
        assert cfg.base_slippage_bps > 0
        assert cfg.min_slippage_bps <= cfg.max_slippage_bps
        assert cfg.cooldown_bars >= 0

    def test_from_env_returns_config(self, monkeypatch):
        monkeypatch.setenv("FEE_RATE", "0.001")
        monkeypatch.setenv("COOLDOWN_BARS", "3")
        cfg = ExecutionConfig.from_env()
        assert abs(cfg.taker_fee_rate - 0.001) < 1e-9
        assert cfg.cooldown_bars == 3
