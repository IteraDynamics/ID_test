from __future__ import annotations

"""Campaign #43-R1 governed preflight, deterministic generation, and replay verification."""

import argparse
import csv
from hashlib import sha256
import io
import json
import math
import os
from pathlib import Path
import shutil
import sys
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from research.ml.validation.historical_alpha_discovery import (
    HORIZON_HOURS,
    RANKABLE_DESCRIPTORS,
    HistoricalAlphaDiscoveryValidationError,
    build_forward_outcome,
    evidence_state,
    family_fold_assignments,
    homogeneous_family_value,
    order_event_families,
    rank_candidate_rows,
    sign,
    validate_candidate_inventory,
    validate_price_series,
)
from research.ml.validation.historical_regime_taxonomy import classify_episodes

PRICE_COLUMNS: tuple[str, ...] = (
    "timestamp", "open", "high", "low", "close", "volume",
)
OUTPUT_FILENAMES: tuple[str, ...] = (
    "btc_core_v1_alpha_candidates.json",
    "btc_core_v1_alpha_candidates.csv",
    "btc_core_v1_alpha_discovery_folds.csv",
    "btc_core_v1_alpha_discovery_report.md",
    "btc_core_v1_alpha_discovery_manifest.json",
)
DEFAULT_OUTPUT_DIR = "artifacts/core_v1_historical_alpha_discovery"

SOURCE_SPECS: dict[str, dict[str, Any]] = {
    "historical_configuration": {
        "path": "artifacts/core_v1_jump_risk_historical_regimes/btc_extended_up_historical_regimes.json",
        "sha256": "0c1ebc70007570cb7172f2a46283ab25128e1911ac34f447cc5f306c211d3a17",
        "kind": "json_object",
    },
    "historical_episodes": {
        "path": "artifacts/core_v1_jump_risk_historical_regimes/btc_extended_up_historical_episodes.csv",
        "sha256": "6eaadd0fd6d2231d517e5062f15bf5ea92f6bd40e3a1b1aded415e891596c143",
        "kind": "csv", "rows": 122,
    },
    "episode_signatures": {
        "path": "artifacts/core_v1_jump_risk_recovery_subtypes/btc_extended_up_episode_signatures.csv",
        "sha256": "ccb0b748b82f7a6449b9caf945b904bfaa4871cdf2a35413c9157c41890e2327",
        "kind": "csv", "rows": 122,
    },
    "event_families": {
        "path": "artifacts/core_v1_historical_event_families/btc_extended_up_event_families.json",
        "sha256": "be4fc3e45f8728313a714cd5f4ea932e6822dcea138f145126f9b0392756e584",
        "kind": "families", "rows": 14,
    },
    "event_family_membership": {
        "path": "artifacts/core_v1_historical_event_families/btc_extended_up_event_family_membership.csv",
        "sha256": "6bba0128dac682194da20126e1c36c81a38e809c8f8867e1a5946747e692f744",
        "kind": "membership", "rows": 122,
    },
    "event_robustness": {
        "path": "artifacts/core_v1_event_robustness/btc_extended_up_event_robustness.json",
        "sha256": "578d8e7c0176489ff5b67761b48ece8bac3285ba06b70ae6ee5d8fe93abb0dc7",
        "kind": "json_object",
    },
    "btc_hourly": {
        "path": "data/btcusd_3600s_2018-01-01_to_2025-12-31.csv",
        "sha256": "d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079",
        "kind": "price_csv", "bytes": 4_792_028, "rows": 70_069,
        "columns": PRICE_COLUMNS,
        "first": "2018-01-01 00:00:00", "last": "2025-12-31 00:00:00",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Campaign #43-R1 governed preflight, generation, or replay verification."
    )
    parser.add_argument("--repository-root", default=str(REPOSITORY_ROOT))
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight-only", action="store_true")
    mode.add_argument("--generate", action="store_true")
    mode.add_argument("--verify-replay", metavar="CANONICAL_DIR")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def sha256_path(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_source(root: Path, relative_path: str) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise HistoricalAlphaDiscoveryValidationError(
            f"governed source path must be repository-relative: {relative_path}"
        )
    path = root / relative
    if not path.is_file():
        raise HistoricalAlphaDiscoveryValidationError(f"missing governed source: {relative_path}")
    return path


def _parse_naive_timestamps(values: pd.Series, field: str) -> pd.DatetimeIndex:
    try:
        parsed = pd.to_datetime(values, errors="raise")
    except (TypeError, ValueError) as exc:
        raise HistoricalAlphaDiscoveryValidationError(
            f"{field} contains invalid timestamps"
        ) from exc
    index = pd.DatetimeIndex(parsed)
    if index.tz is not None:
        raise HistoricalAlphaDiscoveryValidationError(
            f"{field} must use timezone-naive timestamps"
        )
    return index


def _validate_price_frame(path: Path, spec: dict[str, Any]) -> tuple[pd.Series, dict[str, Any]]:
    if path.stat().st_size != int(spec["bytes"]):
        raise HistoricalAlphaDiscoveryValidationError(
            "btc_hourly byte count does not match frozen evidence"
        )
    frame = pd.read_csv(path)
    expected_columns = tuple(str(column) for column in spec["columns"])
    if tuple(frame.columns) != expected_columns:
        raise HistoricalAlphaDiscoveryValidationError(
            "btc_hourly ordered schema does not match frozen evidence"
        )
    if len(frame) != int(spec["rows"]):
        raise HistoricalAlphaDiscoveryValidationError(
            "btc_hourly row count does not match frozen evidence"
        )
    timestamps = _parse_naive_timestamps(frame["timestamp"], "btc_hourly timestamp")
    if timestamps.has_duplicates:
        raise HistoricalAlphaDiscoveryValidationError("btc_hourly contains duplicate timestamps")
    if not timestamps.is_monotonic_increasing:
        raise HistoricalAlphaDiscoveryValidationError(
            "btc_hourly timestamps must be strictly increasing"
        )
    aligned = (
        (timestamps.minute == 0) & (timestamps.second == 0)
        & (timestamps.microsecond == 0) & (timestamps.nanosecond == 0)
    )
    if not aligned.all():
        raise HistoricalAlphaDiscoveryValidationError(
            "btc_hourly timestamps must be exactly hour-aligned"
        )
    if str(timestamps[0]) != spec["first"] or str(timestamps[-1]) != spec["last"]:
        raise HistoricalAlphaDiscoveryValidationError(
            "btc_hourly timestamp bounds do not match frozen evidence"
        )
    numeric_columns = ("open", "high", "low", "close", "volume")
    numeric = frame.loc[:, numeric_columns].apply(pd.to_numeric, errors="coerce")
    if numeric.isna().any().any():
        raise HistoricalAlphaDiscoveryValidationError(
            "btc_hourly numeric columns must be numeric and non-null"
        )
    values = numeric.to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise HistoricalAlphaDiscoveryValidationError(
            "btc_hourly numeric columns must be finite"
        )
    if (numeric.loc[:, ("open", "high", "low", "close")].to_numpy() <= 0).any():
        raise HistoricalAlphaDiscoveryValidationError(
            "btc_hourly OHLC values must be strictly positive"
        )
    if (numeric["volume"].to_numpy() < 0).any():
        raise HistoricalAlphaDiscoveryValidationError(
            "btc_hourly volume must be nonnegative"
        )
    if (numeric["high"] < numeric[["open", "close", "low"]].max(axis=1)).any():
        raise HistoricalAlphaDiscoveryValidationError(
            "btc_hourly high is inconsistent with OHLC values"
        )
    if (numeric["low"] > numeric[["open", "close", "high"]].min(axis=1)).any():
        raise HistoricalAlphaDiscoveryValidationError(
            "btc_hourly low is inconsistent with OHLC values"
        )
    indexed = numeric.copy()
    indexed.index = timestamps
    close = validate_price_series(indexed)
    deltas = timestamps.to_series(index=timestamps).diff().dropna()
    discontinuities = deltas[deltas != pd.Timedelta(hours=1)]
    missing_hours = int(sum(int(delta / pd.Timedelta(hours=1)) - 1 for delta in discontinuities))
    return close, {
        "byte_count": path.stat().st_size,
        "row_count": len(close),
        "ordered_schema": list(expected_columns),
        "first_timestamp": str(close.index[0]),
        "last_timestamp": str(close.index[-1]),
        "price_column": "close",
        "timezone_convention": "timezone-naive",
        "timestamp_discontinuity_count": int(len(discontinuities)),
        "missing_hour_count": missing_hours,
    }


def _validate_exact_coverage(
    close: pd.Series, episodes: pd.DataFrame, membership: pd.DataFrame
) -> dict[str, Any]:
    episode_required = {"window_start", "window_end"}
    membership_required = {"family_id", "episode_id", "window_start", "window_end"}
    if episode_required - set(episodes.columns):
        raise HistoricalAlphaDiscoveryValidationError("historical episodes missing coverage columns")
    if membership_required - set(membership.columns):
        raise HistoricalAlphaDiscoveryValidationError("membership missing coverage columns")
    episode_starts = _parse_naive_timestamps(episodes["window_start"], "historical episode window_start")
    episode_ends = _parse_naive_timestamps(episodes["window_end"], "historical episode window_end")
    membership_starts = _parse_naive_timestamps(membership["window_start"], "membership window_start")
    membership_ends = _parse_naive_timestamps(membership["window_end"], "membership window_end")
    if set(zip(episode_starts, episode_ends, strict=True)) != set(
        zip(membership_starts, membership_ends, strict=True)
    ):
        raise HistoricalAlphaDiscoveryValidationError(
            "historical episode windows do not reconcile to membership"
        )
    family_rows = membership.copy()
    family_rows["_window_end"] = membership_ends
    family_anchors = pd.DatetimeIndex(
        family_rows.groupby("family_id", sort=True)["_window_end"].max().tolist()
    )
    if len(family_anchors) != 14:
        raise HistoricalAlphaDiscoveryValidationError(
            "membership must reconcile to exactly 14 family anchors"
        )

    def summarize(anchors: pd.DatetimeIndex) -> dict[str, Any]:
        result: dict[str, Any] = {
            "observation_count": len(anchors),
            "anchors_missing": int((~anchors.isin(close.index)).sum()),
            "unavailable_by_horizon": {},
        }
        for horizon in HORIZON_HOURS:
            unavailable = 0
            for anchor in anchors:
                expected = pd.date_range(anchor, periods=horizon + 1, freq="1h")
                if not expected.isin(close.index).all():
                    unavailable += 1
            result["unavailable_by_horizon"][str(horizon)] = unavailable
        return result

    episode_coverage = summarize(membership_ends)
    family_coverage = summarize(family_anchors)
    if episode_coverage["anchors_missing"] or family_coverage["anchors_missing"]:
        raise HistoricalAlphaDiscoveryValidationError(
            "governed episode or family anchor is absent from btc_hourly"
        )
    if sum(episode_coverage["unavailable_by_horizon"].values()) + sum(
        family_coverage["unavailable_by_horizon"].values()
    ):
        raise HistoricalAlphaDiscoveryValidationError(
            "governed episode or family horizon coverage is unavailable"
        )
    return {
        "episode": episode_coverage,
        "family": family_coverage,
        "episode_windows_not_in_membership": 0,
        "membership_windows_not_in_episodes": 0,
    }


def _reconstruct_and_validate_candidate_labels(
    historical: dict[str, Any],
    episodes: pd.DataFrame,
    signatures: pd.DataFrame,
    membership: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    config = historical.get("config")
    if not isinstance(config, dict):
        raise HistoricalAlphaDiscoveryValidationError(
            "historical configuration missing config object"
        )
    for field in ("collapse_ratio", "observation_rows"):
        if field not in config:
            raise HistoricalAlphaDiscoveryValidationError(
                f"historical configuration missing {field}"
            )
    reconstructed = episodes.reset_index(drop=True).copy()
    if "episode_id" not in reconstructed.columns:
        reconstructed.insert(0, "episode_id", reconstructed.index.astype(int))
    try:
        actual_ids = pd.to_numeric(reconstructed["episode_id"], errors="raise").astype("int64")
    except (TypeError, ValueError) as exc:
        raise HistoricalAlphaDiscoveryValidationError(
            "historical episode_id must be deterministic integer row positions"
        ) from exc
    expected_ids = pd.Series(range(len(reconstructed)), dtype="int64")
    if not actual_ids.reset_index(drop=True).equals(expected_ids):
        raise HistoricalAlphaDiscoveryValidationError(
            "historical episode_id does not match deterministic row position"
        )
    reconstructed["episode_id"] = actual_ids
    parsed_recovered = (
        reconstructed["recovered_without_retraining"].astype(str).str.lower()
        .map({"true": True, "false": False})
    )
    if parsed_recovered.isna().any():
        raise HistoricalAlphaDiscoveryValidationError(
            "could not parse recovered_without_retraining values"
        )
    reconstructed["recovered_without_retraining"] = parsed_recovered
    if "episode_id" not in signatures.columns:
        raise HistoricalAlphaDiscoveryValidationError(
            "episode signatures missing episode_id"
        )
    signature_frame = signatures.copy()
    if signature_frame["episode_id"].duplicated().any():
        raise HistoricalAlphaDiscoveryValidationError(
            "episode signatures contain duplicate episode_id"
        )
    signature_frame = signature_frame.set_index("episode_id")
    try:
        signature_frame.index = signature_frame.index.astype("int64")
    except (TypeError, ValueError) as exc:
        raise HistoricalAlphaDiscoveryValidationError(
            "episode signature identifiers must be integers"
        ) from exc
    try:
        classified = classify_episodes(
            reconstructed,
            signature_frame,
            collapse_ratio=float(config["collapse_ratio"]),
            observation_rows=int(config["observation_rows"]),
        )
    except (TypeError, ValueError) as exc:
        raise HistoricalAlphaDiscoveryValidationError(
            f"candidate label reconstruction failed: {exc}"
        ) from exc
    classified["intrinsic_subtype"] = (
        classified["collapse_severity"].astype(str) + "__"
        + classified["feature_displacement"].astype(str) + "__"
        + classified["volatility_state"].astype(str)
    )
    required_membership = {"episode_id", "intrinsic_subtype"}
    if required_membership - set(membership.columns):
        raise HistoricalAlphaDiscoveryValidationError(
            "membership missing candidate reconciliation columns"
        )
    if membership["episode_id"].duplicated().any():
        raise HistoricalAlphaDiscoveryValidationError(
            "membership contains duplicate episode_id"
        )
    governed = membership.loc[:, ["episode_id", "intrinsic_subtype"]].copy()
    governed["episode_id"] = pd.to_numeric(governed["episode_id"], errors="raise").astype("int64")
    governed = governed.sort_values("episode_id", kind="mergesort").reset_index(drop=True)
    derived = classified.loc[:, ["episode_id", "intrinsic_subtype"]].copy()
    derived = derived.sort_values("episode_id", kind="mergesort").reset_index(drop=True)
    if not governed["episode_id"].equals(derived["episode_id"]):
        raise HistoricalAlphaDiscoveryValidationError(
            "reconstructed episode identifiers do not reconcile to membership"
        )
    mismatch = governed["intrinsic_subtype"].astype(str) != derived["intrinsic_subtype"].astype(str)
    if mismatch.any():
        ids = governed.loc[mismatch, "episode_id"].astype(int).tolist()
        raise HistoricalAlphaDiscoveryValidationError(
            f"reconstructed intrinsic_subtype does not reconcile to membership: {ids}"
        )
    return classified, {
        "episode_count": int(len(classified)),
        "membership_count": int(len(governed)),
        "intrinsic_subtype_mismatch_count": 0,
        "descriptor_columns": list(RANKABLE_DESCRIPTORS),
        "episode_id_rule": "zero_based_governed_episode_csv_row_position",
    }


def _validate_source(name: str, spec: dict[str, Any], root: Path) -> dict[str, Any]:
    relative = str(spec["path"])
    path = _require_source(root, relative)
    actual_hash = sha256_path(path)
    if actual_hash != spec["sha256"]:
        raise HistoricalAlphaDiscoveryValidationError(
            f"governed source SHA-256 mismatch for {name}: {relative}"
        )
    kind = spec["kind"]
    evidence: dict[str, Any] = {"artifact": relative, "sha256": actual_hash}
    if kind == "json_object":
        if not isinstance(json.loads(path.read_text(encoding="utf-8")), dict):
            raise HistoricalAlphaDiscoveryValidationError(
                f"{name} must contain one JSON object"
            )
        evidence["object_count"] = 1
    elif kind == "families":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list) or len(order_event_families(payload)) != int(spec["rows"]):
            raise HistoricalAlphaDiscoveryValidationError(
                "event_families count does not match frozen evidence"
            )
        evidence["row_count"] = len(payload)
    elif kind in {"csv", "membership"}:
        frame = pd.read_csv(path)
        if len(frame) != int(spec["rows"]):
            raise HistoricalAlphaDiscoveryValidationError(
                f"{name} row count does not match frozen evidence"
            )
        if kind == "membership":
            required = {
                "family_id", "family_ordinal", "episode_id",
                "window_start", "window_end", "intrinsic_subtype",
            }
            if required - set(frame.columns):
                raise HistoricalAlphaDiscoveryValidationError(
                    "membership missing required columns"
                )
            if frame["episode_id"].duplicated().any() or frame["family_id"].nunique() != 14:
                raise HistoricalAlphaDiscoveryValidationError(
                    "membership identity reconciliation failed"
                )
        evidence["row_count"] = len(frame)
    elif kind == "price_csv":
        _, price_evidence = _validate_price_frame(path, spec)
        evidence.update(price_evidence)
    else:
        raise HistoricalAlphaDiscoveryValidationError(
            f"unknown governed source kind for {name}: {kind}"
        )
    return evidence


def _source_hashes(root: Path) -> dict[str, str]:
    return {
        name: sha256_path(_require_source(root, str(spec["path"])))
        for name, spec in sorted(SOURCE_SPECS.items())
    }


def _load_inputs(root: Path) -> dict[str, Any]:
    return {
        "historical": json.loads(_require_source(
            root, str(SOURCE_SPECS["historical_configuration"]["path"])
        ).read_text(encoding="utf-8")),
        "episodes": pd.read_csv(_require_source(
            root, str(SOURCE_SPECS["historical_episodes"]["path"])
        )),
        "signatures": pd.read_csv(_require_source(
            root, str(SOURCE_SPECS["episode_signatures"]["path"])
        )),
        "families": json.loads(_require_source(
            root, str(SOURCE_SPECS["event_families"]["path"])
        ).read_text(encoding="utf-8")),
        "membership": pd.read_csv(_require_source(
            root, str(SOURCE_SPECS["event_family_membership"]["path"])
        )),
    }


def run_preflight(repository_root: Path) -> dict[str, Any]:
    root = repository_root.resolve()
    if not root.is_dir():
        raise HistoricalAlphaDiscoveryValidationError(
            f"repository root does not exist: {root}"
        )
    validate_candidate_inventory(RANKABLE_DESCRIPTORS)
    hashes_before = _source_hashes(root)
    evidence = {
        name: _validate_source(name, spec, root)
        for name, spec in sorted(SOURCE_SPECS.items())
    }
    inputs = _load_inputs(root)
    _, candidate_reconstruction = _reconstruct_and_validate_candidate_labels(
        inputs["historical"], inputs["episodes"], inputs["signatures"], inputs["membership"]
    )
    close, _ = _validate_price_frame(
        _require_source(root, str(SOURCE_SPECS["btc_hourly"]["path"])),
        SOURCE_SPECS["btc_hourly"],
    )
    coverage = _validate_exact_coverage(close, inputs["episodes"], inputs["membership"])
    if hashes_before != _source_hashes(root):
        raise HistoricalAlphaDiscoveryValidationError(
            "governed source mutation detected during preflight"
        )
    return {
        "experiment": "core_v1_historical_alpha_discovery_r1",
        "phase": "source_preflight_and_candidate_reconstruction",
        "research_only": True,
        "observation_only": True,
        "runtime_integration_allowed": False,
        "exposure_mutation_allowed": False,
        "candidate_inventory_valid": True,
        "candidate_reconstruction": candidate_reconstruction,
        "sources": evidence,
        "coverage": coverage,
        "source_count": len(evidence),
        "predictive_results_generated": False,
    }


def _safe_mean(values: Iterable[float]) -> float:
    numbers = [float(value) for value in values]
    return float(np.mean(numbers)) if numbers else 0.0


def _safe_median(values: Iterable[float]) -> float:
    numbers = [float(value) for value in values]
    return float(np.median(numbers)) if numbers else 0.0


def _positive_rate(values: Iterable[bool]) -> float:
    numbers = [bool(value) for value in values]
    return float(sum(numbers) / len(numbers)) if numbers else 0.0


def _finite_tree(value: Any, path: str = "root") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise HistoricalAlphaDiscoveryValidationError(f"nonfinite canonical value at {path}")
    if isinstance(value, Mapping):
        for key, child in value.items():
            _finite_tree(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _finite_tree(child, f"{path}[{index}]")


def _build_results(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    preflight = run_preflight(root)
    hashes_before = _source_hashes(root)
    inputs = _load_inputs(root)
    classified, reconstruction = _reconstruct_and_validate_candidate_labels(
        inputs["historical"], inputs["episodes"], inputs["signatures"], inputs["membership"]
    )
    membership = inputs["membership"].copy()
    membership["episode_id"] = pd.to_numeric(membership["episode_id"], errors="raise").astype("int64")
    episode_frame = classified.merge(
        membership[["episode_id", "family_id"]],
        on="episode_id", how="inner", validate="one_to_one",
    )
    if len(episode_frame) != 122:
        raise HistoricalAlphaDiscoveryValidationError(
            "candidate observations do not reconcile to 122 episodes"
        )
    episode_frame["anchor_timestamp"] = _parse_naive_timestamps(
        episode_frame["window_end"], "episode anchor"
    )
    ordered_families = order_event_families(inputs["families"])
    fold_records = family_fold_assignments(inputs["families"])
    family_by_id = {str(row["family_id"]): row for row in ordered_families}
    if set(family_by_id) != set(membership["family_id"].astype(str)):
        raise HistoricalAlphaDiscoveryValidationError(
            "event family identities do not reconcile to membership"
        )
    close, _ = _validate_price_frame(
        _require_source(root, str(SOURCE_SPECS["btc_hourly"]["path"])),
        SOURCE_SPECS["btc_hourly"],
    )

    episode_outcomes: dict[tuple[int, int], Any] = {}
    for row in episode_frame.itertuples(index=False):
        for horizon in HORIZON_HOURS:
            episode_outcomes[(int(row.episode_id), horizon)] = build_forward_outcome(
                close, anchor=row.anchor_timestamp, horizon_hours=horizon
            )

    family_outcomes: dict[tuple[str, int], Any] = {}
    for family_id, family in family_by_id.items():
        for horizon in HORIZON_HOURS:
            family_outcomes[(family_id, horizon)] = build_forward_outcome(
                close, anchor=family["_window_end"], horizon_hours=horizon
            )

    fold_roles: dict[int, dict[str, list[str]]] = {
        fold_id: {"train": [], "test": []} for fold_id in range(3)
    }
    for record in fold_records:
        fold_roles[int(record["fold_id"])][str(record["role"])].append(str(record["family_id"]))

    candidate_rows: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    descriptor_mixed_counts: dict[str, int] = {}

    for descriptor in RANKABLE_DESCRIPTORS:
        family_values: dict[str, str | None] = {}
        for family_id, group in episode_frame.groupby("family_id", sort=True):
            family_values[str(family_id)] = homogeneous_family_value(
                group[descriptor].astype(str).tolist()
            )
        descriptor_mixed_counts[descriptor] = sum(
            value is None for value in family_values.values()
        )
        values = sorted(episode_frame[descriptor].astype(str).unique().tolist())
        for candidate_value in values:
            episode_ids = episode_frame.loc[
                episode_frame[descriptor].astype(str) == candidate_value, "episode_id"
            ].astype(int).tolist()
            matching_family_ids = sorted(
                family_id for family_id, value in family_values.items()
                if value == candidate_value
            )
            for horizon in HORIZON_HOURS:
                episode_available = [
                    episode_outcomes[(episode_id, horizon)]
                    for episode_id in episode_ids
                    if episode_outcomes[(episode_id, horizon)] is not None
                ]
                family_available = [
                    family_outcomes[(family_id, horizon)]
                    for family_id in matching_family_ids
                    if family_outcomes[(family_id, horizon)] is not None
                ]
                episode_returns = [outcome.forward_return for outcome in episode_available]
                family_returns = [outcome.forward_return for outcome in family_available]
                aggregate_direction = sign(_safe_median(family_returns))
                supported_fold_count = 0
                training_test_agreement_count = 0
                aggregate_direction_agreement_count = 0

                for fold_id in range(3):
                    train_ids = [
                        family_id for family_id in fold_roles[fold_id]["train"]
                        if family_values.get(family_id) == candidate_value
                        and family_outcomes[(family_id, horizon)] is not None
                    ]
                    test_ids = [
                        family_id for family_id in fold_roles[fold_id]["test"]
                        if family_values.get(family_id) == candidate_value
                        and family_outcomes[(family_id, horizon)] is not None
                    ]
                    train_returns = [
                        family_outcomes[(family_id, horizon)].forward_return
                        for family_id in train_ids
                    ]
                    test_returns = [
                        family_outcomes[(family_id, horizon)].forward_return
                        for family_id in test_ids
                    ]
                    supported = len(train_ids) >= 2 and len(test_ids) >= 1
                    train_direction = sign(_safe_median(train_returns)) if supported else None
                    test_direction = sign(_safe_median(test_returns)) if supported else None
                    if supported:
                        supported_fold_count += 1
                        training_test_agreement_count += int(train_direction == test_direction)
                        aggregate_direction_agreement_count += int(test_direction == aggregate_direction)
                    diagnostics.append({
                        "descriptor": descriptor,
                        "candidate_value": candidate_value,
                        "horizon_hours": horizon,
                        "fold_id": fold_id,
                        "train_family_support": len(train_ids),
                        "test_family_support": len(test_ids),
                        "direction_comparison_supported": supported,
                        "training_direction": train_direction,
                        "test_direction": test_direction,
                        "aggregate_family_direction": aggregate_direction,
                        "training_test_direction_agree": (
                            bool(train_direction == test_direction) if supported else False
                        ),
                        "test_aggregate_direction_agree": (
                            bool(test_direction == aggregate_direction) if supported else False
                        ),
                    })

                episode_median = _safe_median(episode_returns)
                family_median = _safe_median(family_returns)
                state = evidence_state(
                    outcome_available=bool(episode_available or family_available),
                    episode_support=len(episode_available),
                    family_support=len(family_available),
                    supported_fold_count=supported_fold_count,
                    episode_median_return=episode_median,
                    family_median_return=family_median,
                    training_test_agreement_count=training_test_agreement_count,
                    aggregate_direction_agreement_count=aggregate_direction_agreement_count,
                )
                candidate_rows.append({
                    "descriptor": descriptor,
                    "candidate_value": candidate_value,
                    "horizon_hours": horizon,
                    "episode_support": len(episode_available),
                    "unavailable_episode_count": len(episode_ids) - len(episode_available),
                    "family_support": len(family_available),
                    "mixed_family_count": descriptor_mixed_counts[descriptor],
                    "unavailable_homogeneous_family_count": (
                        len(matching_family_ids) - len(family_available)
                    ),
                    "supported_fold_count": supported_fold_count,
                    "episode_mean_forward_return": _safe_mean(episode_returns),
                    "episode_median_forward_return": episode_median,
                    "family_mean_forward_return": _safe_mean(family_returns),
                    "family_median_forward_return": family_median,
                    "episode_positive_return_rate": _positive_rate(
                        outcome.positive_return for outcome in episode_available
                    ),
                    "family_positive_return_rate": _positive_rate(
                        outcome.positive_return for outcome in family_available
                    ),
                    "family_mean_maximum_favorable_excursion": _safe_mean(
                        outcome.maximum_favorable_excursion for outcome in family_available
                    ),
                    "family_mean_maximum_adverse_excursion": _safe_mean(
                        outcome.maximum_adverse_excursion for outcome in family_available
                    ),
                    "family_mean_realized_volatility": _safe_mean(
                        outcome.realized_volatility for outcome in family_available
                    ),
                    "training_test_direction_agreement_count": training_test_agreement_count,
                    "aggregate_direction_agreement_count": aggregate_direction_agreement_count,
                    "episode_family_median_sign_agreement": (
                        sign(episode_median) == sign(family_median)
                    ),
                    "episode_family_median_absolute_divergence": abs(
                        episode_median - family_median
                    ),
                    "evidence_state": state,
                })

    ranked = rank_candidate_rows(candidate_rows)
    diagnostics.sort(
        key=lambda row: (
            row["descriptor"], row["candidate_value"],
            row["horizon_hours"], row["fold_id"],
        )
    )
    if hashes_before != _source_hashes(root):
        raise HistoricalAlphaDiscoveryValidationError(
            "governed source mutation detected during generation"
        )
    metadata = {
        "preflight": preflight,
        "candidate_reconstruction": reconstruction,
        "descriptor_mixed_family_counts": descriptor_mixed_counts,
        "source_hashes": hashes_before,
    }
    _finite_tree(ranked)
    _finite_tree(diagnostics)
    return ranked, diagnostics, metadata


def _json_bytes(payload: Any) -> bytes:
    _finite_tree(payload)
    return (
        json.dumps(payload, sort_keys=True, indent=2, allow_nan=False, ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def _csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    if not rows:
        raise HistoricalAlphaDiscoveryValidationError("canonical CSV rows must not be empty")
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        normalized: dict[str, Any] = {}
        for key, value in row.items():
            if isinstance(value, float):
                if not math.isfinite(value):
                    raise HistoricalAlphaDiscoveryValidationError(
                        f"nonfinite CSV value in {key}"
                    )
                normalized[key] = format(value, ".17g")
            elif value is None:
                normalized[key] = ""
            else:
                normalized[key] = value
        writer.writerow(normalized)
    return buffer.getvalue().encode("utf-8")


def _report_bytes(rows: list[dict[str, Any]], metadata: dict[str, Any]) -> bytes:
    state_counts: dict[str, int] = {}
    for row in rows:
        state = str(row["evidence_state"])
        state_counts[state] = state_counts.get(state, 0) + 1
    lines = [
        "# Core v1 Historical Alpha Discovery Report",
        "",
        "## Governance",
        "",
        "Campaign #43-R1 is deterministic, research-only, observation-only, and fail-closed.",
        "High rank is a prioritization aid for later falsification, not evidence of deployable alpha.",
        "This report makes no production, strategy, threshold, signal, order, portfolio, NAV, exposure, or execution recommendation.",
        "",
        "## Reconciliation",
        "",
        f"- Governed sources: {len(metadata['source_hashes'])}",
        f"- Episodes: {metadata['candidate_reconstruction']['episode_count']}",
        "- Independent event families: 14",
        f"- Rankable candidate rows: {len(rows)}",
        "- Horizons: 2, 6, 24, 72, 168 hours",
        "- Chronological expanding folds: 3",
        "",
        "## Evidence-state counts",
        "",
    ]
    for state in (
        "SUPPORTED_ASSOCIATION", "NULL_ASSOCIATION", "UNSTABLE_OOS",
        "CONTRADICTORY_RESOLUTION", "INSUFFICIENT_SUPPORT", "OUTCOME_UNAVAILABLE",
    ):
        lines.append(f"- `{state}`: {state_counts.get(state, 0)}")
    lines.extend([
        "",
        "## Ranked candidate evidence",
        "",
        "| Rank | State | Descriptor | Value | Horizon | Families | Supported folds | Family median return |",
        "|---:|---|---|---|---:|---:|---:|---:|",
    ])
    for rank, row in enumerate(rows, start=1):
        lines.append(
            f"| {rank} | {row['evidence_state']} | {row['descriptor']} | "
            f"{row['candidate_value']} | {row['horizon_hours']} | "
            f"{row['family_support']} | {row['supported_fold_count']} | "
            f"{row['family_median_forward_return']:.10g} |"
        )
    lines.extend([
        "",
        "All null, contradictory, unstable, insufficient-support, and unavailable evidence remains visible in the canonical outputs.",
        "",
    ])
    return "\n".join(lines).encode("utf-8")


def build_canonical_bytes(repository_root: Path) -> dict[str, bytes]:
    root = repository_root.resolve()
    rows, diagnostics, metadata = _build_results(root)
    candidates_payload = {
        "experiment": "core_v1_historical_alpha_discovery_r1",
        "research_only": True,
        "observation_only": True,
        "candidate_inventory": list(RANKABLE_DESCRIPTORS),
        "aliases": [{
            "descriptor": "activation_ratio_band",
            "alias_of": "collapse_severity",
            "ranked_independently": False,
        }],
        "horizon_hours": list(HORIZON_HOURS),
        "rows": rows,
    }
    payloads: dict[str, bytes] = {
        OUTPUT_FILENAMES[0]: _json_bytes(candidates_payload),
        OUTPUT_FILENAMES[1]: _csv_bytes(rows),
        OUTPUT_FILENAMES[2]: _csv_bytes(diagnostics),
        OUTPUT_FILENAMES[3]: _report_bytes(rows, metadata),
    }
    digest = sha256()
    for filename in sorted(payloads):
        digest.update(filename.encode("utf-8"))
        digest.update(b"\0")
        digest.update(payloads[filename])
    manifest = {
        "experiment": "core_v1_historical_alpha_discovery_r1",
        "research_only": True,
        "observation_only": True,
        "generated_timestamp": None,
        "source_hashes": metadata["source_hashes"],
        "canonical_file_hashes": {
            filename: sha256(content).hexdigest()
            for filename, content in sorted(payloads.items())
        },
        "payload_digest_sha256": digest.hexdigest(),
        "canonical_files": list(OUTPUT_FILENAMES),
        "runtime_threshold_order_nav_exposure_changes": False,
    }
    payloads[OUTPUT_FILENAMES[4]] = _json_bytes(manifest)
    for filename, content in payloads.items():
        if b"\r" in content:
            raise HistoricalAlphaDiscoveryValidationError(
                f"canonical output is not LF-only: {filename}"
            )
    return payloads


def publish_canonical(repository_root: Path, output_dir: Path) -> dict[str, Any]:
    root = repository_root.resolve()
    destination = output_dir if output_dir.is_absolute() else root / output_dir
    destination = destination.resolve()
    if root not in destination.parents:
        raise HistoricalAlphaDiscoveryValidationError(
            "output directory must remain inside repository root"
        )
    if destination.exists():
        if not destination.is_dir() or any(destination.iterdir()):
            raise HistoricalAlphaDiscoveryValidationError(
                "output directory must be newly created or explicitly empty"
            )
        destination.rmdir()
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.parent / f".{destination.name}.staging"
    if staging.exists():
        raise HistoricalAlphaDiscoveryValidationError(
            "staging directory already exists"
        )
    payloads = build_canonical_bytes(root)
    staging.mkdir()
    try:
        for filename, content in payloads.items():
            (staging / filename).write_bytes(content)
        for filename, content in payloads.items():
            if (staging / filename).read_bytes() != content:
                raise HistoricalAlphaDiscoveryValidationError(
                    f"staging verification failed: {filename}"
                )
        os.replace(staging, destination)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return {
        "output_dir": str(destination),
        "file_count": len(payloads),
        "payload_digest_sha256": json.loads(
            (destination / OUTPUT_FILENAMES[4]).read_text(encoding="utf-8")
        )["payload_digest_sha256"],
    }


def verify_replay(repository_root: Path, canonical_dir: Path) -> dict[str, Any]:
    root = repository_root.resolve()
    reference = canonical_dir if canonical_dir.is_absolute() else root / canonical_dir
    reference = reference.resolve()
    if not reference.is_dir():
        raise HistoricalAlphaDiscoveryValidationError(
            f"canonical replay directory does not exist: {reference}"
        )
    actual_names = sorted(path.name for path in reference.iterdir() if path.is_file())
    if actual_names != sorted(OUTPUT_FILENAMES):
        raise HistoricalAlphaDiscoveryValidationError(
            "canonical replay directory file set does not match frozen outputs"
        )
    replay = build_canonical_bytes(root)
    mismatches = [
        filename for filename in OUTPUT_FILENAMES
        if (reference / filename).read_bytes() != replay[filename]
    ]
    if mismatches:
        raise HistoricalAlphaDiscoveryValidationError(
            f"canonical replay byte mismatch: {mismatches}"
        )
    manifest = json.loads((reference / OUTPUT_FILENAMES[4]).read_text(encoding="utf-8"))
    return {
        "byte_identical": True,
        "file_count": len(OUTPUT_FILENAMES),
        "payload_digest_sha256": manifest["payload_digest_sha256"],
    }


def main() -> None:
    args = parse_args()
    root = Path(args.repository_root)
    if args.preflight_only:
        result = run_preflight(root)
        print("Campaign #43-R1 governed source preflight passed")
        print(f"Sources validated: {result['source_count']}")
        print(
            "Candidate labels reconciled: "
            f"{result['candidate_reconstruction']['episode_count']}"
        )
        print("Episode observations covered: 122")
        print("Family observations covered: 14")
        print("Predictive results generated: false")
    elif args.generate:
        result = publish_canonical(root, Path(args.output_dir))
        print("Campaign #43-R1 canonical generation passed")
        print(f"Canonical files published: {result['file_count']}")
        print(f"Payload digest: {result['payload_digest_sha256']}")
        print("Predictive results generated: true")
        print("Results not interpreted by runner.")
    else:
        result = verify_replay(root, Path(args.verify_replay))
        print("Campaign #43-R1 replay verification passed")
        print(f"Byte-identical files: {result['file_count']}")
        print(f"Payload digest: {result['payload_digest_sha256']}")
    print("Observation only: no runtime, threshold, order, NAV, or exposure changed.")


if __name__ == "__main__":
    main()
