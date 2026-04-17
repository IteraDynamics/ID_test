"""Layer 2 — TrendFollowingV7 (Indicator-Based Entry, No Regime Gate).

Root cause analysis of v4–v6 ceiling at ~22% CAGR
---------------------------------------------------
All previous versions gated entry on ``ctx.regime == RegimeLabel.TREND_UP``.
The BaselineRegimeEngine classifies TREND_UP only when ATR is between 1.2%
and 4.0% AND the slow EMA momentum is positive.  BTC's hourly ATR during
the strongest bull-market phases runs 3–6%, triggering HIGH_VOL or
VOL_EXPANSION priority rules BEFORE the trend check is reached.

Consequence: the strategy is systematically blocked from entering (or
re-entering after an exit) during the most profitable trend phases — the
explosive acceleration legs of BTC bull runs.  It can only invest during
"moderate" trend conditions, capturing ~22% CAGR of a 56% benchmark.

v7 fix
------
**Entry no longer requires TREND_UP regime.**

Entry is gated on underlying EMA indicators directly:
  - Price above the 200-bar long-term EMA (bear market filter retained)
  - Fast/slow EMA spread > 0.4% (confirmed trend structure)
  - Price above slow EMA (directional confirmation)
  - Not in a confirmed TREND_DOWN regime
  - Direct ATR check: not in crisis (hourly ATR < 5.5%)

The regime label is still used for:
  - TREND_DOWN + confirmed spread → exit (unchanged)
  - Emergency exit replaced by direct ATR crisis threshold (5.5% vs 4% regime)

The 5.5% crisis ATR threshold lets the strategy stay in during normal
high-volatility trending (3–5% ATR), while still exiting during genuine
crashes (March 2020 COVID, May 2021, November 2022 FTX collapse).
"""

from __future__ import annotations

import pandas as pd

from research.regimes.contracts import RegimeLabel
from research.strategies.contracts import Action, StrategyContext, StrategyIntent

STRATEGY_ID = "trend_following_v7"

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

# ── Entry ──────────────────────────────────────────────────────────────────────
MIN_ENTRY_SPREAD = 0.004

# ── Add-on ─────────────────────────────────────────────────────────────────────
ADD_SPREAD_THRESHOLD = 0.015
ADD_MOMENTUM_THRESHOLD = 0.001

# ── Exit ───────────────────────────────────────────────────────────────────────
CROSSOVER_EXIT_THRESHOLD = -0.020
PRICE_BREAK_THRESHOLD = -0.040
TREND_DOWN_SPREAD_THRESHOLD = -0.010
TREND_DOWN_CONFIRM_BARS = 3
# Direct ATR crisis threshold — bypasses regime label.
# Keeps strategy in during normal high-vol trending (3–5% ATR),
# exits only during genuine market dislocations (>5.5%).
CRISIS_ATR_PCT = 0.055

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

    # ── When long ─────────────────────────────────────────────────────────────
    if already_long:
        # Priority 1 — direct ATR crisis exit (replaces regime HIGH_VOL gate)
        if atr_pct > CRISIS_ATR_PCT:
            return StrategyIntent(
                action=Action.EXIT_LONG,
                confidence=0.95,
                desired_exposure_frac=0.0,
                horizon_hours=1,
                reason=f"Crisis volatility: ATR {atr_pct:.3f} > {CRISIS_ATR_PCT}",
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        # Priority 2 — sustained TREND_DOWN with confirmed bearish spread
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

        # Priority 4 — hard structural price break
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

        # Add-on
        if at_base:
            strong_trend = (
                ema_spread > ADD_SPREAD_THRESHOLD
                and spread_momentum > ADD_MOMENTUM_THRESHOLD
                and atr_pct < CRISIS_ATR_PCT
            )
            if strong_trend:
                return StrategyIntent(
                    action=Action.ENTER_LONG,
                    confidence=0.85,
                    desired_exposure_frac=ADD_EXPOSURE,
                    horizon_hours=72,
                    reason=f"Add-on: spread={ema_spread:.3f} > {ADD_SPREAD_THRESHOLD}",
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

    # ── When flat: indicator-based entry, no regime label required ────────────
    in_crisis = atr_pct > CRISIS_ATR_PCT
    in_downtrend = ctx.regime == RegimeLabel.TREND_DOWN

    bullish_entry = (
        not in_crisis
        and not in_downtrend
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
                f"Trend entry: spread={ema_spread:.3f} "
                f"above_long={price_vs_long:.3f} "
                f"regime={ctx.regime.value}"
            ),
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    return StrategyIntent(
        action=Action.FLAT,
        confidence=0.60,
        desired_exposure_frac=0.0,
        horizon_hours=0,
        reason=f"No entry: crisis={in_crisis} downtrend={in_downtrend} spread={ema_spread:.4f}",
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
