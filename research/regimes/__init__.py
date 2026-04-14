"""Layer 1 — Regime Engine.

Exports the primary public surface:
    RegimeLabel, RegimeSignal, BaselineRegimeEngine, compute_regime_series
"""

from research.regimes.contracts import RegimeLabel, RegimeSignal
from research.regimes.baseline_engine import BaselineRegimeEngine
from research.regimes.regime_series import compute_regime_series

__all__ = [
    "RegimeLabel",
    "RegimeSignal",
    "BaselineRegimeEngine",
    "compute_regime_series",
]
