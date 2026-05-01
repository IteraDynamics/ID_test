#!/usr/bin/env python
"""Run HMM regime analysis (research only)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from research.regimes.hmm_regime_v1 import build_hmm_features, fit_hmm_regime


DIAGNOSTIC_COLUMNS = [
    "log_return",
    "vol_20",
    "vol_ratio_20_60",
    "mom_20",
    "mom_60",
    "trend_dist_200",
    "ema_50_200_dist",
]


def _load_ohlcv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df[df.columns[0]] = pd.to_datetime(df[df.columns[0]])
    return df.set_index(df.columns[0]).sort_index()


def _build_state_diagnostics(
    features: pd.DataFrame,
    probabilities: pd.DataFrame,
    state_labels: dict[int, str],
    forward_days: int = 20,
) -> pd.DataFrame:
    """Summarize realized feature profiles by inferred HMM state.

    The optional forward return is reporting-only. It is calculated after fitting,
    is not passed into the HMM, and should not be used as a label input.
    """
    diag_frame = features.join(probabilities[["hmm_state_id", "hmm_state_label"]], how="inner")
    diag_frame[f"forward_{forward_days}d_return"] = (
        diag_frame["log_return"].shift(-1).rolling(forward_days).sum().shift(-(forward_days - 1))
    )

    total_obs = len(diag_frame)
    rows: list[dict[str, float | int | str]] = []

    for state_id in sorted(state_labels):
        state_rows = diag_frame[diag_frame["hmm_state_id"] == state_id]
        count = int(len(state_rows))
        row: dict[str, float | int | str] = {
            "state_id": state_id,
            "assigned_label": state_labels[state_id],
            "count": count,
            "percent_observations": count / total_obs if total_obs else 0.0,
        }

        for col in DIAGNOSTIC_COLUMNS:
            row[f"avg_{col}"] = float(state_rows[col].mean()) if count else float("nan")

        row[f"avg_forward_{forward_days}d_return"] = (
            float(state_rows[f"forward_{forward_days}d_return"].mean()) if count else float("nan")
        )
        rows.append(row)

    return pd.DataFrame(rows)


def _write_summary(
    out_dir: Path,
    data_path: str,
    result,
    diagnostics: pd.DataFrame,
) -> None:
    summary = {
        "data_path": data_path,
        "states": len(result.state_labels),
        "converged": bool(result.converged),
        "iterations": int(result.iterations),
        "log_likelihood": float(result.log_likelihood),
        "state_labels": {str(k): v for k, v in result.state_labels.items()},
        "state_counts": {
            str(int(row["state_id"])): int(row["count"])
            for _, row in diagnostics.iterrows()
        },
        "artifacts": {
            "state_probabilities": str(out_dir / "state_probabilities.csv"),
            "state_diagnostics": str(out_dir / "state_diagnostics.csv"),
            "summary": str(out_dir / "summary.json"),
        },
        "research_status": "shadow_mode_only",
        "notes": [
            "HMM output is research-only and must not replace deterministic Layer 1 yet.",
            "Forward 20-day return is reporting-only and is not used for fitting or label assignment.",
        ],
    }
    with (out_dir / "summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
        f.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", default="artifacts/hmm_regime_v1")
    args = parser.parse_args()

    df = _load_ohlcv(args.data)
    features = build_hmm_features(df)
    result, probs = fit_hmm_regime(features)
    diagnostics = _build_state_diagnostics(features, probs, result.state_labels)

    print("\n=== HMM REGIME ANALYSIS ===")
    print(f"States: {len(result.state_labels)}")
    print(f"Converged: {result.converged}")
    print(f"Iterations: {result.iterations}")
    print(f"Log likelihood: {result.log_likelihood:.6f}")

    print("\nState Labels:")
    for k, v in result.state_labels.items():
        print(f"  State {k}: {v}")

    print("\nState Diagnostics:")
    with pd.option_context(
        "display.max_columns",
        None,
        "display.width",
        220,
        "display.float_format",
        "{:.6f}".format,
    ):
        print(diagnostics.to_string(index=False))

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    probs.to_csv(out_dir / "state_probabilities.csv")
    diagnostics.to_csv(out_dir / "state_diagnostics.csv", index=False)
    _write_summary(out_dir, args.data, result, diagnostics)

    print(f"\nArtifacts saved to: {out_dir}")
    print(f"  - {out_dir / 'state_probabilities.csv'}")
    print(f"  - {out_dir / 'state_diagnostics.csv'}")
    print(f"  - {out_dir / 'summary.json'}")


if __name__ == "__main__":
    main()
