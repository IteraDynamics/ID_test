from __future__ import annotations

"""Fail-closed governed-source preflight for Campaign #43.

This increment validates source identity and structure only. It does not calculate,
rank, serialize, or publish predictive results.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any

import pandas as pd

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from research.ml.validation.historical_alpha_discovery import (
    HistoricalAlphaDiscoveryValidationError,
    order_event_families,
    validate_candidate_inventory,
    validate_price_series,
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
        "path": "artifacts/jump_risk_portfolio_v0/20260716T125121Z_jump-risk-portfolio-integration-v0/predictions/btc_extended_up.csv",
        "sha256": "36b6ffcc9e993f4869dd8f75cde13e7058e101949a577bd24c84e79e58f1dca7",
        "kind": "price_csv",
        "rows": 52453,
        "first": "2020-01-01 01:00:00",
        "last": "2025-12-26 00:00:00",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate Campaign #43 governed source identity and structure only."
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
        help="Required safety flag. Campaign #43 result generation is not implemented in this increment.",
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


def _validate_source(name: str, spec: dict[str, Any], root: Path) -> dict[str, Any]:
    relative = str(spec["path"])
    path = _require_source(root, relative)
    actual_hash = sha256_path(path)
    if actual_hash != spec["sha256"]:
        raise HistoricalAlphaDiscoveryValidationError(
            f"governed source SHA-256 mismatch for {name}: {relative}"
        )

    kind = spec["kind"]
    evidence: dict[str, Any] = {
        "artifact": relative,
        "sha256": actual_hash,
    }

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
            required = {"family_id", "family_ordinal", "episode_id", "window_end"}
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
        frame = pd.read_csv(path, index_col=0)
        close = validate_price_series(frame)
        if len(close) != int(spec["rows"]):
            raise HistoricalAlphaDiscoveryValidationError(
                "btc_hourly row count does not match frozen evidence"
            )
        if str(close.index[0]) != spec["first"]:
            raise HistoricalAlphaDiscoveryValidationError(
                "btc_hourly first timestamp does not match frozen evidence"
            )
        if str(close.index[-1]) != spec["last"]:
            raise HistoricalAlphaDiscoveryValidationError(
                "btc_hourly last timestamp does not match frozen evidence"
            )
        evidence.update(
            {
                "row_count": len(close),
                "first_timestamp": str(close.index[0]),
                "last_timestamp": str(close.index[-1]),
                "price_column": "close",
                "timezone_convention": "timezone-naive"
                if close.index.tz is None
                else str(close.index.tz),
            }
        )
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
    hashes_after = {
        name: sha256_path(_require_source(root, str(spec["path"])))
        for name, spec in sorted(SOURCE_SPECS.items())
    }
    if hashes_before != hashes_after:
        raise HistoricalAlphaDiscoveryValidationError(
            "governed source mutation detected during preflight"
        )

    return {
        "experiment": "core_v1_historical_alpha_discovery",
        "phase": "source_preflight_only",
        "research_only": True,
        "observation_only": True,
        "runtime_integration_allowed": False,
        "exposure_mutation_allowed": False,
        "candidate_inventory_valid": True,
        "sources": evidence,
        "source_count": len(evidence),
        "predictive_results_generated": False,
    }


def main() -> None:
    args = parse_args()
    result = run_preflight(Path(args.repository_root))
    print("Campaign #43 governed source preflight passed")
    print(f"Sources validated: {result['source_count']}")
    print("Predictive results generated: false")
    print("Observation only: no runtime, threshold, order, NAV, or exposure changed.")


if __name__ == "__main__":
    main()
