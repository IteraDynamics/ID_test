"""Paper broker — in-memory trading simulation for paper/shadow mode.

Behaviour:
- All orders execute at the submitted price with configurable slippage.
- No external I/O.
- Thread-unsafe (single-threaded runtime is assumed).
- Full fill history is retained for audit.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Any

from runtime.argus.brokers.base import BaseBroker, BrokerOrder, Fill, OrderStatus

DEFAULT_FEE_RATE = float(os.getenv("FEE_RATE", "0.0006"))
DEFAULT_SLIPPAGE_BPS = float(os.getenv("SLIPPAGE_BPS", "5"))
DEFAULT_INITIAL_CASH = float(os.getenv("PAPER_BROKER_INITIAL_CASH", "100000.0"))
MIN_TRADE_NOTIONAL = float(os.getenv("MIN_TRADE_NOTIONAL_USD", "50.0"))


class PaperBroker(BaseBroker):
    """Paper trading broker with realistic fee and slippage simulation.

    Parameters
    ----------
    initial_cash : float
        Starting USD cash balance.
    fee_rate : float
        Fractional fee per trade.
    slippage_bps : float
        Slippage in basis points applied to fill price.
    min_trade_notional : float
        Minimum USD notional; orders below this are rejected.
    """

    def __init__(
        self,
        initial_cash: float = DEFAULT_INITIAL_CASH,
        fee_rate: float = DEFAULT_FEE_RATE,
        slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
        min_trade_notional: float = MIN_TRADE_NOTIONAL,
    ) -> None:
        self._cash = initial_cash
        self._initial_cash = initial_cash
        self._fee_rate = fee_rate
        self._slippage_frac = slippage_bps / 10_000.0
        self._min_notional = min_trade_notional

        self._positions: dict[str, float] = {}        # asset → units
        self._orders: dict[str, BrokerOrder] = {}     # order_id → order
        self._fills: dict[str, Fill] = {}             # order_id → fill
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
        """Submit and immediately fill a market order at current price.

        The caller must supply the current price via a separate ``fill_at_price``
        call.  Use ``submit_and_fill`` for the combined one-shot path.
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

    def fill_order_at_price(self, order_id: str, price: float) -> Fill | None:
        """Fill a pending order at the given price (with slippage).

        This is called by the orchestrator once it has the current bar price.
        """
        order = self._orders.get(order_id)
        if order is None or order.status != OrderStatus.PENDING:
            return None

        # Apply slippage
        if order.side == "BUY":
            fill_price = price * (1 + self._slippage_frac)
        else:
            fill_price = price * (1 - self._slippage_frac)

        notional = order.qty * fill_price

        # Minimum notional check
        if notional < self._min_notional:
            order.status = OrderStatus.REJECTED
            order.meta["reject_reason"] = f"notional {notional:.2f} < min {self._min_notional}"
            return None

        fee = notional * self._fee_rate

        # Execute
        if order.side == "BUY":
            cost = notional + fee
            if cost > self._cash:
                # Partial fill — use available cash
                available_cash = max(0.0, self._cash - fee)
                order.qty = available_cash / fill_price
                notional = order.qty * fill_price
                fee = notional * self._fee_rate
                cost = notional + fee
                order.status = OrderStatus.PARTIALLY_FILLED
            else:
                order.status = OrderStatus.FILLED

            self._cash -= cost
            self._positions[order.asset] = self._positions.get(order.asset, 0.0) + order.qty

        else:  # SELL
            current_units = self._positions.get(order.asset, 0.0)
            sell_qty = min(order.qty, current_units)
            if sell_qty <= 0:
                order.status = OrderStatus.REJECTED
                order.meta["reject_reason"] = "no position to sell"
                return None

            if sell_qty < order.qty:
                order.qty = sell_qty
                notional = sell_qty * fill_price
                fee = notional * self._fee_rate
                order.status = OrderStatus.PARTIALLY_FILLED
            else:
                order.status = OrderStatus.FILLED

            self._cash += notional - fee
            self._positions[order.asset] = current_units - sell_qty

        fill = Fill(
            order_id=order_id,
            asset=order.asset,
            side=order.side,
            qty=order.qty,
            fill_price=fill_price,
            fee=fee,
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
    ) -> tuple[BrokerOrder, Fill | None]:
        """Convenience: submit + immediately fill at given price."""
        order = self.submit_market_order(asset, side, qty, reason=reason)
        fill = self.fill_order_at_price(order.order_id, price)
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

    def reset(self, initial_cash: float | None = None) -> None:
        """Reset broker to initial state."""
        self._cash = initial_cash or self._initial_cash
        self._positions.clear()
        self._orders.clear()
        self._fills.clear()
        self._fill_history.clear()

    def snapshot(self, asset: str, price: float) -> dict:
        """Return a state snapshot for persistence or logging."""
        return {
            "cash": round(self._cash, 4),
            "positions": {k: round(v, 8) for k, v in self._positions.items()},
            "nav": round(self.get_nav(asset, price), 4),
            "n_fills": len(self._fill_history),
        }
