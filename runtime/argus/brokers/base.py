"""Broker abstraction — base interface and order types.

All broker implementations must subclass BaseBroker and implement the
abstract methods.  The runtime layer (orchestrator) interacts exclusively
through this interface — never through broker-specific APIs.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass
class BrokerOrder:
    """Represents a single order submitted to a broker.

    Attributes
    ----------
    order_id : str
        Broker-assigned or internal order identifier.
    asset : str
        Asset symbol (e.g. "BTC").
    side : str
        "BUY" or "SELL".
    order_type : str
        "MARKET" or "LIMIT".
    qty : float
        Quantity in base asset units.
    limit_price : float | None
        Limit price for LIMIT orders.
    status : OrderStatus
    created_at : datetime
    meta : dict
        Arbitrary metadata for audit.
    """

    order_id: str
    asset: str
    side: str
    order_type: str
    qty: float
    limit_price: float | None = None
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class Fill:
    """Execution fill report.

    Attributes
    ----------
    order_id : str
        Corresponding order ID.
    asset : str
    side : str
    qty : float
        Filled quantity.
    fill_price : float
        Average fill price.
    fee : float
        Total fee paid.
    timestamp : datetime
    """

    order_id: str
    asset: str
    side: str
    qty: float
    fill_price: float
    fee: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


class BaseBroker(abc.ABC):
    """Abstract broker interface.

    Implementations:
    - PaperBroker   — in-memory simulation, no external calls.
    - StubLiveBroker — skeleton for wiring to a real exchange API.
    """

    @abc.abstractmethod
    def get_balance(self) -> dict[str, float]:
        """Return current account balances.

        Returns
        -------
        dict
            Keys: asset symbols + "USD" (or "USDT").
            Values: available balance.
        """

    @abc.abstractmethod
    def get_position(self, asset: str) -> float:
        """Return current position in base asset units."""

    @abc.abstractmethod
    def get_nav(self, asset: str, price: float) -> float:
        """Return current NAV (cash + mark-to-market position) in USD."""

    @abc.abstractmethod
    def submit_market_order(
        self,
        asset: str,
        side: str,
        qty: float,
        reason: str = "",
    ) -> BrokerOrder:
        """Submit a market order.

        Parameters
        ----------
        asset : str
            Asset symbol.
        side : str
            "BUY" or "SELL".
        qty : float
            Quantity in base asset units.
        reason : str
            Audit label.

        Returns
        -------
        BrokerOrder
        """

    @abc.abstractmethod
    def get_fill(self, order_id: str) -> Fill | None:
        """Retrieve fill for a given order ID, or None if unfilled."""

    @abc.abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order.  Returns True if cancelled."""

    def compute_order_qty(
        self,
        asset: str,
        side: str,
        target_exposure_frac: float,
        current_price: float,
    ) -> float:
        """Compute order quantity to reach a target exposure fraction.

        Parameters
        ----------
        asset :
            Asset symbol.
        side :
            "BUY" or "SELL".
        target_exposure_frac :
            Desired position as fraction of NAV [0, 1].
        current_price :
            Current mark price.

        Returns
        -------
        float
            Absolute quantity to trade in base units (always positive).
        """
        nav = self.get_nav(asset, current_price)
        current_units = self.get_position(asset)
        current_value = current_units * current_price
        target_value = nav * target_exposure_frac
        delta_value = target_value - current_value
        qty = abs(delta_value) / current_price if current_price > 0 else 0.0
        return qty
