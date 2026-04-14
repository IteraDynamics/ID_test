"""Stub live broker — skeleton for wiring to a real exchange API.

This is NOT a functional implementation.  It shows the interface contract
that a real exchange adapter must fulfil.  Submitting orders raises
``NotImplementedError`` unless the stub is put in dry-run mode.

Design intent:
- A real implementation would import an exchange SDK (e.g. ccxt) here.
- Auth credentials are read from environment variables, never hardcoded.
- All external calls should have retry logic and error normalisation.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

from runtime.argus.brokers.base import BaseBroker, BrokerOrder, Fill, OrderStatus

log = logging.getLogger(__name__)


class StubLiveBroker(BaseBroker):
    """Live broker stub — raises NotImplementedError on real execution.

    Parameters
    ----------
    dry_run : bool
        If True, methods log warnings instead of raising.  Useful for
        smoke-testing the runtime loop without exchange connectivity.
    """

    def __init__(self, dry_run: bool = True) -> None:
        self._dry_run = dry_run
        self._api_key = os.getenv("EXCHANGE_API_KEY", "")
        self._api_secret = os.getenv("EXCHANGE_API_SECRET", "")
        self._exchange_name = os.getenv("EXCHANGE_NAME", "stub")

        if not self._api_key and not dry_run:
            raise EnvironmentError(
                "EXCHANGE_API_KEY not set.  Set it in .env or pass dry_run=True."
            )

        log.info(
            "StubLiveBroker initialised: exchange=%s dry_run=%s",
            self._exchange_name,
            dry_run,
        )

    def get_balance(self) -> dict[str, float]:
        if self._dry_run:
            log.warning("StubLiveBroker.get_balance() called in dry_run mode — returning zeros.")
            return {"USD": 0.0}
        raise NotImplementedError("Implement get_balance() with real exchange SDK.")

    def get_position(self, asset: str) -> float:
        if self._dry_run:
            log.warning("StubLiveBroker.get_position(%s) called in dry_run mode — returning 0.", asset)
            return 0.0
        raise NotImplementedError("Implement get_position() with real exchange SDK.")

    def get_nav(self, asset: str, price: float) -> float:
        if self._dry_run:
            return 0.0
        raise NotImplementedError("Implement get_nav() with real exchange SDK.")

    def submit_market_order(
        self,
        asset: str,
        side: str,
        qty: float,
        reason: str = "",
    ) -> BrokerOrder:
        if self._dry_run:
            log.warning(
                "StubLiveBroker.submit_market_order() DRY RUN: %s %s %.6f %s",
                side, asset, qty, reason,
            )
            return BrokerOrder(
                order_id="dry_run_stub",
                asset=asset,
                side=side,
                order_type="MARKET",
                qty=qty,
                status=OrderStatus.REJECTED,
                meta={"dry_run": True, "reason": reason},
            )
        raise NotImplementedError(
            "Implement submit_market_order() with real exchange SDK.\n"
            "Wire to: exchange.create_market_order(symbol, side, qty)"
        )

    def get_fill(self, order_id: str) -> Fill | None:
        if self._dry_run:
            return None
        raise NotImplementedError("Implement get_fill() with real exchange SDK.")

    def cancel_order(self, order_id: str) -> bool:
        if self._dry_run:
            return False
        raise NotImplementedError("Implement cancel_order() with real exchange SDK.")
