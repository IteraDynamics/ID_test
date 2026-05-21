#!/usr/bin/env python
"""Equity sector relative-strength research runner.

First-pass non-crypto alpha/active-return research. Rotates among sector ETFs
using trailing momentum and compares against SPY, QQQ, RSP, and equal-weight
sector exposure.

Research-only. No runtime, broker, or live portfolio code is modified.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from research.harness.metrics import compute_metrics
from scripts.run_state_confirmed_risk_off_sweep import _load_close


SECTORS = {
    "XLK": "Technology",
    "XLF": "Financials",
    "XLE": "Energy",
    "XLV": "Health Care",
    "XLI": "Industrials",
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "XLU": "Utilities",
    "XLB": "Materials",
    "XLRE": "Real Estate",
    "XLC": "Communication Services",
}

BENCHMARKS = ["SPY", "QQQ", "RSP"]


def _fmt_pct(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "n/a"
    return "n/a" if math.isnan(v) else f"{v:.2f}%"


def _fmt_money(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "n/a"
    return "n/a" if math.isnan(v) else f"${v:,.2f}"


def _data_path(data_dir: Path, symbol: str) -> Path:
    return data_dir / f"{symbol}_1D.csv"


def _returns(close: pd.Series) -> pd.Series:
    return close.pct_change(fill_method=None).fillna(0.0)


def _equity_from_returns(rets: pd.Series, capital: float, name: str) -> pd.Series:
    out = capital * (1.0 + rets.fillna(0.0)).cumprod()
    out.name = name
    return out


def _metrics(label: str, equity: pd.Series, capital: float) -> dict[str, Any]:
    s = equity.dropna()
    if len(s) < 3:
        return {"label": label, "final_nav": None, "cagr_pct": None, "max_drawdown_pct": None, "sharpe": None, "calmar": None}
    m = compute_metrics(s, trades=[], params={"strategy_id": label, "asset": "PORTFOLIO", "initial_capital": capital})
    return {
        "label": label,
        "final_nav": float(s.iloc[-1]),
        "cagr_pct": m.cagr_pct,
        "max_drawdown_pct": m.max_drawdown_pct,
        "sharpe": m.sharpe,
        "calmar": m.calmar,
    }


def _window_return(equity: pd.Series, start: str, end: str) -> float | None:
    s = equity.loc[(equity.index >= pd.Timestamp(start)) & (equity.index <= pd.Timestamp(end))].dropna()
    if len(s) < 2:
        return None
    return (float(s.iloc[-1]) / float(s.iloc[0]) - 1.0) * 100.0


def _load_prices(data_dir: Path, symbols: list[str], start: str, end: str) -> pd.DataFrame:
    prices = {}
    for sym in symbols:
        path = _data_path(data_dir, sym)
        if not path.exists():
            raise FileNotFoundError(f"Missing required data file: {path}")
        prices[sym] = _load_close(str(path), sym, start, end)
    df = pd.DataFrame(prices).dropna(how="any")
    return df


def _spy_gate(prices: pd.DataFrame, window: int) -> pd.Series:
    spy = prices["SPY"]
    return (spy > spy.rolling(window, min_periods=window).mean()).rename("spy_sma_gate")


def _sector_weights(
    sector_prices: pd.DataFrame,
    lookback: int,
    top_n: int,
    gate_on: pd.Series,
    risk_off: str,
) -> pd.DataFrame:
    momentum = sector_prices / sector_prices.shift(lookback) - 1.0
    weights = pd.DataFrame(0.0, index=sector_prices.index, columns=list(sector_prices.columns) + ["cash"])
    gate = gate_on.reindex(sector_prices.index).fillna(False).astype(bool)
    for ts in sector_prices.index:
        if not bool(gate.loc[ts]):
            if risk_off == "cash":
                weights.loc[ts, "cash"] = 1.0
            elif risk_off == "equal_weight_sectors":
                for c in sector_prices.columns:
                    weights.loc[ts, c] = 1.0 / len(sector_prices.columns)
            else:
                raise ValueError(f"Unsupported risk_off: {risk_off}")
            continue
        row = momentum.loc[ts].dropna()
        if len(row) < top_n:
            weights.loc[ts, "cash"] = 1.0
            continue
        leaders = list(row.sort_values(ascending=False).head(top_n).index)
        for sym in leaders:
            weights.loc[ts, sym] = 1.0 / top_n
    return weights


def _portfolio_equity(returns: pd.DataFrame, weights: pd.DataFrame, capital: float, label: str, lag_weights: bool = True) -> pd.Series:
    w = weights.shift(1).fillna(0.0) if lag_weights else weights.fillna(0.0)
    asset_cols = [c for c in returns.columns if c in w.columns]
    rets = (w[asset_cols] * returns[asset_cols]).sum(axis=1)
    return _equity_from_returns(rets, capital, label)


def _exposure_summary(label: str, weights: pd.DataFrame) -> dict[str, Any]:
    w = weights.dropna(how="all")
    summary = {"label": label}
    for col in w.columns:
        summary[f"{col}_exposure_pct"] = float(w[col].mean() * 100.0)
    changed = (w.diff().abs().sum(axis=1) > 1e-12).fillna(False)
    summary["switch_count"] = max(0, int(changed.sum()) - 1)
    summary["avg_holding_days"] = None if summary["switch_count"] <= 0 else len(w) / summary["switch_count"]
    summary["gross_turnover_units"] = float(w.diff().abs().sum(axis=1).fillna(0.0).sum())
    return summary


def _add_windows(row: dict[str, Any], equity: pd.Series, args: argparse.Namespace) -> dict[str, Any]:
    row["crash_return_pct"] = _window_return(equity, args.crash_start, args.crash_end)
    row["bull_return_pct"] = _window_return(equity, args.bull_start, args.bull_end)
    row["recent_return_pct"] = _window_return(equity, args.recent_start, args.recent_end)
    return row


def _rank(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def safe(v: Any) -> float:
        try:
            x = float(v)
        except (TypeError, ValueError):
            return -9999.0
        return -9999.0 if math.isnan(x) else x
    return sorted(rows, key=lambda r: (safe(r.get("calmar")), safe(r.get("sharpe")), safe(r.get("cagr_pct"))), reverse=True)


def _print_rows(rows: list[dict[str, Any]], limit: int) -> None:
    print(f"  {'Rank':>4} {'Label':<34} {'Final NAV':>14} {'CAGR%':>9} {'MaxDD%':>9} {'Sharpe':>8} {'Calmar':>8} {'Crash%':>9} {'Bull%':>9} {'Sw':>5}")
    print("  " + "-" * 120)
    for i, r in enumerate(rows[:limit], start=1):
        print(
            f"  {i:>4} {r['label']:<34} {_fmt_money(r['final_nav']):>14} {_fmt_pct(r['cagr_pct']):>9} "
            f"{_fmt_pct(r['max_drawdown_pct']):>9} {r['sharpe']:>8.3f} {r['calmar']:>8.3f} "
            f"{_fmt_pct(r.get('crash_return_pct')):>9} {_fmt_pct(r.get('bull_return_pct')):>9} {r.get('switch_count', ''):>5}"
        )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Equity sector relative-strength research")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--start", default="2019-01-01")
    p.add_argument("--end", default="2025-12-30")
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--lookbacks", nargs="+", type=int, default=[63, 126, 252])
    p.add_argument("--top-n", nargs="+", type=int, default=[1, 3, 5])
    p.add_argument("--gates", nargs="+", default=["always_on", "spy_sma"])
    p.add_argument("--spy-sma-window", type=int, default=200)
    p.add_argument("--risk-off", choices=["cash", "equal_weight_sectors"], default="cash")
    p.add_argument("--crash-start", default="2020-02-19")
    p.add_argument("--crash-end", default="2020-03-23")
    p.add_argument("--bull-start", default="2020-03-24")
    p.add_argument("--bull-end", default="2021-12-31")
    p.add_argument("--recent-start", default="2022-01-01")
    p.add_argument("--recent-end", default="2025-12-30")
    p.add_argument("--console-top-n", type=int, default=25)
    p.add_argument("--out-dir", default="artifacts/equity_sector_relative_strength")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    symbols = sorted(set(list(SECTORS.keys()) + BENCHMARKS))
    prices = _load_prices(data_dir, symbols, args.start, args.end)
    sector_prices = prices[list(SECTORS.keys())]
    returns = prices.pct_change(fill_method=None).fillna(0.0)

    curves: dict[str, pd.Series] = {}
    rows: list[dict[str, Any]] = []
    exposures: list[dict[str, Any]] = []

    # Benchmarks.
    for sym in BENCHMARKS:
        eq = _equity_from_returns(returns[sym], args.capital, f"{sym.lower()}_bh")
        curves[eq.name] = eq
        row = _add_windows(_metrics(eq.name, eq, args.capital), eq, args)
        row.update({"type": "benchmark", "switch_count": 0})
        rows.append(row)

    ew_rets = returns[list(SECTORS.keys())].mean(axis=1)
    eq = _equity_from_returns(ew_rets, args.capital, "equal_weight_sectors")
    curves[eq.name] = eq
    row = _add_windows(_metrics(eq.name, eq, args.capital), eq, args)
    row.update({"type": "benchmark", "switch_count": 0})
    rows.append(row)

    always_on = pd.Series(True, index=sector_prices.index)
    spy_gate = _spy_gate(prices, args.spy_sma_window)

    for lookback in args.lookbacks:
        for n in args.top_n:
            for gate_name in args.gates:
                gate = always_on if gate_name == "always_on" else spy_gate
                label = f"sector_rs_top{n}_{lookback}d_{gate_name}"
                weights = _sector_weights(sector_prices, lookback, n, gate, args.risk_off)
                eq = _portfolio_equity(returns[list(SECTORS.keys())], weights, args.capital, label, lag_weights=True)
                curves[label] = eq
                exposure = _exposure_summary(label, weights)
                row = _add_windows(_metrics(label, eq, args.capital), eq, args)
                row.update({"type": "sector_rs", "lookback": lookback, "top_n": n, "gate": gate_name, "risk_off": args.risk_off, **exposure})
                rows.append(row)
                exposures.append(exposure)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(curves).to_csv(out / "equity_curves.csv")
    pd.DataFrame(rows).to_csv(out / "results.csv", index=False)
    pd.DataFrame(exposures).to_csv(out / "exposure_summary.csv", index=False)
    ranked = _rank(rows)
    (out / "summary.json").write_text(json.dumps({"config": vars(args), "results": rows}, indent=2, default=str), encoding="utf-8")
    with (out / "summary.md").open("w", encoding="utf-8") as f:
        f.write("# Equity Sector Relative Strength Summary\n\n")
        f.write("Research-only first-pass sector rotation test.\n\n")
        f.write("| Rank | Label | Final NAV | CAGR | MaxDD | Sharpe | Calmar | Crash | Bull | Switches |\n")
        f.write("|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|\n")
        for i, r in enumerate(ranked[: args.console_top_n], start=1):
            f.write(
                f"| {i} | {r['label']} | {_fmt_money(r['final_nav'])} | {_fmt_pct(r['cagr_pct'])} | {_fmt_pct(r['max_drawdown_pct'])} | "
                f"{r['sharpe']:.3f} | {r['calmar']:.3f} | {_fmt_pct(r.get('crash_return_pct'))} | {_fmt_pct(r.get('bull_return_pct'))} | {r.get('switch_count', '')} |\n"
            )
        f.write("\n```text\nRESEARCH ONLY\nNO RUNTIME WORK\nNO BROKER WORK\n```\n")

    print("=" * 132)
    print("  EQUITY SECTOR RELATIVE STRENGTH — FIRST PASS RESEARCH")
    print("=" * 132)
    print(f"  Date range : {args.start} -> {args.end}")
    print(f"  Risk off   : {args.risk_off}")
    print("-" * 132)
    _print_rows(ranked, args.console_top_n)
    print("=" * 132)
    print(f"  Summary: {out / 'summary.md'}")
    print(f"  Results: {out / 'results.csv'}")
    print("  Verdict: research output only; review before integration.\n")


if __name__ == "__main__":
    main()
