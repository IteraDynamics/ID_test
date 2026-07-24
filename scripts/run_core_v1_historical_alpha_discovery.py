from __future__ import annotations

"""Fail-closed governed-source preflight for Campaign #43-R1.

This increment validates source identity, structure, numeric integrity, and exact
anchor/horizon coverage only. It does not calculate, rank, serialize, or publish
predictive results.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from research.ml.validation.historical_alpha_discovery import (
    HORIZON_HOURS,
    HistoricalAlphaDiscoveryValidationError,
    order_event_families,
    validate_candidate_inventory,
    validate_price_series,
)

PRICE_COLUMNS: tuple[str, ...] = (
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
)

SOURCE_SPECS: dict[str, dict[str, Any]] = {
    "historical_configuration": {
        "path": "artifacts/core_v1_jump_risk_historical_regimes/btc_extended_up_historical_regimes.json",
        "sha256": "0c1ebc70007570cb7172f2a46283ab25128e1911ac34f447cc5f306c211d3a17",
        "kind": "json_object",
    },
    "historical_episodes": {
        "path": "artifacts/core_v1_jump_risk_historical_regimes/btc_extended_up_historical_episodes.csv",
        "sha256": "6eaadd0fd6d2231d517e5062f15bf5ea92f6bd40e3a1b1aded415e891596c143",
        "kind": "csv",
        "rows": 122,
    },
    "episode_signatures": {
        "path": "artifacts/core_v1_jump_risk_recovery_subtypes/btc_extended_up_episode_signatures.csv",
        "sha256": "ccb0b748b82f7a6449b9caf945b904bfaa4871cdf2a35413c9157c41890e2327",
        "kind": "csv",
        "rows": 122,
    },
    "event_families": {
        "path": "artifacts/core_v1_historical_event_families/btc_extended_up_event_families.json",
        "sha256": "be4fc3e45f8728313a714cd5f4ea932e6822dcea138f145126f9b0392756e584",
        "kind": "families",
        "rows": 14,
    },
    "event_family_membership": {
        "path": "artifacts/core_v1_historical_event_families/btc_extended_up_event_family_membership.csv",
        "sha256": "6bba0128dac682194da20126e1c36c81a38e809c8f8867e1a5946747e692f744",
        "kind": "membership",
        "rows": 122,
    },
    "event_robustness": {
        "path": "artifacts/core_v1_event_robustness/btc_extended_up_event_robustness.json",
        "sha256": "578d8e7c0176489ff5b67761b48ece8bac3285ba06b70ae6ee5d8fe93abb0dc7",
        "kind": "json_object",
    },
    "btc_hourly": {
        "path": "data/btcusd_3600s_2018-01-01_to_2025-12-31.csv",
        "sha256": "d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079",
        "kind": "price_csv",
        "bytes": 4792028,
        "rows": 70069,
        "columns": PRICE_COLUMNS,
        "first": "2018-01-01 00:00:00",
        "last": "2025-12-31 00:00:00",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate Campaign #43-R1 governed source identity and structure only."
    )
    parser.add_argument(
        "--repository-root",
        default=str(REPOSITORY_ROOT),
        help="Repository root containing the frozen repository-relative source paths.",
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        required=True,
        help="Required safety flag. Campaign #43-R1 result generation is prohibited in this increment.",
    )
    return parser.parse_args()


def sha256_path(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_source(root: Path, relative_path: str) -> Path:
    if Path(relative_path).is_absolute() or ".." in Path(relative_path).parts:
        raise HistoricalAlphaDiscoveryValidationError(
            f"governed source path must be repository-relative: {relative_path}"
        )
    path = root / relative_path
    if not path.is_file():
        raise HistoricalAlphaDiscoveryValidationError(
            f"missing governed source: {relative_path}"
        )
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
        raise HistoricalAlphaDiscoveryValidationError(
            "btc_hourly contains duplicate timestamps"
        )
    if not timestamps.is_monotonic_increasing:
        raise HistoricalAlphaDiscoveryValidationError(
            "btc_hourly timestamps must be strictly increasing"
        )
    if not (
        (timestamps.minute == 0)
        & (timestamps.second == 0)
        & (timestamps.microsecond == 0)
        & (timestamps.nanosecond == 0)
    ).all():
        raise HistoricalAlphaDiscoveryValidationError(
            "btc_hourly timestamps must be exactly hour-aligned"
        )
    if str(timestamps[0]) != spec["first"]:
        raise HistoricalAlphaDiscoveryValidationError(
            "btc_hourly first timestamp does not match frozen evidence"
        )
    if str(timestamps[-1]) != spec["last"]:
        raise HistoricalAlphaDiscoveryValidationError(
            "btc_hourly last timestamp does not match frozen evidence"
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
    missing_hours = int(
        sum(int(delta / pd.Timedelta(hours=1)) - 1 for delta in discontinuities)
    )

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
    close: pd.Series,
    episodes: pd.DataFrame,
    membership: pd.DataFrame,
) -> dict[str, Any]:
    episode_required = {"window_start", "window_end"}
    membership_required = {"family_id", "episode_id", "window_start", "window_end"}
    episode_missing = sorted(episode_required - set(episodes.columns))
    membership_missing = sorted(membership_required - set(membership.columns))
    if episode_missing:
        raise HistoricalAlphaDiscoveryValidationError(
            f"historical episodes missing required columns: {episode_missing}"
        )
    if membership_missing:
        raise HistoricalAlphaDiscoveryValidationError(
            f"membership missing coverage columns: {membership_missing}"
        )

    episode_starts = _parse_naive_timestamps(
        episodes["window_start"], "historical episode window_start"
    )
    episode_ends = _parse_naive_timestamps(
        episodes["window_end"], "historical episode window_end"
    )
    membership_starts = _parse_naive_timestamps(
        membership["window_start"], "membership window_start"
    )
    membership_ends = _parse_naive_timestamps(
        membership["window_end"], "membership window_end"
    )

    episode_windows = set(zip(episode_starts, episode_ends, strict=True))
    membership_windows = set(zip(membership_starts, membership_ends, strict=True))
    if episode_windows != membership_windows:
        raise HistoricalAlphaDiscoveryValidationError(
            "historical episode windows do not reconcile to membership"
        )

    episode_anchors = _parse_naive_timestamps(
        membership["window_end"], "episode window_end"
    )
    family_rows = membership.copy()
    family_rows["_window_end"] = episode_anchors
    family_anchors = pd.DatetimeIndex(
        family_rows.groupby("family_id", sort=True)["_window_end"].max().tolist()
    )
    if len(family_anchors) != 14:
        raise HistoricalAlphaDiscoveryValidationError(
            "membership must reconcile to exactly 14 family anchors"
        )

    close_index = close.index

    def summarize(anchors: pd.DatetimeIndex) -> dict[str, Any]:
        result: dict[str, Any] = {
            "observation_count": len(anchors),
            "anchors_missing": int((~anchors.isin(close_index)).sum()),
            "unavailable_by_horizon": {},
        }
        for horizon in HORIZON_HOURS:
            unavailable = 0
            for anchor in anchors:
                expected = pd.date_range(anchor, periods=horizon + 1, freq="1h")
                if not expected.isin(close_index).all():
                    unavailable += 1
            result["unavailable_by_horizon"][str(horizon)] = unavailable
        return result

    episode_coverage = summarize(episode_anchors)
    family_coverage = summarize(family_anchors)
    if episode_coverage["anchors_missing"] or family_coverage["anchors_missing"]:
        raise HistoricalAlphaDiscoveryValidationError(
            "governed episode or family anchor is absent from btc_hourly"
        )
    unavailable = sum(episode_coverage["unavailable_by_horizon"].values()) + sum(
        family_coverage["unavailable_by_horizon"].values()
    )
    if unavailable:
        raise HistoricalAlphaDiscoveryValidationError(
            "governed episode or family horizon coverage is unavailable"
        )

    return {
        "episode": episode_coverage,
        "family": family_coverage,
        "episode_windows_not_in_membership": 0,
        "membership_windows_not_in_episodes": 0,
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
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise HistoricalAlphaDiscoveryValidationError(
                f"{name} must contain one JSON object"
            )
        evidence["object_count"] = 1
    elif kind == "families":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise HistoricalAlphaDiscoveryValidationError(
                "event_families must contain a JSON array"
            )
        ordered = order_event_families(payload)
        if len(ordered) != int(spec["rows"]):
            raise HistoricalAlphaDiscoveryValidationError(
                "event_families count does not match frozen evidence"
            )
        evidence["row_count"] = len(ordered)
    elif kind in {"csv", "membership"}:
        frame = pd.read_csv(path)
        if len(frame) != int(spec["rows"]):
            raise HistoricalAlphaDiscoveryValidationError(
                f"{name} row count does not match frozen evidence"
            )
        if kind == "membership":
            required = {
                "family_id",
                "family_ordinal",
                "episode_id",
                "window_start",
                "window_end",
            }
            missing = sorted(required - set(frame.columns))
            if missing:
                raise HistoricalAlphaDiscoveryValidationError(
                    f"membership missing required columns: {missing}"
                )
            if frame["episode_id"].duplicated().any():
                raise HistoricalAlphaDiscoveryValidationError(
                    "membership contains duplicate episode_id"
                )
            if frame["family_id"].nunique() != 14:
                raise HistoricalAlphaDiscoveryValidationError(
                    "membership must reconcile to exactly 14 families"
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


def run_preflight(repository_root: Path) -> dict[str, Any]:
    root = repository_root.resolve()
    if not root.is_dir():
        raise HistoricalAlphaDiscoveryValidationError(
            f"repository root does not exist: {root}"
        )

    validate_candidate_inventory(
        (
            "collapse_severity",
            "feature_displacement",
            "volatility_state",
            "intrinsic_subtype",
        )
    )

    hashes_before = {
        name: sha256_path(_require_source(root, str(spec["path"])))
        for name, spec in sorted(SOURCE_SPECS.items())
    }
    evidence = {
        name: _validate_source(name, spec, root)
        for name, spec in sorted(SOURCE_SPECS.items())
    }

    price_path = _require_source(root, str(SOURCE_SPECS["btc_hourly"]["path"]))
    close, _ = _validate_price_frame(price_path, SOURCE_SPECS["btc_hourly"])
    episodes = pd.read_csv(
        _require_source(root, str(SOURCE_SPECS["historical_episodes"]["path"]))
    )
    membership = pd.read_csv(
        _require_source(root, str(SOURCE_SPECS["event_family_membership"]["path"]))
    )
    coverage = _validate_exact_coverage(close, episodes, membership)

    hashes_after = {
        name: sha256_path(_require_source(root, str(spec["path"])))
        for name, spec in sorted(SOURCE_SPECS.items())
    }
    if hashes_before != hashes_after:
        raise HistoricalAlphaDiscoveryValidationError(
            "governed source mutation detected during preflight"
        )

    return {
        "experiment": "core_v1_historical_alpha_discovery_r1",
        "phase": "source_preflight_only",
        "research_only": True,
        "observation_only": True,
        "runtime_integration_allowed": False,
        "exposure_mutation_allowed": False,
        "candidate_inventory_valid": True,
        "sources": evidence,
        "coverage": coverage,
        "source_count": len(evidence),
        "predictive_results_generated": False,
    }


def main() -> None:
    args = parse_args()
    result = run_preflight(Path(args.repository_root))
    print("Campaign #43-R1 governed source preflight passed")
    print(f"Sources validated: {result['source_count']}")
    print("Episode observations covered: 122")
    print("Family observations covered: 14")
    print("Predictive results generated: false")
    print("Observation only: no runtime, threshold, order, NAV, or exposure changed.")


if __name__ == "__main__":
    main()
