"""Deterministic, observation-only Campaign #45 regime-transition discovery.

This module consumes the frozen Campaign #46 transition ledger. It does not
reconstruct regimes or the chronological purge, and it has no production or
runtime integration surface.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
from scipy.special import ndtr

SOURCE_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume")
TRANSITION_COLUMNS = (
    "transition_id",
    "transition_ordinal",
    "anchor_bar_index",
    "anchor_timestamp",
    "prior_regime_label",
    "current_regime_label",
    "ordered_transition",
    "prior_state_start_timestamp",
    "prior_state_duration_bars",
    "prior_transition_timestamp",
    "spacing_since_prior_transition_bars",
    "spacing_since_prior_transition_hours",
    "current_state_age_bars",
    "anchor_source_row_digest",
)
HORIZONS = (24, 72, 168)
CONTROL_COLUMNS = (
    "trailing_log_return_24h",
    "trailing_log_return_72h",
    "trailing_log_return_168h",
    "realized_volatility_24h",
    "realized_volatility_168h",
    "distance_from_close_mean_168h",
)
OUTPUT_FILENAMES = (
    "regime_transition_source_manifest.json",
    "regime_transition_anchor_inventory.json",
    "regime_transition_anchor_inventory.csv",
    "regime_transition_candidate_inventory.json",
    "regime_transition_candidate_inventory.csv",
    "regime_transition_fold_plan.json",
    "regime_transition_results.json",
    "regime_transition_results.csv",
    "regime_transition_report.md",
    "regime_transition_manifest.json",
)

STATUS_SUPPORTED = "SUPPORTED_ASSOCIATION"
STATUS_MULTIPLICITY = "MULTIPLICITY_NOT_MET"
STATUS_DIRECTION = "DIRECTION_UNSTABLE"
STATUS_OVERALL = "INSUFFICIENT_OVERALL_SUPPORT"
STATUS_PARTITION = "INSUFFICIENT_PARTITION_SUPPORT"
STATUS_BINARY = "INSUFFICIENT_BINARY_SIDE_SUPPORT"
STATUS_TIMESTAMP = "MISSING_EXACT_TIMESTAMP"
STATUS_CONTROL = "MISSING_OR_NONFINITE_CONTROL"
STATUS_SINGULAR = "SINGULAR_DESIGN"
STATUS_SOURCE = "SOURCE_INVALID"
STATUS_LEAKAGE = "LEAKAGE_OR_AMBIGUITY"
STATUS_ESTIMATOR = "ESTIMATOR_FAILURE"


@dataclass(frozen=True)
class SourcePaths:
    manifest: Path
    feasibility: Path
    transitions: Path
    btc: Path


@dataclass(frozen=True)
class FrozenContract:
    btc_sha256: str = "d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079"
    btc_byte_count: int = 4_792_028
    btc_row_count: int = 70_069
    btc_first_timestamp: str = "2018-01-01 00:00:00"
    btc_last_timestamp: str = "2025-12-31 00:00:00"
    total_transition_count: int = 2_789
    eligible_transition_count: int = 2_788
    purged_transition_count: int = 242
    partition_counts: tuple[int, int, int] = (81, 81, 80)
    feasibility_status: str = "CAMPAIGN_45_SOURCE_FEASIBLE"


DEFAULT_CONTRACT = FrozenContract()


@dataclass(frozen=True)
class OLSResult:
    coefficient: float
    standard_error: float
    p_value: float
    confidence_interval_low: float
    confidence_interval_high: float
    approximate_return_difference: float
    n_obs: int
    rank: int


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repo_path(path: Path, repo_root: Path) -> str:
    try:
        rel = path.resolve().relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ValueError(f"path is outside repository root: {path}") from exc
    return rel.as_posix()


def _parse_iso_hour(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"invalid timestamp: {value}") from exc
    if parsed.tzinfo is not None:
        raise ValueError("timestamps must be timezone-naive")
    if parsed.minute or parsed.second or parsed.microsecond:
        raise ValueError("timestamps must be aligned to exact hours")
    return parsed


def _strict_load_json(path: Path) -> Any:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-strict JSON constant: {value}")

    with path.open("r", encoding="utf-8", newline="") as handle:
        return json.load(handle, parse_constant=reject_constant)


def _normalise_scalar(value: Any) -> Any:
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        if value == 0.0:
            return 0.0
        return float(format(value, ".17g"))
    if isinstance(value, dict):
        return {str(key): _normalise_scalar(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalise_scalar(item) for item in value]
    return value


def json_text(payload: Any) -> str:
    normalised = _normalise_scalar(payload)
    return json.dumps(normalised, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def _csv_scalar(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (np.floating, float)):
        numeric = float(value)
        if not math.isfinite(numeric):
            return ""
        if numeric == 0.0:
            numeric = 0.0
        return format(numeric, ".17g")
    if isinstance(value, (np.integer, int)) and not isinstance(value, bool):
        return str(int(value))
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(_normalise_scalar(value), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return str(value)


def csv_text(rows: Sequence[Mapping[str, Any]], columns: Iterable[str]) -> str:
    fieldnames = list(columns)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n", extrasaction="raise")
    writer.writeheader()
    for row in rows:
        writer.writerow({name: _csv_scalar(row.get(name)) for name in fieldnames})
    return buffer.getvalue()


def _write_lf(path: Path, text: str) -> None:
    if "\r" in text:
        raise ValueError("canonical text contains carriage return")
    path.write_text(text, encoding="utf-8", newline="\n")


def _scan_btc_identity(path: Path) -> tuple[dict[str, Any], set[str]]:
    """Inspect only schema and timestamp identity; no price field is converted."""
    row_count = 0
    timestamp_set: set[str] = set()
    first_timestamp: str | None = None
    last_timestamp: str | None = None
    previous: datetime | None = None
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = tuple(next(reader))
        except StopIteration as exc:
            raise ValueError("BTC source is empty") from exc
        if header != SOURCE_COLUMNS:
            raise ValueError(f"BTC ordered schema mismatch: {header}")
        for row in reader:
            if len(row) != len(SOURCE_COLUMNS):
                raise ValueError("BTC row width mismatch")
            timestamp = row[0]
            parsed = _parse_iso_hour(timestamp)
            if previous is not None and parsed <= previous:
                raise ValueError("BTC timestamps must be unique and strictly increasing")
            previous = parsed
            timestamp_set.add(timestamp)
            if first_timestamp is None:
                first_timestamp = timestamp
            last_timestamp = timestamp
            row_count += 1
    if first_timestamp is None or last_timestamp is None:
        raise ValueError("BTC source contains no data rows")
    return (
        {
            "schema": list(SOURCE_COLUMNS),
            "row_count": row_count,
            "first_timestamp": first_timestamp,
            "last_timestamp": last_timestamp,
        },
        timestamp_set,
    )


def _read_transitions(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != TRANSITION_COLUMNS:
            raise ValueError(f"transition ordered schema mismatch: {tuple(reader.fieldnames or ())}")
        rows = list(reader)
    previous_timestamp: datetime | None = None
    seen_ids: set[str] = set()
    seen_anchors: set[str] = set()
    for index, row in enumerate(rows):
        if int(row["transition_ordinal"]) != index:
            raise ValueError("transition ordinals do not reconcile")
        transition_id = row["transition_id"]
        if not transition_id or transition_id in seen_ids:
            raise ValueError("duplicate or empty transition identifier")
        seen_ids.add(transition_id)
        anchor = row["anchor_timestamp"]
        parsed = _parse_iso_hour(anchor)
        if anchor in seen_anchors:
            raise ValueError("duplicate transition anchor")
        seen_anchors.add(anchor)
        if previous_timestamp is not None and parsed <= previous_timestamp:
            raise ValueError("transition anchors must be strictly ordered")
        previous_timestamp = parsed
        prior = row["prior_regime_label"]
        current = row["current_regime_label"]
        if row["ordered_transition"] != f"{prior} -> {current}":
            raise ValueError("ordered transition field mismatch")
    return rows


def preflight_sources(
    paths: SourcePaths,
    *,
    repo_root: Path,
    contract: FrozenContract = DEFAULT_CONTRACT,
) -> dict[str, Any]:
    """Fail-closed governed preflight without outcome or price calculations."""
    for path in (paths.manifest, paths.feasibility, paths.transitions, paths.btc):
        if not path.exists() or not path.is_file():
            raise RuntimeError(f"governed source missing: {_repo_path(path, repo_root)}")

    if paths.btc.stat().st_size != contract.btc_byte_count:
        raise RuntimeError("governed BTC source byte-count mismatch")
    btc_digest = sha256_file(paths.btc)
    if btc_digest != contract.btc_sha256:
        raise RuntimeError("governed BTC source SHA-256 mismatch")

    manifest = _strict_load_json(paths.manifest)
    feasibility = _strict_load_json(paths.feasibility)
    if not isinstance(manifest, dict) or not isinstance(feasibility, dict):
        raise RuntimeError("governed JSON root must be an object")

    expected_files = manifest.get("files")
    if not isinstance(expected_files, dict):
        raise RuntimeError("Campaign #46 manifest missing file digests")
    for name, path in (
        ("btc_hourly_regime_support_feasibility.json", paths.feasibility),
        ("btc_hourly_regime_transitions.csv", paths.transitions),
    ):
        expected = expected_files.get(name)
        if expected != sha256_file(path):
            raise RuntimeError(f"Campaign #46 artifact digest mismatch: {name}")

    source_manifest = manifest.get("source")
    counts_manifest = manifest.get("counts")
    if not isinstance(source_manifest, dict) or not isinstance(counts_manifest, dict):
        raise RuntimeError("Campaign #46 manifest source/counts missing")
    manifest_source_checks = {
        "sha256": contract.btc_sha256,
        "byte_count": contract.btc_byte_count,
        "row_count": contract.btc_row_count,
        "first_timestamp": contract.btc_first_timestamp,
        "last_timestamp": contract.btc_last_timestamp,
    }
    for key, expected in manifest_source_checks.items():
        if source_manifest.get(key) != expected:
            raise RuntimeError(f"Campaign #46 source manifest mismatch: {key}")
    manifest_count_checks = {
        "transitions": contract.total_transition_count,
        "eligible_transitions": contract.eligible_transition_count,
        "purged_transitions": contract.purged_transition_count,
        "folds": list(contract.partition_counts),
    }
    for key, expected in manifest_count_checks.items():
        if counts_manifest.get(key) != expected:
            raise RuntimeError(f"Campaign #46 count manifest mismatch: {key}")
    if manifest.get("feasibility_status") != contract.feasibility_status:
        raise RuntimeError("Campaign #46 manifest feasibility mismatch")
    if manifest.get("predictive_outcomes_generated") is not False:
        raise RuntimeError("Campaign #46 predictive_outcomes_generated must be false")

    btc_identity, btc_timestamps = _scan_btc_identity(paths.btc)
    for key, expected in (
        ("row_count", contract.btc_row_count),
        ("first_timestamp", contract.btc_first_timestamp),
        ("last_timestamp", contract.btc_last_timestamp),
    ):
        if btc_identity[key] != expected:
            raise RuntimeError(f"BTC timestamp/count evidence mismatch: {key}")

    transitions = _read_transitions(paths.transitions)
    if len(transitions) != contract.total_transition_count:
        raise RuntimeError("total transition count mismatch")
    eligible = [
        row
        for row in transitions
        if "UNKNOWN" not in (row["prior_regime_label"], row["current_regime_label"])
    ]
    if len(eligible) != contract.eligible_transition_count:
        raise RuntimeError("eligible non-UNKNOWN transition count mismatch")

    feasibility_checks = {
        "status": contract.feasibility_status,
        "total_transition_count": contract.total_transition_count,
        "eligible_non_unknown_transition_count": contract.eligible_transition_count,
        "purged_transition_count": contract.purged_transition_count,
        "fold_counts": list(contract.partition_counts),
        "predictive_outcomes_generated": False,
    }
    for key, expected in feasibility_checks.items():
        if feasibility.get(key) != expected:
            raise RuntimeError(f"Campaign #46 feasibility mismatch: {key}")

    assignments = feasibility.get("fold_assignments")
    if not isinstance(assignments, list) or len(assignments) != contract.purged_transition_count:
        raise RuntimeError("frozen purge membership count mismatch")
    by_id = {row["transition_id"]: row for row in transitions}
    seen_assignment_ids: set[str] = set()
    seen_assignment_anchors: set[str] = set()
    previous_assignment_anchor: datetime | None = None
    actual_partition_counts = [0, 0, 0]
    anchor_rows: list[dict[str, Any]] = []
    for assignment in assignments:
        if not isinstance(assignment, dict):
            raise RuntimeError("invalid fold assignment")
        transition_id = assignment.get("transition_id")
        anchor = assignment.get("anchor_timestamp")
        fold = assignment.get("fold")
        if transition_id in seen_assignment_ids or anchor in seen_assignment_anchors:
            raise RuntimeError("duplicate frozen anchor assignment")
        if transition_id not in by_id:
            raise RuntimeError("frozen transition ID missing from transition ledger")
        if not isinstance(fold, int) or fold not in (0, 1, 2):
            raise RuntimeError("invalid frozen partition identifier")
        source_row = by_id[transition_id]
        if source_row["anchor_timestamp"] != anchor:
            raise RuntimeError("frozen anchor timestamp mismatch")
        prior = source_row["prior_regime_label"]
        current = source_row["current_regime_label"]
        if "UNKNOWN" in (prior, current):
            raise RuntimeError("UNKNOWN transition admitted to frozen anchor inventory")
        if prior == current:
            raise RuntimeError("self transition admitted to frozen anchor inventory")
        if source_row["ordered_transition"] != f"{prior} -> {current}":
            raise RuntimeError("candidate field reconciliation failure")
        source_anchor_timestamp = str(anchor).replace("T", " ")
        if source_anchor_timestamp not in btc_timestamps:
            raise RuntimeError("frozen anchor timestamp missing from governed BTC source")
        parsed_anchor = _parse_iso_hour(str(anchor))
        if previous_assignment_anchor is not None and parsed_anchor <= previous_assignment_anchor:
            raise RuntimeError("frozen anchors must be strictly ordered")
        previous_assignment_anchor = parsed_anchor
        seen_assignment_ids.add(str(transition_id))
        seen_assignment_anchors.add(str(anchor))
        actual_partition_counts[fold] += 1
        anchor_rows.append({**source_row, "partition": fold + 1})
    if tuple(actual_partition_counts) != contract.partition_counts:
        raise RuntimeError("frozen partition counts mismatch")

    return {
        "status": "PASS",
        "research_only": True,
        "observation_only": True,
        "predictive_outcomes_generated": False,
        "source": {
            "path": _repo_path(paths.btc, repo_root),
            "sha256": btc_digest,
            "byte_count": paths.btc.stat().st_size,
            **btc_identity,
        },
        "campaign_46": {
            "manifest_path": _repo_path(paths.manifest, repo_root),
            "feasibility_path": _repo_path(paths.feasibility, repo_root),
            "transitions_path": _repo_path(paths.transitions, repo_root),
            "manifest_sha256": sha256_file(paths.manifest),
            "feasibility_sha256": sha256_file(paths.feasibility),
            "transitions_sha256": sha256_file(paths.transitions),
            "feasibility_status": contract.feasibility_status,
        },
        "counts": {
            "total_transitions": len(transitions),
            "eligible_non_unknown_transitions": len(eligible),
            "purged_transitions": len(anchor_rows),
            "partitions": actual_partition_counts,
        },
        "anchors": anchor_rows,
    }


def candidate_id(prior_regime: str, current_regime: str, horizon_hours: int) -> str:
    if "UNKNOWN" in (prior_regime, current_regime) or prior_regime == current_regime:
        raise ValueError("candidate must be non-UNKNOWN and non-self")
    if horizon_hours not in HORIZONS:
        raise ValueError("unsupported horizon")
    key = f"campaign45|P-003|{prior_regime}|{current_regime}|{horizon_hours}"
    return sha256_bytes(key.encode("utf-8"))


def build_candidate_inventory(anchor_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    categories = sorted(
        {
            (str(row["prior_regime_label"]), str(row["current_regime_label"]))
            for row in anchor_rows
            if "UNKNOWN" not in (row["prior_regime_label"], row["current_regime_label"])
            and row["prior_regime_label"] != row["current_regime_label"]
        }
    )
    inventory: list[dict[str, Any]] = []
    ordinal = 0
    for prior, current in categories:
        for horizon in HORIZONS:
            inventory.append(
                {
                    "candidate_id": candidate_id(prior, current, horizon),
                    "candidate_ordinal": ordinal,
                    "predictor_class": "P-003",
                    "prior_regime_label": prior,
                    "current_regime_label": current,
                    "ordered_transition": f"{prior} -> {current}",
                    "horizon_hours": horizon,
                }
            )
            ordinal += 1
    return inventory


def _exact_close_series(btc: pd.DataFrame) -> pd.Series:
    if tuple(btc.columns) != SOURCE_COLUMNS:
        raise ValueError(f"BTC ordered schema mismatch: {tuple(btc.columns)}")
    timestamps = pd.to_datetime(btc["timestamp"], errors="raise")
    if getattr(timestamps.dt, "tz", None) is not None:
        raise ValueError("BTC timestamps must be timezone-naive")
    if timestamps.duplicated().any() or not timestamps.is_monotonic_increasing:
        raise ValueError("BTC timestamps must be unique and strictly increasing")
    close = pd.to_numeric(btc["close"], errors="raise").astype(float)
    if not np.isfinite(close.to_numpy()).all() or (close <= 0).any():
        raise ValueError("BTC closes must be positive and finite")
    return pd.Series(close.to_numpy(), index=pd.DatetimeIndex(timestamps), name="close")


def _exact_window(close: pd.Series, end: pd.Timestamp, hours: int) -> np.ndarray | None:
    expected = pd.date_range(end=end, periods=hours + 1, freq="h")
    values = close.reindex(expected)
    if values.isna().any():
        return None
    array = values.to_numpy(dtype=float)
    return array if np.isfinite(array).all() and (array > 0).all() else None


def compute_anchor_controls(close: pd.Series, anchor: pd.Timestamp) -> tuple[dict[str, float | None], list[str]]:
    controls: dict[str, float | None] = {name: None for name in CONTROL_COLUMNS}
    reasons: list[str] = []
    windows: dict[int, np.ndarray | None] = {
        hours: _exact_window(close, anchor, hours) for hours in HORIZONS
    }
    for hours, name in (
        (24, "trailing_log_return_24h"),
        (72, "trailing_log_return_72h"),
        (168, "trailing_log_return_168h"),
    ):
        window = windows[hours]
        if window is None:
            reasons.append(f"MISSING_EXACT_CONTROL_WINDOW_{hours}H")
        else:
            controls[name] = float(math.log(window[-1] / window[0]))
    for hours, name in ((24, "realized_volatility_24h"), (168, "realized_volatility_168h")):
        window = windows[hours]
        if window is not None:
            hourly = np.diff(np.log(window))
            value = float(math.sqrt(float(np.dot(hourly, hourly))))
            controls[name] = value if math.isfinite(value) else None
            if controls[name] is None:
                reasons.append(f"NONFINITE_REALIZED_VOLATILITY_{hours}H")
    mean_index = pd.date_range(end=anchor, periods=168, freq="h")
    mean_values = close.reindex(mean_index)
    if mean_values.isna().any():
        reasons.append("MISSING_EXACT_CLOSE_MEAN_WINDOW_168H")
    else:
        values = mean_values.to_numpy(dtype=float)
        mean = float(np.mean(values))
        std = float(np.std(values, ddof=0))
        if not math.isfinite(std) or std <= 0:
            reasons.append("INVALID_CLOSE_STANDARD_DEVIATION_168H")
        else:
            distance = float((values[-1] - mean) / std)
            if math.isfinite(distance):
                controls["distance_from_close_mean_168h"] = distance
            else:
                reasons.append("NONFINITE_CLOSE_DISTANCE_168H")
    for name, value in controls.items():
        if value is not None and not math.isfinite(value):
            controls[name] = None
            reasons.append(f"NONFINITE_{name.upper()}")
    return controls, sorted(set(reasons))


def compute_forward_outcomes(
    close: pd.Series,
    anchor: pd.Timestamp,
) -> tuple[dict[int, float | None], dict[int, str | None]]:
    outcomes: dict[int, float | None] = {}
    reasons: dict[int, str | None] = {}
    anchor_value = close.get(anchor, np.nan)
    if not math.isfinite(float(anchor_value)) or float(anchor_value) <= 0:
        for horizon in HORIZONS:
            outcomes[horizon] = None
            reasons[horizon] = "MISSING_EXACT_ANCHOR_TIMESTAMP"
        return outcomes, reasons
    for horizon in HORIZONS:
        target = anchor + pd.Timedelta(hours=horizon)
        horizon_value = close.get(target, np.nan)
        if not math.isfinite(float(horizon_value)) or float(horizon_value) <= 0:
            outcomes[horizon] = None
            reasons[horizon] = "MISSING_EXACT_HORIZON_TIMESTAMP"
        else:
            outcomes[horizon] = float(math.log(float(horizon_value) / float(anchor_value)))
            reasons[horizon] = None
    return outcomes, reasons


def build_anchor_inventory(
    anchor_rows: Sequence[Mapping[str, Any]],
    btc: pd.DataFrame,
) -> list[dict[str, Any]]:
    close = _exact_close_series(btc)
    inventory: list[dict[str, Any]] = []
    seen: set[str] = set()
    previous: pd.Timestamp | None = None
    for ordinal, source in enumerate(anchor_rows):
        anchor_text = str(source["anchor_timestamp"])
        if anchor_text in seen:
            raise ValueError("duplicate anchor inventory timestamp")
        anchor = pd.Timestamp(_parse_iso_hour(anchor_text))
        if previous is not None and anchor <= previous:
            raise ValueError("anchor inventory must be strictly ordered")
        previous = anchor
        seen.add(anchor_text)
        controls, control_reasons = compute_anchor_controls(close, anchor)
        outcomes, outcome_reasons = compute_forward_outcomes(close, anchor)
        row: dict[str, Any] = {
            "anchor_ordinal": ordinal,
            "transition_id": source["transition_id"],
            "anchor_timestamp": anchor_text,
            "partition": int(source["partition"]),
            "prior_regime_label": source["prior_regime_label"],
            "current_regime_label": source["current_regime_label"],
            "ordered_transition": source["ordered_transition"],
            **controls,
            "controls_available": not control_reasons
            and all(controls[name] is not None for name in CONTROL_COLUMNS),
            "control_exclusion_reasons": control_reasons,
        }
        for horizon in HORIZONS:
            row[f"forward_log_return_{horizon}h"] = outcomes[horizon]
            row[f"outcome_available_{horizon}h"] = outcomes[horizon] is not None
            row[f"outcome_exclusion_reason_{horizon}h"] = outcome_reasons[horizon]
        inventory.append(row)
    return inventory


def development_scaling(development: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    values = np.asarray(development, dtype=float)
    if values.ndim != 2 or values.shape[1] != len(CONTROL_COLUMNS):
        raise ValueError("development controls have wrong shape")
    if values.shape[0] == 0 or not np.isfinite(values).all():
        raise ValueError("development controls must be complete and finite")
    means = np.mean(values, axis=0)
    stds = np.std(values, axis=0, ddof=0)
    if not np.isfinite(means).all() or not np.isfinite(stds).all() or np.any(stds <= 0):
        raise ValueError("development control standard deviation must be finite and positive")
    return means, stds


def apply_scaling(values: np.ndarray, means: np.ndarray, stds: np.ndarray) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim != 2 or array.shape[1] != len(CONTROL_COLUMNS):
        raise ValueError("control matrix has wrong shape")
    if not np.isfinite(array).all():
        raise ValueError("control matrix must be finite")
    scaled = (array - means) / stds
    if not np.isfinite(scaled).all():
        raise ValueError("scaled controls are non-finite")
    return scaled


def ols_hc3(y: np.ndarray, candidate: np.ndarray, controls: np.ndarray) -> OLSResult:
    outcome = np.asarray(y, dtype=float).reshape(-1)
    indicator = np.asarray(candidate, dtype=float).reshape(-1)
    control_matrix = np.asarray(controls, dtype=float)
    n = outcome.shape[0]
    if control_matrix.shape != (n, len(CONTROL_COLUMNS)) or indicator.shape[0] != n:
        raise ValueError("estimator inputs have incompatible shapes")
    if n <= len(CONTROL_COLUMNS) + 2:
        raise ValueError("insufficient estimator rows")
    if not np.isfinite(outcome).all() or not np.isfinite(indicator).all() or not np.isfinite(control_matrix).all():
        raise ValueError("estimator inputs must be finite")
    if not np.isin(indicator, [0.0, 1.0]).all():
        raise ValueError("candidate indicator must be binary")
    design = np.column_stack([np.ones(n), indicator, control_matrix])
    rank = int(np.linalg.matrix_rank(design))
    if rank != design.shape[1]:
        raise np.linalg.LinAlgError("design matrix is rank deficient")
    xtx_inv = np.linalg.inv(design.T @ design)
    beta = xtx_inv @ design.T @ outcome
    residual = outcome - design @ beta
    leverage = np.einsum("ij,jk,ik->i", design, xtx_inv, design)
    one_minus = 1.0 - leverage
    if not np.isfinite(one_minus).all() or np.any(one_minus <= 0):
        raise ValueError("invalid HC3 leverage")
    adjusted_sq = np.square(residual / one_minus)
    meat = design.T @ (design * adjusted_sq[:, None])
    covariance = xtx_inv @ meat @ xtx_inv
    variance = float(covariance[1, 1])
    coefficient = float(beta[1])
    if not math.isfinite(coefficient) or not math.isfinite(variance) or variance < 0:
        raise ValueError("non-finite OLS/HC3 estimate")
    standard_error = math.sqrt(variance)
    if not math.isfinite(standard_error):
        raise ValueError("non-finite HC3 standard error")
    if standard_error == 0:
        p_value = 0.0 if coefficient != 0 else 1.0
    else:
        p_value = float(2.0 * ndtr(-abs(coefficient / standard_error)))
    critical = 1.959963984540054
    return OLSResult(
        coefficient=coefficient,
        standard_error=standard_error,
        p_value=min(1.0, max(0.0, p_value)),
        confidence_interval_low=coefficient - critical * standard_error,
        confidence_interval_high=coefficient + critical * standard_error,
        approximate_return_difference=float(math.expm1(coefficient)),
        n_obs=n,
        rank=rank,
    )


def binary_side_counts(indicator: Sequence[int | float]) -> dict[str, int]:
    values = np.asarray(indicator, dtype=float)
    return {
        "candidate_present": int(np.sum(values == 1.0)),
        "candidate_absent": int(np.sum(values == 0.0)),
    }


def support_failures(
    *,
    overall_present: int,
    partition_present: Sequence[int],
    binary_samples: Mapping[str, Sequence[int | float]],
) -> list[str]:
    failures: list[str] = []
    if overall_present < 20:
        failures.append(STATUS_OVERALL)
    if len(partition_present) != 3 or any(int(value) < 5 for value in partition_present):
        failures.append(STATUS_PARTITION)
    if any(
        binary_side_counts(values)["candidate_present"] < 5
        or binary_side_counts(values)["candidate_absent"] < 5
        for values in binary_samples.values()
    ):
        failures.append(STATUS_BINARY)
    return failures


def directional_consistency(
    partition_2: float | None,
    partition_3: float | None,
    pooled: float | None,
) -> bool:
    values = (partition_2, partition_3, pooled)
    if any(
        value is None or not math.isfinite(float(value)) or float(value) == 0.0
        for value in values
    ):
        return False
    signs = [math.copysign(1.0, float(value)) for value in values]
    return signs[0] == signs[1] == signs[2]


def benjamini_hochberg(rows: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    eligible: list[tuple[float, str]] = []
    for row in rows:
        if not bool(row.get("rankable")):
            continue
        candidate = str(row["candidate_id"])
        p_value = row.get("pooled_p_value")
        if p_value is None or not math.isfinite(float(p_value)) or not 0.0 <= float(p_value) <= 1.0:
            raise ValueError("rankable pooled p-value must be finite and within [0, 1]")
        eligible.append((float(p_value), candidate))
    eligible.sort(key=lambda item: (item[0], item[1]))
    m = len(eligible)
    adjusted: dict[str, float] = {}
    running = 1.0
    for reverse_index in range(m - 1, -1, -1):
        p_value, candidate = eligible[reverse_index]
        rank = reverse_index + 1
        running = min(running, p_value * m / rank)
        adjusted[candidate] = min(1.0, max(0.0, running))
    return adjusted


def _complete_rows(rows: Sequence[Mapping[str, Any]], horizon: int) -> list[Mapping[str, Any]]:
    outcome_name = f"forward_log_return_{horizon}h"
    complete: list[Mapping[str, Any]] = []
    for row in rows:
        values = [row.get(outcome_name), *[row.get(name) for name in CONTROL_COLUMNS]]
        if all(value is not None and math.isfinite(float(value)) for value in values):
            complete.append(row)
    return complete


def _fit_sample(
    fit_rows: Sequence[Mapping[str, Any]],
    development_rows: Sequence[Mapping[str, Any]],
    *,
    transition: str,
    horizon: int,
    pooled_scaling: bool = False,
) -> tuple[dict[str, Any] | None, str | None]:
    if not fit_rows or not development_rows:
        return None, STATUS_TIMESTAMP
    try:
        development_controls = np.asarray(
            [[float(row[name]) for name in CONTROL_COLUMNS] for row in development_rows],
            dtype=float,
        )
        means, stds = development_scaling(development_controls)
        fit_controls = np.asarray(
            [[float(row[name]) for name in CONTROL_COLUMNS] for row in fit_rows],
            dtype=float,
        )
        scaled = apply_scaling(fit_controls, means, stds)
        indicator = np.asarray(
            [1.0 if row["ordered_transition"] == transition else 0.0 for row in fit_rows]
        )
        sides = binary_side_counts(indicator)
        if sides["candidate_present"] < 5 or sides["candidate_absent"] < 5:
            return None, STATUS_BINARY
        outcome = np.asarray(
            [float(row[f"forward_log_return_{horizon}h"]) for row in fit_rows]
        )
        estimate = ols_hc3(outcome, indicator, scaled)
    except np.linalg.LinAlgError:
        return None, STATUS_SINGULAR
    except ValueError as exc:
        message = str(exc)
        if "standard deviation" in message:
            return None, STATUS_CONTROL
        if "rank deficient" in message:
            return None, STATUS_SINGULAR
        return None, STATUS_ESTIMATOR
    result = {
        "coefficient": estimate.coefficient,
        "standard_error_hc3": estimate.standard_error,
        "p_value_two_sided": estimate.p_value,
        "confidence_interval_95_low": estimate.confidence_interval_low,
        "confidence_interval_95_high": estimate.confidence_interval_high,
        "approximate_return_difference": estimate.approximate_return_difference,
        "n_obs": estimate.n_obs,
        "candidate_present": sides["candidate_present"],
        "candidate_absent": sides["candidate_absent"],
        "control_means": means.tolist(),
        "control_population_standard_deviations": stds.tolist(),
        "scaling_scope": "complete_pooled_eligible_sample"
        if pooled_scaling
        else "development_rows_only",
    }
    return result, None


def evaluate_candidates(
    anchor_inventory: Sequence[Mapping[str, Any]],
    candidate_inventory: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    partitions = {
        number: [row for row in anchor_inventory if int(row["partition"]) == number]
        for number in (1, 2, 3)
    }
    results: list[dict[str, Any]] = []
    for candidate in candidate_inventory:
        transition = str(candidate["ordered_transition"])
        horizon = int(candidate["horizon_hours"])
        all_present = sum(row["ordered_transition"] == transition for row in anchor_inventory)
        partition_present = [
            sum(row["ordered_transition"] == transition for row in partitions[number])
            for number in (1, 2, 3)
        ]
        complete = {
            number: _complete_rows(partitions[number], horizon) for number in (1, 2, 3)
        }
        pooled_rows = _complete_rows(anchor_inventory, horizon)
        binary_samples = {
            "partition_1_development": [
                row["ordered_transition"] == transition for row in complete[1]
            ],
            "partition_2_evaluation": [
                row["ordered_transition"] == transition for row in complete[2]
            ],
            "partitions_1_2_development": [
                row["ordered_transition"] == transition
                for row in complete[1] + complete[2]
            ],
            "partition_3_evaluation": [
                row["ordered_transition"] == transition for row in complete[3]
            ],
            "pooled": [row["ordered_transition"] == transition for row in pooled_rows],
        }
        failures = support_failures(
            overall_present=all_present,
            partition_present=partition_present,
            binary_samples=binary_samples,
        )
        fits: dict[str, Any] = {
            "partition_1_development": None,
            "partition_2_evaluation": None,
            "partition_3_evaluation": None,
            "pooled": None,
        }
        if not failures:
            plans = (
                ("partition_1_development", complete[1], complete[1], False),
                ("partition_2_evaluation", complete[2], complete[1], False),
                (
                    "partition_3_evaluation",
                    complete[3],
                    complete[1] + complete[2],
                    False,
                ),
                ("pooled", pooled_rows, pooled_rows, True),
            )
            for name, fit_rows, development_rows, pooled_scaling in plans:
                fit, failure = _fit_sample(
                    fit_rows,
                    development_rows,
                    transition=transition,
                    horizon=horizon,
                    pooled_scaling=pooled_scaling,
                )
                fits[name] = fit
                if failure is not None:
                    failures.append(failure)
        failures = sorted(set(failures))
        rankable = not failures and all(fits[name] is not None for name in fits)
        pooled_fit = fits["pooled"] if rankable else None
        p2_fit = fits["partition_2_evaluation"] if rankable else None
        p3_fit = fits["partition_3_evaluation"] if rankable else None
        result = {
            **dict(candidate),
            "overall_candidate_present": int(all_present),
            "partition_candidate_present": partition_present,
            "complete_rows_by_partition": [len(complete[number]) for number in (1, 2, 3)],
            "pooled_complete_rows": len(pooled_rows),
            "rankable": rankable,
            "failure_reasons": failures,
            "fits": fits,
            "pooled_coefficient": None if pooled_fit is None else pooled_fit["coefficient"],
            "pooled_standard_error_hc3": None
            if pooled_fit is None
            else pooled_fit["standard_error_hc3"],
            "pooled_p_value": None if pooled_fit is None else pooled_fit["p_value_two_sided"],
            "pooled_confidence_interval_95_low": None
            if pooled_fit is None
            else pooled_fit["confidence_interval_95_low"],
            "pooled_confidence_interval_95_high": None
            if pooled_fit is None
            else pooled_fit["confidence_interval_95_high"],
            "pooled_approximate_return_difference": None
            if pooled_fit is None
            else pooled_fit["approximate_return_difference"],
            "partition_2_evaluation_coefficient": None
            if p2_fit is None
            else p2_fit["coefficient"],
            "partition_3_evaluation_coefficient": None
            if p3_fit is None
            else p3_fit["coefficient"],
            "directional_consistency": False,
            "bh_adjusted_q_value": None,
            "supported_association": False,
            "status": failures[0] if failures else None,
        }
        if rankable:
            result["directional_consistency"] = directional_consistency(
                result["partition_2_evaluation_coefficient"],
                result["partition_3_evaluation_coefficient"],
                result["pooled_coefficient"],
            )
        results.append(result)

    adjusted = benjamini_hochberg(results)
    for result in results:
        if not result["rankable"]:
            continue
        q_value = adjusted[result["candidate_id"]]
        result["bh_adjusted_q_value"] = q_value
        if q_value <= 0.05 and result["directional_consistency"]:
            result["supported_association"] = True
            result["status"] = STATUS_SUPPORTED
        elif q_value > 0.05:
            result["status"] = STATUS_MULTIPLICITY
        else:
            result["status"] = STATUS_DIRECTION
    return results


def _anchor_csv_columns() -> list[str]:
    columns = [
        "anchor_ordinal",
        "transition_id",
        "anchor_timestamp",
        "partition",
        "prior_regime_label",
        "current_regime_label",
        "ordered_transition",
        *CONTROL_COLUMNS,
        "controls_available",
        "control_exclusion_reasons",
    ]
    for horizon in HORIZONS:
        columns.extend(
            [
                f"forward_log_return_{horizon}h",
                f"outcome_available_{horizon}h",
                f"outcome_exclusion_reason_{horizon}h",
            ]
        )
    return columns


def _candidate_csv_columns() -> list[str]:
    return [
        "candidate_id",
        "candidate_ordinal",
        "predictor_class",
        "prior_regime_label",
        "current_regime_label",
        "ordered_transition",
        "horizon_hours",
    ]


def _result_csv_columns() -> list[str]:
    return _candidate_csv_columns() + [
        "overall_candidate_present",
        "partition_candidate_present",
        "complete_rows_by_partition",
        "pooled_complete_rows",
        "rankable",
        "failure_reasons",
        "pooled_coefficient",
        "pooled_standard_error_hc3",
        "pooled_p_value",
        "pooled_confidence_interval_95_low",
        "pooled_confidence_interval_95_high",
        "pooled_approximate_return_difference",
        "partition_2_evaluation_coefficient",
        "partition_3_evaluation_coefficient",
        "directional_consistency",
        "bh_adjusted_q_value",
        "supported_association",
        "status",
        "fits",
    ]


def build_fold_plan(anchor_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    partitions = {
        str(number): [
            {
                "anchor_ordinal": int(row.get("anchor_ordinal", index)),
                "transition_id": row["transition_id"],
                "anchor_timestamp": row["anchor_timestamp"],
            }
            for index, row in enumerate(anchor_rows)
            if int(row["partition"]) == number
        ]
        for number in (1, 2, 3)
    }
    return {
        "partition_counts": [len(partitions[str(number)]) for number in (1, 2, 3)],
        "partitions": partitions,
        "evaluations": [
            {
                "evaluation": "partition_2",
                "development_partitions": [1],
                "evaluation_partition": 2,
                "scaling_scope": "development_rows_only",
            },
            {
                "evaluation": "partition_3",
                "development_partitions": [1, 2],
                "evaluation_partition": 3,
                "scaling_scope": "development_rows_only",
            },
        ],
        "pooled_scaling_scope": "complete_pooled_eligible_sample",
        "partition_recalculation_allowed": False,
    }


def build_report(results: Sequence[Mapping[str, Any]], preflight: Mapping[str, Any]) -> str:
    rankable = sum(bool(row["rankable"]) for row in results)
    supported = sum(bool(row["supported_association"]) for row in results)
    return (
        "# Campaign #45 — Historical Regime State and Transition Discovery\n\n"
        "## Safety boundary\n\n"
        "Research-only, observation-only, anchor-local, leakage-safe, deterministic, replay-safe, and fail-closed. "
        "No runtime, regime, threshold, strategy, signal, order, execution, portfolio, NAV, exposure, dashboard, or model-training behavior is changed.\n\n"
        "## Governed source reconciliation\n\n"
        f"- Total transitions: {preflight['counts']['total_transitions']}\n"
        f"- Eligible non-UNKNOWN transitions: {preflight['counts']['eligible_non_unknown_transitions']}\n"
        f"- Frozen 168-hour-purged anchors: {preflight['counts']['purged_transitions']}\n"
        f"- Frozen partitions: {preflight['counts']['partitions']}\n\n"
        "## Confirmatory family\n\n"
        f"- Candidate-horizon tests: {len(results)}\n"
        f"- Rankable pooled tests in the single BH family: {rankable}\n"
        f"- Supported research associations: {supported}\n\n"
        "A supported association is not an alpha, strategy, deployability, or economic-use claim.\n"
    )


def generate_canonical_outputs(
    paths: SourcePaths,
    *,
    repo_root: Path,
    output_dir: Path,
    contract: FrozenContract = DEFAULT_CONTRACT,
) -> dict[str, Any]:
    before = {
        path: sha256_file(path)
        for path in (paths.manifest, paths.feasibility, paths.transitions, paths.btc)
    }
    preflight = preflight_sources(paths, repo_root=repo_root, contract=contract)
    btc = pd.read_csv(paths.btc)
    anchor_inventory = build_anchor_inventory(preflight["anchors"], btc)
    candidate_inventory = build_candidate_inventory(anchor_inventory)
    fold_plan = build_fold_plan(anchor_inventory)
    results = evaluate_candidates(anchor_inventory, candidate_inventory)

    if output_dir.exists() and any(output_dir.iterdir()):
        raise RuntimeError(
            f"output directory must not exist or must be empty: {_repo_path(output_dir, repo_root)}"
        )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output_dir.parent) as temporary:
        stage = Path(temporary) / output_dir.name
        stage.mkdir()
        source_manifest = {key: value for key, value in preflight.items() if key != "anchors"}
        source_manifest.update(
            {
                "outcomes_generated": True,
                "outcome_definition": "log(exact_horizon_close / exact_anchor_close)",
                "horizons_hours": list(HORIZONS),
                "control_columns": list(CONTROL_COLUMNS),
                "realized_volatility_definition": "square_root_of_sum_of_squared_hourly_log_returns",
                "pooled_scaling_distinction": "complete pooled eligible sample; descriptive pooled confirmatory fit",
            }
        )
        _write_lf(stage / OUTPUT_FILENAMES[0], json_text(source_manifest))
        _write_lf(stage / OUTPUT_FILENAMES[1], json_text(anchor_inventory))
        _write_lf(stage / OUTPUT_FILENAMES[2], csv_text(anchor_inventory, _anchor_csv_columns()))
        _write_lf(stage / OUTPUT_FILENAMES[3], json_text(candidate_inventory))
        _write_lf(stage / OUTPUT_FILENAMES[4], csv_text(candidate_inventory, _candidate_csv_columns()))
        _write_lf(stage / OUTPUT_FILENAMES[5], json_text(fold_plan))
        _write_lf(stage / OUTPUT_FILENAMES[6], json_text(results))
        _write_lf(stage / OUTPUT_FILENAMES[7], csv_text(results, _result_csv_columns()))
        _write_lf(stage / OUTPUT_FILENAMES[8], build_report(results, preflight))
        files_before_manifest = sorted(path.name for path in stage.iterdir())
        manifest = {
            "experiment": "campaign_45_historical_regime_state_and_transition_discovery",
            "research_only": True,
            "observation_only": True,
            "runtime_mutation_allowed": False,
            "regime_mutation_allowed": False,
            "threshold_mutation_allowed": False,
            "strategy_mutation_allowed": False,
            "signal_mutation_allowed": False,
            "order_mutation_allowed": False,
            "execution_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "nav_mutation_allowed": False,
            "exposure_mutation_allowed": False,
            "dashboard_mutation_allowed": False,
            "model_training_allowed": False,
            "counts": {
                "anchors": len(anchor_inventory),
                "partitions": preflight["counts"]["partitions"],
                "candidates": len(candidate_inventory),
                "rankable_candidates": sum(bool(row["rankable"]) for row in results),
                "supported_associations": sum(
                    bool(row["supported_association"]) for row in results
                ),
            },
            "files": {name: sha256_file(stage / name) for name in files_before_manifest},
        }
        canonical = json.dumps(
            manifest, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        manifest["aggregate_payload_digest"] = sha256_bytes(canonical)
        _write_lf(stage / OUTPUT_FILENAMES[9], json_text(manifest))
        after = {path: sha256_file(path) for path in before}
        if before != after:
            raise RuntimeError("governed source bytes changed during generation")
        if output_dir.exists():
            output_dir.rmdir()
        shutil.move(str(stage), str(output_dir))
    return {
        "status": "PASS",
        "output": _repo_path(output_dir, repo_root),
        "counts": manifest["counts"],
        "outcomes_generated": True,
    }
