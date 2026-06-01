"""Layer 2 — TrendFollowingV9 — SPY cross-asset macro gate.

Extends trend_following_v8_ecap60_add80 with one additional gate:

  When SPY is below its 175-day SMA (equity bear market), all new ENTER_LONG
  intents are suppressed to FLAT.

Rationale
---------
In a macro bear market (SPY below SMA175), crypto bear-market rallies
routinely produce false TREND_UP regime signals (2022: July +23%,
August +15%).  The trend strategy enters longs that subsequently reverse,
creating whipsaw losses.  When equity confirms a macro bear, the
probability a crypto TREND_UP signal represents a genuine new uptrend
is low — blocking new longs avoids this category of false entries.

The gate is one-directional:
  Blocks:  new ENTER_LONG (initial + add-on)
  Allows:  HOLD of existing positions, EXIT, FLAT

Existing longs are not force-closed when SPY crosses below SMA175
mid-position — normal exit conditions still apply.  New longs resume
once SPY reclaims its SMA175.

Backward compatible: if df["spy_above_sma175"] is absent (BTC-only run),
the gate is skipped and behaviour is identical to ecap60_add80.
"""

from __future__ import annotations

import pandas as pd

from research.strategies.contracts import Action, StrategyContext, StrategyIntent
from research.strategies import trend_following_v8

STRATEGY_ID = "trend_following_v9"
_ENTRY_CAP  = 0.60
_ADDON_CAP  = 0.80
_SPY_COL    = "spy_above_sma175"


def generate_intent(
    df: pd.DataFrame,
    ctx: StrategyContext,
    closed_only: bool = True,
) -> StrategyIntent:
    intent = trend_following_v8.generate_intent(df, ctx, closed_only)

    # Read SPY cross-asset state for meta logging
    spy_state: bool | None = None
    if _SPY_COL in df.columns:
        val = df[_SPY_COL].iloc[-1]
        if pd.notna(val):
            spy_state = bool(val)

    # Gate: block new long entries when SPY is in a macro bear
    if intent.action == Action.ENTER_LONG and spy_state is False:
        return StrategyIntent(
            action=Action.FLAT,
            confidence=0.60,
            desired_exposure_frac=0.0,
            horizon_hours=0,
            reason="SPY below SMA175 — macro bear, blocking new long entry",
            meta={**intent.meta, "spy_above_sma175": False},
            strategy_id=STRATEGY_ID,
        )

    # Apply exposure caps (same as ecap60_add80)
    is_addon          = intent.action == Action.ENTER_LONG and intent.meta.get("add_on", False)
    is_initial_entry  = intent.action == Action.ENTER_LONG and not is_addon

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
