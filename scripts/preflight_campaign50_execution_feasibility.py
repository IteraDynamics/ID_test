from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path

from research.campaign50_equity_breadth import EXPECTED_COLUMNS, parse_timestamp, sha256_file
from scripts.reconcile_campaign50_equity_sessions import EXPECTED_SHA256
from scripts.run_campaign50_development_validation import (
    DEVELOPMENT,
    HORIZONS,
    VALIDATION,
    stage_anchor_indices,
)


MINIMUMS = {
    "development": {5: 180, 20: 55, 60: 18},
    "validation": {5: 80, 20: 22, 60: 8},
}


def load_target_sessions(path: Path) -> list[date]:
    if sha256_file(path) != EXPECTED_SHA256[path.name]:
        raise ValueError(f"SOURCE_IDENTITY_FAILURE: {path.name}")
    sessions: list[date] = []
    previous: date | None = None
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != EXPECTED_COLUMNS:
            raise ValueError(f"SOURCE_SCHEMA_FAILURE: {path.name}")
        for row_number, row in enumerate(reader, start=2):
            session = parse_timestamp(row["timestamp"]).date()
            if previous is not None and session <= previous:
                raise ValueError(f"SOURCE_ORDER_FAILURE: {path.name}:{row_number}")
            previous = session
            if session <= VALIDATION[1]:
                sessions.append(session)
    return sessions


def build_feasibility(data_root: Path) -> dict[str, object]:
    spy = load_target_sessions(data_root / "SPY_1D.csv")
    qqq = load_target_sessions(data_root / "QQQ_1D.csv")
    if spy != qqq:
        raise ValueError("SOURCE_ORDER_FAILURE: target calendars differ")

    stages = {
        "development": DEVELOPMENT,
        "validation": VALIDATION,
    }
    records: list[dict[str, object]] = []
    structurally_impossible: list[str] = []
    for stage, (start, end) in stages.items():
        for horizon in HORIZONS:
            anchors = stage_anchor_indices(
                spy,
                start=start,
                end=end,
                horizon=horizon,
            )
            minimum = MINIMUMS[stage][horizon]
            feasible = len(anchors) >= minimum
            key = f"{stage}__horizon_{horizon}"
            if not feasible:
                structurally_impossible.append(key)
            records.append(
                {
                    "stage": stage,
                    "horizon": horizon,
                    "maximum_candidate_complete_anchor_count": len(anchors),
                    "frozen_minimum_total_support": minimum,
                    "minimum_structurally_feasible": feasible,
                    "first_anchor": spy[anchors[0]].isoformat() if anchors else None,
                    "last_anchor": spy[anchors[-1]].isoformat() if anchors else None,
                    "last_outcome_session": spy[anchors[-1] + horizon].isoformat() if anchors else None,
                }
            )

    return {
        "preflight_type": "campaign50_execution_feasibility_date_only",
        "status": "PASS" if not structurally_impossible else "FAIL",
        "predictors_generated": False,
        "outcomes_generated": False,
        "prices_loaded": False,
        "holdout_loaded": False,
        "records": records,
        "structurally_impossible_gates": structurally_impossible,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check Campaign 50 anchor/support feasibility using dates only."
    )
    parser.add_argument("--data-root", default="data")
    parser.add_argument(
        "--output",
        default="artifacts/campaign50_execution_feasibility_preflight.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = build_feasibility(Path(args.data_root))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "records": result["records"],
                "structurally_impossible_gates": result["structurally_impossible_gates"],
                "predictors_generated": False,
                "outcomes_generated": False,
                "prices_loaded": False,
                "holdout_loaded": False,
                "output": output.as_posix(),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
