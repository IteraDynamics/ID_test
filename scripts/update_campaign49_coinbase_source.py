from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from scripts.fetch_coinbase_hourly_history import fetch_product, parse_utc


PRODUCT_ID = "BTC-USD"
GRANULARITY_SECONDS = 3600
FIXED_START = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
SCHEMA = ["timestamp", "open", "high", "low", "close", "volume"]
REVISION_ERROR = "HISTORICAL_SOURCE_REVISION"


@dataclass(frozen=True)
class SourceRow:
    timestamp: datetime
    values: tuple[str, str, str, str, str]


@dataclass(frozen=True)
class SourceInventory:
    raw: bytes
    rows: tuple[SourceRow, ...]
    first_timestamp: datetime
    last_timestamp: datetime
    missing_timestamps: tuple[datetime, ...]


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is not None:
        raise ValueError("TIMEZONE_SERIALIZATION_FAILURE")
    if parsed.minute or parsed.second or parsed.microsecond:
        raise ValueError("HOUR_ALIGNMENT_FAILURE")
    return parsed


def _validate_numeric_row(row: dict[str, str], line_number: int) -> None:
    try:
        values = {name: float(row[name]) for name in SCHEMA[1:]}
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"NUMERIC_PARSE_FAILURE line={line_number}") from exc

    if not all(math.isfinite(value) for value in values.values()):
        raise ValueError(f"NONFINITE_VALUE_FAILURE line={line_number}")
    if any(values[name] <= 0 for name in ("open", "high", "low", "close")):
        raise ValueError(f"NONPOSITIVE_OHLC_FAILURE line={line_number}")
    if values["volume"] < 0:
        raise ValueError(f"NEGATIVE_VOLUME_FAILURE line={line_number}")
    if not (
        values["low"] <= values["open"] <= values["high"]
        and values["low"] <= values["close"] <= values["high"]
    ):
        raise ValueError(f"OHLC_RELATIONSHIP_FAILURE line={line_number}")


def inventory_csv_bytes(raw: bytes) -> SourceInventory:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("UTF8_DECODE_FAILURE") from exc

    if "\r" in text:
        raise ValueError("NON_LF_LINE_ENDING_FAILURE")

    reader = csv.DictReader(io.StringIO(text, newline=""))
    if reader.fieldnames != SCHEMA:
        raise ValueError(
            f"SCHEMA_FAILURE expected={SCHEMA} actual={reader.fieldnames}"
        )

    rows: list[SourceRow] = []
    seen: set[datetime] = set()
    previous: datetime | None = None
    for line_number, row in enumerate(reader, start=2):
        timestamp = _parse_timestamp(row["timestamp"])
        _validate_numeric_row(row, line_number)
        if timestamp in seen:
            raise ValueError(f"DUPLICATE_TIMESTAMP_FAILURE timestamp={timestamp}")
        if previous is not None and timestamp <= previous:
            raise ValueError("TIMESTAMP_ORDER_FAILURE")
        seen.add(timestamp)
        previous = timestamp
        rows.append(
            SourceRow(
                timestamp=timestamp,
                values=tuple(row[name] for name in SCHEMA[1:]),
            )
        )

    if not rows:
        raise ValueError("EMPTY_SOURCE_FAILURE")

    first = rows[0].timestamp
    last = rows[-1].timestamp
    missing: list[datetime] = []
    cursor = first
    while cursor <= last:
        if cursor not in seen:
            missing.append(cursor)
        cursor += timedelta(hours=1)

    return SourceInventory(
        raw=raw,
        rows=tuple(rows),
        first_timestamp=first,
        last_timestamp=last,
        missing_timestamps=tuple(missing),
    )


def reconcile_prior_interval(
    prior: SourceInventory,
    candidate: SourceInventory,
) -> None:
    if candidate.first_timestamp != prior.first_timestamp:
        raise ValueError(
            f"{REVISION_ERROR}: start changed "
            f"prior={prior.first_timestamp} candidate={candidate.first_timestamp}"
        )
    if candidate.last_timestamp <= prior.last_timestamp:
        raise ValueError("CUMULATIVE_END_NOT_EXTENDED")

    prior_map = {row.timestamp: row.values for row in prior.rows}
    candidate_map = {row.timestamp: row.values for row in candidate.rows}

    for timestamp, values in prior_map.items():
        candidate_values = candidate_map.get(timestamp)
        if candidate_values is None:
            raise ValueError(
                f"{REVISION_ERROR}: disappeared candle timestamp={timestamp}"
            )
        if candidate_values != values:
            raise ValueError(
                f"{REVISION_ERROR}: changed candle timestamp={timestamp}"
            )

    prior_end = prior.last_timestamp
    for timestamp in candidate_map:
        if timestamp <= prior_end and timestamp not in prior_map:
            raise ValueError(
                f"{REVISION_ERROR}: added historical candle timestamp={timestamp}"
            )


def canonical_csv_bytes(dataframe) -> bytes:
    if list(dataframe.columns) != SCHEMA:
        raise ValueError(
            f"SCHEMA_FAILURE expected={SCHEMA} actual={list(dataframe.columns)}"
        )
    text = dataframe.to_csv(index=False, lineterminator="\n")
    return text.encode("utf-8")


def _format_timestamp(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def output_stem(end: datetime) -> str:
    return f"btcusd_3600s_2026-01-01_to_{end:%Y-%m-%dT%H%M%SZ}"


def build_manifest(
    *,
    candidate: SourceInventory,
    prior: SourceInventory,
    prior_path: Path,
    source_path: Path,
    manifest_path: Path,
    end: datetime,
    acquisition_command: str,
) -> dict[str, object]:
    continuous_count = int(
        (candidate.last_timestamp - candidate.first_timestamp).total_seconds() // 3600
    ) + 1
    return {
        "acquisition_command": acquisition_command,
        "byte_count": len(candidate.raw),
        "continuous_hour_count": continuous_count,
        "data_row_count": len(candidate.rows),
        "endpoint_family": (
            "https://api.exchange.coinbase.com/products/BTC-USD/candles"
        ),
        "first_timestamp": _format_timestamp(candidate.first_timestamp),
        "fixed_start": _iso_z(FIXED_START),
        "granularity_seconds": GRANULARITY_SECONDS,
        "historical_revision_check": "PASS",
        "last_timestamp": _format_timestamp(candidate.last_timestamp),
        "missing_hour_count": len(candidate.missing_timestamps),
        "missing_timestamps": [
            _format_timestamp(value) for value in candidate.missing_timestamps
        ],
        "ordered_schema": SCHEMA,
        "prior_last_timestamp": _format_timestamp(prior.last_timestamp),
        "prior_sha256": hashlib.sha256(prior.raw).hexdigest(),
        "prior_source_path": prior_path.as_posix(),
        "product_id": PRODUCT_ID,
        "provider": "Coinbase Exchange",
        "requested_end": _iso_z(end),
        "sha256": hashlib.sha256(candidate.raw).hexdigest(),
        "source_path": source_path.as_posix(),
        "source_validation_status": "PASS",
        "timestamp_alignment": "whole_hour",
        "timezone_convention": "UTC serialized as timezone-naive",
        "manifest_path": manifest_path.as_posix(),
    }


def write_outputs(
    source_path: Path,
    manifest_path: Path,
    source_bytes: bytes,
    manifest: dict[str, object],
) -> None:
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_bytes(source_bytes)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _validate_end(end: datetime) -> None:
    if end.tzinfo is None:
        raise ValueError("END_TIMEZONE_FAILURE")
    if end.minute or end.second or end.microsecond:
        raise ValueError("END_HOUR_ALIGNMENT_FAILURE")
    if end <= FIXED_START:
        raise ValueError("END_NOT_AFTER_FIXED_START")


def run(args: argparse.Namespace) -> tuple[Path, Path, dict[str, object]]:
    prior_path = Path(args.prior_source)
    prior_manifest_path = Path(args.prior_manifest)
    end = parse_utc(args.end)
    _validate_end(end)

    prior = inventory_csv_bytes(prior_path.read_bytes())
    if prior.first_timestamp != FIXED_START.replace(tzinfo=None):
        raise ValueError("PRIOR_FIXED_START_FAILURE")

    prior_manifest = json.loads(prior_manifest_path.read_text(encoding="utf-8"))
    prior_sha = hashlib.sha256(prior.raw).hexdigest()
    if prior_manifest.get("sha256") != prior_sha:
        raise ValueError("PRIOR_MANIFEST_HASH_FAILURE")

    dataframe = fetch_product(
        product_id=PRODUCT_ID,
        start=FIXED_START,
        end=end,
        sleep_seconds=args.sleep_seconds,
        retries=args.retries,
        retry_sleep_seconds=args.retry_sleep_seconds,
    )
    source_bytes = canonical_csv_bytes(dataframe)
    candidate = inventory_csv_bytes(source_bytes)
    expected_end = end.astimezone(timezone.utc).replace(tzinfo=None)
    if candidate.last_timestamp != expected_end:
        raise ValueError(
            f"END_ENDPOINT_FAILURE expected={expected_end} "
            f"actual={candidate.last_timestamp}"
        )

    reconcile_prior_interval(prior, candidate)

    stem = output_stem(end)
    out_dir = Path(args.out_dir)
    source_path = out_dir / f"{stem}.csv"
    manifest_path = out_dir / f"{stem}.source_manifest.json"
    command = (
        "python scripts/update_campaign49_coinbase_source.py "
        f"--prior-source {prior_path.as_posix()} "
        f"--prior-manifest {prior_manifest_path.as_posix()} "
        f"--end {_iso_z(end)} --out-dir {out_dir.as_posix()}"
    )
    manifest = build_manifest(
        candidate=candidate,
        prior=prior,
        prior_path=prior_path,
        source_path=source_path,
        manifest_path=manifest_path,
        end=end,
        acquisition_command=command,
    )
    write_outputs(source_path, manifest_path, source_bytes, manifest)
    return source_path, manifest_path, manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extend the Campaign 49 Coinbase BTC-USD prospective source while "
            "failing closed on any historical revision."
        )
    )
    parser.add_argument("--prior-source", required=True)
    parser.add_argument("--prior-manifest", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--out-dir", default="data")
    parser.add_argument("--sleep-seconds", type=float, default=0.20)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--retry-sleep-seconds", type=float, default=2.0)
    return parser.parse_args()


def main() -> None:
    source_path, manifest_path, manifest = run(parse_args())
    print(json.dumps(manifest, separators=(",", ":"), sort_keys=True))
    print(f"wrote: {source_path}")
    print(f"wrote: {manifest_path}")


if __name__ == "__main__":
    main()
