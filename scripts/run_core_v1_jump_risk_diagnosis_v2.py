from __future__ import annotations

"""Evidence-aware, observation-only diagnosis for Core v1 Jump Risk streams."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from research.ml.validation.drift_diagnosis_v2 import diagnose_stream_v2

EXPECTED_STREAMS = (
    "btc_medium_up",
    "btc_extended_up",
    "eth_medium_up",
    "eth_extended_up",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run evidence-aware Core v1 Jump Risk drift diagnosis.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--predictions-dir", required=True)
    parser.add_argument(
        "--features-dir",
        help="Optional directory containing one timestamp-indexed CSV per stream, named <stream>.csv",
    )
    parser.add_argument(
        "--market-context-file",
        help="Optional timestamp-indexed CSV shared across streams (volatility, trend, returns, etc.)",
    )
    parser.add_argument("--out-dir", default="artifacts/core_v1_jump_risk_diagnosis_v2")
    parser.add_argument("--run-name", default="core-v1-jump-risk-diagnosis-v2")
    parser.add_argument("--reference-rows", type=int, default=24 * 90)
    parser.add_argument("--observation-rows", type=int, default=24 * 14)
    return parser.parse_args()


def _atomic_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    temporary.replace(path)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_csv(path, index_col=0, parse_dates=True)
    frame.index = pd.to_datetime(frame.index, utc=True).tz_convert(None)
    return frame.sort_index()


def main() -> None:
    args = parse_args()
    predictions_dir = Path(args.predictions_dir).resolve()
    if not predictions_dir.is_dir():
        raise NotADirectoryError(f"Predictions directory not found: {predictions_dir}")

    features_dir = Path(args.features_dir).resolve() if args.features_dir else None
    if features_dir is not None and not features_dir.is_dir():
        raise NotADirectoryError(f"Features directory not found: {features_dir}")

    context = _read_csv(Path(args.market_context_file).resolve()) if args.market_context_file else None

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.out_dir) / f"{timestamp}_{args.run_name}"
    run_dir.mkdir(parents=True, exist_ok=False)

    reports = []
    rows: list[dict[str, Any]] = []
    inputs: dict[str, Any] = {
        "predictions_dir": str(predictions_dir),
        "features_dir": str(features_dir) if features_dir else None,
        "market_context_file": str(Path(args.market_context_file).resolve()) if args.market_context_file else None,
    }

    for stream in EXPECTED_STREAMS:
        asset, model = stream.split("_", 1)
        prediction = _read_csv(predictions_dir / f"{stream}.csv")
        feature_path = features_dir / f"{stream}.csv" if features_dir else None
        features = _read_csv(feature_path) if feature_path is not None else None
        report = diagnose_stream_v2(
            prediction,
            asset=asset.upper(),
            model=model,
            reference_rows=args.reference_rows,
            observation_rows=args.observation_rows,
            feature_frame=features,
            market_context_frame=context,
        )
        reports.append(report)
        base = report.prediction_diagnosis
        rows.append(
            {
                "asset": report.asset,
                "model": report.model,
                "classification": report.classification,
                "confidence": report.confidence,
                "evidence_sufficient": report.evidence_sufficient,
                "reference_activation_rate": base.reference.activation_rate,
                "observation_activation_rate": base.observation.activation_rate,
                "activation_rate_ratio": base.activation_rate_ratio,
                "standardized_probability_mean_shift": base.standardized_probability_mean_shift,
                "below_threshold_within_002": base.threshold_distance.below_within_002,
                "feature_evidence_count": len(report.feature_evidence),
                "market_context_evidence_count": len(report.market_context_evidence),
                "reasons": "|".join(report.reasons),
                "digest": report.digest,
            }
        )
        if report.feature_evidence:
            pd.DataFrame(
                [{"feature": name, **comparison.__dict__} for name, comparison in report.feature_evidence.items()]
            ).to_csv(run_dir / f"{stream}_feature_evidence.csv", index=False)
        if report.market_context_evidence:
            pd.DataFrame(
                [{"feature": name, **comparison.__dict__} for name, comparison in report.market_context_evidence.items()]
            ).to_csv(run_dir / f"{stream}_market_context_evidence.csv", index=False)

    payload = {
        "experiment": "core_v1_jump_risk_drift_diagnosis_v2",
        "observation_only": True,
        "runtime_integration_allowed": False,
        "exposure_mutation_allowed": False,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": {
            "reference_rows": args.reference_rows,
            "observation_rows": args.observation_rows,
            "streams": list(EXPECTED_STREAMS),
            "requires_external_evidence_for_regime_change": True,
        },
        "inputs": inputs,
        "reports": [report.to_dict() for report in reports],
    }
    _atomic_json(run_dir / "jump_risk_diagnosis_v2_summary.json", payload)
    pd.DataFrame(rows).to_csv(run_dir / "jump_risk_diagnosis_v2_by_model.csv", index=False)
    _atomic_json(
        run_dir / "manifest.json",
        {
            "experiment": payload["experiment"],
            "observation_only": True,
            "created_at_utc": payload["created_at_utc"],
            "inputs": inputs,
        },
    )

    print()
    print("Core v1 Jump Risk evidence-aware drift diagnosis complete")
    print(f"Out dir: {run_dir}")
    for report in reports:
        base = report.prediction_diagnosis
        ratio = "n/a" if base.activation_rate_ratio is None else f"{base.activation_rate_ratio:.3f}x"
        print(
            f"- {report.asset:<3} {report.model:<12} "
            f"diagnosis={report.classification:<21} confidence={report.confidence:<4} "
            f"evidence={'yes' if report.evidence_sufficient else 'no ':<3} "
            f"activation={base.reference.activation_rate:.2%}->{base.observation.activation_rate:.2%} "
            f"ratio={ratio}"
        )
    print("Observation only: no Core state, NAV, orders, thresholds, or exposure were changed.")


if __name__ == "__main__":
    main()
