#!/usr/bin/env python
"""Research-only state-confirmed risk-off sweep.

Risk-off requires both Fund v1 drawdown pressure and BTC trend confirmation.
This avoids the drawdown-only problem where the system stays defensive for too
much of the sample after a drawdown has already happened.

No runtime, paper-trading, broker, allocator, governor, or Fund v1 behavior is
modified by this script.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from research.harness.data_loader import load_ohlcv, validate_ohlcv
from research.harness.metrics import compute_metrics
from scripts.run_risk_off_trigger_sweep import (
    _buy_hold_curve,
    _load_baseline_cache,
    _normalized_returns,
    _overlay_curve,
    _parse_destinations,
    _passes_guardrails,
    _slice_return,
    _sort_rows,
    _yearly_returns,
)


def _load_close(path: str, asset: str, start: str | None, end: str | None) -> pd.Series:
    df = load_ohlcv(path, start=start, end=end, asset=asset)
    for warning in validate_ohlcv(df):
        print(f"WARNING [{asset}]: {warning}")
    close = pd.to_numeric(df["close"], errors="coerce").dropna()
    close.name = asset
    return close


def _btc_below_sma(btc_close: pd.Series, baseline_index: pd.Index, sma_window: int) -> pd.Series:
    daily = btc_close.resample("1D").last().ffill()
    sma = daily.rolling(sma_window, min_periods=sma_window).mean()
    # prior-day confirmation only; no same-day lookahead
    confirmed = (daily < sma).shift(1).fillna(False)
    return confirmed.reindex(baseline_index).ffill().fillna(False).astype(bool)


def _state_confirmed_risk_off(
    baseline: pd.Series,
    btc_bad: pd.Series,
    trigger_dd: float,
    release_dd: float,
    release_mode: str,
) -> pd.Series:
    dd = baseline / baseline.cummax() - 1.0
    prior_dd = dd.shift(1).fillna(0.0)
    btc_bad = btc_bad.reindex(baseline.index).ffill().fillna(False).astype(bool)

    active = False
    states: list[bool] = []
    for idx, dd_value in prior_dd.items():
        trend_bad = bool(btc_bad.loc[idx])
        if not active and dd_value <= trigger_dd and trend_bad:
            active = True
        elif active:
            dd_recovered = dd_value >= release_dd
            trend_recovered = not trend_bad
            if release_mode == "either" and (dd_recovered or trend_recovered):
                active = False
            elif release_mode == "both" and dd_recovered and trend_recovered:
                active = False
        states.append(active)
    return pd.Series(states, index=baseline.index, name="risk_off")


def _risk_off_destination_return(destination: pd.Series | None, risk_off: pd.Series) -> float | None:
    if destination is None:
        return 0.0
    aligned = pd.DataFrame({"destination": destination, "risk_off": risk_off.astype(bool)}).dropna(how="any")
    active = aligned[aligned["risk_off"]]
    if len(active) < 2:
        return None
    ret = _normalized_returns(aligned["destination"])
    return round(((1.0 + ret.loc[active.index]).prod() - 1.0) * 100.0, 4)


def _row(
    destination_label: str,
    trigger_dd: float,
    release_dd: float,
    crypto_scale: float,
    sma_window: int,
    release_mode: str,
    equity: pd.Series,
    destination: pd.Series | None,
    baseline: pd.Series,
    risk_off: pd.Series,
    baseline_metrics: Any,
    args: argparse.Namespace,
) -> dict[str, Any]:
    metrics = compute_metrics(
        equity,
        trades=[],
        params={"strategy_id": equity.name, "asset": "PORTFOLIO", "initial_capital": args.capital},
    )
    joined = pd.concat([baseline.pct_change(fill_method=None), equity.pct_change(fill_method=None)], axis=1).dropna()
    corr = round(float(joined.iloc[:, 0].corr(joined.iloc[:, 1])), 4) if len(joined) > 2 else None
    risk_off_days = int(risk_off.loc[equity.index].sum()) if set(equity.index).issubset(set(risk_off.index)) else int(risk_off.sum())
    return {
        "destination": destination_label,
        "trigger_dd": trigger_dd,
        "release_dd": release_dd,
        "crypto_scale": crypto_scale,
        "destination_scale": 1.0 - crypto_scale,
        "sma_window": sma_window,
        "release_mode": release_mode,
        "cagr_pct": metrics.cagr_pct,
        "max_drawdown_pct": metrics.max_drawdown_pct,
        "sharpe": metrics.sharpe,
        "calmar": metrics.calmar,
        "stress_return_pct": _slice_return(equity, args.stress_start, args.stress_end),
        "risk_off_days": risk_off_days,
        "risk_off_pct_days": round(risk_off_days / max(len(equity), 1) * 100.0, 2),
        "destination_risk_off_return_pct": _risk_off_destination_return(destination, risk_off),
        "corr_to_baseline": corr,
        "delta_cagr_vs_baseline": metrics.cagr_pct - baseline_metrics.cagr_pct,
        "delta_maxdd_vs_baseline": metrics.max_drawdown_pct - baseline_metrics.max_drawdown_pct,
        "delta_sharpe_vs_baseline": metrics.sharpe - baseline_metrics.sharpe,
        "delta_calmar_vs_baseline": metrics.calmar - baseline_metrics.calmar,
        "yearly_returns_pct": _yearly_returns(equity),
    }


def _write_outputs(rows: list[dict[str, Any]], out_dir: Path, args: argparse.Namespace) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    sorted_rows = _sort_rows(rows, args)
    flat = [{**r, "yearly_returns_pct": json.dumps(r["yearly_returns_pct"], sort_keys=True)} for r in sorted_rows]
    pd.DataFrame(flat).to_csv(out_dir / "state_confirmed_sweep_summary.csv", index=False)
    with open(out_dir / "state_confirmed_sweep_summary.json", "w", encoding="utf-8") as f:
        json.dump(sorted_rows, f, indent=2, default=str)

    md = out_dir / "state_confirmed_sweep_summary.md"
    with open(md, "w", encoding="utf-8") as f:
        f.write("# State-Confirmed Risk-Off Sweep Summary\n\n")
        f.write("Drawdown plus BTC trend confirmation.\n\n")
        f.write("| Dest | Trigger | Release | SMA | Mode | Crypto | CAGR | MaxDD | Sharpe | Calmar | Stress | RiskOff | dCalmar | Pass |\n")
        f.write("|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|\n")
        for r in sorted_rows[: args.report_top_n]:
            stress = "n/a" if r["stress_return_pct"] is None else f"{r['stress_return_pct']:.2f}%"
            f.write(
                f"| {r['destination']} | {r['trigger_dd']:.0%} | {r['release_dd']:.0%} | {r['sma_window']} | "
                f"{r['release_mode']} | {r['crypto_scale']:.0%} | {r['cagr_pct']:.2f}% | "
                f"{r['max_drawdown_pct']:.2f}% | {r['sharpe']:.3f} | {r['calmar']:.3f} | {stress} | "
                f"{r['risk_off_pct_days']:.1f}% | {r['delta_calmar_vs_baseline']:.3f} | "
                f"{'YES' if _passes_guardrails(r, args) else 'NO'} |\n"
            )
    return md


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Research-only state-confirmed risk-off sweep")
    p.add_argument("--baseline-cache", required=True)
    p.add_argument("--btc-daily", required=True)
    p.add_argument("--destination", action="append", default=[])
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--trigger-dds", nargs="+", type=float, default=[-0.10, -0.15, -0.20, -0.25, -0.30])
    p.add_argument("--release-dds", nargs="+", type=float, default=[-0.03, -0.05, -0.10, -0.15])
    p.add_argument("--crypto-scales", nargs="+", type=float, default=[0.0, 0.25, 0.50, 0.65, 0.75, 0.85])
    p.add_argument("--sma-windows", nargs="+", type=int, default=[100, 200, 365])
    p.add_argument("--release-modes", nargs="+", choices=["either", "both"], default=["either"])
    p.add_argument("--stress-start", default="2022-01-01")
    p.add_argument("--stress-end", default="2022-12-31")
    p.add_argument("--min-calmar", type=float, default=1.15)
    p.add_argument("--min-risk-off-pct", type=float, default=5.0)
    p.add_argument("--max-risk-off-pct", type=float, default=30.0)
    p.add_argument("--max-allowed-drawdown", type=float, default=-0.30)
    p.add_argument("--report-top-n", type=int, default=40)
    p.add_argument("--out-dir", default="artifacts/state_confirmed_risk_off_sweep")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    baseline = _load_baseline_cache(args.baseline_cache)
    baseline_metrics = compute_metrics(baseline, trades=[], params={"strategy_id": "baseline", "asset": "PORTFOLIO", "initial_capital": args.capital})
    btc_close = _load_close(args.btc_daily, "BTC", args.start, args.end)

    destinations: dict[str, pd.Series | None] = {"cash": None}
    for ticker, path in _parse_destinations(args.destination).items():
        destinations[ticker.lower()] = _buy_hold_curve(path, ticker, args.capital, args.start, args.end)

    confirms = {window: _btc_below_sma(btc_close, baseline.index, window) for window in args.sma_windows}
    rows: list[dict[str, Any]] = []

    for sma_window, btc_bad in confirms.items():
        for release_mode in args.release_modes:
            for trigger_dd in args.trigger_dds:
                for release_dd in args.release_dds:
                    if release_dd <= trigger_dd:
                        continue
                    risk_off = _state_confirmed_risk_off(baseline, btc_bad, trigger_dd, release_dd, release_mode)
                    for crypto_scale in args.crypto_scales:
                        for dest_label, dest_curve in destinations.items():
                            label = f"{dest_label}_trig{int(abs(trigger_dd)*100)}_rel{int(abs(release_dd)*100)}_sma{sma_window}_{release_mode}_cs{int(crypto_scale*100)}"
                            equity = _overlay_curve(baseline, dest_curve, risk_off, crypto_scale, args.capital, label)
                            rows.append(_row(dest_label, trigger_dd, release_dd, crypto_scale, sma_window, release_mode, equity, dest_curve, baseline, risk_off, baseline_metrics, args))

    summary = _write_outputs(rows, Path(args.out_dir), args)
    sorted_rows = _sort_rows(rows, args)

    print("=" * 164)
    print("  STATE-CONFIRMED RISK-OFF SWEEP — TOP RESULTS")
    print("=" * 164)
    print(f"  {'Dest':<8} {'Trig':>7} {'Rel':>7} {'SMA':>5} {'Mode':>6} {'Crypto':>7} {'CAGR%':>9} {'MaxDD%':>9} {'Sharpe':>8} {'Calmar':>8} {'Stress%':>9} {'RiskOff':>8} {'dCalmar':>8} {'Pass':>6}")
    print("  " + "-" * 162)
    for r in sorted_rows[: args.report_top_n]:
        stress = "n/a" if r["stress_return_pct"] is None else f"{r['stress_return_pct']:>8.2f}%"
        print(f"  {r['destination']:<8} {r['trigger_dd']:>6.0%} {r['release_dd']:>6.0%} {r['sma_window']:>5} {r['release_mode']:>6} {r['crypto_scale']:>6.0%} {r['cagr_pct']:>8.2f}% {r['max_drawdown_pct']:>8.2f}% {r['sharpe']:>8.3f} {r['calmar']:>8.3f} {stress:>9} {r['risk_off_pct_days']:>7.1f}% {r['delta_calmar_vs_baseline']:>8.3f} {('YES' if _passes_guardrails(r, args) else 'NO'):>6}")
    print("=" * 164)
    print(f"  Summary: {summary}")
    print("  Verdict: research output only; review before any integration.\n")


if __name__ == "__main__":
    main()
