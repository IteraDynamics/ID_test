"""Research harness — deterministic single-strategy backtest engine.

Design principles:
- Closed-bar only: signals are generated after each bar closes.
- No lookahead: at bar i, only data df.iloc[:i+1] is visible.
- Vectorised indicator computation, then bar-by-bar logic loop.
- Fee + slippage applied on every simulated trade.
- Position is modelled as a fractional NAV exposure (0.0–1.0).

Backtest loop:
    for each closed bar i:
        1. Compute regime signal at bar i.
        2. Call strategy.generate_intent(df[:i+1], ctx).
        3. Determine new target exposure (after gov cap if any).
        4. If exposure changes beyond threshold, simulate a trade.
        5. Mark-to-market the position.
        6. Record equity, position, and trade log.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from research.regimes.contracts import RegimeLabel
from research.regimes.baseline_engine import BaselineRegimeEngine
from research.strategies.contracts import Action, StrategyContext, StrategyIntent

# ── Constants ──────────────────────────────────────────────────────────────────
DEFAULT_FEE_RATE = float(os.getenv("FEE_RATE", "0.0006"))
DEFAULT_SLIPPAGE_BPS = float(os.getenv("SLIPPAGE_BPS", "5"))
DEFAULT_INITIAL_CAPITAL = float(os.getenv("INITIAL_CAPITAL", "100000.0"))
REBALANCE_THRESHOLD = 0.02   # only trade if target exposure changes by > 2%


@dataclass
class TradeRecord:
    """Immutable record of a single simulated trade."""

    bar_index: int
    timestamp: str
    direction: str          # "BUY" or "SELL"
    price: float
    qty: float              # units of asset bought/sold
    notional_usd: float
    fee_usd: float
    slippage_usd: float
    prev_exposure: float
    new_exposure: float
    reason: str
    strategy_id: str


@dataclass
class BacktestResult:
    """Complete output of a single-strategy backtest run."""

    equity_curve: pd.Series          # indexed like df
    position_series: pd.Series       # exposure fraction [0, 1]
    regime_series: pd.Series         # RegimeLabel values
    intent_series: list[StrategyIntent]
    trades: list[TradeRecord]
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def n_trades(self) -> int:
        return len(self.trades)

    @property
    def final_equity(self) -> float:
        return float(self.equity_curve.iloc[-1]) if len(self.equity_curve) else 0.0

    @property
    def total_return_pct(self) -> float:
        if len(self.equity_curve) == 0:
            return 0.0
        return (self.equity_curve.iloc[-1] / self.equity_curve.iloc[0] - 1) * 100


def run_backtest(
    df: pd.DataFrame,
    strategy_module: Any,
    regime_engine: BaselineRegimeEngine | None = None,
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    fee_rate: float = DEFAULT_FEE_RATE,
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
    max_exposure: float = 1.0,
    rebalance_threshold: float = REBALANCE_THRESHOLD,
    asset: str = "BTC",
) -> BacktestResult:
    """Run a deterministic single-strategy backtest.

    Parameters
    ----------
    df :
        OHLCV DataFrame (DatetimeIndex, closed bars).
    strategy_module :
        A module or object with a ``generate_intent(df, ctx)`` function.
    regime_engine :
        Regime engine instance.  Defaults to ``BaselineRegimeEngine()``.
    initial_capital :
        Starting NAV in USD.
    fee_rate :
        Fractional fee per trade (e.g. 0.0006 = 0.06%).
    slippage_bps :
        Slippage estimate in basis points applied on notional.
    max_exposure :
        Hard cap on strategy exposure fraction.
    rebalance_threshold :
        Minimum absolute exposure change to trigger a simulated trade.
    asset :
        Asset label for context.

    Returns
    -------
    BacktestResult
    """
    if regime_engine is None:
        regime_engine = BaselineRegimeEngine()

    slippage_frac = slippage_bps / 10_000.0
    n = len(df)

    # Pre-compute regime series (vectorised — uses only past data at each bar
    # via the engine's internal rolling indicators)
    regime_signals = regime_engine.classify_dataframe(df)
    regime_labels = [s.label for s in regime_signals]

    # State variables
    cash = initial_capital
    position_units = 0.0       # units of asset held
    current_exposure = 0.0     # fraction of NAV currently invested

    equity_arr = np.zeros(n, dtype=float)
    position_arr = np.zeros(n, dtype=float)
    trades: list[TradeRecord] = []
    intents: list[StrategyIntent] = []

    for i in range(n):
        close_price = float(df["close"].iloc[i])

        # Mark-to-market NAV
        nav = cash + position_units * close_price

        # ── Generate intent ───────────────────────────────────────────
        regime = regime_labels[i]
        ctx = StrategyContext(
            regime=regime,
            current_exposure_frac=current_exposure,
            asset=asset,
            bar_index=i,
        )

        # Pass only data up to bar i (closed-bar, no lookahead)
        df_slice = df.iloc[: i + 1]
        intent = strategy_module.generate_intent(df_slice, ctx, closed_only=True)
        intents.append(intent)

        # ── Determine target exposure ─────────────────────────────────
        if intent.action in (Action.EXIT_LONG, Action.FLAT):
            target_exposure = 0.0
        elif intent.action == Action.HOLD:
            target_exposure = current_exposure  # no change
        else:
            target_exposure = min(intent.desired_exposure_frac, max_exposure)

        # ── Simulate trade if exposure changes meaningfully ───────────
        delta = target_exposure - current_exposure
        if abs(delta) >= rebalance_threshold:
            direction = "BUY" if delta > 0 else "SELL"
            target_position_value = nav * target_exposure
            current_position_value = position_units * close_price
            trade_notional = abs(target_position_value - current_position_value)

            # Apply slippage to execution price
            slip_price = close_price * (1 + slippage_frac) if direction == "BUY" else close_price * (1 - slippage_frac)
            fee = trade_notional * fee_rate
            slip_cost = trade_notional * slippage_frac

            # Update position
            if direction == "BUY":
                units_traded = trade_notional / slip_price
                position_units += units_traded
                cash -= trade_notional + fee
            else:
                units_traded = trade_notional / slip_price
                position_units -= units_traded
                position_units = max(0.0, position_units)
                cash += trade_notional - fee

            # Re-mark after trade
            nav = cash + position_units * close_price
            current_exposure = (position_units * close_price) / nav if nav > 0 else 0.0

            trades.append(
                TradeRecord(
                    bar_index=i,
                    timestamp=str(df.index[i]),
                    direction=direction,
                    price=close_price,
                    qty=units_traded,
                    notional_usd=trade_notional,
                    fee_usd=fee,
                    slippage_usd=slip_cost,
                    prev_exposure=current_exposure - delta,
                    new_exposure=current_exposure,
                    reason=intent.reason,
                    strategy_id=intent.strategy_id,
                )
            )

        equity_arr[i] = nav
        position_arr[i] = current_exposure

    equity_series = pd.Series(equity_arr, index=df.index, name="equity")
    position_series = pd.Series(position_arr, index=df.index, name="exposure")
    regime_series = pd.Series(regime_labels, index=df.index, name="regime", dtype=object)

    return BacktestResult(
        equity_curve=equity_series,
        position_series=position_series,
        regime_series=regime_series,
        intent_series=intents,
        trades=trades,
        params={
            "initial_capital": initial_capital,
            "fee_rate": fee_rate,
            "slippage_bps": slippage_bps,
            "max_exposure": max_exposure,
            "rebalance_threshold": rebalance_threshold,
            "asset": asset,
            "strategy_id": strategy_module.__name__ if hasattr(strategy_module, "__name__") else str(strategy_module),
            "n_bars": n,
            "start": str(df.index[0]),
            "end": str(df.index[-1]),
        },
    )
