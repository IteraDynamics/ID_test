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


def _frame(
    reference: np.ndarray,
    observed: np.ndarray,
    threshold: float = 0.5,
    *,
    reference_labels: np.ndarray | None = None,
    observation_labels: np.ndarray | None = None,
) -> pd.DataFrame:
    values = np.concatenate([reference, observed])
    if reference_labels is None:
        reference_labels = (reference >= threshold).astype(int)
    if observation_labels is None:
        observation_labels = (observed >= threshold).astype(int)
    labels = np.concatenate([reference_labels, observation_labels])
    index = pd.date_range("2025-01-01", periods=len(values), freq="h")
    return pd.DataFrame(
        {
            "probability": values,
            "train_threshold": threshold,
            "label": labels,
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
    assert report.risk_score <= 2
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
    assert report.risk_score >= 6
    assert report.drift_detected is True
    assert "probability_mean_shift_high" in report.reasons


def test_psi_only_high_is_low_trust_severity() -> None:
    rng = np.random.default_rng(23)
    reference = np.clip(rng.beta(2.0, 8.0, 500), 0.0, 1.0)
    observed = np.clip(rng.beta(2.6, 10.4, 100), 0.0, 1.0)
    report = detect_drift(
        _frame(reference, observed, threshold=0.8),
        asset="BTC",
        model="medium_up",
        reference_rows=500,
        observation_rows=100,
        ks_med=1.0,
        mean_shift_med=10.0,
        exceedance_shift_med=1.0,
    )
    assert report.probability.psi >= 0.25
    assert report.reasons == ("probability_psi_high",)
    assert report.risk_score == 2
    assert report.severity == "LOW"


def test_threshold_collapse_combined_with_distribution_drift_is_high() -> None:
    rng = np.random.default_rng(31)
    reference = np.clip(rng.normal(0.58, 0.10, 500), 0.0, 1.0)
    observed = np.clip(rng.normal(0.42, 0.08, 100), 0.0, 1.0)
    report = detect_drift(
        _frame(reference, observed, threshold=0.55),
        asset="BTC",
        model="extended_up",
        reference_rows=500,
        observation_rows=100,
    )
    assert report.probability.exceedance_rate_shift >= 0.10
    assert "threshold_exceedance_shift_med" in report.reasons
    assert report.risk_score >= 6
    assert report.severity == "HIGH"


def test_outcome_deterioration_is_measured_against_reference() -> None:
    reference = np.full(500, 0.2)
    observed = np.full(100, 0.8)
    report = detect_drift(
        _frame(
            reference,
            observed,
            threshold=0.5,
            reference_labels=np.zeros(500, dtype=int),
            observation_labels=np.zeros(100, dtype=int),
        ),
        asset="ETH",
        model="extended_up",
        reference_rows=500,
        observation_rows=100,
    )
    assert report.outcomes.brier_deterioration is not None
    assert report.outcomes.brier_deterioration > 0.5
    assert "brier_deterioration_high" in report.reasons


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
    assert report.risk_score == 5
    assert report.severity == "MED"


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
