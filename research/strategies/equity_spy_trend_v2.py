"""Layer 2 — Equity SPY Daily Trend v2.

Research-only equity strategy intended to improve on Equity Sleeve v1 by using
partial exposure instead of binary long/flat behavior.

Goal:
    Improve participation in equity bull markets and recoveries while preserving
    the defensive drawdown behavior of Equity Sleeve v1.

Contract:
    generate_intent(df, ctx, closed_only=True) -> StrategyIntent

Design:
    - daily SPY or broad equity ETF bars
    - long-only
    - no leverage
    - no shorting
    - exposure states: 0%, 40%, 80%, 100%
    - deterministic and closed-bar only
"""

from __future__ import annotations

import pandas as pd

from research.strategies.contracts import Action, StrategyContext, StrategyIntent

STRATEGY_ID = "equity_spy_trend_v2"

_FAST_EMA = 50
_SLOW_EMA = 200
_MOMENTUM_LOOKBACK = 63
_SHORT_MOMENTUM_LOOKBACK = 21
_MIN_BARS = max(_SLOW_EMA + 5, _MOMENTUM_LOOKBACK + 5)


def _ema(close: pd.Series, span: int) -> pd.Series:
    return close.ewm(span=span, adjust=False).mean()


def _target_exposure(close: pd.Series) -> tuple[float, str, dict]:
    last_close = float(close.iloc[-1])
    ema_fast = _ema(close, _FAST_EMA)
    ema_slow = _ema(close, _SLOW_EMA)
    fast_now = float(ema_fast.iloc[-1])
    slow_now = float(ema_slow.iloc[-1])
    long_mom = float(last_close / close.iloc[-_MOMENTUM_LOOKBACK] - 1.0)
    short_mom = float(last_close / close.iloc[-_SHORT_MOMENTUM_LOOKBACK] - 1.0)

    above_slow = last_close > slow_now
    fast_above_slow = fast_now > slow_now
    long_mom_positive = long_mom > 0.0
    short_mom_positive = short_mom > 0.0

    trend_score = 0
    trend_score += 1 if above_slow else 0
    trend_score += 1 if fast_above_slow else 0
    trend_score += 1 if long_mom_positive else 0
    trend_score += 1 if short_mom_positive else 0

    meta = {
        "asset_class": "equity",
        "fast_ema": _FAST_EMA,
        "slow_ema": _SLOW_EMA,
        "momentum_lookback": _MOMENTUM_LOOKBACK,
        "short_momentum_lookback": _SHORT_MOMENTUM_LOOKBACK,
        "last_close": last_close,
        "ema_fast": fast_now,
        "ema_slow": slow_now,
        "long_momentum": long_mom,
        "short_momentum": short_mom,
        "above_slow": above_slow,
        "fast_above_slow": fast_above_slow,
        "trend_score": trend_score,
    }

    if trend_score == 4:
        return 1.00, "full equity trend confirmation", meta
    if trend_score == 3:
        return 0.80, "strong equity trend confirmation", meta
    if trend_score == 2 and above_slow:
        return 0.40, "partial equity exposure: mixed but price above long trend", meta
    return 0.0, "flat: insufficient equity trend confirmation", meta


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
    target, reason, meta = _target_exposure(close)
    current = float(ctx.current_exposure_frac or 0.0)
    delta = target - current

    confidence = 0.55 + 0.10 * float(meta["trend_score"])
    confidence = max(0.0, min(0.95, confidence))

    if abs(delta) < 0.05:
        return StrategyIntent(
            action=Action.HOLD,
            confidence=confidence if target > 0 else 0.0,
            desired_exposure_frac=current,
            horizon_hours=24 * 20,
            reason=f"hold: target exposure unchanged ({target:.0%})",
            meta={**meta, "target_exposure": target, "current_exposure": current},
            strategy_id=STRATEGY_ID,
        )

    if target <= 0.0:
        return StrategyIntent(
            action=Action.EXIT_LONG,
            confidence=max(confidence, 0.70),
            desired_exposure_frac=0.0,
            horizon_hours=24 * 5,
            reason=reason,
            meta={**meta, "target_exposure": target, "current_exposure": current},
            strategy_id=STRATEGY_ID,
        )

    return StrategyIntent(
        action=Action.ENTER_LONG,
        confidence=confidence,
        desired_exposure_frac=target,
        horizon_hours=24 * 20,
        reason=reason,
        meta={**meta, "target_exposure": target, "current_exposure": current},
        strategy_id=STRATEGY_ID,
    )
