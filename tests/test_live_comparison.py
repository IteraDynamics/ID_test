"""Synthetic validation for paper NAV extraction and the live comparison runner.

All fixtures are hand-constructed; no governed paper export or market data is
read. A full pass here is the synthetic PASS required before running the
comparison against a real paper export.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from research.live_benchmarks import LiveBenchmarkError, paper_daily_nav
from scripts.run_core_v1_live_comparison import load_benchmark_nav
from scripts.run_core_v1_live_comparison import main as comparison_main


def make_export(tmp_path: Path, events: list[dict[str, object]], *, as_csv: bool = False) -> Path:
    """Build the minimal export structure validate_export_structure() requires."""
    export_dir = tmp_path / "paper_export"
    export_dir.mkdir(parents=True, exist_ok=True)
    (export_dir / "manifest.json").write_text(
        json.dumps({"script_version": "test"}), encoding="utf-8"
    )
    (export_dir / "state.json").write_text(json.dumps({"last_total_nav": 1.0}), encoding="utf-8")
    (export_dir / "market_data.jsonl").write_text("", encoding="utf-8")
    (export_dir / "fills.jsonl").write_text("", encoding="utf-8")
    if as_csv:
        import csv as csv_module

        fieldnames = sorted({key for event in events for key in event})
        with (export_dir / "signals.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv_module.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            for event in events:
                writer.writerow(event)
    else:
        (export_dir / "signals.jsonl").write_text(
            "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8"
        )
    return export_dir


def nav_events(pairs: list[tuple[str, float | None]]) -> list[dict[str, object]]:
    return [{"timestamp": stamp, "total_nav": nav} for stamp, nav in pairs]


# ------------------------------------------------------- paper NAV extraction


def test_paper_daily_nav_takes_last_event_of_day(tmp_path: Path) -> None:
    export_dir = make_export(
        tmp_path,
        nav_events(
            [
                ("2026-07-07T01:00:00+00:00", 100_000.0),
                ("2026-07-07T23:00:00+00:00", 100_500.0),
                ("2026-07-08T12:00:00+00:00", 101_000.0),
            ]
        ),
    )
    assert paper_daily_nav(export_dir) == {
        date(2026, 7, 7): 100_500.0,
        date(2026, 7, 8): 101_000.0,
    }


def test_paper_daily_nav_csv_and_jsonl_agree(tmp_path: Path) -> None:
    events = nav_events([("2026-07-07T23:00:00+00:00", 100_500.0), ("2026-07-08T23:00:00+00:00", 99_000.0)])
    from_jsonl = paper_daily_nav(make_export(tmp_path / "a", events))
    from_csv = paper_daily_nav(make_export(tmp_path / "b", events, as_csv=True))
    assert from_jsonl == from_csv


def test_paper_daily_nav_skips_events_without_nav(tmp_path: Path) -> None:
    export_dir = make_export(
        tmp_path,
        nav_events(
            [
                ("2026-07-07T01:00:00+00:00", 100_000.0),
                ("2026-07-07T02:00:00+00:00", None),
                ("2026-07-08T01:00:00+00:00", 101_000.0),
            ]
        ),
    )
    # The null-NAV event does not overwrite the day's last real observation.
    assert paper_daily_nav(export_dir) == {
        date(2026, 7, 7): 100_000.0,
        date(2026, 7, 8): 101_000.0,
    }


def test_paper_daily_nav_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(LiveBenchmarkError, match="PAPER_EXPORT_FAILURE"):
        paper_daily_nav(tmp_path / "missing")

    no_nav = make_export(tmp_path / "empty", nav_events([("2026-07-07T01:00:00+00:00", None)]))
    with pytest.raises(LiveBenchmarkError, match="no usable total_nav"):
        paper_daily_nav(no_nav)

    negative = make_export(tmp_path / "neg", nav_events([("2026-07-07T01:00:00+00:00", -5.0)]))
    with pytest.raises(LiveBenchmarkError, match="non-positive total_nav"):
        paper_daily_nav(negative)

    unordered = make_export(
        tmp_path / "unordered",
        nav_events([("2026-07-08T01:00:00+00:00", 1.0), ("2026-07-07T01:00:00+00:00", 1.0)]),
    )
    with pytest.raises(LiveBenchmarkError, match="out of order"):
        paper_daily_nav(unordered)


# ------------------------------------------------------- benchmark artifact reader


def write_benchmark_dir(tmp_path: Path, series_a: list[tuple[str, float]], series_b: list[tuple[str, float]]) -> Path:
    benchmark_dir = tmp_path / "benchmarks"
    benchmark_dir.mkdir(parents=True, exist_ok=True)
    for filename, series in (("benchmark_a_nav.csv", series_a), ("benchmark_b_nav.csv", series_b)):
        body = "date,nav\n" + "".join(f"{day},{nav:.6f}\n" for day, nav in series)
        (benchmark_dir / filename).write_text(body, encoding="utf-8", newline="")
    return benchmark_dir


def test_load_benchmark_nav_fails_closed_on_bad_schema(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("day,value\n2026-07-07,1\n", encoding="utf-8", newline="")
    with pytest.raises(LiveBenchmarkError, match="unexpected schema"):
        load_benchmark_nav(path)
    with pytest.raises(LiveBenchmarkError, match="missing"):
        load_benchmark_nav(tmp_path / "nope.csv")


# ------------------------------------------------------- comparison runner


def test_comparison_runner_end_to_end(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Paper up 10%, Benchmark A up 5%, Benchmark B flat, over three days.

    Benchmark B has no 2026-07-08 row, so it must be carried forward at its
    2026-07-07 close for that date.
    """
    export_dir = make_export(
        tmp_path,
        nav_events(
            [
                ("2026-07-07T23:00:00+00:00", 200_000.0),
                ("2026-07-08T23:00:00+00:00", 210_000.0),
                ("2026-07-09T23:00:00+00:00", 220_000.0),
            ]
        ),
    )
    benchmark_dir = write_benchmark_dir(
        tmp_path,
        series_a=[("2026-07-07", 100_000.0), ("2026-07-08", 103_000.0), ("2026-07-09", 105_000.0)],
        series_b=[("2026-07-07", 100_000.0), ("2026-07-09", 100_000.0)],
    )
    out_dir = tmp_path / "out"

    argv = [
        "--paper-export", str(export_dir),
        "--benchmark-dir", str(benchmark_dir),
        "--out-dir", str(out_dir),
    ]
    assert comparison_main(argv) == 0
    output = capsys.readouterr().out
    assert "status: PASS" in output
    assert "paper_core_v1" in output

    metrics = json.loads((out_dir / "comparison_metrics.json").read_text(encoding="utf-8"))
    # Rebasing puts every series at 100,000 on day one.
    assert metrics["paper_core_v1"]["final_nav"] == pytest.approx(110_000.0)
    assert metrics["paper_core_v1"]["cumulative_return"] == pytest.approx(0.10)
    assert metrics["benchmark_a_static_twin"]["cumulative_return"] == pytest.approx(0.05)
    assert metrics["benchmark_b_60_40"]["cumulative_return"] == pytest.approx(0.0)
    assert metrics["paper_minus_benchmark_a_static_twin"]["cumulative_return_spread"] == pytest.approx(0.05)
    assert metrics["paper_minus_benchmark_b_60_40"]["cumulative_return_spread"] == pytest.approx(0.10)

    nav_csv = (out_dir / "comparison_nav.csv").read_bytes()
    assert b"\r" not in nav_csv
    rows = nav_csv.decode().strip().split("\n")
    assert rows[0] == "date,paper_nav,benchmark_a_nav,benchmark_b_nav"
    assert len(rows) == 4
    # Benchmark B carried forward on 07-08 -> unchanged from 07-07.
    assert rows[2].split(",")[3] == "100000.000000"

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["observations"] == 3
    assert manifest["runtime_modified"] is False
    assert set(manifest["benchmark_artifacts"]) == {"benchmark_a_nav.csv", "benchmark_b_nav.csv"}

    # Replay: a second invocation writes byte-identical artifacts.
    first = {p.name: p.read_bytes() for p in out_dir.iterdir()}
    assert comparison_main(argv) == 0
    assert {p.name: p.read_bytes() for p in out_dir.iterdir()} == first


def test_comparison_window_is_the_common_overlap(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    export_dir = make_export(
        tmp_path,
        nav_events(
            [
                ("2026-07-06T23:00:00+00:00", 100_000.0),
                ("2026-07-07T23:00:00+00:00", 101_000.0),
                ("2026-07-08T23:00:00+00:00", 102_000.0),
                ("2026-07-09T23:00:00+00:00", 103_000.0),
            ]
        ),
    )
    # Benchmarks start a day later and end a day earlier than the paper series.
    benchmark_dir = write_benchmark_dir(
        tmp_path,
        series_a=[("2026-07-07", 100_000.0), ("2026-07-08", 101_000.0)],
        series_b=[("2026-07-07", 100_000.0), ("2026-07-08", 100_500.0)],
    )
    out_dir = tmp_path / "out"
    assert comparison_main([
        "--paper-export", str(export_dir),
        "--benchmark-dir", str(benchmark_dir),
        "--out-dir", str(out_dir),
    ]) == 0
    capsys.readouterr()

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["comparison_start"] == "2026-07-07"
    assert manifest["comparison_end"] == "2026-07-08"
    assert manifest["observations"] == 2


def test_comparison_fails_closed_without_overlap(tmp_path: Path) -> None:
    export_dir = make_export(tmp_path, nav_events([("2026-09-01T23:00:00+00:00", 100_000.0)]))
    benchmark_dir = write_benchmark_dir(
        tmp_path,
        series_a=[("2026-07-07", 100_000.0)],
        series_b=[("2026-07-07", 100_000.0)],
    )
    with pytest.raises(LiveBenchmarkError, match="ALIGNMENT_FAILURE"):
        comparison_main([
            "--paper-export", str(export_dir),
            "--benchmark-dir", str(benchmark_dir),
            "--out-dir", str(tmp_path / "out"),
        ])
