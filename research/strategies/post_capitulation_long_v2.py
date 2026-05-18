"""Layer 2 — PostCapitulationLong v2 (Recovery Capture Sleeve).

What v1 taught us
-----------------
v1 had one critical implementation bug:

  ATR spike exit (atr_now > 5.0%) fires during strong RECOVERY moves as
  well as new crash legs.  A 10% up-day after a capitulation bottom
  produces the same hourly ATR signature as a 10% crash day.  v1 was
  exiting positions on its best days, then re-entering 6–12 bars later
  once the EWM ATR decayed.  This created a churn loop — especially on
  ETH (210 trades vs 64 on BTC) — with Exit/Entry ≈ 1.0 and costs
  destroying the underlying positive gross edge (+33% gross on ETH over
  7 years).

Changes vs v1
-------------
1. ATR_SPIKE_EXIT removed entirely from the long-position exit path.
   Recovery bounces produce identical ATR signatures to crash legs.
   Direction cannot be inferred from vol level alone.

2. Regime exit tightened: requires HIGH_VOL AND ema_spread < −6%.
   A brief HIGH_VOL classification during a volatile up-move no longer
   triggers exit.  Both regime AND structural deterioration must confirm.

3. TREND_HANDOFF_SPREAD raised from 0.005 → 0.015.
   Gives the recovery more room before handing off to trend-following.
   Trend-following will enter around the EMA crossover anyway; this
   sleeve needs to stay in until that transition is clear.

4. Entry tightened: MIN_DRAWDOWN 0.25 → 0.28, EMA_SPREAD_MAX −0.002 →
   −0.010.  Reduces noise entries and ETH churn.  Entry only fires at
   meaningful EMA bearish structure, not at near-crossover levels.

5. PEAK_ATR_MIN 0.038 → 0.042.  Requires a more decisive vol spike to
   confirm a genuine crash rather than a prolonged grind-down.

Everything else — sizing, rolling-high drawdown window, EMA periods,
spread improving gate — unchanged from v1.

Philosophy (unchanged)
----------------------
Trend-following exits during crashes and re-enters only after EMA
confirmation.  The gap between exit and re-entry is 4–12 weeks and
contains the fastest price recovery in crypto.  This sleeve occupies
that window exclusively, then hands off once the EMA confirms.
"""

from __future__ import annotations

import pandas as pd
import numpy as np

from research.regimes.contracts import RegimeLabel
from research.strategies.contracts import Action, StrategyContext, StrategyIntent

STRATEGY_ID = "post_capitulation_long_v2"

# ── Crash confirmation ─────────────────────────────────────────────────────────
DRAWDOWN_LOOKBACK     = 2160    # 90-day rolling high window (1H bars)
MIN_DRAWDOWN          = 0.28    # raised: 28% below 90d high (was 25%)
PEAK_ATR_LOOKBACK     = 168     # 7-day window for ATR peak check
PEAK_ATR_MIN          = 0.042   # raised: ATR must have peaked > 4.2% (was 3.8%)

# ── Volatility compression ─────────────────────────────────────────────────────
ATR_PERIOD            = 24      # 24-bar ATR (≈ 1 trading day on 1H bars)
CURRENT_ATR_MAX       = 0.035   # vol compressing: current ATR < 3.5%
CURRENT_ATR_MIN       = 0.010   # market not dead: current ATR > 1.0%

# ── EMA structure ──────────────────────────────────────────────────────────────
FAST_EMA              = 21
SLOW_EMA              = 55
EMA_SPREAD_MAX        = -0.010  # tightened: must be ≥ 1% bearish (was −0.2%)
EMA_SPREAD_MIN        = -0.10   # not catastrophically bearish (−10%+)
EMA_SPREAD_DELTA_BARS = 6       # spread must be improving over last N bars

# ── Sizing ─────────────────────────────────────────────────────────────────────
ENTRY_EXPOSURE        = 0.30    # 30% NAV

# ── Exit thresholds ────────────────────────────────────────────────────────────
# v2: ATR_SPIKE_EXIT removed — recovery bounces produce the same ATR sig as crashes
TREND_HANDOFF_SPREAD  = 0.015   # raised: EMA spread > +1.5% → hand off to TF (was +0.5%)
RECOVERY_DD_EXIT      = 0.12    # drawdown < 12% from 90d high → take profit
SPREAD_STOP           = -0.10   # spread worsening past −10% → cut
# Regime exit: only fire when BOTH regime is HIGH_VOL AND spread confirms deterioration
REGIME_EXIT_ATR_GATE  = 0.060   # ATR threshold for regime-based exit (6%)
REGIME_SPREAD_GATE    = -0.06   # spread must also be < −6% to confirm crash resuming

FLAT_THRESHOLD        = 0.05    # exposure below this = effectively flat


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
        # Crash resumed: regime HIGH_VOL + structural deterioration both required.
        # A volatile up-move can produce HIGH_VOL regime; require spread confirmation.
        if (
            ctx.regime == RegimeLabel.HIGH_VOL
            and atr_now > REGIME_EXIT_ATR_GATE
            and ema_spread < REGIME_SPREAD_GATE
        ):
            return StrategyIntent(
                action=Action.EXIT_LONG,
                confidence=0.88,
                desired_exposure_frac=0.0,
                horizon_hours=2,
                reason=(
                    f"Crash resuming: HIGH_VOL + atr={atr_now:.3f} > {REGIME_EXIT_ATR_GATE} "
                    f"+ spread={ema_spread:.4f} < {REGIME_SPREAD_GATE}"
                ),
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        # EMA spread worsening past structural stop
        if ema_spread < SPREAD_STOP:
            return StrategyIntent(
                action=Action.EXIT_LONG,
                confidence=0.82,
                desired_exposure_frac=0.0,
                horizon_hours=4,
                reason=f"Spread {ema_spread:.4f} < {SPREAD_STOP}: trend worsening — cut",
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        # Hand off: EMA crossover imminent, trend-following entering
        if ema_spread > TREND_HANDOFF_SPREAD:
            return StrategyIntent(
                action=Action.EXIT_LONG,
                confidence=0.80,
                desired_exposure_frac=0.0,
                horizon_hours=4,
                reason=(
                    f"Spread {ema_spread:.4f} > {TREND_HANDOFF_SPREAD}: "
                    "EMA crossover approaching — handing off to trend-following"
                ),
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        # Recovery target reached
        if drawdown_now < RECOVERY_DD_EXIT:
            return StrategyIntent(
                action=Action.EXIT_LONG,
                confidence=0.75,
                desired_exposure_frac=0.0,
                horizon_hours=4,
                reason=f"Drawdown {drawdown_now:.1%} < {RECOVERY_DD_EXIT:.0%} — recovery target hit",
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        # Hold: recovery in progress
        return StrategyIntent(
            action=Action.HOLD,
            confidence=0.65,
            desired_exposure_frac=ctx.current_exposure_frac,
            horizon_hours=168,
            reason=f"Recovery in progress: dd={drawdown_now:.1%} spread={ema_spread:.4f}",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    # ── ENTRY: post-capitulation setup ────────────────────────────────────────

    # Gate 1: not in active crash vol or established bull
    if ctx.regime == RegimeLabel.HIGH_VOL:
        return _flat("HIGH_VOL: crash still live — waiting", meta)

    if ctx.regime == RegimeLabel.TREND_UP:
        return _flat("TREND_UP: trend-following active — post-cap inactive", meta)

    # Gate 2: confirmed major drawdown (tightened from 25% → 28%)
    if drawdown_now < MIN_DRAWDOWN:
        return _flat(
            f"Drawdown {drawdown_now:.1%} < {MIN_DRAWDOWN:.0%}: insufficient — inactive",
            meta,
        )

    # Gate 3: genuine vol spike occurred
    if peak_atr < PEAK_ATR_MIN:
        return _flat(
            f"Peak ATR (7d) {peak_atr:.3f} < {PEAK_ATR_MIN:.3f}: no confirmed crash vol spike",
            meta,
        )

    # Gate 4: vol now compressing
    if atr_now > CURRENT_ATR_MAX:
        return _flat(
            f"ATR {atr_now:.3f} > {CURRENT_ATR_MAX:.3f}: vol not yet compressed — wait",
            meta,
        )

    if atr_now < CURRENT_ATR_MIN:
        return _flat(f"ATR {atr_now:.3f} < {CURRENT_ATR_MIN:.3f}: market inactive", meta)

    # Gate 5: EMA spread — meaningfully bearish (tightened from −0.2% → −1.0%)
    if ema_spread > EMA_SPREAD_MAX:
        return _flat(
            f"Spread {ema_spread:.4f} > {EMA_SPREAD_MAX:.4f}: trend-following may already be long",
            meta,
        )

    if ema_spread < EMA_SPREAD_MIN:
        return _flat(
            f"Spread {ema_spread:.4f} < {EMA_SPREAD_MIN:.2f}: too bearish to enter",
            meta,
        )

    # Gate 6: bearish momentum easing
    if not spread_improving:
        return _flat("Spread not improving over last 6 bars — bearish pressure not easing", meta)

    confidence = round(
        0.60
        + min((drawdown_now - MIN_DRAWDOWN) / 0.30, 0.25)
        + min((CURRENT_ATR_MAX - atr_now) / CURRENT_ATR_MAX, 0.15),
        4,
    )

    return StrategyIntent(
        action=Action.ENTER_LONG,
        confidence=confidence,
        desired_exposure_frac=ENTRY_EXPOSURE,
        horizon_hours=720,
        reason=(
            f"Post-cap v2 entry: dd={drawdown_now:.0%} "
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
