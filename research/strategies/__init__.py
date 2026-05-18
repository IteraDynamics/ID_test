"""Layer 2 — Strategy Modules.

Each strategy exposes:
    generate_intent(df, ctx, closed_only=True) -> StrategyIntent

Imports:
    from research.strategies import Action, StrategyContext, StrategyIntent
    from research.strategies import trend_following, volatility_breakout, mean_reversion
    from research.strategies import trend_following_v2, trend_following_v3, trend_following_v4
"""

from research.strategies.contracts import Action, StrategyContext, StrategyIntent
from research.strategies import trend_following
from research.strategies import trend_following_v2
from research.strategies import trend_following_v3
from research.strategies import trend_following_v4
from research.strategies import trend_following_v5
from research.strategies import trend_following_v6
from research.strategies import trend_following_v7
from research.strategies import trend_following_v8
from research.strategies import trend_following_v8_1
from research.strategies import trend_following_v8_cap75
from research.strategies import trend_following_v8_cap60
from research.strategies import trend_following_v8_cap50
from research.strategies import trend_following_v8_ecap75
from research.strategies import trend_following_v8_ecap75_add90
from research.strategies import trend_following_v8_ecap60
from research.strategies import trend_following_v8_ecap60_add80
from research.strategies import trend_following_v8_ecap50
from research.strategies import trend_following_v8_ecap50_add70
from research.strategies import trend_following_short
from research.strategies import trend_following_short_v2
from research.strategies import crash_short_v1
from research.strategies import crash_short_v2
from research.strategies import volatility_breakout
from research.strategies import mean_reversion
from research.strategies import post_capitulation_long_v1
from research.strategies import post_capitulation_long_v2
from research.strategies import equity_spy_qqq_sma_band_v1
from research.strategies import equity_qqq_trend_v1

REGISTRY: dict[str, object] = {
    "trend_following": trend_following,
    "trend_following_v2": trend_following_v2,
    "trend_following_v3": trend_following_v3,
    "trend_following_v4": trend_following_v4,
    "trend_following_v5": trend_following_v5,
    "trend_following_v6": trend_following_v6,
    "trend_following_v7": trend_following_v7,
    "trend_following_v8": trend_following_v8,
    "trend_following_v8_1": trend_following_v8_1,
    "trend_following_v8_cap75": trend_following_v8_cap75,
    "trend_following_v8_cap60": trend_following_v8_cap60,
    "trend_following_v8_cap50": trend_following_v8_cap50,
    "trend_following_v8_ecap75": trend_following_v8_ecap75,
    "trend_following_v8_ecap75_add90": trend_following_v8_ecap75_add90,
    "trend_following_v8_ecap60": trend_following_v8_ecap60,
    "trend_following_v8_ecap60_add80": trend_following_v8_ecap60_add80,
    "trend_following_v8_ecap50": trend_following_v8_ecap50,
    "trend_following_v8_ecap50_add70": trend_following_v8_ecap50_add70,
    "trend_following_short": trend_following_short,
    "trend_following_short_v2": trend_following_short_v2,
    "crash_short_v1": crash_short_v1,
    "crash_short_v2": crash_short_v2,
    "volatility_breakout": volatility_breakout,
    "mean_reversion": mean_reversion,
    "post_capitulation_long_v1": post_capitulation_long_v1,
    "post_capitulation_long_v2": post_capitulation_long_v2,
    "equity_spy_qqq_sma_band_v1": equity_spy_qqq_sma_band_v1,
    "equity_qqq_trend_v1": equity_qqq_trend_v1,
}

__all__ = [
    "Action",
    "StrategyContext",
    "StrategyIntent",
    "trend_following",
    "trend_following_v2",
    "trend_following_v3",
    "trend_following_v4",
    "trend_following_v5",
    "trend_following_v6",
    "trend_following_v7",
    "trend_following_v8",
    "trend_following_v8_1",
    "trend_following_v8_cap75",
    "trend_following_v8_cap60",
    "trend_following_v8_cap50",
    "trend_following_v8_ecap75",
    "trend_following_v8_ecap75_add90",
    "trend_following_v8_ecap60",
    "trend_following_v8_ecap60_add80",
    "trend_following_v8_ecap50",
    "trend_following_v8_ecap50_add70",
    "trend_following_short",
    "trend_following_short_v2",
    "crash_short_v1",
    "crash_short_v2",
    "volatility_breakout",
    "mean_reversion",
    "post_capitulation_long_v1",
    "post_capitulation_long_v2",
    "equity_spy_qqq_sma_band_v1",
    "equity_qqq_trend_v1",
    "REGISTRY",
]
