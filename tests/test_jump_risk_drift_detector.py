from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from research.ml.validation.drift_detector import (
    aggregate_severity,
    detect_drift,
    ks_statistic,
    population_stability_index,
)


def _frame(reference: np.ndarray, observed: np.ndarray, threshold: float = 0.5) -> pd.DataFrame:
    values = np.concatenate([reference, observed])
    index = pd.date_range("2025-01-01", periods=len(values), freq="h")
    return pd.DataFrame(
        {
            "probability": values,
            "train_threshold": threshold,
            "label": (values >= threshold).astype(int),
        },
        index=index,
    )


def test_stable_probability_stream_is_low_severity() -> None:
    rng = np.random.default_rng(7)
    reference = np.clip(rng.normal(0.35, 0.08, 500), 0.0, 1.0)
    observed = np.clip(rng.normal(0.35, 0.08, 100), 0.0, 1.0)
    report = detect_drift(
        _frame(reference, observed),
        asset="BTC",
        model="medium_up",
        reference_rows=500,
        observation_rows=100,
    )
    assert report.severity == "LOW"
    assert report.drift_detected is False
    assert report.digest == detect_drift(
        _frame(reference, observed),
        asset="BTC",
        model="medium_up",
        reference_rows=500,
        observation_rows=100,
    ).digest


def test_large_probability_shift_is_high_severity() -> None:
    rng = np.random.default_rng(11)
    reference = np.clip(rng.normal(0.25, 0.04, 500), 0.0, 1.0)
    observed = np.clip(rng.normal(0.65, 0.04, 100), 0.0, 1.0)
    report = detect_drift(
        _frame(reference, observed),
        asset="ETH",
        model="extended_up",
        reference_rows=500,
        observation_rows=100,
    )
    assert report.severity == "HIGH"
    assert report.drift_detected is True
    assert "probability_mean_shift_high" in report.reasons


def test_low_probability_level_alone_is_not_drift() -> None:
    reference = np.full(500, 0.03)
    observed = np.full(100, 0.03)
    report = detect_drift(
        _frame(reference, observed, threshold=0.08),
        asset="BTC",
        model="medium_up",
        reference_rows=500,
        observation_rows=100,
    )
    assert report.severity == "LOW"


def test_invalid_probability_is_rejected() -> None:
    frame = _frame(np.full(500, 0.2), np.full(100, 0.2))
    frame.iloc[-1, frame.columns.get_loc("probability")] = 1.2
    with pytest.raises(ValueError, match="outside"):
        detect_drift(
            frame,
            asset="BTC",
            model="medium_up",
            reference_rows=500,
            observation_rows=100,
        )


def test_duplicate_timestamps_are_rejected() -> None:
    frame = _frame(np.full(500, 0.2), np.full(100, 0.2))
    index = list(frame.index)
    index[-1] = index[-2]
    frame.index = pd.DatetimeIndex(index)
    with pytest.raises(ValueError, match="unique and increasing"):
        detect_drift(
            frame,
            asset="BTC",
            model="medium_up",
            reference_rows=500,
            observation_rows=100,
        )


def test_feature_shift_is_reported_in_standardized_units() -> None:
    probabilities = _frame(np.full(500, 0.2), np.full(100, 0.2))
    reference_features = pd.DataFrame({"realized_vol": np.linspace(0.0, 1.0, 500)})
    observation_features = pd.DataFrame({"realized_vol": np.linspace(3.0, 4.0, 100)})
    report = detect_drift(
        probabilities,
        asset="BTC",
        model="medium_up",
        reference_rows=500,
        observation_rows=100,
        reference_features=reference_features,
        observation_features=observation_features,
    )
    assert report.feature_drifts["realized_vol"].standardized_mean_shift > 2.0
    assert report.severity == "HIGH"


def test_distribution_helpers_are_zero_for_identical_samples() -> None:
    sample = np.linspace(0.0, 1.0, 100)
    assert population_stability_index(sample, sample) == pytest.approx(0.0)
    assert ks_statistic(sample, sample) == pytest.approx(0.0)


def test_aggregate_severity_uses_worst_report() -> None:
    low = detect_drift(
        _frame(np.full(500, 0.2), np.full(100, 0.2)),
        asset="BTC",
        model="medium_up",
        reference_rows=500,
        observation_rows=100,
    )
    high = detect_drift(
        _frame(np.full(500, 0.2), np.full(100, 0.8)),
        asset="ETH",
        model="extended_up",
        reference_rows=500,
        observation_rows=100,
    )
    assert aggregate_severity([low, high]) == "HIGH"
