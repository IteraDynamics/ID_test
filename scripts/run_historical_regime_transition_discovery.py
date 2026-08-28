#!/usr/bin/env python
"""Governed Campaign #45 historical regime-transition discovery runner."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from research.ml.validation.historical_regime_transition_discovery import (
    DEFAULT_CONTRACT,
    SourcePaths,
    generate_canonical_outputs,
    preflight_sources,
)

SOURCE_DIR = REPO_ROOT / "artifacts/full_historical_regime_state_sequence"
PATHS = SourcePaths(
    manifest=SOURCE_DIR / "btc_hourly_regime_state_manifest.json",
    feasibility=SOURCE_DIR / "btc_hourly_regime_support_feasibility.json",
    transitions=SOURCE_DIR / "btc_hourly_regime_transitions.csv",
    btc=REPO_ROOT / "data/btcusd_3600s_2018-01-01_to_2025-12-31.csv",
)
OUTPUT_DIR = REPO_ROOT / "artifacts/historical_regime_transitions"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deterministic, research-only Campaign #45 discovery runner."
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Reconcile frozen source identities and stop before outcome construction.",
    )
    args = parser.parse_args()

    if args.preflight_only:
        evidence = preflight_sources(PATHS, repo_root=REPO_ROOT, contract=DEFAULT_CONTRACT)
        payload = {
            "status": evidence["status"],
            "predictive_outcomes_generated": False,
            "counts": evidence["counts"],
            "source": {
                "path": evidence["source"]["path"],
                "sha256": evidence["source"]["sha256"],
                "byte_count": evidence["source"]["byte_count"],
                "row_count": evidence["source"]["row_count"],
                "first_timestamp": evidence["source"]["first_timestamp"],
                "last_timestamp": evidence["source"]["last_timestamp"],
            },
            "campaign_46": {
                "feasibility_status": evidence["campaign_46"]["feasibility_status"],
            },
        }
        print(json.dumps(payload, sort_keys=True, allow_nan=False))
        return 0

    result = generate_canonical_outputs(
        PATHS,
        repo_root=REPO_ROOT,
        output_dir=OUTPUT_DIR,
        contract=DEFAULT_CONTRACT,
    )
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
