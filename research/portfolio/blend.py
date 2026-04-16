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
from research.harness.execution_model import ExecutionConfig, compute_atr_pct_series, compute_fill
from research.harness.metrics import compute_metrics, BacktestMetrics

DEFAULT_INITIAL_CAPITAL = float(os.getenv("INITIAL_CAPITAL", "100000.0"))
REBALANCE_THRESHOLD = float(os.getenv("REBALANCE_THRESHOLD", "0.02"))


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
    exec_config: ExecutionConfig | None = None,
    max_portfolio_exposure: float = 1.0,
    rebalance_threshold: float | None = None,
    asset: str = "BTC",
    calibrators: "dict | None" = None,
    # Legacy kwargs
    fee_rate: float | None = None,
    slippage_bps: float | None = None,
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
    initial_capital :
        Starting NAV in USD.
    exec_config :
        ExecutionConfig controlling all fill cost parameters.
    max_portfolio_exposure :
        Hard cap on blended portfolio exposure.
    rebalance_threshold :
        Minimum absolute exposure delta to trigger a trade.
        Defaults to the REBALANCE_THRESHOLD env var (0.02).
    asset :
        Asset label.
    calibrators :
        Optional dict mapping strategy_id → PlattCalibrator.  When provided,
        each sleeve's strategy module is wrapped so ENTER_LONG confidence values
        are post-processed before blending.  Pass ``None`` for unchanged behaviour.
    fee_rate :
        Legacy override: sets taker_fee_rate on a default ExecutionConfig.
    slippage_bps :
        Legacy override: sets base_slippage_bps on a default ExecutionConfig.

    Returns
    -------
    (PortfolioResult, BacktestMetrics)
    """
    if not sleeves:
        raise ValueError("No sleeves configured.")

    # Apply calibrators to sleeves before anything else
    if calibrators:
        from research.ml.calibration import make_calibrated_strategy
        wrapped = []
        for sleeve in sleeves:
            sid = getattr(sleeve.strategy_module, "STRATEGY_ID", "")
            cal = calibrators.get(sid)
            wrapped.append(SleeveConfig(
                strategy_module=make_calibrated_strategy(sleeve.strategy_module, cal),
                weight=sleeve.weight,
                label=sleeve.label,
                max_sleeve_exposure=sleeve.max_sleeve_exposure,
                allowed_regimes=sleeve.allowed_regimes,
            ))
        sleeves = wrapped

    if regime_engine is None:
        regime_engine = BaselineRegimeEngine()

    _rebalance_threshold = rebalance_threshold if rebalance_threshold is not None else REBALANCE_THRESHOLD

    # Build execution config, honouring legacy kwargs
    if exec_config is None:
        exec_config = ExecutionConfig()
        if fee_rate is not None:
            exec_config.taker_fee_rate = fee_rate
        if slippage_bps is not None:
            exec_config.base_slippage_bps = slippage_bps

    # Normalise weights
    total_weight = sum(s.weight for s in sleeves)
    if total_weight <= 0:
        raise ValueError("Sleeve weights must be positive.")
    normalised_weights = [s.weight / total_weight for s in sleeves]

    n = len(df)

    # Pre-compute regime series and ATR% for dynamic slippage
    regime_signals = regime_engine.classify_dataframe(df)
    regime_labels = [sig.label for sig in regime_signals]
    atr_pct_series = compute_atr_pct_series(df)

    # State
    cash = initial_capital
    position_units = 0.0
    current_exposure = 0.0

    equity_arr = np.zeros(n, dtype=float)
    blended_exp_arr = np.zeros(n, dtype=float)
    sleeve_exp_arrays = {s.label or f"sleeve_{i}": np.zeros(n, dtype=float) for i, s in enumerate(sleeves)}
    sleeve_labels = [s.label or f"sleeve_{i}" for i, s in enumerate(sleeves)]
    trades: list[TradeRecord] = []

    last_trade_bar = -9999

    # Per-sleeve virtual exposure: each sleeve operates as if it owns 100% of
    # its own capital.  Passing the portfolio's total exposure to every sleeve
    # causes strategies to think they're already long the moment any other
    # sleeve enters, producing HOLD signals, wrong sizing, and runaway churn.
    sleeve_virtual_exp = {lbl: 0.0 for lbl in sleeve_labels}

    for i in range(n):
        close_price = float(df["close"].iloc[i])
        atr_pct = float(atr_pct_series.iloc[i])
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
                sleeve_virtual_exp[lbl] = 0.0
                continue

            # Give the sleeve its OWN virtual exposure so it makes decisions
            # as if it were the only strategy running.
            ctx = StrategyContext(
                regime=regime,
                current_exposure_frac=sleeve_virtual_exp[lbl],
                asset=asset,
                bar_index=i,
            )
            intent = sleeve.strategy_module.generate_intent(df_slice, ctx, closed_only=True)

            if intent.action in (Action.EXIT_LONG, Action.FLAT):
                desired = 0.0
                sleeve_virtual_exp[lbl] = 0.0
            elif intent.action == Action.HOLD:
                # Maintain the sleeve's own position — do not use portfolio exposure
                desired = sleeve_virtual_exp[lbl]
            else:  # ENTER_LONG or any sizing action
                desired = min(intent.desired_exposure_frac, sleeve.max_sleeve_exposure)
                sleeve_virtual_exp[lbl] = desired

            sleeve_desired_exposures.append(desired)
            sleeve_exp_arrays[lbl][i] = desired

        # ── Blend: weighted sum, capped ───────────────────────────────
        blended = sum(
            w * e for w, e in zip(normalised_weights, sleeve_desired_exposures)
        )
        target_exposure = min(blended, max_portfolio_exposure)

        # ── Simulate trade ────────────────────────────────────────────
        delta = target_exposure - current_exposure
        cooldown_ok = (i - last_trade_bar) >= exec_config.cooldown_bars
        if abs(delta) >= _rebalance_threshold and cooldown_ok:
            direction = "BUY" if delta > 0 else "SELL"
            target_pv = nav * target_exposure
            current_pv = position_units * close_price
            trade_notional = abs(target_pv - current_pv)

            fill = compute_fill(
                mid_price=close_price,
                notional=trade_notional,
                nav=nav,
                atr_pct=atr_pct,
                direction=direction,
                config=exec_config,
            )

            if direction == "BUY":
                units = trade_notional / fill.effective_price
                position_units += units
                cash -= trade_notional + fill.fee_usd
            else:
                units = trade_notional / fill.effective_price
                position_units = max(0.0, position_units - units)
                cash += trade_notional - fill.fee_usd

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
                    qty=units,
                    notional_usd=trade_notional,
                    fee_usd=round(fill.fee_usd, 6),
                    slippage_usd=round(fill.slippage_usd, 6),
                    spread_usd=round(fill.spread_usd, 6),
                    cost_bps=round(fill.cost_bps, 4),
                    prev_exposure=round(prev_exposure, 6),
                    new_exposure=round(current_exposure, 6),
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
        "taker_fee_rate": exec_config.taker_fee_rate,
        "base_slippage_bps": exec_config.base_slippage_bps,
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
