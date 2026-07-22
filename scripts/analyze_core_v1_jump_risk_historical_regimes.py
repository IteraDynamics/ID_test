from __future__ import annotations

"""Research-only historical regime analysis for Core v1 Jump Risk streams.

The utility identifies historical activation-collapse windows, compares their
feature distributions with the latest observation window, and estimates recovery
without changing model state, thresholds, orders, NAV, or exposure.
"""

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze historical regimes for a locked Core v1 Jump Risk stream.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--predictions-dir", required=True)
    parser.add_argument("--features-dir", required=True)
    parser.add_argument("--stream", default="btc_extended_up")
    parser.add_argument("--reference-rows", type=int, default=4320)
    parser.add_argument("--observation-rows", type=int, default=720)
    parser.add_argument("--step-rows", type=int, default=168)
    parser.add_argument("--collapse-ratio", type=float, default=0.35)
    parser.add_argument("--recovery-ratio", type=float, default=0.80)
    parser.add_argument("--max-recovery-rows", type=int, default=4320)
    parser.add_argument("--top-features", type=int, default=10)
    parser.add_argument(
        "--out-dir",
        default="artifacts/core_v1_jump_risk_historical_regimes",
    )
    return parser.parse_args()


def _read(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_csv(path, index_col=0, parse_dates=True).sort_index()
    if frame.index.has_duplicates:
        raise ValueError(f"Duplicate timestamps in {path}")
    return frame


def _activation(frame: pd.DataFrame) -> pd.Series:
    required = {"probability", "train_threshold"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Prediction file missing columns: {sorted(missing)}")
    prob = pd.to_numeric(frame["probability"], errors="coerce")
    threshold = pd.to_numeric(frame["train_threshold"], errors="coerce")
    if prob.isna().any() or threshold.isna().any():
        raise ValueError("Prediction or threshold contains non-numeric values")
    return (prob >= threshold).astype(float)


def _feature_signature(
    features: pd.DataFrame,
    reference_slice: slice,
    observation_slice: slice,
) -> pd.Series:
    ref = features.iloc[reference_slice].apply(pd.to_numeric, errors="coerce")
    obs = features.iloc[observation_slice].apply(pd.to_numeric, errors="coerce")
    ref_mean = ref.mean()
    obs_mean = obs.mean()
    ref_std = ref.std(ddof=0).replace(0.0, np.nan)
    signature = ((obs_mean - ref_mean) / ref_std).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return signature


def _cosine_similarity(left: pd.Series, right: pd.Series) -> float:
    common = left.index.intersection(right.index)
    if common.empty:
        return 0.0
    a = left.loc[common].to_numpy(dtype=float)
    b = right.loc[common].to_numpy(dtype=float)
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


def analyze(
    predictions: pd.DataFrame,
    features: pd.DataFrame,
    *,
    reference_rows: int,
    observation_rows: int,
    step_rows: int,
    collapse_ratio: float,
    recovery_ratio: float,
    max_recovery_rows: int,
    top_features: int,
) -> dict[str, Any]:
    if not predictions.index.equals(features.index):
        features = features.reindex(predictions.index)
    if features.isna().any().any():
        raise ValueError("Features do not align cleanly to prediction timestamps")

    needed = reference_rows + observation_rows
    if len(predictions) < needed:
        raise ValueError(f"Need at least {needed} rows")

    activation = _activation(predictions)
    latest_end = len(predictions)
    latest_ref_start = latest_end - needed
    latest_obs_start = latest_end - observation_rows
    latest_ref_rate = float(activation.iloc[latest_ref_start:latest_obs_start].mean())
    latest_obs_rate = float(activation.iloc[latest_obs_start:latest_end].mean())
    latest_ratio = latest_obs_rate / latest_ref_rate if latest_ref_rate > 0 else None
    latest_signature = _feature_signature(
        features,
        slice(latest_ref_start, latest_obs_start),
        slice(latest_obs_start, latest_end),
    )

    episodes: list[dict[str, Any]] = []
    for end in range(needed, latest_obs_start + 1, step_rows):
        ref_start = end - needed
        obs_start = end - observation_rows
        ref_rate = float(activation.iloc[ref_start:obs_start].mean())
        obs_rate = float(activation.iloc[obs_start:end].mean())
        if ref_rate <= 0:
            continue
        ratio = obs_rate / ref_rate
        if ratio > collapse_ratio:
            continue

        signature = _feature_signature(
            features,
            slice(ref_start, obs_start),
            slice(obs_start, end),
        )
        similarity = _cosine_similarity(latest_signature, signature)

        recovery_rows: int | None = None
        recovery_rate: float | None = None
        search_stop = min(len(predictions), end + max_recovery_rows)
        for recovery_end in range(end + observation_rows, search_stop + 1, step_rows):
            trailing_rate = float(activation.iloc[recovery_end - observation_rows:recovery_end].mean())
            if trailing_rate >= ref_rate * recovery_ratio:
                recovery_rows = recovery_end - end
                recovery_rate = trailing_rate
                break

        top = (
            signature.abs()
            .sort_values(ascending=False, kind="mergesort")
            .head(top_features)
            .index.tolist()
        )
        episodes.append(
            {
                "window_start": str(predictions.index[obs_start]),
                "window_end": str(predictions.index[end - 1]),
                "reference_activation_rate": ref_rate,
                "observation_activation_rate": obs_rate,
                "activation_ratio": ratio,
                "feature_cosine_similarity_to_latest": similarity,
                "recovered_without_retraining": recovery_rows is not None,
                "recovery_rows": recovery_rows,
                "recovery_rate": recovery_rate,
                "top_shifted_features": top,
            }
        )

    episodes.sort(
        key=lambda row: (
            -row["feature_cosine_similarity_to_latest"],
            row["activation_ratio"],
            row["window_start"],
        )
    )

    return {
        "experiment": "core_v1_jump_risk_historical_regime_analysis",
        "research_only": True,
        "observation_only": True,
        "runtime_integration_allowed": False,
        "exposure_mutation_allowed": False,
        "config": {
            "reference_rows": reference_rows,
            "observation_rows": observation_rows,
            "step_rows": step_rows,
            "collapse_ratio": collapse_ratio,
            "recovery_ratio": recovery_ratio,
            "max_recovery_rows": max_recovery_rows,
            "top_features": top_features,
        },
        "latest_window": {
            "window_start": str(predictions.index[latest_obs_start]),
            "window_end": str(predictions.index[-1]),
            "reference_activation_rate": latest_ref_rate,
            "observation_activation_rate": latest_obs_rate,
            "activation_ratio": latest_ratio,
            "top_shifted_features": latest_signature.abs()
            .sort_values(ascending=False, kind="mergesort")
            .head(top_features)
            .index.tolist(),
        },
        "comparable_episode_count": len(episodes),
        "historical_episodes": episodes,
    }


def main() -> None:
    args = parse_args()
    predictions = _read(Path(args.predictions_dir) / f"{args.stream}.csv")
    features = _read(Path(args.features_dir) / f"{args.stream}.csv")
    payload = analyze(
        predictions,
        features,
        reference_rows=args.reference_rows,
        observation_rows=args.observation_rows,
        step_rows=args.step_rows,
        collapse_ratio=args.collapse_ratio,
        recovery_ratio=args.recovery_ratio,
        max_recovery_rows=args.max_recovery_rows,
        top_features=args.top_features,
    )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{args.stream}_historical_regimes.json"
    csv_path = out_dir / f"{args.stream}_historical_episodes.csv"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    pd.DataFrame(payload["historical_episodes"]).to_csv(csv_path, index=False)

    print()
    print("Core v1 Jump Risk historical regime analysis complete")
    print(f"Stream:              {args.stream}")
    print(f"Comparable episodes: {payload['comparable_episode_count']}")
    if payload["historical_episodes"]:
        print("Most similar historical episodes:")
        table = pd.DataFrame(payload["historical_episodes"]).head(10)
        print(table[[
            "window_start",
            "window_end",
            "activation_ratio",
            "feature_cosine_similarity_to_latest",
            "recovered_without_retraining",
            "recovery_rows",
        ]].to_string(index=False))
    print(f"JSON: {json_path}")
    print(f"CSV:  {csv_path}")
    print("Observation only: no Core state, NAV, orders, thresholds, or exposure were changed.")


if __name__ == "__main__":
    main()
