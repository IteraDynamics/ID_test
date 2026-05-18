"""Accounting invariant tests — capital conservation, PnL, fees, slippage.

Verifies every invariant from the fund_v1 accounting audit:
1. Cash + position_value == NAV (conservation)
2. BUY: cash decreases by fill_price*qty + fee (slippage hits cash)
3. SELL: cash increases by fill_price*qty - fee (slippage hits cash)
4. No negative cash without leverage
5. Realized PnL is correct on close
6. Unrealized PnL is correct mark-to-market
7. total_pnl = realized + unrealized
8. NAV identity: initial_cash - cumulative_fees + total_pnl == NAV
9. Cumulative fees and slippage are tracked
10. Avg entry price is VWAP on adds
11. Avg entry clears on full close
12. NAV conservation check returns ~0 drift
13. Snapshot contains all required fields
14. Partial BUY stays solvent (no negative cash)
"""

from __future__ import annotations

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research.harness.execution_model import ExecutionConfig
from runtime.argus.brokers.paper_broker import PaperBroker
from runtime.argus.brokers.base import OrderStatus

INITIAL_CASH = 100_000.0
PRICE = 50_000.0
ASSET = "BTC"
TOL = 0.01  # dollar tolerance for float comparisons


def make_broker(fee_rate=0.0006, slippage_bps=3.0, min_notional=10.0) -> PaperBroker:
    cfg = ExecutionConfig(
        taker_fee_rate=fee_rate,
        base_slippage_bps=slippage_bps,
        slippage_size_factor=0.0,   # disable size-based slippage for predictability
        slippage_vol_factor=0.0,    # disable vol-based slippage for predictability
        min_slippage_bps=slippage_bps,
        spread_k=0.0,
        min_spread_bps=0.0,
    )
    return PaperBroker(
        initial_cash=INITIAL_CASH,
        exec_config=cfg,
        min_trade_notional=min_notional,
    )


class TestNAVConservation:
    """cash + position_value == NAV at every point."""

    def _check_nav(self, broker: PaperBroker, price: float) -> None:
        cash = broker.get_balance()["USD"]
        pos = broker.get_position(ASSET)
        nav = broker.get_nav(ASSET, price)
        assert abs(cash + pos * price - nav) < TOL, (
            f"NAV drift: cash={cash:.4f} pos={pos:.8f} price={price} "
            f"computed={cash + pos*price:.4f} nav={nav:.4f}"
        )

    def test_nav_conservation_initial(self):
        b = make_broker()
        self._check_nav(b, PRICE)

    def test_nav_conservation_after_buy(self):
        b = make_broker()
        b.submit_and_fill(ASSET, "BUY", 0.5, PRICE)
        self._check_nav(b, PRICE)

    def test_nav_conservation_after_sell(self):
        b = make_broker()
        b.submit_and_fill(ASSET, "BUY", 0.5, PRICE)
        b.submit_and_fill(ASSET, "SELL", 0.5, PRICE)
        self._check_nav(b, PRICE)

    def test_nav_conservation_price_change(self):
        b = make_broker()
        b.submit_and_fill(ASSET, "BUY", 0.5, PRICE)
        new_price = 55_000.0
        self._check_nav(b, new_price)

    def test_nav_conservation_multiple_buys(self):
        b = make_broker()
        b.submit_and_fill(ASSET, "BUY", 0.2, PRICE)
        b.submit_and_fill(ASSET, "BUY", 0.3, PRICE)
        self._check_nav(b, PRICE)

    def test_check_nav_conservation_method_returns_zero(self):
        b = make_broker()
        b.submit_and_fill(ASSET, "BUY", 0.5, PRICE)
        drift = b.check_nav_conservation(ASSET, PRICE)
        assert abs(drift) < TOL


class TestCashAccounting:
    """Exact cash flows: BUY debits fill_price*qty+fee; SELL credits fill_price*qty-fee."""

    def test_buy_cash_deduction_includes_slippage(self):
        """cash_before - cash_after must equal fill_price*qty + fee (not mid*qty + fee)."""
        b = make_broker(fee_rate=0.0006, slippage_bps=10.0)
        cash_before = b.get_balance()["USD"]
        _, fill = b.submit_and_fill(ASSET, "BUY", 1.0, PRICE)
        assert fill is not None
        cash_after = b.get_balance()["USD"]

        expected_deduction = fill.qty * fill.fill_price + fill.fee
        actual_deduction = cash_before - cash_after
        assert abs(actual_deduction - expected_deduction) < TOL, (
            f"BUY deduction wrong: expected={expected_deduction:.4f} got={actual_deduction:.4f}"
        )

    def test_buy_fill_price_above_mid_increases_cash_cost(self):
        """With slippage, cash deduction must be > qty*mid_price + fee."""
        b_no_slip = make_broker(slippage_bps=0.0, fee_rate=0.0006)
        b_slip = make_broker(slippage_bps=20.0, fee_rate=0.0006)

        cash0_ns = b_no_slip.get_balance()["USD"]
        _, f_ns = b_no_slip.submit_and_fill(ASSET, "BUY", 1.0, PRICE)
        deduction_ns = cash0_ns - b_no_slip.get_balance()["USD"]

        cash0_s = b_slip.get_balance()["USD"]
        _, f_s = b_slip.submit_and_fill(ASSET, "BUY", 1.0, PRICE)
        deduction_s = cash0_s - b_slip.get_balance()["USD"]

        assert deduction_s > deduction_ns, (
            "Higher slippage must produce a larger cash deduction"
        )

    def test_sell_cash_receipt_includes_slippage(self):
        """cash_after - cash_before must equal fill_price*qty - fee (not mid*qty - fee)."""
        b = make_broker(fee_rate=0.0006, slippage_bps=10.0)
        b.submit_and_fill(ASSET, "BUY", 1.0, PRICE)
        cash_before = b.get_balance()["USD"]
        _, fill = b.submit_and_fill(ASSET, "SELL", 1.0, PRICE)
        assert fill is not None
        cash_after = b.get_balance()["USD"]

        expected_receipt = fill.qty * fill.fill_price - fill.fee
        actual_receipt = cash_after - cash_before
        assert abs(actual_receipt - expected_receipt) < TOL, (
            f"SELL receipt wrong: expected={expected_receipt:.4f} got={actual_receipt:.4f}"
        )

    def test_sell_fill_price_below_mid_reduces_cash_receipt(self):
        """With slippage, cash receipt from sell must be < qty*mid_price."""
        b = make_broker(slippage_bps=20.0, fee_rate=0.0)  # zero fee, pure slippage
        b.submit_and_fill(ASSET, "BUY", 1.0, PRICE)
        cash_before = b.get_balance()["USD"]
        _, fill = b.submit_and_fill(ASSET, "SELL", 1.0, PRICE)
        cash_after = b.get_balance()["USD"]

        mid_notional = 1.0 * PRICE
        receipt = cash_after - cash_before
        assert receipt < mid_notional, (
            f"SELL receipt {receipt:.2f} must be < mid notional {mid_notional:.2f}"
        )


class TestFeeAccounting:
    """Fee is always deducted from cash; cumulative tracked correctly."""

    def test_fee_charged_on_buy(self):
        b = make_broker(fee_rate=0.001, slippage_bps=0.0)
        _, fill = b.submit_and_fill(ASSET, "BUY", 1.0, PRICE)
        assert fill.fee > 0

    def test_fee_charged_on_sell(self):
        b = make_broker(fee_rate=0.001, slippage_bps=0.0)
        b.submit_and_fill(ASSET, "BUY", 1.0, PRICE)
        _, fill = b.submit_and_fill(ASSET, "SELL", 1.0, PRICE)
        assert fill.fee > 0

    def test_cumulative_fees_accumulate(self):
        b = make_broker(fee_rate=0.001)
        _, f1 = b.submit_and_fill(ASSET, "BUY", 1.0, PRICE)
        _, f2 = b.submit_and_fill(ASSET, "SELL", 1.0, PRICE)
        assert abs(b.get_cumulative_fees() - (f1.fee + f2.fee)) < TOL

    def test_fee_on_fill_price_notional(self):
        """Fee is charged on fill_price*qty, not mid_price*qty."""
        b = make_broker(fee_rate=0.001, slippage_bps=10.0)
        _, fill = b.submit_and_fill(ASSET, "BUY", 1.0, PRICE)
        expected_fee = fill.qty * fill.fill_price * 0.001
        assert abs(fill.fee - expected_fee) < TOL, (
            f"Fee should be on fill notional: expected={expected_fee:.4f} got={fill.fee:.4f}"
        )

    def test_zero_fee_rate_no_fee(self):
        b = make_broker(fee_rate=0.0)
        _, fill = b.submit_and_fill(ASSET, "BUY", 1.0, PRICE)
        assert fill.fee == 0.0


class TestSlippageAccounting:
    """Slippage is embedded in fill_price and actually hits NAV."""

    def test_slippage_reduces_nav_on_buy(self):
        """NAV immediately after BUY at same price must be lower with slippage than without."""
        b_no = make_broker(slippage_bps=0.0, fee_rate=0.0)
        b_sl = make_broker(slippage_bps=20.0, fee_rate=0.0)

        b_no.submit_and_fill(ASSET, "BUY", 1.0, PRICE)
        b_sl.submit_and_fill(ASSET, "BUY", 1.0, PRICE)

        nav_no = b_no.get_nav(ASSET, PRICE)
        nav_sl = b_sl.get_nav(ASSET, PRICE)
        assert nav_sl < nav_no, "Slippage on BUY must reduce NAV"

    def test_slippage_reduces_nav_on_sell(self):
        """Round-trip NAV must be lower with sell slippage than without."""
        b_no = make_broker(slippage_bps=0.0, fee_rate=0.0)
        b_sl = make_broker(slippage_bps=20.0, fee_rate=0.0)

        for b in (b_no, b_sl):
            b.submit_and_fill(ASSET, "BUY", 1.0, PRICE)
            b.submit_and_fill(ASSET, "SELL", 1.0, PRICE)

        assert b_sl.get_nav(ASSET, PRICE) < b_no.get_nav(ASSET, PRICE), (
            "Slippage on SELL must reduce NAV"
        )

    def test_slippage_tracked_cumulatively(self):
        b = make_broker(slippage_bps=10.0, fee_rate=0.0)
        _, f1 = b.submit_and_fill(ASSET, "BUY", 1.0, PRICE)
        assert b.get_cumulative_slippage() > 0

    def test_buy_fill_price_above_mid(self):
        b = make_broker(slippage_bps=10.0)
        _, fill = b.submit_and_fill(ASSET, "BUY", 1.0, PRICE)
        assert fill.fill_price > PRICE

    def test_sell_fill_price_below_mid(self):
        b = make_broker(slippage_bps=10.0)
        b.submit_and_fill(ASSET, "BUY", 1.0, PRICE)
        _, fill = b.submit_and_fill(ASSET, "SELL", 1.0, PRICE)
        assert fill.fill_price < PRICE


class TestPnLTracking:
    """Realized, unrealized, and total PnL are correct."""

    def test_unrealized_pnl_zero_when_flat(self):
        b = make_broker()
        assert b.get_unrealized_pnl(ASSET, PRICE) == 0.0

    def test_unrealized_pnl_after_buy_at_same_price(self):
        """Just after buy at fill_price, unrealized PnL is negative (fill > mid)."""
        b = make_broker(slippage_bps=10.0, fee_rate=0.0)
        _, fill = b.submit_and_fill(ASSET, "BUY", 1.0, PRICE)
        # position is at avg_entry = fill_price (> mid_price = PRICE)
        upnl = b.get_unrealized_pnl(ASSET, PRICE)
        assert upnl < 0, f"Unrealized PnL should reflect slippage cost, got {upnl}"

    def test_unrealized_pnl_follows_price(self):
        """Unrealized PnL increases when price rises above entry."""
        b = make_broker(slippage_bps=0.0, fee_rate=0.0)
        _, fill = b.submit_and_fill(ASSET, "BUY", 1.0, PRICE)
        upnl_flat = b.get_unrealized_pnl(ASSET, PRICE)
        upnl_up = b.get_unrealized_pnl(ASSET, PRICE * 1.10)
        assert upnl_up > upnl_flat

    def test_realized_pnl_zero_before_any_sell(self):
        b = make_broker()
        b.submit_and_fill(ASSET, "BUY", 1.0, PRICE)
        assert b.get_realized_pnl(ASSET) == 0.0

    def test_realized_pnl_on_profitable_close(self):
        """Sell at higher price → positive realized PnL."""
        b = make_broker(slippage_bps=0.0, fee_rate=0.0)
        _, buy_fill = b.submit_and_fill(ASSET, "BUY", 1.0, PRICE)
        sell_price = PRICE * 1.10
        _, sell_fill = b.submit_and_fill(ASSET, "SELL", 1.0, sell_price)
        realized = b.get_realized_pnl(ASSET)
        expected = 1.0 * (sell_fill.fill_price - buy_fill.fill_price)
        assert abs(realized - expected) < TOL, (
            f"Realized PnL: expected={expected:.4f} got={realized:.4f}"
        )

    def test_realized_pnl_on_losing_close(self):
        """Sell at lower price → negative realized PnL."""
        b = make_broker(slippage_bps=0.0, fee_rate=0.0)
        b.submit_and_fill(ASSET, "BUY", 1.0, PRICE)
        sell_price = PRICE * 0.90
        b.submit_and_fill(ASSET, "SELL", 1.0, sell_price)
        assert b.get_realized_pnl(ASSET) < 0

    def test_total_pnl_equals_realized_plus_unrealized(self):
        b = make_broker(slippage_bps=5.0, fee_rate=0.001)
        b.submit_and_fill(ASSET, "BUY", 1.0, PRICE)
        check_price = PRICE * 1.05
        total = b.get_total_pnl(ASSET, check_price)
        r = b.get_realized_pnl(ASSET)
        u = b.get_unrealized_pnl(ASSET, check_price)
        assert abs(total - (r + u)) < TOL

    def test_unrealized_clears_after_full_close(self):
        b = make_broker(slippage_bps=0.0, fee_rate=0.0)
        b.submit_and_fill(ASSET, "BUY", 1.0, PRICE)
        b.submit_and_fill(ASSET, "SELL", 1.0, PRICE)
        assert abs(b.get_unrealized_pnl(ASSET, PRICE)) < TOL

    def test_nav_identity_holds(self):
        """NAV = initial_cash - cumulative_fees + realized + unrealized."""
        b = make_broker(slippage_bps=5.0, fee_rate=0.001)
        b.submit_and_fill(ASSET, "BUY", 1.0, PRICE)
        check_price = PRICE * 1.08
        nav = b.get_nav(ASSET, check_price)
        fees = b.get_cumulative_fees()
        realized = b.get_realized_pnl(ASSET)
        unrealized = b.get_unrealized_pnl(ASSET, check_price)
        identity = INITIAL_CASH - fees + realized + unrealized
        assert abs(nav - identity) < TOL, (
            f"NAV identity failed: NAV={nav:.4f} identity={identity:.4f}"
        )

    def test_nav_identity_after_round_trip(self):
        b = make_broker(slippage_bps=5.0, fee_rate=0.001)
        sell_price = PRICE * 1.05
        b.submit_and_fill(ASSET, "BUY", 1.0, PRICE)
        b.submit_and_fill(ASSET, "SELL", 1.0, sell_price)
        nav = b.get_nav(ASSET, sell_price)
        fees = b.get_cumulative_fees()
        realized = b.get_realized_pnl(ASSET)
        unrealized = b.get_unrealized_pnl(ASSET, sell_price)
        identity = INITIAL_CASH - fees + realized + unrealized
        assert abs(nav - identity) < TOL


class TestAvgEntryPrice:
    """VWAP avg entry price is correct on adds and clears on close."""

    def test_avg_entry_is_fill_price_on_first_buy(self):
        b = make_broker(slippage_bps=10.0, fee_rate=0.0)
        _, fill = b.submit_and_fill(ASSET, "BUY", 1.0, PRICE)
        assert abs(b.get_avg_entry_price(ASSET) - fill.fill_price) < TOL

    def test_avg_entry_zero_when_flat(self):
        b = make_broker()
        assert b.get_avg_entry_price(ASSET) == 0.0

    def test_avg_entry_is_vwap_on_two_buys(self):
        b = make_broker(slippage_bps=0.0, fee_rate=0.0)
        # Use small quantities so both buys fully fill (no partial fills)
        _, f1 = b.submit_and_fill(ASSET, "BUY", 0.5, PRICE)
        price2 = PRICE * 1.10
        _, f2 = b.submit_and_fill(ASSET, "BUY", 0.5, price2)
        expected = (f1.qty * f1.fill_price + f2.qty * f2.fill_price) / (f1.qty + f2.qty)
        assert abs(b.get_avg_entry_price(ASSET) - expected) < TOL

    def test_avg_entry_clears_after_full_close(self):
        b = make_broker()
        b.submit_and_fill(ASSET, "BUY", 1.0, PRICE)
        b.submit_and_fill(ASSET, "SELL", 1.0, PRICE)
        assert b.get_avg_entry_price(ASSET) == 0.0

    def test_avg_entry_unchanged_after_partial_sell(self):
        b = make_broker(slippage_bps=0.0, fee_rate=0.0)
        _, buy = b.submit_and_fill(ASSET, "BUY", 2.0, PRICE)
        entry_before = b.get_avg_entry_price(ASSET)
        b.submit_and_fill(ASSET, "SELL", 1.0, PRICE)
        entry_after = b.get_avg_entry_price(ASSET)
        # partial sell should not change avg entry (standard accounting)
        assert abs(entry_before - entry_after) < TOL


class TestNoNegativeCash:
    """Cash must never go negative without leverage."""

    def test_no_negative_cash_full_buy(self):
        b = make_broker()
        b.submit_and_fill(ASSET, "BUY", 10.0, PRICE)  # would cost $500k on $100k cash → partial
        assert b.get_balance()["USD"] >= -TOL

    def test_no_negative_cash_partial_fill(self):
        """Partial fill must leave cash >= 0."""
        b = make_broker(fee_rate=0.001, slippage_bps=5.0)
        # Order larger than full cash
        b.submit_and_fill(ASSET, "BUY", 100.0, PRICE)
        cash = b.get_balance()["USD"]
        assert cash >= -TOL, f"Cash went negative: {cash:.4f}"

    def test_no_negative_cash_exact_remaining(self):
        """After a maxed-out partial fill, cash should be approximately zero."""
        b = make_broker(fee_rate=0.001, slippage_bps=5.0, min_notional=1.0)
        b.submit_and_fill(ASSET, "BUY", 100.0, PRICE)
        cash = b.get_balance()["USD"]
        # Cash should be near zero (partial fill consumed all available cash)
        assert cash >= -TOL
        assert cash < 10.0, f"Too much cash remaining after oversized order: {cash:.4f}"


class TestSnapshotFields:
    """Snapshot must include all required accounting fields."""

    REQUIRED_FIELDS = {
        "cash", "positions", "avg_entry_price", "nav",
        "realized_pnl", "unrealized_pnl", "total_pnl",
        "cumulative_fees", "cumulative_slippage", "n_fills",
    }

    def test_snapshot_has_all_fields(self):
        b = make_broker()
        snap = b.snapshot(ASSET, PRICE)
        missing = self.REQUIRED_FIELDS - snap.keys()
        assert not missing, f"Snapshot missing fields: {missing}"

    def test_snapshot_nav_matches_get_nav(self):
        b = make_broker()
        b.submit_and_fill(ASSET, "BUY", 0.5, PRICE)
        snap = b.snapshot(ASSET, PRICE)
        assert abs(snap["nav"] - b.get_nav(ASSET, PRICE)) < TOL

    def test_snapshot_pnl_consistent(self):
        b = make_broker(slippage_bps=5.0)
        b.submit_and_fill(ASSET, "BUY", 0.5, PRICE)
        snap = b.snapshot(ASSET, PRICE)
        expected_total = snap["realized_pnl"] + snap["unrealized_pnl"]
        assert abs(snap["total_pnl"] - expected_total) < TOL


class TestReset:
    """Reset clears all state including PnL tracking."""

    def test_reset_clears_pnl(self):
        b = make_broker()
        b.submit_and_fill(ASSET, "BUY", 1.0, PRICE)
        b.submit_and_fill(ASSET, "SELL", 1.0, PRICE * 1.05)
        b.reset()
        assert b.get_realized_pnl(ASSET) == 0.0
        assert b.get_unrealized_pnl(ASSET, PRICE) == 0.0
        assert b.get_cumulative_fees() == 0.0
        assert b.get_cumulative_slippage() == 0.0
        assert b.get_avg_entry_price(ASSET) == 0.0

    def test_reset_restores_cash(self):
        b = make_broker()
        b.submit_and_fill(ASSET, "BUY", 1.0, PRICE)
        b.reset()
        assert abs(b.get_balance()["USD"] - INITIAL_CASH) < TOL

    def test_reset_clears_position(self):
        b = make_broker()
        b.submit_and_fill(ASSET, "BUY", 1.0, PRICE)
        b.reset()
        assert b.get_position(ASSET) == 0.0
