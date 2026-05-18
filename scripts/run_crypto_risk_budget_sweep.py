#!/usr/bin/env python
"""Crypto Risk Budget v2 — hypothetical risk-budget sweep.

Research-only script. Takes an existing Fund v1 equity curve and tests simple
return multipliers as hypothetical risk-budget variants. The intent is to map
whether the current conservative Fund v1 return stream can be scaled toward a
more compelling crypto mandate before deeper strategy-parameter work.

Important:
- This is not a runtime change.
- This is not a paper-trading change.
- This is not an execution model.
- Multipliers above 1.0 are leverage-like what-if diagnostics and must not be
  interpreted as implementable without separate margin, liquidity, slippage,
  financing, and exchange-risk analysis.
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


def _build_passive_curves(btc_close: pd.Series, eth_close: pd.Series) -> pd.DataFrame:
    btc = _normalise(btc_close, "BTC_HODL")
    eth = _normalise(eth_close, "ETH_HODL")
    common = btc.index.intersection(eth.index)
    btc = btc.loc[common]
    eth = eth.loc[common]
    btc_ret = btc.pct_change().fillna(0.0)
    eth_ret = eth.pct_change().fillna(0.0)
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


def _scaled_equity_from_returns(base_equity: pd.Series, scale: float, floor: float = 0.0) -> pd.Series:
    """Apply a simple daily return multiplier.

    The floor protects against impossible negative equity in extreme what-if rows.
    It should not be read as a realistic liquidation/margin model.
    """
    base = base_equity.dropna().astype(float)
    rets = base.pct_change().fillna(0.0)
    scaled_rets = rets * float(scale)
    min_ret = -1.0 + float(floor)
    scaled_rets = scaled_rets.clip(lower=min_ret)
    eq = (1.0 + scaled_rets).cumprod()
    eq.name = f"Fund_v1_scale_{scale:.2f}x"
    return eq


def _capture_summary(strategy: pd.Series, benchmarks: pd.DataFrame) -> dict[str, float]:
    out: dict[str, float] = {}
    strategy_ret = strategy.pct_change().dropna()
    for bench_name, bench in benchmarks.items():
        bench_ret = bench.pct_change().dropna()
        joined = pd.concat([strategy_ret.rename("strategy"), bench_ret.rename("benchmark")], axis=1, join="inner").dropna()
        if joined.empty:
            continue
        strat_total = strategy.loc[joined.index[-1]] / strategy.loc[joined.index[0]] - 1.0
        bench_total = bench.loc[joined.index[-1]] / bench.loc[joined.index[0]] - 1.0
        up = joined["benchmark"] > 0
        down = joined["benchmark"] < 0
        up_denom = joined.loc[up, "benchmark"].sum()
        down_denom = joined.loc[down, "benchmark"].sum()
        out[f"return_capture_vs_{bench_name}"] = float(strat_total / bench_total) if abs(bench_total) > 1e-12 else 0.0
        out[f"up_day_capture_vs_{bench_name}"] = float(joined.loc[up, "strategy"].sum() / up_denom) if abs(up_denom) > 1e-12 else 0.0
        out[f"down_day_capture_vs_{bench_name}"] = float(joined.loc[down, "strategy"].sum() / down_denom) if abs(down_denom) > 1e-12 else 0.0
        out[f"vol_ratio_vs_{bench_name}"] = float(joined["strategy"].std(ddof=0) / joined["benchmark"].std(ddof=0)) if joined["benchmark"].std(ddof=0) > 0 else 0.0
    return out


def _yearly_table(curves: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name, curve in curves.items():
        yr = _yearly_returns(curve)
        for year, value in yr.items():
            rows.append({"series": name, "year": int(year), "return_pct": float(value * 100.0)})
    return pd.DataFrame(rows)


def _format_md_value(value: object, floatfmt: str = ".4f") -> str:
    if isinstance(value, float):
        return format(value, floatfmt)
    if pd.isna(value):
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


def _to_markdown_table(df: pd.DataFrame, floatfmt: str = ".4f") -> str:
    if df.empty:
        return "_No rows._"
    columns = [str(col) for col in df.columns]
    lines = ["| " + " | ".join(columns) + " |"]
    lines.append("| " + " | ".join(["---"] * len(columns)) + " |")
    for _, row in df.iterrows():
        vals = [_format_md_value(row[col], floatfmt=floatfmt) for col in df.columns]
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def _write_markdown(out_path: Path, period: dict[str, str | int], summary: pd.DataFrame, target_rows: pd.DataFrame) -> None:
    lines = [
        "# Crypto Risk Budget v2 — Risk-Budget Sweep",
        "",
        "## Status",
        "",
        "Research-only what-if. No runtime or paper-trading changes approved.",
        "",
        "## Period",
        "",
        "```text",
        f"Start: {period['start']}",
        f"End:   {period['end']}",
        f"Bars:  {period['bars']}",
        "```",
        "",
        "## Sweep Summary",
        "",
        _to_markdown_table(summary),
        "",
        "## Rows Near Target Frontier",
        "",
        _to_markdown_table(target_rows) if not target_rows.empty else "_No rows met target filters._",
        "",
        "## Guardrail",
        "",
        "```text",
        "Return multipliers above 1.0 are leverage-like diagnostics only.",
        "They are not approved runtime behavior and do not model financing, liquidation, exchange limits, or order-routing risk.",
        "```",
        "",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


def _parse_scales(text: str) -> list[float]:
    vals = []
    for raw in text.split(","):
        raw = raw.strip()
        if not raw:
            continue
        vals.append(float(raw))
    if not vals:
        raise ValueError("At least one scale is required")
    return sorted(set(vals))


def main() -> None:
    p = argparse.ArgumentParser(description="Run hypothetical Fund v1 crypto risk-budget multiplier sweep")
    p.add_argument("--fund-equity", required=True, help="Fund v1 equity curve CSV")
    p.add_argument("--fund-column", default="portfolio")
    p.add_argument("--btc-data", required=True)
    p.add_argument("--eth-data", required=True)
    p.add_argument("--scales", default="0.75,1.0,1.25,1.5,1.75,2.0", help="Comma-separated return multipliers")
    p.add_argument("--target-min-cagr", type=float, default=25.0)
    p.add_argument("--target-max-dd", type=float, default=-35.0, help="Lowest acceptable max drawdown pct, e.g. -35")
    p.add_argument("--target-min-sharpe", type=float, default=1.0)
    p.add_argument("--target-min-calmar", type=float, default=0.9)
    p.add_argument("--out-dir", default="artifacts/crypto_risk_budget_v2_sweep")
    args = p.parse_args()

    fund_df = _read_time_indexed_csv(Path(args.fund_equity))
    btc_df = _read_time_indexed_csv(Path(args.btc_data))
    eth_df = _read_time_indexed_csv(Path(args.eth_data))

    fund = _select_numeric_col(fund_df, [args.fund_column, "portfolio", "equity", "strategy_equity"], "Fund_v1")
    btc_close = _select_numeric_col(btc_df, ["close", "Close", "adj_close", "Adj Close"], "BTC_close")
    eth_close = _select_numeric_col(eth_df, ["close", "Close", "adj_close", "Adj Close"], "ETH_close")

    fund_daily = _normalise(_to_daily(fund), "Fund_v1")
    passive = _build_passive_curves(_to_daily(btc_close), _to_daily(eth_close))

    common = fund_daily.index
    for col in passive.columns:
        common = common.intersection(passive[col].dropna().index)
    if len(common) < 365:
        raise SystemExit(f"Insufficient common daily overlap: {len(common)} bars")

    fund_daily = fund_daily.loc[common]
    passive = passive.loc[common]

    scales = _parse_scales(args.scales)
    curve_map: dict[str, pd.Series] = {}
    rows = []
    for scale in scales:
        eq = _scaled_equity_from_returns(fund_daily, scale)
        curve_map[eq.name] = eq
        metrics = asdict(_metrics(eq))
        captures = _capture_summary(eq, passive)
        rows.append({"candidate": eq.name, "scale": scale, **metrics, **captures})

    # Include passive benchmarks for visual/context artifacts, but not as candidates.
    all_curves = pd.concat([pd.DataFrame(curve_map), passive], axis=1).dropna()
    summary = pd.DataFrame(rows)
    base = summary.loc[summary["scale"] == 1.0]
    if not base.empty:
        base_row = base.iloc[0]
        for col in ["total_return_pct", "cagr_pct", "max_drawdown_pct", "sharpe", "calmar", "ann_vol_pct"]:
            summary[f"delta_{col}_vs_1x"] = summary[col] - float(base_row[col])

    target_rows = summary[
        (summary["cagr_pct"] >= args.target_min_cagr)
        & (summary["max_drawdown_pct"] >= args.target_max_dd)
        & (summary["sharpe"] >= args.target_min_sharpe)
        & (summary["calmar"] >= args.target_min_calmar)
    ].copy()
    target_rows = target_rows.sort_values(["calmar", "cagr_pct"], ascending=[False, False])

    yearly = _yearly_table(all_curves)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary.to_csv(out_dir / "sweep_summary.csv", index=False)
    target_rows.to_csv(out_dir / "target_frontier_candidates.csv", index=False)
    all_curves.to_csv(out_dir / "equity_curves.csv")
    yearly.to_csv(out_dir / "yearly_returns.csv", index=False)

    period = {"start": str(all_curves.index[0]), "end": str(all_curves.index[-1]), "bars": int(len(all_curves))}
    payload = {
        "research_status": "research_only_hypothetical_risk_budget_sweep",
        "inputs": {
            "fund_equity": args.fund_equity,
            "fund_column": args.fund_column,
            "btc_data": args.btc_data,
            "eth_data": args.eth_data,
            "scales": scales,
        },
        "period": period,
        "target_filters": {
            "target_min_cagr": args.target_min_cagr,
            "target_max_dd": args.target_max_dd,
            "target_min_sharpe": args.target_min_sharpe,
            "target_min_calmar": args.target_min_calmar,
        },
        "artifacts": {
            "sweep_summary": str(out_dir / "sweep_summary.csv"),
            "target_frontier_candidates": str(out_dir / "target_frontier_candidates.csv"),
            "equity_curves": str(out_dir / "equity_curves.csv"),
            "yearly_returns": str(out_dir / "yearly_returns.csv"),
            "summary_json": str(out_dir / "summary.json"),
            "summary_md": str(out_dir / "summary.md"),
        },
        "decision": {
            "status": "diagnostic_only",
            "not_approved": [
                "runtime_change",
                "paper_trading_change",
                "higher_live_exposure",
                "leverage",
                "margin_use",
                "order_routing_change",
            ],
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    _write_markdown(out_dir / "summary.md", period, summary, target_rows)

    print("\n=== CRYPTO RISK BUDGET V2 — HYPOTHETICAL RISK-BUDGET SWEEP ===")
    print(f"Fund equity: {args.fund_equity} [{args.fund_column}]")
    print(f"Period:      {period['start']} → {period['end']} ({period['bars']} daily bars)")
    print(f"Scales:      {', '.join(f'{x:.2f}x' for x in scales)}")
    with pd.option_context("display.max_columns", None, "display.width", 260, "display.float_format", "{:.4f}".format):
        display_cols = [
            "candidate", "scale", "total_return_pct", "cagr_pct", "max_drawdown_pct", "sharpe", "calmar",
            "ann_vol_pct", "worst_90d_return_pct", "worst_180d_return_pct",
            "return_capture_vs_BTC_HODL", "return_capture_vs_BTC_ETH_50_50_DAILY_REBAL",
        ]
        display_cols = [c for c in display_cols if c in summary.columns]
        print("\nSweep Summary:")
        print(summary[display_cols].to_string(index=False))
        print("\nTarget Frontier Candidates:")
        if target_rows.empty:
            print("No rows met target filters.")
        else:
            print(target_rows[display_cols].to_string(index=False))
    print(f"\nArtifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()
