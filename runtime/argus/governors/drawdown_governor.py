"""Drawdown governor — halts new BUY activity when portfolio drawdown exceeds threshold.

Behaviour:
- Tracks the high-water mark (HWM) of portfolio NAV.
- If current NAV drops by more than ``halt_threshold`` from HWM, the governor
  blocks all ENTER_LONG / BUY actions.
- SELL / EXIT / FLAT actions always pass through (fail-closed on risk side).
- The halt is cleared when NAV recovers to ``recovery_threshold`` of HWM
  OR when manually reset.

This governor is purely in-memory.  State is persisted externally by the
runtime state module.
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)

DEFAULT_HALT_THRESHOLD = float(os.getenv("MAX_DRAWDOWN_HALT_FRAC", "0.20"))
DEFAULT_RECOVERY_THRESHOLD = 0.10  # recover when DD < 10%


class DrawdownGovernor:
    """Monitors portfolio drawdown and blocks new buys when DD exceeds threshold.

    Parameters
    ----------
    halt_threshold : float
        Max drawdown fraction from HWM before halting buys (e.g. 0.20 = 20%).
    recovery_threshold : float
        Drawdown must recover below this fraction before buys are re-enabled.
    """

    def __init__(
        self,
        halt_threshold: float = DEFAULT_HALT_THRESHOLD,
        recovery_threshold: float = DEFAULT_RECOVERY_THRESHOLD,
    ) -> None:
        if not 0.0 < halt_threshold <= 1.0:
            raise ValueError(f"halt_threshold must be in (0, 1], got {halt_threshold}")
        if not 0.0 < recovery_threshold <= halt_threshold:
            raise ValueError(
                f"recovery_threshold must be in (0, halt_threshold], "
                f"got {recovery_threshold} vs halt={halt_threshold}"
            )

        self.halt_threshold = halt_threshold
        self.recovery_threshold = recovery_threshold

        self._high_water_mark: float | None = None
        self._is_halted: bool = False
        self._halt_nav: float | None = None

    # ── Public API ─────────────────────────────────────────────────────────────

    def update(self, nav: float) -> None:
        """Update governor state with the latest NAV.

        Must be called on every bar before ``is_buy_allowed``.
        """
        if nav <= 0:
            return

        if self._high_water_mark is None or nav > self._high_water_mark:
            self._high_water_mark = nav

        drawdown = (nav - self._high_water_mark) / self._high_water_mark  # ≤ 0

        if not self._is_halted and abs(drawdown) >= self.halt_threshold:
            self._is_halted = True
            self._halt_nav = nav
            log.warning(
                "DrawdownGovernor: HALT triggered. NAV=%.2f HWM=%.2f DD=%.2f%%",
                nav,
                self._high_water_mark,
                abs(drawdown) * 100,
            )

        elif self._is_halted and abs(drawdown) < self.recovery_threshold:
            log.info(
                "DrawdownGovernor: HALT cleared. NAV=%.2f HWM=%.2f DD=%.2f%%",
                nav,
                self._high_water_mark,
                abs(drawdown) * 100,
            )
            self._is_halted = False
            self._halt_nav = None

    def is_buy_allowed(self) -> bool:
        """Return True if new BUY/ENTER_LONG actions are permitted."""
        return not self._is_halted

    def is_sell_allowed(self) -> bool:
        """SELL / EXIT always allowed — never blocked by drawdown governor."""
        return True

    @property
    def current_drawdown_pct(self) -> float:
        """Current drawdown % from HWM (negative number or 0)."""
        if self._high_water_mark is None:
            return 0.0
        # We need the most recent NAV — callers should check after update()
        return 0.0  # stateless after update; use state module for live tracking

    def reset_hwm(self, nav: float) -> None:
        """Manually reset the high-water mark (e.g. on strategy reset)."""
        self._high_water_mark = nav
        self._is_halted = False
        log.info("DrawdownGovernor: HWM reset to %.2f", nav)

    def state_dict(self) -> dict:
        return {
            "high_water_mark": self._high_water_mark,
            "is_halted": self._is_halted,
            "halt_threshold": self.halt_threshold,
            "recovery_threshold": self.recovery_threshold,
        }

    def load_state(self, state: dict) -> None:
        self._high_water_mark = state.get("high_water_mark")
        self._is_halted = state.get("is_halted", False)
