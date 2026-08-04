from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from scripts.preflight_campaign52_sources_calendar import (
    Campaign52PreflightError,
    choose_timestamp_column,
    complete_block_facts,
    infer_cadence_seconds,
    lag_mapping_facts,
    parse_timestamp,
    stage_coverage_facts,
)


def test_parse_timestamp_supported_formats() -> None:
    expected = datetime(2024, 1, 2, 3, 4, 5)
    assert parse_timestamp("2024-01-02 03:04:05") == expected
    assert parse_timestamp("2024-01-02T03:04:05Z") == expected


def test_choose_timestamp_column_is_case_insensitive() -> None:
    assert choose_timestamp_column(("Date", "Open", "Close")) == "Date"
    assert choose_timestamp_column(("timestamp", "close")) == "timestamp"


def test_choose_timestamp_column_fails_closed() -> None:
    with pytest.raises(Campaign52PreflightError, match="TIMESTAMP_COLUMN_NOT_FOUND"):
        choose_timestamp_column(("open", "close"))


def test_infer_cadence_prefers_modal_positive_interval() -> None:
    start = datetime(2024, 1, 1)
    timestamps = [
        start,
        start + timedelta(hours=1),
        start + timedelta(hours=2),
        start + timedelta(hours=4),
    ]
    assert infer_cadence_seconds(timestamps) == 3600


def test_stage_coverage_is_exact_for_hourly_sources() -> None:
    facts = stage_coverage_facts(
        datetime(2018, 1, 1),
        datetime(2025, 12, 31, 0, 0, 0),
        3600,
    )
    assert facts["development"] is True
    assert facts["validation"] is False


def test_stage_coverage_allows_trading_calendar_edge_for_daily_sources() -> None:
    facts = stage_coverage_facts(
        datetime(2018, 1, 2),
        datetime(2025, 12, 30),
        86400,
    )
    assert facts == {"development": True, "validation": True}


def test_stage_coverage_still_fails_large_daily_gap() -> None:
    facts = stage_coverage_facts(
        datetime(2018, 1, 2),
        datetime(2025, 12, 20),
        86400,
    )
    assert facts["validation"] is False


def test_complete_block_facts_are_stage_contained() -> None:
    facts = complete_block_facts(
        datetime(2020, 1, 1),
        datetime(2022, 12, 31, 23, 59, 59),
    )
    assert facts["block_days"] == 28
    assert facts["complete_block_count"] == 39
    assert facts["terminal_remainder_days"] == 4.0


def test_lag_mapping_requires_exact_timestamp_and_no_boundary_carry() -> None:
    start = datetime(2024, 1, 1)
    timestamps = [start + timedelta(hours=i) for i in range(700)]
    facts = lag_mapping_facts(timestamps, start, timestamps[-1])
    assert facts["24h"]["exact_mapping_count"] == 676
    assert facts["24h"]["uncovered_count"] == 24
    assert facts["168h"]["exact_mapping_count"] == 532
    assert facts["168h"]["uncovered_count"] == 168
    assert facts["672h"]["exact_mapping_count"] == 28
    assert facts["672h"]["uncovered_count"] == 672


def test_lag_mapping_does_not_nearest_match_missing_timestamp() -> None:
    start = datetime(2024, 1, 1)
    timestamps = [start + timedelta(hours=i) for i in range(30)]
    timestamps.remove(start + timedelta(hours=5))
    facts = lag_mapping_facts(timestamps, start, start + timedelta(hours=29))
    # Six stage timestamps have a nominal 24h predecessor; the hour-29 mapping
    # is absent because hour 5 is missing, leaving five exact mappings.
    assert facts["24h"]["exact_mapping_count"] == 5
