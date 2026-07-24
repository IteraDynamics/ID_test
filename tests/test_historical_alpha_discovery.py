from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from research.ml.validation.historical_alpha_discovery import (
    HORIZON_HOURS,
    RANKABLE_DESCRIPTORS,
    HistoricalAlphaDiscoveryValidationError,
    build_forward_outcome,
    evidence_state,
    family_fold_assignments,
    homogeneous_family_value,
    rank_candidate_rows,
    validate_candidate_inventory,
    validate_price_series,
)
from scripts.run_core_v1_historical_alpha_discovery import (
    PRICE_COLUMNS,
    _reconstruct_and_validate_candidate_labels,
    _validate_exact_coverage,
    _validate_price_frame,
)


def _prices(periods: int = 200) -> pd.DataFrame:
    index = pd.date_range("2024-01-01 00:00:00", periods=periods, freq="1h")
    return pd.DataFrame({"close": [100.0 + index for index in range(periods)]}, index=index)


def _ohlcv(periods: int = 200) -> pd.DataFrame:
    timestamps = pd.date_range("2024-01-01 00:00:00", periods=periods, freq="1h")
    base = pd.Series([100.0 + index for index in range(periods)])
    return pd.DataFrame(
        {
            "timestamp": timestamps.strftime("%Y-%m-%d %H:%M:%S"),
            "open": base,
            "high": base + 2.0,
            "low": base - 2.0,
            "close": base + 1.0,
            "volume": 10.0,
        }
    )


def _price_spec(path: Path, frame: pd.DataFrame) -> dict[str, object]:
    return {
        "bytes": path.stat().st_size,
        "rows": len(frame),
        "columns": PRICE_COLUMNS,
        "first": str(frame.iloc[0]["timestamp"]),
        "last": str(frame.iloc[-1]["timestamp"]),
    }


def _families() -> list[dict[str, object]]:
    return [
        {
            "family_id": f"f{position:02d}",
            "window_start": f"2024-01-{position + 1:02d} 00:00:00",
            "window_end": f"2024-01-{position + 1:02d} 12:00:00",
        }
        for position in range(14)
    ]


def _coverage_frames(start: str = "2024-01-02 00:00:00") -> tuple[pd.DataFrame, pd.DataFrame]:
    anchors = pd.date_range(start, periods=14, freq="12h")
    membership = pd.DataFrame(
        {
            "family_id": [f"f{index:02d}" for index in range(14)],
            "episode_id": [f"e{index:03d}" for index in range(14)],
            "window_start": [
                (anchor - pd.Timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
                for anchor in anchors
            ],
            "window_end": [anchor.strftime("%Y-%m-%d %H:%M:%S") for anchor in anchors],
        }
    )
    episodes = membership[["window_start", "window_end"]].copy()
    return episodes, membership


def _candidate_reconstruction_frames() -> tuple[
    dict[str, object], pd.DataFrame, pd.DataFrame, pd.DataFrame
]:
    historical = {
        "config": {
            "collapse_ratio": 0.50,
            "observation_rows": 24,
        }
    }
    episodes = pd.DataFrame(
        [
            {
                "window_start": "2024-01-01 00:00:00",
                "window_end": "2024-01-02 00:00:00",
                "reference_activation_rate": 0.20,
                "observation_activation_rate": 0.03,
                "activation_ratio": 0.15,
                "feature_cosine_similarity_to_latest": 0.0,
                "recovered_without_retraining": False,
                "recovery_rows": None,
            }
        ]
    )
    signatures = pd.DataFrame(
        [
            {
                "episode_id": 0,
                "atr_proxy": 0.25,
                "ret_1": 0.10,
                "distance_sma_fast": -0.20,
                "volume_z": 0.15,
            }
        ]
    )
    membership = pd.DataFrame(
        [
            {
                "episode_id": 0,
                "intrinsic_subtype": (
                    "MAJOR_COLLAPSE__LOW_DISPLACEMENT_COLLAPSE__VOLATILITY_NEUTRAL"
                ),
            }
        ]
    )
    return historical, episodes, signatures, membership


def test_frozen_candidate_inventory_accepts_only_exact_rankable_fields() -> None:
    assert validate_candidate_inventory(reversed(RANKABLE_DESCRIPTORS)) == RANKABLE_DESCRIPTORS

    with pytest.raises(HistoricalAlphaDiscoveryValidationError, match="look-ahead"):
        validate_candidate_inventory((*RANKABLE_DESCRIPTORS, "recovery_outcome"))

    with pytest.raises(HistoricalAlphaDiscoveryValidationError, match="match the frozen"):
        validate_candidate_inventory(RANKABLE_DESCRIPTORS[:-1])


def test_price_series_requires_exact_close_and_strict_positive_finite_values() -> None:
    prices = _prices()
    close = validate_price_series(prices)
    assert close.name == "close"
    assert len(close) == len(prices)

    with pytest.raises(HistoricalAlphaDiscoveryValidationError, match="exact close"):
        validate_price_series(prices.rename(columns={"close": "price"}))

    invalid = prices.copy()
    invalid.iloc[0, 0] = 0.0
    with pytest.raises(HistoricalAlphaDiscoveryValidationError, match="strictly positive"):
        validate_price_series(invalid)


def test_r1_price_frame_requires_exact_ordered_schema_and_ohlcv_integrity(tmp_path: Path) -> None:
    frame = _ohlcv()
    path = tmp_path / "btc.csv"
    frame.to_csv(path, index=False, lineterminator="\n")
    close, evidence = _validate_price_frame(path, _price_spec(path, frame))
    assert len(close) == len(frame)
    assert evidence["ordered_schema"] == list(PRICE_COLUMNS)
    assert evidence["timestamp_discontinuity_count"] == 0

    reordered = frame[["timestamp", "close", "open", "high", "low", "volume"]]
    reordered_path = tmp_path / "reordered.csv"
    reordered.to_csv(reordered_path, index=False, lineterminator="\n")
    with pytest.raises(HistoricalAlphaDiscoveryValidationError, match="ordered schema"):
        _validate_price_frame(reordered_path, _price_spec(reordered_path, reordered))

    invalid_high = frame.copy()
    invalid_high.loc[0, "high"] = invalid_high.loc[0, "low"]
    invalid_path = tmp_path / "invalid_high.csv"
    invalid_high.to_csv(invalid_path, index=False, lineterminator="\n")
    with pytest.raises(HistoricalAlphaDiscoveryValidationError, match="high is inconsistent"):
        _validate_price_frame(invalid_path, _price_spec(invalid_path, invalid_high))


def test_r1_price_frame_fails_on_duplicate_or_non_hour_aligned_timestamp(tmp_path: Path) -> None:
    duplicate = _ohlcv()
    duplicate.loc[1, "timestamp"] = duplicate.loc[0, "timestamp"]
    duplicate_path = tmp_path / "duplicate.csv"
    duplicate.to_csv(duplicate_path, index=False, lineterminator="\n")
    with pytest.raises(HistoricalAlphaDiscoveryValidationError, match="duplicate timestamps"):
        _validate_price_frame(duplicate_path, _price_spec(duplicate_path, duplicate))

    misaligned = _ohlcv()
    misaligned.loc[1, "timestamp"] = "2024-01-01 01:30:00"
    misaligned_path = tmp_path / "misaligned.csv"
    misaligned.to_csv(misaligned_path, index=False, lineterminator="\n")
    with pytest.raises(HistoricalAlphaDiscoveryValidationError, match="hour-aligned"):
        _validate_price_frame(misaligned_path, _price_spec(misaligned_path, misaligned))


def test_r1_exact_coverage_allows_unrelated_gap_but_rejects_affected_window() -> None:
    full_index = pd.date_range("2024-01-01 00:00:00", periods=500, freq="1h")
    full_close = pd.Series(range(100, 600), index=full_index, dtype=float, name="close")
    episodes, membership = _coverage_frames("2024-01-02 00:00:00")

    episodes["window_start"] = pd.to_datetime(
        episodes["window_start"]
    ).dt.strftime("%Y-%m-%dT%H:%M:%S")
    episodes["window_end"] = pd.to_datetime(
        episodes["window_end"]
    ).dt.strftime("%Y-%m-%dT%H:%M:%S")

    unrelated_gap = full_close.drop(pd.Timestamp("2024-01-01 05:00:00"))
    coverage = _validate_exact_coverage(unrelated_gap, episodes, membership)
    assert coverage["episode"]["unavailable_by_horizon"] == {
        "2": 0,
        "6": 0,
        "24": 0,
        "72": 0,
        "168": 0,
    }
    assert coverage["family"]["unavailable_by_horizon"] == {
        "2": 0,
        "6": 0,
        "24": 0,
        "72": 0,
        "168": 0,
    }

    affected = full_close.drop(pd.Timestamp("2024-01-02 01:00:00"))
    with pytest.raises(HistoricalAlphaDiscoveryValidationError, match="horizon coverage"):
        _validate_exact_coverage(affected, episodes, membership)


def test_candidate_labels_reconstruct_and_reconcile_to_membership() -> None:
    historical, episodes, signatures, membership = _candidate_reconstruction_frames()
    classified, evidence = _reconstruct_and_validate_candidate_labels(
        historical, episodes, signatures, membership
    )

    assert classified.loc[0, "collapse_severity"] == "MAJOR_COLLAPSE"
    assert classified.loc[0, "feature_displacement"] == "LOW_DISPLACEMENT_COLLAPSE"
    assert classified.loc[0, "volatility_state"] == "VOLATILITY_NEUTRAL"
    assert classified.loc[0, "intrinsic_subtype"] == membership.loc[0, "intrinsic_subtype"]
    assert evidence["episode_count"] == 1
    assert evidence["intrinsic_subtype_mismatch_count"] == 0
    assert evidence["episode_id_rule"] == "zero_based_governed_episode_csv_row_position"


def test_candidate_label_reconstruction_fails_closed_on_membership_mismatch() -> None:
    historical, episodes, signatures, membership = _candidate_reconstruction_frames()
    membership.loc[0, "intrinsic_subtype"] = (
        "SEVERE_COLLAPSE__BROAD_SHIFT__VOLATILITY_EXPANSION"
    )

    with pytest.raises(
        HistoricalAlphaDiscoveryValidationError,
        match="intrinsic_subtype does not reconcile",
    ):
        _reconstruct_and_validate_candidate_labels(
            historical, episodes, signatures, membership
        )


def test_forward_outcome_uses_exact_hourly_path_without_lookahead_fill() -> None:
    close = validate_price_series(_prices())
    result = build_forward_outcome(
        close,
        anchor="2024-01-01 00:00:00",
        horizon_hours=2,
    )
    assert result is not None
    assert result.forward_return == pytest.approx(0.02)
    assert result.maximum_favorable_excursion == pytest.approx(0.02)
    assert result.maximum_adverse_excursion == pytest.approx(0.01)
    assert result.positive_return is True

    missing = close.drop(pd.Timestamp("2024-01-01 01:00:00"))
    assert build_forward_outcome(
        missing,
        anchor="2024-01-01 00:00:00",
        horizon_hours=2,
    ) is None

    with pytest.raises(HistoricalAlphaDiscoveryValidationError, match="unauthorized horizon"):
        build_forward_outcome(close, anchor="2024-01-01", horizon_hours=3)


def test_frozen_horizons_are_exact() -> None:
    assert HORIZON_HOURS == (2, 6, 24, 72, 168)


def test_family_folds_are_fixed_expanding_and_outcome_independent() -> None:
    records = family_fold_assignments(list(reversed(_families())))
    fold_zero_train = [
        row["family_id"] for row in records
        if row["fold_id"] == 0 and row["role"] == "train"
    ]
    fold_zero_test = [
        row["family_id"] for row in records
        if row["fold_id"] == 0 and row["role"] == "test"
    ]
    assert fold_zero_train == ["f00", "f01", "f02", "f03", "f04"]
    assert fold_zero_test == ["f05", "f06", "f07"]

    fold_two_train = [
        row["family_id"] for row in records
        if row["fold_id"] == 2 and row["role"] == "train"
    ]
    fold_two_test = [
        row["family_id"] for row in records
        if row["fold_id"] == 2 and row["role"] == "test"
    ]
    assert fold_two_train == [f"f{position:02d}" for position in range(11)]
    assert fold_two_test == ["f11", "f12", "f13"]


def test_family_candidate_value_is_homogeneous_only() -> None:
    assert homogeneous_family_value(["A", "A", "A"]) == "A"
    assert homogeneous_family_value(["A", "B", "A"]) is None


def test_evidence_states_fail_closed_in_frozen_order() -> None:
    base = {
        "outcome_available": True,
        "episode_support": 8,
        "family_support": 4,
        "supported_fold_count": 2,
        "episode_median_return": 0.1,
        "family_median_return": 0.1,
        "training_test_agreement_count": 2,
        "aggregate_direction_agreement_count": 2,
    }
    assert evidence_state(**base) == "SUPPORTED_ASSOCIATION"
    assert evidence_state(**{**base, "family_median_return": 0.0}) == "NULL_ASSOCIATION"
    assert evidence_state(**{**base, "training_test_agreement_count": 1}) == "UNSTABLE_OOS"
    assert evidence_state(**{**base, "family_median_return": -0.1}) == "CONTRADICTORY_RESOLUTION"
    assert evidence_state(**{**base, "family_support": 2}) == "INSUFFICIENT_SUPPORT"
    assert evidence_state(**{**base, "outcome_available": False}) == "OUTCOME_UNAVAILABLE"


def test_candidate_ranking_is_deterministic_and_state_first() -> None:
    rows = [
        {
            "evidence_state": "INSUFFICIENT_SUPPORT",
            "supported_fold_count": 3,
            "training_test_direction_agreement_count": 3,
            "aggregate_direction_agreement_count": 3,
            "family_support": 10,
            "family_median_forward_return": 0.9,
            "horizon_hours": 2,
            "descriptor": "volatility_state",
            "candidate_value": "A",
        },
        {
            "evidence_state": "SUPPORTED_ASSOCIATION",
            "supported_fold_count": 2,
            "training_test_direction_agreement_count": 2,
            "aggregate_direction_agreement_count": 2,
            "family_support": 3,
            "family_median_forward_return": 0.02,
            "horizon_hours": 24,
            "descriptor": "collapse_severity",
            "candidate_value": "B",
        },
        {
            "evidence_state": "SUPPORTED_ASSOCIATION",
            "supported_fold_count": 3,
            "training_test_direction_agreement_count": 3,
            "aggregate_direction_agreement_count": 3,
            "family_support": 4,
            "family_median_forward_return": -0.01,
            "horizon_hours": 6,
            "descriptor": "feature_displacement",
            "candidate_value": "C",
        },
    ]
    first = rank_candidate_rows(rows)
    second = rank_candidate_rows(list(reversed(rows)))
    assert first == second
    assert [row["candidate_value"] for row in first] == ["C", "B", "A"]
