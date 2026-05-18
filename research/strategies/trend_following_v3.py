"""Layer 2 — TrendFollowingV3 (Stepwise Exposure, Single Add-On).

Design rationale
----------------
Extends v2's freeze-on-entry discipline with one controlled add-on:

States
------
  FLAT  (exposure ~0.0)    →  entry fires  →  BASE (0.60)
  BASE  (exposure < 0.70)  →  trend strengthens  →  ADD  (0.80)
  ADD   (exposure >= 0.70) →  hold until exit
  BASE or ADD              →  exit fires  →  FLAT

The exposure threshold 0.70 is used as a proxy for "already added":
  - If current_exposure_frac < 0.70 → we are at BASE, may add.
  - If current_exposure_frac >= 0.70 → we are at ADD or above, hold only.

This is stateless — no memory between bars — because the backtest engine
tracks the actual exposure fraction, which serves as our implicit state.

Add-on conditions (all required)
---------------------------------
  - Regime is still TREND_UP
  - EMA spread > ADD_SPREAD_THRESHOLD (1.0% — a materially strong trend)
  - spread_momentum > ADD_MOMENTUM_THRESHOLD (spread actively widening)
  - Only one add is allowed per cycle (enforced by the 0.70 threshold check)

Entry conditions (tighter than v1/v2)
--------------------------------------
  - Regime is TREND_UP
  - EMA spread > 0.004 (vs 0.003 in v2, 0.002 in v1)
  - Price clearly above slow EMA (> 0)
  - Spread momentum >= 0

Exit conditions (identical to v2)
-----------------------------------
  - HIGH_VOL: immediate
  - TREND_DOWN + crossover: regime and structure both bearish
  - Material crossover: spread < -0.5%
  - Hard price break: -1.5% below slow EMA

Expected vs v2
--------------
  - Slightly more trades (the add-on fires on strong trends)
  - Higher exposure during confirmed strong trends (0.80 vs 0.75)
  - Similar or better Calmar — the add captures the best part of trends
    without continuous churn
"""

from __future__ import annotations

import pandas as pd

from research.regimes.contracts import RegimeLabel
from research.strategies.contracts import Action, StrategyContext, StrategyIntent

STRATEGY_ID = "trend_following_v3"

# ── Parameters ─────────────────────────────────────────────────────────────────
FAST_EMA = 21
SLOW_EMA = 55
MOMENTUM_LOOKBACK = 5

BASE_EXPOSURE = 0.60            # initial position on entry
ADD_EXPOSURE = 0.80             # single step-up on trend confirmation
ADD_STATE_THRESHOLD = 0.70      # above this → already added, hold only

MIN_ENTRY_SPREAD = 0.004        # tighter than v2 (0.003)
ADD_SPREAD_THRESHOLD = 0.010    # spread must reach 1.0% to justify add-on
ADD_MOMENTUM_THRESHOLD = 0.001  # spread must be actively widening

CROSSOVER_EXIT_THRESHOLD = -0.005
PRICE_BREAK_THRESHOLD = -0.015

FLAT_THRESHOLD = 0.05


def generate_intent(
    df: pd.DataFrame,
    ctx: StrategyContext,
    closed_only: bool = True,
) -> StrategyIntent:
    """Generate a trade intent for the current closed bar.

    Parameters
    ----------
    df :
        OHLCV DataFrame up to and including the current closed bar.
    ctx :
        StrategyContext with regime, current exposure, and asset info.
    closed_only :
        Contract guarantee flag — must be True in production.

    Returns
    -------
    StrategyIntent
    """
    if len(df) < SLOW_EMA + MOMENTUM_LOOKBACK + 5:
        return _warmup_intent(ctx)

    close = df["close"]
    ema_fast = close.ewm(span=FAST_EMA, adjust=False).mean()
    ema_slow = close.ewm(span=SLOW_EMA, adjust=False).mean()

    c = float(close.iloc[-1])
    ef = float(ema_fast.iloc[-1])
    es = float(ema_slow.iloc[-1])

    ema_spread = (ef - es) / c

    ema_spread_series = (ema_fast - ema_slow) / close
    spread_momentum = float(
        ema_spread_series.iloc[-1] - ema_spread_series.iloc[-MOMENTUM_LOOKBACK - 1]
    )

    price_vs_slow = (c - es) / es

    meta = {
        "ema_fast": round(ef, 4),
        "ema_slow": round(es, 4),
        "ema_spread": round(ema_spread, 5),
        "spread_momentum": round(spread_momentum, 6),
        "price_vs_slow_ema": round(price_vs_slow, 5),
        "regime": ctx.regime.value,
    }

    already_long = ctx.current_exposure_frac > FLAT_THRESHOLD
    at_base = already_long and ctx.current_exposure_frac < ADD_STATE_THRESHOLD

    # ── When long: exit checks, optional add, or hold ─────────────────────────
    if already_long:
        # Priority 1 — emergency exit
        if ctx.regime == RegimeLabel.HIGH_VOL:
            return StrategyIntent(
                action=Action.EXIT_LONG,
                confidence=0.95,
                desired_exposure_frac=0.0,
                horizon_hours=1,
                reason="HIGH_VOL regime — emergency exit",
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        # Priority 2 — regime flip with crossover
        if ctx.regime == RegimeLabel.TREND_DOWN and ema_spread < 0:
            return StrategyIntent(
                action=Action.EXIT_LONG,
                confidence=0.85,
                desired_exposure_frac=0.0,
                horizon_hours=4,
                reason="TREND_DOWN confirmed by bearish EMA crossover",
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        # Priority 3 — material crossover
        if ema_spread < CROSSOVER_EXIT_THRESHOLD:
            return StrategyIntent(
                action=Action.EXIT_LONG,
                confidence=0.80,
                desired_exposure_frac=0.0,
                horizon_hours=4,
                reason="Material EMA crossover — fast >0.5% below slow",
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        # Priority 4 — structural price break
        if price_vs_slow < PRICE_BREAK_THRESHOLD:
            return StrategyIntent(
                action=Action.EXIT_LONG,
                confidence=0.75,
                desired_exposure_frac=0.0,
                horizon_hours=4,
                reason="Price >1.5% below slow EMA — structural break",
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        # Add-on: only if at base exposure and trend materially strengthening
        if at_base:
            strong_trend = (
                ctx.regime == RegimeLabel.TREND_UP
                and ema_spread > ADD_SPREAD_THRESHOLD
                and spread_momentum > ADD_MOMENTUM_THRESHOLD
            )
            if strong_trend:
                return StrategyIntent(
                    action=Action.ENTER_LONG,
                    confidence=0.80,
                    desired_exposure_frac=ADD_EXPOSURE,
                    horizon_hours=48,
                    reason=(
                        f"Trend strengthening — adding to position "
                        f"(spread={ema_spread:.3f} > {ADD_SPREAD_THRESHOLD})"
                    ),
                    meta={**meta, "add_on": True},
                    strategy_id=STRATEGY_ID,
                )

        # No signal — freeze exposure
        return StrategyIntent(
            action=Action.HOLD,
            confidence=0.70,
            desired_exposure_frac=ctx.current_exposure_frac,
            horizon_hours=24,
            reason="In trend — holding, no resize",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    # ── When flat: entry logic ────────────────────────────────────────────────
    bullish_entry = (
        ctx.regime == RegimeLabel.TREND_UP
        and ema_spread > MIN_ENTRY_SPREAD
        and price_vs_slow > 0.0
        and spread_momentum >= 0
    )

    if bullish_entry:
        return StrategyIntent(
            action=Action.ENTER_LONG,
            confidence=0.75,
            desired_exposure_frac=BASE_EXPOSURE,
            horizon_hours=72,
            reason="Trend entry: TREND_UP + strong EMA structure",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    return StrategyIntent(
        action=Action.FLAT,
        confidence=0.60,
        desired_exposure_frac=0.0,
        horizon_hours=0,
        reason="No bullish structure — flat",
        meta=meta,
        strategy_id=STRATEGY_ID,
    )


def _warmup_intent(ctx: StrategyContext) -> StrategyIntent:
    return StrategyIntent(
        action=Action.FLAT,
        confidence=0.0,
        desired_exposure_frac=0.0,
        horizon_hours=0,
        reason="Insufficient data — warmup period",
        meta={"regime": ctx.regime.value},
        strategy_id=STRATEGY_ID,
    )
