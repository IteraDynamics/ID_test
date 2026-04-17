"""Layer 2 — TrendFollowingV8 Entry-Cap 75% + Add-on Cap 90%.

Builds on trend_following_v8_ecap75.

v8_ecap75 result (the parent)
------------------------------
Entry-only cap at 75% fully restored convexity (Exit/Entry = 1.426x,
matching uncapped v8's 1.423x) while saving $90k slippage and dropping CAGR
by only 0.64pp.  However DD remained at -54.44% — above the -50% target.

Remaining DD source: positions entered at 75% float above the entry cap via
price appreciation, then an add-on pushes them to 100%.  When a sudden crash
hits at 100% exposure, the full position absorbs the loss.

v8_ecap75_add90 design
-----------------------
Two-level asymmetric cap:
  - Initial entries:  capped at 0.75  (same as ecap75)
  - Add-ons:          capped at 0.90  (new — was uncapped in ecap75)
  - HOLD / EXIT / FLAT: pass through unchanged

Positions now travel: 75% (entry) → natural float → 90% max (add-on) → exit.
Peak intentional exposure is 90% instead of 100%.  Natural price appreciation
can push above 90% between bars, but no deliberate trade adds beyond it.

Expected effects vs ecap75:
  - Max DD:    lower (10pp less peak deliberate exposure)
  - Slippage:  lower (add-on notional capped at 90% vs 100% of then-NAV)
  - CAGR:      modest additional dip (slightly less exposure on strong runs)
  - Convexity: preserved (add-ons still fire and grow winners; just capped)
"""

from __future__ import annotations

import pandas as pd

from research.strategies.contracts import Action, StrategyContext, StrategyIntent
from research.strategies import trend_following_v8

STRATEGY_ID = "trend_following_v8_ecap75_add90"
_ENTRY_CAP = 0.75
_ADDON_CAP = 0.90


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
