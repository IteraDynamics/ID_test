from __future__ import annotations

import copy
import json

import pandas as pd
import pytest

from research.ml.validation.historical_regime_taxonomy import build_summary, classify_episodes
from scripts.run_core_v1_historical_regime_taxonomy import _strict_json_records


def _episodes() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "episode_id": 2,
                "window_start": "2024-02-01",
                "window_end": "2024-02-29",
                "reference_activation_rate": 0.5,
                "observation_activation_rate": 0.05,
                "activation_ratio": 0.10,
                "feature_cosine_similarity_to_latest": 0.75,
                "recovered_without_retraining": True,
                "recovery_rows": 720,
            },
            {
                "episode_id": 1,
                "window_start": "2024-01-01",
                "window_end": "2024-01-31",
                "reference_activation_rate": 0.5,
                "observation_activation_rate": 0.1,
                "activation_ratio": 0.20,
                "feature_cosine_similarity_to_latest": 0.40,
                "recovered_without_retraining": False,
                "recovery_rows": None,
            },
        ]
    )


def _signatures() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "atr_14": [1.5, 0.0],
            "realized_vol_24": [1.0, 0.0],
            "feature_a": [2.5, 2.0],
            "feature_b": [0.0, 0.0],
        },
        index=pd.Index([2, 1], name="episode_id"),
    )


def test_thresholds_and_broad_shift_precedence() -> None:
    result = classify_episodes(
        _episodes(), _signatures(), collapse_ratio=0.35, observation_rows=720
    ).set_index("episode_id")

    assert result.loc[2, "collapse_severity"] == "SEVERE_COLLAPSE"
    assert result.loc[1, "collapse_severity"] == "MAJOR_COLLAPSE"
    assert result.loc[2, "feature_displacement"] == "BROAD_SHIFT"
    assert result.loc[2, "volatility_state"] == "VOLATILITY_EXPANSION"
    assert result.loc[2, "recovery_outcome"] == "RAPID_RECOVERY"
    assert result.loc[1, "similarity_band"] == "MEDIUM_SIMILARITY"


def test_concentrated_shift_when_fewer_than_quarter_shifted() -> None:
    episodes = _episodes().iloc[[0]].copy()
    signatures = pd.DataFrame(
        [[2.1, 0.0, 0.0, 0.0, 0.0]],
        index=pd.Index([2], name="episode_id"),
        columns=["feature_a", "b", "c", "d", "e"],
    )
    result = classify_episodes(
        episodes, signatures, collapse_ratio=0.35, observation_rows=720
    )

    assert result.loc[0, "shifted_feature_fraction"] == pytest.approx(0.2)
    assert result.loc[0, "feature_displacement"] == "CONCENTRATED_SHIFT"
    assert result.loc[0, "volatility_state"] == "VOLATILITY_UNAVAILABLE"


def test_recovery_validation_fails_closed() -> None:
    recovered_without_rows = _episodes().iloc[[0]].copy()
    recovered_without_rows.loc[:, "recovery_rows"] = float("nan")
    with pytest.raises(ValueError, match="requires positive recovery_rows"):
        classify_episodes(
            recovered_without_rows,
            _signatures().loc[[2]],
            collapse_ratio=0.35,
            observation_rows=720,
        )

    persistent_with_rows = _episodes().iloc[[1]].copy()
    persistent_with_rows.loc[:, "recovery_rows"] = 100
    with pytest.raises(ValueError, match="must have null recovery_rows"):
        classify_episodes(
            persistent_with_rows,
            _signatures().loc[[1]],
            collapse_ratio=0.35,
            observation_rows=720,
        )


def test_classification_preserves_inputs_and_orders_deterministically() -> None:
    episodes = _episodes()
    signatures = _signatures()
    episodes_before = episodes.copy(deep=True)
    signatures_before = signatures.copy(deep=True)

    result = classify_episodes(
        episodes, signatures, collapse_ratio=0.35, observation_rows=720
    )

    pd.testing.assert_frame_equal(episodes, episodes_before)
    pd.testing.assert_frame_equal(signatures, signatures_before)
    assert result["episode_id"].tolist() == [1, 2]


def test_strict_json_records_normalizes_missing_scalars() -> None:
    episodes = _episodes()
    episodes["recovery_rate"] = [0.75, float("nan")]

    classified = classify_episodes(
        episodes,
        _signatures(),
        collapse_ratio=0.35,
        observation_rows=720,
    )
    records = _strict_json_records(classified)
    records_by_id = {record["episode_id"]: record for record in records}

    assert records_by_id[1]["recovery_rate"] is None
    assert records_by_id[2]["recovery_rate"] == pytest.approx(0.75)
    json.dumps(records, sort_keys=True, allow_nan=False)


def test_summary_is_deterministic_and_sorted() -> None:
    classified = classify_episodes(
        _episodes(), _signatures(), collapse_ratio=0.35, observation_rows=720
    )
    kwargs = {
        "config": {"observation_rows": 720, "collapse_ratio": 0.35},
        "latest_window": {"window_end": "2026-07-01"},
        "source_artifacts": {"signatures": "b.csv", "episodes": "a.csv"},
    }

    first = build_summary(classified, **copy.deepcopy(kwargs))
    second = build_summary(
        classified.sample(frac=1.0, random_state=7), **copy.deepcopy(kwargs)
    )

    assert first == second
    assert list(first["counts"]["collapse_severity"]) == sorted(
        first["counts"]["collapse_severity"]
    )
    assert first["matched_volatility_features"] == ["atr_14", "realized_vol_24"]
