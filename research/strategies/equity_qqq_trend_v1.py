"""Layer 2 — Equity QQQ Trend v1.

Research-only equity growth sleeve for Itera Dynamics.

Purpose:
    Test whether QQQ can serve as a dedicated equity growth / momentum sleeve,
    instead of forcing SPY to behave as both a defensive stabilizer and a growth
    engine.

Contract:
    generate_intent(df, ctx, closed_only=True) -> StrategyIntent

Design:
    - asset target: QQQ or broad Nasdaq-100 proxy
    - timeframe: daily bars
    - signal family: long-only trend / momentum
    - exposure: binary long / flat
    - no leverage
    - no shorting
    - deterministic and closed-bar only
"""

from __future__ import annotations

import pandas as pd

from research.strategies.contracts import Action, StrategyContext, StrategyIntent

STRATEGY_ID = "equity_qqq_trend_v1"

_FAST_EMA = 50
_SLOW_EMA = 100
_MOMENTUM_LOOKBACK = 63
_SHORT_MOMENTUM_LOOKBACK = 21
_INITIAL_EXPOSURE = 1.00
_MIN_BARS = max(_SLOW_EMA + 5, _MOMENTUM_LOOKBACK + 5)


def _ema(close: pd.Series, span: int) -> pd.Series:
    return close.ewm(span=span, adjust=False).mean()


def generate_intent(
    df: pd.DataFrame,
    ctx: StrategyContext,
    closed_only: bool = True,
) -> StrategyIntent:
    data = df.copy()

    if len(data) < _MIN_BARS:
        return StrategyIntent(
            action=Action.HOLD,
            confidence=0.0,
            desired_exposure_frac=0.0,
            horizon_hours=24 * 20,
            reason=f"warmup: {len(data)}/{_MIN_BARS} daily bars",
            meta={"warmup": True, "bars": len(data)},
            strategy_id=STRATEGY_ID,
        )

    close = data["close"].astype(float)
    last_close = float(close.iloc[-1])
    ema_fast = _ema(close, _FAST_EMA)
    ema_slow = _ema(close, _SLOW_EMA)
    fast_now = float(ema_fast.iloc[-1])
    slow_now = float(ema_slow.iloc[-1])
    long_mom = float(last_close / close.iloc[-_MOMENTUM_LOOKBACK] - 1.0)
    short_mom = float(last_close / close.iloc[-_SHORT_MOMENTUM_LOOKBACK] - 1.0)

    in_position = bool(ctx.current_exposure_frac > 0.01)

    trend_confirmed = (
        last_close > slow_now
        and fast_now > slow_now
        and long_mom > 0.0
    )

    early_exit = short_mom < 0.0 and last_close < fast_now
    trend_exit = last_close < slow_now or long_mom < 0.0
    exit_signal = trend_exit or early_exit

    trend_strength = max(0.0, min(1.0, (fast_now / slow_now - 1.0) * 10.0))
    mom_strength = max(0.0, min(1.0, long_mom * 4.0))
    confidence = max(0.55, min(0.95, 0.50 + 0.25 * trend_strength + 0.25 * mom_strength))

    meta = {
        "asset_class": "equity_growth",
        "asset": getattr(ctx, "asset", None),
        "fast_ema": _FAST_EMA,
        "slow_ema": _SLOW_EMA,
        "momentum_lookback": _MOMENTUM_LOOKBACK,
        "short_momentum_lookback": _SHORT_MOMENTUM_LOOKBACK,
        "last_close": last_close,
        "ema_fast": fast_now,
        "ema_slow": slow_now,
        "long_momentum": long_mom,
        "short_momentum": short_mom,
        "trend_confirmed": trend_confirmed,
        "early_exit": early_exit,
        "trend_exit": trend_exit,
    }

    if not in_position and trend_confirmed:
        return StrategyIntent(
            action=Action.ENTER_LONG,
            confidence=confidence,
            desired_exposure_frac=_INITIAL_EXPOSURE,
            horizon_hours=24 * 20,
            reason="QQQ growth trend confirmed: close > EMA100, EMA50 > EMA100, 63d momentum positive",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    if in_position and exit_signal:
        return StrategyIntent(
            action=Action.EXIT_LONG,
            confidence=max(confidence, 0.70),
            desired_exposure_frac=0.0,
            horizon_hours=24 * 5,
            reason="QQQ growth trend exit: EMA100 / momentum / early-exit condition breached",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    return StrategyIntent(
        action=Action.HOLD,
        confidence=confidence if in_position else 0.0,
        desired_exposure_frac=ctx.current_exposure_frac if in_position else 0.0,
        horizon_hours=24 * 20,
        reason="holding QQQ growth exposure" if in_position else "flat: QQQ growth trend conditions not met",
        meta=meta,
        strategy_id=STRATEGY_ID,
    )
