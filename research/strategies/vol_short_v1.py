"""Layer 2 — Short Volatility Sleeve v1.

Research-only volatility carry sleeve for Itera Dynamics.

Purpose:
    Test whether short-volatility exposure can improve portfolio-level results
    as a distinct return stream from crypto and equity beta.

Important:
    This is not a production strategy. Short-volatility products can suffer
    severe tail losses during volatility spikes. This module exists only for
    controlled research.

Contract:
    generate_intent(df, ctx, closed_only=True) -> StrategyIntent

Design:
    - asset target: SVIX / SVXY or equivalent short-vol proxy
    - timeframe: daily bars
    - long-only exposure to short-vol instrument
    - no leverage beyond the product's embedded exposure
    - exit on negative trend or severe drawdown
    - deterministic and closed-bar only
"""

from __future__ import annotations

import pandas as pd

from research.strategies.contracts import Action, StrategyContext, StrategyIntent

STRATEGY_ID = "vol_short_v1"

_FAST_EMA = 20
_SLOW_EMA = 100
_MOMENTUM_LOOKBACK = 21
_DRAWDOWN_LOOKBACK = 63
_MAX_LOCAL_DRAWDOWN = -0.20
_TARGET_EXPOSURE = 1.00
_MIN_BARS = max(_SLOW_EMA + 5, _DRAWDOWN_LOOKBACK + 5)


def _ema(close: pd.Series, span: int) -> pd.Series:
    return close.ewm(span=span, adjust=False).mean()


def _rolling_drawdown(close: pd.Series, lookback: int) -> float:
    window = close.tail(lookback)
    peak = float(window.max())
    if peak <= 0:
        return 0.0
    return float(window.iloc[-1] / peak - 1.0)


def generate_intent(df: pd.DataFrame, ctx: StrategyContext, closed_only: bool = True) -> StrategyIntent:
    data = df.copy()

    if len(data) < _MIN_BARS:
        return StrategyIntent(
            action=Action.HOLD,
            confidence=0.0,
            desired_exposure_frac=0.0,
            horizon_hours=24 * 10,
            reason=f"warmup: {len(data)}/{_MIN_BARS} daily bars",
            meta={"warmup": True, "bars": len(data)},
            strategy_id=STRATEGY_ID,
        )

    close = data["close"].astype(float)
    last = float(close.iloc[-1])
    fast = float(_ema(close, _FAST_EMA).iloc[-1])
    slow = float(_ema(close, _SLOW_EMA).iloc[-1])
    mom = float(last / close.iloc[-_MOMENTUM_LOOKBACK] - 1.0)
    dd = _rolling_drawdown(close, _DRAWDOWN_LOOKBACK)
    in_position = bool(ctx.current_exposure_frac > 0.01)

    entry_signal = last > slow and fast > slow and mom > 0.0 and dd > _MAX_LOCAL_DRAWDOWN
    exit_signal = last < slow or fast < slow or mom < 0.0 or dd <= _MAX_LOCAL_DRAWDOWN

    confidence = 0.55
    if entry_signal:
        confidence = min(0.90, 0.60 + min(0.30, max(0.0, mom)))

    meta = {
        "asset_class": "volatility_short_carry",
        "asset": getattr(ctx, "asset", None),
        "fast_ema": _FAST_EMA,
        "slow_ema": _SLOW_EMA,
        "momentum_lookback": _MOMENTUM_LOOKBACK,
        "drawdown_lookback": _DRAWDOWN_LOOKBACK,
        "max_local_drawdown": _MAX_LOCAL_DRAWDOWN,
        "last_close": last,
        "ema_fast": fast,
        "ema_slow": slow,
        "momentum": mom,
        "rolling_drawdown": dd,
        "entry_signal": entry_signal,
        "exit_signal": exit_signal,
    }

    if not in_position and entry_signal:
        return StrategyIntent(
            action=Action.ENTER_LONG,
            confidence=confidence,
            desired_exposure_frac=_TARGET_EXPOSURE,
            horizon_hours=24 * 10,
            reason="short-vol carry trend confirmed with drawdown guardrail passing",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    if in_position and exit_signal:
        return StrategyIntent(
            action=Action.EXIT_LONG,
            confidence=max(confidence, 0.70),
            desired_exposure_frac=0.0,
            horizon_hours=24 * 3,
            reason="short-vol carry exit: trend/momentum/drawdown guardrail breached",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    return StrategyIntent(
        action=Action.HOLD,
        confidence=confidence if in_position else 0.0,
        desired_exposure_frac=ctx.current_exposure_frac if in_position else 0.0,
        horizon_hours=24 * 10,
        reason="holding short-vol carry exposure" if in_position else "flat: short-vol entry conditions not met",
        meta=meta,
        strategy_id=STRATEGY_ID,
    )
