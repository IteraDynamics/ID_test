"""Layer 1 contracts — RegimeLabel enum and RegimeSignal dataclass.

These types are the exclusive output of the Regime Engine and are consumed by
Layer 2 (strategy modules) and Layer 3 (allocator / governors).

Rules:
- No I/O.
- No broker dependency.
- No mutable state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RegimeLabel(str, Enum):
    """Discrete market regime classifications.

    Values are designed to be:
    - Exhaustive enough to drive conditional strategy behaviour.
    - Sparse enough to remain interpretable.
    - Stable — strategy modules key on these strings, so additions are fine
      but renames require coordinated updates across Layer 2.
    """

    TREND_UP = "TREND_UP"
    TREND_DOWN = "TREND_DOWN"
    RANGE = "RANGE"
    VOL_COMPRESSION = "VOL_COMPRESSION"
    VOL_EXPANSION = "VOL_EXPANSION"
    HIGH_VOL = "HIGH_VOL"
    UNKNOWN = "UNKNOWN"

    def is_trending(self) -> bool:
        return self in (RegimeLabel.TREND_UP, RegimeLabel.TREND_DOWN)

    def is_bullish(self) -> bool:
        return self == RegimeLabel.TREND_UP

    def is_bearish(self) -> bool:
        return self == RegimeLabel.TREND_DOWN

    def is_ranging(self) -> bool:
        return self in (RegimeLabel.RANGE, RegimeLabel.VOL_COMPRESSION)

    def is_high_risk(self) -> bool:
        return self in (RegimeLabel.HIGH_VOL, RegimeLabel.VOL_EXPANSION)


@dataclass(frozen=True)
class RegimeSignal:
    """Output of a single-bar regime classification.

    Attributes:
        label:      The primary regime classification.
        confidence: 0.0–1.0, where 1.0 means all sub-signals agree.
        sub_signals: Dict of intermediate indicator values for audit/debug.
            Keys are implementation-defined (e.g. 'trend_score', 'atr_pct').
        bar_index:  The integer index of the closed bar this signal describes.
        timestamp:  ISO-format timestamp string for the closed bar (optional).
    """

    label: RegimeLabel
    confidence: float
    sub_signals: dict[str, Any] = field(default_factory=dict)
    bar_index: int = -1
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"RegimeSignal.confidence must be in [0, 1], got {self.confidence}"
            )
