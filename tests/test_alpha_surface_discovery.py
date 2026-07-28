from __future__ import annotations

from copy import deepcopy

import pytest

from research.ml.validation.alpha_surface_discovery import (
    AlphaSurfaceDiscoveryValidationError,
    SCORE_DIMENSIONS,
    frozen_surface_inventory,
    priority_key,
    rank_surfaces,
    validate_inventory,
)
from scripts.run_alpha_surface_discovery import (
    OUTPUT_FILENAMES,
    _csv_bytes,
    _canonical_json,
    replay_digest,
    verify_lf_only,
)


def test_frozen_inventory_validates_and_is_deterministically_ordered() -> None:
    first = validate_inventory(frozen_surface_inventory())
    second = validate_inventory(list(reversed(frozen_surface_inventory())))

    assert first == second
    assert [row["surface_id"] for row in first] == sorted(
        row["surface_id"] for row in first
    )


def test_registered_candidate_a_001_is_present_once_without_duplicate_credit() -> None:
    inventory = validate_inventory(frozen_surface_inventory())
    registered = [row for row in inventory if row["surface_id"] == "S-001"]

    assert len(registered) == 1
    assert registered[0]["available_independence_count"] == 14
    assert "same five independent families" in registered[0][
        "known_overlap_or_redundancy"
    ]


def test_non_rankable_surfaces_remain_visible_without_scores() -> None:
    inventory = validate_inventory(frozen_surface_inventory())
    non_rankable = [row for row in inventory if not row["rankable"]]
    priorities = rank_surfaces(inventory)

    assert non_rankable
    assert all(row["non_rankable_reasons"] for row in non_rankable)
    assert all(row["scores"] == {} for row in non_rankable)
    assert {row["surface_id"] for row in priorities}.isdisjoint(
        {row["surface_id"] for row in non_rankable}
    )


def test_rankable_surface_requires_exact_frozen_score_dimensions() -> None:
    inventory = frozen_surface_inventory()
    inventory[0]["scores"].pop(SCORE_DIMENSIONS[0])

    with pytest.raises(
        AlphaSurfaceDiscoveryValidationError,
        match="scores must match frozen dimensions exactly",
    ):
        validate_inventory(inventory)


def test_non_rankable_surface_cannot_receive_scores() -> None:
    inventory = frozen_surface_inventory()
    target = next(row for row in inventory if not row["rankable"])
    target["scores"] = {dimension: 0 for dimension in SCORE_DIMENSIONS}

    with pytest.raises(
        AlphaSurfaceDiscoveryValidationError,
        match="non-rankable surface must not receive scores",
    ):
        validate_inventory(inventory)


def test_known_leakage_surface_fails_closed_and_remains_unrankable() -> None:
    inventory = validate_inventory(frozen_surface_inventory())
    recovery = next(row for row in inventory if row["surface_id"] == "S-007")

    assert recovery["leakage_state"] == "KNOWN_LOOK_AHEAD"
    assert recovery["rankable"] is False
    assert recovery["non_rankable_reasons"] == ["predictor leakage is known"]


def test_ranking_uses_frozen_tuple_and_does_not_mutate_inventory() -> None:
    inventory = frozen_surface_inventory()
    original = deepcopy(inventory)
    priorities = rank_surfaces(inventory)

    assert inventory == original
    assert priorities == sorted(priorities, key=priority_key)
    assert [row["rank"] for row in priorities] == list(
        range(1, len(priorities) + 1)
    )
    assert priorities[0]["surface_id"] == "S-002"


def test_equal_scores_fall_back_to_surface_id() -> None:
    inventory = frozen_surface_inventory()
    rankable = [row for row in inventory if row["rankable"]][:2]
    rankable[1]["scores"] = deepcopy(rankable[0]["scores"])
    rankable[1]["estimated_implementation_complexity"] = rankable[0][
        "estimated_implementation_complexity"
    ]

    priorities = rank_surfaces(rankable + [
        row for row in inventory if row["surface_id"] == "S-007"
    ])

    assert [row["surface_id"] for row in priorities] == sorted(
        row["surface_id"] for row in rankable
    )


def test_canonical_serializers_are_lf_only_and_stable() -> None:
    payload = [{"b": 2, "a": ["x", "y"]}]
    json_one = _canonical_json(payload)
    json_two = _canonical_json(deepcopy(payload))
    csv_one = _csv_bytes(payload, ("a", "b"))
    csv_two = _csv_bytes(deepcopy(payload), ("a", "b"))

    assert json_one == json_two
    assert csv_one == csv_two
    verify_lf_only({"inventory.json": json_one, "inventory.csv": csv_one})


def test_replay_digest_depends_on_all_frozen_outputs() -> None:
    outputs = {name: f"{name}\n".encode("utf-8") for name in OUTPUT_FILENAMES}
    first = replay_digest(outputs)
    mutated = dict(outputs)
    mutated[OUTPUT_FILENAMES[0]] = b"changed\n"

    assert first == replay_digest(dict(reversed(list(outputs.items()))))
    assert first != replay_digest(mutated)
