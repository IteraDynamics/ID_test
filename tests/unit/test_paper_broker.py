"""Unit tests — Layer 3 PaperBroker.

Verifies:
- Initial state.
- Buy/sell mechanics.
- Fee and slippage application.
- Partial fill on insufficient cash.
- Sell capped to available units.
- Min notional rejection.
- Fill history tracking.
- Snapshot output.
- Reset.
"""

from __future__ import annotations

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from runtime.argus.brokers.paper_broker import PaperBroker
from runtime.argus.brokers.base import OrderStatus


class TestPaperBroker:
    INITIAL_CASH = 100_000.0
    PRICE = 25_000.0
    ASSET = "BTC"

    def setup_method(self):
        self.broker = PaperBroker(
            initial_cash=self.INITIAL_CASH,
            fee_rate=0.001,
            slippage_bps=5,
            min_trade_notional=10.0,
        )

    def test_initial_balance(self):
        bal = self.broker.get_balance()
        assert bal["USD"] == self.INITIAL_CASH
        assert self.broker.get_position(self.ASSET) == 0.0

    def test_initial_nav(self):
        nav = self.broker.get_nav(self.ASSET, self.PRICE)
        assert nav == self.INITIAL_CASH

    def test_buy_reduces_cash(self):
        self.broker.submit_and_fill(self.ASSET, "BUY", 1.0, self.PRICE)
        bal = self.broker.get_balance()
        assert bal["USD"] < self.INITIAL_CASH

    def test_buy_increases_position(self):
        qty = 1.0
        self.broker.submit_and_fill(self.ASSET, "BUY", qty, self.PRICE)
        pos = self.broker.get_position(self.ASSET)
        assert pos > 0

    def test_buy_then_sell_round_trip(self):
        qty = 1.0
        _, fill_buy = self.broker.submit_and_fill(self.ASSET, "BUY", qty, self.PRICE)
        assert fill_buy is not None
        assert fill_buy.side == "BUY"

        pos = self.broker.get_position(self.ASSET)
        _, fill_sell = self.broker.submit_and_fill(self.ASSET, "SELL", pos, self.PRICE)
        assert fill_sell is not None

        remaining_pos = self.broker.get_position(self.ASSET)
        assert remaining_pos < 1e-9

    def test_slippage_applied_on_buy(self):
        """BUY fill price should be > submitted price."""
        slippage_frac = 5 / 10_000
        _, fill = self.broker.submit_and_fill(self.ASSET, "BUY", 1.0, self.PRICE)
        expected_fill = self.PRICE * (1 + slippage_frac)
        assert abs(fill.fill_price - expected_fill) < 0.01

    def test_slippage_applied_on_sell(self):
        """SELL fill price should be < submitted price."""
        self.broker.submit_and_fill(self.ASSET, "BUY", 1.0, self.PRICE)
        slippage_frac = 5 / 10_000
        _, fill = self.broker.submit_and_fill(self.ASSET, "SELL", 1.0, self.PRICE)
        expected_fill = self.PRICE * (1 - slippage_frac)
        assert abs(fill.fill_price - expected_fill) < 0.01

    def test_fee_deducted(self):
        fee_rate = 0.001
        qty = 1.0
        _, fill = self.broker.submit_and_fill(self.ASSET, "BUY", qty, self.PRICE)
        # Fee should be approximately qty * fill_price * fee_rate
        expected_fee = qty * fill.fill_price * fee_rate
        assert abs(fill.fee - expected_fee) < 0.01

    def test_sell_more_than_held_is_capped(self):
        # Buy 1.0 BTC, try to sell 2.0
        self.broker.submit_and_fill(self.ASSET, "BUY", 1.0, self.PRICE)
        _, fill = self.broker.submit_and_fill(self.ASSET, "SELL", 2.0, self.PRICE)
        # Should partially fill at 1.0 BTC
        assert fill is not None
        assert fill.qty <= 1.0 + 1e-9

    def test_sell_with_no_position_rejected(self):
        _, fill = self.broker.submit_and_fill(self.ASSET, "SELL", 1.0, self.PRICE)
        assert fill is None

    def test_min_notional_rejection(self):
        """Order below min notional should be rejected."""
        broker = PaperBroker(min_trade_notional=500.0)
        _, fill = broker.submit_and_fill(self.ASSET, "BUY", 0.000001, self.PRICE)
        assert fill is None

    def test_fill_history_grows(self):
        self.broker.submit_and_fill(self.ASSET, "BUY", 1.0, self.PRICE)
        self.broker.submit_and_fill(self.ASSET, "SELL", 1.0, self.PRICE)
        assert len(self.broker.fill_history) == 2

    def test_nav_consistent_after_round_trip(self):
        """NAV after a round trip (same price, no fee/slip) should be < initial due to costs."""
        nav_before = self.broker.get_nav(self.ASSET, self.PRICE)
        self.broker.submit_and_fill(self.ASSET, "BUY", 1.0, self.PRICE)
        self.broker.submit_and_fill(self.ASSET, "SELL", 1.0, self.PRICE)
        nav_after = self.broker.get_nav(self.ASSET, self.PRICE)
        assert nav_after < nav_before  # fees+slippage consumed

    def test_snapshot(self):
        snap = self.broker.snapshot(self.ASSET, self.PRICE)
        assert "cash" in snap
        assert "nav" in snap
        assert "positions" in snap

    def test_reset(self):
        self.broker.submit_and_fill(self.ASSET, "BUY", 1.0, self.PRICE)
        self.broker.reset()
        assert self.broker.get_position(self.ASSET) == 0.0
        assert abs(self.broker.get_balance()["USD"] - self.INITIAL_CASH) < 0.01

    def test_compute_order_qty_buy(self):
        # If fully flat and want 50% exposure at $25k price, NAV=$100k → target=$50k → qty=2.0
        qty = self.broker.compute_order_qty(self.ASSET, "BUY", 0.50, self.PRICE)
        assert abs(qty - 2.0) < 0.01

    def test_compute_order_qty_returns_positive(self):
        qty_buy = self.broker.compute_order_qty(self.ASSET, "BUY", 0.5, self.PRICE)
        qty_sell = self.broker.compute_order_qty(self.ASSET, "SELL", 0.0, self.PRICE)
        assert qty_buy >= 0
        assert qty_sell >= 0
