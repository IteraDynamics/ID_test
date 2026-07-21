from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from research.ml.validation.drift_persistence import (
    classify_persistence,
    evaluate_persistence,
)


def _frame(reference: np.ndarray, windows: list[np.ndarray], threshold: float = 0.5) -> pd.DataFrame:
    values = np.concatenate([reference, *windows])
    labels = (values >= threshold).astype(int)
    index = pd.date_range("2025-01-01", periods=len(values), freq="h")
    return pd.DataFrame(
        {
            "probability": values,
            "train_threshold": threshold,
            "label": labels,
        },
        index=index,
    )


def test_classify_persistence_states() -> None:
    assert classify_persistence(("LOW",)) == "STABLE"
    assert classify_persistence(("LOW", "HIGH")) == "HIGH_TRANSIENT"
    assert classify_persistence(("HIGH", "HIGH")) == "HIGH_PERSISTENT"
    assert classify_persistence(("LOW", "MED")) == "MED_TRANSIENT"
    assert classify_persistence(("MED", "MED")) == "MED_PERSISTENT"
    assert classify_persistence(("HIGH", "LOW")) == "RECOVERED"


def test_high_requires_consecutive_windows_for_persistence() -> None:
    reference = np.full(100, 0.2)
    high_one = np.full(24, 0.8)
    high_two = np.full(24, 0.8)
    report, assessment = evaluate_persistence(
        _frame(reference, [high_one, high_two]),
        asset="BTC",
        model="extended_up",
        reference_rows=100,
        observation_rows=24,
        requested_windows=2,
    )
    assert report.severity == "HIGH"
    assert assessment.state == "HIGH_PERSISTENT"
    assert assessment.persistence_breaches == 2
    assert assessment.evaluated_windows == 2
    assert assessment.persistence_sufficient is True
    assert assessment.window_severities == ("HIGH", "HIGH")


def test_single_available_high_is_transient_and_history_limited() -> None:
    reference = np.full(100, 0.2)
    observed = np.full(24, 0.8)
    report, assessment = evaluate_persistence(
        _frame(reference, [observed]),
        asset="BTC",
        model="extended_up",
        reference_rows=100,
        observation_rows=24,
        requested_windows=3,
    )
    assert report.severity == "HIGH"
    assert assessment.state == "HIGH_TRANSIENT"
    assert assessment.evaluated_windows == 1
    assert assessment.requested_windows == 3
    assert assessment.persistence_sufficient is False


def test_recovery_is_detected() -> None:
    rng = np.random.default_rng(17)
    reference = np.clip(rng.normal(0.2, 0.03, 100), 0.0, 1.0)
    high = np.clip(rng.normal(0.8, 0.03, 24), 0.0, 1.0)
    recovered = np.clip(rng.normal(0.2, 0.03, 24), 0.0, 1.0)
    report, assessment = evaluate_persistence(
        _frame(reference, [high, recovered]),
        asset="ETH",
        model="extended_up",
        reference_rows=100,
        observation_rows=24,
        requested_windows=2,
    )
    assert report.severity == "LOW"
    assert assessment.state == "RECOVERED"
    assert assessment.window_severities[0] == "HIGH"
    assert assessment.window_severities[-1] == "LOW"


def test_invalid_persistence_configuration_is_rejected() -> None:
    frame = _frame(np.full(100, 0.2), [np.full(24, 0.2)])
    with pytest.raises(ValueError, match="requested_windows"):
        evaluate_persistence(
            frame,
            asset="BTC",
            model="medium_up",
            reference_rows=100,
            observation_rows=24,
            requested_windows=0,
        )
