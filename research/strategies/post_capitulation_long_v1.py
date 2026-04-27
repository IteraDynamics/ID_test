"""Layer 2 — PostCapitulationLong v1 (Recovery Capture Sleeve).

Philosophy
----------
Trend-following has three phases relative to a crash cycle:

  1. In-position during bull run (captures the move)
  2. Exiting during crash (correct — protects capital)
  3. FLAT while volatility compresses post-crash (idle — misses the first
     20–30% of every recovery because EMA confirmation arrives late)

This sleeve targets phase 3: the post-crash stabilisation window.

It fires ONLY when all of the following are simultaneously true:
  1. Price is 25%+ below its 90-day rolling high (confirmed crash, not a
     routine pullback in a bull market).
  2. ATR% peaked above 3.8% in the last 7 days (a genuine volatility spike
     occurred — distinguishes crashes from slow grinds down).
  3. Current ATR% is now in [1.0%, 3.5%] — vol is compressing.  The crash
     leg is over; we are not buying into active panic.
  4. Regime is NOT HIGH_VOL and NOT TREND_UP.  HIGH_VOL means the crash is
     still live.  TREND_UP means trend-following already re-entered; our
     job is done.
  5. EMA spread (fast − slow) / close is in [−10%, −0.2%]: still bearish
     (trend-following is flat) but not in free-fall.
  6. EMA spread has been improving (less negative) over the last 6 bars:
     bearish momentum is easing, not intensifying.

Orthogonality
-------------
By construction this sleeve is negatively or near-zero correlated with
Fund v1:
  - Fund v1 is exiting/flat when this fires (price down 25%+, vol was high)
  - This sleeve exits when Fund v1 is entering (EMA spread turns bullish)
  - They never hold simultaneously in steady state

Exit conditions (any single trigger):
  1. Regime HIGH_VOL or TREND_DOWN resumes: crash leg continuing → exit.
  2. ATR% > 5.0%: vol spike = new crash leg → exit.
  3. EMA spread > +0.5%: EMA crossover approaching; trend-following will
     enter; hand off and go flat.
  4. Drawdown from 90d high < 12%: price recovered substantially → take
     profit.
  5. EMA spread < −10%: trend worsening beyond entry level → cut.

Sizing
------
30% NAV.  This is a recovery capture sleeve, not the primary P&L driver.
Conservative sizing ensures the portfolio survives a wrong-entry scenario.
"""

from __future__ import annotations

import pandas as pd
import numpy as np

from research.regimes.contracts import RegimeLabel
from research.strategies.contracts import Action, StrategyContext, StrategyIntent

STRATEGY_ID = "post_capitulation_long_v1"

# ── Crash confirmation ─────────────────────────────────────────────────────────
DRAWDOWN_LOOKBACK    = 2160    # 90-day rolling high window (1H bars)
MIN_DRAWDOWN         = 0.25    # price must be ≥ 25% below 90d high
PEAK_ATR_LOOKBACK    = 168     # 7-day window for ATR peak check
PEAK_ATR_MIN         = 0.038   # ATR must have peaked > 3.8% recently

# ── Volatility compression ─────────────────────────────────────────────────────
ATR_PERIOD           = 24      # 24-bar ATR (≈ 1 trading day)
CURRENT_ATR_MAX      = 0.035   # vol compressing: current ATR < 3.5%
CURRENT_ATR_MIN      = 0.010   # market not dead: current ATR > 1.0%

# ── EMA structure ──────────────────────────────────────────────────────────────
FAST_EMA             = 21
SLOW_EMA             = 55
EMA_SPREAD_MAX       = -0.002  # still bearish (fast < slow — TF is flat)
EMA_SPREAD_MIN       = -0.10   # not catastrophically bearish (-10%+)
EMA_SPREAD_DELTA_BARS = 6      # spread must be improving over last N bars

# ── Sizing ─────────────────────────────────────────────────────────────────────
ENTRY_EXPOSURE       = 0.30    # 30% NAV — recovery capture, not primary driver

# ── Exit thresholds ────────────────────────────────────────────────────────────
ATR_SPIKE_EXIT       = 0.050   # new crash leg: vol spike exit
TREND_HANDOFF_SPREAD = 0.005   # EMA spread bullish: trend-following entering
RECOVERY_DD_EXIT     = 0.12    # drawdown < 12% from 90d high: recovered enough
SPREAD_STOP          = -0.10   # spread worsening past −10%: cut

FLAT_THRESHOLD       = 0.05    # exposure below this = effectively flat


def generate_intent(
    df: pd.DataFrame,
    ctx: StrategyContext,
    closed_only: bool = True,
) -> StrategyIntent:
    """Generate a post-capitulation recovery intent for the current closed bar."""
    min_bars = DRAWDOWN_LOOKBACK + max(SLOW_EMA, ATR_PERIOD) + PEAK_ATR_LOOKBACK + 10
    if len(df) < min_bars:
        return _warmup(ctx)

    close = df["close"]
    high  = df["high"]
    low   = df["low"]

    ema_fast = close.ewm(span=FAST_EMA, adjust=False).mean()
    ema_slow = close.ewm(span=SLOW_EMA, adjust=False).mean()
    atr      = _atr(high, low, close, ATR_PERIOD)

    c           = float(close.iloc[-1])
    atr_now     = float(atr.iloc[-1]) / c if c > 0 else 0.03

    ema_spread_series = (ema_fast - ema_slow) / close.clip(lower=1.0)
    ema_spread        = float(ema_spread_series.iloc[-1])

    # 90-day rolling high → drawdown
    rolling_high = float(close.rolling(DRAWDOWN_LOOKBACK).max().iloc[-1])
    drawdown_now = (rolling_high - c) / rolling_high if rolling_high > 0 else 0.0

    # Peak ATR in last 7 days
    atr_pct_series = atr / close.clip(lower=1.0)
    peak_atr       = float(atr_pct_series.iloc[-PEAK_ATR_LOOKBACK:].max())

    # EMA spread trend over last N bars
    spread_improving = bool(
        ema_spread_series.iloc[-1] > ema_spread_series.iloc[-(EMA_SPREAD_DELTA_BARS + 1)]
    )

    currently_long = ctx.current_exposure_frac > FLAT_THRESHOLD

    meta = {
        "drawdown":         round(drawdown_now, 4),
        "atr_pct":          round(atr_now, 5),
        "peak_atr_7d":      round(peak_atr, 5),
        "ema_spread":       round(ema_spread, 5),
        "spread_improving": spread_improving,
        "regime":           ctx.regime.value,
        "rolling_high":     round(rolling_high, 2),
    }

    # ── EXIT: when in a recovery position ─────────────────────────────────────
    if currently_long:
        # New crash leg: vol spike
        if atr_now > ATR_SPIKE_EXIT:
            return StrategyIntent(
                action=Action.EXIT_LONG,
                confidence=0.90,
                desired_exposure_frac=0.0,
                horizon_hours=2,
                reason=f"ATR spike {atr_now:.3f} > {ATR_SPIKE_EXIT:.3f} — new crash leg, exiting",
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        # Crash resuming: regime deteriorated
        if ctx.regime in (RegimeLabel.HIGH_VOL, RegimeLabel.TREND_DOWN) and atr_now > 0.025:
            return StrategyIntent(
                action=Action.EXIT_LONG,
                confidence=0.85,
                desired_exposure_frac=0.0,
                horizon_hours=2,
                reason=f"Regime {ctx.regime.value} with elevated ATR — crash resuming",
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        # EMA spread worsening past stop level
        if ema_spread < SPREAD_STOP:
            return StrategyIntent(
                action=Action.EXIT_LONG,
                confidence=0.80,
                desired_exposure_frac=0.0,
                horizon_hours=4,
                reason=f"EMA spread {ema_spread:.4f} < {SPREAD_STOP}: trend worsening — cut",
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        # Hand off to trend-following: EMA spread approaching bullish crossover
        if ema_spread > TREND_HANDOFF_SPREAD:
            return StrategyIntent(
                action=Action.EXIT_LONG,
                confidence=0.80,
                desired_exposure_frac=0.0,
                horizon_hours=4,
                reason=f"EMA spread {ema_spread:.4f} > {TREND_HANDOFF_SPREAD} — handing off to trend-following",
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        # Recovery target reached: drawdown compressed significantly
        if drawdown_now < RECOVERY_DD_EXIT:
            return StrategyIntent(
                action=Action.EXIT_LONG,
                confidence=0.75,
                desired_exposure_frac=0.0,
                horizon_hours=4,
                reason=f"Recovery target: drawdown {drawdown_now:.1%} < {RECOVERY_DD_EXIT:.0%} — take profit",
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        # Hold: recovery in progress
        return StrategyIntent(
            action=Action.HOLD,
            confidence=0.65,
            desired_exposure_frac=ctx.current_exposure_frac,
            horizon_hours=168,
            reason=f"Recovery in progress: drawdown={drawdown_now:.1%}, spread={ema_spread:.4f}",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    # ── ENTRY: post-capitulation setup ────────────────────────────────────────

    # Gate 1: not in active crash vol or established bull
    if ctx.regime == RegimeLabel.HIGH_VOL:
        return _flat("Regime HIGH_VOL: crash still live — waiting", meta)

    if ctx.regime == RegimeLabel.TREND_UP:
        return _flat("Regime TREND_UP: trend-following active — post-cap inactive", meta)

    # Gate 2: confirmed major drawdown
    if drawdown_now < MIN_DRAWDOWN:
        return _flat(
            f"Drawdown {drawdown_now:.1%} < {MIN_DRAWDOWN:.0%}: not a crash — post-cap inactive",
            meta,
        )

    # Gate 3: genuine vol spike occurred (confirms crash, not slow grind)
    if peak_atr < PEAK_ATR_MIN:
        return _flat(
            f"Peak ATR (7d) {peak_atr:.3f} < {PEAK_ATR_MIN:.3f}: no vol spike — not a crash",
            meta,
        )

    # Gate 4: vol is now compressing (crash leg ending)
    if atr_now > CURRENT_ATR_MAX:
        return _flat(
            f"ATR {atr_now:.3f} > {CURRENT_ATR_MAX:.3f}: vol not yet compressed — wait",
            meta,
        )

    if atr_now < CURRENT_ATR_MIN:
        return _flat(
            f"ATR {atr_now:.3f} < {CURRENT_ATR_MIN:.3f}: market inactive",
            meta,
        )

    # Gate 5: EMA spread — still bearish (TF flat) but not catastrophic
    if ema_spread > EMA_SPREAD_MAX:
        return _flat(
            f"EMA spread {ema_spread:.4f} > {EMA_SPREAD_MAX:.4f}: trend-following may already be long",
            meta,
        )

    if ema_spread < EMA_SPREAD_MIN:
        return _flat(
            f"EMA spread {ema_spread:.4f} < {EMA_SPREAD_MIN:.2f}: trend too bearish to enter",
            meta,
        )

    # Gate 6: bearish momentum easing
    if not spread_improving:
        return _flat(
            "EMA spread not improving over last 6 bars — bearish pressure not easing",
            meta,
        )

    # All gates passed: enter recovery position
    confidence = round(
        0.60
        + min((drawdown_now - MIN_DRAWDOWN) / 0.30, 0.25)   # deeper crash = higher conf
        + min((CURRENT_ATR_MAX - atr_now) / CURRENT_ATR_MAX, 0.15),  # lower vol = higher conf
        4,
    )

    return StrategyIntent(
        action=Action.ENTER_LONG,
        confidence=confidence,
        desired_exposure_frac=ENTRY_EXPOSURE,
        horizon_hours=720,
        reason=(
            f"Post-capitulation entry: drawdown={drawdown_now:.0%} "
            f"peak_atr(7d)={peak_atr:.3f} cur_atr={atr_now:.3f} "
            f"spread={ema_spread:.4f} regime={ctx.regime.value}"
        ),
        meta=meta,
        strategy_id=STRATEGY_ID,
    )


# ── Helpers ────────────────────────────────────────────────────────────────────

def _flat(reason: str, meta: dict) -> StrategyIntent:
    return StrategyIntent(
        action=Action.FLAT,
        confidence=0.55,
        desired_exposure_frac=0.0,
        horizon_hours=0,
        reason=reason,
        meta=meta,
        strategy_id=STRATEGY_ID,
    )


def _warmup(ctx: StrategyContext) -> StrategyIntent:
    return StrategyIntent(
        action=Action.FLAT,
        confidence=0.0,
        desired_exposure_frac=0.0,
        horizon_hours=0,
        reason="Insufficient data — warmup period",
        meta={"regime": ctx.regime.value},
        strategy_id=STRATEGY_ID,
    )


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()
