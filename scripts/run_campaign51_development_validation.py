from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from research.campaign51_conditional_directional import (
    FAMILY_SIZE,
    SOURCE_BYTE_COUNT,
    SOURCE_COLUMNS,
    SOURCE_ROW_COUNT,
    SOURCE_SHA256,
    SPECIFICATION_COMMIT,
    Campaign51Error,
    Candidate,
    Standardization,
    candidate_inventory,
    canonical_csv_bytes,
    canonical_json_bytes,
    classify_development,
    classify_validation,
    forward_log_return,
    holm_adjust,
    ols_hc3_interaction,
    parse_timestamp,
    predictor_values,
    sha256_bytes,
    standardization_params,
    support_gate,
    transform_predictors,
)
from research.ml.validation.simple_btc_price_state_predictive_baselines import (
    GOVERNED_MISSING_TIMESTAMPS,
)

EXECUTION_GO_COMMIT = "e9eba6f7141851934fbe6a31b4f5c999493d7ab8"
DEVELOPMENT_START = datetime(2018, 1, 1, 0, 0, 0)
DEVELOPMENT_END = datetime(2022, 12, 31, 23, 0, 0)
VALIDATION_START = datetime(2023, 1, 1, 0, 0, 0)
VALIDATION_END = datetime(2024, 12, 31, 23, 0, 0)
HOLDOUT_START = datetime(2025, 1, 1, 0, 0, 0)
ANCHOR_ORIGIN = datetime(2018, 1, 8, 0, 0, 0)
ANCHOR_SPACING = timedelta(hours=168)

INVENTORY_FIELDS = (
    "candidate_ordinal", "candidate_key", "directional_variable",
    "movement_state", "horizon_hours",
)
RESULT_FIELDS = (
    "candidate_ordinal", "candidate_key", "directional_variable",
    "movement_state", "horizon_hours", "stage", "status", "rankable", "n",
    "directional_mean_development", "directional_sd_development",
    "state_mean_development", "state_sd_development", "beta0",
    "beta_directional", "beta_state", "beta_interaction",
    "se_interaction_hc3", "t_stat", "raw_p_value",
    "holm_adjusted_p_value", "ci_low", "ci_high", "failure_reason",
)
SHORTLIST_FIELDS = (
    "candidate_ordinal", "candidate_key", "directional_variable",
    "movement_state", "horizon_hours", "development_beta_interaction",
    "development_holm_adjusted_p_value", "validation_beta_interaction",
    "validation_holm_adjusted_p_value",
    "validation_to_development_abs_ratio",
)


def _timestamp_text(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _source_gap_inventory(timestamps: list[datetime]) -> tuple[str, ...]:
    present = set(timestamps)
    missing: list[str] = []
    cursor = timestamps[0]
    while cursor <= timestamps[-1]:
        if cursor not in present:
            missing.append(_timestamp_text(cursor))
        cursor += timedelta(hours=1)
    return tuple(missing)


def load_source_without_holdout_close(
    source: Path,
) -> tuple[list[datetime], dict[datetime, float]]:
    raw = source.read_bytes()
    if sha256_bytes(raw) != SOURCE_SHA256:
        raise Campaign51Error("SOURCE_SHA256_MISMATCH")
    if len(raw) != SOURCE_BYTE_COUNT:
        raise Campaign51Error("SOURCE_BYTE_COUNT_MISMATCH")

    timestamps: list[datetime] = []
    close_by_time: dict[datetime, float] = {}
    previous: datetime | None = None
    with source.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != SOURCE_COLUMNS:
            raise Campaign51Error("SOURCE_SCHEMA_MISMATCH")
        for row_number, row in enumerate(reader, start=2):
            timestamp = parse_timestamp(row["timestamp"])
            if timestamp.minute or timestamp.second or timestamp.microsecond:
                raise Campaign51Error(
                    f"SOURCE_TIMESTAMP_ALIGNMENT_FAILURE:{row_number}"
                )
            if previous is not None and timestamp <= previous:
                raise Campaign51Error(f"SOURCE_TIMESTAMP_ORDER_FAILURE:{row_number}")
            timestamps.append(timestamp)
            previous = timestamp
            if timestamp < HOLDOUT_START:
                close = float(row["close"])
                if not math.isfinite(close) or close <= 0:
                    raise Campaign51Error(f"SOURCE_CLOSE_FAILURE:{row_number}")
                close_by_time[timestamp] = close

    if len(timestamps) != SOURCE_ROW_COUNT:
        raise Campaign51Error("SOURCE_ROW_COUNT_MISMATCH")
    if _timestamp_text(timestamps[0]) != "2018-01-01 00:00:00":
        raise Campaign51Error("SOURCE_FIRST_TIMESTAMP_MISMATCH")
    if _timestamp_text(timestamps[-1]) != "2025-12-31 00:00:00":
        raise Campaign51Error("SOURCE_LAST_TIMESTAMP_MISMATCH")
    if _source_gap_inventory(timestamps) != tuple(GOVERNED_MISSING_TIMESTAMPS):
        raise Campaign51Error("SOURCE_GAP_INVENTORY_MISMATCH")
    if any(timestamp >= HOLDOUT_START for timestamp in close_by_time):
        raise Campaign51Error("HOLDOUT_CLOSE_LOADED")
    return timestamps, close_by_time


def stage_anchors(start: datetime, end: datetime) -> list[datetime]:
    anchor = ANCHOR_ORIGIN
    while anchor < start:
        anchor += ANCHOR_SPACING
    anchors: list[datetime] = []
    while anchor <= end:
        anchors.append(anchor)
        anchor += ANCHOR_SPACING
    return anchors


def candidate_rows(
    candidate: Candidate,
    close_by_time: dict[datetime, float],
    stage_start: datetime,
    stage_end: datetime,
) -> tuple[list[float], list[float], list[float]]:
    directional: list[float] = []
    movement: list[float] = []
    outcomes: list[float] = []
    for anchor in stage_anchors(stage_start, stage_end):
        if anchor + timedelta(hours=candidate.horizon_hours) > stage_end:
            continue
        try:
            predictors = predictor_values(close_by_time, anchor)
            outcome = forward_log_return(
                close_by_time, anchor, candidate.horizon_hours, stage_end
            )
        except Campaign51Error as exc:
            if str(exc) in {
                "WINDOW_TIMESTAMP_FAILURE",
                "OUTCOME_TIMESTAMP_FAILURE",
                "OUTCOME_STAGE_BOUNDARY_FAILURE",
            }:
                continue
            raise
        directional.append(float(predictors[candidate.directional_variable]))
        movement.append(float(predictors[candidate.movement_state]))
        outcomes.append(float(outcome))
    return directional, movement, outcomes


def _blank_result(index: int, candidate: Candidate, stage: str) -> dict[str, Any]:
    return {
        "candidate_ordinal": index,
        "candidate_key": candidate.key,
        "directional_variable": candidate.directional_variable,
        "movement_state": candidate.movement_state,
        "horizon_hours": candidate.horizon_hours,
        "stage": stage,
        "status": "UNRANKABLE",
        "rankable": False,
        "n": 0,
        "directional_mean_development": None,
        "directional_sd_development": None,
        "state_mean_development": None,
        "state_sd_development": None,
        "beta0": None,
        "beta_directional": None,
        "beta_state": None,
        "beta_interaction": None,
        "se_interaction_hc3": None,
        "t_stat": None,
        "raw_p_value": None,
        "holm_adjusted_p_value": None,
        "ci_low": None,
        "ci_high": None,
        "failure_reason": "",
    }


def _put_params(row: dict[str, Any], params: Standardization) -> None:
    row.update({
        "directional_mean_development": params.directional_mean,
        "directional_sd_development": params.directional_sd,
        "state_mean_development": params.state_mean,
        "state_sd_development": params.state_sd,
    })


def _put_fit(row: dict[str, Any], fit: Any) -> None:
    row.update({
        "rankable": True,
        "beta0": fit.beta0,
        "beta_directional": fit.beta_directional,
        "beta_state": fit.beta_state,
        "beta_interaction": fit.beta_interaction,
        "se_interaction_hc3": fit.se_interaction_hc3,
        "t_stat": fit.t_stat,
        "raw_p_value": fit.p_value,
        "ci_low": fit.ci_low,
        "ci_high": fit.ci_high,
    })


def fit_development(
    candidates: list[Candidate], close_by_time: dict[datetime, float]
) -> tuple[list[dict[str, Any]], dict[str, Standardization]]:
    rows: list[dict[str, Any]] = []
    params_by_key: dict[str, Standardization] = {}
    raw_p: dict[str, float] = {}
    for index, candidate in enumerate(candidates):
        row = _blank_result(index, candidate, "development")
        directional, movement, outcomes = candidate_rows(
            candidate, close_by_time, DEVELOPMENT_START, DEVELOPMENT_END
        )
        row["n"] = len(outcomes)
        gate_failure = support_gate("development", candidate.horizon_hours, len(outcomes))
        if gate_failure is not None:
            row["failure_reason"] = gate_failure
            rows.append(row)
            continue
        try:
            params = standardization_params(directional, movement)
            params_by_key[candidate.key] = params
            _put_params(row, params)
            directional_z, movement_z, _ = transform_predictors(
                directional, movement, params
            )
            fit = ols_hc3_interaction(directional_z, movement_z, outcomes)
        except (Campaign51Error, np.linalg.LinAlgError) as exc:
            row["failure_reason"] = str(exc)
            rows.append(row)
            continue
        _put_fit(row, fit)
        raw_p[candidate.key] = fit.p_value
        rows.append(row)

    adjusted = holm_adjust(raw_p, FAMILY_SIZE)
    for row in rows:
        if row["rankable"]:
            row["holm_adjusted_p_value"] = adjusted[row["candidate_key"]]
            row["status"] = classify_development(
                True, row["holm_adjusted_p_value"]
            )
    return rows, params_by_key


def fit_validation(
    candidates: list[Candidate],
    close_by_time: dict[datetime, float],
    development_rows: list[dict[str, Any]],
    params_by_key: dict[str, Standardization],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    raw_p: dict[str, float] = {}
    development_by_key = {row["candidate_key"]: row for row in development_rows}
    for index, candidate in enumerate(candidates):
        row = _blank_result(index, candidate, "validation")
        directional, movement, outcomes = candidate_rows(
            candidate, close_by_time, VALIDATION_START, VALIDATION_END
        )
        row["n"] = len(outcomes)
        params = params_by_key.get(candidate.key)
        if params is not None:
            _put_params(row, params)
        gate_failure = support_gate("validation", candidate.horizon_hours, len(outcomes))
        if gate_failure is not None:
            row["failure_reason"] = gate_failure
            rows.append(row)
            continue
        if params is None:
            row["failure_reason"] = "DEVELOPMENT_STANDARDIZATION_UNAVAILABLE"
            rows.append(row)
            continue
        try:
            directional_z, movement_z, _ = transform_predictors(
                directional, movement, params
            )
            fit = ols_hc3_interaction(directional_z, movement_z, outcomes)
        except (Campaign51Error, np.linalg.LinAlgError) as exc:
            row["failure_reason"] = str(exc)
            rows.append(row)
            continue
        _put_fit(row, fit)
        raw_p[candidate.key] = fit.p_value
        rows.append(row)

    adjusted = holm_adjust(raw_p, FAMILY_SIZE)
    for row in rows:
        if row["rankable"]:
            row["holm_adjusted_p_value"] = adjusted[row["candidate_key"]]
            development = development_by_key[row["candidate_key"]]
            row["status"] = classify_validation(
                development["status"],
                True,
                development["beta_interaction"],
                row["beta_interaction"],
                row["holm_adjusted_p_value"],
            )
    return rows


def shortlist_rows(
    candidates: list[Candidate],
    development_rows: list[dict[str, Any]],
    validation_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    development_by_key = {row["candidate_key"]: row for row in development_rows}
    validation_by_key = {row["candidate_key"]: row for row in validation_rows}
    shortlist: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates):
        development = development_by_key[candidate.key]
        validation = validation_by_key[candidate.key]
        if validation["status"] != "VALIDATION_SUPPORTED":
            continue
        development_beta = float(development["beta_interaction"])
        validation_beta = float(validation["beta_interaction"])
        shortlist.append({
            "candidate_ordinal": index,
            "candidate_key": candidate.key,
            "directional_variable": candidate.directional_variable,
            "movement_state": candidate.movement_state,
            "horizon_hours": candidate.horizon_hours,
            "development_beta_interaction": development_beta,
            "development_holm_adjusted_p_value": development["holm_adjusted_p_value"],
            "validation_beta_interaction": validation_beta,
            "validation_holm_adjusted_p_value": validation["holm_adjusted_p_value"],
            "validation_to_development_abs_ratio": (
                abs(validation_beta) / abs(development_beta)
            ),
        })
    return shortlist


def _status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return dict(sorted(counts.items()))


def execute(source: Path, output_dir: Path) -> dict[str, Any]:
    timestamps, close_by_time = load_source_without_holdout_close(source)
    candidates = candidate_inventory()
    development, params_by_key = fit_development(candidates, close_by_time)
    validation = fit_validation(
        candidates, close_by_time, development, params_by_key
    )
    shortlist = shortlist_rows(candidates, development, validation)

    inventory = [
        {
            "candidate_ordinal": index,
            "candidate_key": candidate.key,
            "directional_variable": candidate.directional_variable,
            "movement_state": candidate.movement_state,
            "horizon_hours": candidate.horizon_hours,
        }
        for index, candidate in enumerate(candidates)
    ]
    manifest = {
        "status": "PASS",
        "campaign_id": 51,
        "specification_commit_sha": SPECIFICATION_COMMIT,
        "execution_go_commit_sha": EXECUTION_GO_COMMIT,
        "source_path": source.as_posix(),
        "source_sha256": SOURCE_SHA256,
        "source_byte_count": SOURCE_BYTE_COUNT,
        "source_row_count": SOURCE_ROW_COUNT,
        "first_timestamp": _timestamp_text(timestamps[0]),
        "last_timestamp": _timestamp_text(timestamps[-1]),
        "governed_missing_timestamp_count": len(GOVERNED_MISSING_TIMESTAMPS),
        "candidate_count": len(candidates),
        "development_status_counts": _status_counts(development),
        "validation_status_counts": _status_counts(validation),
        "shortlist_count": len(shortlist),
        "prices_loaded_through": "2024-12-31 23:00:00",
        "predictors_generated": True,
        "forward_outcomes_generated": True,
        "models_fitted": True,
        "development_validation_execution_enabled": True,
        "holdout_loaded": False,
        "confirmation_enabled": False,
        "runtime_modified": False,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "campaign51_candidate_inventory.csv": canonical_csv_bytes(
            INVENTORY_FIELDS, inventory
        ),
        "campaign51_development_results.csv": canonical_csv_bytes(
            RESULT_FIELDS, development
        ),
        "campaign51_validation_results.csv": canonical_csv_bytes(
            RESULT_FIELDS, validation
        ),
        "campaign51_shortlist.csv": canonical_csv_bytes(
            SHORTLIST_FIELDS, shortlist
        ),
        "campaign51_stage_manifest.json": canonical_json_bytes(manifest),
    }
    for name, payload in outputs.items():
        (output_dir / name).write_bytes(payload)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Governed Campaign 51 development/validation execution."
    )
    parser.add_argument("--source", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = execute(Path(args.source), Path(args.output_dir))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
