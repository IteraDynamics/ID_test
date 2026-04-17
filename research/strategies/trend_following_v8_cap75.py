"""Layer 2 — TrendFollowingV8 Cap75 (exposure throttle experiment).

Exposure-throttling variant of trend_following_v8.

Hypothesis: the signal is already good enough.  The remaining slippage and
drawdown problems come from moving too much capital per decision.  This
variant tests a hard 75% NAV cap on desired exposure to quantify:
  - How much slippage is reduced by pure capital throttling
  - How much CAGR is sacrificed at this cap level
  - Whether Sharpe / Calmar improve enough to justify lower raw return

Signal logic: identical to trend_following_v8 (no changes).
Only change: desired_exposure_frac is capped at 0.75 on every intent.
"""

from __future__ import annotations

import pandas as pd

from research.strategies.contracts import Action, StrategyContext, StrategyIntent
from research.strategies import trend_following_v8

STRATEGY_ID = "trend_following_v8_cap75"
_CAP = 0.75


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
