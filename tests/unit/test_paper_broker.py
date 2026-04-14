"""Unit tests — Layer 3 PaperBroker.

Verifies:
- Initial state.
- Buy/sell mechanics.
- Fee and slippage application (dynamic model via ExecutionConfig).
- Partial fill on insufficient cash.
- Sell capped to available units.
- Min notional rejection.
- Fill history tracking.
- Snapshot output.
- Reset.
- Cost fields present on Fill (slippage_usd, spread_usd, cost_bps, mid_price).
"""

from __future__ import annotations

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research.harness.execution_model import ExecutionConfig
from runtime.argus.brokers.paper_broker import PaperBroker
from runtime.argus.brokers.base import OrderStatus


def make_broker(fee_rate=0.001, min_notional=10.0, **cfg_overrides) -> PaperBroker:
    cfg = ExecutionConfig(taker_fee_rate=fee_rate)
    for k, v in cfg_overrides.items():
        setattr(cfg, k, v)
    return PaperBroker(
        initial_cash=100_000.0,
        exec_config=cfg,
        min_trade_notional=min_notional,
    )


class TestPaperBroker:
    INITIAL_CASH = 100_000.0
    PRICE = 25_000.0
    ASSET = "BTC"

    def setup_method(self):
        self.broker = make_broker()

    # ── Initial state ─────────────────────────────────────────────────────────

    def test_initial_balance(self):
        bal = self.broker.get_balance()
        assert bal["USD"] == self.INITIAL_CASH
        assert self.broker.get_position(self.ASSET) == 0.0

    def test_initial_nav(self):
        nav = self.broker.get_nav(self.ASSET, self.PRICE)
        assert nav == self.INITIAL_CASH

    # ── Buy/sell mechanics ────────────────────────────────────────────────────

    def test_buy_reduces_cash(self):
        self.broker.submit_and_fill(self.ASSET, "BUY", 1.0, self.PRICE)
        bal = self.broker.get_balance()
        assert bal["USD"] < self.INITIAL_CASH

    def test_buy_increases_position(self):
        self.broker.submit_and_fill(self.ASSET, "BUY", 1.0, self.PRICE)
        assert self.broker.get_position(self.ASSET) > 0

    def test_buy_then_sell_round_trip(self):
        _, fill_buy = self.broker.submit_and_fill(self.ASSET, "BUY", 1.0, self.PRICE)
        assert fill_buy is not None and fill_buy.side == "BUY"

        pos = self.broker.get_position(self.ASSET)
        _, fill_sell = self.broker.submit_and_fill(self.ASSET, "SELL", pos, self.PRICE)
        assert fill_sell is not None

        assert self.broker.get_position(self.ASSET) < 1e-9

    # ── Dynamic slippage ──────────────────────────────────────────────────────

    def test_buy_fill_price_above_mid(self):
        """BUY fill price must always be > the submitted mid price."""
        _, fill = self.broker.submit_and_fill(self.ASSET, "BUY", 1.0, self.PRICE)
        assert fill.fill_price > self.PRICE

    def test_sell_fill_price_below_mid(self):
        """SELL fill price must always be < the submitted mid price."""
        self.broker.submit_and_fill(self.ASSET, "BUY", 1.0, self.PRICE)
        _, fill = self.broker.submit_and_fill(self.ASSET, "SELL", 1.0, self.PRICE)
        assert fill.fill_price < self.PRICE

    def test_fill_price_more_adverse_with_high_atr(self):
        """Higher ATR -> worse fill price (more slippage + spread)."""
        b_calm = make_broker()
        b_vol = make_broker()

        _, f_calm = b_calm.submit_and_fill(self.ASSET, "BUY", 1.0, self.PRICE, atr_pct=0.005)
        _, f_vol  = b_vol.submit_and_fill(self.ASSET,  "BUY", 1.0, self.PRICE, atr_pct=0.05)

        assert f_vol.fill_price > f_calm.fill_price

    def test_fill_has_cost_fields(self):
        """Fill object must carry mid_price, slippage_usd, spread_usd, cost_bps."""
        _, fill = self.broker.submit_and_fill(self.ASSET, "BUY", 1.0, self.PRICE, atr_pct=0.02)
        assert fill.mid_price == self.PRICE
        assert fill.slippage_usd >= 0.0
        assert fill.spread_usd >= 0.0
        assert fill.cost_bps > 0.0

    # ── Fee ───────────────────────────────────────────────────────────────────

    def test_fee_deducted(self):
        _, fill = self.broker.submit_and_fill(self.ASSET, "BUY", 1.0, self.PRICE)
        assert fill.fee > 0.0

    def test_nav_reduced_by_round_trip_costs(self):
        """NAV after a round trip at the same price must be < initial (costs consumed)."""
        nav_before = self.broker.get_nav(self.ASSET, self.PRICE)
        self.broker.submit_and_fill(self.ASSET, "BUY", 1.0, self.PRICE)
        self.broker.submit_and_fill(self.ASSET, "SELL", 1.0, self.PRICE)
        nav_after = self.broker.get_nav(self.ASSET, self.PRICE)
        assert nav_after < nav_before

    # ── Edge cases ────────────────────────────────────────────────────────────

    def test_sell_more_than_held_is_capped(self):
        self.broker.submit_and_fill(self.ASSET, "BUY", 1.0, self.PRICE)
        _, fill = self.broker.submit_and_fill(self.ASSET, "SELL", 2.0, self.PRICE)
        assert fill is not None
        assert fill.qty <= 1.0 + 1e-9

    def test_sell_with_no_position_rejected(self):
        _, fill = self.broker.submit_and_fill(self.ASSET, "SELL", 1.0, self.PRICE)
        assert fill is None

    def test_min_notional_rejection(self):
        broker = PaperBroker(min_trade_notional=500.0)
        _, fill = broker.submit_and_fill(self.ASSET, "BUY", 0.000001, self.PRICE)
        assert fill is None

    # ── History and state ─────────────────────────────────────────────────────

    def test_fill_history_grows(self):
        self.broker.submit_and_fill(self.ASSET, "BUY", 1.0, self.PRICE)
        self.broker.submit_and_fill(self.ASSET, "SELL", 1.0, self.PRICE)
        assert len(self.broker.fill_history) == 2

    def test_snapshot(self):
        snap = self.broker.snapshot(self.ASSET, self.PRICE)
        assert "cash" in snap and "nav" in snap and "positions" in snap

    def test_reset(self):
        self.broker.submit_and_fill(self.ASSET, "BUY", 1.0, self.PRICE)
        self.broker.reset()
        assert self.broker.get_position(self.ASSET) == 0.0
        assert abs(self.broker.get_balance()["USD"] - self.INITIAL_CASH) < 0.01

    # ── compute_order_qty (on BaseBroker) ─────────────────────────────────────

    def test_compute_order_qty_buy(self):
        # Fully flat, want 50% exposure at $25k price, NAV=$100k -> target=$50k -> qty=2.0
        qty = self.broker.compute_order_qty(self.ASSET, "BUY", 0.50, self.PRICE)
        assert abs(qty - 2.0) < 0.01

    def test_compute_order_qty_returns_positive(self):
        qty_buy = self.broker.compute_order_qty(self.ASSET, "BUY", 0.5, self.PRICE)
        qty_sell = self.broker.compute_order_qty(self.ASSET, "SELL", 0.0, self.PRICE)
        assert qty_buy >= 0
        assert qty_sell >= 0

    # ── Legacy kwargs ─────────────────────────────────────────────────────────

    def test_legacy_fee_rate_kwarg(self):
        """Passing fee_rate= directly still works."""
        broker = PaperBroker(initial_cash=100_000.0, fee_rate=0.002)
        _, fill = broker.submit_and_fill(self.ASSET, "BUY", 1.0, self.PRICE)
        notional = 1.0 * self.PRICE
        assert fill.fee >= notional * 0.002 - 1.0
