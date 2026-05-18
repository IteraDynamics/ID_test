"""Per-label Platt calibrator for regime confidence scores.

The regime engine already emits a confidence value for each RegimeLabel using
linear heuristics.  This module post-processes those values per-label so that
each label's confidence is a calibrated estimate of regime persistence
(i.e. probability that the regime label remains correct N bars ahead).

Training labels are generated without manual annotation: for each bar, the
label is 1 if the regime engine predicts the same label N bars later (the
regime was stable), 0 if it changed.  This is fully causal — the label is
derived from a later bar, but inference only uses the current bar's features.

Usage
-----
    cal = RegimeCalibrator.fit(regime_signals, horizon_bars=24)
    calibrated_conf = cal.predict("TREND_UP", raw_conf=0.72)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Sequence

from research.ml.calibration.platt_calibrator import PlattCalibrator, MIN_SAMPLES_PLATT


@dataclass
class RegimeCalibrator:
    """Per-label Platt calibrators for regime confidence.

    One ``PlattCalibrator`` is fitted per ``RegimeLabel`` string.
    Labels with insufficient samples remain unfitted (passthrough).

    Attributes
    ----------
    calibrators : dict[str, PlattCalibrator]
        Mapping from regime label string → fitted (or unfitted) calibrator.
    model_version : str
        Version tag for audit.
    trained_at : str
        ISO timestamp.
    horizon_bars : int
        Number of bars used to define a "stable regime" training label.
    """

    calibrators: dict[str, PlattCalibrator] = field(default_factory=dict)
    model_version: str = ""
    trained_at: str = ""
    horizon_bars: int = 24

    # ── Inference ─────────────────────────────────────────────────────────

    def predict(self, regime_label: str, raw_confidence: float) -> float:
        """Return calibrated regime confidence in [0, 1].

        Falls back to raw_confidence if no calibrator exists for this label
        or if the label's calibrator is not fitted.
        """
        cal = self.calibrators.get(regime_label)
        if cal is None or not cal.is_fitted:
            return float(raw_confidence)
        return cal.predict(raw_confidence)

    def predict_with_meta(self, regime_label: str, raw_confidence: float) -> dict:
        """Return calibrated value + audit metadata."""
        cal = self.calibrators.get(regime_label)
        if cal is None or not cal.is_fitted:
            return {
                "calibrated_confidence": float(raw_confidence),
                "raw_confidence": float(raw_confidence),
                "regime_label": regime_label,
                "source": "heuristic_passthrough",
                "model_version": self.model_version,
            }
        meta = cal.predict_with_meta(raw_confidence)
        meta["regime_label"] = regime_label
        return meta

    # ── Training ──────────────────────────────────────────────────────────

    @classmethod
    def fit(
        cls,
        regime_signals: Sequence,
        horizon_bars: int = 24,
        model_version: str = "",
        min_samples: int = MIN_SAMPLES_PLATT,
    ) -> "RegimeCalibrator":
        """Fit per-label calibrators from a sequence of RegimeSignals.

        Parameters
        ----------
        regime_signals :
            Ordered list of ``RegimeSignal`` objects (from
            ``BaselineRegimeEngine.classify_dataframe``).
        horizon_bars :
            A regime is considered "stable" if the same label appears at
            ``bar_index + horizon_bars``.  This defines the binary label.
        model_version :
            Optional version tag.
        min_samples :
            Minimum number of samples required to fit a calibrator per label.

        Returns
        -------
        RegimeCalibrator
            With per-label calibrators fitted where data permits.
        """
        version = model_version or time.strftime("%Y%m%d_%H%M%S")
        n = len(regime_signals)

        # Group raw confidences and stability labels per regime label
        from collections import defaultdict
        label_scores: dict[str, list[float]] = defaultdict(list)
        label_labels: dict[str, list[int]] = defaultdict(list)

        for i, sig in enumerate(regime_signals):
            future_idx = i + horizon_bars
            if future_idx >= n:
                break  # no label available for tail bars
            label_str = str(sig.label.value) if hasattr(sig.label, "value") else str(sig.label)
            # Skip UNKNOWN — not useful to calibrate
            if label_str == "UNKNOWN":
                continue

            future_sig = regime_signals[future_idx]
            future_label = str(future_sig.label.value) if hasattr(future_sig.label, "value") else str(future_sig.label)
            stability = 1 if label_str == future_label else 0

            label_scores[label_str].append(sig.confidence)
            label_labels[label_str].append(stability)

        # Fit one calibrator per label
        calibrators: dict[str, PlattCalibrator] = {}
        for label_str, scores in label_scores.items():
            labels = label_labels[label_str]
            cal = PlattCalibrator.fit(
                raw_confidences=scores,
                outcome_labels=labels,
                strategy_id=f"regime_{label_str}",
                model_version=version,
                min_samples=min_samples,
            )
            calibrators[label_str] = cal

        return cls(
            calibrators=calibrators,
            model_version=version,
            trained_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            horizon_bars=horizon_bars,
        )

    # ── Serialisation ─────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Serialise to a JSON-compatible dict."""
        return {
            "schema_version": "1",
            "type": "regime_calibrator",
            "model_version": self.model_version,
            "trained_at": self.trained_at,
            "horizon_bars": self.horizon_bars,
            "calibrators": {
                label: {
                    "A": cal.A,
                    "B": cal.B,
                    "n_samples": cal.n_samples,
                    "is_fitted": cal.is_fitted,
                    "calibration_method": cal.calibration_method,
                    "trained_at": cal.trained_at,
                    "_isotonic_xs": cal._isotonic_xs,
                    "_isotonic_ys": cal._isotonic_ys,
                }
                for label, cal in self.calibrators.items()
            },
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RegimeCalibrator":
        """Deserialise from a JSON-compatible dict."""
        cals: dict[str, PlattCalibrator] = {}
        for label, cd in d.get("calibrators", {}).items():
            cals[label] = PlattCalibrator(
                A=float(cd.get("A", 1.0)),
                B=float(cd.get("B", 0.0)),
                strategy_id=f"regime_{label}",
                model_version=d.get("model_version", ""),
                n_samples=int(cd.get("n_samples", 0)),
                is_fitted=bool(cd.get("is_fitted", False)),
                calibration_method=str(cd.get("calibration_method", "platt")),
                trained_at=str(cd.get("trained_at", "")),
                _isotonic_xs=list(cd.get("_isotonic_xs", [])),
                _isotonic_ys=list(cd.get("_isotonic_ys", [])),
            )
        return cls(
            calibrators=cals,
            model_version=str(d.get("model_version", "")),
            trained_at=str(d.get("trained_at", "")),
            horizon_bars=int(d.get("horizon_bars", 24)),
        )
