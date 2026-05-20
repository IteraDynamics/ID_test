#!/usr/bin/env python
"""Research-only transition/cost review for state-confirmed allocator candidates.

This script evaluates practical capital movement for a selected state-confirmed
risk-off destination rule. It estimates entry/exit events, turnover, and
friction-adjusted performance.

Default target is the current leading candidate:
- destination: GLD
- trigger_dd: -18%
- release_dd: -12%
- BTC SMA: 200
- release_mode: either
- crypto_scale: 0%

No runtime, paper-trading, broker, allocator, governor, or Fund v1 behavior is
modified by this script.
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
from scripts.run_risk_off_trigger_sweep import (
    _buy_hold_curve,
    _load_baseline_cache,
    _overlay_curve,
)
from scripts.run_state_confirmed_risk_off_sweep import (
    _btc_below_sma,
    _load_close,
    _state_confirmed_risk_off,
)


def _fmt_pct(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if math.isnan(v):
        return "n/a"
    return f"{v:.2f}%"


def _fmt_money(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if math.isnan(v):
        return "n/a"
    return f"${v:,.2f}"


def _risk_off_transitions(risk_off: pd.Series) -> pd.DataFrame:
    state = risk_off.astype(bool)
    prev = state.shift(1).fillna(False).astype(bool)
    entries = state & ~prev
    exits = ~state & prev
    rows: list[dict[str, Any]] = []
    for ts in state.index[entries]:
        rows.append({"timestamp": ts, "event": "enter_risk_off"})
    for ts in state.index[exits]:
        rows.append({"timestamp": ts, "event": "exit_risk_off"})
    out = pd.DataFrame(rows)
    if out.empty:
        return pd.DataFrame(columns=["timestamp", "event"])
    return out.sort_values("timestamp").reset_index(drop=True)


def _target_destination_weight(risk_off: pd.Series, crypto_scale: float) -> pd.Series:
    # During normal state destination weight is 0. During risk-off it is the
    # displaced crypto allocation, i.e. 1 - crypto_scale.
    return risk_off.astype(float) * (1.0 - crypto_scale)


def _turnover_table(
    overlay: pd.Series,
    risk_off: pd.Series,
    crypto_scale: float,
    destination_label: str,
    total_friction_bps: float,
) -> pd.DataFrame:
    target_dest_weight = _target_destination_weight(risk_off, crypto_scale).reindex(overlay.index).ffill().fillna(0.0)
    prev_weight = target_dest_weight.shift(1).fillna(0.0)
    weight_change = (target_dest_weight - prev_weight).abs()
    event_rows = weight_change[weight_change > 0]

    rows: list[dict[str, Any]] = []
    for ts, weight_delta in event_rows.items():
        nav = float(overlay.loc[ts])
        notional = nav * float(weight_delta)
        friction = notional * (total_friction_bps / 10_000.0)
        event = "enter_risk_off" if target_dest_weight.loc[ts] > prev_weight.loc[ts] else "exit_risk_off"
        rows.append(
            {
                "timestamp": ts,
                "event": event,
                "destination": destination_label,
                "prev_destination_weight": round(float(prev_weight.loc[ts]), 6),
                "new_destination_weight": round(float(target_dest_weight.loc[ts]), 6),
                "weight_delta": round(float(weight_delta), 6),
                "nav_before_cost": round(nav, 4),
                "notional_turned_over": round(notional, 4),
                "friction_bps": total_friction_bps,
                "estimated_friction_cost": round(friction, 4),
            }
        )
    return pd.DataFrame(rows)


def _apply_transition_costs(overlay: pd.Series, turnover: pd.DataFrame) -> pd.Series:
    if turnover.empty:
        out = overlay.copy()
        out.name = "cost_adjusted_overlay"
        return out

    costs = turnover.groupby("timestamp")["estimated_friction_cost"].sum()
    cost_units = pd.Series(0.0, index=overlay.index)
    for ts, cost in costs.items():
        if ts in cost_units.index:
            cost_units.loc[ts] += float(cost)

    # Convert fixed dollar costs into daily return drags on the previous NAV.
    rets = overlay.pct_change(fill_method=None).fillna(0.0)
    adjusted = [float(overlay.iloc[0])]
    for i in range(1, len(overlay)):
        prev_nav = adjusted[-1]
        nav = prev_nav * (1.0 + float(rets.iloc[i]))
        nav -= float(cost_units.iloc[i])
        adjusted.append(max(nav, 0.0))
    out = pd.Series(adjusted, index=overlay.index, name="cost_adjusted_overlay")
    return out


def _slice_return(equity: pd.Series, start: str, end: str) -> float | None:
    s = equity.loc[(equity.index >= pd.Timestamp(start)) & (equity.index <= pd.Timestamp(end))].dropna()
    if len(s) < 2:
        return None
    return (float(s.iloc[-1]) / float(s.iloc[0]) - 1.0) * 100.0


def _summary_row(
    label: str,
    equity: pd.Series,
    args: argparse.Namespace,
    baseline_metrics: Any,
    total_cost: float,
    transition_count: int,
    gross_turnover_notional: float,
) -> dict[str, Any]:
    metrics = compute_metrics(equity, trades=[], params={"strategy_id": label, "asset": "PORTFOLIO", "initial_capital": args.capital})
    return {
        "label": label,
        "cagr_pct": metrics.cagr_pct,
        "max_drawdown_pct": metrics.max_drawdown_pct,
        "sharpe": metrics.sharpe,
        "calmar": metrics.calmar,
        "stress_return_pct": _slice_return(equity, args.stress_start, args.stress_end),
        "delta_cagr_vs_baseline": metrics.cagr_pct - baseline_metrics.cagr_pct,
        "delta_maxdd_vs_baseline": metrics.max_drawdown_pct - baseline_metrics.max_drawdown_pct,
        "delta_sharpe_vs_baseline": metrics.sharpe - baseline_metrics.sharpe,
        "delta_calmar_vs_baseline": metrics.calmar - baseline_metrics.calmar,
        "transition_count": transition_count,
        "gross_turnover_notional": gross_turnover_notional,
        "estimated_total_friction_cost": total_cost,
    }


def _write_outputs(
    args: argparse.Namespace,
    summary_rows: list[dict[str, Any]],
    turnover: pd.DataFrame,
    curves: pd.DataFrame,
    risk_off: pd.Series,
) -> Path:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(summary_rows).to_csv(out_dir / "transition_cost_summary.csv", index=False)
    turnover.to_csv(out_dir / "transition_events.csv", index=False)
    curves.to_csv(out_dir / "transition_cost_equity_curves.csv")
    risk_off.astype(int).to_csv(out_dir / "risk_off_state.csv", header=True)

    with open(out_dir / "transition_cost_review.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "config": vars(args),
                "summary": summary_rows,
                "transition_events": turnover.to_dict("records"),
            },
            f,
            indent=2,
            default=str,
        )

    md = out_dir / "transition_cost_review.md"
    with open(md, "w", encoding="utf-8") as f:
        f.write("# State-Confirmed Transition / Cost Review\n\n")
        f.write("Research-only CFO-style review for one state-confirmed allocator candidate.\n\n")
        f.write("## Candidate\n\n")
        f.write(f"- Destination: `{args.destination_label}`\n")
        f.write(f"- Trigger / release: `{args.trigger_dd:.0%}` / `{args.release_dd:.0%}`\n")
        f.write(f"- BTC SMA window: `{args.btc_sma_window}`\n")
        f.write(f"- Release mode: `{args.release_mode}`\n")
        f.write(f"- Crypto scale while risk-off: `{args.crypto_scale:.0%}`\n")
        f.write(f"- Total friction assumption: `{args.total_friction_bps:.2f}` bps per transition notional\n\n")

        f.write("## Summary\n\n")
        f.write("| Label | CAGR | MaxDD | Sharpe | Calmar | Stress | Transitions | Turnover | Cost | dCalmar vs Base |\n")
        f.write("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n")
        for r in summary_rows:
            f.write(
                f"| {r['label']} | {_fmt_pct(r['cagr_pct'])} | {_fmt_pct(r['max_drawdown_pct'])} | "
                f"{r['sharpe']:.3f} | {r['calmar']:.3f} | {_fmt_pct(r['stress_return_pct'])} | "
                f"{r['transition_count']} | {_fmt_money(r['gross_turnover_notional'])} | "
                f"{_fmt_money(r['estimated_total_friction_cost'])} | {r['delta_calmar_vs_baseline']:.3f} |\n"
            )

        f.write("\n## Transition Events\n\n")
        if turnover.empty:
            f.write("No destination weight transition events detected.\n")
        else:
            f.write("| # | Date | Event | New Dest Wt | Notional | Cost |\n")
            f.write("|---:|---|---|---:|---:|---:|\n")
            for i, row in enumerate(turnover.to_dict("records"), start=1):
                f.write(
                    f"| {i} | {pd.Timestamp(row['timestamp']).date().isoformat()} | {row['event']} | "
                    f"{float(row['new_destination_weight']):.0%} | {_fmt_money(row['notional_turned_over'])} | "
                    f"{_fmt_money(row['estimated_friction_cost'])} |\n"
                )
    return md


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Research-only transition/cost review for state-confirmed allocator candidate")
    p.add_argument("--baseline-cache", required=True)
    p.add_argument("--btc-daily", required=True)
    p.add_argument("--destination", required=True, help="Destination in TICKER=path form")
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--trigger-dd", type=float, default=-0.18)
    p.add_argument("--release-dd", type=float, default=-0.12)
    p.add_argument("--crypto-scale", type=float, default=0.0)
    p.add_argument("--btc-sma-window", type=int, default=200)
    p.add_argument("--release-mode", choices=["either", "both"], default="either")
    p.add_argument("--total-friction-bps", type=float, default=10.0, help="Round-trip style total bps applied to each changed notional")
    p.add_argument("--stress-start", default="2022-01-01")
    p.add_argument("--stress-end", default="2022-12-31")
    p.add_argument("--out-dir", default="artifacts/state_confirmed_transition_cost_review")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if "=" not in args.destination:
        raise ValueError("--destination must be TICKER=path")
    args.destination_label, dest_path = args.destination.split("=", 1)
    args.destination_label = args.destination_label.strip().upper()
    dest_path = dest_path.strip()

    baseline = _load_baseline_cache(args.baseline_cache)
    btc_close = _load_close(args.btc_daily, "BTC", args.start, args.end)
    destination = _buy_hold_curve(dest_path, args.destination_label, args.capital, args.start, args.end)
    btc_bad = _btc_below_sma(btc_close, baseline.index, args.btc_sma_window)
    risk_off = _state_confirmed_risk_off(baseline, btc_bad, args.trigger_dd, args.release_dd, args.release_mode)
    overlay = _overlay_curve(baseline, destination, risk_off, args.crypto_scale, args.capital, "pre_cost_overlay")

    turnover = _turnover_table(overlay, risk_off, args.crypto_scale, args.destination_label, args.total_friction_bps)
    cost_adjusted = _apply_transition_costs(overlay, turnover)

    total_cost = float(turnover["estimated_friction_cost"].sum()) if not turnover.empty else 0.0
    gross_turnover = float(turnover["notional_turned_over"].sum()) if not turnover.empty else 0.0
    transition_count = int(len(turnover))
    baseline_metrics = compute_metrics(baseline, trades=[], params={"strategy_id": "baseline", "asset": "PORTFOLIO", "initial_capital": args.capital})

    rows = [
        _summary_row("baseline", baseline, args, baseline_metrics, 0.0, 0, 0.0),
        _summary_row("pre_cost_overlay", overlay, args, baseline_metrics, 0.0, transition_count, gross_turnover),
        _summary_row("cost_adjusted_overlay", cost_adjusted, args, baseline_metrics, total_cost, transition_count, gross_turnover),
    ]

    curves = pd.DataFrame(
        {
            "baseline": baseline,
            args.destination_label.lower(): destination,
            "pre_cost_overlay": overlay,
            "cost_adjusted_overlay": cost_adjusted,
        }
    ).dropna(how="all")

    md = _write_outputs(args, rows, turnover, curves, risk_off)

    print("=" * 132)
    print("  STATE-CONFIRMED TRANSITION / COST REVIEW")
    print("=" * 132)
    print(f"  Destination      : {args.destination_label}")
    print(f"  Trigger / Release: {args.trigger_dd:.0%} / {args.release_dd:.0%}")
    print(f"  BTC trend filter : SMA{args.btc_sma_window}, release={args.release_mode}")
    print(f"  Crypto scale     : {args.crypto_scale:.0%}")
    print(f"  Friction         : {args.total_friction_bps:.2f} bps per changed notional")
    print("-" * 132)
    for row in rows:
        print(
            f"  {row['label']:<22} CAGR={row['cagr_pct']:>7.2f}%  MaxDD={row['max_drawdown_pct']:>7.2f}%  "
            f"Sharpe={row['sharpe']:>6.3f}  Calmar={row['calmar']:>6.3f}  "
            f"Cost={_fmt_money(row['estimated_total_friction_cost']):>12}"
        )
    print("-" * 132)
    print(f"  Transitions      : {transition_count}")
    print(f"  Gross turnover   : {_fmt_money(gross_turnover)}")
    print(f"  Estimated cost   : {_fmt_money(total_cost)}")
    print("=" * 132)
    print(f"  Summary: {md}")
    print("  Verdict: research output only; review before any integration.\n")


if __name__ == "__main__":
    main()
