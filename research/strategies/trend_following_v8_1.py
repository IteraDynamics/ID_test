"""Layer 2 — TrendFollowingV8_1 (v8 + Confirmed Trend Window).

Root cause of v8's slippage problem
-------------------------------------
v8 had 281 trades with a 33.6% win rate — meaning ~188 losing round-trips.
Each failed entry pays full slippage twice (entry + exit).  At ~$1,700 avg
slippage per trade, those 188 losses generated roughly $320k of the $477k
total slippage.  Winning trades generated the other ~$160k but more than
paid their cost.

The specific failure mode: entering RIGHT AT the EMA crossover.  When the
fast EMA just crossed above the slow EMA, the spread is barely positive and
momentum is fragile.  These fresh-crossover entries frequently reverse within
hours, paying the full round-trip cost for a small or negative return.

v8.1 fix: confirmed trend window
----------------------------------
Before any initial entry fires, require that the EMA spread has been
continuously positive for the last ENTRY_CONFIRM_BARS bars.

  spread_confirmed = min(spread[-N:]) > 0

If the spread dipped below zero at any point in the last N bars, we don't
enter — even if the current bar looks bullish.  This filters out:
  - Fresh crossovers that immediately reverse
  - "Bouncing" spreads that go positive/negative repeatedly
  - Entries during period where the trend has not yet established itself

ENTRY_CONFIRM_BARS = 8 (8 hours on hourly data) is the minimum sustained
duration required.  8 hours was chosen to catch intraday fake-outs while not
being so long as to miss the first 5-10% of a genuine trend move.

The confirmation does NOT apply to add-ons — by definition the position is
already on, so the trend has already been confirmed at entry.

All other v8 parameters are unchanged:
  - Regime-graduated entry sizing (90% / 70%)
  - ENTRY_ATR_CAP = 3.5%
  - spread_momentum > 0 for initial entry
  - MIN_ENTRY_SPREAD = 0.6%, ELEVATED_ENTRY_SPREAD = 1.0%
  - CRISIS_ATR_PCT = 5.0%
"""

from __future__ import annotations

import pandas as pd

from research.regimes.contracts import RegimeLabel
from research.strategies.contracts import Action, StrategyContext, StrategyIntent

STRATEGY_ID = "trend_following_v8_1"

# ── EMAs ───────────────────────────────────────────────────────────────────────
FAST_EMA = 21
SLOW_EMA = 55
LONG_EMA = 200
MOMENTUM_LOOKBACK = 5
ATR_PERIOD = 24

# ── Tier 1 exposure (TREND_UP / VOL_COMPRESSION) ──────────────────────────────
BASE_EXPOSURE = 0.90
MIN_ENTRY_SPREAD = 0.006        # 0.6%

# ── Tier 2 exposure (RANGE / VOL_EXPANSION) ───────────────────────────────────
ELEVATED_EXPOSURE = 0.70
ELEVATED_ENTRY_SPREAD = 0.010   # 1.0%

# ── Slippage control ──────────────────────────────────────────────────────────
ENTRY_ATR_CAP = 0.035           # block new entries above 3.5% ATR

# ── Trend confirmation window (v8.1 addition) ─────────────────────────────────
# Spread must have been positive for ALL of the last N bars before entry fires.
# Filters fresh crossovers and bouncing spreads that quickly reverse.
ENTRY_CONFIRM_BARS = 8

# ── Add-on ─────────────────────────────────────────────────────────────────────
ADD_EXPOSURE = 1.00
ADD_STATE_THRESHOLD = 0.95
ADD_SPREAD_THRESHOLD = 0.020    # 2.0%
ADD_MOMENTUM_THRESHOLD = 0.001

# ── Exits ──────────────────────────────────────────────────────────────────────
CROSSOVER_EXIT_THRESHOLD = -0.020
PRICE_BREAK_THRESHOLD = -0.040
TREND_DOWN_SPREAD_THRESHOLD = -0.010
TREND_DOWN_CONFIRM_BARS = 3
CRISIS_ATR_PCT = 0.050

FLAT_THRESHOLD = 0.05

_BLOCKED_ENTRY_REGIMES = frozenset([RegimeLabel.HIGH_VOL, RegimeLabel.TREND_DOWN])
_TIER1_REGIMES = frozenset([RegimeLabel.TREND_UP, RegimeLabel.VOL_COMPRESSION])


def generate_intent(
    df: pd.DataFrame,
    ctx: StrategyContext,
    closed_only: bool = True,
) -> StrategyIntent:
    """Generate a trend-following intent for the current closed bar."""
    min_bars = (
        max(SLOW_EMA, LONG_EMA, ATR_PERIOD)
        + MOMENTUM_LOOKBACK
        + TREND_DOWN_CONFIRM_BARS
        + ENTRY_CONFIRM_BARS
        + 5
    )
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
        # Priority 1 — crisis exit
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
                    f"TREND_DOWN + spread < {TREND_DOWN_SPREAD_THRESHOLD} "
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

        # Add-on: TREND_UP + low ATR only; no confirmation window needed
        if at_base and ctx.regime == RegimeLabel.TREND_UP and atr_pct <= ENTRY_ATR_CAP:
            strong_trend = (
                ema_spread > ADD_SPREAD_THRESHOLD
                and spread_momentum > ADD_MOMENTUM_THRESHOLD
            )
            if strong_trend:
                return StrategyIntent(
                    action=Action.ENTER_LONG,
                    confidence=0.85,
                    desired_exposure_frac=ADD_EXPOSURE,
                    horizon_hours=72,
                    reason=f"Add-on (TREND_UP): spread={ema_spread:.3f} > {ADD_SPREAD_THRESHOLD}",
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

    # ── When flat: regime-graduated entry ────────────────────────────────────
    if ctx.regime in _BLOCKED_ENTRY_REGIMES or atr_pct > CRISIS_ATR_PCT:
        return StrategyIntent(
            action=Action.FLAT,
            confidence=0.60,
            desired_exposure_frac=0.0,
            horizon_hours=0,
            reason=f"Entry blocked: regime={ctx.regime.value} atr={atr_pct:.3f}",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    if atr_pct > ENTRY_ATR_CAP:
        return StrategyIntent(
            action=Action.FLAT,
            confidence=0.55,
            desired_exposure_frac=0.0,
            horizon_hours=0,
            reason=f"Entry ATR cap: atr={atr_pct:.3f} > {ENTRY_ATR_CAP}",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    if ctx.regime in _TIER1_REGIMES:
        required_spread = MIN_ENTRY_SPREAD
        entry_exposure = BASE_EXPOSURE
        tier = "tier1"
    else:
        required_spread = ELEVATED_ENTRY_SPREAD
        entry_exposure = ELEVATED_EXPOSURE
        tier = "tier2"

    # Confirmation window: spread must have been positive for all N bars.
    # A single negative bar in the window means the trend is not yet established.
    spread_confirmed = float(ema_spread_series.iloc[-ENTRY_CONFIRM_BARS:].min()) > 0

    bullish_entry = (
        ema_spread > required_spread
        and spread_confirmed
        and spread_momentum > 0
        and price_vs_long > 0.0
        and price_vs_slow > 0.0
    )

    if bullish_entry:
        return StrategyIntent(
            action=Action.ENTER_LONG,
            confidence=0.80,
            desired_exposure_frac=entry_exposure,
            horizon_hours=96,
            reason=(
                f"Trend entry ({tier}): regime={ctx.regime.value} "
                f"spread={ema_spread:.3f} confirmed={ENTRY_CONFIRM_BARS}bars "
                f"→ {entry_exposure:.0%} exposure"
            ),
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    return StrategyIntent(
        action=Action.FLAT,
        confidence=0.60,
        desired_exposure_frac=0.0,
        horizon_hours=0,
        reason=(
            f"No signal: spread={ema_spread:.4f} required={required_spread} "
            f"confirmed={spread_confirmed} mom={spread_momentum:.4f} ({tier})"
        ),
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
