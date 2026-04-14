"""Signal generator — runs Layer 1 + Layer 2 and returns structured signals.

This is the pure-computation bridge between the research layer and the
runtime execution layer.  It has no I/O and no side effects.

Usage by the orchestrator:
    signals = generate_signals(df, strategies, weights, regime_engine)
    decision = allocator.allocate(signals.intents_with_weights, ...)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from research.regimes.contracts import RegimeLabel, RegimeSignal
from research.regimes.baseline_engine import BaselineRegimeEngine
from research.strategies.contracts import Action, StrategyContext, StrategyIntent


@dataclass
class SignalBundle:
    """Output of generate_signals() for a single bar.

    Attributes
    ----------
    regime_signal : RegimeSignal
        Layer 1 output for the current bar.
    intents_with_weights : list[(StrategyIntent, float)]
        (intent, weight) pairs from all active strategy sleeves.
    bar_index : int
    timestamp : str
    """

    regime_signal: RegimeSignal
    intents_with_weights: list[tuple[StrategyIntent, float]]
    bar_index: int
    timestamp: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def regime(self) -> RegimeLabel:
        return self.regime_signal.label

    @property
    def intents(self) -> list[StrategyIntent]:
        return [intent for intent, _ in self.intents_with_weights]


def generate_signals(
    df: pd.DataFrame,
    strategies: list[tuple[Any, float]],  # (module, weight)
    regime_engine: BaselineRegimeEngine | None = None,
    current_exposure: float = 0.0,
    asset: str = "BTC",
) -> SignalBundle:
    """Generate regime + strategy signals for the latest closed bar in df.

    Parameters
    ----------
    df :
        OHLCV DataFrame up to and including the current closed bar.
    strategies :
        List of (strategy_module, weight) pairs.
    regime_engine :
        Regime engine instance.  Defaults to BaselineRegimeEngine().
    current_exposure :
        Current portfolio exposure fraction.
    asset :
        Asset identifier.

    Returns
    -------
    SignalBundle
    """
    if regime_engine is None:
        regime_engine = BaselineRegimeEngine()

    bar_index = len(df) - 1

    # ── Layer 1: Regime ───────────────────────────────────────────────
    regime_signal = regime_engine.classify_bar(df, bar_index)

    # ── Layer 2: Strategies ───────────────────────────────────────────
    intents_with_weights: list[tuple[StrategyIntent, float]] = []
    for strategy_module, weight in strategies:
        ctx = StrategyContext(
            regime=regime_signal.label,
            current_exposure_frac=current_exposure,
            asset=asset,
            bar_index=bar_index,
        )
        intent = strategy_module.generate_intent(df, ctx, closed_only=True)
        intents_with_weights.append((intent, weight))

    return SignalBundle(
        regime_signal=regime_signal,
        intents_with_weights=intents_with_weights,
        bar_index=bar_index,
        timestamp=str(df.index[-1]) if len(df) > 0 else "",
    )
