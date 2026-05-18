#!/usr/bin/env python
"""Fund Paper Readiness v1 — sleeve correlation diagnostics.

Research-only diagnostic for Itera's promoted two-sleeve paper fund view.
Measures whether crypto and equity sleeve returns are actually complementary
through time.

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

import pandas as pd

from scripts.run_fund_paper_readiness_v1 import (
    DEFAULT_CURVES,
    _md_table,
    _normalize_curve,
    _perf,
    _read_curves,
    _slice,
)


DEFAULT_OUT = "artifacts/fund_paper_correlation_diagnostics_v1"
ROLLING_WINDOWS = [63, 126, 252]
NAMED_WINDOWS = [
    ("FULL", "1900-01-01", "2100-01-01"),
    ("COVID_2020", "2020-02-01", "2020-06-30"),
    ("BEAR_2022", "2022-01-01", "2022-12-31"),
    ("POST_2022_RECOVERY", "2023-01-01", "2024-12-31"),
    ("RECENT_2025_PLUS", "2025-01-01", "2100-01-01"),
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Measure crypto/equity sleeve correlation for fund paper readiness",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--curves", default=DEFAULT_CURVES)
    p.add_argument("--crypto-column", default="CRYPTO_SLEEVE")
    p.add_argument("--equity-column", default="EQUITY_SLEEVE")
    p.add_argument("--fund-column", default="FUND_STATIC_CRYPTO50_EQUITY50")
    p.add_argument("--out-dir", default=DEFAULT_OUT)
    return p.parse_args()


def _corr(a: pd.Series, b: pd.Series) -> float:
    aligned = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
    if len(aligned) < 3:
        return 0.0
    return float(aligned["a"].corr(aligned["b"]))


def _return_frame(curves: pd.DataFrame, crypto_col: str, equity_col: str, fund_col: str | None) -> pd.DataFrame:
    missing = [c for c in [crypto_col, equity_col] if c not in curves.columns]
    if missing:
        raise ValueError(f"Missing required columns {missing}. Columns={list(curves.columns)}")

    crypto = _normalize_curve(curves[crypto_col], 1.0).rename("crypto")
    equity = _normalize_curve(curves[equity_col], 1.0).rename("equity")
    out = pd.concat([crypto, equity], axis=1).dropna()
    if fund_col and fund_col in curves.columns:
        fund = _normalize_curve(curves[fund_col], 1.0).rename("fund_reference")
        out = pd.concat([out, fund], axis=1).dropna()
    out["crypto_return"] = out["crypto"].pct_change(fill_method=None)
    out["equity_return"] = out["equity"].pct_change(fill_method=None)
    if "fund_reference" in out.columns:
        out["fund_reference_return"] = out["fund_reference"].pct_change(fill_method=None)
    return out.dropna()


def _build_window_summary(rets: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for name, start, end in NAMED_WINDOWS:
        sub = rets.loc[(rets.index >= pd.Timestamp(start)) & (rets.index <= pd.Timestamp(end))]
        if len(sub) < 20:
            continue
        row: dict[str, Any] = {
            "window": name,
            "start": str(sub.index[0]),
            "end": str(sub.index[-1]),
            "bars": len(sub),
            "crypto_equity_corr": _corr(sub["crypto_return"], sub["equity_return"]),
            "crypto_mean_daily_return_pct": float(sub["crypto_return"].mean() * 100.0),
            "equity_mean_daily_return_pct": float(sub["equity_return"].mean() * 100.0),
            "crypto_vol_daily_pct": float(sub["crypto_return"].std(ddof=0) * 100.0),
            "equity_vol_daily_pct": float(sub["equity_return"].std(ddof=0) * 100.0),
        }
        if "fund_reference_return" in sub.columns:
            row["fund_crypto_corr"] = _corr(sub["fund_reference_return"], sub["crypto_return"])
            row["fund_equity_corr"] = _corr(sub["fund_reference_return"], sub["equity_return"])
        rows.append(row)
    return pd.DataFrame(rows)


def _rolling_correlation(rets: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for window in ROLLING_WINDOWS:
        s = rets["crypto_return"].rolling(window).corr(rets["equity_return"])
        frames.append(s.rename(f"rolling_corr_{window}d"))
    return pd.concat(frames, axis=1).dropna(how="all")


def _rolling_summary(rolling: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for col in rolling.columns:
        s = rolling[col].dropna()
        if s.empty:
            continue
        rows.append(
            {
                "series": col,
                "mean_corr": float(s.mean()),
                "median_corr": float(s.median()),
                "min_corr": float(s.min()),
                "max_corr": float(s.max()),
                "pct_corr_below_0": float((s < 0.0).mean() * 100.0),
                "pct_corr_below_0_25": float((s < 0.25).mean() * 100.0),
                "pct_corr_above_0_75": float((s > 0.75).mean() * 100.0),
            }
        )
    return pd.DataFrame(rows)


def _write_summary_md(
    path: Path,
    args: argparse.Namespace,
    window_summary: pd.DataFrame,
    rolling_summary: pd.DataFrame,
    perf: pd.DataFrame,
) -> None:
    lines = [
        "# Fund Paper Correlation Diagnostics v1",
        "",
        "Research-only diagnostic measuring whether Itera's promoted crypto and equity sleeves behave as complementary return streams.",
        "",
        "## Inputs",
        "",
        "```text",
        f"Curves: {args.curves}",
        f"Crypto column: {args.crypto_column}",
        f"Equity column: {args.equity_column}",
        f"Fund reference column: {args.fund_column}",
        "```",
        "",
        "## Window Correlation Summary",
        "",
        _md_table(window_summary, max_rows=50),
        "",
        "## Rolling Correlation Summary",
        "",
        _md_table(rolling_summary, max_rows=20),
        "",
        "## Reference Performance",
        "",
        _md_table(perf, max_rows=20),
        "",
        "## Interpretation",
        "",
        "```text",
        "Lower and unstable correlation between sleeves supports the side-by-side fund thesis.",
        "High correlation during stress windows would weaken the diversification story and should be monitored.",
        "This is a diagnostic only; it does not approve new allocation logic or strategy changes.",
        "```",
        "",
        "## Guardrail",
        "",
        "```text",
        "No live trading, broker integration, paper-broker execution, dashboard integration, or dynamic allocator decisions are approved.",
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    curves = _read_curves(Path(args.curves))
    fund_col = args.fund_column if args.fund_column in curves.columns else None
    rets = _return_frame(curves, args.crypto_column, args.equity_column, fund_col)
    window_summary = _build_window_summary(rets)
    rolling = _rolling_correlation(rets)
    rolling_sum = _rolling_summary(rolling)

    perf_rows = []
    perf_rows.append({"series": "CRYPTO_SLEEVE", "start": str(rets.index[0]), "end": str(rets.index[-1]), "bars": len(rets), **_perf(rets["crypto"])})
    perf_rows.append({"series": "EQUITY_SLEEVE", "start": str(rets.index[0]), "end": str(rets.index[-1]), "bars": len(rets), **_perf(rets["equity"])})
    if "fund_reference" in rets.columns:
        perf_rows.append({"series": fund_col or "FUND_REFERENCE", "start": str(rets.index[0]), "end": str(rets.index[-1]), "bars": len(rets), **_perf(rets["fund_reference"])})
    perf = pd.DataFrame(perf_rows)

    rets.to_csv(out_dir / "sleeve_returns.csv")
    window_summary.to_csv(out_dir / "correlation_summary.csv", index=False)
    rolling.to_csv(out_dir / "rolling_correlation.csv")
    rolling_sum.to_csv(out_dir / "rolling_correlation_summary.csv", index=False)
    perf.to_csv(out_dir / "reference_performance.csv", index=False)

    summary = {
        "research_status": "research_only_fund_paper_correlation_diagnostics_v1",
        "inputs": vars(args),
        "artifacts": {
            "sleeve_returns": str(out_dir / "sleeve_returns.csv"),
            "correlation_summary": str(out_dir / "correlation_summary.csv"),
            "rolling_correlation": str(out_dir / "rolling_correlation.csv"),
            "rolling_correlation_summary": str(out_dir / "rolling_correlation_summary.csv"),
            "reference_performance": str(out_dir / "reference_performance.csv"),
            "summary_json": str(out_dir / "summary.json"),
            "summary_md": str(out_dir / "summary.md"),
        },
        "decision": {
            "status": "diagnostic_only",
            "not_approved": ["live_trading", "broker_integration", "paper_broker_execution", "dashboard_integration", "dynamic_allocator"],
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    _write_summary_md(out_dir / "summary.md", args, window_summary, rolling_sum, perf)

    with pd.option_context("display.max_columns", None, "display.width", 360, "display.float_format", "{:.4f}".format):
        print("\n=== FUND PAPER CORRELATION DIAGNOSTICS V1 ===")
        print(f"Curves: {args.curves}")
        print(f"Fund reference column loaded: {fund_col if fund_col else 'none'}")
        print("\nWindow Correlation Summary:")
        print(window_summary.to_string(index=False))
        print("\nRolling Correlation Summary:")
        print(rolling_sum.to_string(index=False))
        print("\nReference Performance:")
        print(perf.to_string(index=False))
    print(f"\nArtifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()
