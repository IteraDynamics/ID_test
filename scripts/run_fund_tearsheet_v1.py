#!/usr/bin/env python
"""Fund Tear Sheet v1 generator.

Reporting-only script that packages existing fund side-by-side composite artifacts
into a concise investor-style markdown tear sheet.

No strategy research, paper trading, live allocation, broker/execution, runtime,
dashboard, or dynamic allocator changes are made.
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


DEFAULT_OUT = "artifacts/fund_tearsheet_v1"
DEFAULT_PRIMARY = "artifacts/fund_side_by_side_composite_v1_tilted_4s"
DEFAULT_SECONDARY = "artifacts/fund_side_by_side_composite_v1"
PREFERRED_SERIES = "FUND_STATIC_CRYPTO50_EQUITY50"
SECONDARY_SERIES = "FUND_STATIC_CRYPTO60_EQUITY40"
BENCHMARK_ORDER = [
    "CRYPTO_SLEEVE",
    "EQUITY_SLEEVE",
    "PASSIVE_SPY_QQQ_50_50",
    "QQQ_HODL",
    "SPY_HODL",
    "BTC_ETH_50_50_DAILY_REBAL",
    "BTC_ETH_60_40_DAILY_REBAL",
    "BTC_HODL",
    "ETH_HODL",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate Fund Tear Sheet v1 from fund composite artifacts",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--primary-dir", default=DEFAULT_PRIMARY, help="Primary composite artifact directory, usually tilted 4-sleeve run.")
    p.add_argument("--secondary-dir", default=DEFAULT_SECONDARY, help="Secondary composite artifact directory, usually Fund_v1 daily run with crypto benchmarks.")
    p.add_argument("--preferred-series", default=PREFERRED_SERIES)
    p.add_argument("--secondary-series", default=SECONDARY_SERIES)
    p.add_argument("--out-dir", default=DEFAULT_OUT)
    return p.parse_args()


def _read_csv_required(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing required artifact: {path}")
    df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"Empty required artifact: {path}")
    return df


def _read_csv_optional(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _series_rows(perf: pd.DataFrame, names: list[str], source_label: str) -> pd.DataFrame:
    rows = perf[perf["series"].isin(names)].copy()
    if rows.empty:
        return rows
    rows.insert(0, "source", source_label)
    order = {name: i for i, name in enumerate(names)}
    rows["_order"] = rows["series"].map(order).fillna(999)
    return rows.sort_values("_order").drop(columns=["_order"])


def _fmt_pct(value: Any) -> str:
    try:
        return f"{float(value):.2f}%"
    except Exception:
        return "n/a"


def _fmt_num(value: Any) -> str:
    try:
        return f"{float(value):.3f}"
    except Exception:
        return "n/a"


def _fmt_int(value: Any) -> str:
    try:
        return f"{int(round(float(value)))}"
    except Exception:
        return "n/a"


def _metric(row: pd.Series, col: str, kind: str = "num") -> str:
    if row is None or row.empty or col not in row:
        return "n/a"
    if kind == "pct":
        return _fmt_pct(row[col])
    if kind == "int":
        return _fmt_int(row[col])
    return _fmt_num(row[col])


def _one_row(df: pd.DataFrame, series: str) -> pd.Series:
    rows = df[df["series"] == series]
    if rows.empty:
        return pd.Series(dtype=object)
    return rows.iloc[0]


def _md_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    if df.empty:
        return "_No rows available._"
    if max_rows is not None:
        df = df.head(max_rows)
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        vals = []
        for c in df.columns:
            value = row[c]
            if isinstance(value, float):
                vals.append(f"{value:.4f}")
            else:
                vals.append(str(value).replace("|", "\\|").replace("\n", " "))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def _select_display_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "source",
        "series",
        "start",
        "end",
        "cagr_pct",
        "max_drawdown_pct",
        "sharpe",
        "sortino",
        "calmar",
        "ann_vol_pct",
        "worst_90d_return_pct",
        "worst_180d_return_pct",
        "max_time_underwater_days",
    ]
    existing = [c for c in cols if c in df.columns]
    return df[existing].copy()


def _benchmark_table(primary_perf: pd.DataFrame, secondary_perf: pd.DataFrame, preferred_series: str) -> pd.DataFrame:
    rows = []
    preferred_primary = _one_row(primary_perf, preferred_series)
    preferred_secondary = _one_row(secondary_perf, preferred_series)
    for bench in BENCHMARK_ORDER:
        bench_row = _one_row(primary_perf, bench)
        source = "primary"
        compare_row = preferred_primary
        if bench_row.empty:
            bench_row = _one_row(secondary_perf, bench)
            source = "secondary"
            compare_row = preferred_secondary if not preferred_secondary.empty else preferred_primary
        if bench_row.empty or compare_row.empty:
            continue
        rows.append(
            {
                "benchmark": bench,
                "benchmark_source": source,
                "preferred_cagr_pct": compare_row.get("cagr_pct"),
                "benchmark_cagr_pct": bench_row.get("cagr_pct"),
                "cagr_delta_pct": compare_row.get("cagr_pct") - bench_row.get("cagr_pct"),
                "preferred_maxdd_pct": compare_row.get("max_drawdown_pct"),
                "benchmark_maxdd_pct": bench_row.get("max_drawdown_pct"),
                "maxdd_delta_pct": compare_row.get("max_drawdown_pct") - bench_row.get("max_drawdown_pct"),
                "preferred_sharpe": compare_row.get("sharpe"),
                "benchmark_sharpe": bench_row.get("sharpe"),
                "preferred_calmar": compare_row.get("calmar"),
                "benchmark_calmar": bench_row.get("calmar"),
            }
        )
    return pd.DataFrame(rows)


def _window_table(primary_windows: pd.DataFrame, preferred_series: str) -> pd.DataFrame:
    if primary_windows.empty:
        return pd.DataFrame()
    wanted = [preferred_series, "CRYPTO_SLEEVE", "EQUITY_SLEEVE", "PASSIVE_SPY_QQQ_50_50", "QQQ_HODL", "SPY_HODL"]
    rows = primary_windows[primary_windows["series"].isin(wanted)].copy()
    if rows.empty:
        return rows
    order = {name: i for i, name in enumerate(wanted)}
    rows["_order"] = rows["series"].map(order).fillna(999)
    return rows.sort_values(["window", "_order"]).drop(columns=["_order"])


def _write_tearsheet(
    path: Path,
    primary_perf: pd.DataFrame,
    secondary_perf: pd.DataFrame,
    selected_perf: pd.DataFrame,
    benchmark: pd.DataFrame,
    window_summary: pd.DataFrame,
    args: argparse.Namespace,
) -> None:
    preferred = _one_row(primary_perf, args.preferred_series)
    secondary = _one_row(primary_perf, args.secondary_series)
    passive = _one_row(primary_perf, "PASSIVE_SPY_QQQ_50_50")
    crypto = _one_row(primary_perf, "CRYPTO_SLEEVE")
    equity = _one_row(primary_perf, "EQUITY_SLEEVE")
    crypto_beta = _one_row(secondary_perf, "BTC_ETH_50_50_DAILY_REBAL")

    lines = [
        "# Itera Dynamics — Fund Tear Sheet v1",
        "",
        "## Executive Summary",
        "",
        "Itera is currently best described as a research-backed, two-sleeve systematic fund architecture:",
        "",
        "```text",
        "1. Governed crypto sleeve",
        "2. Governed equity sleeve: SPY/QQQ SMA175 + BIL risk-off",
        "3. Static side-by-side fund reporting view, currently centered on 50/50 crypto/equity",
        "```",
        "",
        "The current promoted fund view is not a dynamic allocator. It is a reporting/product construction showing how the independent crypto and equity systems behave side by side under static capital weights.",
        "",
        "## Preferred Composite",
        "",
        f"Preferred series: `{args.preferred_series}`",
        "",
        "```text",
        f"CAGR:      {_metric(preferred, 'cagr_pct', 'pct')}",
        f"MaxDD:     {_metric(preferred, 'max_drawdown_pct', 'pct')}",
        f"Sharpe:    {_metric(preferred, 'sharpe')}",
        f"Sortino:   {_metric(preferred, 'sortino')}",
        f"Calmar:    {_metric(preferred, 'calmar')}",
        f"Ann Vol:   {_metric(preferred, 'ann_vol_pct', 'pct')}",
        f"Worst 90d: {_metric(preferred, 'worst_90d_return_pct', 'pct')}",
        f"Worst 180d:{_metric(preferred, 'worst_180d_return_pct', 'pct')}",
        "```",
        "",
        "Secondary aggressive view:",
        "",
        "```text",
        f"Series:    {args.secondary_series}",
        f"CAGR:      {_metric(secondary, 'cagr_pct', 'pct')}",
        f"MaxDD:     {_metric(secondary, 'max_drawdown_pct', 'pct')}",
        f"Sharpe:    {_metric(secondary, 'sharpe')}",
        f"Calmar:    {_metric(secondary, 'calmar')}",
        "```",
        "",
        "## Architecture Status",
        "",
        "```text",
        "Promoted:",
        "  - Crypto sleeve as independent systematic crypto engine candidate",
        "  - Equity Core SMA175 + BIL as governed equity sleeve",
        "  - Static 50/50 side-by-side composite as fund reporting/product view",
        "",
        "Not promoted:",
        "  - Dynamic crypto/equity allocator",
        "  - Sector rotation sleeve",
        "  - Breadth/dispersion equity-alpha overlays",
        "```",
        "",
        "## Performance Table",
        "",
        _md_table(_select_display_columns(selected_perf), max_rows=30),
        "",
        "## Benchmark Comparison",
        "",
        _md_table(benchmark, max_rows=40),
        "",
        "## Benchmark Interpretation",
        "",
        "Versus passive SPY/QQQ 50/50, the preferred Itera composite slightly trails raw CAGR but materially improves drawdown, volatility, Sharpe, and Calmar:",
        "",
        "```text",
        f"Itera 50/50 CAGR:       {_metric(preferred, 'cagr_pct', 'pct')}",
        f"SPY/QQQ 50/50 CAGR:     {_metric(passive, 'cagr_pct', 'pct')}",
        "",
        f"Itera 50/50 MaxDD:      {_metric(preferred, 'max_drawdown_pct', 'pct')}",
        f"SPY/QQQ 50/50 MaxDD:    {_metric(passive, 'max_drawdown_pct', 'pct')}",
        "",
        f"Itera 50/50 Sharpe:     {_metric(preferred, 'sharpe')}",
        f"SPY/QQQ 50/50 Sharpe:   {_metric(passive, 'sharpe')}",
        "",
        f"Itera 50/50 Calmar:     {_metric(preferred, 'calmar')}",
        f"SPY/QQQ 50/50 Calmar:   {_metric(passive, 'calmar')}",
        "```",
        "",
        "Versus passive crypto beta, the composite does not match raw BTC/ETH bull-cycle returns. Its value proposition is a smoother, lower-drawdown, better risk-adjusted return stream:",
        "",
        "```text",
        f"Itera 50/50 CAGR:       {_metric(_one_row(secondary_perf, args.preferred_series), 'cagr_pct', 'pct')}",
        f"BTC/ETH 50/50 CAGR:     {_metric(crypto_beta, 'cagr_pct', 'pct')}",
        "",
        f"Itera 50/50 MaxDD:      {_metric(_one_row(secondary_perf, args.preferred_series), 'max_drawdown_pct', 'pct')}",
        f"BTC/ETH 50/50 MaxDD:    {_metric(crypto_beta, 'max_drawdown_pct', 'pct')}",
        "",
        f"Itera 50/50 Sharpe:     {_metric(_one_row(secondary_perf, args.preferred_series), 'sharpe')}",
        f"BTC/ETH 50/50 Sharpe:   {_metric(crypto_beta, 'sharpe')}",
        "",
        f"Itera 50/50 Calmar:     {_metric(_one_row(secondary_perf, args.preferred_series), 'calmar')}",
        f"BTC/ETH 50/50 Calmar:   {_metric(crypto_beta, 'calmar')}",
        "```",
        "",
        "## Window / Stress Period Review",
        "",
        _md_table(_select_display_columns(window_summary), max_rows=80),
        "",
        "## What This Beats",
        "",
        "```text",
        "- Standalone crypto sleeve on Sharpe / Calmar / drawdown profile",
        "- Standalone equity sleeve on CAGR / Sharpe / Calmar / drawdown profile",
        "- Passive SPY/QQQ on drawdown, volatility, Sharpe, and Calmar",
        "- Passive BTC/ETH baskets on drawdown-adjusted quality, not raw CAGR",
        "```",
        "",
        "## What This Does Not Beat",
        "",
        "```text",
        "- Passive BTC/ETH raw CAGR during the 2019–2025 crypto bull-cycle window",
        "- QQQ HODL raw CAGR during the same equity growth window",
        "- Passive SPY/QQQ 50/50 raw CAGR by a small margin in the tested window",
        "```",
        "",
        "## Caveats",
        "",
        "```text",
        "- Research-only; not live fund performance",
        "- No legal fund vehicle or investor offering is implied",
        "- No live allocation approval is implied",
        "- Results depend on the validity of source equity curves and local market data",
        "- Fees, taxes, slippage, custody, financing, capacity, and operational constraints may not be fully modeled",
        "- The combined fund window begins in 2019 because the crypto sleeve begins in 2019",
        "```",
        "",
        "## Non-Approved Items",
        "",
        "```text",
        "No paper trading approval",
        "No live trading approval",
        "No broker integration approval",
        "No runtime integration approval",
        "No dynamic crypto/equity allocator",
        "No promoted equity alpha overlay",
        "No promoted sector rotation sleeve",
        "```",
        "",
        "## Bottom Line",
        "",
        "The current Itera fund setup is a disciplined two-sleeve systematic architecture: governed crypto plus governed equities, viewed through a static 50/50 fund composite. The strongest current story is not raw-return dominance; it is a cleaner drawdown-adjusted return stream than passive equity benchmarks and passive crypto beta.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    primary_dir = Path(args.primary_dir)
    secondary_dir = Path(args.secondary_dir)
    primary_perf = _read_csv_required(primary_dir / "performance_summary.csv")
    secondary_perf = _read_csv_required(secondary_dir / "performance_summary.csv")
    primary_windows = _read_csv_optional(primary_dir / "window_performance_summary.csv")

    selected_names = [
        args.preferred_series,
        args.secondary_series,
        "CRYPTO_SLEEVE",
        "EQUITY_SLEEVE",
        "PASSIVE_SPY_QQQ_50_50",
        "QQQ_HODL",
        "SPY_HODL",
    ]
    selected_primary = _series_rows(primary_perf, selected_names, "primary_tilted_4s")
    selected_secondary = _series_rows(
        secondary_perf,
        [args.preferred_series, "BTC_ETH_50_50_DAILY_REBAL", "BTC_ETH_60_40_DAILY_REBAL", "BTC_HODL", "ETH_HODL"],
        "secondary_fund_v1_crypto_benchmarks",
    )
    selected_perf = pd.concat([selected_primary, selected_secondary], ignore_index=True)
    benchmark = _benchmark_table(primary_perf, secondary_perf, args.preferred_series)
    window_summary = _window_table(primary_windows, args.preferred_series)

    selected_perf.to_csv(out_dir / "selected_performance_table.csv", index=False)
    benchmark.to_csv(out_dir / "benchmark_comparison_table.csv", index=False)
    window_summary.to_csv(out_dir / "window_summary_table.csv", index=False)

    summary = {
        "research_status": "reporting_only_fund_tearsheet_v1",
        "inputs": {
            "primary_dir": args.primary_dir,
            "secondary_dir": args.secondary_dir,
            "preferred_series": args.preferred_series,
            "secondary_series": args.secondary_series,
        },
        "artifacts": {
            "fund_tearsheet_md": str(out_dir / "fund_tearsheet.md"),
            "fund_tearsheet_summary_json": str(out_dir / "fund_tearsheet_summary.json"),
            "selected_performance_table": str(out_dir / "selected_performance_table.csv"),
            "benchmark_comparison_table": str(out_dir / "benchmark_comparison_table.csv"),
            "window_summary_table": str(out_dir / "window_summary_table.csv"),
        },
        "decision": {
            "status": "reporting_only",
            "not_approved": ["paper_trading", "live_allocation", "broker_change", "runtime_change", "dashboard_change", "dynamic_allocator"],
        },
    }
    (out_dir / "fund_tearsheet_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    _write_tearsheet(out_dir / "fund_tearsheet.md", primary_perf, secondary_perf, selected_perf, benchmark, window_summary, args)

    with pd.option_context("display.max_columns", None, "display.width", 360, "display.float_format", "{:.4f}".format):
        print("\n=== FUND TEAR SHEET V1 ===")
        print(f"Primary dir: {args.primary_dir}")
        print(f"Secondary dir: {args.secondary_dir}")
        print(f"Preferred series: {args.preferred_series}")
        print("\nSelected Performance:")
        print(_select_display_columns(selected_perf).to_string(index=False))
        print("\nBenchmark Comparison:")
        print(benchmark.to_string(index=False) if not benchmark.empty else "No benchmark rows.")
    print(f"\nArtifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()
