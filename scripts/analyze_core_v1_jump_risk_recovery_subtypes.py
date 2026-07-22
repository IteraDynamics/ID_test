from __future__ import annotations

"""Research-only recovery subtype analysis for historical Jump Risk collapses.

This utility reads the historical regime-analysis outputs, reconstructs each
collapse episode against the locked prediction and feature evidence, and compares
recovered versus persistent episodes. It is observation-only and never mutates
Core state, thresholds, orders, NAV, or exposure.
"""

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze recovery subtypes for historical Core v1 Jump Risk collapse episodes.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--predictions-dir", required=True)
    parser.add_argument("--features-dir", required=True)
    parser.add_argument(
        "--historical-dir",
        default="artifacts/core_v1_jump_risk_historical_regimes",
    )
    parser.add_argument("--stream", default="btc_extended_up")
    parser.add_argument("--reference-rows", type=int, default=4320)
    parser.add_argument("--observation-rows", type=int, default=720)
    parser.add_argument("--top-features", type=int, default=15)
    parser.add_argument(
        "--out-dir",
        default="artifacts/core_v1_jump_risk_recovery_subtypes",
    )
    return parser.parse_args()


def _read(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_csv(path, index_col=0, parse_dates=True).sort_index()
    if frame.index.has_duplicates:
        raise ValueError(f"Duplicate timestamps in {path}")
    return frame


def _numeric(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.apply(pd.to_numeric, errors="coerce")
    if out.isna().any().any():
        missing = out.columns[out.isna().any()].tolist()
        raise ValueError(f"Non-numeric or missing feature values: {missing}")
    return out


def _activation(predictions: pd.DataFrame) -> pd.Series:
    required = {"probability", "train_threshold"}
    missing = required - set(predictions.columns)
    if missing:
        raise ValueError(f"Prediction file missing columns: {sorted(missing)}")
    probability = pd.to_numeric(predictions["probability"], errors="coerce")
    threshold = pd.to_numeric(predictions["train_threshold"], errors="coerce")
    if probability.isna().any() or threshold.isna().any():
        raise ValueError("Prediction or threshold contains non-numeric values")
    return (probability >= threshold).astype(float)


def _signature(features: pd.DataFrame, ref_start: int, obs_start: int, obs_end: int) -> pd.Series:
    reference = features.iloc[ref_start:obs_start]
    observation = features.iloc[obs_start:obs_end]
    reference_std = reference.std(ddof=0).replace(0.0, np.nan)
    return (
        (observation.mean() - reference.mean()) / reference_std
    ).replace([np.inf, -np.inf], np.nan).fillna(0.0)


def _median_effect(recovered: pd.DataFrame, persistent: pd.DataFrame) -> pd.DataFrame:
    recovered_median = recovered.median(axis=0)
    persistent_median = persistent.median(axis=0)
    combined = pd.concat([recovered, persistent], axis=0)
    scale = combined.std(axis=0, ddof=0).replace(0.0, np.nan)
    standardized_difference = (
        (recovered_median - persistent_median) / scale
    ).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    result = pd.DataFrame(
        {
            "feature": recovered.columns,
            "recovered_median_signature": recovered_median.values,
            "persistent_median_signature": persistent_median.values,
            "median_signature_difference": (recovered_median - persistent_median).values,
            "standardized_group_difference": standardized_difference.values,
        }
    )
    result["absolute_standardized_group_difference"] = result[
        "standardized_group_difference"
    ].abs()
    return result.sort_values(
        ["absolute_standardized_group_difference", "feature"],
        ascending=[False, True],
        kind="mergesort",
    ).reset_index(drop=True)


def analyze(
    predictions: pd.DataFrame,
    features: pd.DataFrame,
    episodes: pd.DataFrame,
    *,
    reference_rows: int,
    observation_rows: int,
    top_features: int,
) -> dict[str, Any]:
    if not predictions.index.equals(features.index):
        features = features.reindex(predictions.index)
    features = _numeric(features)
    if features.isna().any().any():
        raise ValueError("Features do not align cleanly to prediction timestamps")

    activation = _activation(predictions)
    timestamp_to_position = {timestamp: position for position, timestamp in enumerate(predictions.index)}

    episode_rows: list[dict[str, Any]] = []
    signatures: list[pd.Series] = []
    for episode_id, row in episodes.reset_index(drop=True).iterrows():
        end_timestamp = pd.Timestamp(row["window_end"])
        if end_timestamp not in timestamp_to_position:
            raise ValueError(f"Historical episode end timestamp is not in prediction index: {end_timestamp}")
        obs_end = timestamp_to_position[end_timestamp] + 1
        obs_start = obs_end - observation_rows
        ref_start = obs_start - reference_rows
        if ref_start < 0:
            raise ValueError(f"Insufficient reference history for episode ending {end_timestamp}")

        signature = _signature(features, ref_start, obs_start, obs_end)
        signatures.append(signature.rename(episode_id))

        ref_rate = float(activation.iloc[ref_start:obs_start].mean())
        obs_rate = float(activation.iloc[obs_start:obs_end].mean())
        episode_rows.append(
            {
                "episode_id": episode_id,
                "window_start": str(predictions.index[obs_start]),
                "window_end": str(predictions.index[obs_end - 1]),
                "reference_activation_rate": ref_rate,
                "observation_activation_rate": obs_rate,
                "activation_ratio": obs_rate / ref_rate if ref_rate > 0 else None,
                "feature_cosine_similarity_to_latest": float(row["feature_cosine_similarity_to_latest"]),
                "recovered_without_retraining": bool(row["recovered_without_retraining"]),
                "recovery_rows": None if pd.isna(row.get("recovery_rows")) else int(row["recovery_rows"]),
            }
        )

    episode_frame = pd.DataFrame(episode_rows)
    signature_frame = pd.DataFrame(signatures)
    signature_frame.index.name = "episode_id"

    recovered_ids = episode_frame.loc[
        episode_frame["recovered_without_retraining"], "episode_id"
    ].tolist()
    persistent_ids = episode_frame.loc[
        ~episode_frame["recovered_without_retraining"], "episode_id"
    ].tolist()
    if not recovered_ids or not persistent_ids:
        raise ValueError("Need at least one recovered and one persistent episode")

    recovered = signature_frame.loc[recovered_ids]
    persistent = signature_frame.loc[persistent_ids]
    feature_comparison = _median_effect(recovered, persistent)

    recovered_rows = pd.to_numeric(
        episode_frame.loc[episode_frame["recovered_without_retraining"], "recovery_rows"],
        errors="coerce",
    ).dropna()
    recovery_summary = {
        "count": int(len(recovered_rows)),
        "median_rows": float(recovered_rows.median()),
        "mean_rows": float(recovered_rows.mean()),
        "minimum_rows": int(recovered_rows.min()),
        "maximum_rows": int(recovered_rows.max()),
        "p25_rows": float(recovered_rows.quantile(0.25)),
        "p75_rows": float(recovered_rows.quantile(0.75)),
    }

    group_summary = (
        episode_frame.groupby("recovered_without_retraining", sort=True)
        .agg(
            episode_count=("episode_id", "count"),
            median_activation_ratio=("activation_ratio", "median"),
            mean_activation_ratio=("activation_ratio", "mean"),
            median_similarity_to_latest=("feature_cosine_similarity_to_latest", "median"),
            mean_similarity_to_latest=("feature_cosine_similarity_to_latest", "mean"),
        )
        .reset_index()
        .to_dict(orient="records")
    )

    top = feature_comparison.head(top_features).to_dict(orient="records")
    return {
        "experiment": "core_v1_jump_risk_recovery_subtype_analysis",
        "research_only": True,
        "observation_only": True,
        "runtime_integration_allowed": False,
        "exposure_mutation_allowed": False,
        "config": {
            "reference_rows": reference_rows,
            "observation_rows": observation_rows,
            "top_features": top_features,
        },
        "episode_count": int(len(episode_frame)),
        "recovered_episode_count": int(len(recovered_ids)),
        "persistent_episode_count": int(len(persistent_ids)),
        "recovered_fraction": float(len(recovered_ids) / len(episode_frame)),
        "recovery_duration_summary": recovery_summary,
        "group_summary": group_summary,
        "top_recovery_discriminating_features": top,
        "episodes": episode_rows,
    }, episode_frame, feature_comparison, signature_frame


def main() -> None:
    args = parse_args()
    predictions = _read(Path(args.predictions_dir) / f"{args.stream}.csv")
    features = _read(Path(args.features_dir) / f"{args.stream}.csv")

    historical_path = Path(args.historical_dir) / f"{args.stream}_historical_episodes.csv"
    if not historical_path.exists():
        raise FileNotFoundError(historical_path)
    episodes = pd.read_csv(historical_path)
    required = {
        "window_end",
        "feature_cosine_similarity_to_latest",
        "recovered_without_retraining",
        "recovery_rows",
    }
    missing = required - set(episodes.columns)
    if missing:
        raise ValueError(f"Historical episodes file missing columns: {sorted(missing)}")
    episodes["recovered_without_retraining"] = episodes[
        "recovered_without_retraining"
    ].astype(str).str.lower().map({"true": True, "false": False})
    if episodes["recovered_without_retraining"].isna().any():
        raise ValueError("Could not parse recovered_without_retraining values")

    payload, episode_frame, feature_comparison, signature_frame = analyze(
        predictions,
        features,
        episodes,
        reference_rows=args.reference_rows,
        observation_rows=args.observation_rows,
        top_features=args.top_features,
    )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{args.stream}_recovery_subtypes.json"
    episode_path = out_dir / f"{args.stream}_recovery_subtype_episodes.csv"
    feature_path = out_dir / f"{args.stream}_recovery_feature_comparison.csv"
    signature_path = out_dir / f"{args.stream}_episode_signatures.csv"

    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    episode_frame.to_csv(episode_path, index=False)
    feature_comparison.to_csv(feature_path, index=False)
    signature_frame.to_csv(signature_path)

    print()
    print("Core v1 Jump Risk recovery subtype analysis complete")
    print(f"Stream:                {args.stream}")
    print(f"Episodes:              {payload['episode_count']}")
    print(f"Recovered:             {payload['recovered_episode_count']}")
    print(f"Persistent:            {payload['persistent_episode_count']}")
    print(f"Recovered fraction:    {payload['recovered_fraction']:.3f}")
    duration = payload["recovery_duration_summary"]
    print(f"Median recovery rows:  {duration['median_rows']:.1f}")
    print("Top recovery-discriminating features:")
    print(feature_comparison.head(args.top_features)[[
        "feature",
        "recovered_median_signature",
        "persistent_median_signature",
        "standardized_group_difference",
    ]].to_string(index=False))
    print(f"JSON:                  {json_path}")
    print(f"Episodes CSV:          {episode_path}")
    print(f"Feature comparison:    {feature_path}")
    print(f"Episode signatures:    {signature_path}")
    print("Observation only: no Core state, NAV, orders, thresholds, or exposure were changed.")


if __name__ == "__main__":
    main()
