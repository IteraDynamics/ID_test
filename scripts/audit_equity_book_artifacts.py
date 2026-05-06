#!/usr/bin/env python
"""Equity Book v1 — artifact audit and benchmark normalizer.

Research-only script. Audits candidate equity-curve CSVs, normalizes them to a
common overlap, computes comparable performance metrics, and benchmarks them
against SPY/QQQ buy-and-hold and SPY/QQQ 50/50 daily rebalanced exposure.

No runtime, broker, paper-trading, allocator, or live changes are made.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


DEFAULT_OUT = "artifacts/equity_book_v1_audit"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Audit Equity Book v1 artifacts against SPY/QQQ benchmarks",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--candidate",
        action="append",
        default=[],
        help=(
            "Candidate equity curve spec as name:path[:column]. "
            "Repeat for multiple candidates. Example: spy_strategy:artifacts/spy/equity_curves.csv:portfolio"
        ),
    )
    p.add_argument("--spy-data", default="data/SPY_1D.csv")
    p.add_argument("--qqq-data", default="data/QQQ_1D.csv")
    p.add_argument("--out-dir", default=DEFAULT_OUT)
    p.add_argument("--target-return", type=float, default=0.0, help="Per-bar target return for Sortino")
    return p.parse_args()


def _read_time_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"Empty CSV: {path}")
    time_col = _detect_time_col(df)
    df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
    df = df.dropna(subset=[time_col]).set_index(time_col).sort_index()
    df.index = df.index.tz_localize(None) if getattr(df.index, "tz", None) is not None else df.index
    if df.empty:
        raise ValueError(f"No valid timestamp rows in {path}")
    return df


def _detect_time_col(df: pd.DataFrame) -> str:
    preferred = ["timestamp", "time", "date", "datetime", "Unnamed: 0"]
    lower = {str(c).lower(): c for c in df.columns}
    for name in preferred:
        if name.lower() in lower:
            return lower[name.lower()]
    return str(df.columns[0])


def _select_numeric_col(df: pd.DataFrame, preferred: Iterable[str], label: str) -> pd.Series:
    for col in preferred:
        if col and col in df.columns:
            s = pd.to_numeric(df[col], errors="coerce").dropna()
            if len(s) > 1:
                s.name = label
                return s.astype(float)
    numeric = []
    for col in df.columns:
        s = pd.to_numeric(df[col], errors="coerce")
        if s.notna().sum() > 1:
            numeric.append(col)
    if not numeric:
        raise ValueError(f"No numeric columns found for {label}; columns={list(df.columns)}")
    # Prefer common equity curve column names if available.
    for col in ["portfolio", "equity", "strategy_equity", "close", "Close"]:
        if col in numeric:
            s = pd.to_numeric(df[col], errors="coerce").dropna().astype(float)
            s.name = label
            return s
    s = pd.to_numeric(df[numeric[0]], errors="coerce").dropna().astype(float)
    s.name = label
    return s


def _parse_candidate(spec: str) -> tuple[str, Path, str | None]:
    parts = spec.split(":")
    if len(parts) < 2:
        raise ValueError(f"Invalid candidate spec '{spec}'. Expected name:path[:column]")
    name = parts[0].strip()
    path = Path(parts[1].strip())
    col = parts[2].strip() if len(parts) >= 3 and parts[2].strip() else None
    if not name:
        raise ValueError(f"Candidate name missing in spec: {spec}")
    return name, path, col


def _normalise(s: pd.Series, name: str) -> pd.Series:
    s = s.dropna().astype(float)
    if s.empty:
        raise ValueError(f"Cannot normalize empty series: {name}")
    if float(s.iloc[0]) <= 0:
        raise ValueError(f"Cannot normalize non-positive-start series: {name}")
    out = s / float(s.iloc[0])
    out.name = name
    return out


def _to_daily(s: pd.Series) -> pd.Series:
    return s.sort_index().resample("1D").last().dropna()


def _bars_per_year(index: pd.DatetimeIndex) -> float:
    if len(index) < 3:
        return 252.0
    deltas = index.to_series().diff().dropna().dt.total_seconds()
    if deltas.empty:
        return 252.0
    med = float(deltas.median())
    if med <= 0:
        return 252.0
    # Equities are daily by default, but this also handles hourly if needed.
    if med >= 20 * 3600:
        return 252.0
    return float(365.25 * 24 * 3600 / med)


def _max_time_underwater_days(eq: pd.Series) -> float:
    eq = eq.dropna().astype(float)
    if eq.empty:
        return 0.0
    dd = eq / eq.cummax() - 1.0
    start = None
    max_days = 0.0
    for ts, flag in (dd < 0).items():
        if flag and start is None:
            start = ts
        elif not flag and start is not None:
            max_days = max(max_days, (ts - start).total_seconds() / 86400.0)
            start = None
    if start is not None:
        max_days = max(max_days, (eq.index[-1] - start).total_seconds() / 86400.0)
    return float(max_days)


def _sortino(eq: pd.Series, target_return: float = 0.0) -> float:
    eq = eq.dropna().astype(float)
    rets = eq.pct_change().dropna()
    if rets.empty:
        return 0.0
    excess = rets - float(target_return)
    downside = np.minimum(excess, 0.0)
    downside_dev = float(np.sqrt(np.mean(np.square(downside))))
    if downside_dev <= 1e-12:
        return 0.0
    return float((excess.mean() / downside_dev) * math.sqrt(_bars_per_year(eq.index)))


def _perf(eq: pd.Series, target_return: float = 0.0) -> dict[str, float]:
    eq = eq.dropna().astype(float)
    if len(eq) < 2:
        return {}
    rets = eq.pct_change().dropna()
    years = max((eq.index[-1] - eq.index[0]).total_seconds() / (365.25 * 24 * 3600), 1e-9)
    total = float(eq.iloc[-1] / eq.iloc[0] - 1.0)
    cagr = float((eq.iloc[-1] / eq.iloc[0]) ** (1.0 / years) - 1.0)
    dd = eq / eq.cummax() - 1.0
    max_dd = float(dd.min())
    std = float(rets.std(ddof=0)) if len(rets) else 0.0
    bpy = _bars_per_year(eq.index)
    sharpe = float((rets.mean() / std) * math.sqrt(bpy)) if std > 1e-12 else 0.0
    ann_vol = float(std * math.sqrt(bpy)) if std > 0 else 0.0
    calmar = float(cagr / abs(max_dd)) if max_dd < 0 else 0.0
    daily = _to_daily(eq)
    worst_90 = float(daily.pct_change(90).dropna().min()) if len(daily) > 90 else 0.0
    worst_180 = float(daily.pct_change(180).dropna().min()) if len(daily) > 180 else 0.0
    return {
        "total_return_pct": total * 100.0,
        "cagr_pct": cagr * 100.0,
        "max_drawdown_pct": max_dd * 100.0,
        "sharpe": sharpe,
        "sortino": _sortino(eq, target_return),
        "calmar": calmar,
        "ann_vol_pct": ann_vol * 100.0,
        "worst_90d_return_pct": worst_90 * 100.0,
        "worst_180d_return_pct": worst_180 * 100.0,
        "time_underwater_pct": float((dd < 0).mean() * 100.0),
        "max_time_underwater_days": _max_time_underwater_days(eq),
    }


def _build_benchmarks(spy_close: pd.Series, qqq_close: pd.Series) -> pd.DataFrame:
    spy = _normalise(_to_daily(spy_close), "SPY_HODL")
    qqq = _normalise(_to_daily(qqq_close), "QQQ_HODL")
    common = spy.index.intersection(qqq.index)
    spy = spy.loc[common]
    qqq = qqq.loc[common]
    spy_ret = spy.pct_change().fillna(0.0)
    qqq_ret = qqq.pct_change().fillna(0.0)
    blend = (1.0 + (0.50 * spy_ret + 0.50 * qqq_ret)).cumprod()
    blend.name = "SPY_QQQ_50_50_DAILY_REBAL"
    return pd.DataFrame({"SPY_HODL": spy, "QQQ_HODL": qqq, "SPY_QQQ_50_50_DAILY_REBAL": blend})


def _capture(strategy: pd.Series, benchmark: pd.Series) -> dict[str, float]:
    s = _normalise(strategy, strategy.name or "strategy")
    b = _normalise(benchmark, benchmark.name or "benchmark")
    common = s.index.intersection(b.index)
    s = s.loc[common]
    b = b.loc[common]
    sr = s.pct_change().dropna()
    br = b.pct_change().dropna()
    joined = pd.concat([sr.rename("s"), br.rename("b")], axis=1).dropna()
    if joined.empty:
        return {"return_capture_ratio": 0.0, "up_day_capture_ratio": 0.0, "down_day_capture_ratio": 0.0, "vol_ratio": 0.0}
    s_total = float(s.loc[joined.index[-1]] / s.loc[joined.index[0]] - 1.0)
    b_total = float(b.loc[joined.index[-1]] / b.loc[joined.index[0]] - 1.0)
    up = joined["b"] > 0
    down = joined["b"] < 0
    up_denom = float(joined.loc[up, "b"].sum())
    down_denom = float(joined.loc[down, "b"].sum())
    return {
        "return_capture_ratio": float(s_total / b_total) if abs(b_total) > 1e-12 else 0.0,
        "up_day_capture_ratio": float(joined.loc[up, "s"].sum() / up_denom) if abs(up_denom) > 1e-12 else 0.0,
        "down_day_capture_ratio": float(joined.loc[down, "s"].sum() / down_denom) if abs(down_denom) > 1e-12 else 0.0,
        "vol_ratio": float(joined["s"].std(ddof=0) / joined["b"].std(ddof=0)) if joined["b"].std(ddof=0) > 0 else 0.0,
    }


def _capture_table(candidates: pd.DataFrame, benchmarks: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for series in candidates.columns:
        for benchmark in benchmarks.columns:
            rows.append({"series": series, "benchmark": benchmark, **_capture(candidates[series], benchmarks[benchmark])})
    return pd.DataFrame(rows)


def _yearly(curves: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name, curve in curves.items():
        s = curve.dropna().astype(float)
        yr = s.resample("YE").last().pct_change().dropna()
        for ts, ret in yr.items():
            rows.append({"series": name, "year": int(ts.year), "return_pct": float(ret * 100.0)})
    return pd.DataFrame(rows)


def _fmt(v: object, floatfmt: str = ".4f") -> str:
    if isinstance(v, float):
        return format(v, floatfmt)
    if pd.isna(v):
        return ""
    return str(v).replace("|", "\\|").replace("\n", " ")


def _md_table(df: pd.DataFrame, cols: list[str] | None = None) -> str:
    if df.empty:
        return "_No rows._"
    if cols is not None:
        df = df[[c for c in cols if c in df.columns]]
    columns = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(columns) + " |"]
    lines.append("| " + " | ".join(["---"] * len(columns)) + " |")
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(_fmt(row[c]) for c in df.columns) + " |")
    return "\n".join(lines)


def _write_summary(path: Path, perf: pd.DataFrame, capture: pd.DataFrame, yearly: pd.DataFrame, args: argparse.Namespace) -> None:
    perf_cols = ["series", "total_return_pct", "cagr_pct", "max_drawdown_pct", "sharpe", "sortino", "calmar", "ann_vol_pct", "worst_90d_return_pct", "worst_180d_return_pct", "max_time_underwater_days"]
    capture_cols = ["series", "benchmark", "return_capture_ratio", "up_day_capture_ratio", "down_day_capture_ratio", "vol_ratio"]
    lines = [
        "# Equity Book v1 — Artifact Audit",
        "",
        "Research-only artifact audit. No runtime or paper-trading changes approved.",
        "",
        "## Inputs",
        "",
        "```text",
        f"SPY data: {args.spy_data}",
        f"QQQ data: {args.qqq_data}",
        f"Candidates: {len(args.candidate)}",
        "```",
        "",
        "## Performance Summary",
        "",
        _md_table(perf, perf_cols),
        "",
        "## Benchmark Capture Summary",
        "",
        _md_table(capture, capture_cols),
        "",
        "## Yearly Returns",
        "",
        _md_table(yearly.pivot_table(index="year", columns="series", values="return_pct").reset_index()),
        "",
        "## Guardrail",
        "",
        "```text",
        "This audit only normalizes and compares existing candidate curves and passive benchmarks.",
        "It does not approve any equity strategy for paper trading or live allocation.",
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    spy_df = _read_time_csv(Path(args.spy_data))
    qqq_df = _read_time_csv(Path(args.qqq_data))
    spy_close = _select_numeric_col(spy_df, ["close", "Close", "adj_close", "Adj Close"], "SPY_close")
    qqq_close = _select_numeric_col(qqq_df, ["close", "Close", "adj_close", "Adj Close"], "QQQ_close")
    benchmarks = _build_benchmarks(spy_close, qqq_close)

    candidate_curves: dict[str, pd.Series] = {}
    for spec in args.candidate:
        name, path, col = _parse_candidate(spec)
        df = _read_time_csv(path)
        s = _select_numeric_col(df, [col, "portfolio", "equity", "strategy_equity", "SPY", "QQQ"], name)
        candidate_curves[name] = s

    if not candidate_curves:
        print("No candidates supplied; benchmarking passive SPY/QQQ only.")

    candidates = pd.DataFrame(candidate_curves) if candidate_curves else pd.DataFrame(index=benchmarks.index)

    # Common overlap across candidates and benchmarks.
    common = benchmarks.dropna().index
    for col in candidates.columns:
        common = common.intersection(candidates[col].dropna().index)
    if len(common) < 252:
        raise SystemExit(f"Insufficient common overlap for equity audit: {len(common)} bars")

    bench_common = pd.DataFrame({col: _normalise(benchmarks[col].loc[common], col) for col in benchmarks.columns})
    cand_common = pd.DataFrame({col: _normalise(candidates[col].loc[common], col) for col in candidates.columns}) if len(candidates.columns) else pd.DataFrame(index=common)
    all_curves = pd.concat([cand_common, bench_common], axis=1).dropna()

    perf = pd.DataFrame([{"series": col, **_perf(all_curves[col], args.target_return)} for col in all_curves.columns])
    perf = perf.sort_values(["calmar", "cagr_pct"], ascending=[False, False])
    capture = _capture_table(cand_common, bench_common) if len(cand_common.columns) else pd.DataFrame()
    yearly = _yearly(all_curves)

    all_curves.to_csv(out_dir / "normalized_equity_curves.csv")
    perf.to_csv(out_dir / "performance_summary.csv", index=False)
    capture.to_csv(out_dir / "benchmark_capture_summary.csv", index=False)
    yearly.to_csv(out_dir / "yearly_returns.csv", index=False)

    payload = {
        "research_status": "research_only_equity_book_v1_artifact_audit",
        "inputs": {
            "candidates": args.candidate,
            "spy_data": args.spy_data,
            "qqq_data": args.qqq_data,
            "target_return": args.target_return,
        },
        "common_overlap": {"start": str(all_curves.index[0]), "end": str(all_curves.index[-1]), "bars": int(len(all_curves))},
        "artifacts": {
            "normalized_equity_curves": str(out_dir / "normalized_equity_curves.csv"),
            "performance_summary": str(out_dir / "performance_summary.csv"),
            "benchmark_capture_summary": str(out_dir / "benchmark_capture_summary.csv"),
            "yearly_returns": str(out_dir / "yearly_returns.csv"),
            "summary_json": str(out_dir / "summary.json"),
            "summary_md": str(out_dir / "summary.md"),
        },
        "decision": {"status": "diagnostic_only", "not_approved": ["runtime_change", "paper_trading_change", "live_allocation_change", "broker_change"]},
    }
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    _write_summary(out_dir / "summary.md", perf, capture, yearly, args)

    perf_cols = ["series", "total_return_pct", "cagr_pct", "max_drawdown_pct", "sharpe", "sortino", "calmar", "ann_vol_pct", "worst_90d_return_pct", "worst_180d_return_pct", "max_time_underwater_days"]
    capture_cols = ["series", "benchmark", "return_capture_ratio", "up_day_capture_ratio", "down_day_capture_ratio", "vol_ratio"]
    with pd.option_context("display.max_columns", None, "display.width", 280, "display.float_format", "{:.4f}".format):
        print("\n=== EQUITY BOOK V1 — ARTIFACT AUDIT ===")
        print(f"Common overlap: {payload['common_overlap']['start']} → {payload['common_overlap']['end']} ({payload['common_overlap']['bars']} bars)")
        print("\nPerformance Summary:")
        print(perf[[c for c in perf_cols if c in perf.columns]].to_string(index=False))
        print("\nBenchmark Capture Summary:")
        if capture.empty:
            print("No candidate curves supplied; capture table skipped.")
        else:
            print(capture[[c for c in capture_cols if c in capture.columns]].to_string(index=False))
    print(f"\nArtifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()
