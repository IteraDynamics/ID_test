from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from research.campaign51_conditional_directional import (
    FAMILY_SIZE,
    HORIZONS,
    MODEL_TERM_COUNT,
    SOURCE_BYTE_COUNT,
    SOURCE_COLUMNS,
    SOURCE_ROW_COUNT,
    SOURCE_SHA256,
    SPECIFICATION_COMMIT,
    SUPPORT_GATES,
    candidate_inventory,
    parse_timestamp,
    sha256_bytes,
)
from research.ml.validation.simple_btc_price_state_predictive_baselines import (
    GOVERNED_MISSING_TIMESTAMPS,
)


def execute(source: Path, output: Path) -> dict[str, object]:
    raw = source.read_bytes()
    if sha256_bytes(raw) != SOURCE_SHA256:
        raise ValueError("SOURCE_SHA256_MISMATCH")
    if len(raw) != SOURCE_BYTE_COUNT:
        raise ValueError("SOURCE_BYTE_COUNT_MISMATCH")

    timestamps = []
    with source.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != SOURCE_COLUMNS:
            raise ValueError("SOURCE_SCHEMA_MISMATCH")
        previous = None
        for row_number, row in enumerate(reader, start=2):
            timestamp = parse_timestamp(row["timestamp"])
            if timestamp.minute or timestamp.second or timestamp.microsecond:
                raise ValueError(f"SOURCE_TIMESTAMP_ALIGNMENT_FAILURE:{row_number}")
            if previous is not None and timestamp <= previous:
                raise ValueError(f"SOURCE_TIMESTAMP_ORDER_FAILURE:{row_number}")
            timestamps.append(timestamp)
            previous = timestamp

    if len(timestamps) != SOURCE_ROW_COUNT:
        raise ValueError("SOURCE_ROW_COUNT_MISMATCH")
    if timestamps[0].strftime("%Y-%m-%d %H:%M:%S") != "2018-01-01 00:00:00":
        raise ValueError("SOURCE_FIRST_TIMESTAMP_MISMATCH")
    if timestamps[-1].strftime("%Y-%m-%d %H:%M:%S") != "2025-12-31 00:00:00":
        raise ValueError("SOURCE_LAST_TIMESTAMP_MISMATCH")

    timestamp_set = set(timestamps)
    expected = []
    cursor = timestamps[0]
    while cursor <= timestamps[-1]:
        if cursor not in timestamp_set:
            expected.append(cursor.strftime("%Y-%m-%d %H:%M:%S"))
        cursor = cursor.replace() + __import__("datetime").timedelta(hours=1)
    if tuple(expected) != tuple(GOVERNED_MISSING_TIMESTAMPS):
        raise ValueError("SOURCE_GAP_INVENTORY_MISMATCH")

    candidates = candidate_inventory()
    result = {
        "status": "PASS",
        "preflight_type": "campaign51_source_only_implementation",
        "source_path": source.as_posix(),
        "source_sha256": SOURCE_SHA256,
        "source_byte_count": len(raw),
        "source_row_count": len(timestamps),
        "first_timestamp": timestamps[0].strftime("%Y-%m-%d %H:%M:%S"),
        "last_timestamp": timestamps[-1].strftime("%Y-%m-%d %H:%M:%S"),
        "governed_missing_timestamp_count": len(expected),
        "specification_commit_sha": SPECIFICATION_COMMIT,
        "candidate_count": len(candidates),
        "candidate_keys": [candidate.key for candidate in candidates],
        "horizons_hours": list(HORIZONS),
        "support_gates": SUPPORT_GATES,
        "model_term_count": MODEL_TERM_COUNT,
        "covariance": "HC3",
        "multiplicity": "Holm",
        "multiplicity_family_size": FAMILY_SIZE,
        "prices_loaded": False,
        "predictors_generated": False,
        "forward_outcomes_generated": False,
        "models_fitted": False,
        "holdout_loaded": False,
        "confirmation_enabled": False,
        "development_validation_execution_enabled": False,
        "runtime_modified": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Campaign 51 source-only implementation preflight.")
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(json.dumps(execute(Path(args.source), Path(args.output)), sort_keys=True))


if __name__ == "__main__":
    main()
