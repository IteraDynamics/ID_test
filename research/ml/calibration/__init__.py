"""research.ml.calibration — Post-process heuristic confidence → P(win).

Public API
----------
make_calibrated_strategy(module, calibrator)
    Wraps a strategy module so that every ENTER_LONG intent has its
    confidence replaced by the calibrated probability.  All other intents
    (EXIT_LONG, HOLD, FLAT) are passed through unchanged.

    Returns the original module unchanged if calibrator is None or unfitted.

_apply_calibration(intent, calibrator)
    Low-level function: applies one calibrator to one StrategyIntent.
    Exported for testing.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from research.strategies.contracts import Action, StrategyContext, StrategyIntent
from research.ml.calibration.platt_calibrator import PlattCalibrator


# ── Core calibration helper ───────────────────────────────────────────────────

def _apply_calibration(
    intent: StrategyIntent,
    calibrator: PlattCalibrator,
) -> StrategyIntent:
    """Return a new StrategyIntent with calibrated confidence.

    Only ENTER_LONG intents are modified; all others are returned as-is.
    If the calibrator is unfitted, the intent is returned unchanged.

    The raw confidence is preserved in ``intent.meta["ml_calibration"]["raw_confidence"]``
    for the full audit trail.
    """
    if intent.action != Action.ENTER_LONG or not calibrator.is_fitted:
        return intent

    cal_meta = calibrator.predict_with_meta(intent.confidence)
    calibrated_conf = cal_meta["calibrated_confidence"]
    # Enforce valid range (PlattCalibrator already clips, but be defensive)
    calibrated_conf = max(0.0, min(1.0, float(calibrated_conf)))

    return StrategyIntent(
        action=intent.action,
        confidence=calibrated_conf,
        desired_exposure_frac=intent.desired_exposure_frac,
        horizon_hours=intent.horizon_hours,
        reason=intent.reason,
        meta={**intent.meta, "ml_calibration": cal_meta},
        strategy_id=intent.strategy_id,
    )


# ── Strategy wrapper ──────────────────────────────────────────────────────────

class _CalibratedStrategyWrapper:
    """Thin wrapper around a strategy module that post-processes confidence.

    Exposes the same ``generate_intent(df, ctx, closed_only)`` interface so
    it is a drop-in replacement everywhere a strategy module is expected.
    """

    def __init__(self, module: Any, calibrator: PlattCalibrator | None) -> None:
        self._module = module
        self._calibrator = calibrator
        # Preserve the strategy id and module name for auditability
        self.STRATEGY_ID = getattr(module, "STRATEGY_ID", "unknown")
        self.__name__ = getattr(module, "__name__", str(module))

    def generate_intent(
        self,
        df: pd.DataFrame,
        ctx: StrategyContext,
        closed_only: bool = True,
    ) -> StrategyIntent:
        intent = self._module.generate_intent(df, ctx, closed_only=closed_only)
        if self._calibrator is None or not self._calibrator.is_fitted:
            return intent
        return _apply_calibration(intent, self._calibrator)


def make_calibrated_strategy(
    strategy_module: Any,
    calibrator: PlattCalibrator | None,
) -> Any:
    """Wrap a strategy module with optional confidence calibration.

    Parameters
    ----------
    strategy_module :
        A module or object exposing ``generate_intent(df, ctx, closed_only)``.
    calibrator :
        A fitted ``PlattCalibrator``.  If ``None`` or unfitted, the original
        module is returned unchanged (zero overhead, identical behaviour).

    Returns
    -------
    Any
        Either the original module (no-op case) or a
        ``_CalibratedStrategyWrapper`` that has the same interface.
    """
    if calibrator is None or not calibrator.is_fitted:
        return strategy_module
    return _CalibratedStrategyWrapper(strategy_module, calibrator)


__all__ = [
    "make_calibrated_strategy",
    "_apply_calibration",
    "PlattCalibrator",
]
