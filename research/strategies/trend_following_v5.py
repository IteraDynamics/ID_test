"""Layer 2 — TrendFollowingV5 (Recalibrated Vol Targeting, Confirmed Exits).

Changes from v4
---------------
Terminal analysis of v4 identified four improvement areas:

1.  **VOL_TARGET_PCT 2% → 3%**
    BTC's typical hourly ATR is 2–4%.  With a 2% target, vol_scale was
    systematically ~0.5–0.67, cutting the intended 90% base exposure to 45–60%.
    Avg entry was 56.8% NAV — roughly half the intended size.  Raising the
    target to 3% keeps vol_scale near 1.0 during normal BTC conditions and only
    reduces size during genuinely extreme volatility (>6% hourly ATR).

2.  **Drop spread_momentum >= 0 entry gate**
    Requiring the 5-bar EMA spread momentum to be non-negative blocked entries
    during healthy consolidation phases of uptrends where momentum oscillates
    around zero.  The remaining three entry conditions (TREND_UP regime, above
    long EMA, spread > 0.4%, price above slow EMA) are sufficient discipline.

3.  **TREND_DOWN exit requires N confirmed bars of bearish spread**
    A single TREND_DOWN regime bar with bearish spread could trigger an exit
    that proved to be a one-bar dip.  v5 requires the spread to have been below
    TREND_DOWN_SPREAD_THRESHOLD for TREND_DOWN_CONFIRM_BARS consecutive bars
    before the exit fires.  Computed stateless from the spread series in df.

4.  **Tighten add-on threshold: 1.2% → 1.5%**
    Reserve the 90% → 100% add-on for genuinely exceptional trend strength,
    not the first moderately strong TREND_UP bar.
"""

from __future__ import annotations

import pandas as pd

from research.regimes.contracts import RegimeLabel
from research.strategies.contracts import Action, StrategyContext, StrategyIntent

STRATEGY_ID = "trend_following_v5"

# ── EMAs ───────────────────────────────────────────────────────────────────────
FAST_EMA = 21
SLOW_EMA = 55
LONG_EMA = 200
MOMENTUM_LOOKBACK = 5
ATR_PERIOD = 24

# ── Exposure ───────────────────────────────────────────────────────────────────
BASE_EXPOSURE = 0.90
ADD_EXPOSURE = 1.00
ADD_STATE_THRESHOLD = 0.95

# ── Entry conditions ───────────────────────────────────────────────────────────
MIN_ENTRY_SPREAD = 0.004

# ── Add-on conditions ──────────────────────────────────────────────────────────
ADD_SPREAD_THRESHOLD = 0.015    # raised from 1.2% → 1.5%: reserve for strong trends
ADD_MOMENTUM_THRESHOLD = 0.001

# ── Exit conditions ────────────────────────────────────────────────────────────
CROSSOVER_EXIT_THRESHOLD = -0.020
PRICE_BREAK_THRESHOLD = -0.040
TREND_DOWN_SPREAD_THRESHOLD = -0.010
TREND_DOWN_CONFIRM_BARS = 3     # spread must be below threshold for this many bars

# ── ATR vol-targeting (v5: raised target to match typical BTC hourly ATR) ─────
VOL_TARGET_PCT = 0.030          # was 0.020 in v4 — now matches typical BTC hourly ATR
MIN_VOL_SCALE = 0.50

FLAT_THRESHOLD = 0.05


def generate_intent(
    df: pd.DataFrame,
    ctx: StrategyContext,
    closed_only: bool = True,
) -> StrategyIntent:
    """Generate a trend-following intent for the current closed bar."""
    min_bars = max(SLOW_EMA, LONG_EMA, ATR_PERIOD) + MOMENTUM_LOOKBACK + TREND_DOWN_CONFIRM_BARS + 5
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
    atr_pct = float(atr.iloc[-1]) / c if c > 0 else 0.03

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
        "atr_pct": round(atr_pct, 5),
        "regime": ctx.regime.value,
    }

    already_long = ctx.current_exposure_frac > FLAT_THRESHOLD
    at_base = already_long and ctx.current_exposure_frac < ADD_STATE_THRESHOLD

    # ── When long: exits first, then optional add, then hold ──────────────────
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

        # Priority 2 — sustained TREND_DOWN with confirmed bearish spread
        # Requires spread below threshold for TREND_DOWN_CONFIRM_BARS consecutive
        # bars, preventing single-bar dip exits.
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
                    f"for {TREND_DOWN_CONFIRM_BARS} bars — confirmed reversal"
                ),
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        # Priority 3 — deep EMA crossover
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

        # Add-on: tighter threshold (1.5%) — only in strongest trends
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

        return StrategyIntent(
            action=Action.HOLD,
            confidence=0.70,
            desired_exposure_frac=ctx.current_exposure_frac,
            horizon_hours=24,
            reason="In trend — holding",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    # ── When flat: entry (no spread_momentum gate) ────────────────────────────
    bullish_entry = (
        ctx.regime == RegimeLabel.TREND_UP
        and price_vs_long > 0.0          # above long-term EMA
        and ema_spread > MIN_ENTRY_SPREAD
        and price_vs_slow > 0.0
        # spread_momentum gate removed: was blocking valid re-entries during
        # healthy consolidation phases where momentum oscillates near zero
    )

    if bullish_entry:
        vol_scale = min(1.0, max(MIN_VOL_SCALE, VOL_TARGET_PCT / atr_pct))
        entry_exposure = round(BASE_EXPOSURE * vol_scale, 4)
        confidence = round(min(0.90, 0.70 + vol_scale * 0.20), 4)

        return StrategyIntent(
            action=Action.ENTER_LONG,
            confidence=confidence,
            desired_exposure_frac=entry_exposure,
            horizon_hours=96,
            reason=(
                f"Trend entry: TREND_UP spread={ema_spread:.3f} "
                f"above_long={price_vs_long:.3f} "
                f"vol_scale={vol_scale:.2f} → {entry_exposure:.2f}"
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
