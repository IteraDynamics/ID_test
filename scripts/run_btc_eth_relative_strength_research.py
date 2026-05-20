#!/usr/bin/env python
"""First-pass BTC/ETH relative-strength research runner.

Research-only script. It compares BTC buy-and-hold, ETH buy-and-hold,
static BTC/ETH blends, and simple relative-strength rotation variants.

No runtime, broker, governor, or live execution code is modified.
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


def _returns(close: pd.Series) -> pd.Series:
    return close.pct_change(fill_method=None).fillna(0.0)


def _equity_from_returns(rets: pd.Series, capital: float, name: str) -> pd.Series:
    out = capital * (1.0 + rets.fillna(0.0)).cumprod()
    out.name = name
    return out


def _static_blend(btc_ret: pd.Series, eth_ret: pd.Series, btc_weight: float, capital: float, name: str) -> pd.Series:
    rets = btc_weight * btc_ret + (1.0 - btc_weight) * eth_ret
    return _equity_from_returns(rets, capital, name)


def _relative_strength_weights(
    btc_close: pd.Series,
    eth_close: pd.Series,
    lookback: int,
    style: str,
) -> pd.DataFrame:
    btc_mom = btc_close / btc_close.shift(lookback) - 1.0
    eth_mom = eth_close / eth_close.shift(lookback) - 1.0
    eth_leader = eth_mom > btc_mom
    weights = pd.DataFrame(index=btc_close.index, columns=["BTC", "ETH"], dtype=float)
    if style == "leader_100":
        weights["BTC"] = 1.0
        weights["ETH"] = 0.0
        weights.loc[eth_leader, "BTC"] = 0.0
        weights.loc[eth_leader, "ETH"] = 1.0
    elif style == "leader_75":
        weights["BTC"] = 0.75
        weights["ETH"] = 0.25
        weights.loc[eth_leader, "BTC"] = 0.25
        weights.loc[eth_leader, "ETH"] = 0.75
    else:
        raise ValueError(f"Unsupported style: {style}")
    unavailable = btc_mom.isna() | eth_mom.isna()
    weights.loc[unavailable, "BTC"] = 0.50
    weights.loc[unavailable, "ETH"] = 0.50
    return weights


def _rotation_equity(
    btc_ret: pd.Series,
    eth_ret: pd.Series,
    weights: pd.DataFrame,
    capital: float,
    name: str,
    lag_weights: bool = True,
) -> pd.Series:
    w = weights.shift(1).fillna(0.50) if lag_weights else weights.fillna(0.50)
    rets = w["BTC"] * btc_ret + w["ETH"] * eth_ret
    return _equity_from_returns(rets, capital, name)


def _exposure_summary(label: str, weights: pd.DataFrame) -> dict[str, Any]:
    btc = weights["BTC"].dropna()
    eth = weights["ETH"].dropna()
    leader_switches = int(((btc != btc.shift(1)) | (eth != eth.shift(1))).sum())
    active_switches = max(0, leader_switches - 1)
    avg_hold = None
    if active_switches > 0:
        avg_hold = len(weights) / active_switches
    return {
        "label": label,
        "btc_exposure_pct": float(btc.mean() * 100.0) if len(btc) else None,
        "eth_exposure_pct": float(eth.mean() * 100.0) if len(eth) else None,
        "switch_count": active_switches,
        "avg_holding_days": avg_hold,
    }


def _metrics(label: str, equity: pd.Series, capital: float) -> dict[str, Any]:
    m = compute_metrics(equity.dropna(), trades=[], params={"strategy_id": label, "asset": "PORTFOLIO", "initial_capital": capital})
    return {
        "label": label,
        "final_nav": float(equity.dropna().iloc[-1]),
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


def _write_outputs(
    args: argparse.Namespace,
    curves: dict[str, pd.Series],
    rows: list[dict[str, Any]],
    exposures: list[dict[str, Any]],
) -> Path:
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    curves_df = pd.DataFrame(curves)
    curves_df.to_csv(out / "equity_curves.csv")
    pd.DataFrame(rows).to_csv(out / "results.csv", index=False)
    pd.DataFrame(exposures).to_csv(out / "exposure_summary.csv", index=False)
    summary_json = {"config": vars(args), "results": rows, "exposure_summary": exposures}
    (out / "summary.json").write_text(json.dumps(summary_json, indent=2, default=str), encoding="utf-8")
    ranked = sorted(rows, key=lambda r: (r["calmar"], r["sharpe"], r["cagr_pct"]), reverse=True)
    md = out / "summary.md"
    with md.open("w", encoding="utf-8") as f:
        f.write("# BTC/ETH Relative Strength Research Summary\n\n")
        f.write("Research-only first pass comparing static BTC/ETH exposure and relative-strength rotation.\n\n")
        f.write("## Top Results By Calmar\n\n")
        f.write("| Rank | Label | Final NAV | CAGR | MaxDD | Sharpe | Calmar | Crash | Bull | Recent |\n")
        f.write("|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|\n")
        for i, r in enumerate(ranked, start=1):
            f.write(
                f"| {i} | {r['label']} | {_fmt_money(r['final_nav'])} | {_fmt_pct(r['cagr_pct'])} | "
                f"{_fmt_pct(r['max_drawdown_pct'])} | {r['sharpe']:.3f} | {r['calmar']:.3f} | "
                f"{_fmt_pct(r['crash_return_pct'])} | {_fmt_pct(r['bull_return_pct'])} | {_fmt_pct(r['recent_return_pct'])} |\n"
            )
        f.write("\n## Exposure Summary\n\n")
        f.write("| Label | BTC Exposure | ETH Exposure | Switches | Avg Holding Days |\n")
        f.write("|---|---:|---:|---:|---:|\n")
        for e in exposures:
            f.write(
                f"| {e['label']} | {_fmt_pct(e['btc_exposure_pct'])} | {_fmt_pct(e['eth_exposure_pct'])} | "
                f"{e['switch_count']} | {'' if e['avg_holding_days'] is None else f'{e['avg_holding_days']:.1f}'} |\n"
            )
        f.write("\n## Boundary\n\n")
        f.write("```text\nRESEARCH ONLY\nNO RUNTIME WORK\nNO BROKER WORK\nNO PORTFOLIO INTEGRATION\n```\n")
    return md


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="BTC/ETH relative-strength research runner")
    p.add_argument("--btc-data", required=True)
    p.add_argument("--eth-data", required=True)
    p.add_argument("--start", default="2019-01-01")
    p.add_argument("--end", default="2025-12-30")
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--lookbacks", nargs="+", type=int, default=[30, 60, 90, 180])
    p.add_argument("--styles", nargs="+", default=["leader_100", "leader_75"])
    p.add_argument("--static-btc-weights", nargs="+", type=float, default=[0.50, 0.60])
    p.add_argument("--crash-start", default="2021-11-01")
    p.add_argument("--crash-end", default="2022-12-31")
    p.add_argument("--bull-start", default="2023-01-01")
    p.add_argument("--bull-end", default="2025-12-30")
    p.add_argument("--recent-start", default="2025-01-01")
    p.add_argument("--recent-end", default="2025-12-30")
    p.add_argument("--out-dir", default="artifacts/btc_eth_relative_strength")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    btc = _load_close(args.btc_data, "BTC", args.start, args.end)
    eth = _load_close(args.eth_data, "ETH", args.start, args.end)
    common = btc.index.intersection(eth.index).sort_values()
    btc = btc.reindex(common).dropna()
    eth = eth.reindex(common).dropna()
    common = btc.index.intersection(eth.index)
    btc = btc.reindex(common)
    eth = eth.reindex(common)
    btc_ret = _returns(btc)
    eth_ret = _returns(eth)

    curves: dict[str, pd.Series] = {}
    exposures: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []

    curves["btc_bh"] = _equity_from_returns(btc_ret, args.capital, "btc_bh")
    curves["eth_bh"] = _equity_from_returns(eth_ret, args.capital, "eth_bh")
    for label in ["btc_bh", "eth_bh"]:
        w = pd.DataFrame(index=common, columns=["BTC", "ETH"], dtype=float)
        if label == "btc_bh":
            w["BTC"], w["ETH"] = 1.0, 0.0
        else:
            w["BTC"], w["ETH"] = 0.0, 1.0
        exposures.append(_exposure_summary(label, w))

    for weight in args.static_btc_weights:
        label = f"static_btc{int(round(weight * 100))}_eth{int(round((1.0 - weight) * 100))}"
        curves[label] = _static_blend(btc_ret, eth_ret, weight, args.capital, label)
        w = pd.DataFrame({"BTC": weight, "ETH": 1.0 - weight}, index=common)
        exposures.append(_exposure_summary(label, w))

    for lookback in args.lookbacks:
        for style in args.styles:
            label = f"rs_{style}_{lookback}d"
            weights = _relative_strength_weights(btc, eth, lookback, style)
            curves[label] = _rotation_equity(btc_ret, eth_ret, weights, args.capital, label, lag_weights=True)
            exposures.append(_exposure_summary(label, weights))

    for label, equity in curves.items():
        row = _metrics(label, equity, args.capital)
        row["crash_return_pct"] = _window_return(equity, args.crash_start, args.crash_end)
        row["bull_return_pct"] = _window_return(equity, args.bull_start, args.bull_end)
        row["recent_return_pct"] = _window_return(equity, args.recent_start, args.recent_end)
        rows.append(row)

    md = _write_outputs(args, curves, rows, exposures)
    ranked = sorted(rows, key=lambda r: (r["calmar"], r["sharpe"], r["cagr_pct"]), reverse=True)

    print("=" * 132)
    print("  BTC/ETH RELATIVE STRENGTH — FIRST PASS RESEARCH")
    print("=" * 132)
    print(f"  Date range : {args.start} -> {args.end}")
    print(f"  Lookbacks  : {', '.join(str(x) for x in args.lookbacks)}")
    print("-" * 132)
    print(f"  {'Rank':>4} {'Label':<30} {'Final NAV':>14} {'CAGR%':>9} {'MaxDD%':>9} {'Sharpe':>8} {'Calmar':>8} {'Crash%':>9} {'Bull%':>9}")
    print("  " + "-" * 130)
    for i, row in enumerate(ranked, start=1):
        print(
            f"  {i:>4} {row['label']:<30} {_fmt_money(row['final_nav']):>14} {row['cagr_pct']:>8.2f}% "
            f"{row['max_drawdown_pct']:>8.2f}% {row['sharpe']:>8.3f} {row['calmar']:>8.3f} "
            f"{_fmt_pct(row['crash_return_pct']):>9} {_fmt_pct(row['bull_return_pct']):>9}"
        )
    print("=" * 132)
    print(f"  Summary: {md}")
    print("  Verdict: research output only; review before any integration.\n")


if __name__ == "__main__":
    main()
