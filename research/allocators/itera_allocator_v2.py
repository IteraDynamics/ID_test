"""Itera Allocator v2 — Defensive Overlay Allocator.

Research-only allocator for Itera Fund v0.

Allocator v1 attempted continuous relative-strength allocation and did not beat
static baselines. Allocator v2 uses a stricter mandate:

    Default to the static baseline.
    Intervene only when risk conditions justify it.

Design principles:
    - defensive overlay, not return optimizer
    - low turnover
    - deterministic
    - no future leakage
    - bounded deviations from baseline
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class DefensiveAllocatorConfig:
    base_crypto_weight: float = 0.70
    defensive_crypto_weight: float = 0.50
    min_defensive_days: int = 20
    drawdown_trigger: float = -0.10
    drawdown_recover: float = -0.04
    fast_ma_days: int = 50
    slow_ma_days: int = 200
    momentum_days: int = 63
    min_warmup_days: int = 200


@dataclass(frozen=True)
class DefensiveAllocatorDecision:
    crypto_weight: float
    equity_weight: float
    defensive_state: bool
    crypto_drawdown: float
    crypto_trend_score: float
    equity_trend_score: float
    reason: str


def _drawdown(curve: pd.Series) -> float:
    if curve.empty:
        return 0.0
    peak = float(curve.cummax().iloc[-1])
    if peak <= 0:
        return 0.0
    return float(curve.iloc[-1] / peak - 1.0)


def _trend_score(curve: pd.Series, fast_days: int, slow_days: int, momentum_days: int) -> float:
    if len(curve) < max(slow_days, momentum_days) + 5:
        return 0.0

    s = curve.dropna().astype(float)
    fast = float(s.ewm(span=fast_days, adjust=False).mean().iloc[-1])
    slow = float(s.ewm(span=slow_days, adjust=False).mean().iloc[-1])
    mom = float(s.iloc[-1] / s.iloc[-momentum_days] - 1.0)

    score = 0.0
    score += 0.5 if fast > slow else -0.5
    score += 0.3 if s.iloc[-1] > slow else -0.3
    score += 0.2 if mom > 0 else -0.2
    return max(-1.0, min(1.0, score))


def decide_defensive_weights(
    crypto_curve: pd.Series,
    equity_curve: pd.Series,
    current_defensive_state: bool = False,
    defensive_days: int = 0,
    config: DefensiveAllocatorConfig | None = None,
) -> DefensiveAllocatorDecision:
    """Return next target weights for the defensive overlay.

    Uses only data available through the current close.
    """
    cfg = config or DefensiveAllocatorConfig()

    if len(crypto_curve) < cfg.min_warmup_days or len(equity_curve) < cfg.min_warmup_days:
        return DefensiveAllocatorDecision(
            crypto_weight=cfg.base_crypto_weight,
            equity_weight=1.0 - cfg.base_crypto_weight,
            defensive_state=False,
            crypto_drawdown=_drawdown(crypto_curve),
            crypto_trend_score=0.0,
            equity_trend_score=0.0,
            reason="warmup: base allocation",
        )

    crypto_dd = _drawdown(crypto_curve)
    crypto_score = _trend_score(crypto_curve, cfg.fast_ma_days, cfg.slow_ma_days, cfg.momentum_days)
    equity_score = _trend_score(equity_curve, cfg.fast_ma_days, cfg.slow_ma_days, cfg.momentum_days)

    defensive_state = current_defensive_state
    reason = "base allocation"

    trigger_defense = crypto_dd <= cfg.drawdown_trigger and crypto_score < 0
    allow_recover = (
        defensive_days >= cfg.min_defensive_days
        and crypto_dd >= cfg.drawdown_recover
        and crypto_score > 0
    )

    if current_defensive_state:
        if allow_recover:
            defensive_state = False
            reason = "recover: crypto drawdown repaired and trend score positive"
        else:
            defensive_state = True
            reason = "remain defensive: recovery conditions not met"
    else:
        if trigger_defense:
            defensive_state = True
            reason = "enter defensive: crypto drawdown breach with negative trend score"

    crypto_weight = cfg.defensive_crypto_weight if defensive_state else cfg.base_crypto_weight
    equity_weight = 1.0 - crypto_weight

    return DefensiveAllocatorDecision(
        crypto_weight=crypto_weight,
        equity_weight=equity_weight,
        defensive_state=defensive_state,
        crypto_drawdown=crypto_dd,
        crypto_trend_score=crypto_score,
        equity_trend_score=equity_score,
        reason=reason,
    )
