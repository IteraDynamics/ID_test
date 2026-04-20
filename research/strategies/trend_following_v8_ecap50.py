"""Layer 2 — TrendFollowingV8 Entry-Cap 50% (asymmetric exposure control).

Applies the same asymmetric-cap design as trend_following_v8_ecap75 but with
a more conservative 50% NAV ceiling on initial entries.

Signal logic: identical to trend_following_v8.
Only change: ENTER_LONG initial entries capped at 0.50.
Add-ons, HOLD, EXIT_LONG, and FLAT pass through unchanged.
"""

from __future__ import annotations

import pandas as pd

from research.strategies.contracts import Action, StrategyContext, StrategyIntent
from research.strategies import trend_following_v8

STRATEGY_ID = "trend_following_v8_ecap50"
_ENTRY_CAP = 0.50


def generate_intent(
    df: pd.DataFrame,
    ctx: StrategyContext,
    closed_only: bool = True,
) -> StrategyIntent:
    intent = trend_following_v8.generate_intent(df, ctx, closed_only)

    is_initial_entry = (
        intent.action == Action.ENTER_LONG
        and not intent.meta.get("add_on", False)
        and intent.desired_exposure_frac > _ENTRY_CAP
    )

    if is_initial_entry:
        return StrategyIntent(
            action=intent.action,
            confidence=intent.confidence,
            desired_exposure_frac=_ENTRY_CAP,
            horizon_hours=intent.horizon_hours,
            reason=intent.reason,
            meta={**intent.meta, "entry_cap": _ENTRY_CAP},
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
