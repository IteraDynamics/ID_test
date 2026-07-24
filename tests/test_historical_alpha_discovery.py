from __future__ import annotations

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


def _prices(periods: int = 200) -> pd.DataFrame:
    index = pd.date_range("2024-01-01 00:00:00", periods=periods, freq="1h")
    return pd.DataFrame({"close": [100.0 + index for index in range(periods)]}, index=index)


def _families() -> list[dict[str, object]]:
    return [
        {
            "family_id": f"f{position:02d}",
            "window_start": f"2024-01-{position + 1:02d} 00:00:00",
            "window_end": f"2024-01-{position + 1:02d} 12:00:00",
        }
        for position in range(14)
    ]


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
