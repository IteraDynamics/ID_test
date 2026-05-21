#!/usr/bin/env python
"""Risk-budgeted BTC/ETH relative-strength research runner.

Research-only script. Tests whether an equity-curve drawdown rule can reduce the
large drawdowns seen in raw and SMA-gated BTC/ETH relative-strength variants.
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
from scripts.run_btc_eth_relative_strength_governed import (
    _fmt_money,
    _fmt_pct,
    _gate_series,
    _returns,
    _selector_weights,
    _static_weights,
)


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


def _off_weights(selector_row: pd.Series, mode: str, exposure: float) -> dict[str, float]:
    if mode == "cash":
        return {"BTC": 0.0, "ETH": 0.0, "cash": 1.0}
    if mode == "reduced_selector":
        btc = float(selector_row["BTC"]) * exposure
        eth = float(selector_row["ETH"]) * exposure
        return {"BTC": btc, "ETH": eth, "cash": 1.0 - btc - eth}
    if mode == "reduced_static_50_50":
        return {"BTC": 0.5 * exposure, "ETH": 0.5 * exposure, "cash": 1.0 - exposure}
    raise ValueError(f"unsupported mode: {mode}")


def _simulate(
    label: str,
    btc_ret: pd.Series,
    eth_ret: pd.Series,
    selector: pd.DataFrame,
    gate_on: pd.Series,
    capital: float,
    gate_off_exposure: float,
    risk_trigger: float,
    risk_release: float,
    risk_mode: str,
    risk_exposure: float,
    release_requires_gate: bool,
) -> tuple[pd.Series, dict[str, Any]]:
    idx = btc_ret.index.intersection(eth_ret.index).intersection(selector.index).sort_values()
    gate = gate_on.reindex(idx).fillna(False).astype(bool)
    selector = selector.reindex(idx).ffill().fillna({"BTC": 0.5, "ETH": 0.5, "cash": 0.0})

    nav = capital
    peak = capital
    risk_state = False
    prev_w = {"BTC": 0.5, "ETH": 0.5, "cash": 0.0}
    rows = []
    entries = exits = 0

    for i, ts in enumerate(idx):
        daily_ret = 0.0 if i == 0 else prev_w["BTC"] * float(btc_ret.loc[ts]) + prev_w["ETH"] * float(eth_ret.loc[ts])
        nav *= 1.0 + daily_ret
        peak = max(peak, nav)
        dd = nav / peak - 1.0

        if (not risk_state) and dd <= risk_trigger:
            risk_state = True
            entries += 1
        elif risk_state and dd >= risk_release and ((not release_requires_gate) or bool(gate.loc[ts])):
            risk_state = False
            exits += 1

        srow = selector.loc[ts]
        if risk_state:
            w = _off_weights(srow, risk_mode, risk_exposure)
        elif bool(gate.loc[ts]):
            w = {"BTC": float(srow["BTC"]), "ETH": float(srow["ETH"]), "cash": float(srow.get("cash", 0.0))}
        else:
            w = _off_weights(srow, "reduced_selector", gate_off_exposure)

        rows.append({"date": ts, "nav": nav, "dd": dd, "risk_state": risk_state, "gate_on": bool(gate.loc[ts]), **{f"w_{k}": v for k, v in w.items()}})
        prev_w = w

    df = pd.DataFrame(rows).set_index("date")
    eq = df["nav"].rename(label)
    changes = ((df["w_BTC"] != df["w_BTC"].shift(1)) | (df["w_ETH"] != df["w_ETH"].shift(1)) | (df["w_cash"] != df["w_cash"].shift(1))).fillna(False)
    meta = {
        "risk_entries": entries,
        "risk_exits": exits,
        "risk_state_pct": float(df["risk_state"].mean() * 100.0),
        "gate_on_pct": float(df["gate_on"].mean() * 100.0),
        "cash_exposure_pct": float(df["w_cash"].mean() * 100.0),
        "btc_exposure_pct": float(df["w_BTC"].mean() * 100.0),
        "eth_exposure_pct": float(df["w_ETH"].mean() * 100.0),
        "switch_count": max(0, int(changes.sum()) - 1),
    }
    return eq, meta


def _rank(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda r: (r["calmar"], r["sharpe"], r["cagr_pct"]), reverse=True)


def _constrained(rows: list[dict[str, Any]], floor: float) -> list[dict[str, Any]]:
    return [r for r in rows if not math.isnan(float(r["max_drawdown_pct"])) and float(r["max_drawdown_pct"]) >= floor]


def _print_rows(rows: list[dict[str, Any]], limit: int) -> None:
    print(f"  {'Rank':>4} {'Label':<60} {'Final NAV':>14} {'CAGR%':>9} {'MaxDD%':>9} {'Sharpe':>8} {'Calmar':>8} {'Crash%':>9} {'Cash%':>8} {'Risk%':>8} {'Sw':>5}")
    print("  " + "-" * 158)
    if not rows:
        print("  n/a  No rows matched this constraint")
        return
    for i, r in enumerate(rows[:limit], start=1):
        print(f"  {i:>4} {r['label']:<60} {_fmt_money(r['final_nav']):>14} {r['cagr_pct']:>8.2f}% {r['max_drawdown_pct']:>8.2f}% {r['sharpe']:>8.3f} {r['calmar']:>8.3f} {_fmt_pct(r['crash_return_pct']):>9} {_fmt_pct(r.get('cash_exposure_pct')):>8} {_fmt_pct(r.get('risk_state_pct')):>8} {r.get('switch_count',''):>5}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Risk-budgeted BTC/ETH relative-strength research")
    p.add_argument("--btc-data", required=True)
    p.add_argument("--eth-data", required=True)
    p.add_argument("--start", default="2019-01-01")
    p.add_argument("--end", default="2025-12-30")
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--lookbacks", nargs="+", type=int, default=[30, 60, 90])
    p.add_argument("--styles", nargs="+", default=["leader_100", "leader_75"])
    p.add_argument("--gates", nargs="+", default=["blend_sma", "btc_sma", "both_sma"])
    p.add_argument("--gate-sma-windows", nargs="+", type=int, default=[200])
    p.add_argument("--gate-off-exposures", nargs="+", type=float, default=[0.25, 0.50])
    p.add_argument("--risk-triggers", nargs="+", type=float, default=[-0.20, -0.25, -0.30])
    p.add_argument("--risk-releases", nargs="+", type=float, default=[-0.10, -0.15, -0.20])
    p.add_argument("--risk-modes", nargs="+", choices=["cash", "reduced_selector", "reduced_static_50_50"], default=["cash", "reduced_selector", "reduced_static_50_50"])
    p.add_argument("--risk-exposures", nargs="+", type=float, default=[0.0, 0.10, 0.25])
    p.add_argument("--release-without-gate", action="store_true")
    p.add_argument("--drawdown-floors", nargs="+", type=float, default=[-50.0, -45.0, -40.0, -35.0])
    p.add_argument("--top-n", type=int, default=25)
    p.add_argument("--crash-start", default="2021-11-01")
    p.add_argument("--crash-end", default="2022-12-31")
    p.add_argument("--bull-start", default="2023-01-01")
    p.add_argument("--bull-end", default="2025-12-30")
    p.add_argument("--recent-start", default="2025-01-01")
    p.add_argument("--recent-end", default="2025-12-30")
    p.add_argument("--out-dir", default="artifacts/btc_eth_relative_strength_risk_budget")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    btc = _load_close(args.btc_data, "BTC", args.start, args.end)
    eth = _load_close(args.eth_data, "ETH", args.start, args.end)
    idx = btc.index.intersection(eth.index).sort_values()
    btc, eth = btc.reindex(idx).dropna(), eth.reindex(idx).dropna()
    idx = btc.index.intersection(eth.index).sort_values()
    btc, eth = btc.reindex(idx), eth.reindex(idx)
    btc_ret, eth_ret = _returns(btc), _returns(eth)

    curves: dict[str, pd.Series] = {}
    rows: list[dict[str, Any]] = []

    # Baselines.
    for label, weights in {"btc_bh": _static_weights(idx, 1.0), "eth_bh": _static_weights(idx, 0.0), "static_btc50_eth50": _static_weights(idx, 0.5)}.items():
        w = weights.shift(0).fillna({"BTC": 0.5, "ETH": 0.5, "cash": 0.0})
        eq = (args.capital * (1.0 + (w["BTC"] * btc_ret + w["ETH"] * eth_ret)).cumprod()).rename(label)
        curves[label] = eq
        row = _metrics(label, eq, args.capital)
        row.update({"crash_return_pct": _window_return(eq, args.crash_start, args.crash_end), "bull_return_pct": _window_return(eq, args.bull_start, args.bull_end), "cash_exposure_pct": float(w["cash"].mean() * 100.0), "risk_state_pct": 0.0, "switch_count": 0})
        rows.append(row)

    for lookback in args.lookbacks:
        for style in args.styles:
            selector = _selector_weights(btc, eth, lookback, style)
            selector["cash"] = 0.0
            for gate in args.gates:
                for sma in args.gate_sma_windows:
                    gate_on = _gate_series(gate, btc, eth, sma)
                    for gate_off_exposure in args.gate_off_exposures:
                        for risk_trigger in args.risk_triggers:
                            for risk_release in args.risk_releases:
                                if risk_release <= risk_trigger:
                                    continue
                                for risk_mode in args.risk_modes:
                                    for risk_exposure in args.risk_exposures:
                                        if risk_mode == "cash" and risk_exposure != 0.0:
                                            continue
                                        if risk_mode != "cash" and risk_exposure <= 0.0:
                                            continue
                                        label = f"rb_{style}_{lookback}d_{gate}{sma}_goff{int(gate_off_exposure*100)}_tr{int(abs(risk_trigger)*100)}_rel{int(abs(risk_release)*100)}_{risk_mode}{int(risk_exposure*100)}"
                                        eq, meta = _simulate(label, btc_ret, eth_ret, selector, gate_on, args.capital, gate_off_exposure, risk_trigger, risk_release, risk_mode, risk_exposure, not args.release_without_gate)
                                        curves[label] = eq
                                        row = _metrics(label, eq, args.capital)
                                        row.update({"crash_return_pct": _window_return(eq, args.crash_start, args.crash_end), "bull_return_pct": _window_return(eq, args.bull_start, args.bull_end), "recent_return_pct": _window_return(eq, args.recent_start, args.recent_end), "lookback": lookback, "style": style, "gate": gate, "sma": sma, "gate_off_exposure": gate_off_exposure, "risk_trigger": risk_trigger, "risk_release": risk_release, "risk_mode": risk_mode, "risk_exposure": risk_exposure, **meta})
                                        rows.append(row)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(curves).to_csv(out / "equity_curves.csv")
    pd.DataFrame(rows).to_csv(out / "results.csv", index=False)
    leaderboard = []
    for floor in args.drawdown_floors:
        for rank, row in enumerate(_rank(_constrained(rows, floor))[: args.top_n], start=1):
            leaderboard.append({"drawdown_floor_pct": floor, "rank": rank, **row})
    pd.DataFrame(leaderboard).to_csv(out / "constrained_leaderboards.csv", index=False)
    (out / "summary.json").write_text(json.dumps({"config": vars(args), "results": rows, "constrained_leaderboards": leaderboard}, indent=2, default=str), encoding="utf-8")
    (out / "summary.md").write_text("# Risk-Budgeted BTC/ETH Relative Strength\n\nResearch-only output. See CSV artifacts for full results.\n", encoding="utf-8")

    print("=" * 162)
    print("  RISK-BUDGETED BTC/ETH RELATIVE STRENGTH — RESEARCH")
    print("=" * 162)
    print(f"  Date range : {args.start} -> {args.end}")
    print(f"  Lookbacks  : {', '.join(str(x) for x in args.lookbacks)}")
    print("-" * 162)
    print("  Top results by Calmar:")
    _print_rows(_rank(rows), args.top_n)
    for floor in args.drawdown_floors:
        print("-" * 162)
        print(f"  Top results by Calmar with MaxDD >= {floor:.0f}%:")
        _print_rows(_rank(_constrained(rows, floor)), args.top_n)
    print("=" * 162)
    print(f"  Summary: {out / 'summary.md'}")
    print(f"  Extra: {out / 'constrained_leaderboards.csv'}")
    print("  Verdict: research output only; review before any integration.\n")


if __name__ == "__main__":
    main()
