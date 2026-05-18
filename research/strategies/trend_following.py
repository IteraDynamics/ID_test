"""Layer 2 — TrendFollowingStrategy (Core Structural Sleeve).

Logic summary:
    This is the primary structural exposure strategy.  It participates in
    sustained BTC up-trends and exits when trend evidence deteriorates.

Signal construction:
    1. Dual EMA alignment: fast EMA > slow EMA → bullish structure.
    2. Price above slow EMA: confirms trend (not just a crossover on pullback).
    3. ADX proxy (EMA spread rate of change): measures trend strength.
    4. Regime gate: only enters in TREND_UP; exits on TREND_DOWN or HIGH_VOL.

Entry conditions (all must hold):
    - Regime is TREND_UP.
    - Close > slow EMA.
    - Fast EMA > slow EMA.
    - EMA spread widening (positive momentum).

Exit conditions (any triggers full exit):
    - Regime is TREND_DOWN or HIGH_VOL.
    - Close < slow EMA by more than a tolerance band.
    - EMA crossover flips bearish.

Sizing:
    - Base size = 0.8 of NAV when conditions strong.
    - Scaled down proportionally to EMA spread strength.
    - Min size when marginal conditions = 0.4.
"""

from __future__ import annotations

import pandas as pd
import numpy as np

from research.regimes.contracts import RegimeLabel
from research.strategies.contracts import Action, StrategyContext, StrategyIntent

STRATEGY_ID = "trend_following_v1"

# ── Parameters ─────────────────────────────────────────────────────────────────
FAST_EMA = 21
SLOW_EMA = 55
MOMENTUM_LOOKBACK = 5
MIN_EXPOSURE = 0.40
MAX_EXPOSURE = 0.80
EMA_BELOW_TOLERANCE = -0.005  # allow close to be 0.5% below slow EMA (noise tolerance)


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
        Columns: [open, high, low, close, volume].
    ctx :
        StrategyContext with regime, current exposure, and asset info.
    closed_only :
        If True (default), only bar at ``df.index[-1]`` is evaluated.
        This flag is a contract-level guarantee — strategies must honour it.

    Returns
    -------
    StrategyIntent
    """
    if len(df) < SLOW_EMA + MOMENTUM_LOOKBACK + 5:
        return _warmup_intent(ctx)

    close = df["close"]

    ema_fast = close.ewm(span=FAST_EMA, adjust=False).mean()
    ema_slow = close.ewm(span=SLOW_EMA, adjust=False).mean()

    # Current bar values (closed)
    c = float(close.iloc[-1])
    ef = float(ema_fast.iloc[-1])
    es = float(ema_slow.iloc[-1])

    # EMA spread relative to price
    ema_spread = (ef - es) / c

    # EMA spread momentum: is spread widening?
    ema_spread_prev_series = (ema_fast - ema_slow) / close
    spread_momentum = float(
        ema_spread_prev_series.iloc[-1] - ema_spread_prev_series.iloc[-MOMENTUM_LOOKBACK - 1]
    )

    # Price position relative to slow EMA
    price_vs_slow = (c - es) / es

    meta = {
        "ema_fast": round(ef, 4),
        "ema_slow": round(es, 4),
        "ema_spread": round(ema_spread, 5),
        "spread_momentum": round(spread_momentum, 6),
        "price_vs_slow_ema": round(price_vs_slow, 5),
        "regime": ctx.regime.value,
    }

    # ── Exit conditions ───────────────────────────────────────────────
    if ctx.regime in (RegimeLabel.TREND_DOWN, RegimeLabel.HIGH_VOL):
        return StrategyIntent(
            action=Action.EXIT_LONG,
            confidence=0.90,
            desired_exposure_frac=0.0,
            horizon_hours=4,
            reason=f"Regime exit signal: {ctx.regime.value}",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    if price_vs_slow < EMA_BELOW_TOLERANCE and ctx.current_exposure_frac > 0:
        return StrategyIntent(
            action=Action.EXIT_LONG,
            confidence=0.75,
            desired_exposure_frac=0.0,
            horizon_hours=4,
            reason="Close below slow EMA — structural break",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    if ema_spread < 0 and ctx.current_exposure_frac > 0:
        return StrategyIntent(
            action=Action.EXIT_LONG,
            confidence=0.80,
            desired_exposure_frac=0.0,
            horizon_hours=2,
            reason="EMA crossover bearish — fast below slow",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    # ── Entry conditions ──────────────────────────────────────────────
    bullish_structure = (
        ctx.regime == RegimeLabel.TREND_UP
        and ema_spread > 0.002          # fast materially above slow
        and price_vs_slow > EMA_BELOW_TOLERANCE
        and spread_momentum >= 0        # trend strengthening or stable
    )

    if bullish_structure:
        # Scale exposure with EMA spread strength (stronger spread → higher size)
        spread_strength = min(ema_spread / 0.02, 1.0)  # normalise at 2% spread
        exposure = MIN_EXPOSURE + spread_strength * (MAX_EXPOSURE - MIN_EXPOSURE)
        exposure = round(min(exposure, MAX_EXPOSURE), 4)
        confidence = min(0.55 + spread_strength * 0.35, 0.90)

        return StrategyIntent(
            action=Action.ENTER_LONG,
            confidence=round(confidence, 4),
            desired_exposure_frac=exposure,
            horizon_hours=48,
            reason="Trend-following entry: bullish EMA structure with TREND_UP regime",
            meta={**meta, "spread_strength": round(spread_strength, 4)},
            strategy_id=STRATEGY_ID,
        )

    # ── Hold ─────────────────────────────────────────────────────────
    if ctx.current_exposure_frac > 0:
        return StrategyIntent(
            action=Action.HOLD,
            confidence=0.60,
            desired_exposure_frac=ctx.current_exposure_frac,
            horizon_hours=24,
            reason="No new signal — holding existing position",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    # ── Flat / no edge ────────────────────────────────────────────────
    return StrategyIntent(
        action=Action.FLAT,
        confidence=0.55,
        desired_exposure_frac=0.0,
        horizon_hours=0,
        reason="No bullish structure detected — staying flat",
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
