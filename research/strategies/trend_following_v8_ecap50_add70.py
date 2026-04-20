"""Layer 2 — TrendFollowingV8 Entry-Cap 50% + Add-on Cap 70%.

Builds on trend_following_v8_ecap50.

Two-level asymmetric cap:
  - Initial entries:  capped at 0.50
  - Add-ons:          capped at 0.70
  - HOLD / EXIT / FLAT: pass through unchanged

Positions travel: 50% (entry) → natural float → 70% max (add-on) → exit.
Peak intentional exposure is 70% instead of 100%.
"""

from __future__ import annotations

import pandas as pd

from research.strategies.contracts import Action, StrategyContext, StrategyIntent
from research.strategies import trend_following_v8

STRATEGY_ID = "trend_following_v8_ecap50_add70"
_ENTRY_CAP = 0.50
_ADDON_CAP = 0.70


def generate_intent(
    df: pd.DataFrame,
    ctx: StrategyContext,
    closed_only: bool = True,
) -> StrategyIntent:
    intent = trend_following_v8.generate_intent(df, ctx, closed_only)

    is_addon = intent.action == Action.ENTER_LONG and intent.meta.get("add_on", False)
    is_initial_entry = intent.action == Action.ENTER_LONG and not is_addon

    if is_initial_entry and intent.desired_exposure_frac > _ENTRY_CAP:
        return StrategyIntent(
            action=intent.action,
            confidence=intent.confidence,
            desired_exposure_frac=_ENTRY_CAP,
            horizon_hours=intent.horizon_hours,
            reason=intent.reason,
            meta={**intent.meta, "entry_cap": _ENTRY_CAP},
            strategy_id=STRATEGY_ID,
        )

    if is_addon and intent.desired_exposure_frac > _ADDON_CAP:
        return StrategyIntent(
            action=intent.action,
            confidence=intent.confidence,
            desired_exposure_frac=_ADDON_CAP,
            horizon_hours=intent.horizon_hours,
            reason=intent.reason,
            meta={**intent.meta, "addon_cap": _ADDON_CAP},
            strategy_id=STRATEGY_ID,
        )

    return StrategyIntent(
        action=intent.action,
        confidence=intent.confidence,
        desired_exposure_frac=intent.desired_exposure_frac,
        horizon_hours=intent.horizon_hours,
        reason=intent.reason,
        meta=intent.meta,
        strategy_id=STRATEGY_ID,
    )
