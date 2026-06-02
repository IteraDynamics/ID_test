"""Layer 2 — TrendFollowingV10 — SPY macro gate + 90-day BTC recovery override.

Identical to trend_following_v9 except the BTC SMA override uses a 90-calendar-day
lookback instead of 175.

Rationale for shorter BTC SMA
------------------------------
v9 (BTC SMA175) proved the dual-signal approach is correct — 2022 whipsaw
suppressed, 2023 recovery partially captured.  But 2023 was still below
baseline (+29.5% vs +37.8%) because the SMA175 unlock lagged the actual
BTC recovery by several weeks.

A 90-day SMA (~2160 hourly bars) crosses above current price faster during
genuine recoveries while still filtering the 2022 false rallies:

  2022 July bear-market rally (+23%, ~45 days):
      90-day SMA still incorporates prior 90 days of declining prices.
      BTC at $24k, 90-day SMA still elevated from prior cycle → BLOCK ✓

  2023 Q1 genuine recovery (BTC $16k → $30k):
      90-day SMA recalibrates faster → BTC crosses above it earlier in
      January/February → gate opens sooner → more of the rally captured ✓

Gate logic (unchanged from v9):
  Block ENTER_LONG when: SPY below SMA175 AND BTC below own 90-day SMA
  Allow ENTER_LONG when: SPY below SMA175 BUT BTC above own 90-day SMA
  No gate when:          SPY above SMA175 (macro bull — normal operation)

Backward compatible: if df["spy_above_sma175"] is absent, gate is skipped.
"""

from __future__ import annotations

import pandas as pd

from research.strategies.contracts import Action, StrategyContext, StrategyIntent
from research.strategies import trend_following_v8

STRATEGY_ID   = "trend_following_v10"
_ENTRY_CAP    = 0.60
_ADDON_CAP    = 0.80
_SPY_COL      = "spy_above_sma175"
_BTC_SMA_DAYS = 90   # calendar days — faster unlock vs v9's 175


def _btc_above_sma(df: pd.DataFrame) -> bool | None:
    """True if BTC close is above its 90-calendar-day SMA.

    Auto-detects bar size (1H, 4H, etc.) so the same lookback duration is
    used regardless of timeframe.  Returns None when insufficient warmup.
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
    # already reclaimed its own 90-day SMA (leading-recovery override).
    if intent.action == Action.ENTER_LONG and spy_state is False:
        btc_bullish = _btc_above_sma(df)
        if btc_bullish is not True:
            return StrategyIntent(
                action=Action.FLAT,
                confidence=0.60,
                desired_exposure_frac=0.0,
                horizon_hours=0,
                reason=(
                    "SPY below SMA175 (macro bear) and BTC below own SMA90 "
                    "— no recovery confirmation, blocking new long entry"
                ),
                meta={
                    **intent.meta,
                    "spy_above_sma175": False,
                    "btc_above_sma90":  btc_bullish,
                    "btc_override":     False,
                },
                strategy_id=STRATEGY_ID,
            )
        # BTC has reclaimed its 90-day SMA while SPY is still bearish.
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
                "btc_above_sma90":  True,
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
