"""Shared helpers for research-only single-asset equity SMA sleeves.

This module intentionally implements a *single-asset* interpretation of the
SPY/QQQ SMA-band research idea. Each strategy wrapper owns exactly one asset
and returns an executable long/flat exposure intent for that asset's sleeve.

Contract:
    generate_intent(df, ctx, closed_only=True) -> StrategyIntent

Design constraints:
    - Layer 2 only: no I/O, no broker dependency, no mutable state.
    - Closed-bar only: the caller supplies bars available through the current
      decision point.
    - Long/flat only: no leverage and no shorting.
    - desired_exposure_frac is local to the asset sleeve, not portfolio gross.
"""

from __future__ import annotations

import pandas as pd

from research.strategies.contracts import Action, StrategyContext, StrategyIntent

DEFAULT_SMA_WINDOW = 175
RESEARCH_BAND_MIN = 150
RESEARCH_BAND_MAX = 200
_MIN_CONFIDENCE = 0.55
_FULL_EXPOSURE = 1.00
_FLAT_THRESHOLD = 0.01


def _validate_sma_window(sma_window: int) -> int:
    window = int(sma_window)
    if window <= 1:
        raise ValueError(f"sma_window must be > 1, got {sma_window}")
    return window


def _confidence(close: float, sma: float) -> float:
    if sma <= 0:
        return 0.0
    distance = abs(close / sma - 1.0)
    return max(_MIN_CONFIDENCE, min(0.95, 0.55 + distance * 5.0))


def generate_single_asset_sma_intent(
    df: pd.DataFrame,
    ctx: StrategyContext,
    *,
    asset: str,
    strategy_id: str,
    sma_window: int = DEFAULT_SMA_WINDOW,
) -> StrategyIntent:
    """Generate a long/flat SMA-band intent for one equity asset.

    Parameters
    ----------
    df:
        Single-asset OHLCV DataFrame. Must include a `close` column.
    ctx:
        Strategy context supplied by the harness/runtime.
    asset:
        Human-readable asset label, e.g. `SPY` or `QQQ`.
    strategy_id:
        Unique strategy identifier for audit trail.
    sma_window:
        Daily SMA lookback. The researched band is 150-200 trading days;
        the default center is 175.
    """
    window = _validate_sma_window(sma_window)
    asset = asset.upper()

    if "close" not in df.columns:
        raise ValueError(
            f"{strategy_id}: expected single-asset OHLCV with a 'close' column; "
            f"got columns={list(df.columns)}"
        )

    close = pd.to_numeric(df["close"], errors="coerce").dropna()
    bars = len(close)

    base_meta = {
        "asset_class": "equity",
        "asset": asset,
        "research_band": [RESEARCH_BAND_MIN, RESEARCH_BAND_MAX],
        "preferred_center": DEFAULT_SMA_WINDOW,
        "sma_window": window,
        "bars": bars,
        "closed_bar_signal": True,
        "target_effective_next_bar": True,
        "single_asset_sleeve": True,
    }

    if bars < window:
        return StrategyIntent(
            action=Action.HOLD,
            confidence=0.0,
            desired_exposure_frac=0.0,
            horizon_hours=24 * 20,
            reason=f"warmup: {bars}/{window} daily bars",
            meta={**base_meta, "warmup": True, "active": False},
            strategy_id=strategy_id,
        )

    sma = close.rolling(window, min_periods=window).mean()
    last_close = float(close.iloc[-1])
    last_sma = float(sma.iloc[-1])
    active = bool(last_close > last_sma)
    current = float(ctx.current_exposure_frac)
    conf = _confidence(last_close, last_sma)

    meta = {
        **base_meta,
        "warmup": False,
        "close": last_close,
        "sma": last_sma,
        "distance_to_sma": (last_close / last_sma - 1.0) if last_sma > 0 else None,
        "active": active,
        "ctx_asset": getattr(ctx, "asset", None),
        "ctx_bar_index": getattr(ctx, "bar_index", None),
    }

    if active and current < _FULL_EXPOSURE - _FLAT_THRESHOLD:
        return StrategyIntent(
            action=Action.ENTER_LONG,
            confidence=conf,
            desired_exposure_frac=_FULL_EXPOSURE,
            horizon_hours=24 * 20,
            reason=f"{asset} close above SMA{window}: long sleeve",
            meta=meta,
            strategy_id=strategy_id,
        )

    if not active and current > _FLAT_THRESHOLD:
        return StrategyIntent(
            action=Action.EXIT_LONG,
            confidence=conf,
            desired_exposure_frac=0.0,
            horizon_hours=24 * 5,
            reason=f"{asset} close below/equal SMA{window}: exit sleeve",
            meta=meta,
            strategy_id=strategy_id,
        )

    return StrategyIntent(
        action=Action.HOLD,
        confidence=conf if current > _FLAT_THRESHOLD else 0.0,
        desired_exposure_frac=current if active else 0.0,
        horizon_hours=24 * 20,
        reason=f"{asset} SMA{window} state unchanged",
        meta=meta,
        strategy_id=strategy_id,
    )
