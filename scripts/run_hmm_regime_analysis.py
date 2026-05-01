#!/usr/bin/env python
"""Run HMM regime analysis (research only)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from research.harness.resampler import resample_ohlcv
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

DATE_COLUMN_CANDIDATES = [
    "timestamp",
    "datetime",
    "date",
    "time",
    "open_time",
    "start_time",
]

OHLCV_COLUMN_CANDIDATES = {
    "open": ["open", "Open", "OPEN"],
    "high": ["high", "High", "HIGH"],
    "low": ["low", "Low", "LOW"],
    "close": [
        "close",
        "Close",
        "CLOSE",
        "adj_close",
        "Adj Close",
        "adjusted_close",
        "price",
        "last",
    ],
    "volume": ["volume", "Volume", "VOLUME", "vol", "Vol"],
}


def _find_column(columns: pd.Index, candidates: list[str]) -> str | None:
    exact = {str(col): str(col) for col in columns}
    for candidate in candidates:
        if candidate in exact:
            return exact[candidate]

    normalized = {str(col).strip().lower().replace(" ", "_"): str(col) for col in columns}
    for candidate in candidates:
        key = candidate.strip().lower().replace(" ", "_")
        if key in normalized:
            return normalized[key]
    return None


def _load_ohlcv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"Input file is empty: {path}")

    date_col = _find_column(df.columns, DATE_COLUMN_CANDIDATES) or str(df.columns[0])
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce", utc=False)
    df = df.dropna(subset=[date_col]).set_index(date_col).sort_index()

    rename_map: dict[str, str] = {}
    for canonical, candidates in OHLCV_COLUMN_CANDIDATES.items():
        found = _find_column(df.columns, candidates)
        if found is not None:
            rename_map[found] = canonical

    if "close" not in rename_map.values() and "close" not in df.columns:
        available = ", ".join(str(col) for col in df.columns)
        close_candidates = OHLCV_COLUMN_CANDIDATES["close"]
        raise ValueError(
            "Could not find a close-price column. "
            f"Looked for: {close_candidates}. "
            f"Available columns: [{available}]"
        )

    df = df.rename(columns=rename_map)
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["close"])

    if df.empty:
        raise ValueError(f"No valid timestamp/close rows after loading: {path}")

    return df


def _maybe_resample(df: pd.DataFrame, freq: str | None) -> pd.DataFrame:
    if not freq:
        return df

    required = {"open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"Cannot resample to {freq}; missing OHLC columns: {sorted(missing)}. "
            "Resampling requires open, high, low, close."
        )
    return resample_ohlcv(df, freq)


def _build_state_diagnostics(
    features: pd.DataFrame,
    probabilities: pd.DataFrame,
    state_labels: dict[int, str],
    forward_bars: int = 20,
) -> pd.DataFrame:
    """Summarize realized feature profiles by inferred HMM state.

    The optional forward return is reporting-only. It is calculated after fitting,
    is not passed into the HMM, and should not be used as a label input.
    """
    diag_frame = features.join(probabilities[["hmm_state_id", "hmm_state_label"]], how="inner")
    diag_frame[f"forward_{forward_bars}bar_return"] = (
        diag_frame["log_return"].shift(-1).rolling(forward_bars).sum().shift(-(forward_bars - 1))
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

        row[f"avg_forward_{forward_bars}bar_return"] = (
            float(state_rows[f"forward_{forward_bars}bar_return"].mean()) if count else float("nan")
        )
        rows.append(row)

    return pd.DataFrame(rows)


def _write_summary(
    out_dir: Path,
    data_path: str,
    resample: str | None,
    result,
    diagnostics: pd.DataFrame,
) -> None:
    summary = {
        "data_path": data_path,
        "resample": resample,
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
            "Forward 20-bar return is reporting-only and is not used for fitting or label assignment.",
        ],
    }
    with (out_dir / "summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
        f.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", default="artifacts/hmm_regime_v1")
    parser.add_argument(
        "--resample",
        default=None,
        help="Optional pandas resample frequency such as 4h or 1D. Uses closed-bar OHLCV resampling.",
    )
    args = parser.parse_args()

    df = _load_ohlcv(args.data)
    df = _maybe_resample(df, args.resample)
    features = build_hmm_features(df)
    result, probs = fit_hmm_regime(features)
    diagnostics = _build_state_diagnostics(features, probs, result.state_labels)

    print("\n=== HMM REGIME ANALYSIS ===")
    print(f"Data: {args.data}")
    print(f"Resample: {args.resample or 'none'}")
    print(f"Bars after load/resample: {len(df)}")
    print(f"Feature rows: {len(features)}")
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
    _write_summary(out_dir, args.data, args.resample, result, diagnostics)

    print(f"\nArtifacts saved to: {out_dir}")
    print(f"  - {out_dir / 'state_probabilities.csv'}")
    print(f"  - {out_dir / 'state_diagnostics.csv'}")
    print(f"  - {out_dir / 'summary.json'}")


if __name__ == "__main__":
    main()
