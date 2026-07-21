from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.export_core_v1_jump_risk_evidence import (
    PREDICTION_COLUMNS,
    _assert_prediction_parity,
    _split_shifted_output,
)


def _combined() -> pd.DataFrame:
    index = pd.date_range("2025-01-01", periods=4, freq="h")
    return pd.DataFrame(
        {
            "probability": [0.10, 0.20, 0.30, 0.40],
            "label": [0, 1, 0, 1],
            "train_threshold": [0.80, 0.80, 0.85, 0.85],
            "test_year": [2025, 2025, 2025, 2025],
            "feature_a": [10.0, 20.0, 30.0, 40.0],
            "feature_b": [1.0, 2.0, 3.0, 4.0],
        },
        index=index,
    )


def test_prediction_and_features_receive_identical_one_bar_shift() -> None:
    prediction, evidence = _split_shifted_output(_combined(), ["feature_a", "feature_b"])

    assert prediction.index.equals(evidence.index)
    assert prediction["probability"].tolist() == [0.10, 0.20, 0.30]
    assert prediction["train_threshold"].tolist() == [0.80, 0.80, 0.85]
    assert evidence["feature_a"].tolist() == [10.0, 20.0, 30.0]
    assert evidence["feature_b"].tolist() == [1.0, 2.0, 3.0]


def test_existing_label_semantics_are_not_shifted() -> None:
    prediction, _ = _split_shifted_output(_combined(), ["feature_a", "feature_b"])

    assert prediction["label"].tolist() == [1, 0, 1]
    assert prediction["test_year"].tolist() == [2025, 2025, 2025]


def test_parity_accepts_identical_numeric_frames() -> None:
    prediction, _ = _split_shifted_output(_combined(), ["feature_a", "feature_b"])
    expected = prediction.copy()

    _assert_prediction_parity(expected, prediction, "btc_medium_up")


def test_parity_rejects_probability_change() -> None:
    prediction, _ = _split_shifted_output(_combined(), ["feature_a", "feature_b"])
    expected = prediction.copy()
    expected.loc[expected.index[-1], "probability"] += 1e-5

    with pytest.raises(RuntimeError, match="parity failed for probability"):
        _assert_prediction_parity(expected, prediction, "btc_medium_up")


def test_parity_rejects_index_change() -> None:
    prediction, _ = _split_shifted_output(_combined(), ["feature_a", "feature_b"])
    expected = prediction.iloc[:-1].copy()

    with pytest.raises(RuntimeError, match="prediction index mismatch"):
        _assert_prediction_parity(expected, prediction, "btc_medium_up")


def test_prediction_column_contract_is_stable() -> None:
    prediction, _ = _split_shifted_output(_combined(), ["feature_a", "feature_b"])

    assert prediction.columns.tolist() == PREDICTION_COLUMNS
    assert np.isfinite(prediction[["probability", "train_threshold"]].to_numpy()).all()
