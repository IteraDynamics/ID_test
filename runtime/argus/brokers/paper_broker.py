"""Paper broker — in-memory trading simulation for paper/shadow mode.

Behaviour:
- All orders execute using the shared ExecutionConfig fill model.
- Execution cost is identical to the research backtest engine (same compute_fill).
- No external I/O.
- Thread-unsafe (single-threaded runtime is assumed).
- Full fill history is retained for audit.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Any

from research.harness.execution_model import ExecutionConfig, compute_fill
from runtime.argus.brokers.base import BaseBroker, BrokerOrder, Fill, OrderStatus

DEFAULT_INITIAL_CASH = float(os.getenv("PAPER_BROKER_INITIAL_CASH", "100000.0"))
MIN_TRADE_NOTIONAL = float(os.getenv("MIN_TRADE_NOTIONAL_USD", "50.0"))


class PaperBroker(BaseBroker):
    """Paper trading broker with realistic execution cost simulation.

    Uses ExecutionConfig (shared with the backtest engine) so that paper-trade
    costs are identical to backtest costs.

    Parameters
    ----------
    initial_cash : float
        Starting USD cash balance.
    exec_config : ExecutionConfig | None
        Execution cost parameters.  Defaults to ExecutionConfig.from_env().
    min_trade_notional : float
        Minimum USD notional; orders below this are rejected.

    Legacy keyword arguments
    ------------------------
    fee_rate : float | None
        If exec_config is None, overrides taker_fee_rate on a default config.
    slippage_bps : float | None
        If exec_config is None, overrides base_slippage_bps on a default config.
    """

    def __init__(
        self,
        initial_cash: float = DEFAULT_INITIAL_CASH,
        exec_config: ExecutionConfig | None = None,
        min_trade_notional: float = MIN_TRADE_NOTIONAL,
        # Legacy kwargs
        fee_rate: float | None = None,
        slippage_bps: float | None = None,
    ) -> None:
        self._cash = initial_cash
        self._initial_cash = initial_cash
        self._min_notional = min_trade_notional

        # Build execution config
        if exec_config is None:
            exec_config = ExecutionConfig.from_env()
            if fee_rate is not None:
                exec_config.taker_fee_rate = fee_rate
            if slippage_bps is not None:
                exec_config.base_slippage_bps = slippage_bps
        self._exec_config = exec_config

        self._positions: dict[str, float] = {}        # asset -> units
        self._orders: dict[str, BrokerOrder] = {}     # order_id -> order
        self._fills: dict[str, Fill] = {}             # order_id -> fill
        self._fill_history: list[Fill] = []

    # ── BaseBroker API ─────────────────────────────────────────────────────────

    def get_balance(self) -> dict[str, float]:
        balances = {"USD": self._cash}
        balances.update(self._positions)
        return balances

    def get_position(self, asset: str) -> float:
        return self._positions.get(asset, 0.0)

    def get_nav(self, asset: str, price: float) -> float:
        position_value = self.get_position(asset) * price
        return self._cash + position_value

    def submit_market_order(
        self,
        asset: str,
        side: str,
        qty: float,
        reason: str = "",
    ) -> BrokerOrder:
        """Submit a market order (pending fill).

        Use ``submit_and_fill`` for the combined one-shot path.
        """
        if qty <= 0:
            raise ValueError(f"Order qty must be positive, got {qty}")
        if side not in ("BUY", "SELL"):
            raise ValueError(f"side must be BUY or SELL, got {side!r}")

        order_id = str(uuid.uuid4())[:8]
        order = BrokerOrder(
            order_id=order_id,
            asset=asset,
            side=side,
            order_type="MARKET",
            qty=qty,
            status=OrderStatus.PENDING,
            meta={"reason": reason},
        )
        self._orders[order_id] = order
        return order

    def fill_order_at_price(
        self,
        order_id: str,
        price: float,
        atr_pct: float = 0.0,
    ) -> Fill | None:
        """Fill a pending order at the given price using ExecutionConfig.

        Parameters
        ----------
        order_id :
            ID of a PENDING order.
        price :
            Current mid/reference price (bar close).
        atr_pct :
            ATR as fraction of price at this bar (e.g. 0.02 = 2%).
            Used for vol-dependent slippage.  Defaults to 0.0 (base slippage only).
        """
        order = self._orders.get(order_id)
        if order is None or order.status != OrderStatus.PENDING:
            return None

        # Approximate notional for fill computation
        notional_approx = order.qty * price
        nav = self.get_nav(order.asset, price)

        # Minimum notional check
        if notional_approx < self._min_notional:
            order.status = OrderStatus.REJECTED
            order.meta["reject_reason"] = (
                f"notional {notional_approx:.2f} < min {self._min_notional}"
            )
            return None

        fill_result = compute_fill(
            mid_price=price,
            notional=notional_approx,
            nav=nav,
            atr_pct=atr_pct,
            direction=order.side,
            config=self._exec_config,
        )

        fill_price = fill_result.effective_price
        fee = fill_result.fee_usd

        # Execute
        if order.side == "BUY":
            cost = notional_approx + fee
            if cost > self._cash:
                # Partial fill — use available cash
                available_cash = max(0.0, self._cash - fee)
                order.qty = available_cash / fill_price
                notional_approx = order.qty * fill_price
                fee = notional_approx * fill_result.fee_rate_applied
                cost = notional_approx + fee
                order.status = OrderStatus.PARTIALLY_FILLED
            else:
                order.status = OrderStatus.FILLED

            self._cash -= cost
            self._positions[order.asset] = (
                self._positions.get(order.asset, 0.0) + order.qty
            )

        else:  # SELL
            current_units = self._positions.get(order.asset, 0.0)
            sell_qty = min(order.qty, current_units)
            if sell_qty <= 0:
                order.status = OrderStatus.REJECTED
                order.meta["reject_reason"] = "no position to sell"
                return None

            if sell_qty < order.qty:
                order.qty = sell_qty
                notional_approx = sell_qty * fill_price
                fee = notional_approx * fill_result.fee_rate_applied
                order.status = OrderStatus.PARTIALLY_FILLED
            else:
                order.status = OrderStatus.FILLED

            self._cash += notional_approx - fee
            self._positions[order.asset] = current_units - sell_qty

        fill = Fill(
            order_id=order_id,
            asset=order.asset,
            side=order.side,
            qty=order.qty,
            fill_price=fill_price,
            fee=fee,
            mid_price=price,
            slippage_usd=round(fill_result.slippage_usd, 6),
            spread_usd=round(fill_result.spread_usd, 6),
            cost_bps=round(fill_result.cost_bps, 4),
        )
        self._fills[order_id] = fill
        self._fill_history.append(fill)
        return fill

    def submit_and_fill(
        self,
        asset: str,
        side: str,
        qty: float,
        price: float,
        reason: str = "",
        atr_pct: float = 0.0,
    ) -> tuple[BrokerOrder, Fill | None]:
        """Convenience: submit + immediately fill at given price.

        Parameters
        ----------
        atr_pct :
            ATR as fraction of price.  Passed through to ExecutionConfig slippage
            model.  If omitted, only base slippage is applied (conservative).
        """
        order = self.submit_market_order(asset, side, qty, reason=reason)
        fill = self.fill_order_at_price(order.order_id, price, atr_pct=atr_pct)
        return order, fill

    def get_fill(self, order_id: str) -> Fill | None:
        return self._fills.get(order_id)

    def cancel_order(self, order_id: str) -> bool:
        order = self._orders.get(order_id)
        if order and order.status == OrderStatus.PENDING:
            order.status = OrderStatus.CANCELLED
            return True
        return False

    # ── Paper-specific helpers ─────────────────────────────────────────────────

    @property
    def fill_history(self) -> list[Fill]:
        return list(self._fill_history)

    def get_average_entry_price(self, asset: str) -> float:
        """Weighted average entry price for the current position (average cost basis).

        Walks fill history in chronological order.  BUY fills increase the cost
        pool; SELL fills reduce units while keeping the per-unit cost unchanged.
        Returns 0.0 when the position is flat.
        """
        total_units = 0.0
        total_cost = 0.0
        for fill in self._fill_history:
            if fill.asset != asset:
                continue
            if fill.side == "BUY":
                total_cost += fill.qty * fill.fill_price
                total_units += fill.qty
            else:  # SELL
                if total_units > 0:
                    avg = total_cost / total_units
                    sold = min(fill.qty, total_units)
                    total_units -= sold
                    total_cost = total_units * avg
        if total_units <= 1e-12:
            return 0.0
        return total_cost / total_units

    def process_capital_flow(self, amount: float) -> None:
        """Adjust cash for a fund-level capital transfer — not a trade.

        Parameters
        ----------
        amount : float
            Positive = capital inflow, negative = capital outflow.

        Both _cash and _initial_cash are shifted so that performance metrics
        (returns relative to starting capital) are not distorted by transfers.
        Neither value is allowed to go below zero.
        """
        self._cash         = max(0.0, self._cash         + amount)
        self._initial_cash = max(0.0, self._initial_cash + amount)

    def reset(self, initial_cash: float | None = None) -> None:
        """Reset broker to initial state."""
        self._cash = initial_cash or self._initial_cash
        self._positions.clear()
        self._orders.clear()
        self._fills.clear()
        self._fill_history.clear()

    def snapshot(self, asset: str, price: float) -> dict:
        """Return a state snapshot for persistence or logging."""
        avg_entry = self.get_average_entry_price(asset)
        return {
            "cash": round(self._cash, 4),
            "positions": {k: round(v, 8) for k, v in self._positions.items()},
            "nav": round(self.get_nav(asset, price), 4),
            "n_fills": len(self._fill_history),
            "average_entry_price": round(avg_entry, 6),
        }
