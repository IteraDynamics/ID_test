"""Layer 2 — TrendFollowingV8 Entry-Cap 75% (asymmetric exposure control).

Motivation
----------
The hard-cap variants (cap75/cap60/cap50) confirmed that pure exposure
throttling cuts slippage and drawdown, but revealed an unintended structural
cost: the hard cap applies to HOLD intents too, so every time BTC appreciates
and the position grows above the ceiling the wrapper triggers a rebalancing
SELL.  This kills the trend-following convexity:

  v8 uncapped   exit/entry = 1.423x   (winners compound and grow)
  v8_cap75      exit/entry = 1.011x   (constantly trimmed back to 75%)

The 1.423x ratio is *the* edge in trend-following — letting a 75% position
ride to 90-100% as BTC trends.  Removing it erases a large part of CAGR
that the lower entry slippage cannot compensate.

v8_ecap75 design: asymmetric cap
----------------------------------
Only INITIAL entries are capped at 75% NAV.  All other intents pass through
unchanged:

  ENTER_LONG (initial, meta has no "add_on" key)  → cap at 0.75
  ENTER_LONG (add-on, meta["add_on"] == True)     → pass through uncapped
  HOLD                                             → pass through uncapped
  EXIT_LONG / FLAT                                 → pass through uncapped

Result:
  - Fresh positions start at 75% NAV (lower entry slippage, lower day-1 DD)
  - Once invested, the position floats freely above 75% as BTC trends up
  - Add-ons still fire when the trend is very strong (spread > 2.0%),
    growing a naturally risen position toward 100%
  - Exit behaviour is completely unchanged

Expected behaviour relative to v8 uncapped:
  - Entry slippage: lower (75% vs 90% notional at entry)
  - Convexity: largely preserved (positions still grow to 90-100% on winners)
  - Max DD: lower (starting at 75% means a sudden crash at entry hurts less)
  - Exit/Entry ratio: should recover toward the 1.3-1.4x range

Signal logic: identical to trend_following_v8.
Only change: ENTER_LONG initial entries capped at 0.75.
"""

from __future__ import annotations

import pandas as pd

from research.strategies.contracts import Action, StrategyContext, StrategyIntent
from research.strategies import trend_following_v8

STRATEGY_ID = "trend_following_v8_ecap75"
_ENTRY_CAP = 0.75


def generate_intent(
    df: pd.DataFrame,
    ctx: StrategyContext,
    closed_only: bool = True,
) -> StrategyIntent:
    intent = trend_following_v8.generate_intent(df, ctx, closed_only)

    # Cap only fresh initial entries — not add-ons, not holds, not exits.
    # Add-ons grow an already-established position; capping them would sell
    # into strength and destroy the trend-following convexity.
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
