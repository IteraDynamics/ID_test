from __future__ import annotations

"""Build deterministic, research-only historical regime taxonomy artifacts."""

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
from pathlib import Path

import pandas as pd

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

from research.ml.validation.historical_regime_artifact_io import (
    stable_artifact_identifier,
    write_text_lf,
)
from research.ml.validation.historical_regime_taxonomy import build_summary, classify_episodes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Classify Core v1 Jump Risk historical collapse episodes.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--historical-json",
        default="artifacts/core_v1_jump_risk_historical_regimes/btc_extended_up_historical_regimes.json",
    )
    parser.add_argument(
        "--historical-episodes",
        default="artifacts/core_v1_jump_risk_historical_regimes/btc_extended_up_historical_episodes.csv",
    )
    parser.add_argument(
        "--episode-signatures",
        default="artifacts/core_v1_jump_risk_recovery_subtypes/btc_extended_up_episode_signatures.csv",
    )
    parser.add_argument(
        "--out-dir",
        default="artifacts/core_v1_jump_risk_historical_regime_taxonomy",
    )
    parser.add_argument("--stream", default="btc_extended_up")
    return parser.parse_args()


def _strict_json_records(frame: pd.DataFrame) -> list[dict[str, object]]:
    """Normalize pandas missing scalars to JSON null without changing the frame."""
    normalized = frame.astype(object).where(pd.notna(frame), None)
    return normalized.to_dict(orient="records")


def main() -> None:
    args = parse_args()
    historical_json_path = Path(args.historical_json)
    episodes_path = Path(args.historical_episodes)
    signatures_path = Path(args.episode_signatures)
    for path in (historical_json_path, episodes_path, signatures_path):
        if not path.exists():
            raise FileNotFoundError(path)

    historical = json.loads(historical_json_path.read_text(encoding="utf-8"))
    config = historical.get("config")
    latest_window = historical.get("latest_window")
    if not isinstance(config, dict) or not isinstance(latest_window, dict):
        raise ValueError("historical regime artifact missing config or latest_window")

    episodes = pd.read_csv(episodes_path)
    if "episode_id" not in episodes.columns:
        episodes = episodes.reset_index(drop=True)
        episodes.insert(0, "episode_id", episodes.index.astype(int))
    episodes["recovered_without_retraining"] = (
        episodes["recovered_without_retraining"]
        .astype(str)
        .str.lower()
        .map({"true": True, "false": False})
    )
    if episodes["recovered_without_retraining"].isna().any():
        raise ValueError("could not parse recovered_without_retraining values")

    signatures = pd.read_csv(signatures_path, index_col="episode_id")
    try:
        signatures.index = signatures.index.astype(episodes["episode_id"].dtype)
    except (TypeError, ValueError):
        pass

    classified = classify_episodes(
        episodes,
        signatures,
        collapse_ratio=float(config["collapse_ratio"]),
        observation_rows=int(config["observation_rows"]),
    )
    summary = build_summary(
        classified,
        config=config,
        latest_window=latest_window,
        source_artifacts={
            "historical_json": stable_artifact_identifier(
                historical_json_path, REPOSITORY_ROOT
            ),
            "historical_episodes": stable_artifact_identifier(
                episodes_path, REPOSITORY_ROOT
            ),
            "episode_signatures": stable_artifact_identifier(
                signatures_path, REPOSITORY_ROOT
            ),
        },
    )

    episode_json_text = json.dumps(
        _strict_json_records(classified),
        indent=2,
        sort_keys=True,
        allow_nan=False,
    )
    summary_json_text = json.dumps(
        summary,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    episode_csv_path = out_dir / f"{args.stream}_classified_episodes.csv"
    episode_json_path = out_dir / f"{args.stream}_classified_episodes.json"
    summary_path = out_dir / f"{args.stream}_taxonomy_summary.json"

    csv_frame = classified.copy()
    csv_frame["volatility_features"] = csv_frame["volatility_features"].map(
        lambda values: json.dumps(values, separators=(",", ":"))
    )
    csv_frame.to_csv(episode_csv_path, index=False, lineterminator="\n")
    write_text_lf(episode_json_path, episode_json_text)
    write_text_lf(summary_path, summary_json_text)

    print()
    print("Core v1 Jump Risk historical regime taxonomy complete")
    print(f"Stream:              {args.stream}")
    print(f"Episodes:            {summary['episode_count']}")
    print(f"Digest:              {summary['deterministic_digest_sha256']}")
    print(f"Episode CSV:         {episode_csv_path}")
    print(f"Episode JSON:        {episode_json_path}")
    print(f"Summary JSON:        {summary_path}")
    print("Observation only: no Core state, NAV, orders, thresholds, or exposure were changed.")


if __name__ == "__main__":
    main()
