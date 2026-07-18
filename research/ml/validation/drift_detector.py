"""ML validation — lightweight drift detection for probabilities and features.

Grok collab addition for high-ROI monitoring of jump edge stability.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class DriftMetrics:
    """Summary of detected drift."""
    ewma_prob: float
    cusum_stat: float
    drift_detected: bool
    severity: str  # LOW/MED/HIGH
    feature_drifts: Dict[str, float]


def compute_ewma(series: pd.Series, alpha: float = 0.1) -> float:
    """Simple EWMA for recent value."""
    if len(series) == 0:
        return 0.0
    return float(series.ewm(alpha=alpha, adjust=False).mean().iloc[-1])


def cusum_change_detection(series: pd.Series, threshold: float = 3.0) -> tuple[float, bool]:
    """Basic CUSUM for shift detection."""
    if len(series) < 10:
        return 0.0, False
    mean = series.mean()
    cusum = 0.0
    max_cusum = 0.0
    for val in series:
        cusum = max(0, cusum + (val - mean))
        max_cusum = max(max_cusum, cusum)
    detected = max_cusum > threshold
    return max_cusum, detected


def detect_drift(
    probs: pd.Series,
    features: pd.DataFrame | None = None,
    window: int = 50,
    prob_threshold: float = 0.05,
) -> DriftMetrics:
    """Detect drift in jump probabilities and key features."""
    recent = probs.iloc[-window:] if len(probs) > window else probs
    ewma_p = compute_ewma(recent)
    cusum, shift = cusum_change_detection(recent)

    feature_drifts = {}
    if features is not None:
        recent_feat = features.iloc[-window:]
        for col in features.columns[:5]:  # top few
            if col in recent_feat:
                drift = abs(recent_feat[col].mean() - features[col].mean())
                feature_drifts[col] = float(drift)

    severity = "LOW"
    if shift or ewma_p < prob_threshold:
        severity = "HIGH" if cusum > 5.0 else "MED"

    return DriftMetrics(
        ewma_prob=float(ewma_p),
        cusum_stat=float(cusum),
        drift_detected=shift or ewma_p < prob_threshold,
        severity=severity,
        feature_drifts=feature_drifts,
    )

# Example integration stub
def add_drift_to_metrics(result, probs_series):
    """Hook for BacktestResult or paper telemetry."""
    drift = detect_drift(probs_series)
    return {"drift": drift}
