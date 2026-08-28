from __future__ import annotations

from datetime import datetime, timedelta

from research.campaign51_conditional_directional import candidate_inventory
from scripts.run_campaign51_development_validation import (
    ANCHOR_ORIGIN,
    DEVELOPMENT_END,
    DEVELOPMENT_START,
    EXECUTION_GO_COMMIT,
    HOLDOUT_START,
    VALIDATION_END,
    VALIDATION_START,
    stage_anchors,
)


def test_runner_identity_and_candidate_inventory() -> None:
    assert EXECUTION_GO_COMMIT == "e9eba6f7141851934fbe6a31b4f5c999493d7ab8"
    assert len(candidate_inventory()) == 12


def test_stage_anchors_are_weekly_and_stage_contained() -> None:
    development = stage_anchors(DEVELOPMENT_START, DEVELOPMENT_END)
    validation = stage_anchors(VALIDATION_START, VALIDATION_END)

    assert development[0] == ANCHOR_ORIGIN
    assert all(
        right - left == timedelta(hours=168)
        for left, right in zip(development, development[1:])
    )
    assert all(
        right - left == timedelta(hours=168)
        for left, right in zip(validation, validation[1:])
    )
    assert all(DEVELOPMENT_START <= value <= DEVELOPMENT_END for value in development)
    assert all(VALIDATION_START <= value <= VALIDATION_END for value in validation)
    assert all(value < HOLDOUT_START for value in development + validation)


def test_holdout_boundary_is_exact() -> None:
    assert HOLDOUT_START == datetime(2025, 1, 1, 0, 0, 0)
    assert VALIDATION_END < HOLDOUT_START
