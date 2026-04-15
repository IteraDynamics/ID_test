"""Research harness — deterministic single-strategy backtest engine.

Design principles:
- Closed-bar only: signals are generated after each bar closes.
- No lookahead: at bar i, only data df.iloc[:i+1] is visible.
- Vectorised indicator computation, then bar-by-bar logic loop.
- Realistic execution costs via ExecutionConfig (fee + dynamic slippage + spread).
- Cooldown bars between trades to reduce overtrading in choppy markets.

Backtest loop:
    for each closed bar i:
        1. Compute regime signal at bar i.
        2. Call strategy.generate_intent(df[:i+1], ctx).
        3. Determine new target exposure (capped by max_exposure).
        4. Skip trade if cooldown not elapsed.
        5. If exposure changes beyond threshold, simulate a trade using
           ExecutionConfig (dynamic slippage depends on trade size + ATR).
        6. Mark-to-market the position.
        7. Record equity, position, and trade log.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from research.harness.execution_model import (
    ExecutionConfig,
    compute_atr_pct_series,
    compute_fill,
)
from research.regimes.contracts import RegimeLabel
from research.regimes.baseline_engine import BaselineRegimeEngine
from research.strategies.contracts import Action, StrategyContext, StrategyIntent

# ── Constants ──────────────────────────────────────────────────────────────────
DEFAULT_INITIAL_CAPITAL = float(os.getenv("INITIAL_CAPITAL", "100000.0"))
REBALANCE_THRESHOLD = float(os.getenv("REBALANCE_THRESHOLD", "0.02"))


@dataclass
class TradeRecord:
    """Immutable record of a single simulated trade."""

    bar_index: int
    timestamp: str
    direction: str          # "BUY" or "SELL"

    # Prices
    mid_price: float        # bar close (execution reference, no adjustment)
    effective_price: float  # actual fill price (mid +/- slippage + spread)

    # Size
    qty: float              # units of asset bought/sold
    notional_usd: float     # target dollar change at mid price

    # Costs (all USD)
    fee_usd: float
    slippage_usd: float
    spread_usd: float
    cost_bps: float         # (fee + slippage + spread) / notional * 10_000

    # Exposure
    prev_exposure: float
    new_exposure: float

    # Audit
    reason: str
    strategy_id: str

    @property
    def price(self) -> float:
        """Legacy alias: callers that read .price get mid_price."""
        return self.mid_price


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
    exec_config: ExecutionConfig | None = None,
    max_exposure: float = 1.0,
    rebalance_threshold: float = REBALANCE_THRESHOLD,
    asset: str = "BTC",
    # Legacy kwargs — honoured when exec_config is None
    fee_rate: float | None = None,
    slippage_bps: float | None = None,
    # ML calibration — optional, backward-compatible
    calibrators: "dict | None" = None,
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
    exec_config :
        ExecutionConfig controlling all fill cost parameters.  If None, a
        default config is constructed (optionally overriding taker_fee_rate
        and base_slippage_bps via the legacy fee_rate / slippage_bps kwargs).
    max_exposure :
        Hard cap on strategy exposure fraction.
    rebalance_threshold :
        Minimum absolute exposure change to trigger a simulated trade.
    asset :
        Asset label for context.
    fee_rate :
        Legacy: sets taker_fee_rate on a default ExecutionConfig.
    slippage_bps :
        Legacy: sets base_slippage_bps on a default ExecutionConfig.
    calibrators :
        Optional dict mapping strategy_id → PlattCalibrator.  When provided,
        ENTER_LONG confidence values are post-processed before the bar loop.
        Pass ``None`` (default) for identical behaviour to prior versions.

    Returns
    -------
    BacktestResult
    """
    if calibrators:
        from research.ml.calibration import make_calibrated_strategy
        sid = getattr(strategy_module, "STRATEGY_ID", "")
        cal = calibrators.get(sid)
        if cal is not None:
            strategy_module = make_calibrated_strategy(strategy_module, cal)
    if regime_engine is None:
        regime_engine = BaselineRegimeEngine()

    # Build execution config, honouring legacy kwargs
    if exec_config is None:
        exec_config = ExecutionConfig()
        if fee_rate is not None:
            exec_config.taker_fee_rate = fee_rate
        if slippage_bps is not None:
            exec_config.base_slippage_bps = slippage_bps

    n = len(df)

    # Pre-compute regime series (vectorised — causal at every bar)
    regime_signals = regime_engine.classify_dataframe(df)
    regime_labels = [s.label for s in regime_signals]

    # Pre-compute ATR% series for dynamic slippage (causal EWM, no lookahead)
    atr_pct_series = compute_atr_pct_series(df)

    # State variables
    cash = initial_capital
    position_units = 0.0
    current_exposure = 0.0
    last_trade_bar = -9999  # for cooldown enforcement

    equity_arr = np.zeros(n, dtype=float)
    position_arr = np.zeros(n, dtype=float)
    trades: list[TradeRecord] = []
    intents: list[StrategyIntent] = []

    for i in range(n):
        close_price = float(df["close"].iloc[i])
        atr_pct = float(atr_pct_series.iloc[i])

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
            target_exposure = current_exposure
        else:
            target_exposure = min(intent.desired_exposure_frac, max_exposure)

        # ── Cooldown check ────────────────────────────────────────────
        cooldown_ok = (i - last_trade_bar) >= exec_config.cooldown_bars

        # ── Simulate trade if exposure changes meaningfully ───────────
        delta = target_exposure - current_exposure
        if abs(delta) >= rebalance_threshold and cooldown_ok:
            direction = "BUY" if delta > 0 else "SELL"
            target_position_value = nav * target_exposure
            current_position_value = position_units * close_price
            trade_notional = abs(target_position_value - current_position_value)

            # Compute fill using dynamic execution model
            fill = compute_fill(
                mid_price=close_price,
                notional=trade_notional,
                nav=nav,
                atr_pct=atr_pct,
                direction=direction,
                config=exec_config,
            )

            # Update position
            # Cash: deduct/receive notional at mid + fee (slippage embedded in units)
            if direction == "BUY":
                units_traded = trade_notional / fill.effective_price
                position_units += units_traded
                cash -= trade_notional + fill.fee_usd
            else:
                units_traded = trade_notional / fill.effective_price
                position_units = max(0.0, position_units - units_traded)
                cash += trade_notional - fill.fee_usd

            # Re-mark after trade
            nav = cash + position_units * close_price
            prev_exposure = current_exposure
            current_exposure = (position_units * close_price) / nav if nav > 0 else 0.0
            last_trade_bar = i

            trades.append(
                TradeRecord(
                    bar_index=i,
                    timestamp=str(df.index[i]),
                    direction=direction,
                    mid_price=close_price,
                    effective_price=round(fill.effective_price, 6),
                    qty=units_traded,
                    notional_usd=trade_notional,
                    fee_usd=round(fill.fee_usd, 6),
                    slippage_usd=round(fill.slippage_usd, 6),
                    spread_usd=round(fill.spread_usd, 6),
                    cost_bps=round(fill.cost_bps, 4),
                    prev_exposure=round(prev_exposure, 6),
                    new_exposure=round(current_exposure, 6),
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
            "taker_fee_rate": exec_config.taker_fee_rate,
            "use_maker_fees": exec_config.use_maker_fees,
            "base_slippage_bps": exec_config.base_slippage_bps,
            "slippage_size_factor": exec_config.slippage_size_factor,
            "slippage_vol_factor": exec_config.slippage_vol_factor,
            "cooldown_bars": exec_config.cooldown_bars,
            "max_exposure": max_exposure,
            "rebalance_threshold": rebalance_threshold,
            "asset": asset,
            "strategy_id": (
                strategy_module.__name__
                if hasattr(strategy_module, "__name__")
                else str(strategy_module)
            ),
            "n_bars": n,
            "start": str(df.index[0]),
            "end": str(df.index[-1]),
        },
    )
