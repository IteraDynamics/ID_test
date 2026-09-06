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
from datetime import datetime, timedelta
from pathlib import Path

from research.ml.validation.simple_btc_price_state_predictive_baselines import (
    DEFAULT_CONTRACT,
    GOVERNED_MISSING_TIMESTAMPS,
    SOURCE_COLUMNS,
)

# Keep standalone script execution working until the separate packaging migration.



HORIZONS = (24, 72, 168)
ANCHOR_SPACING_HOURS = 168
LOOKBACK_HOURS = 168
PROPOSED_STAGES = {
    "development": (
        datetime(2018, 1, 1, 0, 0, 0),
        datetime(2022, 12, 31, 23, 0, 0),
    ),
    "validation": (
        datetime(2023, 1, 1, 0, 0, 0),
        datetime(2024, 12, 31, 23, 0, 0),
    ),
    "confirmation": (
        datetime(2025, 1, 1, 0, 0, 0),
        datetime(2025, 12, 31, 0, 0, 0),
    ),
}
RECOMMENDED_DIRECTIONAL_VARIABLES = (
    "return_trailing_24h",
    "return_trailing_168h",
)
RECOMMENDED_MOVEMENT_STATES = (
    "realized_volatility_trailing_24h",
    "drawdown_from_high_trailing_168h",
)


def sha256_file(path: Path) -> str:
    from research.artifact_io.v1 import sha256_file_v1
    return sha256_file_v1(path, chunk_size=1048576, factory=hashlib.sha256)


def parse_timestamp(raw: str) -> datetime:
    value = datetime.fromisoformat(raw.strip())
    if value.tzinfo is not None:
        raise ValueError("SOURCE_TIMESTAMP_TIMEZONE_FAILURE")
    if value.minute or value.second or value.microsecond:
        raise ValueError("SOURCE_TIMESTAMP_ALIGNMENT_FAILURE")
    return value


def load_timestamps_only(path: Path) -> list[datetime]:
    contract = DEFAULT_CONTRACT
    if sha256_file(path) != contract.source_sha256:
        raise ValueError("SOURCE_SHA256_MISMATCH")
    if path.stat().st_size != contract.source_byte_count:
        raise ValueError("SOURCE_BYTE_COUNT_MISMATCH")

    timestamps: list[datetime] = []
    previous: datetime | None = None
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != SOURCE_COLUMNS:
            raise ValueError("SOURCE_SCHEMA_MISMATCH")
        for row_number, row in enumerate(reader, start=2):
            timestamp = parse_timestamp(row["timestamp"])
            if previous is not None and timestamp <= previous:
                raise ValueError(f"SOURCE_TIMESTAMP_ORDER_FAILURE:{row_number}")
            timestamps.append(timestamp)
            previous = timestamp

    if len(timestamps) != contract.source_row_count:
        raise ValueError("SOURCE_ROW_COUNT_MISMATCH")
    if timestamps[0].strftime("%Y-%m-%d %H:%M:%S") != contract.first_timestamp:
        raise ValueError("SOURCE_FIRST_TIMESTAMP_MISMATCH")
    if timestamps[-1].strftime("%Y-%m-%d %H:%M:%S") != contract.last_timestamp:
        raise ValueError("SOURCE_LAST_TIMESTAMP_MISMATCH")

    timestamp_set = set(timestamps)
    expected = []
    cursor = timestamps[0]
    while cursor <= timestamps[-1]:
        if cursor not in timestamp_set:
            expected.append(cursor.strftime("%Y-%m-%d %H:%M:%S"))
        cursor += timedelta(hours=1)
    if tuple(expected) != tuple(GOVERNED_MISSING_TIMESTAMPS):
        raise ValueError("SOURCE_GAP_INVENTORY_MISMATCH")
    return timestamps


def exact_window_exists(
    timestamp_set: set[datetime],
    *,
    start: datetime,
    end: datetime,
) -> bool:
    cursor = start
    while cursor <= end:
        if cursor not in timestamp_set:
            return False
        cursor += timedelta(hours=1)
    return True


def stage_anchor_records(timestamps: list[datetime]) -> list[dict[str, object]]:
    timestamp_set = set(timestamps)
    origin = timestamps[0] + timedelta(hours=LOOKBACK_HOURS)
    predictor_complete: list[datetime] = []
    cursor = origin
    while cursor <= timestamps[-1]:
        if exact_window_exists(
            timestamp_set,
            start=cursor - timedelta(hours=LOOKBACK_HOURS),
            end=cursor,
        ):
            predictor_complete.append(cursor)
        cursor += timedelta(hours=ANCHOR_SPACING_HOURS)

    records: list[dict[str, object]] = []
    for stage, (stage_start, stage_end) in PROPOSED_STAGES.items():
        stage_predictor_anchors = [
            timestamp
            for timestamp in predictor_complete
            if stage_start <= timestamp <= stage_end
        ]
        for horizon in HORIZONS:
            feasible = [
                timestamp
                for timestamp in stage_predictor_anchors
                if timestamp + timedelta(hours=horizon) <= stage_end
                and timestamp + timedelta(hours=horizon) in timestamp_set
            ]
            records.append(
                {
                    "stage": stage,
                    "horizon_hours": horizon,
                    "predictor_complete_anchor_count": len(stage_predictor_anchors),
                    "stage_contained_endpoint_anchor_count": len(feasible),
                    "first_feasible_anchor": (
                        feasible[0].strftime("%Y-%m-%d %H:%M:%S")
                        if feasible
                        else None
                    ),
                    "last_feasible_anchor": (
                        feasible[-1].strftime("%Y-%m-%d %H:%M:%S")
                        if feasible
                        else None
                    ),
                    "last_endpoint": (
                        (feasible[-1] + timedelta(hours=horizon)).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                        if feasible
                        else None
                    ),
                }
            )
    return records


def build_preflight(source_path: Path) -> dict[str, object]:
    timestamps = load_timestamps_only(source_path)
    records = stage_anchor_records(timestamps)
    return {
        "preflight_type": "campaign51_source_variable_feasibility_timestamp_only",
        "status": "PASS",
        "source_path": source_path.as_posix(),
        "source_sha256": DEFAULT_CONTRACT.source_sha256,
        "source_row_count": len(timestamps),
        "first_timestamp": timestamps[0].strftime("%Y-%m-%d %H:%M:%S"),
        "last_timestamp": timestamps[-1].strftime("%Y-%m-%d %H:%M:%S"),
        "governed_missing_timestamp_count": len(GOVERNED_MISSING_TIMESTAMPS),
        "recommended_directional_variables": list(
            RECOMMENDED_DIRECTIONAL_VARIABLES
        ),
        "recommended_movement_states": list(RECOMMENDED_MOVEMENT_STATES),
        "horizons_hours": list(HORIZONS),
        "candidate_count_if_selected": (
            len(RECOMMENDED_DIRECTIONAL_VARIABLES)
            * len(RECOMMENDED_MOVEMENT_STATES)
            * len(HORIZONS)
        ),
        "records": records,
        "prices_loaded": False,
        "predictors_generated": False,
        "forward_outcomes_generated": False,
        "models_fitted": False,
        "holdout_outcomes_loaded": False,
        "family_selected": False,
        "runtime_modified": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Campaign 51 timestamp-only source/variable feasibility preflight."
    )
    parser.add_argument(
        "--source",
        default=DEFAULT_CONTRACT.source_path,
    )
    parser.add_argument(
        "--output",
        default="artifacts/campaign51_source_variable_feasibility_preflight.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = build_preflight(Path(args.source))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
