#!/usr/bin/env python
"""Fund Diversification Diagnostics v1.

Research-only diagnostic for Itera's promoted two-sleeve fund view.

This script measures whether the promoted crypto and equity sleeves behave as
complementary return streams by analyzing full-period, rolling, and stress-window
correlations.

No broker orders, live trading, runtime integration, dashboard integration, or
dynamic allocation decisions are made.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd


DEFAULT_CURVES = "artifacts/fund_side_by_side_composite_v1_tilted_4s/equity_curves.csv"
DEFAULT_OUT = "artifacts/fund_paper_readiness_v1"
WINDOWS = [
    ("FULL", "1900-01-01", "2100-01-01"),
    ("COVID_2020", "2020-02-01", "2020-06-30"),
    ("BEAR_2022", "2022-01-01", "2022-12-31"),
    ("POST_2022_RECOVERY", "2023-01-01", "2024-12-31"),
    ("RECENT_2025_PLUS", "2025-01-01", "2100-01-01"),
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Measure sleeve diversification for the promoted two-sleeve fund view",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--curves", default=DEFAULT_CURVES)
    p.add_argument("--crypto-column", default="CRYPTO_SLEEVE")
    p.add_argument("--equity-column", default="EQUITY_SLEEVE")
    p.add_argument("--rolling-windows", default="63,126,252")
    p.add_argument("--out-dir", default=DEFAULT_OUT)
    return p.parse_args()


def _detect_time_col(df: pd.DataFrame) -> str:
    lower = {str(c).lower(): c for c in df.columns}
    for name in ["timestamp", "date", "datetime", "time", "unnamed: 0"]:
        if name in lower:
            return str(lower[name])
    return str(df.columns[0])


def _read_curves(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing curves file: {path}")
    df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"Empty curves file: {path}")
    time_col = _detect_time_col(df)
    df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
    df = df.dropna(subset=[time_col]).set_index(time_col).sort_index()
    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_localize(None)
    return df


def _parse_windows(raw: str) -> list[int]:
    out = []
    for part in str(raw).split(","):
        part = part.strip()
        if not part:
            continue
        value = int(part)
        if value <= 1:
            raise ValueError(f"rolling windows must be > 1, got {value}")
        out.append(value)
    if not out:
        raise ValueError("at least one rolling window is required")
    return list(dict.fromkeys(out))


def _slice(df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end) + pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1)
    return df.loc[(df.index >= start_ts) & (df.index <= end_ts)].dropna()


def _corr_safe(df: pd.DataFrame) -> float:
    clean = df.dropna()
    if len(clean) < 3:
        return float("nan")
    if clean.iloc[:, 0].std(ddof=0) <= 1e-12 or clean.iloc[:, 1].std(ddof=0) <= 1e-12:
        return float("nan")
    return float(clean.iloc[:, 0].corr(clean.iloc[:, 1]))


def _beta_safe(y: pd.Series, x: pd.Series) -> float:
    clean = pd.concat([y.rename("y"), x.rename("x")], axis=1).dropna()
    if len(clean) < 3:
        return float("nan")
    var = float(clean["x"].var(ddof=0))
    if var <= 1e-12:
        return float("nan")
    return float(clean["y"].cov(clean["x"]) / var)


def _up_down_capture(strategy: pd.Series, benchmark: pd.Series) -> tuple[float, float]:
    clean = pd.concat([strategy.rename("strategy"), benchmark.rename("benchmark")], axis=1).dropna()
    if clean.empty:
        return float("nan"), float("nan")
    up = clean[clean["benchmark"] > 0]
    down = clean[clean["benchmark"] < 0]
    up_cap = float(up["strategy"].mean() / up["benchmark"].mean()) if len(up) and abs(up["benchmark"].mean()) > 1e-12 else float("nan")
    down_cap = float(down["strategy"].mean() / down["benchmark"].mean()) if len(down) and abs(down["benchmark"].mean()) > 1e-12 else float("nan")
    return up_cap, down_cap


def _make_correlation_summary(returns: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for name, start, end in WINDOWS:
        sub = _slice(returns, start, end)
        if len(sub) < 20:
            continue
        corr = _corr_safe(sub[["crypto_return", "equity_return"]])
        crypto_beta_to_equity = _beta_safe(sub["crypto_return"], sub["equity_return"])
        equity_beta_to_crypto = _beta_safe(sub["equity_return"], sub["crypto_return"])
        crypto_up_cap, crypto_down_cap = _up_down_capture(sub["crypto_return"], sub["equity_return"])
        equity_up_cap, equity_down_cap = _up_down_capture(sub["equity_return"], sub["crypto_return"])
        rows.append(
            {
                "window": name,
                "start": str(sub.index[0]),
                "end": str(sub.index[-1]),
                "bars": len(sub),
                "crypto_equity_corr": corr,
                "crypto_beta_to_equity": crypto_beta_to_equity,
                "equity_beta_to_crypto": equity_beta_to_crypto,
                "crypto_up_capture_vs_equity": crypto_up_cap,
                "crypto_down_capture_vs_equity": crypto_down_cap,
                "equity_up_capture_vs_crypto": equity_up_cap,
                "equity_down_capture_vs_crypto": equity_down_cap,
                "crypto_ann_vol_proxy": float(sub["crypto_return"].std(ddof=0) * np.sqrt(252.0)),
                "equity_ann_vol_proxy": float(sub["equity_return"].std(ddof=0) * np.sqrt(252.0)),
            }
        )
    return pd.DataFrame(rows)


def _make_rolling_correlation(returns: pd.DataFrame, windows: list[int]) -> pd.DataFrame:
    out = pd.DataFrame(index=returns.index)
    for w in windows:
        out[f"rolling_corr_{w}d"] = returns["crypto_return"].rolling(w, min_periods=w).corr(returns["equity_return"])
    return out.dropna(how="all")


def _make_rolling_summary(rolling: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for col in rolling.columns:
        s = rolling[col].dropna()
        if s.empty:
            continue
        rows.append(
            {
                "series": col,
                "observations": len(s),
                "mean_corr": float(s.mean()),
                "median_corr": float(s.median()),
                "min_corr": float(s.min()),
                "max_corr": float(s.max()),
                "pct_below_0": float((s < 0).mean() * 100.0),
                "pct_below_0_25": float((s < 0.25).mean() * 100.0),
                "pct_above_0_75": float((s > 0.75).mean() * 100.0),
            }
        )
    return pd.DataFrame(rows)


def _fmt(value: Any, digits: int = 4) -> str:
    try:
        if pd.isna(value):
            return "n/a"
        return f"{float(value):.{digits}f}"
    except Exception:
        return str(value)


def _md_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    if df.empty:
        return "_No rows._"
    if max_rows is not None:
        df = df.head(max_rows)
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        vals = []
        for c in df.columns:
            value = row[c]
            if isinstance(value, float):
                vals.append(_fmt(value))
            else:
                vals.append(str(value).replace("|", "\\|").replace("\n", " "))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def _write_summary_md(path: Path, corr_summary: pd.DataFrame, rolling_summary: pd.DataFrame, args: argparse.Namespace) -> None:
    full = corr_summary[corr_summary["window"] == "FULL"].iloc[0] if not corr_summary[corr_summary["window"] == "FULL"].empty else pd.Series(dtype=object)
    lines = [
        "# Fund Diversification Diagnostics v1",
        "",
        "Research-only correlation and diversification diagnostics for Itera's promoted two-sleeve fund view.",
        "",
        "## Inputs",
        "",
        "```text",
        f"Curves: {args.curves}",
        f"Crypto column: {args.crypto_column}",
        f"Equity column: {args.equity_column}",
        f"Rolling windows: {args.rolling_windows}",
        "```",
        "",
        "## Headline Read",
        "",
        "```text",
        f"Full-period crypto/equity return correlation: {_fmt(full.get('crypto_equity_corr'))}",
        f"Crypto beta to equity sleeve:              {_fmt(full.get('crypto_beta_to_equity'))}",
        f"Equity beta to crypto sleeve:              {_fmt(full.get('equity_beta_to_crypto'))}",
        "```",
        "",
        "A lower or unstable correlation supports the idea that the sleeves may be complementary. A persistently high correlation would weaken the diversification argument.",
        "",
        "## Window Correlation Summary",
        "",
        _md_table(corr_summary, max_rows=20),
        "",
        "## Rolling Correlation Summary",
        "",
        _md_table(rolling_summary, max_rows=20),
        "",
        "## Interpretation Guardrail",
        "",
        "```text",
        "Correlation is descriptive, not predictive. It can change during stress. This diagnostic supports fund-readiness review, but it does not approve a new sleeve, allocator, broker integration, or live trading.",
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rolling_windows = _parse_windows(args.rolling_windows)

    curves = _read_curves(Path(args.curves))
    for col in [args.crypto_column, args.equity_column]:
        if col not in curves.columns:
            raise ValueError(f"Missing required column '{col}' in {args.curves}. Columns={list(curves.columns)}")

    sleeve_curves = curves[[args.crypto_column, args.equity_column]].copy()
    sleeve_curves.columns = ["crypto_curve", "equity_curve"]
    sleeve_curves = sleeve_curves.dropna()
    returns = sleeve_curves.pct_change(fill_method=None).dropna()
    returns.columns = ["crypto_return", "equity_return"]

    corr_summary = _make_correlation_summary(returns)
    rolling_corr = _make_rolling_correlation(returns, rolling_windows)
    rolling_summary = _make_rolling_summary(rolling_corr)

    corr_summary.to_csv(out_dir / "correlation_summary.csv", index=False)
    rolling_corr.to_csv(out_dir / "rolling_correlation.csv")
    rolling_summary.to_csv(out_dir / "rolling_correlation_summary.csv", index=False)
    returns.to_csv(out_dir / "sleeve_return_inputs.csv")

    summary = {
        "research_status": "research_only_fund_diversification_diagnostics_v1",
        "inputs": {
            "curves": args.curves,
            "crypto_column": args.crypto_column,
            "equity_column": args.equity_column,
            "rolling_windows": rolling_windows,
        },
        "artifacts": {
            "correlation_summary": str(out_dir / "correlation_summary.csv"),
            "rolling_correlation": str(out_dir / "rolling_correlation.csv"),
            "rolling_correlation_summary": str(out_dir / "rolling_correlation_summary.csv"),
            "sleeve_return_inputs": str(out_dir / "sleeve_return_inputs.csv"),
            "diversification_summary_md": str(out_dir / "diversification_summary.md"),
            "diversification_summary_json": str(out_dir / "diversification_summary.json"),
        },
        "decision": {"status": "diagnostic_only", "not_approved": ["live_trading", "broker_integration", "paper_broker_execution", "dashboard_integration", "dynamic_allocator"]},
    }
    (out_dir / "diversification_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    _write_summary_md(out_dir / "diversification_summary.md", corr_summary, rolling_summary, args)

    with pd.option_context("display.max_columns", None, "display.width", 360, "display.float_format", "{:.4f}".format):
        print("\n=== FUND DIVERSIFICATION DIAGNOSTICS V1 ===")
        print(f"Curves: {args.curves}")
        print("\nCorrelation Summary:")
        print(corr_summary.to_string(index=False))
        print("\nRolling Correlation Summary:")
        print(rolling_summary.to_string(index=False))
    print(f"\nArtifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()
