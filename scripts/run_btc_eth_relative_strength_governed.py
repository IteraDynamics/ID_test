#!/usr/bin/env python
"""Governed BTC/ETH relative-strength research runner.

This script tests the raw BTC/ETH relative-strength selector behind simple
crypto exposure gates. The goal is to see whether we can reduce the severe
crypto drawdowns while preserving enough of the selector's return edge.

Research-only. No runtime, broker, governor, or live execution code is modified.
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


def _valid_num(value: Any) -> bool:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return False
    return not math.isnan(v)


def _returns(close: pd.Series) -> pd.Series:
    return close.pct_change(fill_method=None).fillna(0.0)


def _equity_from_returns(rets: pd.Series, capital: float, name: str) -> pd.Series:
    out = capital * (1.0 + rets.fillna(0.0)).cumprod()
    out.name = name
    return out


def _rolling_sma(close: pd.Series, window: int) -> pd.Series:
    return close.rolling(window, min_periods=window).mean()


def _blend_close(btc: pd.Series, eth: pd.Series, btc_weight: float = 0.50) -> pd.Series:
    btc_norm = btc / btc.dropna().iloc[0]
    eth_norm = eth / eth.dropna().iloc[0]
    out = btc_weight * btc_norm + (1.0 - btc_weight) * eth_norm
    out.name = f"blend_btc{int(round(btc_weight * 100))}_eth{int(round((1.0 - btc_weight) * 100))}"
    return out


def _gate_series(gate: str, btc: pd.Series, eth: pd.Series, sma_window: int) -> pd.Series:
    if gate == "always_on":
        return pd.Series(True, index=btc.index, name=gate)
    if gate == "btc_sma":
        return (btc > _rolling_sma(btc, sma_window)).rename(gate)
    if gate == "blend_sma":
        blend = _blend_close(btc, eth, 0.50)
        return (blend > _rolling_sma(blend, sma_window)).rename(gate)
    if gate == "both_sma":
        return ((btc > _rolling_sma(btc, sma_window)) & (eth > _rolling_sma(eth, sma_window))).rename(gate)
    raise ValueError(f"Unsupported gate: {gate}")


def _selector_weights(btc: pd.Series, eth: pd.Series, lookback: int, style: str) -> pd.DataFrame:
    btc_mom = btc / btc.shift(lookback) - 1.0
    eth_mom = eth / eth.shift(lookback) - 1.0
    eth_leads = eth_mom > btc_mom
    weights = pd.DataFrame(index=btc.index, columns=["BTC", "ETH"], dtype=float)
    if style == "leader_100":
        weights["BTC"] = 1.0
        weights["ETH"] = 0.0
        weights.loc[eth_leads, "BTC"] = 0.0
        weights.loc[eth_leads, "ETH"] = 1.0
    elif style == "leader_75":
        weights["BTC"] = 0.75
        weights["ETH"] = 0.25
        weights.loc[eth_leads, "BTC"] = 0.25
        weights.loc[eth_leads, "ETH"] = 0.75
    else:
        raise ValueError(f"Unsupported style: {style}")
    unavailable = btc_mom.isna() | eth_mom.isna()
    weights.loc[unavailable, "BTC"] = 0.50
    weights.loc[unavailable, "ETH"] = 0.50
    return weights


def _apply_governor(selector: pd.DataFrame, gate_on: pd.Series, off_exposure: float, off_mode: str) -> pd.DataFrame:
    gate = gate_on.reindex(selector.index).fillna(False).astype(bool)
    out = selector.copy()
    if off_mode == "cash":
        out.loc[~gate, "BTC"] = 0.0
        out.loc[~gate, "ETH"] = 0.0
    elif off_mode == "reduced_selector":
        out.loc[~gate, "BTC"] = selector.loc[~gate, "BTC"] * off_exposure
        out.loc[~gate, "ETH"] = selector.loc[~gate, "ETH"] * off_exposure
    elif off_mode == "reduced_static_50_50":
        out.loc[~gate, "BTC"] = off_exposure * 0.50
        out.loc[~gate, "ETH"] = off_exposure * 0.50
    else:
        raise ValueError(f"Unsupported off_mode: {off_mode}")
    out["cash"] = 1.0 - out["BTC"] - out["ETH"]
    out.loc[out["cash"].abs() < 1e-12, "cash"] = 0.0
    return out


def _strategy_equity(
    btc_ret: pd.Series,
    eth_ret: pd.Series,
    weights: pd.DataFrame,
    capital: float,
    label: str,
    lag_weights: bool = True,
) -> pd.Series:
    w = weights.shift(1) if lag_weights else weights.copy()
    w = w.fillna({"BTC": 0.50, "ETH": 0.50, "cash": 0.0})
    if "cash" not in w.columns:
        w["cash"] = 1.0 - w["BTC"] - w["ETH"]
    rets = w["BTC"] * btc_ret + w["ETH"] * eth_ret
    return _equity_from_returns(rets, capital, label)


def _static_weights(index: pd.Index, btc_weight: float) -> pd.DataFrame:
    return pd.DataFrame({"BTC": btc_weight, "ETH": 1.0 - btc_weight, "cash": 0.0}, index=index)


def _metrics(label: str, equity: pd.Series, capital: float) -> dict[str, Any]:
    s = equity.dropna()
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


def _exposure_summary(label: str, weights: pd.DataFrame, gate_on: pd.Series | None = None) -> dict[str, Any]:
    w = weights.dropna(how="any")
    btc = w["BTC"]
    eth = w["ETH"]
    cash = w["cash"] if "cash" in w.columns else 1.0 - btc - eth
    changed = ((btc != btc.shift(1)) | (eth != eth.shift(1)) | (cash != cash.shift(1))).fillna(False)
    switch_count = max(0, int(changed.sum()) - 1)
    avg_hold = None if switch_count <= 0 else len(w) / switch_count
    gross_turnover = btc.diff().abs().fillna(0.0) + eth.diff().abs().fillna(0.0) + cash.diff().abs().fillna(0.0)
    gate_pct = None if gate_on is None else float(gate_on.reindex(w.index).fillna(False).astype(bool).mean() * 100.0)
    return {
        "label": label,
        "btc_exposure_pct": float(btc.mean() * 100.0),
        "eth_exposure_pct": float(eth.mean() * 100.0),
        "cash_exposure_pct": float(cash.mean() * 100.0),
        "gate_on_pct": gate_pct,
        "switch_count": switch_count,
        "avg_holding_days": avg_hold,
        "gross_turnover_units": float(gross_turnover.sum()),
    }


def _add_window_metrics(row: dict[str, Any], equity: pd.Series, args: argparse.Namespace) -> dict[str, Any]:
    row["crash_return_pct"] = _window_return(equity, args.crash_start, args.crash_end)
    row["bull_return_pct"] = _window_return(equity, args.bull_start, args.bull_end)
    row["recent_return_pct"] = _window_return(equity, args.recent_start, args.recent_end)
    return row


def _rank(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda r: (r["calmar"], r["sharpe"], r["cagr_pct"]), reverse=True)


def _constrained_rows(rows: list[dict[str, Any]], drawdown_floor: float) -> list[dict[str, Any]]:
    return [r for r in rows if _valid_num(r.get("max_drawdown_pct")) and float(r["max_drawdown_pct"]) >= drawdown_floor]


def _leaderboard_records(rows: list[dict[str, Any]], exposures: list[dict[str, Any]], floors: list[float], top_n: int) -> list[dict[str, Any]]:
    exposure_by_label = {e["label"]: e for e in exposures}
    records: list[dict[str, Any]] = []
    for floor in floors:
        for rank, row in enumerate(_rank(_constrained_rows(rows, floor))[:top_n], start=1):
            exp = exposure_by_label.get(row["label"], {})
            records.append({
                "drawdown_floor_pct": floor,
                "rank": rank,
                **row,
                "btc_exposure_pct": exp.get("btc_exposure_pct"),
                "eth_exposure_pct": exp.get("eth_exposure_pct"),
                "cash_exposure_pct": exp.get("cash_exposure_pct"),
                "gate_on_pct": exp.get("gate_on_pct"),
                "switch_count": exp.get("switch_count"),
                "avg_holding_days": exp.get("avg_holding_days"),
                "gross_turnover_units": exp.get("gross_turnover_units"),
            })
    return records


def _write_ranked_table(f, title: str, ranked: list[dict[str, Any]], exposure_by_label: dict[str, dict[str, Any]]) -> None:
    f.write(f"## {title}\n\n")
    f.write("| Rank | Label | Final NAV | CAGR | MaxDD | Sharpe | Calmar | Crash | Bull | Cash | Gate On | Switches |\n")
    f.write("|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n")
    if not ranked:
        f.write("| n/a | No rows matched this constraint |  |  |  |  |  |  |  |  |  |\n\n")
        return
    for i, r in enumerate(ranked, start=1):
        e = exposure_by_label.get(r["label"], {})
        f.write(
            f"| {i} | {r['label']} | {_fmt_money(r['final_nav'])} | {_fmt_pct(r['cagr_pct'])} | "
            f"{_fmt_pct(r['max_drawdown_pct'])} | {r['sharpe']:.3f} | {r['calmar']:.3f} | "
            f"{_fmt_pct(r['crash_return_pct'])} | {_fmt_pct(r['bull_return_pct'])} | "
            f"{_fmt_pct(e.get('cash_exposure_pct'))} | {_fmt_pct(e.get('gate_on_pct'))} | {e.get('switch_count', '')} |\n"
        )
    f.write("\n")


def _write_outputs(
    args: argparse.Namespace,
    curves: dict[str, pd.Series],
    rows: list[dict[str, Any]],
    exposures: list[dict[str, Any]],
) -> Path:
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(curves).to_csv(out / "equity_curves.csv")
    pd.DataFrame(rows).to_csv(out / "results.csv", index=False)
    pd.DataFrame(exposures).to_csv(out / "exposure_summary.csv", index=False)
    constrained = _leaderboard_records(rows, exposures, args.drawdown_floors, args.constrained_top_n)
    pd.DataFrame(constrained).to_csv(out / "constrained_leaderboards.csv", index=False)
    (out / "summary.json").write_text(
        json.dumps({"config": vars(args), "results": rows, "exposure_summary": exposures, "constrained_leaderboards": constrained}, indent=2, default=str),
        encoding="utf-8",
    )

    ranked = _rank(rows)
    exposure_by_label = {e["label"]: e for e in exposures}
    md = out / "summary.md"
    with md.open("w", encoding="utf-8") as f:
        f.write("# Governed BTC/ETH Relative Strength Research Summary\n\n")
        f.write("Research-only comparison of raw/static crypto exposure and governed BTC/ETH relative-strength variants.\n\n")
        f.write("This report includes constrained drawdown leaderboards because the highest-return rows may still be too volatile for an investable sleeve.\n\n")
        _write_ranked_table(f, "Top Results By Calmar", ranked[:args.console_top_n], exposure_by_label)
        for floor in args.drawdown_floors:
            constrained_ranked = _rank(_constrained_rows(rows, floor))[:args.constrained_top_n]
            _write_ranked_table(f, f"Top Results By Calmar With MaxDD >= {floor:.0f}%", constrained_ranked, exposure_by_label)
        f.write("## Boundary\n\n")
        f.write("```text\nRESEARCH ONLY\nNO RUNTIME WORK\nNO BROKER WORK\nNO PORTFOLIO INTEGRATION\n```\n")
    return md


def _print_rows(rows: list[dict[str, Any]], exposure_by_label: dict[str, dict[str, Any]], max_rows: int) -> None:
    print(
        f"  {'Rank':>4} {'Label':<58} {'Final NAV':>14} {'CAGR%':>9} {'MaxDD%':>9} "
        f"{'Sharpe':>8} {'Calmar':>8} {'Crash%':>9} {'Cash%':>8} {'GateOn':>8} {'Sw':>5}"
    )
    print("  " + "-" * 154)
    if not rows:
        print("  n/a  No rows matched this constraint")
        return
    for i, row in enumerate(rows[:max_rows], start=1):
        exp = exposure_by_label.get(row["label"], {})
        print(
            f"  {i:>4} {row['label']:<58} {_fmt_money(row['final_nav']):>14} {row['cagr_pct']:>8.2f}% "
            f"{row['max_drawdown_pct']:>8.2f}% {row['sharpe']:>8.3f} {row['calmar']:>8.3f} "
            f"{_fmt_pct(row['crash_return_pct']):>9} {_fmt_pct(exp.get('cash_exposure_pct')):>8} "
            f"{_fmt_pct(exp.get('gate_on_pct')):>8} {exp.get('switch_count', ''):>5}"
        )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Governed BTC/ETH relative-strength research runner")
    p.add_argument("--btc-data", required=True)
    p.add_argument("--eth-data", required=True)
    p.add_argument("--start", default="2019-01-01")
    p.add_argument("--end", default="2025-12-30")
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--lookbacks", nargs="+", type=int, default=[30, 60, 90])
    p.add_argument("--styles", nargs="+", default=["leader_100", "leader_75"])
    p.add_argument("--gates", nargs="+", default=["always_on", "btc_sma", "blend_sma", "both_sma"])
    p.add_argument("--gate-sma-windows", nargs="+", type=int, default=[200])
    p.add_argument("--off-modes", nargs="+", default=["cash", "reduced_static_50_50", "reduced_selector"])
    p.add_argument("--off-exposures", nargs="+", type=float, default=[0.0, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50])
    p.add_argument("--drawdown-floors", nargs="+", type=float, default=[-50.0, -45.0, -40.0])
    p.add_argument("--console-top-n", type=int, default=25)
    p.add_argument("--constrained-top-n", type=int, default=10)
    p.add_argument("--static-btc-weights", nargs="+", type=float, default=[0.50, 0.60])
    p.add_argument("--crash-start", default="2021-11-01")
    p.add_argument("--crash-end", default="2022-12-31")
    p.add_argument("--bull-start", default="2023-01-01")
    p.add_argument("--bull-end", default="2025-12-30")
    p.add_argument("--recent-start", default="2025-01-01")
    p.add_argument("--recent-end", default="2025-12-30")
    p.add_argument("--out-dir", default="artifacts/btc_eth_relative_strength_governed")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    btc = _load_close(args.btc_data, "BTC", args.start, args.end)
    eth = _load_close(args.eth_data, "ETH", args.start, args.end)
    common = btc.index.intersection(eth.index).sort_values()
    btc = btc.reindex(common).dropna()
    eth = eth.reindex(common).dropna()
    common = btc.index.intersection(eth.index).sort_values()
    btc = btc.reindex(common)
    eth = eth.reindex(common)
    btc_ret = _returns(btc)
    eth_ret = _returns(eth)

    curves: dict[str, pd.Series] = {}
    rows: list[dict[str, Any]] = []
    exposures: list[dict[str, Any]] = []

    baseline_defs = {"btc_bh": _static_weights(common, 1.0), "eth_bh": _static_weights(common, 0.0)}
    for w in args.static_btc_weights:
        baseline_defs[f"static_btc{int(round(w * 100))}_eth{int(round((1.0 - w) * 100))}"] = _static_weights(common, w)
    for label, weights in baseline_defs.items():
        equity = _strategy_equity(btc_ret, eth_ret, weights, args.capital, label, lag_weights=False)
        curves[label] = equity
        rows.append(_add_window_metrics(_metrics(label, equity, args.capital), equity, args))
        exposures.append(_exposure_summary(label, weights))

    for lookback in args.lookbacks:
        for style in args.styles:
            selector = _selector_weights(btc, eth, lookback, style)
            selector["cash"] = 0.0
            raw_label = f"raw_{style}_{lookback}d"
            raw_equity = _strategy_equity(btc_ret, eth_ret, selector, args.capital, raw_label, lag_weights=True)
            curves[raw_label] = raw_equity
            rows.append(_add_window_metrics(_metrics(raw_label, raw_equity, args.capital), raw_equity, args))
            exposures.append(_exposure_summary(raw_label, selector))

            for gate in args.gates:
                for sma in args.gate_sma_windows:
                    gate_on = _gate_series(gate, btc, eth, sma)
                    for off_mode in args.off_modes:
                        for off_exposure in args.off_exposures:
                            if off_mode == "cash" and off_exposure != 0.0:
                                continue
                            if off_mode != "cash" and off_exposure <= 0.0:
                                continue
                            label = f"gov_{style}_{lookback}d_{gate}{sma}_{off_mode}{int(round(off_exposure * 100))}"
                            weights = _apply_governor(selector, gate_on, off_exposure, off_mode)
                            equity = _strategy_equity(btc_ret, eth_ret, weights, args.capital, label, lag_weights=True)
                            curves[label] = equity
                            rows.append(_add_window_metrics(_metrics(label, equity, args.capital), equity, args))
                            exposures.append(_exposure_summary(label, weights, gate_on))

    md = _write_outputs(args, curves, rows, exposures)
    exposure_by_label = {e["label"]: e for e in exposures}
    ranked = _rank(rows)

    print("=" * 156)
    print("  GOVERNED BTC/ETH RELATIVE STRENGTH — RESEARCH")
    print("=" * 156)
    print(f"  Date range       : {args.start} -> {args.end}")
    print(f"  Lookbacks        : {', '.join(str(x) for x in args.lookbacks)}")
    print(f"  Gates            : {', '.join(args.gates)}")
    print(f"  Off exposures    : {', '.join(f'{x:.0%}' for x in args.off_exposures)}")
    print(f"  Drawdown floors  : {', '.join(f'{x:.0f}%' for x in args.drawdown_floors)}")
    print("-" * 156)
    print("  Top results by Calmar:")
    _print_rows(ranked, exposure_by_label, args.console_top_n)
    for floor in args.drawdown_floors:
        print("-" * 156)
        print(f"  Top results by Calmar with MaxDD >= {floor:.0f}%:")
        _print_rows(_rank(_constrained_rows(rows, floor)), exposure_by_label, args.constrained_top_n)
    print("=" * 156)
    print(f"  Summary: {md}")
    print("  Extra: artifacts/btc_eth_relative_strength_governed/constrained_leaderboards.csv")
    print("  Verdict: research output only; review before any integration.\n")


if __name__ == "__main__":
    main()
