"""Compare live Core v1 paper NAV against the pre-registered benchmarks.

Joins the paper runtime's exported NAV series (from
``scripts/export_core_v1_paper_data.py``) against the governed benchmark
artifacts produced by ``scripts/run_core_v1_live_benchmarks.py``, and reports
all three series under identical metric definitions.

Benchmark NAV series are read from their canonical artifacts, never
recomputed here: those artifacts and their digests are the governed identity.

Observation-only. No runtime, strategy, order, NAV, exposure, or production
behavior is modified.
"""

from __future__ import annotations

# Preserve direct-file execution; package imports use normal discovery.
if __package__ in (None, ""):
    try:
        from _checkout_bootstrap import bootstrap as _bootstrap_checkout
    except ModuleNotFoundError as _bootstrap_error:
        if _bootstrap_error.name != "_checkout_bootstrap":
            raise
        from scripts._checkout_bootstrap import bootstrap as _bootstrap_checkout
    _bootstrap_checkout(__file__)


import argparse
import csv
import hashlib

import json
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

from research.live_benchmarks import (
    REGISTERED_STARTING_CAPITAL,
    LiveBenchmarkError,
    _last_close_on_or_before,
    canonical_csv_bytes,
    canonical_json_bytes,
    compute_series_metrics,
    paper_daily_nav,
    sha256_file,
)

BENCHMARK_FILES = {
    "benchmark_a_static_twin": "benchmark_a_nav.csv",
    "benchmark_b_60_40": "benchmark_b_nav.csv",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Compare live paper NAV against the registered Core v1 benchmarks.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--paper-export", required=True, help="Paper export directory copied from the runtime host.")
    p.add_argument("--benchmark-dir", default="artifacts/core_v1_live_benchmarks")
    p.add_argument("--out-dir", default="artifacts/core_v1_live_comparison")
    p.add_argument("--start", default=None, help="Optional first comparison date (default: latest common start).")
    p.add_argument("--end", default=None, help="Optional last comparison date (default: earliest common end).")
    p.add_argument("--starting-capital", type=float, default=REGISTERED_STARTING_CAPITAL)
    return p.parse_args(argv)


def load_benchmark_nav(path: Path) -> dict[date, float]:
    if not path.exists():
        raise LiveBenchmarkError(f"BENCHMARK_ARTIFACT_FAILURE: missing {path.name}")
    series: dict[date, float] = {}
    previous: date | None = None
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != ("date", "nav"):
            raise LiveBenchmarkError(f"BENCHMARK_ARTIFACT_FAILURE: unexpected schema in {path.name}")
        for row_number, row in enumerate(reader, start=2):
            try:
                session = date.fromisoformat(row["date"])
                nav = float(row["nav"])
            except (TypeError, ValueError) as exc:
                raise LiveBenchmarkError(
                    f"BENCHMARK_ARTIFACT_FAILURE: {path.name}:{row_number}"
                ) from exc
            if previous is not None and session <= previous:
                raise LiveBenchmarkError(f"BENCHMARK_ARTIFACT_FAILURE: {path.name}:{row_number} out of order")
            series[session] = nav
            previous = session
    if not series:
        raise LiveBenchmarkError(f"BENCHMARK_ARTIFACT_FAILURE: {path.name} has no rows")
    return series


def _compute_artifacts(args: argparse.Namespace) -> tuple[dict[str, bytes], list[str]]:
    export_dir = Path(args.paper_export)
    benchmark_dir = Path(args.benchmark_dir)

    paper = paper_daily_nav(export_dir)
    benchmarks = {
        name: load_benchmark_nav(benchmark_dir / filename)
        for name, filename in sorted(BENCHMARK_FILES.items())
    }

    latest_start = max([min(paper)] + [min(series) for series in benchmarks.values()])
    earliest_end = min([max(paper)] + [max(series) for series in benchmarks.values()])
    start = date.fromisoformat(args.start) if args.start else latest_start
    end = date.fromisoformat(args.end) if args.end else earliest_end
    if start > end:
        raise LiveBenchmarkError(
            f"ALIGNMENT_FAILURE: no overlapping window (start {start.isoformat()} > end {end.isoformat()})"
        )

    # The paper series defines the comparison calendar; benchmarks are valued at
    # their last close on or before each paper date.
    dates = [session for session in sorted(paper) if start <= session <= end]
    if not dates:
        raise LiveBenchmarkError("ALIGNMENT_FAILURE: no paper observations inside the comparison window")

    aligned = {
        name: [_last_close_on_or_before(series, session, name) for session in dates]
        for name, series in benchmarks.items()
    }
    paper_nav = [paper[session] for session in dates]

    # Rebase every series to the same starting capital so the comparison is not
    # distorted by differing first-observation values.
    def rebased(values: list[float]) -> list[float]:
        base = values[0]
        return [args.starting_capital * value / base for value in values]

    series_nav = {"paper_core_v1": rebased(paper_nav)}
    for name, values in aligned.items():
        series_nav[name] = rebased(values)

    metrics = {
        name: compute_series_metrics(name, dates, values, args.starting_capital)
        for name, values in sorted(series_nav.items())
    }
    for name in sorted(BENCHMARK_FILES):
        paper_metrics = metrics["paper_core_v1"]
        metrics[f"paper_minus_{name}"] = {
            "cumulative_return_spread": round(
                float(paper_metrics["cumulative_return"]) - float(metrics[name]["cumulative_return"]), 8
            ),
            "max_drawdown_spread": round(
                float(paper_metrics["max_drawdown"]) - float(metrics[name]["max_drawdown"]), 8
            ),
        }

    rows = []
    for index, session in enumerate(dates):
        rows.append(
            {
                "date": session.isoformat(),
                "paper_nav": f"{series_nav['paper_core_v1'][index]:.6f}",
                "benchmark_a_nav": f"{series_nav['benchmark_a_static_twin'][index]:.6f}",
                "benchmark_b_nav": f"{series_nav['benchmark_b_60_40'][index]:.6f}",
            }
        )

    manifest = {
        "registration_document": "docs/research/CORE_V1_LIVE_BENCHMARK_REGISTRATION.md",
        "paper_export_dir": str(export_dir).replace("\\", "/"),
        "paper_export_manifest_sha256": (
            sha256_file(export_dir / "manifest.json") if (export_dir / "manifest.json").exists() else None
        ),
        "benchmark_artifacts": {
            filename: sha256_file(benchmark_dir / filename)
            for filename in sorted(BENCHMARK_FILES.values())
            if (benchmark_dir / filename).exists()
        },
        "comparison_start": dates[0].isoformat(),
        "comparison_end": dates[-1].isoformat(),
        "observations": len(dates),
        "starting_capital": args.starting_capital,
        "rebased_to_common_start": True,
        "runtime_modified": False,
        "paper_record_modified": False,
    }

    artifacts = {
        "comparison_nav.csv": canonical_csv_bytes(
            ("date", "paper_nav", "benchmark_a_nav", "benchmark_b_nav"), rows
        ),
        "comparison_metrics.json": canonical_json_bytes(metrics),
        "manifest.json": canonical_json_bytes(manifest),
    }
    return artifacts, _summary_lines(metrics, dates)


def _summary_lines(metrics: dict[str, dict[str, object]], dates: list[date]) -> list[str]:
    header = f"{'series':<26}{'final NAV':>14}{'return':>10}{'max DD':>10}"
    lines = [
        f"window: {dates[0].isoformat()} .. {dates[-1].isoformat()} ({len(dates)} observations)",
        header,
        "-" * len(header),
    ]
    for name in ("paper_core_v1", "benchmark_a_static_twin", "benchmark_b_60_40"):
        row = metrics[name]
        lines.append(
            f"{name:<26}{float(row['final_nav']):>14,.2f}"
            f"{float(row['cumulative_return']) * 100:>9.2f}%"
            f"{float(row['max_drawdown']) * 100:>9.2f}%"
        )
    for name in ("benchmark_a_static_twin", "benchmark_b_60_40"):
        spread = metrics[f"paper_minus_{name}"]
        lines.append(
            f"paper minus {name}: "
            f"return {float(spread['cumulative_return_spread']) * 100:+.2f} pp, "
            f"drawdown {float(spread['max_drawdown_spread']) * 100:+.2f} pp"
        )
    return lines


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    first_pass, summary = _compute_artifacts(args)
    second_pass, _ = _compute_artifacts(args)
    for name in first_pass:
        if first_pass[name] != second_pass[name]:
            raise LiveBenchmarkError(f"REPLAY_IDENTITY_FAILURE: {name}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("status: PASS (replay identity verified across two in-memory passes)")
    for line in summary:
        print(line)
    print()
    for name, payload in first_pass.items():
        (out_dir / name).write_bytes(payload)
        print(f"{name}: sha256 {hashlib.sha256(payload).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
