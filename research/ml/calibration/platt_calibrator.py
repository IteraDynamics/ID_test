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

    Supports two modes:
    - Univariate Platt: P(win) = sigmoid(A * raw_conf + B).
    - Multivariate logistic: P(win) = sigmoid(weights · features + B).
      Used automatically when raw confidence has near-zero variance (e.g. a
      strategy emits the same constant confidence for every entry).

    Attributes
    ----------
    A : float
        Platt slope (univariate mode). 1.0 when unfitted.
    B : float
        Intercept. Used in both univariate and multivariate modes.
    strategy_id : str
        Strategy this calibrator was trained for.
    model_version : str
        Identifier for the training run (e.g. date-stamp).
    n_samples : int
        Number of training samples used to fit.
    is_fitted : bool
        False → predict() is a passthrough returning raw confidence unchanged.
    calibration_method : str
        "platt", "isotonic_fallback", or "multivariate_logistic".
    trained_at : str
        ISO-format timestamp of when fit() was called.
    feature_names : list[str]
        Feature names used in multivariate mode (empty for univariate).
    weights : list[float]
        Logistic regression coefficients for multivariate mode.
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
    feature_names: list[float] = field(default_factory=list)
    weights: list[float] = field(default_factory=list)
    _isotonic_xs: list[float] = field(default_factory=list)
    _isotonic_ys: list[float] = field(default_factory=list)

    # ── Inference ────────────────────────────────────────────────────────

    def predict(self, raw_confidence: float) -> float:
        """Return calibrated win probability in [0, 1].

        Returns raw_confidence unchanged if calibrator is not fitted.
        For multivariate mode, falls back to 0.5 when no features are provided.
        """
        if not self.is_fitted:
            return float(raw_confidence)

        if self.calibration_method == "isotonic_fallback":
            return self._isotonic_predict(raw_confidence)

        if self.calibration_method == "multivariate_logistic":
            # Univariate fallback: raw_confidence as a single feature
            if self.feature_names and "raw_confidence" in self.feature_names:
                return self.predict_from_features({"raw_confidence": raw_confidence}, raw_confidence)
            # If raw_confidence is not a trained feature, return base probability
            score = self.B
            return float(np.clip(_sigmoid(np.array(score)), 0.0, 1.0))

        score = self.A * raw_confidence + self.B
        return float(np.clip(_sigmoid(np.array(score)), 0.0, 1.0))

    def predict_from_features(
        self,
        features: dict,
        raw_confidence: float | None = None,
    ) -> float:
        """Return calibrated win probability using full feature vector.

        Used by multivariate logistic mode. Falls back to univariate
        ``predict()`` if this calibrator was not fitted in multivariate mode.

        Parameters
        ----------
        features :
            Dict of feature name → float value (e.g. from ``intent.meta``).
        raw_confidence :
            Raw heuristic confidence (used as fallback for univariate mode).
        """
        if not self.is_fitted:
            return float(raw_confidence) if raw_confidence is not None else 0.5

        if self.calibration_method != "multivariate_logistic" or not self.feature_names:
            # Univariate fallback
            if raw_confidence is not None:
                return self.predict(raw_confidence)
            return 0.5

        x = np.array([features.get(fname, 0.0) for fname in self.feature_names])
        score = float(np.dot(np.array(self.weights), x) + self.B)
        return float(np.clip(_sigmoid(np.array(score)), 0.0, 1.0))

    def predict_with_meta(
        self,
        raw_confidence: float,
        features: dict | None = None,
    ) -> dict:
        """Return calibrated value plus audit metadata dict.

        The dict is injected into ``StrategyIntent.meta["ml_calibration"]``
        by ``_apply_calibration`` for full auditability.

        Parameters
        ----------
        raw_confidence :
            Raw heuristic confidence from the strategy.
        features :
            Optional dict of indicator values from ``intent.meta``.  When
            provided and this is a multivariate calibrator, the full feature
            vector is used instead of just ``raw_confidence``.
        """
        if features and self.calibration_method == "multivariate_logistic":
            calibrated = self.predict_from_features(features, raw_confidence)
        else:
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

    @classmethod
    def fit_multivariate(
        cls,
        samples: list,
        strategy_id: str = "",
        model_version: str = "",
        feature_names: list[str] | None = None,
        min_samples: int = MIN_SAMPLES_PLATT,
    ) -> "PlattCalibrator":
        """Fit multivariate logistic regression on the full indicator feature vector.

        Useful when raw confidence has near-zero variance (e.g. a strategy
        emits a fixed confidence for all entries).  Feature values come from
        ``CalibrationSample.features`` (populated from ``intent.meta`` at the
        entry bar — no lookahead).

        Parameters
        ----------
        samples :
            ``list[CalibrationSample]`` from ``extract_calibration_samples()``.
        strategy_id :
            Strategy identifier for the audit trail.
        model_version :
            Optional version tag (defaults to current timestamp).
        feature_names :
            Explicit list of feature keys to use.  When ``None``, all features
            with non-trivial variance (std > 1e-6) are selected automatically.
        min_samples :
            Minimum samples required to fit; below this returns unfitted.

        Returns
        -------
        PlattCalibrator
            Fitted calibrator with ``calibration_method="multivariate_logistic"``,
            or passthrough if insufficient samples or no variable features found.
        """
        n = len(samples)
        version = model_version or time.strftime("%Y%m%d_%H%M%S")
        base = cls(strategy_id=strategy_id, model_version=version, n_samples=n)

        if n < min_samples:
            return base  # is_fitted=False → passthrough

        if not _SCIPY_AVAILABLE:
            return base

        # Collect candidate feature names with non-trivial variance
        if feature_names is None:
            all_keys: list[str] = []
            seen: set[str] = set()
            for s in samples:
                for k in s.features:
                    if k not in seen:
                        all_keys.append(k)
                        seen.add(k)
            feature_names = []
            for k in all_keys:
                vals = np.array([s.features.get(k, 0.0) for s in samples])
                if float(np.std(vals)) > 1e-6:
                    feature_names.append(k)
            feature_names = sorted(feature_names)  # deterministic ordering

        if not feature_names:
            return base  # no variable features

        # Build feature matrix
        X_raw = np.array(
            [[s.features.get(fname, 0.0) for fname in feature_names] for s in samples],
            dtype=float,
        )
        labels = np.array([s.outcome_label for s in samples], dtype=float)

        # Standardize (zero-mean, unit-variance) for numerical stability
        mu = X_raw.mean(axis=0)
        sigma = X_raw.std(axis=0)
        sigma[sigma < 1e-8] = 1.0  # avoid divide-by-zero for near-constant features
        X_std = (X_raw - mu) / sigma

        def neg_ll(params: np.ndarray) -> float:
            w = params[:-1]
            b = params[-1]
            p = _sigmoid(X_std @ w + b)
            eps = 1e-12
            p = np.clip(p, eps, 1.0 - eps)
            return -float(np.mean(labels * np.log(p) + (1.0 - labels) * np.log(1.0 - p)))

        x0 = np.zeros(len(feature_names) + 1)
        result = minimize(neg_ll, x0, method="L-BFGS-B", options={"maxiter": 2000, "ftol": 1e-9})

        if result.fun >= neg_ll(x0):
            return base  # optimization did not improve on the null model

        w_std = result.x[:-1]
        b_std = result.x[-1]

        # Convert standardized weights → raw-feature weights so no standardization
        # is needed at inference time:  sigmoid(w_std · z + b) = sigmoid(w_raw · x + b_raw)
        w_raw = w_std / sigma
        b_raw = float(b_std - np.dot(w_raw, mu))

        base.feature_names = feature_names
        base.weights = w_raw.tolist()
        base.A = 0.0  # not used in multivariate mode
        base.B = b_raw
        base.is_fitted = True
        base.calibration_method = "multivariate_logistic"
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
