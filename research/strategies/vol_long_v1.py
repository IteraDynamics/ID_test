"""Layer 2 — Long Volatility Sleeve v1.

Research-only crash-hedge sleeve for Itera Dynamics.

Purpose:
    Test whether long-volatility exposure (VIX proxies) can improve
    portfolio drawdowns and tail behavior.

Contract:
    generate_intent(df, ctx, closed_only=True) -> StrategyIntent
"""

from __future__ import annotations

import pandas as pd

from research.strategies.contracts import Action, StrategyContext, StrategyIntent

STRATEGY_ID = "vol_long_v1"

_FAST_EMA = 10
_SLOW_EMA = 50
_MOMENTUM_LOOKBACK = 10
_TARGET_EXPOSURE = 1.0
_MIN_BARS = _SLOW_EMA + 5


def _ema(close: pd.Series, span: int) -> pd.Series:
    return close.ewm(span=span, adjust=False).mean()


def generate_intent(df: pd.DataFrame, ctx: StrategyContext, closed_only: bool = True) -> StrategyIntent:
    data = df.copy()

    if len(data) < _MIN_BARS:
        return StrategyIntent(
            action=Action.HOLD,
            confidence=0.0,
            desired_exposure_frac=0.0,
            horizon_hours=24 * 5,
            reason="warmup",
            meta={},
            strategy_id=STRATEGY_ID,
        )

    close = data["close"].astype(float)
    last = float(close.iloc[-1])
    fast = float(_ema(close, _FAST_EMA).iloc[-1])
    slow = float(_ema(close, _SLOW_EMA).iloc[-1])
    mom = float(last / close.iloc[-_MOMENTUM_LOOKBACK] - 1.0)

    in_position = ctx.current_exposure_frac > 0.01

    entry = last > fast > slow and mom > 0
    exit = last < fast or mom < 0

    if not in_position and entry:
        return StrategyIntent(Action.ENTER_LONG, 0.7, _TARGET_EXPOSURE, 24*5,
                              "vol spike / momentum", {}, STRATEGY_ID)

    if in_position and exit:
        return StrategyIntent(Action.EXIT_LONG, 0.7, 0.0, 24*2,
                              "vol decay", {}, STRATEGY_ID)

    return StrategyIntent(Action.HOLD, 0.0 if not in_position else 0.6,
                          ctx.current_exposure_frac if in_position else 0.0,
                          24*5,
                          "hold/flat", {}, STRATEGY_ID)
