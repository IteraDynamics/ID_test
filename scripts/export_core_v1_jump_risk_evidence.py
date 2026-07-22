from __future__ import annotations

"""Export exact, replay-aligned feature evidence for locked Jump Risk streams.

The exporter regenerates the frozen walk-forward predictions from canonical inputs,
verifies parity against an existing locked predictions directory, and writes only
the exact model-input columns used for each prediction. It is research-only and
never mutates Core state, NAV, orders, thresholds, or exposure.
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import research.jump_risk_engine.lab as lab
from research.jump_risk_engine.lab import JumpRiskConfig, read_ohlcv
from scripts.run_jump_risk_portfolio_integration import (
    CANONICAL_DATA,
    FEATURE_SETS,
    LOCKED_MODELS,
    _build_frame,
    _canonical_path,
    _utc_naive_index,
)

EXPECTED_STREAMS = (
    ("BTC", "medium_up"),
    ("BTC", "extended_up"),
    ("ETH", "medium_up"),
    ("ETH", "extended_up"),
)
PREDICTION_COLUMNS = ["probability", "label", "train_threshold", "test_year"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export exact feature evidence for Core v1 Jump Risk diagnosis v2.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--predictions-dir", required=True, help="Locked prediction CSV directory used by drift monitoring")
    parser.add_argument("--btc-data", default=CANONICAL_DATA["btc_data"])
    parser.add_argument("--eth-data", default=CANONICAL_DATA["eth_data"])
    parser.add_argument("--out-dir", default="artifacts/core_v1_jump_risk_evidence")
    parser.add_argument("--run-name", default="core-v1-jump-risk-evidence")
    parser.add_argument("--oos-start", default="2020-01-01")
    parser.add_argument("--oos-end", default="2025-12-31")
    parser.add_argument("--risk-quantile", type=float, default=0.95)
    parser.add_argument("--jump-z", type=float, default=3.0)
    parser.add_argument("--absolute-jump", type=float, default=0.05)
    return parser.parse_args()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    temporary.replace(path)


def _read_prediction_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_csv(path, index_col=0, parse_dates=True)
    frame.index = _utc_naive_index(frame.index)
    return frame.sort_index()


def _split_shifted_output(combined: pd.DataFrame, features: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply the production one-bar delay to predictions, threshold, and inputs.

    Labels and test-year metadata intentionally retain the existing locked-stream
    semantics. Feature evidence is shifted exactly with the prediction it produced.
    """
    out = combined.sort_index().copy()
    shift_columns = ["probability", "train_threshold", *features]
    out[shift_columns] = out[shift_columns].shift(1)
    prediction = out[PREDICTION_COLUMNS].dropna(subset=["probability", "train_threshold"])
    evidence = out.loc[prediction.index, features].copy()
    if evidence.isna().any().any():
        missing = evidence.columns[evidence.isna().any()].tolist()
        raise RuntimeError(f"Shifted evidence contains missing values: {missing}")
    return prediction, evidence


def _oos_predictions_and_features(
    ohlcv: pd.DataFrame,
    asset: str,
    candidate_name: str,
    oos_start: str,
    oos_end: str,
    jump_z: float,
    absolute_jump: float,
    risk_quantile: float,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    spec = LOCKED_MODELS[candidate_name]
    cfg = JumpRiskConfig(
        asset=asset,
        horizon_bars=int(spec["horizon_bars"]),
        vol_window=96,
        fast_window=24,
        slow_window=240,
        jump_z=jump_z,
        absolute_jump=absolute_jump,
        min_train_rows=500,
        min_train_events=20,
        test_start_year=pd.Timestamp(oos_start).year,
    )
    frame = _build_frame(ohlcv, cfg)
    features = FEATURE_SETS[str(spec["feature_set"])]
    label_col = f"jump_{spec['target']}"
    rows: list[pd.DataFrame] = []

    for year in range(pd.Timestamp(oos_start).year, pd.Timestamp(oos_end).year + 1):
        train = frame[frame.index.year < year]
        test = frame[frame.index.year == year]
        if test.empty:
            continue
        train_events = int(train[label_col].sum())
        train_nonevents = int((train[label_col] == 0).sum())
        if len(train) < cfg.min_train_rows or min(train_events, train_nonevents) < cfg.min_train_events:
            continue

        model = lab._make_model(str(spec["model"]))
        train_x = train[features].astype(float)
        test_x = test[features].astype(float)
        model.fit(train_x, train[label_col].astype(int))
        train_prob = model.predict_proba(train_x)[:, 1]
        test_prob = model.predict_proba(test_x)[:, 1]

        fold = pd.DataFrame(
            {
                "probability": test_prob,
                "label": test[label_col].astype(int),
                "train_threshold": float(np.quantile(train_prob, risk_quantile)),
                "test_year": year,
            },
            index=test.index,
        )
        rows.append(fold.join(test_x))

    if not rows:
        raise RuntimeError(f"No OOS predictions generated for {asset} {candidate_name}")

    combined = pd.concat(rows).sort_index()
    combined.index = _utc_naive_index(combined.index)
    start_ts = pd.Timestamp(oos_start)
    end_ts = pd.Timestamp(oos_end)
    combined = combined.loc[(combined.index >= start_ts) & (combined.index <= end_ts)]
    prediction, evidence = _split_shifted_output(combined, features)
    return prediction, evidence, features


def _assert_prediction_parity(expected: pd.DataFrame, regenerated: pd.DataFrame, stream: str) -> None:
    missing = sorted(set(PREDICTION_COLUMNS) - set(expected.columns))
    if missing:
        raise ValueError(f"{stream}: locked prediction file is missing columns {missing}")

    expected = expected[PREDICTION_COLUMNS].sort_index()
    regenerated = regenerated[PREDICTION_COLUMNS].sort_index()
    if not expected.index.equals(regenerated.index):
        left_only = len(expected.index.difference(regenerated.index))
        right_only = len(regenerated.index.difference(expected.index))
        raise RuntimeError(f"{stream}: prediction index mismatch; locked_only={left_only}, regenerated_only={right_only}")

    for column in PREDICTION_COLUMNS:
        left = pd.to_numeric(expected[column], errors="coerce").to_numpy(dtype=float)
        right = pd.to_numeric(regenerated[column], errors="coerce").to_numpy(dtype=float)
        if not np.allclose(left, right, rtol=1e-12, atol=1e-12, equal_nan=True):
            max_delta = float(np.nanmax(np.abs(left - right)))
            raise RuntimeError(f"{stream}: parity failed for {column}; max_abs_delta={max_delta:.16g}")


def main() -> None:
    args = parse_args()
    if not 0.50 < args.risk_quantile < 1.0:
        raise ValueError("--risk-quantile must be between 0.50 and 1.0")

    predictions_dir = Path(args.predictions_dir).resolve()
    if not predictions_dir.is_dir():
        raise NotADirectoryError(f"Predictions directory not found: {predictions_dir}")

    btc_path = _canonical_path(args.btc_data)
    eth_path = _canonical_path(args.eth_data)
    sources = {"BTC": read_ohlcv(btc_path), "ETH": read_ohlcv(eth_path)}

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.out_dir) / f"{timestamp}_{args.run_name}"
    features_dir = run_dir / "features"
    features_dir.mkdir(parents=True, exist_ok=False)

    streams: list[dict[str, Any]] = []
    for asset, candidate in EXPECTED_STREAMS:
        stream = f"{asset.lower()}_{candidate}"
        print(f"Regenerating and verifying locked stream: {stream}")
        regenerated, evidence, feature_names = _oos_predictions_and_features(
            sources[asset],
            asset,
            candidate,
            args.oos_start,
            args.oos_end,
            args.jump_z,
            args.absolute_jump,
            args.risk_quantile,
        )
        locked_path = predictions_dir / f"{stream}.csv"
        locked = _read_prediction_csv(locked_path)
        _assert_prediction_parity(locked, regenerated, stream)

        evidence_path = features_dir / f"{stream}.csv"
        evidence.to_csv(evidence_path)
        streams.append(
            {
                "stream": stream,
                "rows": int(len(evidence)),
                "feature_count": len(feature_names),
                "features": feature_names,
                "locked_prediction_sha256": _sha256(locked_path),
                "evidence_sha256": _sha256(evidence_path),
                "parity": "PASS",
            }
        )

    manifest = {
        "experiment": "core_v1_jump_risk_feature_evidence_export",
        "research_only": True,
        "observation_only": True,
        "runtime_integration_allowed": False,
        "exposure_mutation_allowed": False,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": vars(args),
        "inputs": {
            "predictions_dir": str(predictions_dir),
            "btc_sha256": _sha256(btc_path),
            "eth_sha256": _sha256(eth_path),
        },
        "alignment": {
            "prediction_shift_bars": 1,
            "feature_shift_bars": 1,
            "label_shift_bars": 0,
            "note": "Each exported feature row is the exact model input associated with the delayed prediction at the same timestamp.",
        },
        "streams": streams,
    }
    _atomic_json(run_dir / "manifest.json", manifest)

    print()
    print("Core v1 Jump Risk feature evidence export complete")
    print(f"Run dir:      {run_dir}")
    print(f"Features dir: {features_dir}")
    print("Prediction parity: PASS for all four streams")
    print("Observation only: no Core state, NAV, orders, thresholds, or exposure were changed.")


if __name__ == "__main__":
    main()
