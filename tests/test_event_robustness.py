from __future__ import annotations

import copy

import pandas as pd
import pytest

from research.ml.validation.event_robustness import (
    EventRobustnessValidationError,
    build_event_robustness,
    validate_governed_inputs,
)


def _membership() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"family_id": "f0", "family_ordinal": 0, "episode_id": 0, "member_ordinal": 0,
             "intrinsic_subtype": "A", "recovery_outcome": "FAST"},
            {"family_id": "f0", "family_ordinal": 0, "episode_id": 1, "member_ordinal": 1,
             "intrinsic_subtype": "A", "recovery_outcome": "SLOW"},
            {"family_id": "f0", "family_ordinal": 0, "episode_id": 2, "member_ordinal": 2,
             "intrinsic_subtype": "B", "recovery_outcome": "SLOW"},
            {"family_id": "f1", "family_ordinal": 1, "episode_id": 3, "member_ordinal": 0,
             "intrinsic_subtype": "A", "recovery_outcome": "FAST"},
        ]
    )


def _families() -> list[dict[str, object]]:
    return [
        {
            "family_id": "f0", "family_ordinal": 0, "episode_ids": [0, 1, 2],
            "episode_count": 3, "intrinsic_subtype_counts": {"A": 2, "B": 1},
            "intrinsic_subtype_mixed": True,
            "recovery_outcome_counts": {"FAST": 1, "SLOW": 2},
            "recovery_outcome_mixed": True,
        },
        {
            "family_id": "f1", "family_ordinal": 1, "episode_ids": [3],
            "episode_count": 1, "intrinsic_subtype_counts": {"A": 1},
            "intrinsic_subtype_mixed": False,
            "recovery_outcome_counts": {"FAST": 1},
            "recovery_outcome_mixed": False,
        },
    ]


def _build() -> dict[str, object]:
    return build_event_robustness(
        _membership(), _families(),
        source_artifacts={"families": "a.json", "membership": "b.csv"},
    )


def test_builds_threshold_free_episode_and_family_views() -> None:
    result = _build()
    assert result["episode_count"] == 4
    assert result["event_family_count"] == 2
    assert result["counting_rules"]["mixed_family_dominant_label_inference"] is False

    subtype = {record["label"]: record for record in result["intrinsic_subtype"]}
    assert subtype["A"]["episode_count"] == 3
    assert subtype["A"]["event_family_presence_count"] == 2
    assert subtype["A"]["event_family_homogeneous_count"] == 1
    assert subtype["A"]["episode_amplification_ratio"] == 1.5
    assert subtype["B"]["episode_count"] == 1
    assert subtype["B"]["event_family_presence_count"] == 1
    assert subtype["B"]["event_family_homogeneous_count"] == 0


def test_mixed_families_are_not_forced_to_dominant_label() -> None:
    result = _build()
    recovery = {record["label"]: record for record in result["recovery_outcome"]}
    assert recovery["SLOW"]["event_family_presence_count"] == 1
    assert recovery["SLOW"]["event_family_homogeneous_count"] == 0
    assert result["family_composition"] == {
        "intrinsic_subtype_homogeneous": 1,
        "intrinsic_subtype_mixed": 1,
        "recovery_outcome_homogeneous": 1,
        "recovery_outcome_mixed": 1,
    }


def test_replay_is_identical_and_input_order_is_canonicalized() -> None:
    first = _build()
    membership = _membership().iloc[::-1].reset_index(drop=True)
    families = list(reversed(_families()))
    second = build_event_robustness(
        membership, families,
        source_artifacts={"membership": "b.csv", "families": "a.json"},
    )
    assert first == second


def test_fails_closed_on_duplicate_episode_membership() -> None:
    membership = _membership()
    membership.loc[3, "episode_id"] = 2
    with pytest.raises(EventRobustnessValidationError, match="duplicate episode_id"):
        validate_governed_inputs(membership, _families())


def test_fails_closed_on_family_count_disagreement() -> None:
    families = copy.deepcopy(_families())
    families[0]["intrinsic_subtype_counts"] = {"A": 3, "B": 1}
    with pytest.raises(EventRobustnessValidationError, match="subtype counts do not reconcile"):
        validate_governed_inputs(_membership(), families)


def test_fails_closed_on_mixed_flag_disagreement() -> None:
    families = copy.deepcopy(_families())
    families[0]["intrinsic_subtype_mixed"] = False
    with pytest.raises(EventRobustnessValidationError, match="intrinsic mixed flag"):
        validate_governed_inputs(_membership(), families)


def test_fails_closed_on_membership_label_disagreement() -> None:
    membership = _membership()
    membership.loc[0, "intrinsic_subtype"] = "B"
    with pytest.raises(EventRobustnessValidationError, match="membership subtype counts disagree"):
        validate_governed_inputs(membership, _families())
