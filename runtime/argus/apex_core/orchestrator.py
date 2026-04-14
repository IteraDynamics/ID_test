"""Orchestrator — the runtime execution loop for IteraDynamics.

The orchestrator:
1. Loads persisted state.
2. Fetches or receives the latest closed-bar OHLCV DataFrame.
3. Calls generate_signals() (Layer 1 + Layer 2).
4. Calls the allocator (Layer 3 governance).
5. Executes approved trades via the broker.
6. Persists updated state.

It is the ONLY place in the system that executes trades.
Research code (harness, strategies, regime engine) has no access to this class.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

import pandas as pd

from research.regimes.baseline_engine import BaselineRegimeEngine
from runtime.argus.apex_core.signal_generator import generate_signals, SignalBundle
from runtime.argus.allocators.portfolio_allocator import PortfolioAllocator, AllocationDecision
from runtime.argus.brokers.base import BaseBroker
from runtime.argus.governors.drawdown_governor import DrawdownGovernor
from runtime.argus.governors.exposure_governor import ExposureGovernor
from runtime.argus.state.runtime_state import RuntimeState

log = logging.getLogger(__name__)


class Orchestrator:
    """Runtime orchestrator for IteraDynamics.

    Parameters
    ----------
    broker : BaseBroker
        Broker implementation (PaperBroker or StubLiveBroker).
    strategies : list[(module, weight)]
        Strategy sleeves with weights.
    regime_engine : BaselineRegimeEngine | None
        Defaults to BaselineRegimeEngine().
    drawdown_governor : DrawdownGovernor | None
    exposure_governor : ExposureGovernor | None
    asset : str
    state_path : str | None
        Path to persist runtime state.
    """

    def __init__(
        self,
        broker: BaseBroker,
        strategies: list[tuple[Any, float]],
        regime_engine: BaselineRegimeEngine | None = None,
        drawdown_governor: DrawdownGovernor | None = None,
        exposure_governor: ExposureGovernor | None = None,
        asset: str = "BTC",
        state_path: str | None = None,
    ) -> None:
        self.broker = broker
        self.strategies = strategies
        self.regime_engine = regime_engine or BaselineRegimeEngine()
        self.asset = asset
        self.state_path = state_path

        dd_gov = drawdown_governor or DrawdownGovernor()
        exp_gov = exposure_governor or ExposureGovernor()
        self.allocator = PortfolioAllocator(
            drawdown_governor=dd_gov,
            exposure_governor=exp_gov,
        )

        self._state = RuntimeState.load(state_path)
        self._cycle_count = 0

    # ── Public API ─────────────────────────────────────────────────────────────

    def step(self, df: pd.DataFrame) -> dict[str, Any]:
        """Execute one orchestrator cycle on the provided OHLCV DataFrame.

        Called once per closed bar (e.g. every hour for hourly data).

        Parameters
        ----------
        df :
            OHLCV DataFrame up to and including the current closed bar.

        Returns
        -------
        dict
            Cycle audit record.
        """
        self._cycle_count += 1
        current_price = float(df["close"].iloc[-1])
        timestamp = str(df.index[-1])

        # ── Update governor with current NAV ──────────────────────────
        nav = self.broker.get_nav(self.asset, current_price)
        current_units = self.broker.get_position(self.asset)
        current_exposure = (current_units * current_price) / nav if nav > 0 else 0.0

        self.allocator.dd_gov.update(nav)

        # ── Generate signals ──────────────────────────────────────────
        bundle: SignalBundle = generate_signals(
            df=df,
            strategies=self.strategies,
            regime_engine=self.regime_engine,
            current_exposure=current_exposure,
            asset=self.asset,
        )

        log.info(
            "Cycle %d | %s | regime=%s | price=%.2f | nav=%.2f | exposure=%.3f",
            self._cycle_count, timestamp,
            bundle.regime.value, current_price, nav, current_exposure,
        )

        # ── Allocate ──────────────────────────────────────────────────
        decision: AllocationDecision = self.allocator.allocate(
            intents=bundle.intents_with_weights,
            current_nav=nav,
            current_exposure=current_exposure,
            regime=bundle.regime,
        )

        log.info(
            "Allocation: action=%s target_exp=%.4f approved=%s | %s",
            decision.action, decision.target_exposure, decision.approved, decision.reason,
        )

        # ── Execute ───────────────────────────────────────────────────
        fill = None
        if decision.approved and decision.action in ("BUY", "SELL"):
            qty = self.broker.compute_order_qty(
                asset=self.asset,
                side=decision.action,
                target_exposure_frac=decision.target_exposure,
                current_price=current_price,
            )
            if qty > 1e-8:
                order, fill = self.broker.submit_and_fill(
                    asset=self.asset,
                    side=decision.action,
                    qty=qty,
                    price=current_price,
                    reason=decision.reason[:120],
                )
                if fill:
                    log.info(
                        "Fill: %s %.6f %s @ %.2f fee=%.4f",
                        fill.side, fill.qty, fill.asset, fill.fill_price, fill.fee,
                    )
                    self._state.fill_count += 1

        # ── Update & persist state ────────────────────────────────────
        new_nav = self.broker.get_nav(self.asset, current_price)
        new_units = self.broker.get_position(self.asset)
        new_exposure = (new_units * current_price) / new_nav if new_nav > 0 else 0.0
        balance = self.broker.get_balance()

        self._state.update_from_broker(
            asset=self.asset,
            position_units=new_units,
            cash=balance.get("USD", 0.0),
            nav=new_nav,
            exposure_frac=new_exposure,
            bar_timestamp=timestamp,
        )
        self._state.drawdown_governor_halted = not self.allocator.dd_gov.is_buy_allowed()
        if self.state_path:
            self._state.save(self.state_path)

        return {
            "cycle": self._cycle_count,
            "timestamp": timestamp,
            "regime": bundle.regime.value,
            "price": current_price,
            "nav": new_nav,
            "exposure": new_exposure,
            "decision_action": decision.action,
            "decision_approved": decision.approved,
            "decision_reason": decision.reason,
            "fill": {
                "side": fill.side,
                "qty": fill.qty,
                "price": fill.fill_price,
                "fee": fill.fee,
            } if fill else None,
        }

    def run_loop(
        self,
        df_provider,
        poll_interval_seconds: int = 3600,
        max_cycles: int | None = None,
    ) -> None:
        """Run the orchestrator in a continuous loop.

        Parameters
        ----------
        df_provider :
            A callable that returns the latest OHLCV DataFrame on each call.
        poll_interval_seconds :
            Seconds to wait between cycles.
        max_cycles :
            If set, stop after this many cycles (useful for testing).
        """
        log.info("Orchestrator starting. asset=%s poll=%ds", self.asset, poll_interval_seconds)
        cycle = 0
        while True:
            try:
                df = df_provider()
                record = self.step(df)
                cycle += 1
                if max_cycles and cycle >= max_cycles:
                    log.info("Reached max_cycles=%d — stopping.", max_cycles)
                    break
                time.sleep(poll_interval_seconds)
            except KeyboardInterrupt:
                log.info("Orchestrator stopped by user.")
                break
            except Exception as exc:
                log.exception("Orchestrator cycle error: %s", exc)
                time.sleep(min(poll_interval_seconds, 60))
