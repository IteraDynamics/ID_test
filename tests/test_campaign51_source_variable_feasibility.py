from __future__ import annotations

from datetime import datetime, timedelta

from scripts.preflight_campaign51_source_variable_feasibility import (
    HORIZONS,
    PROPOSED_STAGES,
    exact_window_exists,
    stage_anchor_records,
)


def hourly(start: datetime, count: int) -> list[datetime]:
    return [start + timedelta(hours=index) for index in range(count)]


def test_exact_window_requires_every_timestamp() -> None:
    timestamps = set(hourly(datetime(2020, 1, 1), 10))
    assert exact_window_exists(
        timestamps,
        start=datetime(2020, 1, 1),
        end=datetime(2020, 1, 1, 9),
    )
    timestamps.remove(datetime(2020, 1, 1, 5))
    assert not exact_window_exists(
        timestamps,
        start=datetime(2020, 1, 1),
        end=datetime(2020, 1, 1, 9),
    )


def test_stage_records_are_timestamp_only_and_stage_contained() -> None:
    start = datetime(2018, 1, 1)
    end = datetime(2025, 12, 31)
    count = int((end - start).total_seconds() // 3600) + 1
    records = stage_anchor_records(hourly(start, count))
    assert len(records) == len(PROPOSED_STAGES) * len(HORIZONS)
    for record in records:
        assert record["stage_contained_endpoint_anchor_count"] <= record[
            "predictor_complete_anchor_count"
        ]
        if record["last_endpoint"] is not None:
            endpoint = datetime.fromisoformat(str(record["last_endpoint"]))
            assert endpoint <= PROPOSED_STAGES[str(record["stage"])][1]
