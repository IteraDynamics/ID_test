"""Itera Allocator v1 — Dynamic multi-asset research allocator.

Research-only allocator for combining Crypto Sleeve v1 and Equity Sleeve v1.

Goal:
    Test whether simple, explainable dynamic allocation can improve on the
    Itera Fund v0 static 70/30 baseline without introducing overfit behavior.

Inputs:
    Daily equity curves for crypto and equity sleeves.

Outputs:
    Daily target weights for crypto and equity sleeves.

Design principles:
    - Deterministic
    - Low-turnover
    - No optimization
    - No future leakage
    - Small, bounded allocation shifts
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class AllocatorDecision:
    crypto_weight: float
    equity_weight: float
    reason: str
    crypto_score: float
    equity_score: float


@dataclass(frozen=True)
class AllocatorConfig:
    base_crypto_weight: float = 0.70
    base_equity_weight: float = 0.30
    min_crypto_weight: float = 0.50
    max_crypto_weight: float = 0.80
    rebalance_threshold: float = 0.05
    fast_ma_days: int = 50
    slow_ma_days: int = 200
    momentum_days: int = 63


def _trend_score(curve: pd.Series, fast_days: int, slow_days: int, momentum_days: int) -> float:
    """Return a simple bounded trend score in [-1, +1]."""
    if len(curve) < max(slow_days, momentum_days) + 5:
        return 0.0

    s = curve.dropna().astype(float)
    fast = s.ewm(span=fast_days, adjust=False).mean().iloc[-1]
    slow = s.ewm(span=slow_days, adjust=False).mean().iloc[-1]
    mom = s.iloc[-1] / s.iloc[-momentum_days] - 1.0

    score = 0.0
    score += 0.5 if fast > slow else -0.5
    score += 0.3 if s.iloc[-1] > slow else -0.3
    score += 0.2 if mom > 0 else -0.2
    return max(-1.0, min(1.0, score))


def decide_weights(
    crypto_curve: pd.Series,
    equity_curve: pd.Series,
    current_crypto_weight: float | None = None,
    config: AllocatorConfig | None = None,
) -> AllocatorDecision:
    """Return target crypto/equity weights using only data available so far."""
    cfg = config or AllocatorConfig()
    current_crypto_weight = cfg.base_crypto_weight if current_crypto_weight is None else current_crypto_weight

    crypto_score = _trend_score(crypto_curve, cfg.fast_ma_days, cfg.slow_ma_days, cfg.momentum_days)
    equity_score = _trend_score(equity_curve, cfg.fast_ma_days, cfg.slow_ma_days, cfg.momentum_days)
    spread = crypto_score - equity_score

    target_crypto = cfg.base_crypto_weight
    reason = "neutral: base allocation"

    if spread >= 0.75:
        target_crypto = cfg.max_crypto_weight
        reason = "crypto favored: crypto trend score materially stronger"
    elif spread <= -0.75:
        target_crypto = cfg.min_crypto_weight
        reason = "equity favored: equity trend score materially stronger"
    elif crypto_score < 0 and equity_score < 0:
        target_crypto = cfg.min_crypto_weight
        reason = "risk-off: both sleeves have negative trend scores"

    if abs(target_crypto - current_crypto_weight) < cfg.rebalance_threshold:
        target_crypto = current_crypto_weight
        reason = f"hold weights: change below rebalance threshold ({cfg.rebalance_threshold:.0%})"

    target_crypto = max(cfg.min_crypto_weight, min(cfg.max_crypto_weight, target_crypto))
    target_equity = 1.0 - target_crypto

    return AllocatorDecision(
        crypto_weight=target_crypto,
        equity_weight=target_equity,
        reason=reason,
        crypto_score=crypto_score,
        equity_score=equity_score,
    )
