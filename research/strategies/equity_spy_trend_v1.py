"""Layer 2 — Equity SPY Daily Trend v1.

Research-only equity strategy used to test whether the Itera architecture can
extend cleanly beyond crypto.

This module is intentionally simple:
    - asset target: SPY or another broad equity ETF
    - timeframe: daily bars
    - signal family: long-only trend following
    - no leverage, no shorting

Contract:
    generate_intent(df, ctx, closed_only=True) -> StrategyIntent

Design notes:
    - Uses adjusted OHLCV data if supplied by the data file.
    - Uses only closed bars.
    - Requires enough warmup history before entering.
    - Intended as a first framework-generalization test, not a production equity model.
"""

from __future__ import annotations

import pandas as pd

from research.strategies.contracts import Action, StrategyContext, StrategyIntent

STRATEGY_ID = "equity_spy_trend_v1"

_FAST_EMA = 50
_SLOW_EMA = 200
_MOMENTUM_LOOKBACK = 63
_INITIAL_EXPOSURE = 0.80
_MIN_CONFIDENCE = 0.55
_MIN_BARS = max(_SLOW_EMA + 5, _MOMENTUM_LOOKBACK + 5)


def _ema(close: pd.Series, span: int) -> pd.Series:
    return close.ewm(span=span, adjust=False).mean()


def generate_intent(
    df: pd.DataFrame,
    ctx: StrategyContext,
    closed_only: bool = True,
) -> StrategyIntent:
    """Generate a long-only daily SPY trend intent.

    Entry condition:
        close > EMA200, EMA50 > EMA200, and 63-day momentum > 0

    Exit condition:
        close < EMA200 or EMA50 < EMA200

    Otherwise hold / stay flat.
    """
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
    momentum = float(last_close / close.iloc[-_MOMENTUM_LOOKBACK] - 1.0)

    in_position = bool(ctx.current_exposure_frac > 0.01)
    trend_up = last_close > slow_now and fast_now > slow_now and momentum > 0.0
    exit_signal = last_close < slow_now or fast_now < slow_now

    trend_strength = max(0.0, min(1.0, (fast_now / slow_now - 1.0) * 10.0))
    mom_strength = max(0.0, min(1.0, momentum * 4.0))
    confidence = max(_MIN_CONFIDENCE, min(0.95, 0.50 + 0.25 * trend_strength + 0.25 * mom_strength))

    meta = {
        "asset_class": "equity",
        "asset": getattr(ctx, "asset", None),
        "fast_ema": _FAST_EMA,
        "slow_ema": _SLOW_EMA,
        "momentum_lookback": _MOMENTUM_LOOKBACK,
        "last_close": last_close,
        "ema_fast": fast_now,
        "ema_slow": slow_now,
        "momentum": momentum,
        "trend_up": trend_up,
        "exit_signal": exit_signal,
    }

    if not in_position and trend_up:
        return StrategyIntent(
            action=Action.ENTER_LONG,
            confidence=confidence,
            desired_exposure_frac=_INITIAL_EXPOSURE,
            horizon_hours=24 * 20,
            reason="SPY daily trend up: close > EMA200, EMA50 > EMA200, momentum positive",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    if in_position and exit_signal:
        return StrategyIntent(
            action=Action.EXIT_LONG,
            confidence=max(confidence, 0.70),
            desired_exposure_frac=0.0,
            horizon_hours=24 * 5,
            reason="SPY daily trend exit: close/EMA50 below EMA200",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    return StrategyIntent(
        action=Action.HOLD,
        confidence=confidence if in_position else 0.0,
        desired_exposure_frac=ctx.current_exposure_frac if in_position else 0.0,
        horizon_hours=24 * 20,
        reason="holding existing SPY exposure" if in_position else "flat: SPY trend conditions not met",
        meta=meta,
        strategy_id=STRATEGY_ID,
    )
