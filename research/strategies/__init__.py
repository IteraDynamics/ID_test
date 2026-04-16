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
from research.strategies import volatility_breakout
from research.strategies import mean_reversion

REGISTRY: dict[str, object] = {
    "trend_following": trend_following,
    "trend_following_v2": trend_following_v2,
    "trend_following_v3": trend_following_v3,
    "trend_following_v4": trend_following_v4,
    "volatility_breakout": volatility_breakout,
    "mean_reversion": mean_reversion,
}

__all__ = [
    "Action",
    "StrategyContext",
    "StrategyIntent",
    "trend_following",
    "trend_following_v2",
    "trend_following_v3",
    "trend_following_v4",
    "volatility_breakout",
    "mean_reversion",
    "REGISTRY",
]
