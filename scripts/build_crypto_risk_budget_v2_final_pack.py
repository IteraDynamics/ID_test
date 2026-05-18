#!/usr/bin/env python
"""Crypto Risk Budget v2 — final comparison pack builder.

Research-only report builder. Consumes direct hybrid finalist equity curves,
Fund v1 baseline equity, and BTC/ETH OHLCV data to generate a final comparison
pack before any paper-trading promotion decision.

Outputs:
    final_performance_summary.csv
    sortino_summary.csv
    yearly_returns.csv
    benchmark_capture_summary.csv
    baseline_delta_summary.csv
    paper_trading_readiness_checklist.md
    summary.json
    summary.md

No runtime, paper-trading, production allocation, or execution changes are made.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_CANDIDATE_CURVES = "artifacts/crypto_risk_budget_v2_hybrid_direct_confirmation/candidate_equity_curves.csv"
DEFAULT_FUND_EQUITY = "artifacts/fund_equal_cal_4s_2019-03-08_2025-12-31/equity_curves.csv"
DEFAULT_OUT = "artifacts/crypto_risk_budget_v2_final_comparison_pack"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build Crypto Risk Budget v2 final comparison pack",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--candidate-equity-curves", default=DEFAULT_CANDIDATE_CURVES)
    p.add_argument("--fund-equity", default=DEFAULT_FUND_EQUITY)
    p.add_argument("--fund-column", default="portfolio")
    p.add_argument("--btc-data", required=True)
    p.add_argument("--eth-data", required=True)
    p.add_argument("--target-return", type=float, default=0.0, help="Per-bar MAR/target return for Sortino")
    p.add_argument("--out-dir", default=DEFAULT_OUT)
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


def _select_numeric_col(df: pd.DataFrame, preferred: list[str], label: str) -> pd.Series:
    for col in preferred:
        if col in df.columns:
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
    s = pd.to_numeric(df[numeric[0]], errors="coerce").dropna().astype(float)
    s.name = label
    return s


def _normalise(s: pd.Series, name: str) -> pd.Series:
    s = s.dropna().astype(float)
    if s.empty:
        raise ValueError(f"Cannot normalize empty series: {name}")
    if float(s.iloc[0]) <= 0:
        raise ValueError(f"Cannot normalize series starting <= 0: {name}")
    out = s / float(s.iloc[0])
    out.name = name
    return out


def _to_daily(s: pd.Series) -> pd.Series:
    return s.sort_index().resample("1D").last().dropna()


def _bars_per_year(index: pd.DatetimeIndex) -> float:
    if len(index) < 3:
        return 365.25
    deltas = index.to_series().diff().dropna().dt.total_seconds()
    if deltas.empty:
        return 365.25
    med = float(deltas.median())
    if med <= 0:
        return 365.25
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


def _yearly_returns(curves: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name, curve in curves.items():
        s = curve.dropna().astype(float)
        yr = s.resample("YE").last().pct_change().dropna()
        for ts, ret in yr.items():
            rows.append({"series": name, "year": int(ts.year), "return_pct": float(ret * 100.0)})
    return pd.DataFrame(rows)


def _build_passive(btc_close: pd.Series, eth_close: pd.Series) -> pd.DataFrame:
    btc = _normalise(_to_daily(btc_close), "BTC_HODL")
    eth = _normalise(_to_daily(eth_close), "ETH_HODL")
    common = btc.index.intersection(eth.index)
    btc = btc.loc[common]
    eth = eth.loc[common]
    btc_ret = btc.pct_change().fillna(0.0)
    eth_ret = eth.pct_change().fillna(0.0)
    blend = (1.0 + (0.50 * btc_ret + 0.50 * eth_ret)).cumprod()
    blend.name = "BTC_ETH_50_50_DAILY_REBAL"
    return pd.DataFrame({"BTC_HODL": btc, "ETH_HODL": eth, "BTC_ETH_50_50_DAILY_REBAL": blend})


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


def _benchmark_capture(curves: pd.DataFrame, passive: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for series in curves.columns:
        if series in passive.columns:
            continue
        for benchmark in passive.columns:
            rows.append({"series": series, "benchmark": benchmark, **_capture(curves[series], passive[benchmark])})
    return pd.DataFrame(rows)


def _baseline_deltas(perf: pd.DataFrame, baseline: str) -> pd.DataFrame:
    if baseline not in set(perf["series"]):
        return pd.DataFrame()
    base = perf.loc[perf["series"] == baseline].iloc[0]
    rows = []
    metric_cols = [c for c in perf.columns if c != "series"]
    for _, row in perf.iterrows():
        if row["series"] == baseline:
            continue
        out = {"series": row["series"], "baseline": baseline}
        for col in metric_cols:
            out[f"delta_{col}"] = float(row[col]) - float(base[col])
        rows.append(out)
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


def _write_checklist(path: Path, primary: str, secondary: str) -> None:
    content = f"""# Crypto Risk Budget v2 — Paper-Trading Readiness Checklist

## Status

Research checklist only. No runtime, paper-trading, order-routing, leverage, or allocation changes are approved by this file.

## Primary Candidate

```text
{primary}
```

## Secondary Candidate

```text
{secondary}
```

## Required Before Paper-Trading Promotion

- [ ] Confirm direct hybrid backtest artifacts are committed or archived in a reproducible location.
- [ ] Confirm final comparison pack reviewed: performance, Sortino, yearly returns, passive benchmark capture, and baseline deltas.
- [ ] Confirm candidate survives stress-cost assumptions: fee=0.0008, base_slippage=5 bps, slippage_vol_factor=80, cooldown=2.
- [ ] Confirm no candidate relies on a single calendar year or narrow window.
- [ ] Confirm ETH_4H cap75 is intentionally approved as the only incremental risk-budget expansion for the primary candidate.
- [ ] Confirm BTC sleeves remain controlled under ecap75 for the primary candidate.
- [ ] Confirm ETH_1H remains controlled under ecap75.
- [ ] Confirm live Coinbase Advanced fee tier and expected order size before any paper-trading change.
- [ ] Confirm no leverage/margin is introduced.
- [ ] Confirm rollback plan to current Fund v1 baseline.
- [ ] Add explicit config naming for the candidate before runtime/paper-trading use.
- [ ] Run a final smoke test / CI harness after implementation.

## Non-Approved Items

```text
No live capital increase.
No leverage.
No production allocator change.
No order-routing change.
No paper-trading promotion until explicitly approved after review.
```
"""
    path.write_text(content, encoding="utf-8")


def _write_summary(path: Path, perf: pd.DataFrame, sortino: pd.DataFrame, yearly: pd.DataFrame, capture: pd.DataFrame, deltas: pd.DataFrame) -> None:
    perf_cols = ["series", "total_return_pct", "cagr_pct", "max_drawdown_pct", "sharpe", "sortino", "calmar", "ann_vol_pct", "worst_90d_return_pct", "worst_180d_return_pct", "max_time_underwater_days"]
    sortino_cols = ["series", "sortino", "daily_sortino"]
    capture_cols = ["series", "benchmark", "return_capture_ratio", "up_day_capture_ratio", "down_day_capture_ratio", "vol_ratio"]
    delta_cols = ["series", "baseline", "delta_cagr_pct", "delta_max_drawdown_pct", "delta_sharpe", "delta_sortino", "delta_calmar", "delta_ann_vol_pct"]
    lines = [
        "# Crypto Risk Budget v2 — Final Comparison Pack",
        "",
        "Research-only final comparison pack. No runtime or paper-trading changes approved.",
        "",
        "## Performance Summary",
        "",
        _md_table(perf, perf_cols),
        "",
        "## Sortino Summary",
        "",
        _md_table(sortino, sortino_cols),
        "",
        "## Baseline Deltas",
        "",
        _md_table(deltas, delta_cols),
        "",
        "## Benchmark Capture Summary",
        "",
        _md_table(capture, capture_cols),
        "",
        "## Yearly Returns",
        "",
        _md_table(yearly.pivot_table(index="year", columns="series", values="return_pct").reset_index()),
        "",
        "## Decision Guardrail",
        "",
        "```text",
        "The final pack supports research review only.",
        "Any paper-trading promotion requires explicit implementation, review, and approval.",
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    candidate_df = _read_time_csv(Path(args.candidate_equity_curves))
    candidate_curves = candidate_df.apply(pd.to_numeric, errors="coerce")

    fund_df = _read_time_csv(Path(args.fund_equity))
    fund = _select_numeric_col(fund_df, [args.fund_column, "portfolio", "equity"], "Fund_v1_current")

    btc_df = _read_time_csv(Path(args.btc_data))
    eth_df = _read_time_csv(Path(args.eth_data))
    btc_close = _select_numeric_col(btc_df, ["close", "Close", "adj_close", "Adj Close"], "BTC_close")
    eth_close = _select_numeric_col(eth_df, ["close", "Close", "adj_close", "Adj Close"], "ETH_close")
    passive = _build_passive(btc_close, eth_close)

    all_curves = candidate_curves.copy()
    all_curves["Fund_v1_current"] = fund
    # Normalize all on common overlap for apples-to-apples final pack.
    common = all_curves.dropna(how="all").index
    for col in all_curves.columns:
        common = common.intersection(all_curves[col].dropna().index)
    for col in passive.columns:
        common = common.intersection(passive[col].dropna().index)
    if len(common) < 365:
        raise SystemExit(f"Insufficient common overlap: {len(common)} bars")

    final_curves = pd.DataFrame({col: _normalise(all_curves[col].loc[common], col) for col in all_curves.columns})
    passive_common = pd.DataFrame({col: _normalise(passive[col].loc[common], col) for col in passive.columns})
    final_with_passive = pd.concat([final_curves, passive_common], axis=1).dropna()

    perf_rows = []
    for col in final_with_passive.columns:
        perf_rows.append({"series": col, **_perf(final_with_passive[col], args.target_return)})
    perf = pd.DataFrame(perf_rows).sort_values(["calmar", "cagr_pct"], ascending=[False, False])

    sortino_rows = []
    for col in final_with_passive.columns:
        hourly = _sortino(final_with_passive[col], args.target_return)
        daily = _sortino(_to_daily(final_with_passive[col]), args.target_return)
        sortino_rows.append({"series": col, "sortino": hourly, "daily_sortino": daily})
    sortino = pd.DataFrame(sortino_rows).sort_values("sortino", ascending=False)

    yearly = _yearly_returns(final_with_passive)
    capture = _benchmark_capture(final_curves, passive_common)
    deltas = _baseline_deltas(perf, "Fund_v1_current")

    final_with_passive.to_csv(out_dir / "normalized_equity_curves.csv")
    perf.to_csv(out_dir / "final_performance_summary.csv", index=False)
    sortino.to_csv(out_dir / "sortino_summary.csv", index=False)
    yearly.to_csv(out_dir / "yearly_returns.csv", index=False)
    capture.to_csv(out_dir / "benchmark_capture_summary.csv", index=False)
    deltas.to_csv(out_dir / "baseline_delta_summary.csv", index=False)
    _write_checklist(out_dir / "paper_trading_readiness_checklist.md", "hybrid_eth4h_cap75_only", "hybrid_4h_cap75_1h_ecap75")
    _write_summary(out_dir / "summary.md", perf, sortino, yearly, capture, deltas)

    payload = {
        "research_status": "research_only_final_comparison_pack",
        "inputs": {
            "candidate_equity_curves": args.candidate_equity_curves,
            "fund_equity": args.fund_equity,
            "fund_column": args.fund_column,
            "btc_data": args.btc_data,
            "eth_data": args.eth_data,
            "target_return": args.target_return,
        },
        "common_overlap": {"start": str(final_with_passive.index[0]), "end": str(final_with_passive.index[-1]), "bars": int(len(final_with_passive))},
        "artifacts": {
            "normalized_equity_curves": str(out_dir / "normalized_equity_curves.csv"),
            "final_performance_summary": str(out_dir / "final_performance_summary.csv"),
            "sortino_summary": str(out_dir / "sortino_summary.csv"),
            "yearly_returns": str(out_dir / "yearly_returns.csv"),
            "benchmark_capture_summary": str(out_dir / "benchmark_capture_summary.csv"),
            "baseline_delta_summary": str(out_dir / "baseline_delta_summary.csv"),
            "paper_trading_readiness_checklist": str(out_dir / "paper_trading_readiness_checklist.md"),
            "summary_md": str(out_dir / "summary.md"),
            "summary_json": str(out_dir / "summary.json"),
        },
        "decision": {"status": "diagnostic_only", "not_approved": ["runtime_change", "paper_trading_change", "higher_live_exposure", "leverage", "order_routing_change"]},
    }
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    perf_cols = ["series", "total_return_pct", "cagr_pct", "max_drawdown_pct", "sharpe", "sortino", "calmar", "ann_vol_pct", "worst_90d_return_pct", "worst_180d_return_pct", "max_time_underwater_days"]
    capture_cols = ["series", "benchmark", "return_capture_ratio", "up_day_capture_ratio", "down_day_capture_ratio", "vol_ratio"]
    delta_cols = ["series", "baseline", "delta_cagr_pct", "delta_max_drawdown_pct", "delta_sharpe", "delta_sortino", "delta_calmar", "delta_ann_vol_pct"]
    with pd.option_context("display.max_columns", None, "display.width", 300, "display.float_format", "{:.4f}".format):
        print("\n=== CRYPTO RISK BUDGET V2 — FINAL COMPARISON PACK ===")
        print(f"Common overlap: {payload['common_overlap']['start']} → {payload['common_overlap']['end']} ({payload['common_overlap']['bars']} bars)")
        print("\nFinal Performance Summary:")
        print(perf[[c for c in perf_cols if c in perf.columns]].to_string(index=False))
        print("\nSortino Summary:")
        print(sortino.to_string(index=False))
        print("\nBaseline Delta Summary:")
        if deltas.empty:
            print("No baseline deltas available.")
        else:
            print(deltas[[c for c in delta_cols if c in deltas.columns]].to_string(index=False))
        print("\nBenchmark Capture Summary:")
        print(capture[[c for c in capture_cols if c in capture.columns]].to_string(index=False))
    print(f"\nArtifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()
