#!/usr/bin/env python
"""Crypto Risk Budget v2 — upside/downside capture audit.

Research-only script. Compares a Fund v1 crypto equity curve against passive
BTC, ETH, and BTC/ETH blended HODL benchmarks over the same timestamp window.

The goal is to diagnose whether Fund v1 is leaving too much upside on the table
relative to passive crypto, before changing strategy risk parameters.

No runtime, paper-trading, execution, allocator, governor, or strategy logic is
modified by this script.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PerfMetrics:
    total_return_pct: float
    cagr_pct: float
    max_drawdown_pct: float
    sharpe: float
    calmar: float
    ann_vol_pct: float
    best_year_pct: float
    worst_year_pct: float
    worst_90d_return_pct: float
    worst_180d_return_pct: float
    time_underwater_pct: float
    max_time_underwater_days: float


def _read_time_indexed_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")
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
    lower_map = {str(col).lower(): col for col in df.columns}
    for name in preferred:
        if name.lower() in lower_map:
            return lower_map[name.lower()]
    return str(df.columns[0])


def _select_numeric_col(df: pd.DataFrame, preferred: Iterable[str], label: str) -> pd.Series:
    for col in preferred:
        if col in df.columns:
            s = pd.to_numeric(df[col], errors="coerce").dropna()
            if len(s) > 1:
                s.name = label
                return s.astype(float)
    numeric_cols = []
    for col in df.columns:
        s = pd.to_numeric(df[col], errors="coerce")
        if s.notna().sum() > 1:
            numeric_cols.append(col)
    if not numeric_cols:
        raise ValueError(f"No numeric columns found for {label}; columns={list(df.columns)}")
    s = pd.to_numeric(df[numeric_cols[0]], errors="coerce").dropna().astype(float)
    s.name = label
    return s


def _to_daily(series: pd.Series) -> pd.Series:
    return series.sort_index().resample("1D").last().dropna()


def _normalise(series: pd.Series, name: str) -> pd.Series:
    s = series.dropna().astype(float)
    if s.empty:
        raise ValueError(f"Cannot normalise empty series: {name}")
    if float(s.iloc[0]) <= 0:
        raise ValueError(f"Cannot normalise series starting <= 0: {name}")
    out = s / float(s.iloc[0])
    out.name = name
    return out


def _infer_bars_per_year(index: pd.DatetimeIndex) -> float:
    if len(index) < 3:
        return 365.25
    deltas = index.to_series().diff().dropna().dt.total_seconds()
    if deltas.empty:
        return 365.25
    median_seconds = float(deltas.median())
    if median_seconds <= 0:
        return 365.25
    return float((365.25 * 24 * 3600) / median_seconds)


def _drawdown(equity: pd.Series) -> pd.Series:
    eq = equity.dropna().astype(float)
    return eq / eq.cummax() - 1.0


def _max_time_underwater_days(equity: pd.Series) -> float:
    eq = equity.dropna().astype(float)
    if eq.empty:
        return 0.0
    dd = _drawdown(eq)
    underwater = dd < 0
    max_days = 0.0
    start = None
    for ts, is_underwater in underwater.items():
        if is_underwater and start is None:
            start = ts
        elif not is_underwater and start is not None:
            max_days = max(max_days, (ts - start).total_seconds() / 86400.0)
            start = None
    if start is not None:
        max_days = max(max_days, (eq.index[-1] - start).total_seconds() / 86400.0)
    return float(max_days)


def _yearly_returns(equity: pd.Series) -> pd.Series:
    annual = equity.resample("YE").last().pct_change().dropna()
    annual.index = annual.index.year
    return annual


def _metrics(equity: pd.Series) -> PerfMetrics:
    eq = equity.dropna().astype(float)
    if len(eq) < 2:
        return PerfMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)

    rets = eq.pct_change().dropna()
    total_return = float(eq.iloc[-1] / eq.iloc[0] - 1.0)
    years = max((eq.index[-1] - eq.index[0]).total_seconds() / (365.25 * 24 * 3600), 1e-9)
    cagr = float((eq.iloc[-1] / eq.iloc[0]) ** (1.0 / years) - 1.0)
    dd = _drawdown(eq)
    max_dd = float(dd.min())
    bars_per_year = _infer_bars_per_year(eq.index)
    std = float(rets.std(ddof=0)) if len(rets) else 0.0
    ann_vol = std * math.sqrt(bars_per_year) if std > 0 else 0.0
    sharpe = float((rets.mean() / std) * math.sqrt(bars_per_year)) if std > 0 else 0.0
    calmar = float(cagr / abs(max_dd)) if max_dd < 0 else 0.0
    yr = _yearly_returns(eq)
    worst_90 = float(eq.pct_change(90).dropna().min()) if len(eq) > 90 else 0.0
    worst_180 = float(eq.pct_change(180).dropna().min()) if len(eq) > 180 else 0.0
    time_underwater = float((dd < 0).mean()) if len(dd) else 0.0

    return PerfMetrics(
        total_return_pct=total_return * 100.0,
        cagr_pct=cagr * 100.0,
        max_drawdown_pct=max_dd * 100.0,
        sharpe=sharpe,
        calmar=calmar,
        ann_vol_pct=ann_vol * 100.0,
        best_year_pct=float(yr.max() * 100.0) if len(yr) else 0.0,
        worst_year_pct=float(yr.min() * 100.0) if len(yr) else 0.0,
        worst_90d_return_pct=worst_90 * 100.0,
        worst_180d_return_pct=worst_180 * 100.0,
        time_underwater_pct=time_underwater * 100.0,
        max_time_underwater_days=_max_time_underwater_days(eq),
    )


def _capture_ratio(strategy_returns: pd.Series, benchmark_returns: pd.Series, mask: pd.Series) -> float:
    aligned = pd.concat([strategy_returns, benchmark_returns, mask.astype(bool)], axis=1, join="inner").dropna()
    if aligned.empty:
        return 0.0
    s = aligned.iloc[:, 0]
    b = aligned.iloc[:, 1]
    m = aligned.iloc[:, 2].astype(bool)
    denom = float(b[m].sum())
    if abs(denom) < 1e-12:
        return 0.0
    return float(s[m].sum() / denom)


def _build_passive_curves(btc_close: pd.Series, eth_close: pd.Series) -> pd.DataFrame:
    btc = _normalise(btc_close, "BTC_HODL")
    eth = _normalise(eth_close, "ETH_HODL")
    common = btc.index.intersection(eth.index)
    btc = btc.loc[common]
    eth = eth.loc[common]

    btc_ret = btc.pct_change().fillna(0.0)
    eth_ret = eth.pct_change().fillna(0.0)

    # Daily rebalanced 50/50 and 60/40 passive benchmarks.
    half = (1.0 + (0.50 * btc_ret + 0.50 * eth_ret)).cumprod()
    sixty = (1.0 + (0.60 * btc_ret + 0.40 * eth_ret)).cumprod()
    half.name = "BTC_ETH_50_50_DAILY_REBAL"
    sixty.name = "BTC_ETH_60_40_DAILY_REBAL"

    return pd.DataFrame({
        "BTC_HODL": btc,
        "ETH_HODL": eth,
        "BTC_ETH_50_50_DAILY_REBAL": half,
        "BTC_ETH_60_40_DAILY_REBAL": sixty,
    })


def _rolling_windows(equity_curves: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name, curve in equity_curves.items():
        curve = curve.dropna().astype(float)
        for window in [30, 90, 180, 365]:
            ret = curve.pct_change(window).dropna()
            if ret.empty:
                continue
            rows.append({
                "series": name,
                "window_days": window,
                "worst_return_pct": float(ret.min() * 100.0),
                "best_return_pct": float(ret.max() * 100.0),
                "median_return_pct": float(ret.median() * 100.0),
            })
    return pd.DataFrame(rows)


def _yearly_capture(strategy: pd.Series, benchmarks: pd.DataFrame) -> pd.DataFrame:
    rows = []
    strategy_ret = strategy.pct_change().dropna()
    for bench_name, bench in benchmarks.items():
        bench_ret = bench.pct_change().dropna()
        joined = pd.concat([strategy_ret.rename("strategy"), bench_ret.rename("benchmark")], axis=1, join="inner").dropna()
        for year, grp in joined.groupby(joined.index.year):
            b_sum = float(grp["benchmark"].sum())
            s_sum = float(grp["strategy"].sum())
            rows.append({
                "year": int(year),
                "benchmark": bench_name,
                "strategy_simple_sum_return_pct": s_sum * 100.0,
                "benchmark_simple_sum_return_pct": b_sum * 100.0,
                "capture_ratio": float(s_sum / b_sum) if abs(b_sum) > 1e-12 else 0.0,
                "benchmark_positive": bool(b_sum > 0),
            })
    return pd.DataFrame(rows)


def _capture_summary(strategy: pd.Series, benchmarks: pd.DataFrame) -> pd.DataFrame:
    rows = []
    strategy_returns = strategy.pct_change().dropna()
    for bench_name, bench in benchmarks.items():
        bench_returns = bench.pct_change().dropna()
        joined = pd.concat([strategy_returns.rename("strategy"), bench_returns.rename("benchmark")], axis=1, join="inner").dropna()
        if joined.empty:
            continue
        up_mask = joined["benchmark"] > 0
        down_mask = joined["benchmark"] < 0
        bull_mask = joined["benchmark"].rolling(90).sum() > 0
        bear_mask = joined["benchmark"].rolling(90).sum() < 0
        rows.append({
            "benchmark": bench_name,
            "strategy_total_return_pct": float((strategy.loc[joined.index[-1]] / strategy.loc[joined.index[0]] - 1.0) * 100.0),
            "benchmark_total_return_pct": float((bench.loc[joined.index[-1]] / bench.loc[joined.index[0]] - 1.0) * 100.0),
            "return_capture_ratio": float((strategy.loc[joined.index[-1]] / strategy.loc[joined.index[0]] - 1.0) / (bench.loc[joined.index[-1]] / bench.loc[joined.index[0]] - 1.0)) if abs(bench.loc[joined.index[-1]] / bench.loc[joined.index[0]] - 1.0) > 1e-12 else 0.0,
            "up_day_capture_ratio": _capture_ratio(joined["strategy"], joined["benchmark"], up_mask),
            "down_day_capture_ratio": _capture_ratio(joined["strategy"], joined["benchmark"], down_mask),
            "rolling_90d_bull_capture_ratio": _capture_ratio(joined["strategy"], joined["benchmark"], bull_mask.fillna(False)),
            "rolling_90d_bear_capture_ratio": _capture_ratio(joined["strategy"], joined["benchmark"], bear_mask.fillna(False)),
            "strategy_ann_vol_pct": float(joined["strategy"].std(ddof=0) * math.sqrt(_infer_bars_per_year(joined.index)) * 100.0),
            "benchmark_ann_vol_pct": float(joined["benchmark"].std(ddof=0) * math.sqrt(_infer_bars_per_year(joined.index)) * 100.0),
            "vol_ratio_vs_benchmark": float(joined["strategy"].std(ddof=0) / joined["benchmark"].std(ddof=0)) if joined["benchmark"].std(ddof=0) > 0 else 0.0,
        })
    return pd.DataFrame(rows)


def _exposure_proxy(strategy: pd.Series, benchmarks: pd.DataFrame) -> pd.DataFrame:
    """Estimate realised beta/exposure proxy from rolling covariance.

    This is not actual strategy exposure. It is a realised sensitivity proxy.
    """
    rows = []
    strategy_ret = strategy.pct_change().dropna()
    for bench_name, bench in benchmarks.items():
        bench_ret = bench.pct_change().dropna()
        joined = pd.concat([strategy_ret.rename("strategy"), bench_ret.rename("benchmark")], axis=1, join="inner").dropna()
        if len(joined) < 90:
            continue
        rolling_cov = joined["strategy"].rolling(90).cov(joined["benchmark"])
        rolling_var = joined["benchmark"].rolling(90).var()
        beta = (rolling_cov / rolling_var).replace([np.inf, -np.inf], np.nan).dropna()
        rows.append({
            "benchmark": bench_name,
            "avg_rolling_90d_beta": float(beta.mean()) if len(beta) else 0.0,
            "median_rolling_90d_beta": float(beta.median()) if len(beta) else 0.0,
            "p10_rolling_90d_beta": float(beta.quantile(0.10)) if len(beta) else 0.0,
            "p90_rolling_90d_beta": float(beta.quantile(0.90)) if len(beta) else 0.0,
        })
    return pd.DataFrame(rows)


def _write_markdown(out_path: Path, period: dict[str, str | int], metrics: pd.DataFrame, capture: pd.DataFrame) -> None:
    lines = [
        "# Crypto Risk Budget v2 — Upside/Downside Capture Audit",
        "",
        "## Status",
        "",
        "Research-only diagnostic. No runtime, paper-trading, execution, allocator, governor, or strategy logic changed.",
        "",
        "## Period",
        "",
        "```text",
        f"Start: {period['start']}",
        f"End:   {period['end']}",
        f"Bars:  {period['bars']}",
        "```",
        "",
        "## Performance Metrics",
        "",
        metrics.to_markdown(index=False, floatfmt=".4f"),
        "",
        "## Capture Summary",
        "",
        capture.to_markdown(index=False, floatfmt=".4f") if not capture.empty else "_No capture rows._",
        "",
        "## Interpretation Guardrail",
        "",
        "```text",
        "This audit measures where Fund v1 sits versus passive BTC/ETH benchmarks.",
        "It should be used to identify upside-capture gaps before changing strategy risk parameters.",
        "Higher CAGR candidates must still preserve a meaningful drawdown advantage versus passive crypto.",
        "```",
        "",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser(description="Analyze Fund v1 upside/downside capture versus passive crypto benchmarks")
    p.add_argument("--fund-equity", required=True, help="Fund v1 equity curve CSV")
    p.add_argument("--fund-column", default="portfolio", help="Fund equity column to use")
    p.add_argument("--btc-data", required=True, help="BTC OHLCV CSV")
    p.add_argument("--eth-data", required=True, help="ETH OHLCV CSV")
    p.add_argument("--out-dir", default="artifacts/crypto_risk_budget_v2_capture_audit")
    args = p.parse_args()

    fund_df = _read_time_indexed_csv(Path(args.fund_equity))
    btc_df = _read_time_indexed_csv(Path(args.btc_data))
    eth_df = _read_time_indexed_csv(Path(args.eth_data))

    fund = _select_numeric_col(fund_df, [args.fund_column, "portfolio", "equity", "strategy_equity"], "Fund_v1")
    btc_close = _select_numeric_col(btc_df, ["close", "Close", "adj_close", "Adj Close"], "BTC_close")
    eth_close = _select_numeric_col(eth_df, ["close", "Close", "adj_close", "Adj Close"], "ETH_close")

    fund_daily = _normalise(_to_daily(fund), "Fund_v1")
    btc_daily = _to_daily(btc_close)
    eth_daily = _to_daily(eth_close)
    passive = _build_passive_curves(btc_daily, eth_daily)

    common = fund_daily.index
    for col in passive.columns:
        common = common.intersection(passive[col].dropna().index)
    if len(common) < 365:
        raise SystemExit(f"Insufficient common daily overlap: {len(common)} bars")

    fund_daily = fund_daily.loc[common]
    passive = passive.loc[common]
    all_curves = pd.concat([fund_daily, passive], axis=1).dropna()

    metrics_rows = []
    for name, curve in all_curves.items():
        metrics_rows.append({"series": name, **asdict(_metrics(curve))})
    metrics = pd.DataFrame(metrics_rows)

    capture = _capture_summary(fund_daily.loc[all_curves.index], passive.loc[all_curves.index])
    yearly = _yearly_capture(fund_daily.loc[all_curves.index], passive.loc[all_curves.index])
    rolling = _rolling_windows(all_curves)
    exposure = _exposure_proxy(fund_daily.loc[all_curves.index], passive.loc[all_curves.index])

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    all_curves.to_csv(out_dir / "equity_curves.csv")
    metrics.to_csv(out_dir / "performance_metrics.csv", index=False)
    capture.to_csv(out_dir / "capture_summary.csv", index=False)
    yearly.to_csv(out_dir / "yearly_capture_summary.csv", index=False)
    rolling.to_csv(out_dir / "rolling_window_summary.csv", index=False)
    exposure.to_csv(out_dir / "exposure_diagnostics.csv", index=False)

    period = {"start": str(all_curves.index[0]), "end": str(all_curves.index[-1]), "bars": int(len(all_curves))}
    summary = {
        "research_status": "research_only_capture_audit",
        "inputs": {
            "fund_equity": args.fund_equity,
            "fund_column": args.fund_column,
            "btc_data": args.btc_data,
            "eth_data": args.eth_data,
        },
        "period": period,
        "artifacts": {
            "equity_curves": str(out_dir / "equity_curves.csv"),
            "performance_metrics": str(out_dir / "performance_metrics.csv"),
            "capture_summary": str(out_dir / "capture_summary.csv"),
            "yearly_capture_summary": str(out_dir / "yearly_capture_summary.csv"),
            "rolling_window_summary": str(out_dir / "rolling_window_summary.csv"),
            "exposure_diagnostics": str(out_dir / "exposure_diagnostics.csv"),
            "summary_json": str(out_dir / "summary.json"),
            "summary_md": str(out_dir / "summary.md"),
        },
        "decision": {
            "status": "diagnostic_only",
            "next_step": "use capture gaps to decide which Fund v1 risk-budget lever to test first",
            "not_approved": [
                "paper_trading_change",
                "runtime_change",
                "higher_live_exposure",
                "leverage",
                "order_routing_change",
            ],
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    _write_markdown(out_dir / "summary.md", period, metrics, capture)

    print("\n=== CRYPTO RISK BUDGET V2 — UPSIDE/DOWNSIDE CAPTURE AUDIT ===")
    print(f"Fund equity: {args.fund_equity} [{args.fund_column}]")
    print(f"BTC data:    {args.btc_data}")
    print(f"ETH data:    {args.eth_data}")
    print(f"Period:      {period['start']} → {period['end']}  ({period['bars']} daily bars)")
    with pd.option_context("display.max_columns", None, "display.width", 240, "display.float_format", "{:.4f}".format):
        print("\nPerformance Metrics:")
        print(metrics.to_string(index=False))
        print("\nCapture Summary:")
        print(capture.to_string(index=False))
        print("\nExposure Diagnostics:")
        print(exposure.to_string(index=False))
    print(f"\nArtifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()
