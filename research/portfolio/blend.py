"""Portfolio-level multi-strategy blend.

Runs N strategy modules independently, then combines their exposure signals
into a single portfolio-level exposure governed by weights and caps.

Design:
- Each strategy runs independently (pure functions, no shared state).
- A sleeve weight array defines capital allocation across strategies.
- Regime-based sleeve gating: a sleeve can be disabled for specific regimes.
- The combined exposure is capped by the portfolio governor.
- Final equity curve is computed from the blended exposure.

This is a research-side simulation.  Runtime blending is handled in Layer 3.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from research.regimes.baseline_engine import BaselineRegimeEngine
from research.regimes.contracts import RegimeLabel
from research.strategies.contracts import Action, StrategyContext
from research.harness.backtest_engine import TradeRecord
from research.harness.metrics import compute_metrics, BacktestMetrics

DEFAULT_FEE_RATE = float(os.getenv("FEE_RATE", "0.0006"))
DEFAULT_SLIPPAGE_BPS = float(os.getenv("SLIPPAGE_BPS", "5"))
DEFAULT_INITIAL_CAPITAL = float(os.getenv("INITIAL_CAPITAL", "100000.0"))
REBALANCE_THRESHOLD = 0.02


@dataclass
class SleeveConfig:
    """Configuration for a single strategy sleeve in the portfolio.

    Attributes
    ----------
    strategy_module : Any
        A strategy module with a ``generate_intent(df, ctx)`` function.
    weight : float
        Capital weight allocated to this sleeve in [0, 1].
        Weights across all sleeves need not sum to 1 — they are normalised.
    label : str
        Human-readable label for this sleeve.
    max_sleeve_exposure : float
        Maximum exposure this sleeve can contribute to the portfolio.
    allowed_regimes : set[RegimeLabel] | None
        If provided, this sleeve is disabled outside these regimes.
    """

    strategy_module: Any
    weight: float
    label: str = ""
    max_sleeve_exposure: float = 1.0
    allowed_regimes: set[RegimeLabel] | None = None


@dataclass
class PortfolioResult:
    """Output of a multi-strategy portfolio backtest."""

    equity_curve: pd.Series
    blended_exposure: pd.Series
    sleeve_exposures: dict[str, pd.Series]   # label → exposure series
    regime_series: pd.Series
    trades: list[TradeRecord]
    sleeve_results: dict[str, Any]           # label → per-sleeve metrics
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def final_equity(self) -> float:
        return float(self.equity_curve.iloc[-1]) if len(self.equity_curve) else 0.0


def run_portfolio_backtest(
    df: pd.DataFrame,
    sleeves: list[SleeveConfig],
    regime_engine: BaselineRegimeEngine | None = None,
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    fee_rate: float = DEFAULT_FEE_RATE,
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
    max_portfolio_exposure: float = 1.0,
    asset: str = "BTC",
) -> tuple[PortfolioResult, BacktestMetrics]:
    """Run a multi-strategy portfolio backtest.

    Parameters
    ----------
    df :
        OHLCV DataFrame.
    sleeves :
        List of SleeveConfig objects.
    regime_engine :
        Regime engine.  Defaults to BaselineRegimeEngine().
    initial_capital, fee_rate, slippage_bps :
        Standard backtest parameters.
    max_portfolio_exposure :
        Hard cap on blended portfolio exposure.
    asset :
        Asset label.

    Returns
    -------
    (PortfolioResult, BacktestMetrics)
    """
    if not sleeves:
        raise ValueError("No sleeves configured.")

    if regime_engine is None:
        regime_engine = BaselineRegimeEngine()

    # Normalise weights
    total_weight = sum(s.weight for s in sleeves)
    if total_weight <= 0:
        raise ValueError("Sleeve weights must be positive.")
    normalised_weights = [s.weight / total_weight for s in sleeves]

    slippage_frac = slippage_bps / 10_000.0
    n = len(df)

    # Pre-compute regime series
    regime_signals = regime_engine.classify_dataframe(df)
    regime_labels = [sig.label for sig in regime_signals]

    # State
    cash = initial_capital
    position_units = 0.0
    current_exposure = 0.0

    equity_arr = np.zeros(n, dtype=float)
    blended_exp_arr = np.zeros(n, dtype=float)
    sleeve_exp_arrays = {s.label or f"sleeve_{i}": np.zeros(n, dtype=float) for i, s in enumerate(sleeves)}
    sleeve_labels = [s.label or f"sleeve_{i}" for i, s in enumerate(sleeves)]
    trades: list[TradeRecord] = []

    for i in range(n):
        close_price = float(df["close"].iloc[i])
        nav = cash + position_units * close_price
        regime = regime_labels[i]
        df_slice = df.iloc[: i + 1]

        # ── Collect per-sleeve intents ────────────────────────────────
        sleeve_desired_exposures = []
        for j, sleeve in enumerate(sleeves):
            lbl = sleeve_labels[j]

            # Check if this sleeve is allowed in current regime
            if sleeve.allowed_regimes is not None and regime not in sleeve.allowed_regimes:
                sleeve_desired_exposures.append(0.0)
                sleeve_exp_arrays[lbl][i] = 0.0
                continue

            ctx = StrategyContext(
                regime=regime,
                current_exposure_frac=current_exposure,
                asset=asset,
                bar_index=i,
            )
            intent = sleeve.strategy_module.generate_intent(df_slice, ctx, closed_only=True)

            if intent.action in (Action.EXIT_LONG, Action.FLAT):
                desired = 0.0
            elif intent.action == Action.HOLD:
                desired = current_exposure * normalised_weights[j]
            else:
                desired = min(intent.desired_exposure_frac, sleeve.max_sleeve_exposure)

            sleeve_desired_exposures.append(desired)
            sleeve_exp_arrays[lbl][i] = desired

        # ── Blend: weighted sum, capped ───────────────────────────────
        blended = sum(
            w * e for w, e in zip(normalised_weights, sleeve_desired_exposures)
        )
        target_exposure = min(blended, max_portfolio_exposure)

        # ── Simulate trade ────────────────────────────────────────────
        delta = target_exposure - current_exposure
        if abs(delta) >= REBALANCE_THRESHOLD:
            direction = "BUY" if delta > 0 else "SELL"
            target_pv = nav * target_exposure
            current_pv = position_units * close_price
            trade_notional = abs(target_pv - current_pv)

            slip_price = (
                close_price * (1 + slippage_frac)
                if direction == "BUY"
                else close_price * (1 - slippage_frac)
            )
            fee = trade_notional * fee_rate
            slip_cost = trade_notional * slippage_frac

            if direction == "BUY":
                units = trade_notional / slip_price
                position_units += units
                cash -= trade_notional + fee
            else:
                units = trade_notional / slip_price
                position_units = max(0.0, position_units - units)
                cash += trade_notional - fee

            nav = cash + position_units * close_price
            current_exposure = (position_units * close_price) / nav if nav > 0 else 0.0

            trades.append(
                TradeRecord(
                    bar_index=i,
                    timestamp=str(df.index[i]),
                    direction=direction,
                    price=close_price,
                    qty=units,
                    notional_usd=trade_notional,
                    fee_usd=fee,
                    slippage_usd=slip_cost,
                    prev_exposure=current_exposure - delta,
                    new_exposure=current_exposure,
                    reason=f"portfolio_blend target={target_exposure:.3f}",
                    strategy_id="portfolio",
                )
            )

        equity_arr[i] = nav
        blended_exp_arr[i] = current_exposure

    equity_series = pd.Series(equity_arr, index=df.index, name="equity")
    blended_series = pd.Series(blended_exp_arr, index=df.index, name="blended_exposure")
    regime_series = pd.Series(regime_labels, index=df.index, name="regime", dtype=object)
    sleeve_exp_series = {
        lbl: pd.Series(arr, index=df.index, name=lbl)
        for lbl, arr in sleeve_exp_arrays.items()
    }

    params = {
        "initial_capital": initial_capital,
        "fee_rate": fee_rate,
        "slippage_bps": slippage_bps,
        "max_portfolio_exposure": max_portfolio_exposure,
        "asset": asset,
        "sleeves": [
            {"label": s.label, "weight": s.weight, "normalised_weight": normalised_weights[j]}
            for j, s in enumerate(sleeves)
        ],
        "n_bars": n,
        "start": str(df.index[0]),
        "end": str(df.index[-1]),
        "strategy_id": "portfolio_blend",
    }

    result = PortfolioResult(
        equity_curve=equity_series,
        blended_exposure=blended_series,
        sleeve_exposures=sleeve_exp_series,
        regime_series=regime_series,
        trades=trades,
        sleeve_results={},
        params=params,
    )

    metrics = compute_metrics(equity_series, trades, params)
    return result, metrics
