#!/usr/bin/env python
"""Governed Campaign #46 source-only regime-state sequence runner."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from research.ml.validation.full_historical_regime_state_sequence import (
    RUN_COLUMNS,
    STATE_COLUMNS,
    TRANSITION_COLUMNS,
    classify_source,
    csv_text,
    json_text,
    sha256_file,
    validate_ohlcv,
)

SOURCE = REPO_ROOT / "data/btcusd_3600s_2018-01-01_to_2025-12-31.csv"
OUTPUT = REPO_ROOT / "artifacts/full_historical_regime_state_sequence"
EXPECTED = {
    "sha256": "d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079",
    "bytes": 4_792_028,
    "rows": 70_069,
    "first": "2018-01-01 00:00:00",
    "last": "2025-12-31 00:00:00",
}


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def preflight() -> tuple[pd.DataFrame, dict]:
    if not SOURCE.exists() or not SOURCE.is_file():
        raise RuntimeError(f"governed source missing: {SOURCE.relative_to(REPO_ROOT)}")
    if SOURCE.stat().st_size != EXPECTED["bytes"]:
        raise RuntimeError("governed source byte-count mismatch")
    if sha256_file(SOURCE) != EXPECTED["sha256"]:
        raise RuntimeError("governed source SHA-256 mismatch")
    df = pd.read_csv(SOURCE)
    evidence = validate_ohlcv(df)
    checks = {
        "row_count": EXPECTED["rows"],
        "first_timestamp": EXPECTED["first"],
        "last_timestamp": EXPECTED["last"],
        "discontinuity_count": 14,
        "missing_timestamp_count": 36,
        "largest_elapsed_hours": 16,
        "largest_missing_timestamp_count": 15,
    }
    for key, expected in checks.items():
        if evidence[key] != expected:
            raise RuntimeError(f"source evidence mismatch for {key}: {evidence[key]} != {expected}")
    return df, evidence


def build_report(summary: dict, evidence: dict, state_count: int, run_count: int) -> str:
    return (
        "# Campaign #46 — Full Historical Regime State Sequence\n\n"
        "## Safety boundary\n\n"
        "Source-only, deterministic, observation-only, replay-safe, and fail-closed. "
        "No predictive outcomes were generated.\n\n"
        "## Source reconciliation\n\n"
        f"- Source rows: {evidence['row_count']}\n"
        f"- State rows: {state_count}\n"
        f"- State runs: {run_count}\n"
        f"- Complete transitions: {summary['total_transition_count']}\n"
        f"- Eligible non-UNKNOWN transitions: {summary['eligible_non_unknown_transition_count']}\n"
        f"- 168-hour purged transitions: {summary['purged_transition_count']}\n"
        f"- Feasibility folds: {summary['fold_counts']}\n\n"
        "## Campaign #45 source feasibility\n\n"
        f"**Status:** `{summary['status']}`\n\n"
        "This status concerns source support only. It is not evidence of alpha, predictive value, or deployability.\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    before_hash = sha256_file(SOURCE) if SOURCE.exists() else None
    df, evidence = preflight()
    if args.preflight_only:
        print(json.dumps({"status": "PASS", "source": evidence}, sort_keys=True))
        return 0
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise RuntimeError(f"output directory must not exist or must be empty: {OUTPUT}")
    states, runs, transitions, folds, summary = classify_source(df)
    with tempfile.TemporaryDirectory(dir=OUTPUT.parent if OUTPUT.parent.exists() else REPO_ROOT) as tmp:
        stage = Path(tmp) / OUTPUT.name
        stage.mkdir(parents=True)
        _write(stage / "btc_hourly_regime_state_sequence.csv", csv_text(states, STATE_COLUMNS))
        _write(stage / "btc_hourly_regime_state_sequence.json", json_text(states))
        _write(stage / "btc_hourly_regime_state_runs.csv", csv_text(runs, RUN_COLUMNS))
        _write(stage / "btc_hourly_regime_transitions.csv", csv_text(transitions, TRANSITION_COLUMNS))
        _write(stage / "btc_hourly_regime_transitions.json", json_text(transitions))
        _write(stage / "btc_hourly_regime_support_feasibility.json", json_text({**summary, "fold_assignments": folds}))
        _write(stage / "btc_hourly_regime_state_report.md", build_report(summary, evidence, len(states), len(runs)))
        files = sorted(p.name for p in stage.iterdir())
        manifest = {
            "experiment": "campaign_46_full_historical_regime_state_sequence",
            "source_only": True,
            "observation_only": True,
            "predictive_outcomes_generated": False,
            "runtime_mutation_allowed": False,
            "threshold_mutation_allowed": False,
            "signal_mutation_allowed": False,
            "strategy_mutation_allowed": False,
            "order_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "nav_mutation_allowed": False,
            "exposure_mutation_allowed": False,
            "dashboard_mutation_allowed": False,
            "source": {
                "path": str(SOURCE.relative_to(REPO_ROOT)).replace("\\", "/"),
                "sha256": EXPECTED["sha256"],
                "byte_count": EXPECTED["bytes"],
                **evidence,
            },
            "counts": {
                "states": len(states),
                "runs": len(runs),
                "transitions": len(transitions),
                "eligible_transitions": summary["eligible_non_unknown_transition_count"],
                "purged_transitions": summary["purged_transition_count"],
                "folds": summary["fold_counts"],
            },
            "feasibility_status": summary["status"],
            "files": {name: _file_digest(stage / name) for name in files},
        }
        aggregate = hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        manifest["aggregate_payload_digest"] = aggregate
        _write(stage / "btc_hourly_regime_state_manifest.json", json_text(manifest))
        if before_hash != sha256_file(SOURCE):
            raise RuntimeError("governed source changed during generation")
        if OUTPUT.exists():
            OUTPUT.rmdir()
        shutil.move(str(stage), str(OUTPUT))
    print(json.dumps({"status": "PASS", "feasibility": summary["status"], "output": str(OUTPUT)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
