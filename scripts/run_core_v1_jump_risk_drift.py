from __future__ import annotations

"""Observation-only drift audit for Core v1 Jump Risk paper predictions."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from research.ml.validation.drift_detector import aggregate_severity
from research.ml.validation.drift_persistence import evaluate_persistence

EXPECTED_STREAMS = (
    "btc_medium_up",
    "btc_extended_up",
    "eth_medium_up",
    "eth_extended_up",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run deterministic drift monitoring over frozen Core v1 Jump Risk OOS probability streams.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--predictions-dir",
        required=True,
        help="Predictions directory from run_jump_risk_portfolio_integration.py",
    )
    parser.add_argument("--out-dir", default="artifacts/core_v1_jump_risk_drift")
    parser.add_argument("--run-name", default="core-v1-jump-risk-drift")
    parser.add_argument("--reference-rows", type=int, default=24 * 90)
    parser.add_argument("--observation-rows", type=int, default=24 * 14)
    parser.add_argument("--persistence-windows", type=int, default=3)
    parser.add_argument("--required-consecutive", type=int, default=2)
    return parser.parse_args()


def _atomic_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )
    temporary.replace(path)


def _read_stream(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing locked Jump Risk prediction stream: {path}")
    frame = pd.read_csv(path, index_col=0, parse_dates=True)
    frame.index = pd.to_datetime(frame.index, utc=True).tz_convert(None)
    return frame.sort_index()


def main() -> None:
    args = parse_args()
    predictions_dir = Path(args.predictions_dir).resolve()
    if not predictions_dir.is_dir():
        raise NotADirectoryError(f"Predictions directory not found: {predictions_dir}")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.out_dir) / f"{timestamp}_{args.run_name}"
    run_dir.mkdir(parents=True, exist_ok=False)

    reports = []
    assessments = []
    rows: list[dict[str, Any]] = []
    input_files: dict[str, str] = {}

    for stream in EXPECTED_STREAMS:
        asset, model = stream.split("_", 1)
        path = predictions_dir / f"{stream}.csv"
        frame = _read_stream(path)
        report, persistence = evaluate_persistence(
            frame,
            asset=asset.upper(),
            model=model,
            reference_rows=args.reference_rows,
            observation_rows=args.observation_rows,
            requested_windows=args.persistence_windows,
            required_consecutive=args.required_consecutive,
        )
        reports.append(report)
        assessments.append(persistence)
        input_files[stream] = str(path)
        rows.append(
            {
                "asset": report.asset,
                "model": report.model,
                "severity": report.severity,
                "risk_score": report.risk_score,
                "drift_detected": report.drift_detected,
                "persistence_state": persistence.state,
                "persistence_breaches": persistence.persistence_breaches,
                "evaluated_windows": persistence.evaluated_windows,
                "requested_windows": persistence.requested_windows,
                "persistence_sufficient": persistence.persistence_sufficient,
                "consecutive_high_windows": persistence.consecutive_high_windows,
                "consecutive_non_low_windows": persistence.consecutive_non_low_windows,
                "window_severities": "|".join(persistence.window_severities),
                "reasons": "|".join(report.reasons),
                "score_components": json.dumps(
                    report.score_components, sort_keys=True, separators=(",", ":")
                ),
                "psi": report.probability.psi,
                "ks_statistic": report.probability.ks_statistic,
                "standardized_mean_shift": report.probability.standardized_mean_shift,
                "reference_mean_probability": report.probability.reference_mean,
                "observation_mean_probability": report.probability.observation_mean,
                "reference_exceedance_rate": report.probability.reference_exceedance_rate,
                "observation_exceedance_rate": report.probability.observation_exceedance_rate,
                "reference_brier_score": report.outcomes.reference.brier_score,
                "observation_brier_score": report.outcomes.observation.brier_score,
                "brier_deterioration": report.outcomes.brier_deterioration,
                "reference_calibration_error": report.outcomes.reference.calibration_error,
                "observation_calibration_error": report.outcomes.observation.calibration_error,
                "calibration_deterioration": report.outcomes.calibration_deterioration,
                "reference_threshold_precision": report.outcomes.reference.threshold_precision,
                "observation_threshold_precision": report.outcomes.observation.threshold_precision,
                "threshold_precision_drop": report.outcomes.threshold_precision_drop,
                "digest": report.digest,
            }
        )

    aggregate = aggregate_severity(reports)
    report_payloads = []
    for report, persistence in zip(reports, assessments, strict=True):
        report_payload = report.to_dict()
        report_payload["persistence_breaches"] = persistence.persistence_breaches
        report_payload["persistence"] = persistence.to_dict()
        report_payloads.append(report_payload)

    payload = {
        "experiment": "core_v1_jump_risk_drift_monitoring_v3",
        "observation_only": True,
        "runtime_integration_allowed": False,
        "exposure_mutation_allowed": False,
        "aggregate_severity": aggregate,
        "drift_detected": aggregate != "LOW",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": {
            "reference_rows": args.reference_rows,
            "observation_rows": args.observation_rows,
            "persistence_windows": args.persistence_windows,
            "required_consecutive": args.required_consecutive,
            "streams": list(EXPECTED_STREAMS),
            "severity_policy": "weighted_trust_score_with_rolling_persistence",
        },
        "inputs": input_files,
        "reports": report_payloads,
    }

    _atomic_json(run_dir / "jump_risk_drift_summary.json", payload)
    pd.DataFrame(rows).to_csv(run_dir / "jump_risk_drift_by_model.csv", index=False)
    _atomic_json(
        run_dir / "manifest.json",
        {
            "experiment": payload["experiment"],
            "observation_only": True,
            "source_predictions_dir": str(predictions_dir),
            "created_at_utc": payload["created_at_utc"],
            "aggregate_severity": aggregate,
            "severity_policy": "weighted_trust_score_with_rolling_persistence",
            "persistence_windows": args.persistence_windows,
            "required_consecutive": args.required_consecutive,
        },
    )

    print()
    print("Core v1 Jump Risk drift monitoring complete")
    print(f"Out dir: {run_dir}")
    print(f"Aggregate severity: {aggregate}")
    for row in rows:
        sufficiency = "confirmed" if row["persistence_sufficient"] else "history-limited"
        print(
            f"- {row['asset']:<3} {row['model']:<12} "
            f"severity={row['severity']:<4} score={row['risk_score']:<2} "
            f"persistence={row['persistence_state']:<15} ({sufficiency}, "
            f"{row['evaluated_windows']}/{row['requested_windows']} windows) "
            f"psi={row['psi']:.4f} ks={row['ks_statistic']:.4f} "
            f"mean_shift={row['standardized_mean_shift']:.4f}"
        )
    print("Observation only: no Core state, NAV, orders, or exposure were changed.")


if __name__ == "__main__":
    main()
