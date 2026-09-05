from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Sequence

# Keep standalone script execution working until the separate packaging migration.
import sys as _artifact_sys
from pathlib import Path as _ArtifactPath
if str(_ArtifactPath(__file__).resolve().parents[1]) not in _artifact_sys.path:
    _artifact_sys.path.insert(0, str(_ArtifactPath(__file__).resolve().parents[1]))


SPECIFICATION_COMMIT = "14a96b4078eec516570fce0c289baa061398a995"
REFERENCE_COMMIT = "1b556e599fd962469f8b7eace595b15e9d6d6cf6"

STAGES = {
    "development": (datetime(2020, 1, 1), datetime(2022, 12, 31, 23, 59, 59)),
    "validation": (datetime(2023, 1, 1), datetime(2025, 12, 31, 23, 59, 59)),
}
LAGS_HOURS = (24, 168, 672)
BLOCK_DAYS = 28
DAILY_STAGE_EDGE_TOLERANCE_DAYS = 7

TIMESTAMP_COLUMNS = ("timestamp", "date", "datetime", "time")
TIMESTAMP_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%d %H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S%z",
)


class Campaign52PreflightError(ValueError):
    pass


@dataclass(frozen=True)
class TimestampInventory:
    path: str
    sha256: str
    byte_count: int
    row_count: int
    schema: tuple[str, ...]
    timestamp_column: str
    first_timestamp: str
    last_timestamp: str
    duplicate_timestamp_count: int
    strictly_increasing: bool
    inferred_cadence_seconds: int | None
    missing_expected_timestamp_count: int | None
    stage_coverage: dict[str, bool]


def sha256_bytes(payload: bytes) -> str:
    from research.artifact_io.v1 import sha256_bytes_v1
    return sha256_bytes_v1(payload, factory=hashlib.sha256)


def parse_timestamp(value: str) -> datetime:
    raw = value.strip()
    if not raw:
        raise Campaign52PreflightError("EMPTY_TIMESTAMP")
    for fmt in TIMESTAMP_FORMATS:
        try:
            parsed = datetime.strptime(raw, fmt)
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
            return parsed
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except ValueError as exc:
        raise Campaign52PreflightError(f"UNSUPPORTED_TIMESTAMP:{raw}") from exc


def choose_timestamp_column(fieldnames: Sequence[str]) -> str:
    lowered = {name.strip().lower(): name for name in fieldnames}
    for candidate in TIMESTAMP_COLUMNS:
        if candidate in lowered:
            return lowered[candidate]
    raise Campaign52PreflightError("TIMESTAMP_COLUMN_NOT_FOUND")


def infer_cadence_seconds(timestamps: Sequence[datetime]) -> int | None:
    if len(timestamps) < 2:
        return None
    positive = sorted(
        int((right - left).total_seconds())
        for left, right in zip(timestamps, timestamps[1:])
        if right > left
    )
    if not positive:
        return None
    counts: dict[int, int] = {}
    for value in positive:
        counts[value] = counts.get(value, 0) + 1
    return min(counts, key=lambda value: (-counts[value], value))


def count_missing_expected(timestamps: Sequence[datetime], cadence_seconds: int | None) -> int | None:
    if cadence_seconds is None or not timestamps:
        return None
    span = int((timestamps[-1] - timestamps[0]).total_seconds())
    if span < 0 or span % cadence_seconds != 0:
        return None
    expected = span // cadence_seconds + 1
    unique = len(set(timestamps))
    return max(0, expected - unique)


def stage_coverage_facts(
    first_timestamp: datetime,
    last_timestamp: datetime,
    cadence_seconds: int | None,
) -> dict[str, bool]:
    """Check inclusive calendar-date stage coverage without repairing data.

    The frozen stages are specified as inclusive calendar dates. Therefore an
    intraday source stamped at 00:00 on the final stage date covers that date;
    it need not contain a synthetic 23:59:59 row. Daily-or-slower trading
    sources may end up to seven calendar days before the inclusive end date to
    tolerate weekends and exchange holidays. Start coverage remains strict by
    calendar date for every source.
    """
    daily_or_slower = cadence_seconds is not None and cadence_seconds >= 86_400
    return {
        stage: (
            first_timestamp.date() <= start.date()
            and (
                last_timestamp.date() >= end.date()
                or (
                    daily_or_slower
                    and last_timestamp.date()
                    >= (end - timedelta(days=DAILY_STAGE_EDGE_TOLERANCE_DAYS)).date()
                )
            )
        )
        for stage, (start, end) in STAGES.items()
    }


def inspect_source(path: Path) -> TimestampInventory:
    raw = path.read_bytes()
    timestamps: list[datetime] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = tuple(reader.fieldnames or ())
        if not fieldnames:
            raise Campaign52PreflightError(f"EMPTY_HEADER:{path.as_posix()}")
        timestamp_column = choose_timestamp_column(fieldnames)
        previous: datetime | None = None
        strictly_increasing = True
        duplicates = 0
        seen: set[datetime] = set()
        for row in reader:
            timestamp = parse_timestamp(row.get(timestamp_column, ""))
            if timestamp in seen:
                duplicates += 1
            seen.add(timestamp)
            if previous is not None and timestamp <= previous:
                strictly_increasing = False
            timestamps.append(timestamp)
            previous = timestamp

    if not timestamps:
        raise Campaign52PreflightError(f"NO_DATA_ROWS:{path.as_posix()}")

    cadence = infer_cadence_seconds(timestamps)
    stage_coverage = stage_coverage_facts(timestamps[0], timestamps[-1], cadence)
    return TimestampInventory(
        path=path.as_posix(),
        sha256=sha256_bytes(raw),
        byte_count=len(raw),
        row_count=len(timestamps),
        schema=fieldnames,
        timestamp_column=timestamp_column,
        first_timestamp=timestamps[0].strftime("%Y-%m-%d %H:%M:%S"),
        last_timestamp=timestamps[-1].strftime("%Y-%m-%d %H:%M:%S"),
        duplicate_timestamp_count=duplicates,
        strictly_increasing=strictly_increasing,
        inferred_cadence_seconds=cadence,
        missing_expected_timestamp_count=count_missing_expected(timestamps, cadence),
        stage_coverage=stage_coverage,
    )


def complete_block_facts(stage_start: datetime, stage_end: datetime) -> dict[str, object]:
    exclusive_end = stage_end + timedelta(seconds=1)
    duration = exclusive_end - stage_start
    block = timedelta(days=BLOCK_DAYS)
    complete = duration // block
    terminal = duration - complete * block
    return {
        "block_days": BLOCK_DAYS,
        "complete_block_count": int(complete),
        "terminal_remainder_seconds": int(terminal.total_seconds()),
        "terminal_remainder_days": terminal.total_seconds() / 86400.0,
    }


def lag_mapping_facts(
    timestamps: Iterable[datetime], stage_start: datetime, stage_end: datetime
) -> dict[str, dict[str, int]]:
    stage = sorted(ts for ts in timestamps if stage_start <= ts <= stage_end)
    stage_set = set(stage)
    result: dict[str, dict[str, int]] = {}
    for lag in LAGS_HOURS:
        delta = timedelta(hours=lag)
        mapped = sum(1 for ts in stage if ts - delta in stage_set and ts - delta >= stage_start)
        result[f"{lag}h"] = {
            "stage_timestamp_count": len(stage),
            "exact_mapping_count": mapped,
            "uncovered_count": len(stage) - mapped,
        }
    return result


def read_timestamps_only(path: Path) -> list[datetime]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = tuple(reader.fieldnames or ())
        timestamp_column = choose_timestamp_column(fieldnames)
        return [parse_timestamp(row.get(timestamp_column, "")) for row in reader]


def execute(paths: Sequence[Path], output: Path) -> dict[str, object]:
    if len(paths) != 6:
        raise Campaign52PreflightError("EXACTLY_SIX_SOURCES_REQUIRED")
    inventories = [inspect_source(path) for path in paths]
    if any(not item.strictly_increasing for item in inventories):
        failures = [item.path for item in inventories if not item.strictly_increasing]
        raise Campaign52PreflightError(f"SOURCE_TIMESTAMP_ORDER_FAILURE:{json.dumps(failures)}")
    if any(item.duplicate_timestamp_count for item in inventories):
        failures = {
            item.path: item.duplicate_timestamp_count
            for item in inventories
            if item.duplicate_timestamp_count
        }
        raise Campaign52PreflightError(
            f"SOURCE_DUPLICATE_TIMESTAMP_FAILURE:{json.dumps(failures, sort_keys=True)}"
        )
    coverage_failures = {
        item.path: [stage for stage, covered in item.stage_coverage.items() if not covered]
        for item in inventories
        if not all(item.stage_coverage.values())
    }
    if coverage_failures:
        raise Campaign52PreflightError(
            f"SOURCE_STAGE_COVERAGE_FAILURE:{json.dumps(coverage_failures, sort_keys=True)}"
        )

    btc = inventories[0]
    if btc.sha256 != "d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079":
        raise Campaign52PreflightError("BTC_SHA256_MISMATCH")
    if btc.byte_count != 4_792_028 or btc.row_count != 70_069:
        raise Campaign52PreflightError("BTC_IDENTITY_MISMATCH")

    calendar = {}
    for stage, (start, end) in STAGES.items():
        calendar[stage] = {
            "block_facts": complete_block_facts(start, end),
            "lag_mappings_by_source": {
                item.path: lag_mapping_facts(read_timestamps_only(Path(item.path)), start, end)
                for item in inventories
            },
        }

    payload: dict[str, object] = {
        "status": "PASS",
        "preflight_type": "campaign52_source_identity_calendar",
        "specification_commit_sha": SPECIFICATION_COMMIT,
        "reference_commit_sha": REFERENCE_COMMIT,
        "stage_coverage_semantics": "inclusive_calendar_date",
        "daily_stage_edge_tolerance_days": DAILY_STAGE_EDGE_TOLERANCE_DAYS,
        "sources": [item.__dict__ for item in inventories],
        "calendar": calendar,
        "prices_parsed": False,
        "targets_generated": False,
        "signals_generated": False,
        "positions_generated": False,
        "trades_generated": False,
        "costs_generated": False,
        "returns_generated": False,
        "nav_generated": False,
        "performance_metrics_calculated": False,
        "capture_replay_implemented": False,
        "runtime_modified": False,
        "strategy_modified": False,
        "weights_modified": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Campaign 52 source-only identity/calendar preflight.")
    parser.add_argument("--btc", required=True)
    parser.add_argument("--eth", required=True)
    parser.add_argument("--spy", required=True)
    parser.add_argument("--qqq", required=True)
    parser.add_argument("--bil", required=True)
    parser.add_argument("--gld", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = [Path(args.btc), Path(args.eth), Path(args.spy), Path(args.qqq), Path(args.bil), Path(args.gld)]
    print(json.dumps(execute(paths, Path(args.output)), sort_keys=True))


if __name__ == "__main__":
    main()
