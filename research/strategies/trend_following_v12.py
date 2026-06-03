"""trend_following_v12 — Medium-term momentum filter + ATR vol scaling.

Extends v11 (parabolic extension cap + SPY cross-asset gate) with two
position-sizing overlays applied only to new ENTER_LONG and add-on entries:

1. 90-day momentum filter (timeframe-agnostic)
   Computes the 90-calendar-day rolling return.  In sideways / grinding
   markets the return is near zero or negative, meaning a short-term TREND_UP
   signal is not confirmed on the medium-term frame.  Entry exposure is scaled
   down — the position is taken but smaller — rather than blocked outright.

   Scale schedule (applied to v11 desired_exposure_frac):
     momentum  > 0%:          1.00×  — medium-term uptrend confirmed
     momentum  0% → -15%:     0.65×  — sideways / grinding
     momentum  < -15%:        0.40×  — medium-term downtrend

2. ATR volatility targeting (timeframe-agnostic)
   Scales position size to approximate a 15 % annualised volatility
   contribution.  Reduces exposure in choppy high-vol conditions; preserves
   full exposure in controlled low-vol trends.

     target_daily_vol ≈ 0.0082  (= 15 % / √252)
     vol_scale = clamp(target_daily_vol / atr_pct, 0.50, 1.00)

   Both factors are applied multiplicatively after the parabolic cap:
     final_exposure = v11_exposure × momentum_scale × vol_scale

Why this helps 2025 but preserves 2023
---------------------------------------
2023: BTC +100 % YTD — 90-day momentum strongly positive AND ATR controlled →
      momentum_scale = 1.0, vol_scale ≈ 0.8 – 1.0 → near-full positions kept.

2025: BTC sideways / grinding — 90-day momentum near zero or negative AND
      moderate ATR → momentum_scale = 0.40 – 0.65, vol_scale ≈ 0.5 – 0.8 →
      20 – 50 % of v11 size → fewer whipsaws, shallower drawdowns, higher
      Sharpe contribution from the trend sleeve.

HOLDs and exits pass through unchanged; position reduction in a deteriorating
market is handled by the existing regime-based exit logic in v8 / v9.
"""

from __future__ import annotations

import pandas as pd

from research.strategies.contracts import Action, StrategyContext, StrategyIntent
from research.strategies import trend_following_v11

STRATEGY_ID = "trend_following_v12"

# ── 90-day momentum parameters ─────────────────────────────────────────────────
_MOM_DAYS           = 90      # calendar days lookback
_MOM_SIDEWAYS_THR   = 0.00    # ≤ this → sideways scale
_MOM_BEAR_THR       = -0.15   # ≤ this → bear scale
_MOM_FULL_SCALE     = 1.00
_MOM_SIDEWAYS_SCALE = 0.65
_MOM_BEAR_SCALE     = 0.40

# ── ATR vol-targeting parameters ───────────────────────────────────────────────
_ATR_PERIOD         = 14       # bars (Wilder EWM)
_TARGET_DAILY_VOL   = 0.0082   # ≈ 15 % / √252 annualised
_VOL_SCALE_FLOOR    = 0.50     # never cut position below 50 % of v11 level
_VOL_SCALE_CAP      = 1.00     # never amplify above v11 level


# ── Helpers ────────────────────────────────────────────────────────────────────

def _bar_hours(df: pd.DataFrame) -> float:
    if len(df.index) < 2:
        return 1.0
    return max(1.0, (df.index[-1] - df.index[-2]).total_seconds() / 3600)


def _momentum_90d(df: pd.DataFrame) -> float | None:
    """90-calendar-day rolling return; None when warmup is insufficient."""
    close = df["close"]
    bh    = _bar_hours(df)
    n     = round(_MOM_DAYS * 24 / bh)
    if len(close) < n + 1:
        return None
    past = float(close.iloc[-n - 1])
    if past <= 0:
        return None
    return float(close.iloc[-1]) / past - 1.0


def _atr_pct(df: pd.DataFrame) -> float | None:
    """14-bar Wilder ATR as a fraction of close; None when warmup insufficient."""
    close = df["close"]
    high  = df["high"]
    low   = df["low"]
    if len(close) < _ATR_PERIOD + 5:
        return None
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    atr = float(tr.ewm(span=_ATR_PERIOD, adjust=False).mean().iloc[-1])
    c   = float(close.iloc[-1])
    if c <= 0:
        return None
    return atr / c


# ── Strategy entry point ───────────────────────────────────────────────────────

def generate_intent(
    df: pd.DataFrame,
    ctx: StrategyContext,
    closed_only: bool = True,
) -> StrategyIntent:
    intent = trend_following_v11.generate_intent(df, ctx, closed_only)

    # Only size-scale new long entries (initial or add-on).
    # HOLDs, EXITs, FLATs, and ENTER_SHORT pass through unchanged.
    if intent.action != Action.ENTER_LONG:
        return StrategyIntent(
            action=intent.action,
            confidence=intent.confidence,
            desired_exposure_frac=intent.desired_exposure_frac,
            horizon_hours=intent.horizon_hours,
            reason=intent.reason,
            meta=intent.meta,
            strategy_id=STRATEGY_ID,
        )

    # ── 1. 90-day momentum scale ───────────────────────────────────────────────
    mom = _momentum_90d(df)
    if mom is None:
        # Insufficient warmup — pass through at full v11 exposure
        momentum_scale = _MOM_FULL_SCALE
        mom_tier = "warmup"
    elif mom > _MOM_SIDEWAYS_THR:
        momentum_scale = _MOM_FULL_SCALE
        mom_tier = "uptrend"
    elif mom > _MOM_BEAR_THR:
        momentum_scale = _MOM_SIDEWAYS_SCALE
        mom_tier = "sideways"
    else:
        momentum_scale = _MOM_BEAR_SCALE
        mom_tier = "bear"

    # ── 2. ATR vol-targeting scale ─────────────────────────────────────────────
    atr_p = _atr_pct(df)
    if atr_p is None or atr_p <= 0:
        vol_scale = _VOL_SCALE_CAP
    else:
        raw_scale = _TARGET_DAILY_VOL / atr_p
        vol_scale = max(_VOL_SCALE_FLOOR, min(_VOL_SCALE_CAP, raw_scale))

    # ── Combined scale → final exposure ───────────────────────────────────────
    combined   = momentum_scale * vol_scale
    v11_exp    = intent.desired_exposure_frac
    new_exp    = v11_exp * combined

    return StrategyIntent(
        action=intent.action,
        confidence=intent.confidence,
        desired_exposure_frac=new_exp,
        horizon_hours=intent.horizon_hours,
        reason=intent.reason,
        meta={
            **intent.meta,
            "v12_momentum_90d":    round(mom, 4) if mom is not None else None,
            "v12_mom_tier":        mom_tier,
            "v12_momentum_scale":  round(momentum_scale, 3),
            "v12_atr_pct":         round(atr_p, 5) if atr_p is not None else None,
            "v12_vol_scale":       round(vol_scale, 3),
            "v12_combined_scale":  round(combined, 3),
            "v12_pre_scale_exp":   round(v11_exp, 3),
        },
        strategy_id=STRATEGY_ID,
    )
