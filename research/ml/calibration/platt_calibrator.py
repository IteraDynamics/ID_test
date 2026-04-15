"""Platt scaling calibrator for strategy confidence scores.

Maps raw heuristic confidence values → calibrated win probability P(win)
using Platt scaling: P(win) = sigmoid(A * raw_conf + B).

Fitted via scipy.optimize.minimize (L-BFGS-B) on binary cross-entropy.
Falls back to a pure-numpy isotonic regression when sample count is low.

Design constraints:
- Uses only scipy + numpy (no scikit-learn dependency).
- Deterministic: same A, B → identical predictions.
- Graceful degradation: unfitted calibrator is a passthrough.
- JSON-serialisable: A and B are plain floats stored in model_store.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

try:
    from scipy.optimize import minimize
    _SCIPY_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SCIPY_AVAILABLE = False


# ── Constants ────────────────────────────────────────────────────────────────
MIN_SAMPLES_PLATT = 30    # below this, stay unfitted (passthrough)
MIN_SAMPLES_ISOTONIC = 10  # isotonic needs fewer points but is coarser


# ── Helpers ──────────────────────────────────────────────────────────────────

def _sigmoid(x: np.ndarray) -> np.ndarray:
    """Numerically stable sigmoid."""
    return np.where(x >= 0, 1.0 / (1.0 + np.exp(-x)), np.exp(x) / (1.0 + np.exp(x)))


def _neg_log_likelihood(params: np.ndarray, scores: np.ndarray, labels: np.ndarray) -> float:
    """Binary cross-entropy loss for Platt scaling."""
    A, B = params
    p = _sigmoid(A * scores + B)
    eps = 1e-12
    p = np.clip(p, eps, 1.0 - eps)
    return -float(np.mean(labels * np.log(p) + (1.0 - labels) * np.log(1.0 - p)))


def _pool_adjacent_violators(scores: np.ndarray, labels: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Pure-numpy isotonic regression via pool adjacent violators.

    Returns (sorted_scores, calibrated_probs) — piecewise-constant mapping.
    """
    order = np.argsort(scores)
    xs = scores[order]
    ys = labels[order].astype(float)

    # PAV: merge adjacent blocks that violate monotone non-decreasing
    # Each block stores (sum_y, count)
    blocks: list[list[float]] = [[y, 1.0] for y in ys]
    i = 0
    while i < len(blocks) - 1:
        if blocks[i][0] / blocks[i][1] > blocks[i + 1][0] / blocks[i + 1][1]:
            # Merge i and i+1
            blocks[i][0] += blocks[i + 1][0]
            blocks[i][1] += blocks[i + 1][1]
            del blocks[i + 1]
            if i > 0:
                i -= 1
        else:
            i += 1

    # Expand back to per-sample predictions
    calibrated = np.empty(len(ys))
    idx = 0
    for block in blocks:
        prob = block[0] / block[1]
        count = int(block[1])
        calibrated[idx : idx + count] = prob
        idx += count

    # Un-sort
    result = np.empty(len(ys))
    result[order] = calibrated
    return xs, result


# ── Main class ───────────────────────────────────────────────────────────────

@dataclass
class PlattCalibrator:
    """Maps raw heuristic confidence → calibrated win probability.

    Platt scaling: P(win) = sigmoid(A * raw_conf + B).

    Attributes
    ----------
    A : float
        Platt slope (fitted). 1.0 when unfitted (identity-ish).
    B : float
        Platt intercept (fitted). 0.0 when unfitted.
    strategy_id : str
        Strategy this calibrator was trained for.
    model_version : str
        Identifier for the training run (e.g. date-stamp).
    n_samples : int
        Number of training samples used to fit.
    is_fitted : bool
        False → predict() is a passthrough returning raw confidence unchanged.
    calibration_method : str
        "platt" or "isotonic_fallback".
    trained_at : str
        ISO-format timestamp of when fit() was called.
    _isotonic_xs : list[float]
        Breakpoints for isotonic fallback (empty when method="platt").
    _isotonic_ys : list[float]
        Calibrated probs at breakpoints (empty when method="platt").
    """

    A: float = 1.0
    B: float = 0.0
    strategy_id: str = ""
    model_version: str = ""
    n_samples: int = 0
    is_fitted: bool = False
    calibration_method: str = "platt"
    trained_at: str = ""
    _isotonic_xs: list[float] = field(default_factory=list)
    _isotonic_ys: list[float] = field(default_factory=list)

    # ── Inference ────────────────────────────────────────────────────────

    def predict(self, raw_confidence: float) -> float:
        """Return calibrated win probability in [0, 1].

        Returns raw_confidence unchanged if calibrator is not fitted.
        """
        if not self.is_fitted:
            return float(raw_confidence)

        if self.calibration_method == "isotonic_fallback":
            return self._isotonic_predict(raw_confidence)

        score = self.A * raw_confidence + self.B
        return float(np.clip(_sigmoid(np.array(score)), 0.0, 1.0))

    def predict_with_meta(self, raw_confidence: float) -> dict:
        """Return calibrated value plus audit metadata dict.

        The dict is injected into ``StrategyIntent.meta["ml_calibration"]``
        by ``_apply_calibration`` for full auditability.
        """
        calibrated = self.predict(raw_confidence)
        return {
            "calibrated_confidence": round(calibrated, 6),
            "raw_confidence": round(float(raw_confidence), 6),
            "model_version": self.model_version,
            "strategy_id": self.strategy_id,
            "calibration_method": self.calibration_method,
            "n_training_samples": self.n_samples,
            "source": "ml_calibrated" if self.is_fitted else "heuristic_passthrough",
        }

    # ── Training ─────────────────────────────────────────────────────────

    @classmethod
    def fit(
        cls,
        raw_confidences: Sequence[float],
        outcome_labels: Sequence[int],
        strategy_id: str = "",
        model_version: str = "",
        min_samples: int = MIN_SAMPLES_PLATT,
    ) -> "PlattCalibrator":
        """Fit a calibrator from training data.

        Parameters
        ----------
        raw_confidences :
            Heuristic confidence values at each entry bar [0, 1].
        outcome_labels :
            Binary labels: 1 = winning trade cycle, 0 = losing trade cycle.
        strategy_id :
            Strategy identifier for the audit trail.
        model_version :
            Optional version tag (defaults to current timestamp).
        min_samples :
            Minimum number of samples required before fitting.
            Below this threshold the calibrator remains unfitted (passthrough).

        Returns
        -------
        PlattCalibrator
            Fitted calibrator, or passthrough calibrator if insufficient data.
        """
        scores = np.asarray(raw_confidences, dtype=float)
        labels = np.asarray(outcome_labels, dtype=float)
        n = len(scores)
        version = model_version or time.strftime("%Y%m%d_%H%M%S")

        base = cls(strategy_id=strategy_id, model_version=version, n_samples=n)

        if n < min_samples:
            return base  # is_fitted=False → passthrough

        # Try Platt scaling first (requires scipy)
        if _SCIPY_AVAILABLE:
            result = minimize(
                _neg_log_likelihood,
                x0=np.array([1.0, 0.0]),
                args=(scores, labels),
                method="L-BFGS-B",
                options={"maxiter": 1000, "ftol": 1e-9},
            )
            if result.success or result.fun < _neg_log_likelihood([1.0, 0.0], scores, labels):
                A, B = float(result.x[0]), float(result.x[1])
                base.A = A
                base.B = B
                base.is_fitted = True
                base.calibration_method = "platt"
                base.trained_at = time.strftime("%Y-%m-%dT%H:%M:%S")
                return base

        # Fallback: isotonic regression (pure numpy)
        if n >= MIN_SAMPLES_ISOTONIC:
            xs, ys = _pool_adjacent_violators(scores, labels)
            # Store unique breakpoints
            unique_xs: list[float] = []
            unique_ys: list[float] = []
            for x, y in zip(xs.tolist(), ys.tolist()):
                if not unique_xs or x != unique_xs[-1]:
                    unique_xs.append(x)
                    unique_ys.append(y)
            base._isotonic_xs = unique_xs
            base._isotonic_ys = unique_ys
            base.is_fitted = True
            base.calibration_method = "isotonic_fallback"
            base.trained_at = time.strftime("%Y-%m-%dT%H:%M:%S")

        return base

    # ── Internal ─────────────────────────────────────────────────────────

    def _isotonic_predict(self, raw_confidence: float) -> float:
        """Linear interpolation over isotonic breakpoints."""
        xs = np.asarray(self._isotonic_xs)
        ys = np.asarray(self._isotonic_ys)
        if len(xs) == 0:
            return float(raw_confidence)
        return float(np.clip(np.interp(raw_confidence, xs, ys), 0.0, 1.0))
