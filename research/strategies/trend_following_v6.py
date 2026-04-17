"""Layer 2 — TrendFollowingV6 (Fixed Full Exposure, No Vol Scaling).

Why v4 and v5 stalled at ~22% CAGR
-------------------------------------
Both versions used ATR-based entry sizing designed to target a fixed
volatility contribution.  Terminal analysis showed entries happen
predominantly when BTC's hourly ATR is 4–6% — breakouts and acceleration
phases — so vol_scale was consistently 0.50–0.65, cutting the 90% base
exposure to 45–58% at every single entry.  The strategy was trying to enter
trends at half-size precisely when it should be most confident.

v6 hypothesis
-------------
The exit/entry notional ratio (1.7x in v4/v5) shows winners outsize losers
significantly.  If the entry sizing is doubled (from ~58% to 90%), the P&L
should scale roughly proportionally — pushing from ~22% CAGR toward 35%+.

Changes from v5
---------------
1.  **Remove ATR vol scaling entirely.**  Entry is always BASE_EXPOSURE (0.90).
    Single variable changed from v5 to isolate the effect cleanly.
    The 200-bar long-term filter and wider exit thresholds are retained.
"""

from __future__ import annotations

import pandas as pd

from research.regimes.contracts import RegimeLabel
from research.strategies.contracts import Action, StrategyContext, StrategyIntent

STRATEGY_ID = "trend_following_v6"

# ── EMAs ───────────────────────────────────────────────────────────────────────
FAST_EMA = 21
SLOW_EMA = 55
LONG_EMA = 200
MOMENTUM_LOOKBACK = 5

# ── Exposure ───────────────────────────────────────────────────────────────────
BASE_EXPOSURE = 0.90
ADD_EXPOSURE = 1.00
ADD_STATE_THRESHOLD = 0.95

# ── Entry conditions ───────────────────────────────────────────────────────────
MIN_ENTRY_SPREAD = 0.004

# ── Add-on conditions ──────────────────────────────────────────────────────────
ADD_SPREAD_THRESHOLD = 0.015
ADD_MOMENTUM_THRESHOLD = 0.001

# ── Exit conditions ────────────────────────────────────────────────────────────
CROSSOVER_EXIT_THRESHOLD = -0.020
PRICE_BREAK_THRESHOLD = -0.040
TREND_DOWN_SPREAD_THRESHOLD = -0.010
TREND_DOWN_CONFIRM_BARS = 3

FLAT_THRESHOLD = 0.05


def generate_intent(
    df: pd.DataFrame,
    ctx: StrategyContext,
    closed_only: bool = True,
) -> StrategyIntent:
    """Generate a trend-following intent for the current closed bar."""
    min_bars = max(SLOW_EMA, LONG_EMA) + MOMENTUM_LOOKBACK + TREND_DOWN_CONFIRM_BARS + 5
    if len(df) < min_bars:
        return _warmup_intent(ctx)

    close = df["close"]
    high = df["high"]
    low = df["low"]

    ema_fast = close.ewm(span=FAST_EMA, adjust=False).mean()
    ema_slow = close.ewm(span=SLOW_EMA, adjust=False).mean()
    ema_long = close.ewm(span=LONG_EMA, adjust=False).mean()

    c = float(close.iloc[-1])
    ef = float(ema_fast.iloc[-1])
    es = float(ema_slow.iloc[-1])
    el = float(ema_long.iloc[-1])

    ema_spread_series = (ema_fast - ema_slow) / close
    ema_spread = float(ema_spread_series.iloc[-1])
    spread_momentum = float(
        ema_spread_series.iloc[-1] - ema_spread_series.iloc[-MOMENTUM_LOOKBACK - 1]
    )
    price_vs_slow = (c - es) / es
    price_vs_long = (c - el) / el

    meta = {
        "ema_fast": round(ef, 4),
        "ema_slow": round(es, 4),
        "ema_long": round(el, 4),
        "ema_spread": round(ema_spread, 5),
        "spread_momentum": round(spread_momentum, 6),
        "price_vs_slow_ema": round(price_vs_slow, 5),
        "price_vs_long_ema": round(price_vs_long, 5),
        "regime": ctx.regime.value,
    }

    already_long = ctx.current_exposure_frac > FLAT_THRESHOLD
    at_base = already_long and ctx.current_exposure_frac < ADD_STATE_THRESHOLD

    # ── When long ─────────────────────────────────────────────────────────────
    if already_long:
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

        recent_spreads = ema_spread_series.iloc[-TREND_DOWN_CONFIRM_BARS:]
        sustained_bear = bool((recent_spreads < TREND_DOWN_SPREAD_THRESHOLD).all())
        if ctx.regime == RegimeLabel.TREND_DOWN and sustained_bear:
            return StrategyIntent(
                action=Action.EXIT_LONG,
                confidence=0.85,
                desired_exposure_frac=0.0,
                horizon_hours=4,
                reason=(
                    f"TREND_DOWN + spread below {TREND_DOWN_SPREAD_THRESHOLD} "
                    f"for {TREND_DOWN_CONFIRM_BARS} bars"
                ),
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        if ema_spread < CROSSOVER_EXIT_THRESHOLD:
            return StrategyIntent(
                action=Action.EXIT_LONG,
                confidence=0.80,
                desired_exposure_frac=0.0,
                horizon_hours=4,
                reason=f"Deep EMA crossover: spread {ema_spread:.3f} < {CROSSOVER_EXIT_THRESHOLD}",
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        if price_vs_slow < PRICE_BREAK_THRESHOLD:
            return StrategyIntent(
                action=Action.EXIT_LONG,
                confidence=0.75,
                desired_exposure_frac=0.0,
                horizon_hours=4,
                reason=f"Price {price_vs_slow:.3f} < {PRICE_BREAK_THRESHOLD} below slow EMA",
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        if at_base:
            strong_trend = (
                ctx.regime == RegimeLabel.TREND_UP
                and ema_spread > ADD_SPREAD_THRESHOLD
                and spread_momentum > ADD_MOMENTUM_THRESHOLD
            )
            if strong_trend:
                return StrategyIntent(
                    action=Action.ENTER_LONG,
                    confidence=0.85,
                    desired_exposure_frac=ADD_EXPOSURE,
                    horizon_hours=72,
                    reason=f"Strong trend add-on: spread={ema_spread:.3f} > {ADD_SPREAD_THRESHOLD}",
                    meta={**meta, "add_on": True},
                    strategy_id=STRATEGY_ID,
                )

        return StrategyIntent(
            action=Action.HOLD,
            confidence=0.70,
            desired_exposure_frac=ctx.current_exposure_frac,
            horizon_hours=24,
            reason="In trend — holding",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    # ── When flat ─────────────────────────────────────────────────────────────
    bullish_entry = (
        ctx.regime == RegimeLabel.TREND_UP
        and price_vs_long > 0.0
        and ema_spread > MIN_ENTRY_SPREAD
        and price_vs_slow > 0.0
    )

    if bullish_entry:
        return StrategyIntent(
            action=Action.ENTER_LONG,
            confidence=0.80,
            desired_exposure_frac=BASE_EXPOSURE,
            horizon_hours=96,
            reason=(
                f"Trend entry: TREND_UP spread={ema_spread:.3f} "
                f"above_long={price_vs_long:.3f}"
            ),
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    return StrategyIntent(
        action=Action.FLAT,
        confidence=0.60,
        desired_exposure_frac=0.0,
        horizon_hours=0,
        reason="No bullish structure or below long-term EMA — flat",
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
