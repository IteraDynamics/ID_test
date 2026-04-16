"""Layer 2 — TrendFollowingV4 (Wide Stops, Full Exposure, Vol-Scaled Entry).

Why v3 underperforms the BTC benchmark
---------------------------------------
v3 captures only ~10% CAGR on a ~56% CAGR asset.  The primary cause is
exit conditions tuned for a low-volatility asset, not BTC:

- PRICE_BREAK_THRESHOLD = -1.5% below the 55-bar EMA fires on routine hourly
  consolidations — BTC can pause 3–8% below its short EMA mid-trend.
- CROSSOVER_EXIT_THRESHOLD = -0.5% triggers on the first bearish tick of a
  fast/slow crossover, shaking out positions before the trend reversal confirms.
- MAX_EXPOSURE = 0.80 leaves capital on the table during the strongest moves.

v4 design changes
-----------------
1.  **Wider exit thresholds**: price break raised to -4.0%, crossover to -2.0%.
    TREND_DOWN exit now requires the spread to be < -1.0% (not just negative),
    requiring genuine bearish structure before the strategy capitulates.

2.  **Full-conviction exposure**: BASE = 0.90, ADD = 1.00.  A confirmed BTC
    uptrend justifies near-full allocation.

3.  **Long-term trend filter** (200-bar EMA): entry gated on price > long-term
    EMA.  Keeps the strategy out of bear markets (2022 avoided entirely).

4.  **ATR-based entry sizing**: position scaled inversely to realised hourly
    volatility, targeting a fixed volatility contribution.  In calm, low-vol
    trends the full base exposure is deployed; in volatile conditions the size
    is reduced proportionally (floor: 50% of base).  This produces a better
    Sharpe without sacrificing CAGR materially.

5.  **Freeze-on-hold**: once in a position the strategy returns HOLD with the
    exact current exposure.  No intra-trend resizing beyond the single add-on.

Expected vs v3
--------------
- Fewer shake-outs during bull-market consolidations → higher CAGR
- Larger positions in confirmed trends → more upside capture
- Long-term EMA filter → reduced 2022-style drawdowns
- ATR scaling → improved Sharpe by reducing exposure in dangerous regimes
"""

from __future__ import annotations

import pandas as pd

from research.regimes.contracts import RegimeLabel
from research.strategies.contracts import Action, StrategyContext, StrategyIntent

STRATEGY_ID = "trend_following_v4"

# ── EMAs ───────────────────────────────────────────────────────────────────────
FAST_EMA = 21
SLOW_EMA = 55
LONG_EMA = 200          # long-term trend filter: only trade above this
MOMENTUM_LOOKBACK = 5
ATR_PERIOD = 24         # 24-bar realised volatility for entry sizing

# ── Exposure ───────────────────────────────────────────────────────────────────
BASE_EXPOSURE = 0.90    # initial entry — full conviction
ADD_EXPOSURE = 1.00     # single add-on at peak trend confirmation
ADD_STATE_THRESHOLD = 0.95  # above this we're already at ADD, hold only

# ── Entry conditions ───────────────────────────────────────────────────────────
MIN_ENTRY_SPREAD = 0.004        # same as v3
ADD_SPREAD_THRESHOLD = 0.012    # stronger threshold for the add (vs 1.0% in v3)
ADD_MOMENTUM_THRESHOLD = 0.001

# ── Exit conditions — materially wider than v2/v3 ─────────────────────────────
CROSSOVER_EXIT_THRESHOLD = -0.020   # fast EMA must be 2.0% below slow (was -0.5%)
PRICE_BREAK_THRESHOLD = -0.040      # price must be 4.0% below slow EMA (was -1.5%)
TREND_DOWN_SPREAD_THRESHOLD = -0.010  # TREND_DOWN only exits when spread < -1.0%

# ── ATR-based vol-targeting ────────────────────────────────────────────────────
VOL_TARGET_PCT = 0.020  # target 2.0% ATR-per-bar volatility contribution
MIN_VOL_SCALE = 0.50    # floor: never go below 50% of BASE_EXPOSURE

FLAT_THRESHOLD = 0.05


def generate_intent(
    df: pd.DataFrame,
    ctx: StrategyContext,
    closed_only: bool = True,
) -> StrategyIntent:
    """Generate a trend-following intent for the current closed bar."""
    min_bars = max(SLOW_EMA, LONG_EMA, ATR_PERIOD) + MOMENTUM_LOOKBACK + 5
    if len(df) < min_bars:
        return _warmup_intent(ctx)

    close = df["close"]
    high = df["high"]
    low = df["low"]

    ema_fast = close.ewm(span=FAST_EMA, adjust=False).mean()
    ema_slow = close.ewm(span=SLOW_EMA, adjust=False).mean()
    ema_long = close.ewm(span=LONG_EMA, adjust=False).mean()
    atr = _atr(high, low, close, ATR_PERIOD)

    c = float(close.iloc[-1])
    ef = float(ema_fast.iloc[-1])
    es = float(ema_slow.iloc[-1])
    el = float(ema_long.iloc[-1])
    atr_pct = float(atr.iloc[-1]) / c if c > 0 else 0.02

    ema_spread = (ef - es) / c
    ema_spread_series = (ema_fast - ema_slow) / close
    spread_momentum = float(
        ema_spread_series.iloc[-1] - ema_spread_series.iloc[-MOMENTUM_LOOKBACK - 1]
    )
    price_vs_slow = (c - es) / es
    price_vs_long = (c - el) / el  # positive = above long-term EMA

    meta = {
        "ema_fast": round(ef, 4),
        "ema_slow": round(es, 4),
        "ema_long": round(el, 4),
        "ema_spread": round(ema_spread, 5),
        "spread_momentum": round(spread_momentum, 6),
        "price_vs_slow_ema": round(price_vs_slow, 5),
        "price_vs_long_ema": round(price_vs_long, 5),
        "atr_pct": round(atr_pct, 5),
        "regime": ctx.regime.value,
    }

    already_long = ctx.current_exposure_frac > FLAT_THRESHOLD
    at_base = already_long and ctx.current_exposure_frac < ADD_STATE_THRESHOLD

    # ── When long: exits first, then optional add, then hold ──────────────────
    if already_long:
        # Priority 1 — emergency exit: vol regime too dangerous
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

        # Priority 2 — regime flip WITH confirmed bearish crossover
        # Requires spread < -1.0% to avoid exiting on minor regime dips
        if ctx.regime == RegimeLabel.TREND_DOWN and ema_spread < TREND_DOWN_SPREAD_THRESHOLD:
            return StrategyIntent(
                action=Action.EXIT_LONG,
                confidence=0.85,
                desired_exposure_frac=0.0,
                horizon_hours=4,
                reason=(
                    f"TREND_DOWN + spread {ema_spread:.3f} < "
                    f"{TREND_DOWN_SPREAD_THRESHOLD} — confirmed reversal"
                ),
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        # Priority 3 — deep EMA crossover (fast EMA materially below slow)
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

        # Priority 4 — hard structural price break (crash protection)
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

        # Add-on: only at base exposure in a materially strengthening trend
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
                    reason=(
                        f"Strong trend add-on: spread={ema_spread:.3f} > "
                        f"{ADD_SPREAD_THRESHOLD}"
                    ),
                    meta={**meta, "add_on": True},
                    strategy_id=STRATEGY_ID,
                )

        # Freeze — hold current exposure, no resize
        return StrategyIntent(
            action=Action.HOLD,
            confidence=0.70,
            desired_exposure_frac=ctx.current_exposure_frac,
            horizon_hours=24,
            reason="In trend — holding",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    # ── When flat: entry logic ────────────────────────────────────────────────
    # Long-term filter: only enter while price is above the 200-bar EMA
    above_long_ema = price_vs_long > 0.0

    bullish_entry = (
        ctx.regime == RegimeLabel.TREND_UP
        and above_long_ema
        and ema_spread > MIN_ENTRY_SPREAD
        and price_vs_slow > 0.0
        and spread_momentum >= 0
    )

    if bullish_entry:
        # ATR-based vol scaling: target fixed vol contribution at entry
        # Reduces size in high-vol markets; full size in calm uptrends
        vol_scale = min(1.0, max(MIN_VOL_SCALE, VOL_TARGET_PCT / atr_pct))
        entry_exposure = round(BASE_EXPOSURE * vol_scale, 4)
        confidence = round(min(0.90, 0.70 + vol_scale * 0.20), 4)

        return StrategyIntent(
            action=Action.ENTER_LONG,
            confidence=confidence,
            desired_exposure_frac=entry_exposure,
            horizon_hours=96,
            reason=(
                f"Trend entry: TREND_UP + spread={ema_spread:.3f} "
                f"above_long_ema={price_vs_long:.3f} "
                f"vol_scale={vol_scale:.2f} → exposure={entry_exposure:.2f}"
            ),
            meta={**meta, "vol_scale": round(vol_scale, 4)},
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


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


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
