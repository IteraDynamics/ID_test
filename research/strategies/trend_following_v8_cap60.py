"""Layer 2 — TrendFollowingV8 Cap60 (exposure throttle experiment).

Exposure-throttling variant of trend_following_v8.

See trend_following_v8_cap75 for experiment design rationale.
This variant tests a 60% NAV cap.

Signal logic: identical to trend_following_v8 (no changes).
Only change: desired_exposure_frac is capped at 0.60 on every intent.
"""

from __future__ import annotations

import pandas as pd

from research.strategies.contracts import Action, StrategyContext, StrategyIntent
from research.strategies import trend_following_v8

STRATEGY_ID = "trend_following_v8_cap60"
_CAP = 0.60


def generate_intent(
    df: pd.DataFrame,
    ctx: StrategyContext,
    closed_only: bool = True,
) -> StrategyIntent:
    intent = trend_following_v8.generate_intent(df, ctx, closed_only)
    capped = min(intent.desired_exposure_frac, _CAP)
    meta = {**intent.meta, "exposure_cap": _CAP} if capped < intent.desired_exposure_frac else intent.meta
    return StrategyIntent(
        action=intent.action,
        confidence=intent.confidence,
        desired_exposure_frac=capped,
        horizon_hours=intent.horizon_hours,
        reason=intent.reason,
        meta=meta,
        strategy_id=STRATEGY_ID,
    )
