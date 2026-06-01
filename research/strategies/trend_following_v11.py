"""Layer 2 — TrendFollowingV11 — Parabolic extension exposure trimmer.

Extends trend_following_v9 (SPY macro gate + BTC recovery override) with a
third layer: scale down entry exposure when BTC is in a parabolic extension
above its 365-day SMA.

Rationale
---------
The fund's worst drawdown (-23.7% stitched OOS) traces to the Nov 2021 ATH.
The peak NAV was reached when the fund was fully exposed (~60%) into a
parabolic move that subsequently reversed -75%.  Reducing exposure as BTC
extends further from its long-term mean limits the peak NAV and therefore
the peak-to-trough drawdown — improving Calmar without sacrificing the bulk
of upside in normal trend conditions.

BTC extension is measured against the 365-calendar-day SMA, which captures
one full year of price history and provides a stable "structural fair value"
reference.  Parabolic moves — defined as price far above any reasonable
trailing average — carry higher reversal risk regardless of trend regime.

Three-tier cap schedule (entry / add-on):
  Normal      (<60% above SMA365):  60% / 80%   ← same as ecap60_add80
  Extended    (60–100% above):      40% / 60%   ← soft trim
  Parabolic   (>100% above):        25% / 40%   ← hard trim

Historical calibration (not optimised — round thresholds chosen first):
  Apr 2021 ATH  $60k, SMA365 ~$22k → +173% → hard cap  ✓
  Nov 2021 ATH  $69k, SMA365 ~$42k →  +64% → soft cap  ✓
  Aug 2022 rally $25k, SMA365 ~$40k → -37% → no cap (v9 SPY/BTC gate handles) ✓
  Dec 2023 peak  $42k, SMA365 ~$27k →  +56% → no cap  ✓  (recovery intact)
  Mar 2024 ETF   $73k, SMA365 ~$32k → +128% → hard cap  (prudent at that extension)

The parabolic cap only affects new ENTER_LONG intents.  Existing positions
are not force-reduced — normal exit conditions still apply.

Backward compatible: if df["spy_above_sma175"] is absent, the v9 gate is
skipped; the parabolic cap still applies.
"""

from __future__ import annotations

import pandas as pd

from research.strategies.contracts import Action, StrategyContext, StrategyIntent
from research.strategies import trend_following_v9

STRATEGY_ID = "trend_following_v11"

# ── Parabolic extension thresholds ─────────────────────────────────────────────
_PARA_SMA_DAYS         = 365   # calendar days

_PARA_SOFT_THRESHOLD   = 0.60  # 60% above SMA365 → soft trim
_PARA_HARD_THRESHOLD   = 1.00  # 100% above SMA365 → hard trim

_PARA_SOFT_ENTRY_CAP   = 0.40
_PARA_SOFT_ADDON_CAP   = 0.60
_PARA_HARD_ENTRY_CAP   = 0.25
_PARA_HARD_ADDON_CAP   = 0.40


def _btc_extension(df: pd.DataFrame) -> float | None:
    """Return (close / SMA365 - 1).  Negative means price is below SMA.

    Auto-detects bar size so the 365-day window is timeframe-agnostic.
    Returns None when warmup history is insufficient.
    """
    close = df["close"]
    if len(close) < 2:
        return None
    bar_hours = max(1.0, (df.index[-1] - df.index[-2]).total_seconds() / 3600)
    sma_bars  = round(_PARA_SMA_DAYS * 24 / bar_hours)
    if len(close) < sma_bars:
        return None
    sma_val = float(close.rolling(sma_bars).mean().iloc[-1])
    if pd.isna(sma_val) or sma_val <= 0:
        return None
    return (float(close.iloc[-1]) - sma_val) / sma_val


def generate_intent(
    df: pd.DataFrame,
    ctx: StrategyContext,
    closed_only: bool = True,
) -> StrategyIntent:
    intent = trend_following_v9.generate_intent(df, ctx, closed_only)

    # Only new long entries are subject to the parabolic cap.
    # HOLDs, EXITs, FLATs, and existing positions pass through unchanged.
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

    extension = _btc_extension(df)
    is_addon  = intent.meta.get("add_on", False)

    # Determine which parabolic tier applies
    if extension is not None and extension > _PARA_HARD_THRESHOLD:
        cap    = _PARA_HARD_ADDON_CAP if is_addon else _PARA_HARD_ENTRY_CAP
        tier   = "parabolic"
    elif extension is not None and extension > _PARA_SOFT_THRESHOLD:
        cap    = _PARA_SOFT_ADDON_CAP if is_addon else _PARA_SOFT_ENTRY_CAP
        tier   = "extended"
    else:
        # Below parabolic threshold — pass through v9's intent unchanged
        return StrategyIntent(
            action=intent.action,
            confidence=intent.confidence,
            desired_exposure_frac=intent.desired_exposure_frac,
            horizon_hours=intent.horizon_hours,
            reason=intent.reason,
            meta={**intent.meta, "btc_extension": round(extension, 3) if extension is not None else None},
            strategy_id=STRATEGY_ID,
        )

    # Apply parabolic cap if it's more restrictive than v9's intent
    new_exposure = min(intent.desired_exposure_frac, cap)
    return StrategyIntent(
        action=intent.action,
        confidence=intent.confidence,
        desired_exposure_frac=new_exposure,
        horizon_hours=intent.horizon_hours,
        reason=intent.reason,
        meta={
            **intent.meta,
            "parabolic_tier":      tier,
            "parabolic_cap":       cap,
            "btc_extension":       round(extension, 3),
            "pre_cap_exposure":    round(intent.desired_exposure_frac, 3),
        },
        strategy_id=STRATEGY_ID,
    )
