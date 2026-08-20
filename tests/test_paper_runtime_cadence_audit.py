"""Tests for the paper runtime cadence audit.

The audit's job is to measure how long after a source bar *closes* the live
runtime observes and decides on it. Its first version computed this from
`bar_timestamp` directly -- but `bar_timestamp` is a bar's *start* label, not
its close (`scripts/run_core_v1_paper_live.py`'s own `drop_incomplete_bars`
docstring: "a bar labeled T covers [T, T+bar_duration)"). That silently
overstated every reported lag by exactly the bar's own duration, and a
separate issue -- averaging in cycles that re-log an already-seen, unchanged
bar -- inflated the aggregate further for any sleeve coarser than the poll
interval. These tests pin the corrected behavior and include a regression
case demonstrating the exact bug the original version had.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_core_v1_paper_live import TIMEFRAME_DURATION as LIVE_RUNTIME_TIMEFRAME_DURATION
from scripts.run_paper_runtime_cadence_audit import TIMEFRAME_DURATION, build_report


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _market_row(cycle: int, sleeve: str, asset: str, timeframe: str, bar_start: str, observed: str) -> dict:
    return {
        "cycle": cycle,
        "sleeve": sleeve,
        "asset": asset,
        "timeframe": timeframe,
        "bar_timestamp": bar_start,
        "timestamp": observed,
    }


def _signal_row(cycle: int, observed: str) -> dict:
    return {"cycle": cycle, "timestamp": observed}


def _build(tmp_path: Path, market_rows: list[dict], signal_rows: list[dict], fill_rows: list[dict] | None = None):
    export_dir = tmp_path / "export"
    _write_jsonl(export_dir / "market_data.jsonl", market_rows)
    _write_jsonl(export_dir / "signals.jsonl", signal_rows)
    _write_jsonl(export_dir / "fills.jsonl", fill_rows or [])
    report, rows = build_report(export_dir, assumption_hours=1.0)
    return report, rows


# ------------------------------------------------------- bar-close arithmetic


def test_timeframe_duration_matches_live_runtime() -> None:
    """The audit's duplicated constant must never silently drift from the runtime's own."""
    assert TIMEFRAME_DURATION == LIVE_RUNTIME_TIMEFRAME_DURATION


def test_observe_age_measured_from_bar_close_not_bar_start(tmp_path: Path) -> None:
    """A 1H bar labeled 00:00 closes at 01:00. Observed at 01:05 -> lag is 5 minutes, not 65."""
    market_rows = [
        _market_row(1, "ETH_1H_trend", "ETH", "1H", "2024-01-01 00:00:00", "2024-01-01T01:05:00+00:00"),
    ]
    signal_rows = [_signal_row(1, "2024-01-01T01:05:00+00:00")]
    report, rows = _build(tmp_path, market_rows, signal_rows)

    assert rows[0]["bar_close_to_observation_hours"] == pytest.approx(5 / 60, abs=1e-6)
    stats = report["bar_close_to_observation_hours_by_sleeve_all_decisions"]["ETH_1H_trend"]
    assert stats["median"] == pytest.approx(5 / 60, abs=1e-3)


def test_reverting_to_bar_start_reproduces_the_original_bug(tmp_path: Path) -> None:
    """Canary: the old (bar_timestamp-only) formula must NOT match the corrected one.

    This proves the fix actually changed behavior rather than being a no-op --
    an audit correction that can't be shown to differ from the bug it fixes is
    not evidence the bug is fixed.
    """
    market_rows = [
        _market_row(1, "ETH_1H_trend", "ETH", "1H", "2024-01-01 00:00:00", "2024-01-01T01:05:00+00:00"),
    ]
    signal_rows = [_signal_row(1, "2024-01-01T01:05:00+00:00")]
    report, rows = _build(tmp_path, market_rows, signal_rows)

    corrected_lag_hours = rows[0]["bar_close_to_observation_hours"]

    # The original buggy computation: observed - bar_start, no duration added.
    from scripts.run_paper_runtime_cadence_audit import parse_ts

    bar_start = parse_ts("2024-01-01 00:00:00")
    observed = parse_ts("2024-01-01T01:05:00+00:00")
    buggy_lag_hours = (observed - bar_start).total_seconds() / 3600.0

    assert buggy_lag_hours == pytest.approx(1 + 5 / 60, abs=1e-6)
    assert corrected_lag_hours != pytest.approx(buggy_lag_hours, abs=1e-3)
    # The discrepancy is exactly the bar's own duration -- the bug's signature.
    assert buggy_lag_hours - corrected_lag_hours == pytest.approx(1.0, abs=1e-6)


def test_four_hour_bar_close_computed_correctly(tmp_path: Path) -> None:
    """A 4H bar labeled 00:00 closes at 04:00, not 00:00."""
    market_rows = [
        _market_row(1, "BTC_4H_trend", "BTC", "4H", "2024-01-01 00:00:00", "2024-01-01T04:10:00+00:00"),
    ]
    signal_rows = [_signal_row(1, "2024-01-01T04:10:00+00:00")]
    report, rows = _build(tmp_path, market_rows, signal_rows)
    assert rows[0]["bar_close_to_observation_hours"] == pytest.approx(10 / 60, abs=1e-6)


def test_unrecognized_timeframe_fails_closed(tmp_path: Path) -> None:
    """An unknown timeframe must raise, never silently default to zero duration."""
    market_rows = [
        _market_row(1, "MYSTERY_15M", "BTC", "15M", "2024-01-01 00:00:00", "2024-01-01T00:20:00+00:00"),
    ]
    signal_rows = [_signal_row(1, "2024-01-01T00:20:00+00:00")]
    with pytest.raises(ValueError, match="Unrecognized timeframe"):
        _build(tmp_path, market_rows, signal_rows)


# ------------------------------------------------------- fresh-bar-only vs all-decisions


def test_stale_relogs_inflate_all_decisions_but_not_fresh_pickup(tmp_path: Path) -> None:
    """A 4H bar re-logged across 4 hourly cycles: 'all decisions' sees growing staleness,
    'fresh bar only' sees just the one genuine pickup moment."""
    bar_start = "2024-01-01 00:00:00"  # closes at 04:00
    market_rows = [
        # Fresh pickup: 10 minutes after true close.
        _market_row(1, "BTC_4H_trend", "BTC", "4H", bar_start, "2024-01-01T04:10:00+00:00"),
        # Re-logged, same unchanged bar, growing older each cycle.
        _market_row(2, "BTC_4H_trend", "BTC", "4H", bar_start, "2024-01-01T05:10:00+00:00"),
        _market_row(3, "BTC_4H_trend", "BTC", "4H", bar_start, "2024-01-01T06:10:00+00:00"),
        _market_row(4, "BTC_4H_trend", "BTC", "4H", bar_start, "2024-01-01T07:10:00+00:00"),
    ]
    signal_rows = [_signal_row(c, r["timestamp"]) for c, r in zip([1, 2, 3, 4], market_rows)]
    report, rows = _build(tmp_path, market_rows, signal_rows)

    all_stats = report["bar_close_to_observation_hours_by_sleeve_all_decisions"]["BTC_4H_trend"]
    fresh_stats = report["bar_close_to_observation_hours_by_sleeve_fresh_bar_only"]["BTC_4H_trend"]

    assert all_stats["count"] == 4
    assert fresh_stats["count"] == 1
    assert fresh_stats["median"] == pytest.approx(10 / 60, abs=1e-3)  # summarize() rounds to 4dp
    # The all-decisions median is pulled up by the growing-stale re-logs.
    assert all_stats["median"] > fresh_stats["median"]

    assert rows[0]["first_sighting_of_this_bar"] is True
    assert rows[1]["first_sighting_of_this_bar"] is False
    assert rows[2]["first_sighting_of_this_bar"] is False
    assert rows[3]["first_sighting_of_this_bar"] is False


# ------------------------------------------------------- jump risk verdict


def test_jump_risk_verdict_reports_both_all_decisions_and_fresh_bar_only(tmp_path: Path) -> None:
    bar_start = "2024-01-01 00:00:00"
    market_rows = [
        _market_row(1, "ETH_1H_trend", "ETH", "1H", bar_start, "2024-01-01T01:05:00+00:00"),
        _market_row(2, "ETH_1H_trend", "ETH", "1H", "2024-01-01 01:00:00", "2024-01-01T02:05:00+00:00"),
    ]
    signal_rows = [_signal_row(1, "2024-01-01T01:05:00+00:00"), _signal_row(2, "2024-01-01T02:05:00+00:00")]
    report, rows = _build(tmp_path, market_rows, signal_rows)

    verdict = report["jump_risk_verdict"]["ETH"]
    assert verdict["observations_all_decisions"] == 2
    assert verdict["observations_fresh_bar_only"] == 2  # every bar here is a fresh pickup
    assert verdict["within_research_assumption_pct_fresh_bar_only"] == 100.0
    assert report["jump_risk_verdict"]["BTC"] == {"observations": 0, "verdict": "NO_DATA"}
