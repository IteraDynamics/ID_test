from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from research.ml.validation.drift_diagnosis import diagnose_stream


def _frame(
    reference_probability: np.ndarray,
    observation_probability: np.ndarray,
    *,
    threshold: float = 0.5,
    reference_label: np.ndarray | None = None,
    observation_label: np.ndarray | None = None,
    extra: dict[str, np.ndarray] | None = None,
) -> pd.DataFrame:
    probability = np.concatenate([reference_probability, observation_probability])
    data: dict[str, np.ndarray] = {
        "probability": probability,
        "train_threshold": np.full(len(probability), threshold),
    }
    if reference_label is not None and observation_label is not None:
        data["label"] = np.concatenate([reference_label, observation_label])
    if extra:
        data.update(extra)
    return pd.DataFrame(
        data,
        index=pd.date_range("2025-01-01", periods=len(probability), freq="h"),
    )


def test_regime_change_when_activation_collapses_with_broad_shift() -> None:
    reference = np.tile(np.array([0.42, 0.48, 0.52, 0.58]), 25)
    observation = np.tile(np.array([0.20, 0.24, 0.28, 0.32]), 6)
    reference_label = (reference >= 0.5).astype(int)
    observation_label = (observation >= 0.5).astype(int)
    report = diagnose_stream(
        _frame(
            reference,
            observation,
            reference_label=reference_label,
            observation_label=observation_label,
        ),
        asset="BTC",
        model="extended_up",
        reference_rows=100,
        observation_rows=24,
    )
    assert report.classification == "REGIME_CHANGE"
    assert report.reference.activation_rate == pytest.approx(0.5)
    assert report.observation.activation_rate == 0.0
    assert report.observation_only is True
    assert report.exposure_mutation_allowed is False


def test_threshold_mismatch_when_predictions_cluster_just_below_threshold() -> None:
    reference = np.tile(np.array([0.45, 0.49, 0.51, 0.55]), 25)
    observation = np.tile(np.array([0.481, 0.486, 0.491, 0.496]), 6)
    reference_label = (reference >= 0.5).astype(int)
    observation_label = np.zeros(24, dtype=int)
    report = diagnose_stream(
        _frame(
            reference,
            observation,
            reference_label=reference_label,
            observation_label=observation_label,
        ),
        asset="BTC",
        model="extended_up",
        reference_rows=100,
        observation_rows=24,
    )
    assert report.classification == "THRESHOLD_MISMATCH"
    assert report.threshold_distance.below_within_002 >= 0.5


def test_model_degradation_takes_priority_over_activation_explanation() -> None:
    reference = np.tile(np.array([0.10, 0.20, 0.80, 0.90]), 25)
    observation = np.tile(np.array([0.10, 0.20, 0.30, 0.40]), 6)
    reference_label = (reference >= 0.5).astype(int)
    observation_label = np.ones(24, dtype=int)
    report = diagnose_stream(
        _frame(
            reference,
            observation,
            reference_label=reference_label,
            observation_label=observation_label,
        ),
        asset="ETH",
        model="medium_up",
        reference_rows=100,
        observation_rows=24,
    )
    assert report.classification == "MODEL_DEGRADATION"
    assert report.observation.brier_score is not None
    assert report.reference.brier_score is not None
    assert report.observation.brier_score > report.reference.brier_score


def test_data_pipeline_suspect_when_recent_feature_missingness_jumps() -> None:
    reference = np.full(100, 0.4)
    observation = np.full(24, 0.4)
    feature = np.concatenate([np.ones(100), np.array([np.nan] * 12 + [1.0] * 12)])
    report = diagnose_stream(
        _frame(reference, observation, extra={"feature_x": feature}),
        asset="ETH",
        model="extended_up",
        reference_rows=100,
        observation_rows=24,
    )
    assert report.classification == "DATA_PIPELINE_SUSPECT"
    assert report.feature_comparisons["feature_x"].observation_missing_fraction == 0.5


def test_inconclusive_for_stable_stream() -> None:
    pattern = np.array([0.3, 0.4, 0.6, 0.7])
    reference = np.tile(pattern, 25)
    observation = np.tile(pattern, 6)
    report = diagnose_stream(
        _frame(reference, observation),
        asset="BTC",
        model="medium_up",
        reference_rows=100,
        observation_rows=24,
    )
    assert report.classification == "INCONCLUSIVE"
    assert len(report.digest) == 64


def test_invalid_history_is_rejected() -> None:
    frame = _frame(np.full(20, 0.4), np.full(10, 0.4))
    with pytest.raises(ValueError, match="Need at least"):
        diagnose_stream(
            frame,
            asset="BTC",
            model="medium_up",
            reference_rows=50,
            observation_rows=24,
        )
