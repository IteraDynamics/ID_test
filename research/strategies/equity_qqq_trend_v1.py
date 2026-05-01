"""Layer 2 — Equity QQQ Trend v1b.

Research-only equity growth sleeve for Itera Dynamics.

Purpose:
    Test whether QQQ can serve as a dedicated equity growth / momentum sleeve,
    instead of forcing SPY to behave as both a defensive stabilizer and a growth
    engine.

v1b refinement:
    - require 3 consecutive entry-confirmation days
    - require 2 consecutive exit-confirmation days
    - soften the 21-day early exit
    - add a 10-trading-day minimum hold period

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

STRATEGY_ID = "equity_qqq_trend_v1b"

_FAST_EMA = 50
_SLOW_EMA = 100
_MOMENTUM_LOOKBACK = 63
_SHORT_MOMENTUM_LOOKBACK = 21
_INITIAL_EXPOSURE = 1.00
_ENTRY_CONFIRM_DAYS = 3
_EXIT_CONFIRM_DAYS = 2
_MIN_HOLD_DAYS = 10
_MIN_BARS = max(_SLOW_EMA + 5, _MOMENTUM_LOOKBACK + 5, _ENTRY_CONFIRM_DAYS + 5, _EXIT_CONFIRM_DAYS + 5)


def _ema(close: pd.Series, span: int) -> pd.Series:
    return close.ewm(span=span, adjust=False).mean()


def _consecutive_true(s: pd.Series, days: int) -> bool:
    if len(s) < days:
        return False
    return bool(s.tail(days).all())


def _bars_since_last_entry(ctx: StrategyContext) -> int | None:
    """Best-effort age-in-position from optional StrategyContext metadata.

    The existing research runners do not yet persist an entry timestamp in the
    context. When unavailable, this returns None and the runner-level position
    state remains the source of truth. This keeps the strategy contract pure and
    avoids hidden persistence.
    """
    meta = getattr(ctx, "meta", None) or {}
    val = meta.get("bars_since_entry") if isinstance(meta, dict) else None
    try:
        return None if val is None else int(val)
    except (TypeError, ValueError):
        return None


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
    ema_fast = _ema(close, _FAST_EMA)
    ema_slow = _ema(close, _SLOW_EMA)

    last_close = float(close.iloc[-1])
    fast_now = float(ema_fast.iloc[-1])
    slow_now = float(ema_slow.iloc[-1])
    long_mom_s = close / close.shift(_MOMENTUM_LOOKBACK) - 1.0
    short_mom_s = close / close.shift(_SHORT_MOMENTUM_LOOKBACK) - 1.0
    long_mom = float(long_mom_s.iloc[-1])
    short_mom = float(short_mom_s.iloc[-1])

    in_position = bool(ctx.current_exposure_frac > 0.01)
    bars_since_entry = _bars_since_last_entry(ctx)
    min_hold_met = bars_since_entry is None or bars_since_entry >= _MIN_HOLD_DAYS

    raw_entry = (close > ema_slow) & (ema_fast > ema_slow) & (long_mom_s > 0.0)
    entry_confirmed = _consecutive_true(raw_entry.fillna(False), _ENTRY_CONFIRM_DAYS)

    trend_exit_raw = (close < ema_slow) | (long_mom_s < 0.0)
    softened_early_exit_raw = (short_mom_s < -0.03) & (close < ema_fast) & (ema_fast < ema_fast.shift(3))
    exit_raw = trend_exit_raw | softened_early_exit_raw
    exit_confirmed = _consecutive_true(exit_raw.fillna(False), _EXIT_CONFIRM_DAYS)
    exit_signal = exit_confirmed and min_hold_met

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
        "entry_confirm_days": _ENTRY_CONFIRM_DAYS,
        "exit_confirm_days": _EXIT_CONFIRM_DAYS,
        "min_hold_days": _MIN_HOLD_DAYS,
        "bars_since_entry": bars_since_entry,
        "min_hold_met": min_hold_met,
        "last_close": last_close,
        "ema_fast": fast_now,
        "ema_slow": slow_now,
        "long_momentum": long_mom,
        "short_momentum": short_mom,
        "entry_confirmed": entry_confirmed,
        "exit_confirmed": exit_confirmed,
        "trend_exit_raw": bool(trend_exit_raw.iloc[-1]),
        "softened_early_exit_raw": bool(softened_early_exit_raw.iloc[-1]),
    }

    if not in_position and entry_confirmed:
        return StrategyIntent(
            action=Action.ENTER_LONG,
            confidence=confidence,
            desired_exposure_frac=_INITIAL_EXPOSURE,
            horizon_hours=24 * 20,
            reason="QQQ growth trend confirmed for 3 consecutive days",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    if in_position and exit_signal:
        return StrategyIntent(
            action=Action.EXIT_LONG,
            confidence=max(confidence, 0.70),
            desired_exposure_frac=0.0,
            horizon_hours=24 * 5,
            reason="QQQ growth exit confirmed for 2 consecutive days after minimum hold",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    return StrategyIntent(
        action=Action.HOLD,
        confidence=confidence if in_position else 0.0,
        desired_exposure_frac=ctx.current_exposure_frac if in_position else 0.0,
        horizon_hours=24 * 20,
        reason="holding QQQ growth exposure" if in_position else "flat: QQQ entry confirmation not met",
        meta=meta,
        strategy_id=STRATEGY_ID,
    )
