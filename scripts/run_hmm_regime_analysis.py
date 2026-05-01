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
from research.regimes.hmm_regime_v1 import HMMConfig, build_hmm_features, fit_hmm_regime


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


def _build_transition_matrix(probabilities: pd.DataFrame, state_labels: dict[int, str]) -> pd.DataFrame:
    states = sorted(state_labels)
    label_by_state = {state: f"{state}:{state_labels[state]}" for state in states}
    counts = pd.DataFrame(0, index=states, columns=states, dtype=int)

    observed = probabilities["hmm_state_id"].astype(int)
    prev_states = observed.iloc[:-1].to_numpy()
    next_states = observed.iloc[1:].to_numpy()
    for prev_state, next_state in zip(prev_states, next_states):
        counts.loc[int(prev_state), int(next_state)] += 1

    row_totals = counts.sum(axis=1).replace(0, pd.NA)
    matrix = counts.div(row_totals, axis=0).fillna(0.0)
    matrix.index = [label_by_state[s] for s in states]
    matrix.columns = [label_by_state[s] for s in states]
    return matrix


def _build_state_episodes(probabilities: pd.DataFrame, state_labels: dict[int, str]) -> pd.DataFrame:
    observed = probabilities["hmm_state_id"].astype(int)
    if observed.empty:
        return pd.DataFrame(
            columns=[
                "episode_id",
                "state_id",
                "state_label",
                "start_time",
                "end_time",
                "bars",
            ]
        )

    episodes: list[dict[str, object]] = []
    episode_id = 0
    start_pos = 0
    current_state = int(observed.iloc[0])

    for pos in range(1, len(observed)):
        state = int(observed.iloc[pos])
        if state != current_state:
            idx = observed.index
            episodes.append(
                {
                    "episode_id": episode_id,
                    "state_id": current_state,
                    "state_label": state_labels[current_state],
                    "start_time": idx[start_pos],
                    "end_time": idx[pos - 1],
                    "bars": pos - start_pos,
                }
            )
            episode_id += 1
            start_pos = pos
            current_state = state

    idx = observed.index
    episodes.append(
        {
            "episode_id": episode_id,
            "state_id": current_state,
            "state_label": state_labels[current_state],
            "start_time": idx[start_pos],
            "end_time": idx[-1],
            "bars": len(observed) - start_pos,
        }
    )
    return pd.DataFrame(episodes)


def _build_dwell_summary(episodes: pd.DataFrame, state_labels: dict[int, str]) -> pd.DataFrame:
    rows: list[dict[str, float | int | str]] = []
    for state_id in sorted(state_labels):
        state_episodes = episodes[episodes["state_id"] == state_id]
        episode_count = int(len(state_episodes))
        if episode_count:
            bars = state_episodes["bars"].astype(float)
            rows.append(
                {
                    "state_id": state_id,
                    "state_label": state_labels[state_id],
                    "episode_count": episode_count,
                    "avg_dwell_bars": float(bars.mean()),
                    "median_dwell_bars": float(bars.median()),
                    "max_dwell_bars": int(bars.max()),
                    "single_bar_episode_pct": float((bars == 1).mean()),
                }
            )
        else:
            rows.append(
                {
                    "state_id": state_id,
                    "state_label": state_labels[state_id],
                    "episode_count": 0,
                    "avg_dwell_bars": 0.0,
                    "median_dwell_bars": 0.0,
                    "max_dwell_bars": 0,
                    "single_bar_episode_pct": 0.0,
                }
            )
    return pd.DataFrame(rows)


def _write_summary(
    out_dir: Path,
    data_path: str,
    resample: str | None,
    config: HMMConfig,
    result,
    diagnostics: pd.DataFrame,
    transition_matrix: pd.DataFrame,
    dwell_summary: pd.DataFrame,
) -> None:
    summary = {
        "data_path": data_path,
        "resample": resample,
        "config": {
            "n_states": int(config.n_states),
            "max_iter": int(config.max_iter),
            "tol": float(config.tol),
            "random_seed": int(config.random_seed),
            "min_std": float(config.min_std),
        },
        "states": len(result.state_labels),
        "converged": bool(result.converged),
        "iterations": int(result.iterations),
        "log_likelihood": float(result.log_likelihood),
        "state_labels": {str(k): v for k, v in result.state_labels.items()},
        "state_counts": {
            str(int(row["state_id"])): int(row["count"])
            for _, row in diagnostics.iterrows()
        },
        "state_persistence": {
            str(index): float(transition_matrix.loc[index, index])
            for index in transition_matrix.index
        },
        "dwell_summary": {
            str(int(row["state_id"])): {
                "state_label": row["state_label"],
                "episode_count": int(row["episode_count"]),
                "avg_dwell_bars": float(row["avg_dwell_bars"]),
                "median_dwell_bars": float(row["median_dwell_bars"]),
                "max_dwell_bars": int(row["max_dwell_bars"]),
                "single_bar_episode_pct": float(row["single_bar_episode_pct"]),
            }
            for _, row in dwell_summary.iterrows()
        },
        "artifacts": {
            "state_probabilities": str(out_dir / "state_probabilities.csv"),
            "state_diagnostics": str(out_dir / "state_diagnostics.csv"),
            "transition_matrix": str(out_dir / "transition_matrix.csv"),
            "dwell_summary": str(out_dir / "dwell_summary.csv"),
            "state_episodes": str(out_dir / "state_episodes.csv"),
            "summary": str(out_dir / "summary.json"),
        },
        "research_status": "shadow_mode_only",
        "notes": [
            "HMM output is research-only and must not replace deterministic Layer 1 yet.",
            "Forward 20-bar return is reporting-only and is not used for fitting or label assignment.",
            "Transition and dwell diagnostics are descriptive and are not strategy rules.",
        ],
    }
    with (out_dir / "summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True, default=str)
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
    parser.add_argument("--max-iter", type=int, default=75, help="Maximum HMM EM iterations")
    parser.add_argument("--tol", type=float, default=1e-5, help="HMM convergence tolerance")
    args = parser.parse_args()

    df = _load_ohlcv(args.data)
    df = _maybe_resample(df, args.resample)
    features = build_hmm_features(df)
    config = HMMConfig(max_iter=args.max_iter, tol=args.tol)
    result, probs = fit_hmm_regime(features, config=config)
    diagnostics = _build_state_diagnostics(features, probs, result.state_labels)
    transition_matrix = _build_transition_matrix(probs, result.state_labels)
    state_episodes = _build_state_episodes(probs, result.state_labels)
    dwell_summary = _build_dwell_summary(state_episodes, result.state_labels)

    print("\n=== HMM REGIME ANALYSIS ===")
    print(f"Data: {args.data}")
    print(f"Resample: {args.resample or 'none'}")
    print(f"Bars after load/resample: {len(df)}")
    print(f"Feature rows: {len(features)}")
    print(f"States: {len(result.state_labels)}")
    print(f"Max iterations: {config.max_iter}")
    print(f"Tolerance: {config.tol}")
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

    print("\nTransition Matrix:")
    with pd.option_context(
        "display.max_columns",
        None,
        "display.width",
        220,
        "display.float_format",
        "{:.4f}".format,
    ):
        print(transition_matrix.to_string())

    print("\nDwell Summary:")
    with pd.option_context(
        "display.max_columns",
        None,
        "display.width",
        220,
        "display.float_format",
        "{:.4f}".format,
    ):
        print(dwell_summary.to_string(index=False))

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    probs.to_csv(out_dir / "state_probabilities.csv")
    diagnostics.to_csv(out_dir / "state_diagnostics.csv", index=False)
    transition_matrix.to_csv(out_dir / "transition_matrix.csv")
    dwell_summary.to_csv(out_dir / "dwell_summary.csv", index=False)
    state_episodes.to_csv(out_dir / "state_episodes.csv", index=False)
    _write_summary(
        out_dir,
        args.data,
        args.resample,
        config,
        result,
        diagnostics,
        transition_matrix,
        dwell_summary,
    )

    print(f"\nArtifacts saved to: {out_dir}")
    print(f"  - {out_dir / 'state_probabilities.csv'}")
    print(f"  - {out_dir / 'state_diagnostics.csv'}")
    print(f"  - {out_dir / 'transition_matrix.csv'}")
    print(f"  - {out_dir / 'dwell_summary.csv'}")
    print(f"  - {out_dir / 'state_episodes.csv'}")
    print(f"  - {out_dir / 'summary.json'}")


if __name__ == "__main__":
    main()
