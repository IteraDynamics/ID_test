#!/usr/bin/env python
"""Equity Book v1 — robustness audit for shortlisted baseline candidates.

Research-only script. Reads an existing Equity Book v1 baseline equity-curve
artifact and evaluates selected SPY/QQQ candidates across named market windows.

This script does not re-run strategy logic, tune parameters, add overlays,
modify crypto/fund code, or approve paper/live trading. It only audits already
produced equity curves.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


DEFAULT_CURVES = "artifacts/equity_book_v1_baselines_wide/equity_curves.csv"
DEFAULT_OUT = "artifacts/equity_book_v1_robustness"
DEFAULT_SERIES = [
    "SPY_QQQ_50_50_SMA150_CASH",
    "SPY_QQQ_50_50_SMA200_CASH",
    "QQQ_SMA150_CASH",
    "SPY_QQQ_50_50_DAILY_REBAL",
    "QQQ_HODL",
    "SPY_HODL",
]
DEFAULT_BENCHMARKS = ["SPY_QQQ_50_50_DAILY_REBAL", "QQQ_HODL", "SPY_HODL"]
DEFAULT_WINDOWS = [
    "FULL:1900-01-01:2100-01-01",
    "GFC_2007_2009:2007-10-01:2009-03-31",
    "COVID_2020:2020-02-01:2020-06-30",
    "BEAR_2022:2022-01-01:2022-12-31",
    "POST_2022_RECOVERY:2023-01-01:2024-12-31",
    "RECENT_2025_PLUS:2025-01-01:2100-01-01",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Audit Equity Book v1 shortlisted candidates across named robustness windows",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--equity-curves", default=DEFAULT_CURVES)
    p.add_argument("--out-dir", default=DEFAULT_OUT)
    p.add_argument(
        "--series",
        action="append",
        default=[],
        help="Series to audit. Repeat for multiple. Defaults to the Equity Book v1 shortlist plus benchmarks.",
    )
    p.add_argument(
        "--benchmark",
        action="append",
        default=[],
        help="Benchmark series for capture/delta comparisons. Repeat for multiple.",
    )
    p.add_argument(
        "--window",
        action="append",
        default=[],
        help="Window as NAME:YYYY-MM-DD:YYYY-MM-DD. End is inclusive after date normalization.",
    )
    p.add_argument("--target-return", type=float, default=0.0, help="Per-bar target return for Sortino.")
    return p.parse_args()


def _detect_time_col(df: pd.DataFrame) -> str:
    lower = {str(c).lower(): c for c in df.columns}
    for name in ["timestamp", "date", "datetime", "time", "unnamed: 0"]:
        if name in lower:
            return str(lower[name])
    return str(df.columns[0])


def _read_curves(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing equity curves file: {path}")
    df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"Empty equity curves file: {path}")
    time_col = _detect_time_col(df)
    df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
    df = df.dropna(subset=[time_col]).set_index(time_col).sort_index()
    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_localize(None)
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(axis=1, how="all")
    if df.empty:
        raise ValueError(f"No numeric equity curves found in {path}")
    return df


def _parse_windows(raw_windows: Iterable[str]) -> list[dict[str, object]]:
    windows = []
    for raw in raw_windows:
        parts = str(raw).split(":")
        if len(parts) != 3:
            raise ValueError(f"Invalid --window '{raw}'. Expected NAME:YYYY-MM-DD:YYYY-MM-DD")
        name, start, end = [p.strip() for p in parts]
        if not name:
            raise ValueError(f"Window name missing in '{raw}'")
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        if end_ts < start_ts:
            raise ValueError(f"Window end before start in '{raw}'")
        windows.append({"window": name, "start": start_ts, "end": end_ts})
    return windows


def _bars_per_year(index: pd.DatetimeIndex) -> float:
    if len(index) < 3:
        return 252.0
    deltas = index.to_series().diff().dropna().dt.total_seconds()
    if deltas.empty:
        return 252.0
    med = float(deltas.median())
    if med <= 0:
        return 252.0
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
    rets = eq.dropna().astype(float).pct_change().dropna()
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
    return {
        "total_return_pct": total * 100.0,
        "cagr_pct": cagr * 100.0,
        "max_drawdown_pct": max_dd * 100.0,
        "sharpe": sharpe,
        "sortino": _sortino(eq, target_return),
        "calmar": calmar,
        "ann_vol_pct": ann_vol * 100.0,
        "time_underwater_pct": float((dd < 0).mean() * 100.0),
        "max_time_underwater_days": _max_time_underwater_days(eq),
    }


def _normalise_window(curves: pd.DataFrame) -> pd.DataFrame:
    out = curves.dropna(how="all").copy()
    for col in out.columns:
        s = out[col].dropna().astype(float)
        if len(s) < 2 or float(s.iloc[0]) <= 0:
            out[col] = np.nan
        else:
            out[col] = out[col] / float(s.iloc[0])
    return out.dropna(axis=1, how="all")


def _capture(strategy: pd.Series, benchmark: pd.Series) -> dict[str, float]:
    s = strategy.dropna().astype(float)
    b = benchmark.dropna().astype(float)
    common = s.index.intersection(b.index)
    s = s.loc[common]
    b = b.loc[common]
    if len(common) < 2:
        return {"return_capture_ratio": 0.0, "up_day_capture_ratio": 0.0, "down_day_capture_ratio": 0.0, "vol_ratio": 0.0}
    sr = s.pct_change().dropna()
    br = b.pct_change().dropna()
    joined = pd.concat([sr.rename("s"), br.rename("b")], axis=1).dropna()
    if joined.empty:
        return {"return_capture_ratio": 0.0, "up_day_capture_ratio": 0.0, "down_day_capture_ratio": 0.0, "vol_ratio": 0.0}
    s_total = float(s.loc[joined.index[-1]] / s.loc[joined.index[0]] - 1.0)
    b_total = float(b.loc[joined.index[-1]] / b.loc[joined.index[0]] - 1.0)
    up = joined["b"] > 0.0
    down = joined["b"] < 0.0
    up_denom = float(joined.loc[up, "b"].sum())
    down_denom = float(joined.loc[down, "b"].sum())
    return {
        "return_capture_ratio": float(s_total / b_total) if abs(b_total) > 1e-12 else 0.0,
        "up_day_capture_ratio": float(joined.loc[up, "s"].sum() / up_denom) if abs(up_denom) > 1e-12 else 0.0,
        "down_day_capture_ratio": float(joined.loc[down, "s"].sum() / down_denom) if abs(down_denom) > 1e-12 else 0.0,
        "vol_ratio": float(joined["s"].std(ddof=0) / joined["b"].std(ddof=0)) if joined["b"].std(ddof=0) > 0 else 0.0,
    }


def _window_slice(curves: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    # Treat date-like end as inclusive through the full calendar day.
    inclusive_end = end + pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1)
    return curves.loc[(curves.index >= start) & (curves.index <= inclusive_end)].dropna(how="all")


def _build_window_outputs(
    curves: pd.DataFrame,
    windows: list[dict[str, object]],
    series: list[str],
    benchmarks: list[str],
    target_return: float,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    perf_rows = []
    capture_rows = []
    curve_frames = []

    missing = [s for s in series if s not in curves.columns]
    if missing:
        raise ValueError(f"Requested series missing from curves: {missing}")
    missing_bench = [s for s in benchmarks if s not in curves.columns]
    if missing_bench:
        raise ValueError(f"Requested benchmarks missing from curves: {missing_bench}")

    selected = list(dict.fromkeys(series + benchmarks))
    for window in windows:
        name = str(window["window"])
        start = pd.Timestamp(window["start"])
        end = pd.Timestamp(window["end"])
        raw = _window_slice(curves[selected], start, end)
        norm = _normalise_window(raw)
        if len(norm) < 20:
            perf_rows.append({"window": name, "series": "__WINDOW_SKIPPED__", "bars": int(len(norm)), "reason": "insufficient_rows"})
            continue

        long = norm.reset_index().melt(id_vars=norm.index.name or "timestamp", var_name="series", value_name="normalized_equity")
        long.insert(0, "window", name)
        curve_frames.append(long)

        for col in norm.columns:
            metrics = _perf(norm[col], target_return)
            perf_rows.append(
                {
                    "window": name,
                    "series": col,
                    "start": str(norm[col].dropna().index[0]),
                    "end": str(norm[col].dropna().index[-1]),
                    "bars": int(norm[col].dropna().shape[0]),
                    **metrics,
                }
            )

        for candidate in series:
            if candidate in benchmarks or candidate not in norm.columns:
                continue
            for benchmark in benchmarks:
                if benchmark not in norm.columns:
                    continue
                cap = _capture(norm[candidate], norm[benchmark])
                cand_perf = _perf(norm[candidate], target_return)
                bench_perf = _perf(norm[benchmark], target_return)
                capture_rows.append(
                    {
                        "window": name,
                        "series": candidate,
                        "benchmark": benchmark,
                        **cap,
                        "delta_total_return_pct": cand_perf.get("total_return_pct", 0.0) - bench_perf.get("total_return_pct", 0.0),
                        "delta_cagr_pct": cand_perf.get("cagr_pct", 0.0) - bench_perf.get("cagr_pct", 0.0),
                        "delta_max_drawdown_pct": cand_perf.get("max_drawdown_pct", 0.0) - bench_perf.get("max_drawdown_pct", 0.0),
                        "delta_sharpe": cand_perf.get("sharpe", 0.0) - bench_perf.get("sharpe", 0.0),
                        "delta_calmar": cand_perf.get("calmar", 0.0) - bench_perf.get("calmar", 0.0),
                    }
                )

    perf = pd.DataFrame(perf_rows)
    capture = pd.DataFrame(capture_rows)
    long_curves = pd.concat(curve_frames, ignore_index=True) if curve_frames else pd.DataFrame()
    return perf, capture, long_curves


def _fmt(v: object, floatfmt: str = ".4f") -> str:
    if isinstance(v, float):
        return format(v, floatfmt)
    if pd.isna(v):
        return ""
    return str(v).replace("|", "\\|").replace("\n", " ")


def _md_table(df: pd.DataFrame, cols: list[str] | None = None, max_rows: int | None = None) -> str:
    if df.empty:
        return "_No rows._"
    if cols is not None:
        df = df[[c for c in cols if c in df.columns]]
    if max_rows is not None:
        df = df.head(max_rows)
    columns = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(_fmt(row[c]) for c in df.columns) + " |")
    return "\n".join(lines)


def _write_summary_md(path: Path, perf: pd.DataFrame, capture: pd.DataFrame, args: argparse.Namespace, series: list[str], benchmarks: list[str]) -> None:
    perf_cols = ["window", "series", "total_return_pct", "cagr_pct", "max_drawdown_pct", "sharpe", "sortino", "calmar", "ann_vol_pct", "bars"]
    capture_cols = ["window", "series", "benchmark", "return_capture_ratio", "up_day_capture_ratio", "down_day_capture_ratio", "vol_ratio", "delta_cagr_pct", "delta_max_drawdown_pct", "delta_sharpe", "delta_calmar"]
    candidate_perf = perf[(perf["series"].isin(series)) & (~perf["series"].isin(benchmarks))].copy() if not perf.empty else pd.DataFrame()
    lines = [
        "# Equity Book v1 — Robustness Audit",
        "",
        "Research-only robustness audit for shortlisted SPY/QQQ baseline candidates.",
        "",
        "## Inputs",
        "",
        "```text",
        f"Equity curves: {args.equity_curves}",
        f"Series: {', '.join(series)}",
        f"Benchmarks: {', '.join(benchmarks)}",
        "```",
        "",
        "## Candidate Window Metrics",
        "",
        _md_table(candidate_perf, perf_cols, max_rows=80),
        "",
        "## Capture / Delta Summary",
        "",
        _md_table(capture, capture_cols, max_rows=120),
        "",
        "## Guardrail",
        "",
        "```text",
        "This audit reads existing baseline equity curves only.",
        "It does not approve paper trading, live allocation, broker changes, crypto allocator changes, or defensive carry overlays.",
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    series = args.series or DEFAULT_SERIES
    benchmarks = args.benchmark or DEFAULT_BENCHMARKS
    windows = _parse_windows(args.window or DEFAULT_WINDOWS)

    curves = _read_curves(Path(args.equity_curves))
    perf, capture, long_curves = _build_window_outputs(curves, windows, series, benchmarks, args.target_return)

    perf_sorted = perf.copy()
    if "window" in perf_sorted.columns and "calmar" in perf_sorted.columns:
        perf_sorted = perf_sorted.sort_values(["window", "calmar", "sharpe", "cagr_pct"], ascending=[True, False, False, False])

    perf_sorted.to_csv(out_dir / "window_performance_summary.csv", index=False)
    capture.to_csv(out_dir / "window_capture_summary.csv", index=False)
    long_curves.to_csv(out_dir / "normalized_window_equity_curves.csv", index=False)

    payload = {
        "research_status": "research_only_equity_book_v1_robustness_audit",
        "inputs": {
            "equity_curves": args.equity_curves,
            "series": series,
            "benchmarks": benchmarks,
            "windows": [{"window": w["window"], "start": str(w["start"]), "end": str(w["end"])} for w in windows],
            "target_return": args.target_return,
        },
        "artifacts": {
            "window_performance_summary": str(out_dir / "window_performance_summary.csv"),
            "window_capture_summary": str(out_dir / "window_capture_summary.csv"),
            "normalized_window_equity_curves": str(out_dir / "normalized_window_equity_curves.csv"),
            "summary_json": str(out_dir / "summary.json"),
            "summary_md": str(out_dir / "summary.md"),
        },
        "decision": {
            "status": "diagnostic_only",
            "not_approved": [
                "runtime_change",
                "paper_trading_change",
                "live_allocation_change",
                "broker_change",
                "crypto_allocator_change",
                "defensive_carry_overlay",
            ],
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    _write_summary_md(out_dir / "summary.md", perf_sorted, capture, args, series, benchmarks)

    perf_cols = ["window", "series", "total_return_pct", "cagr_pct", "max_drawdown_pct", "sharpe", "sortino", "calmar", "ann_vol_pct", "bars"]
    capture_cols = ["window", "series", "benchmark", "return_capture_ratio", "up_day_capture_ratio", "down_day_capture_ratio", "vol_ratio", "delta_cagr_pct", "delta_max_drawdown_pct", "delta_sharpe", "delta_calmar"]
    with pd.option_context("display.max_columns", None, "display.width", 320, "display.float_format", "{:.4f}".format):
        print("\n=== EQUITY BOOK V1 — ROBUSTNESS AUDIT ===")
        print(f"Equity curves: {args.equity_curves}")
        print(f"Series: {', '.join(series)}")
        print(f"Benchmarks: {', '.join(benchmarks)}")
        print("\nWindow Performance Summary:")
        print(perf_sorted[[c for c in perf_cols if c in perf_sorted.columns]].to_string(index=False))
        print("\nWindow Capture Summary:")
        print(capture[[c for c in capture_cols if c in capture.columns]].to_string(index=False))
    print(f"\nArtifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()
