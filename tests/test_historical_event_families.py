from __future__ import annotations

from hashlib import sha256
import json

import numpy as np
import pandas as pd
import pytest

from research.ml.validation.historical_event_families import (
    EventFamilyValidationError,
    build_event_families,
    insert_episode_ids,
    reconcile_source_and_classified,
    validate_prediction_timestamps,
)

SOURCE_ARTIFACT = "artifacts/core_v1_jump_risk_historical_regimes/btc_extended_up_historical_episodes.csv"


def _prediction_index() -> pd.DatetimeIndex:
    return pd.date_range("2024-01-01 00:00:00", periods=16, freq="h")


def _classified() -> pd.DataFrame:
    common = {
        "reference_activation_rate": 0.5,
        "observation_activation_rate": 0.1,
        "activation_ratio": 0.2,
        "recovered_without_retraining": True,
        "recovery_rows": 2,
    }
    return pd.DataFrame([
        {
            **common,
            "episode_id": 2,
            "window_start": "2024-01-01 09:00:00",
            "window_end": "2024-01-01 10:00:00",
            "feature_cosine_similarity_to_latest": 0.2,
            "collapse_severity": "MAJOR_COLLAPSE",
            "feature_displacement": "BROAD_SHIFT",
            "volatility_state": "VOLATILITY_EXPANSION",
            "recovery_outcome": "PERSISTENT_COLLAPSE",
        },
        {
            **common,
            "episode_id": 0,
            "window_start": "2024-01-01 00:00:00",
            "window_end": "2024-01-01 02:00:00",
            "feature_cosine_similarity_to_latest": 0.4,
            "collapse_severity": "SEVERE_COLLAPSE",
            "feature_displacement": "BROAD_SHIFT",
            "volatility_state": "VOLATILITY_EXPANSION",
            "recovery_outcome": "RAPID_RECOVERY",
        },
        {
            **common,
            "episode_id": 1,
            "window_start": "2024-01-01 03:00:00",
            "window_end": "2024-01-01 05:00:00",
            "feature_cosine_similarity_to_latest": 0.8,
            "collapse_severity": "MAJOR_COLLAPSE",
            "feature_displacement": "CONCENTRATED_SHIFT",
            "volatility_state": "VOLATILITY_NEUTRAL",
            "recovery_outcome": "DELAYED_RECOVERY",
        },
    ])


def _source() -> pd.DataFrame:
    classified = _classified().sort_values("episode_id", kind="mergesort")
    return classified[[
        "window_start", "window_end", "reference_activation_rate",
        "observation_activation_rate", "activation_ratio",
        "feature_cosine_similarity_to_latest", "recovered_without_retraining",
        "recovery_rows",
    ]].reset_index(drop=True)


def _build(episodes: pd.DataFrame | None = None):
    return build_event_families(
        _classified() if episodes is None else episodes,
        prediction_timestamps=_prediction_index(),
        source_artifact=SOURCE_ARTIFACT,
        bar_cadence="PT1H",
    )


def test_episode_identity_and_reconciliation_are_exact() -> None:
    source = _source()
    inserted = insert_episode_ids(source)
    assert inserted["episode_id"].tolist() == [0, 1, 2]
    pd.testing.assert_frame_equal(reconcile_source_and_classified(source, _classified()), _classified())

    changed = _classified().copy()
    changed.loc[changed["episode_id"] == 1, "activation_ratio"] = 0.25
    with pytest.raises(EventFamilyValidationError, match="governed field disagreement"):
        reconcile_source_and_classified(source, changed)


def test_grouping_is_canonical_transitive_and_gap_aware() -> None:
    extra = _classified().iloc[[0]].copy()
    extra.loc[:, "episode_id"] = 3
    extra.loc[:, "window_start"] = "2024-01-01 05:00:00"
    extra.loc[:, "window_end"] = "2024-01-01 07:00:00"
    episodes = pd.concat([_classified(), extra], ignore_index=True)

    membership, families = _build(episodes)

    assert [family["episode_ids"] for family in families] == [[0, 1, 3], [2]]
    assert membership["episode_id"].tolist() == [0, 1, 3, 2]
    assert families[0]["duration_bars"] == 8


def test_exact_one_hour_adjacency_joins_but_larger_gap_splits() -> None:
    episodes = _classified().query("episode_id in [0, 1]").copy()
    _, joined = _build(episodes)
    assert len(joined) == 1

    episodes.loc[episodes["episode_id"] == 1, "window_start"] = "2024-01-01 04:00:00"
    _, split = _build(episodes)
    assert len(split) == 2


def test_input_order_does_not_change_outputs() -> None:
    membership_a, families_a = _build(_classified())
    membership_b, families_b = _build(_classified().sample(frac=1.0, random_state=7))
    pd.testing.assert_frame_equal(membership_a, membership_b)
    assert families_a == families_b


def test_family_identity_matches_strict_canonical_payload() -> None:
    _, families = _build(_classified().query("episode_id in [0, 1]"))
    payload = {
        "bar_cadence": "PT1H",
        "episode_ids": [0, 1],
        "family_end": "2024-01-01T05:00:00",
        "family_start": "2024-01-01T00:00:00",
        "source_artifact": SOURCE_ARTIFACT,
        "specification_version": "1",
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    assert families[0]["family_id"] == sha256(canonical.encode("utf-8")).hexdigest()


def test_composition_similarity_and_latest_tie_breaking() -> None:
    episodes = _classified().query("episode_id in [0, 1]").copy()
    episodes.loc[:, "window_start"] = "2024-01-01 00:00:00"
    episodes.loc[:, "window_end"] = "2024-01-01 05:00:00"
    _, families = _build(episodes)
    family = families[0]

    assert family["intrinsic_subtype_mixed"] is True
    assert family["recovery_outcome_mixed"] is True
    assert family["latest_episode_id"] == 1
    assert family["latest_episode_similarity_to_current"] == pytest.approx(0.8)
    assert family["maximum_similarity_to_current"] == pytest.approx(0.8)
    assert family["median_similarity_to_current"] == pytest.approx(0.6)
    assert list(family["intrinsic_subtype_counts"]) == sorted(family["intrinsic_subtype_counts"])


def test_prediction_timestamp_validation_preserves_missing_bar_gaps() -> None:
    timestamps = list(_prediction_index())
    del timestamps[6:9]
    assert len(validate_prediction_timestamps(timestamps, bar_cadence="PT1H")) == 13

    irregular = [pd.Timestamp("2024-01-01 00:00:00"), pd.Timestamp("2024-01-01 01:30:00")]
    with pytest.raises(EventFamilyValidationError, match="integer multiples"):
        validate_prediction_timestamps(irregular, bar_cadence="PT1H")


def test_timestamp_cadence_identity_and_similarity_fail_closed() -> None:
    duplicate_timestamps = list(_prediction_index()) + [_prediction_index()[-1]]
    with pytest.raises(EventFamilyValidationError, match="duplicate prediction"):
        validate_prediction_timestamps(duplicate_timestamps, bar_cadence="PT1H")

    malformed = _classified().copy()
    malformed.loc[0, "window_start"] = "not-a-timestamp"
    with pytest.raises(EventFamilyValidationError, match="malformed"):
        _build(malformed)

    reversed_interval = _classified().copy()
    reversed_interval.loc[0, "window_start"] = "2024-01-01 11:00:00"
    with pytest.raises(EventFamilyValidationError, match="must not precede"):
        _build(reversed_interval)

    absent_boundary = _classified().copy()
    absent_boundary.loc[0, "window_end"] = "2024-01-01 10:30:00"
    with pytest.raises(EventFamilyValidationError, match="boundary absent"):
        _build(absent_boundary)

    duplicate_ids = _classified().copy()
    duplicate_ids.loc[0, "episode_id"] = 1
    with pytest.raises(EventFamilyValidationError, match="duplicate episode"):
        _build(duplicate_ids)

    nonfinite = _classified().copy()
    nonfinite.loc[0, "feature_cosine_similarity_to_latest"] = np.inf
    with pytest.raises(EventFamilyValidationError, match="must be finite"):
        _build(nonfinite)


def test_outputs_are_complete_once_and_strict_json() -> None:
    membership, families = _build()
    assert membership["episode_id"].is_unique
    assert sorted(membership["episode_id"].tolist()) == [0, 1, 2]
    json.dumps(families, sort_keys=True, separators=(",", ":"), allow_nan=False)
    assert all(record["research_only"] for record in families)
    assert all(record["observation_only"] for record in families)
    assert all(not record["runtime_integration_allowed"] for record in families)
    assert all(not record["exposure_mutation_allowed"] for record in families)
