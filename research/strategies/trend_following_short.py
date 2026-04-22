"""Layer 2 — TrendFollowingShortStrategy (Short-Side Structural Sleeve).

Logic summary:
    Structural mirror of trend_following_v1 for the bearish side.
    Participates in sustained down-trends and covers when trend evidence reverses.

Signal construction:
    1. Dual EMA alignment: fast EMA < slow EMA → bearish structure.
    2. Price below slow EMA: confirms trend (not just a crossover on dead-cat bounce).
    3. ADX proxy (EMA spread rate of change): measures bearish trend strength.
    4. Regime gate: only enters in TREND_DOWN; covers on TREND_UP or HIGH_VOL.

Entry conditions (all must hold):
    - Regime is TREND_DOWN.
    - Close < slow EMA.
    - Fast EMA < slow EMA (spread materially negative).
    - EMA spread widening bearishly (spread_momentum <= 0).

Exit conditions (any triggers full cover):
    - Regime is TREND_UP or HIGH_VOL.
    - Close > slow EMA by more than a tolerance band.
    - EMA crossover flips bullish (fast crosses above slow).

Sizing:
    - Base size = 0.8 of NAV when conditions strong.
    - Scaled down proportionally to EMA spread strength (bearish side).
    - Min size when marginal conditions = 0.4.
"""

from __future__ import annotations

import pandas as pd

from research.regimes.contracts import RegimeLabel
from research.strategies.contracts import Action, StrategyContext, StrategyIntent

STRATEGY_ID = "trend_following_short_v1"

# ── Parameters ─────────────────────────────────────────────────────────────────
FAST_EMA = 21
SLOW_EMA = 55
MOMENTUM_LOOKBACK = 5
MIN_EXPOSURE = 0.40
MAX_EXPOSURE = 0.80
EMA_ABOVE_TOLERANCE = 0.005   # allow close to be 0.5% above slow EMA before covering


def generate_intent(
    df: pd.DataFrame,
    ctx: StrategyContext,
    closed_only: bool = True,
) -> StrategyIntent:
    """Generate a short trade intent for the current closed bar."""
    if len(df) < SLOW_EMA + MOMENTUM_LOOKBACK + 5:
        return _warmup_intent(ctx)

    close = df["close"]

    ema_fast = close.ewm(span=FAST_EMA, adjust=False).mean()
    ema_slow = close.ewm(span=SLOW_EMA, adjust=False).mean()

    c = float(close.iloc[-1])
    ef = float(ema_fast.iloc[-1])
    es = float(ema_slow.iloc[-1])

    # Negative when bearish (fast < slow)
    ema_spread = (ef - es) / c

    # Spread momentum: negative means spread growing more bearish (strengthening)
    ema_spread_series = (ema_fast - ema_slow) / close
    spread_momentum = float(
        ema_spread_series.iloc[-1] - ema_spread_series.iloc[-MOMENTUM_LOOKBACK - 1]
    )

    price_vs_slow = (c - es) / es

    # Read signed exposure injected by the backtest engine
    signed_exposure = ctx.meta.get("signed_exposure", 0.0)
    currently_short = signed_exposure < -0.01

    meta = {
        "ema_fast": round(ef, 4),
        "ema_slow": round(es, 4),
        "ema_spread": round(ema_spread, 5),
        "spread_momentum": round(spread_momentum, 6),
        "price_vs_slow_ema": round(price_vs_slow, 5),
        "regime": ctx.regime.value,
        "signed_exposure": round(signed_exposure, 4),
    }

    # ── Exit / cover conditions ───────────────────────────────────────
    if ctx.regime in (RegimeLabel.TREND_UP, RegimeLabel.HIGH_VOL):
        return StrategyIntent(
            action=Action.EXIT_SHORT,
            confidence=0.90,
            desired_exposure_frac=0.0,
            horizon_hours=4,
            reason=f"Regime exit signal: {ctx.regime.value}",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    if price_vs_slow > EMA_ABOVE_TOLERANCE and currently_short:
        return StrategyIntent(
            action=Action.EXIT_SHORT,
            confidence=0.75,
            desired_exposure_frac=0.0,
            horizon_hours=4,
            reason="Close above slow EMA — structural reversal, covering short",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    if ema_spread > 0 and currently_short:
        return StrategyIntent(
            action=Action.EXIT_SHORT,
            confidence=0.80,
            desired_exposure_frac=0.0,
            horizon_hours=2,
            reason="EMA crossover bullish — fast above slow, covering short",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    # ── Entry conditions ──────────────────────────────────────────────
    bearish_structure = (
        ctx.regime == RegimeLabel.TREND_DOWN
        and ema_spread < -0.002              # fast materially below slow
        and price_vs_slow < EMA_ABOVE_TOLERANCE  # price not far above slow EMA
        and spread_momentum <= 0             # trend strengthening or stable bearishly
    )

    if bearish_structure:
        spread_strength = min(abs(ema_spread) / 0.02, 1.0)
        exposure = MIN_EXPOSURE + spread_strength * (MAX_EXPOSURE - MIN_EXPOSURE)
        exposure = round(min(exposure, MAX_EXPOSURE), 4)
        confidence = min(0.55 + spread_strength * 0.35, 0.90)

        return StrategyIntent(
            action=Action.ENTER_SHORT,
            confidence=round(confidence, 4),
            desired_exposure_frac=exposure,
            horizon_hours=48,
            reason="Trend-following short entry: bearish EMA structure with TREND_DOWN regime",
            meta={**meta, "spread_strength": round(spread_strength, 4)},
            strategy_id=STRATEGY_ID,
        )

    # ── Hold existing short ───────────────────────────────────────────
    if currently_short:
        return StrategyIntent(
            action=Action.HOLD,
            confidence=0.60,
            desired_exposure_frac=ctx.current_exposure_frac,
            horizon_hours=24,
            reason="No new signal — holding short position",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    # ── Flat / no edge ────────────────────────────────────────────────
    return StrategyIntent(
        action=Action.FLAT,
        confidence=0.55,
        desired_exposure_frac=0.0,
        horizon_hours=0,
        reason="No bearish structure detected — staying flat",
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
