"""Layer 2 — TrendFollowingV9 — SPY cross-asset macro gate + BTC recovery override.

Extends trend_following_v8_ecap60_add80 with a two-signal cross-asset gate:

  1. SPY below SMA175  → macro bear context is active.
  2. BTC below own SMA175 (175 calendar days, timeframe-agnostic) → BTC has not
     yet reclaimed its structural level.

  Block ENTER_LONG only when BOTH conditions hold.
  Allow ENTER_LONG when SPY is bearish BUT BTC has already reclaimed its SMA175
  — this is the crypto-leads-equity recovery pattern (e.g. Q1 2023: BTC +90%
  while SPY was still below its SMA175 until April).

Rationale
---------
v9 original (SPY-only gate) fixed 2022 whipsaw but cost 2023 performance:
SPY's 175-day SMA is a slow indicator (~8.5-month average).  SPY didn't
reclaim SMA175 until April 2023, but BTC had already run from $16k to $30k
in January–March.  Blocking longs until SPY confirmed missed the entire
first leg of the 2023 bull.

The BTC SMA175 override detects this exactly:
  2022 July rally (+23%): BTC SMA175 ≈ $35-40k, BTC at $24k → below → BLOCK ✓
  2023 Q1 rally (+90%):   BTC crossed its own SMA175 in late-Jan/Feb → ALLOW ✓

The gate is still one-directional:
  Blocks:  new ENTER_LONG when SPY bear AND BTC structural downtrend
  Allows:  HOLD of existing positions, EXIT, FLAT always
  Overrides: ENTER_LONG when SPY bear BUT BTC > own SMA175

Backward compatible: if df["spy_above_sma175"] is absent, gate is skipped.
"""

from __future__ import annotations

import pandas as pd

from research.strategies.contracts import Action, StrategyContext, StrategyIntent
from research.strategies import trend_following_v8

STRATEGY_ID   = "trend_following_v9"
_ENTRY_CAP    = 0.60
_ADDON_CAP    = 0.80
_SPY_COL      = "spy_above_sma175"
_BTC_SMA_DAYS = 175   # calendar days — mirrors SPY SMA175 concept


def _btc_above_sma(df: pd.DataFrame) -> bool | None:
    """True if BTC close is above its 175-calendar-day SMA.

    Auto-detects bar size (1H, 4H, etc.) so the same lookback duration is
    used regardless of timeframe.  Returns None when there is insufficient
    warmup history.
    """
    close = df["close"]
    if len(close) < 2:
        return None
    bar_hours = max(1.0, (df.index[-1] - df.index[-2]).total_seconds() / 3600)
    sma_bars  = round(_BTC_SMA_DAYS * 24 / bar_hours)
    if len(close) < sma_bars:
        return None
    sma_val = close.rolling(sma_bars).mean().iloc[-1]
    if pd.isna(sma_val):
        return None
    return float(close.iloc[-1]) > float(sma_val)


def generate_intent(
    df: pd.DataFrame,
    ctx: StrategyContext,
    closed_only: bool = True,
) -> StrategyIntent:
    intent = trend_following_v8.generate_intent(df, ctx, closed_only)

    # Read SPY cross-asset state
    spy_state: bool | None = None
    if _SPY_COL in df.columns:
        val = df[_SPY_COL].iloc[-1]
        if pd.notna(val):
            spy_state = bool(val)

    # Gate: when SPY is in a macro bear, block new longs UNLESS BTC has
    # already reclaimed its own structural level (leading-recovery override).
    if intent.action == Action.ENTER_LONG and spy_state is False:
        btc_bullish = _btc_above_sma(df)
        if btc_bullish is not True:
            # Both SPY and BTC in structural downtrend — block entry.
            return StrategyIntent(
                action=Action.FLAT,
                confidence=0.60,
                desired_exposure_frac=0.0,
                horizon_hours=0,
                reason=(
                    "SPY below SMA175 (macro bear) and BTC below own SMA175 "
                    "— no recovery confirmation, blocking new long entry"
                ),
                meta={
                    **intent.meta,
                    "spy_above_sma175": False,
                    "btc_above_sma175": btc_bullish,
                    "btc_override":     False,
                },
                strategy_id=STRATEGY_ID,
            )
        # BTC has reclaimed its structural level while SPY is still bearish.
        # Crypto is leading the recovery — allow the entry.
        intent = StrategyIntent(
            action=intent.action,
            confidence=intent.confidence,
            desired_exposure_frac=intent.desired_exposure_frac,
            horizon_hours=intent.horizon_hours,
            reason=intent.reason,
            meta={
                **intent.meta,
                "spy_above_sma175": False,
                "btc_above_sma175": True,
                "btc_override":     True,
            },
            strategy_id=STRATEGY_ID,
        )

    # Apply exposure caps (same as ecap60_add80)
    is_addon         = intent.action == Action.ENTER_LONG and intent.meta.get("add_on", False)
    is_initial_entry = intent.action == Action.ENTER_LONG and not is_addon

    if is_initial_entry and intent.desired_exposure_frac > _ENTRY_CAP:
        return StrategyIntent(
            action=intent.action,
            confidence=intent.confidence,
            desired_exposure_frac=_ENTRY_CAP,
            horizon_hours=intent.horizon_hours,
            reason=intent.reason,
            meta={**intent.meta, "entry_cap": _ENTRY_CAP, "spy_above_sma175": spy_state},
            strategy_id=STRATEGY_ID,
        )

    if is_addon and intent.desired_exposure_frac > _ADDON_CAP:
        return StrategyIntent(
            action=intent.action,
            confidence=intent.confidence,
            desired_exposure_frac=_ADDON_CAP,
            horizon_hours=intent.horizon_hours,
            reason=intent.reason,
            meta={**intent.meta, "addon_cap": _ADDON_CAP, "spy_above_sma175": spy_state},
            strategy_id=STRATEGY_ID,
        )

    return StrategyIntent(
        action=intent.action,
        confidence=intent.confidence,
        desired_exposure_frac=intent.desired_exposure_frac,
        horizon_hours=intent.horizon_hours,
        reason=intent.reason,
        meta={**intent.meta, "spy_above_sma175": spy_state},
        strategy_id=STRATEGY_ID,
    )
