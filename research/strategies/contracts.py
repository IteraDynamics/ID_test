"""Layer 2 contracts — Action enum, StrategyContext, StrategyIntent.

These are the exclusive inputs/outputs of strategy modules.

Rules:
- No I/O.
- No broker dependency.
- No mutable state between calls.
- Strategy modules may only read the context supplied here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from research.regimes.contracts import RegimeLabel


class Action(str, Enum):
    """Discrete trade intent signal."""

    ENTER_LONG = "ENTER_LONG"
    EXIT_LONG = "EXIT_LONG"
    ENTER_SHORT = "ENTER_SHORT"
    EXIT_SHORT = "EXIT_SHORT"
    HOLD = "HOLD"
    FLAT = "FLAT"

    def is_bullish(self) -> bool:
        return self == Action.ENTER_LONG

    def is_bearish(self) -> bool:
        return self == Action.ENTER_SHORT

    def is_risk_off(self) -> bool:
        return self in (Action.EXIT_LONG, Action.EXIT_SHORT, Action.FLAT)


@dataclass(frozen=False)
class StrategyContext:
    """Execution context passed into every strategy call.

    Contains the current regime and any runtime state the strategy needs to
    observe.  All fields are read-only from the strategy's perspective —
    strategies MUST NOT mutate this object.

    Attributes
    ----------
    regime : RegimeLabel
        Current regime label from Layer 1.
    current_exposure_frac : float
        Current portfolio exposure in [0, 1] as fraction of NAV.
    asset : str
        Asset identifier (e.g. "BTC").
    bar_index : int
        0-based index of the current closed bar in the DataFrame.
    meta : dict
        Optional extra context (e.g. portfolio metrics, funding rates).
    """

    regime: RegimeLabel
    current_exposure_frac: float = 0.0
    asset: str = "BTC"
    bar_index: int = 0
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.current_exposure_frac <= 1.0:
            raise ValueError(
                f"current_exposure_frac must be in [0, 1], got {self.current_exposure_frac}"
            )


@dataclass(frozen=True)
class StrategyIntent:
    """Output of a strategy's generate_intent() call for a single closed bar.

    Attributes
    ----------
    action : Action
        Directional intent.
    confidence : float
        0.0–1.0 confidence in the signal.
    desired_exposure_frac : float
        Desired position size as fraction of NAV [0, 1].
        Layer 3 (allocator/governor) may reduce this further.
    horizon_hours : int
        Suggested holding horizon in hours.  Advisory — not enforced.
    reason : str
        Human-readable explanation for audit / diagnostics.
    meta : dict
        Arbitrary diagnostic data (indicator values, sub-scores, etc.).
    strategy_id : str
        Unique strategy identifier for audit trail.
    """

    action: Action
    confidence: float
    desired_exposure_frac: float
    horizon_hours: int
    reason: str
    meta: dict[str, Any] = field(default_factory=dict)
    strategy_id: str = "unknown"

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0, 1], got {self.confidence}")
        if not 0.0 <= self.desired_exposure_frac <= 1.0:
            raise ValueError(
                f"desired_exposure_frac must be in [0, 1], got {self.desired_exposure_frac}"
            )
        if self.horizon_hours < 0:
            raise ValueError(f"horizon_hours must be >= 0, got {self.horizon_hours}")

    @property
    def is_entry(self) -> bool:
        return self.action in (Action.ENTER_LONG, Action.ENTER_SHORT)

    @property
    def is_exit(self) -> bool:
        return self.action in (Action.EXIT_LONG, Action.EXIT_SHORT, Action.FLAT)

    @property
    def is_hold(self) -> bool:
        return self.action == Action.HOLD

    def with_capped_exposure(self, cap: float) -> "StrategyIntent":
        """Return a new intent with desired_exposure_frac capped at *cap*."""
        return StrategyIntent(
            action=self.action,
            confidence=self.confidence,
            desired_exposure_frac=min(self.desired_exposure_frac, cap),
            horizon_hours=self.horizon_hours,
            reason=self.reason,
            meta={**self.meta, "exposure_cap_applied": cap},
            strategy_id=self.strategy_id,
        )
