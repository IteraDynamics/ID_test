from __future__ import annotations

"""Observation-only diagnosis for Core v1 Jump Risk prediction streams."""

# Preserve direct-file execution; package imports use normal discovery.
if __package__ in (None, ""):
    try:
        from _checkout_bootstrap import bootstrap as _bootstrap_checkout
    except ModuleNotFoundError as _bootstrap_error:
        if _bootstrap_error.name != "_checkout_bootstrap":
            raise
        from scripts._checkout_bootstrap import bootstrap as _bootstrap_checkout
    _bootstrap_checkout(__file__)


import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent

from research.ml.validation.drift_diagnosis import diagnose_stream

EXPECTED_STREAMS = (
    "btc_medium_up",
    "btc_extended_up",
    "eth_medium_up",
    "eth_extended_up",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Diagnose deterministic Core v1 Jump Risk probability drift.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--predictions-dir", required=True)
    parser.add_argument("--out-dir", default="artifacts/core_v1_jump_risk_diagnosis")
    parser.add_argument("--run-name", default="core-v1-jump-risk-diagnosis")
    parser.add_argument("--reference-rows", type=int, default=24 * 90)
    parser.add_argument("--observation-rows", type=int, default=24 * 14)
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
    summary_rows: list[dict[str, Any]] = []
    inputs: dict[str, str] = {}

    for stream in EXPECTED_STREAMS:
        asset, model = stream.split("_", 1)
        path = predictions_dir / f"{stream}.csv"
        frame = _read_stream(path)
        report = diagnose_stream(
            frame,
            asset=asset.upper(),
            model=model,
            reference_rows=args.reference_rows,
            observation_rows=args.observation_rows,
        )
        reports.append(report)
        inputs[stream] = str(path)

        summary_rows.append(
            {
                "asset": report.asset,
                "model": report.model,
                "classification": report.classification,
                "confidence": report.confidence,
                "reference_activation_rate": report.reference.activation_rate,
                "observation_activation_rate": report.observation.activation_rate,
                "activation_rate_change": report.activation_rate_change,
                "activation_rate_ratio": report.activation_rate_ratio,
                "reference_probability_mean": report.reference.probability_mean,
                "observation_probability_mean": report.observation.probability_mean,
                "standardized_probability_mean_shift": report.standardized_probability_mean_shift,
                "below_threshold_within_002": report.threshold_distance.below_within_002,
                "reference_brier_score": report.reference.brier_score,
                "observation_brier_score": report.observation.brier_score,
                "reference_calibration_error": report.reference.calibration_error,
                "observation_calibration_error": report.observation.calibration_error,
                "reasons": "|".join(report.reasons),
                "digest": report.digest,
            }
        )

        if report.probability_buckets:
            pd.DataFrame(report.probability_buckets).to_csv(
                run_dir / f"{stream}_observation_probability_buckets.csv", index=False
            )
        if report.feature_comparisons:
            feature_rows = [
                {"feature": name, **comparison.__dict__}
                for name, comparison in report.feature_comparisons.items()
            ]
            pd.DataFrame(feature_rows).to_csv(
                run_dir / f"{stream}_feature_comparison.csv", index=False
            )

    payload = {
        "experiment": "core_v1_jump_risk_drift_diagnosis_v1",
        "observation_only": True,
        "runtime_integration_allowed": False,
        "exposure_mutation_allowed": False,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": {
            "reference_rows": args.reference_rows,
            "observation_rows": args.observation_rows,
            "streams": list(EXPECTED_STREAMS),
            "classification_policy": (
                "DATA_PIPELINE_SUSPECT > MODEL_DEGRADATION > "
                "THRESHOLD_MISMATCH > REGIME_CHANGE > INCONCLUSIVE"
            ),
        },
        "inputs": inputs,
        "reports": [report.to_dict() for report in reports],
    }

    _atomic_json(run_dir / "jump_risk_diagnosis_summary.json", payload)
    pd.DataFrame(summary_rows).to_csv(run_dir / "jump_risk_diagnosis_by_model.csv", index=False)
    _atomic_json(
        run_dir / "manifest.json",
        {
            "experiment": payload["experiment"],
            "observation_only": True,
            "source_predictions_dir": str(predictions_dir),
            "created_at_utc": payload["created_at_utc"],
            "reference_rows": args.reference_rows,
            "observation_rows": args.observation_rows,
        },
    )

    print()
    print("Core v1 Jump Risk drift diagnosis complete")
    print(f"Out dir: {run_dir}")
    for report in reports:
        ratio = "n/a" if report.activation_rate_ratio is None else f"{report.activation_rate_ratio:.3f}x"
        print(
            f"- {report.asset:<3} {report.model:<12} "
            f"diagnosis={report.classification:<21} confidence={report.confidence:<4} "
            f"activation={report.reference.activation_rate:.2%}->{report.observation.activation_rate:.2%} "
            f"ratio={ratio} mean_shift={report.standardized_probability_mean_shift:.3f} "
            f"near_threshold={report.threshold_distance.below_within_002:.2%}"
        )
    print("Observation only: no Core state, NAV, orders, thresholds, or exposure were changed.")


if __name__ == "__main__":
    main()
