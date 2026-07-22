from __future__ import annotations

import numpy as np
import pandas as pd

from research.ml.validation.drift_diagnosis_v2 import diagnose_stream_v2


def _prediction_frame(reference: np.ndarray, observation: np.ndarray, threshold: float = 0.5) -> pd.DataFrame:
    probability = np.concatenate([reference, observation])
    return pd.DataFrame(
        {
            "probability": probability,
            "train_threshold": np.full(len(probability), threshold),
        },
        index=pd.date_range("2025-01-01", periods=len(probability), freq="h"),
    )


def _evidence_frame(reference: np.ndarray, observation: np.ndarray, name: str = "feature_x") -> pd.DataFrame:
    values = np.concatenate([reference, observation])
    return pd.DataFrame(
        {name: values},
        index=pd.date_range("2025-01-01", periods=len(values), freq="h"),
    )


def test_without_external_evidence_remains_inconclusive() -> None:
    reference = np.tile(np.array([0.42, 0.48, 0.52, 0.58]), 25)
    observation = np.tile(np.array([0.20, 0.24, 0.28, 0.32]), 6)
    report = diagnose_stream_v2(
        _prediction_frame(reference, observation),
        asset="BTC",
        model="extended_up",
        reference_rows=100,
        observation_rows=24,
    )
    assert report.classification == "INCONCLUSIVE"
    assert report.evidence_sufficient is False
    assert report.observation_only is True
    assert report.exposure_mutation_allowed is False


def test_material_feature_shift_supports_regime_change() -> None:
    reference = np.tile(np.array([0.42, 0.48, 0.52, 0.58]), 25)
    observation = np.tile(np.array([0.20, 0.24, 0.28, 0.32]), 6)
    feature = _evidence_frame(np.tile(np.array([0.0, 0.1, 0.2, 0.3]), 25), np.full(24, 2.0))
    report = diagnose_stream_v2(
        _prediction_frame(reference, observation),
        asset="BTC",
        model="extended_up",
        reference_rows=100,
        observation_rows=24,
        feature_frame=feature,
    )
    assert report.classification == "REGIME_CHANGE"
    assert report.confidence in {"MED", "HIGH"}
    assert report.evidence_sufficient is True
    assert report.feature_evidence["feature_x"].standardized_mean_shift >= 0.5


def test_market_context_can_support_regime_change() -> None:
    reference = np.tile(np.array([0.42, 0.48, 0.52, 0.58]), 25)
    observation = np.tile(np.array([0.20, 0.24, 0.28, 0.32]), 6)
    context = _evidence_frame(np.tile(np.array([10.0, 11.0, 12.0, 13.0]), 25), np.full(24, 30.0), "realized_vol")
    report = diagnose_stream_v2(
        _prediction_frame(reference, observation),
        asset="BTC",
        model="extended_up",
        reference_rows=100,
        observation_rows=24,
        market_context_frame=context,
    )
    assert report.classification == "REGIME_CHANGE"
    assert "realized_vol" in report.market_context_evidence


def test_missingness_jump_is_pipeline_suspect() -> None:
    reference = np.tile(np.array([0.42, 0.48, 0.52, 0.58]), 25)
    observation = np.tile(np.array([0.20, 0.24, 0.28, 0.32]), 6)
    evidence_values = np.concatenate([np.ones(100), np.array([np.nan] * 12 + [1.0] * 12)])
    feature = pd.DataFrame(
        {"feature_x": evidence_values},
        index=pd.date_range("2025-01-01", periods=124, freq="h"),
    )
    report = diagnose_stream_v2(
        _prediction_frame(reference, observation),
        asset="BTC",
        model="extended_up",
        reference_rows=100,
        observation_rows=24,
        feature_frame=feature,
    )
    assert report.classification == "DATA_PIPELINE_SUSPECT"
    assert report.confidence == "HIGH"


def test_threshold_mismatch_does_not_require_external_evidence() -> None:
    reference = np.tile(np.array([0.45, 0.49, 0.51, 0.55]), 25)
    observation = np.tile(np.array([0.481, 0.486, 0.491, 0.496]), 6)
    report = diagnose_stream_v2(
        _prediction_frame(reference, observation),
        asset="BTC",
        model="extended_up",
        reference_rows=100,
        observation_rows=24,
    )
    assert report.classification == "THRESHOLD_MISMATCH"


def test_digest_is_deterministic() -> None:
    reference = np.tile(np.array([0.42, 0.48, 0.52, 0.58]), 25)
    observation = np.tile(np.array([0.20, 0.24, 0.28, 0.32]), 6)
    prediction = _prediction_frame(reference, observation)
    first = diagnose_stream_v2(
        prediction,
        asset="BTC",
        model="extended_up",
        reference_rows=100,
        observation_rows=24,
    )
    second = diagnose_stream_v2(
        prediction,
        asset="BTC",
        model="extended_up",
        reference_rows=100,
        observation_rows=24,
    )
    assert first.digest == second.digest
    assert len(first.digest) == 64
