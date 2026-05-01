#!/usr/bin/env python
"""Analyze crypto sleeve performance by HMM composite regime.

Research-only attribution utility. Joins the shadow-mode crypto composite HMM
regime labels to an existing Fund v1 equity curve artifact and summarizes
forward next-bar returns by composite regime.

This script does not modify runtime behavior, strategy logic, allocation,
governors, or execution paths.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


DEFAULT_COMPOSITE_PATH = Path(
    "artifacts/hmm_regime_v1_crypto_composite/crypto_composite_regimes.csv"
)
DEFAULT_OUT_DIR = Path("artifacts/hmm_regime_v1_crypto_composite_performance")
REGIME_COLUMN = "composite_regime"


def _find_latest_equity_curves() -> Path:
    candidates = sorted(
        Path("artifacts").glob("**/equity_curves.csv"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(
            "Could not auto-discover an equity_curves.csv artifact. "
            "Pass --equity-curves explicitly, for example: "
            "--equity-curves artifacts/<fund_run>/equity_curves.csv"
        )
    return candidates[0]


def _read_time_indexed_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing required artifact: {path}")
    df = pd.read_csv(path, index_col=0)
    df.index = pd.to_datetime(df.index, errors="coerce")
    df = df[~df.index.isna()].sort_index()
    if df.empty:
        raise ValueError(f"No valid timestamp rows in artifact: {path}")
    return df


def _select_equity_columns(equity: pd.DataFrame) -> list[str]:
    numeric_cols = []
    for col in equity.columns:
        converted = pd.to_numeric(equity[col], errors="coerce")
        if converted.notna().sum() > 1:
            equity[col] = converted
            numeric_cols.append(str(col))
    if not numeric_cols:
        raise ValueError("No numeric equity curve columns found.")
    return numeric_cols


def _join_regimes_to_forward_returns(
    composite: pd.DataFrame,
    equity: pd.DataFrame,
    equity_cols: list[str],
) -> pd.DataFrame:
    if REGIME_COLUMN not in composite.columns:
        raise ValueError(f"Composite artifact missing required column: {REGIME_COLUMN}")

    start = max(composite.index.min(), equity.index.min())
    end = min(composite.index.max(), equity.index.max())
    if pd.isna(start) or pd.isna(end) or start >= end:
        raise ValueError(f"No overlapping period: start={start}, end={end}")

    composite_slice = composite.loc[start:end].copy()
    equity_slice = equity.loc[start:end, equity_cols].copy()

    # Regime at timestamp t is evaluated against the next observed equity return.
    # This is attribution, not a trading rule.
    forward_returns = equity_slice.pct_change().shift(-1)
    forward_returns = forward_returns.add_prefix("fwd_ret_")

    joined = composite_slice.join(forward_returns, how="outer").sort_index().ffill()
    joined = joined.dropna(subset=[REGIME_COLUMN])
    return joined


def _safe_return_stats(returns: pd.Series, baseline_avg: float, total_sum_return: float) -> dict[str, float | int]:
    returns = returns.dropna()
    count = int(len(returns))
    if count == 0:
        return {
            "bars": 0,
            "avg_forward_return": 0.0,
            "avg_forward_return_bps": 0.0,
            "median_forward_return": 0.0,
            "hit_rate": 0.0,
            "return_vol": 0.0,
            "avg_return_lift_vs_baseline": 0.0,
            "avg_return_lift_vs_baseline_bps": 0.0,
            "simple_sum_return": 0.0,
            "share_of_total_sum_return": 0.0,
        }

    avg = float(returns.mean())
    simple_sum = float(returns.sum())
    share = simple_sum / total_sum_return if abs(total_sum_return) > 1e-12 else 0.0
    lift = avg - baseline_avg
    return {
        "bars": count,
        "avg_forward_return": avg,
        "avg_forward_return_bps": avg * 10_000.0,
        "median_forward_return": float(returns.median()),
        "hit_rate": float((returns > 0).mean()),
        "return_vol": float(returns.std(ddof=0)),
        "avg_return_lift_vs_baseline": lift,
        "avg_return_lift_vs_baseline_bps": lift * 10_000.0,
        "simple_sum_return": simple_sum,
        "share_of_total_sum_return": float(share),
    }


def _summarize_returns(joined: pd.DataFrame, equity_cols: list[str]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    total_bars = len(joined)
    baseline_by_col = {
        col: float(joined[f"fwd_ret_{col}"].dropna().mean()) for col in equity_cols
    }
    total_sum_by_col = {
        col: float(joined[f"fwd_ret_{col}"].dropna().sum()) for col in equity_cols
    }

    for regime, grp in joined.groupby(REGIME_COLUMN, sort=False):
        for col in equity_cols:
            ret_col = f"fwd_ret_{col}"
            returns = grp[ret_col].dropna()
            stats = _safe_return_stats(
                returns,
                baseline_avg=baseline_by_col[col],
                total_sum_return=total_sum_by_col[col],
            )
            row = {
                "composite_regime": regime,
                "series": col,
                **stats,
                "pct_observations": float(stats["bars"] / total_bars) if total_bars else 0.0,
            }
            rows.append(row)

    return pd.DataFrame(rows).sort_values(["series", "composite_regime"])


def _summarize_overall(joined: pd.DataFrame, equity_cols: list[str]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for col in equity_cols:
        ret_col = f"fwd_ret_{col}"
        returns = joined[ret_col].dropna()
        count = int(len(returns))
        avg = float(returns.mean()) if count else 0.0
        rows.append(
            {
                "series": col,
                "bars": count,
                "avg_forward_return": avg,
                "avg_forward_return_bps": avg * 10_000.0,
                "median_forward_return": float(returns.median()) if count else 0.0,
                "hit_rate": float((returns > 0).mean()) if count else 0.0,
                "return_vol": float(returns.std(ddof=0)) if count else 0.0,
                "simple_sum_return": float(returns.sum()) if count else 0.0,
            }
        )
    return pd.DataFrame(rows)


def _build_regime_rankings(regime_summary: pd.DataFrame) -> pd.DataFrame:
    ranking_frames = []
    for series, grp in regime_summary.groupby("series", sort=False):
        ranked = grp.sort_values("avg_forward_return", ascending=False).copy()
        ranked["rank_by_avg_forward_return"] = range(1, len(ranked) + 1)
        ranking_frames.append(ranked)
    return pd.concat(ranking_frames, ignore_index=True)


def _format_markdown_value(value: object, floatfmt: str = ".6f") -> str:
    if isinstance(value, float):
        return format(value, floatfmt)
    return str(value)


def _to_markdown_table(df: pd.DataFrame, floatfmt: str = ".6f") -> str:
    if df.empty:
        return "_No rows._"
    columns = [str(col) for col in df.columns]
    lines = ["| " + " | ".join(columns) + " |"]
    lines.append("| " + " | ".join(["---"] * len(columns)) + " |")
    for _, row in df.iterrows():
        values = [_format_markdown_value(row[col], floatfmt=floatfmt) for col in df.columns]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def _primary_series(ranking: pd.DataFrame) -> str:
    series_set = set(ranking["series"])
    for candidate in ["crypto_sleeve", "portfolio", "itera_four_sleeve"]:
        if candidate in series_set:
            return candidate
    return str(ranking["series"].iloc[0])


def _write_markdown(
    out_path: Path,
    equity_curves_path: Path,
    composite_path: Path,
    overall: pd.DataFrame,
    ranking: pd.DataFrame,
) -> None:
    primary_series = _primary_series(ranking)
    primary = ranking[ranking["series"] == primary_series].sort_values("rank_by_avg_forward_return")

    lines = [
        "# HMM Regime v1 — Crypto Composite Performance Attribution",
        "",
        "## Status",
        "",
        "Research-only attribution. This joins shadow-mode crypto composite HMM regimes to an existing equity curve artifact and summarizes forward next-bar returns by regime.",
        "",
        "## Inputs",
        "",
        "```text",
        f"Composite regimes: {composite_path}",
        f"Equity curves: {equity_curves_path}",
        "Return alignment: composite regime at time t mapped to next-bar equity return after t",
        "```",
        "",
        "## Overall Series Summary",
        "",
        _to_markdown_table(overall),
        "",
        f"## Regime Ranking — {primary_series}",
        "",
        _to_markdown_table(
            primary[
                [
                    "composite_regime",
                    "bars",
                    "pct_observations",
                    "avg_forward_return_bps",
                    "avg_return_lift_vs_baseline_bps",
                    "hit_rate",
                    "simple_sum_return",
                    "share_of_total_sum_return",
                    "rank_by_avg_forward_return",
                ]
            ]
        ),
        "",
        "## Interpretation Guardrail",
        "",
        "```text",
        "This is attribution evidence only, not an execution rule.",
        "The script intentionally avoids compounding non-contiguous regime slices because that can create misleading magnitudes.",
        "Do not wire composite regimes into Fund v1 paper trading.",
        "If the attribution is useful, the next step is a separate shadow-mode governor hypothesis test with explicit costs and transition rules.",
        "```",
        "",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--composite", default=str(DEFAULT_COMPOSITE_PATH))
    parser.add_argument("--equity-curves", default=None)
    parser.add_argument("--out", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    composite_path = Path(args.composite)
    equity_curves_path = Path(args.equity_curves) if args.equity_curves else _find_latest_equity_curves()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    composite = _read_time_indexed_csv(composite_path)
    equity = _read_time_indexed_csv(equity_curves_path)
    equity_cols = _select_equity_columns(equity)

    joined = _join_regimes_to_forward_returns(composite, equity, equity_cols)
    regime_summary = _summarize_returns(joined, equity_cols)
    overall = _summarize_overall(joined, equity_cols)
    ranking = _build_regime_rankings(regime_summary)
    primary_series = _primary_series(ranking)

    joined.to_csv(out_dir / "composite_regime_forward_returns.csv")
    regime_summary.to_csv(out_dir / "regime_performance_summary.csv", index=False)
    overall.to_csv(out_dir / "overall_performance_summary.csv", index=False)
    ranking.to_csv(out_dir / "regime_performance_ranking.csv", index=False)

    payload = {
        "research_status": "shadow_mode_only",
        "inputs": {
            "composite_regimes": str(composite_path),
            "equity_curves": str(equity_curves_path),
        },
        "alignment": {
            "method": "composite regime at time t joined to next-bar forward equity return after t",
            "bars": int(len(joined)),
            "start": str(joined.index.min()),
            "end": str(joined.index.max()),
            "equity_columns": equity_cols,
            "primary_series": primary_series,
        },
        "metric_notes": [
            "Regime slices are non-contiguous; compounded conditional returns and conditional drawdowns are intentionally not reported.",
            "Use average return, lift versus baseline, hit rate, and contribution-style sums as attribution evidence only.",
        ],
        "artifacts": {
            "composite_regime_forward_returns": str(out_dir / "composite_regime_forward_returns.csv"),
            "regime_performance_summary": str(out_dir / "regime_performance_summary.csv"),
            "overall_performance_summary": str(out_dir / "overall_performance_summary.csv"),
            "regime_performance_ranking": str(out_dir / "regime_performance_ranking.csv"),
            "summary_md": str(out_dir / "summary.md"),
            "summary_json": str(out_dir / "summary.json"),
        },
        "decision": {
            "status": "research_only_attribution",
            "next_step": "review_whether_composite_regimes_explain_fund_v1_crypto_sleeve_behavior",
            "not_approved": [
                "fund_v1_runtime_change",
                "direct_strategy_gating",
                "exposure_scaling",
                "allocator_integration",
                "production_layer_1_replacement",
            ],
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    _write_markdown(out_dir / "summary.md", equity_curves_path, composite_path, overall, ranking)

    print("\n=== HMM CRYPTO COMPOSITE PERFORMANCE ATTRIBUTION ===")
    print(f"Composite: {composite_path}")
    print(f"Equity curves: {equity_curves_path}")
    with pd.option_context("display.max_columns", None, "display.width", 220, "display.float_format", "{:.6f}".format):
        print("\nOverall Performance Summary:")
        print(overall.to_string(index=False))
        print(f"\nRegime Ranking — {primary_series}:")
        print(
            ranking[ranking["series"] == primary_series]
            .sort_values("rank_by_avg_forward_return")
            .to_string(index=False)
        )
    print(f"\nArtifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()
