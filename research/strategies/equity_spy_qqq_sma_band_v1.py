"""Layer 2 — Equity Book SPY/QQQ SMA Band v1.

Research-only implementation-readiness module for the Equity Book v1 finalist
band documented in `docs/equity_book_v1_baseline_findings.md`.

The strategy is a deterministic daily SPY/QQQ trend-to-cash book:
    - 50% SPY sleeve when SPY closes above its SMA window.
    - 50% QQQ sleeve when QQQ closes above its SMA window.
    - inactive sleeve exposure goes to cash.
    - default center window is 175 trading days inside the researched
      150–200 day band.

Contract:
    generate_intent(df, ctx, closed_only=True) -> StrategyIntent

Implementation notes:
    - This is not a broker/runtime module.
    - It has no I/O and no mutable state.
    - It uses only bars supplied in df, which must already be closed bars.
    - The returned weights are target weights for the *next* executable bar.
    - Multi-asset target weights are carried in intent.meta["target_weights"].
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from research.strategies.contracts import Action, StrategyContext, StrategyIntent


STRATEGY_ID = "equity_spy_qqq_sma_band_v1"
DEFAULT_SMA_WINDOW = 175
RESEARCH_BAND_MIN = 150
RESEARCH_BAND_MAX = 200
SPY_TARGET_WEIGHT = 0.50
QQQ_TARGET_WEIGHT = 0.50
_MIN_CONFIDENCE = 0.55


@dataclass(frozen=True)
class EquityBookSignal:
    """Single-bar target weights and diagnostics for the SPY/QQQ book."""

    target_weights: dict[str, float]
    sma_window: int
    spy_close: float | None
    qqq_close: float | None
    spy_sma: float | None
    qqq_sma: float | None
    spy_active: bool
    qqq_active: bool
    gross_exposure: float
    cash_weight: float
    warmup: bool
    bars: int

    def as_meta(self) -> dict[str, Any]:
        return {
            "asset_class": "equity",
            "book": "SPY_QQQ",
            "research_band": [RESEARCH_BAND_MIN, RESEARCH_BAND_MAX],
            "preferred_center": DEFAULT_SMA_WINDOW,
            "sma_window": self.sma_window,
            "target_weights": self.target_weights,
            "spy_close": self.spy_close,
            "qqq_close": self.qqq_close,
            "spy_sma": self.spy_sma,
            "qqq_sma": self.qqq_sma,
            "spy_active": self.spy_active,
            "qqq_active": self.qqq_active,
            "gross_exposure": self.gross_exposure,
            "cash_weight": self.cash_weight,
            "warmup": self.warmup,
            "bars": self.bars,
            "closed_bar_signal": True,
            "target_effective_next_bar": True,
        }


def _validate_sma_window(sma_window: int) -> int:
    window = int(sma_window)
    if window <= 1:
        raise ValueError(f"sma_window must be > 1, got {sma_window}")
    return window


def _find_close_column(df: pd.DataFrame, asset: str) -> str:
    """Find a close column for an asset in a wide daily equity DataFrame."""
    asset_upper = asset.upper()
    asset_lower = asset.lower()
    candidates = [
        f"{asset_lower}_close",
        f"{asset_upper}_close",
        f"close_{asset_lower}",
        f"close_{asset_upper}",
        f"{asset_lower}.close",
        f"{asset_upper}.close",
        asset_lower,
        asset_upper,
    ]
    lower_map = {str(c).lower(): str(c) for c in df.columns}
    for candidate in candidates:
        if candidate.lower() in lower_map:
            return lower_map[candidate.lower()]
    raise ValueError(
        f"Could not find close column for {asset_upper}. "
        f"Expected one of {candidates}; got columns={list(df.columns)}"
    )


def compute_signal(
    df: pd.DataFrame,
    sma_window: int = DEFAULT_SMA_WINDOW,
) -> EquityBookSignal:
    """Compute the latest closed-bar SPY/QQQ target weights.

    Parameters
    ----------
    df:
        Wide daily DataFrame containing SPY and QQQ close columns. Supported
        names include `spy_close`/`qqq_close`, `SPY_close`/`QQQ_close`,
        `close_spy`/`close_qqq`, or `SPY`/`QQQ`.
    sma_window:
        SMA lookback in trading days. The researched finalist band is 150–200;
        the default preferred center is 175.
    """
    window = _validate_sma_window(sma_window)
    if df.empty:
        return _warmup_signal(window, bars=0)

    spy_col = _find_close_column(df, "SPY")
    qqq_col = _find_close_column(df, "QQQ")
    data = df[[spy_col, qqq_col]].copy()
    data.columns = ["SPY", "QQQ"]
    data["SPY"] = pd.to_numeric(data["SPY"], errors="coerce")
    data["QQQ"] = pd.to_numeric(data["QQQ"], errors="coerce")
    data = data.dropna(subset=["SPY", "QQQ"])

    if len(data) < window:
        return _warmup_signal(window, bars=len(data))

    spy_close = float(data["SPY"].iloc[-1])
    qqq_close = float(data["QQQ"].iloc[-1])
    spy_sma = float(data["SPY"].rolling(window, min_periods=window).mean().iloc[-1])
    qqq_sma = float(data["QQQ"].rolling(window, min_periods=window).mean().iloc[-1])

    spy_active = bool(spy_close > spy_sma)
    qqq_active = bool(qqq_close > qqq_sma)
    spy_weight = SPY_TARGET_WEIGHT if spy_active else 0.0
    qqq_weight = QQQ_TARGET_WEIGHT if qqq_active else 0.0
    gross = float(spy_weight + qqq_weight)
    cash = float(max(0.0, 1.0 - gross))

    return EquityBookSignal(
        target_weights={"SPY": spy_weight, "QQQ": qqq_weight, "cash": cash},
        sma_window=window,
        spy_close=spy_close,
        qqq_close=qqq_close,
        spy_sma=spy_sma,
        qqq_sma=qqq_sma,
        spy_active=spy_active,
        qqq_active=qqq_active,
        gross_exposure=gross,
        cash_weight=cash,
        warmup=False,
        bars=len(data),
    )


def _warmup_signal(sma_window: int, bars: int) -> EquityBookSignal:
    return EquityBookSignal(
        target_weights={"SPY": 0.0, "QQQ": 0.0, "cash": 1.0},
        sma_window=sma_window,
        spy_close=None,
        qqq_close=None,
        spy_sma=None,
        qqq_sma=None,
        spy_active=False,
        qqq_active=False,
        gross_exposure=0.0,
        cash_weight=1.0,
        warmup=True,
        bars=bars,
    )


def _confidence(signal: EquityBookSignal) -> float:
    if signal.warmup:
        return 0.0
    distances = []
    if signal.spy_close and signal.spy_sma and signal.spy_sma > 0:
        distances.append(abs(signal.spy_close / signal.spy_sma - 1.0))
    if signal.qqq_close and signal.qqq_sma and signal.qqq_sma > 0:
        distances.append(abs(signal.qqq_close / signal.qqq_sma - 1.0))
    avg_distance = float(sum(distances) / len(distances)) if distances else 0.0
    return max(_MIN_CONFIDENCE, min(0.95, 0.55 + avg_distance * 5.0))


def generate_intent(
    df: pd.DataFrame,
    ctx: StrategyContext,
    closed_only: bool = True,
    sma_window: int = DEFAULT_SMA_WINDOW,
) -> StrategyIntent:
    """Generate the latest closed-bar SPY/QQQ book intent.

    The StrategyIntent `desired_exposure_frac` is the gross equity exposure.
    The per-asset target weights are provided in `meta["target_weights"]`.
    """
    signal = compute_signal(df, sma_window=sma_window)
    meta = signal.as_meta()
    meta["ctx_asset"] = getattr(ctx, "asset", None)
    meta["ctx_bar_index"] = getattr(ctx, "bar_index", None)

    if signal.warmup:
        return StrategyIntent(
            action=Action.HOLD,
            confidence=0.0,
            desired_exposure_frac=0.0,
            horizon_hours=24,
            reason=f"warmup: {signal.bars}/{signal.sma_window} daily bars",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    current = float(ctx.current_exposure_frac)
    target = float(signal.gross_exposure)
    conf = _confidence(signal)

    if target > current + 0.01:
        action = Action.ENTER_LONG
        reason = "increase SPY/QQQ equity book exposure from closed-bar SMA signal"
    elif target < current - 0.01:
        action = Action.EXIT_LONG if target <= 0.0 else Action.HOLD
        reason = "reduce SPY/QQQ equity book exposure from closed-bar SMA signal"
    else:
        action = Action.HOLD
        reason = "maintain SPY/QQQ equity book exposure"

    return StrategyIntent(
        action=action,
        confidence=conf,
        desired_exposure_frac=target,
        horizon_hours=24 * 20,
        reason=reason,
        meta=meta,
        strategy_id=STRATEGY_ID,
    )
