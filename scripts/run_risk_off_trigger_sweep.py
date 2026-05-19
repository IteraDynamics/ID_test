#!/usr/bin/env python
"""Research-only risk-off trigger sweep runner.

Sweeps defensive trigger/release/crypto-scale parameters for a small set of
serious capital destinations. This script is designed to answer whether the
risk-off state detector can materially improve Fund v1 portfolio quality.

Default focus:
- cash
- BIL
- GLD

This is Layer 3 governor / capital destination research. It does not modify
runtime, paper trading, brokers, allocators, governors, or Fund v1 behavior.
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
from research.harness.metrics import BacktestMetrics, compute_metrics


def _load_baseline_cache(path: str) -> pd.Series:
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    if "baseline" not in df.columns:
        raise ValueError(f"Baseline cache must include a 'baseline' column: {path}")
    baseline = pd.to_numeric(df["baseline"], errors="coerce").dropna()
    baseline.name = "baseline"
    if len(baseline) < 2:
        raise ValueError(f"Baseline cache has insufficient rows: {path}")
    return baseline


def _parse_destinations(raw: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in raw:
        if "=" not in item:
            raise ValueError(f"Destination must be TICKER=path, got {item!r}")
        ticker, path = item.split("=", 1)
        ticker = ticker.strip().upper()
        path = path.strip()
        if not ticker or not path:
            raise ValueError(f"Destination must be TICKER=path, got {item!r}")
        out[ticker] = path
    return out


def _buy_hold_curve(path: str, ticker: str, capital: float, start: str | None, end: str | None) -> pd.Series:
    df = load_ohlcv(path, start=start, end=end, asset=ticker)
    for warning in validate_ohlcv(df):
        print(f"WARNING [{ticker}]: {warning}")
    close = pd.to_numeric(df["close"], errors="coerce").dropna()
    curve = capital * (close / float(close.iloc[0]))
    curve.name = ticker
    return curve


def _normalized_returns(equity: pd.Series) -> pd.Series:
    return equity.pct_change(fill_method=None).fillna(0.0)


def _risk_off_state(baseline: pd.Series, trigger_dd: float, release_dd: float) -> pd.Series:
    dd = baseline / baseline.cummax() - 1.0
    prior_dd = dd.shift(1).fillna(0.0)
    active = False
    states = []
    for value in prior_dd:
        if not active and value <= trigger_dd:
            active = True
        elif active and value >= release_dd:
            active = False
        states.append(active)
    return pd.Series(states, index=baseline.index, name="risk_off")


def _overlay_curve(
    baseline: pd.Series,
    destination: pd.Series | None,
    risk_off: pd.Series,
    crypto_scale: float,
    capital: float,
    label: str,
) -> pd.Series:
    aligned = pd.DataFrame({"baseline": baseline, "risk_off": risk_off.astype(float)})
    if destination is not None:
        aligned["destination"] = destination
    aligned = aligned.dropna(how="any")

    crypto_ret = _normalized_returns(aligned["baseline"])
    if destination is None:
        dest_ret = pd.Series(0.0, index=aligned.index)
    else:
        dest_ret = _normalized_returns(aligned["destination"])

    active = aligned["risk_off"].astype(bool)
    weight_crypto = pd.Series(1.0, index=aligned.index)
    weight_dest = pd.Series(0.0, index=aligned.index)
    weight_crypto.loc[active] = crypto_scale
    weight_dest.loc[active] = 1.0 - crypto_scale

    portfolio_ret = weight_crypto * crypto_ret + weight_dest * dest_ret
    equity = capital * (1.0 + portfolio_ret).cumprod()
    equity.name = label
    return equity


def _slice_return(equity: pd.Series, start: str, end: str) -> float | None:
    s = equity.loc[(equity.index >= pd.Timestamp(start)) & (equity.index <= pd.Timestamp(end))].dropna()
    if len(s) < 2:
        return None
    return round((float(s.iloc[-1]) / float(s.iloc[0]) - 1.0) * 100.0, 4)


def _risk_off_destination_return(destination: pd.Series | None, risk_off: pd.Series) -> float | None:
    if destination is None:
        return 0.0
    aligned = pd.DataFrame({"destination": destination, "risk_off": risk_off.astype(bool)}).dropna(how="any")
    active = aligned[aligned["risk_off"]]
    if len(active) < 2:
        return None
    ret = _normalized_returns(aligned["destination"])
    active_rets = ret.loc[active.index]
    return round(((1.0 + active_rets).prod() - 1.0) * 100.0, 4)


def _yearly_returns(equity: pd.Series) -> dict[str, float]:
    out: dict[str, float] = {}
    clean = equity.dropna()
    for year, group in clean.groupby(clean.index.year):
        if len(group) < 2:
            continue
        out[str(year)] = round((float(group.iloc[-1]) / float(group.iloc[0]) - 1.0) * 100.0, 4)
    return out


def _row(
    destination_label: str,
    trigger_dd: float,
    release_dd: float,
    crypto_scale: float,
    equity: pd.Series,
    destination: pd.Series | None,
    metrics: BacktestMetrics,
    baseline: pd.Series,
    risk_off: pd.Series,
    baseline_metrics: BacktestMetrics,
    args: argparse.Namespace,
) -> dict[str, Any]:
    joined = pd.concat([baseline.pct_change(fill_method=None), equity.pct_change(fill_method=None)], axis=1).dropna()
    corr = round(float(joined.iloc[:, 0].corr(joined.iloc[:, 1])), 4) if len(joined) > 2 else None
    risk_off_days = int(risk_off.loc[equity.index].sum()) if set(equity.index).issubset(set(risk_off.index)) else int(risk_off.sum())
    risk_off_pct = round(risk_off_days / max(len(equity), 1) * 100.0, 2)
    return {
        "destination": destination_label,
        "trigger_dd": trigger_dd,
        "release_dd": release_dd,
        "crypto_scale": crypto_scale,
        "destination_scale": 1.0 - crypto_scale,
        "cagr_pct": metrics.cagr_pct,
        "max_drawdown_pct": metrics.max_drawdown_pct,
        "sharpe": metrics.sharpe,
        "calmar": metrics.calmar,
        "stress_return_pct": _slice_return(equity, args.stress_start, args.stress_end),
        "risk_off_days": risk_off_days,
        "risk_off_pct_days": risk_off_pct,
        "destination_risk_off_return_pct": _risk_off_destination_return(destination, risk_off),
        "corr_to_baseline": corr,
        "delta_cagr_vs_baseline": metrics.cagr_pct - baseline_metrics.cagr_pct,
        "delta_maxdd_vs_baseline": metrics.max_drawdown_pct - baseline_metrics.max_drawdown_pct,
        "delta_sharpe_vs_baseline": metrics.sharpe - baseline_metrics.sharpe,
        "delta_calmar_vs_baseline": metrics.calmar - baseline_metrics.calmar,
        "yearly_returns_pct": _yearly_returns(equity),
    }


def _passes_guardrails(row: dict[str, Any], args: argparse.Namespace) -> bool:
    return (
        row["calmar"] >= args.min_calmar
        and row["risk_off_pct_days"] <= args.max_risk_off_pct
        and row["risk_off_pct_days"] >= args.min_risk_off_pct
        and row["max_drawdown_pct"] >= args.max_allowed_drawdown
    )


def _sort_rows(rows: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda r: (
            _passes_guardrails(r, args),
            r["calmar"],
            r["sharpe"],
            r["max_drawdown_pct"],
            r["cagr_pct"],
        ),
        reverse=True,
    )


def _write_outputs(rows: list[dict[str, Any]], out_dir: Path, args: argparse.Namespace) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    sorted_rows = _sort_rows(rows, args)
    flat = [{**r, "yearly_returns_pct": json.dumps(r["yearly_returns_pct"], sort_keys=True)} for r in sorted_rows]
    pd.DataFrame(flat).to_csv(out_dir / "sweep_summary.csv", index=False)
    with open(out_dir / "sweep_summary.json", "w", encoding="utf-8") as f:
        json.dump(sorted_rows, f, indent=2, default=str)

    md = out_dir / "sweep_summary.md"
    with open(md, "w", encoding="utf-8") as f:
        f.write("# Risk-Off Trigger Sweep Summary\n\n")
        f.write("Research-only Layer 3 trigger/release/scale sweep. Rows are sorted by guardrail pass, Calmar, Sharpe, MaxDD, and CAGR.\n\n")
        f.write("## Guardrails\n\n")
        f.write(f"- Minimum Calmar: `{args.min_calmar}`\n")
        f.write(f"- Risk-off active range: `{args.min_risk_off_pct}%` to `{args.max_risk_off_pct}%` of days\n")
        f.write(f"- Max allowed drawdown: `{args.max_allowed_drawdown:.0%}`\n\n")
        f.write("| Dest | Trigger | Release | Crypto Scale | CAGR | MaxDD | Sharpe | Calmar | Stress | RiskOff | dCalmar | Pass |\n")
        f.write("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|\n")
        for r in sorted_rows[: args.report_top_n]:
            stress = "n/a" if r["stress_return_pct"] is None else f"{r['stress_return_pct']:.2f}%"
            f.write(
                f"| {r['destination']} | {r['trigger_dd']:.0%} | {r['release_dd']:.0%} | {r['crypto_scale']:.0%} | "
                f"{r['cagr_pct']:.2f}% | {r['max_drawdown_pct']:.2f}% | {r['sharpe']:.3f} | {r['calmar']:.3f} | "
                f"{stress} | {r['risk_off_pct_days']:.1f}% | {r['delta_calmar_vs_baseline']:.3f} | "
                f"{'YES' if _passes_guardrails(r, args) else 'NO'} |\n"
            )
    return md


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Research-only risk-off trigger sweep runner")
    p.add_argument("--baseline-cache", required=True)
    p.add_argument("--destination", action="append", default=[], help="Destination in TICKER=path form. Repeatable. Cash is always included.")
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--trigger-dds", nargs="+", type=float, default=[-0.10, -0.15, -0.20, -0.25, -0.30])
    p.add_argument("--release-dds", nargs="+", type=float, default=[-0.03, -0.05, -0.10, -0.15])
    p.add_argument("--crypto-scales", nargs="+", type=float, default=[0.0, 0.25, 0.50, 0.65, 0.75, 0.85])
    p.add_argument("--stress-start", default="2022-01-01")
    p.add_argument("--stress-end", default="2022-12-31")
    p.add_argument("--min-calmar", type=float, default=1.15)
    p.add_argument("--min-risk-off-pct", type=float, default=5.0)
    p.add_argument("--max-risk-off-pct", type=float, default=30.0)
    p.add_argument("--max-allowed-drawdown", type=float, default=-0.30)
    p.add_argument("--report-top-n", type=int, default=40)
    p.add_argument("--out-dir", default="artifacts/risk_off_trigger_sweep")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    baseline = _load_baseline_cache(args.baseline_cache)
    baseline_metrics = compute_metrics(
        baseline,
        trades=[],
        params={"strategy_id": "baseline", "asset": "PORTFOLIO", "initial_capital": args.capital},
    )

    destination_paths = _parse_destinations(args.destination)
    destinations: dict[str, pd.Series | None] = {"cash": None}
    for ticker, path in destination_paths.items():
        destinations[ticker.lower()] = _buy_hold_curve(path, ticker, args.capital, args.start, args.end)

    print("\nRisk-Off Trigger Sweep Runner")
    print("Role: Layer 3 governor / capital destination research")
    print("Runtime impact: none")
    print("Fund v1 paper-trading impact: none")
    print(f"Baseline cache: {args.baseline_cache}")
    print(f"Baseline: CAGR={baseline_metrics.cagr_pct:.2f}% MaxDD={baseline_metrics.max_drawdown_pct:.2f}% Sharpe={baseline_metrics.sharpe:.3f} Calmar={baseline_metrics.calmar:.3f}")
    print(f"Destinations: {', '.join(destinations.keys())}")
    print(f"Grid size: {len(args.trigger_dds) * len(args.release_dds) * len(args.crypto_scales) * len(destinations)} rows\n")

    rows: list[dict[str, Any]] = []
    for trigger_dd in args.trigger_dds:
        for release_dd in args.release_dds:
            if release_dd <= trigger_dd:
                continue
            risk_off = _risk_off_state(baseline, trigger_dd, release_dd)
            for crypto_scale in args.crypto_scales:
                for destination_label, destination_curve in destinations.items():
                    label = f"{destination_label}_trig{int(abs(trigger_dd) * 100)}_rel{int(abs(release_dd) * 100)}_cs{int(crypto_scale * 100)}"
                    equity = _overlay_curve(
                        baseline=baseline,
                        destination=destination_curve,
                        risk_off=risk_off,
                        crypto_scale=crypto_scale,
                        capital=args.capital,
                        label=label,
                    )
                    metrics = compute_metrics(
                        equity,
                        trades=[],
                        params={"strategy_id": label, "asset": "PORTFOLIO", "initial_capital": args.capital},
                    )
                    rows.append(
                        _row(
                            destination_label=destination_label,
                            trigger_dd=trigger_dd,
                            release_dd=release_dd,
                            crypto_scale=crypto_scale,
                            equity=equity,
                            destination=destination_curve,
                            metrics=metrics,
                            baseline=baseline,
                            risk_off=risk_off,
                            baseline_metrics=baseline_metrics,
                            args=args,
                        )
                    )

    summary = _write_outputs(rows, Path(args.out_dir), args)
    sorted_rows = _sort_rows(rows, args)

    print("=" * 144)
    print("  RISK-OFF TRIGGER SWEEP — TOP RESULTS")
    print("=" * 144)
    print(
        f"  {'Dest':<8} {'Trig':>7} {'Rel':>7} {'Crypto':>7} {'CAGR%':>9} {'MaxDD%':>9} "
        f"{'Sharpe':>8} {'Calmar':>8} {'Stress%':>9} {'RiskOff':>8} {'dCalmar':>8} {'Pass':>6}"
    )
    print("  " + "-" * 142)
    for r in sorted_rows[: args.report_top_n]:
        stress = "n/a" if r["stress_return_pct"] is None else f"{r['stress_return_pct']:>8.2f}%"
        print(
            f"  {r['destination']:<8} {r['trigger_dd']:>6.0%} {r['release_dd']:>6.0%} {r['crypto_scale']:>6.0%} "
            f"{r['cagr_pct']:>8.2f}% {r['max_drawdown_pct']:>8.2f}% {r['sharpe']:>8.3f} {r['calmar']:>8.3f} "
            f"{stress:>9} {r['risk_off_pct_days']:>7.1f}% {r['delta_calmar_vs_baseline']:>8.3f} "
            f"{('YES' if _passes_guardrails(r, args) else 'NO'):>6}"
        )
    print("=" * 144)
    print(f"  Summary: {summary}")
    print("  Verdict: research output only; review before any integration.\n")


if __name__ == "__main__":
    main()
