#!/usr/bin/env python
"""Research-only GLD/BIL destination blend review.

This script evaluates blended capital destinations during a selected
state-confirmed risk-off allocator rule. It is designed to answer whether a
GLD/BIL blend can preserve much of GLD's upside while reducing destination risk.

Default candidate rule:
- trigger_dd: -18%
- release_dd: -12%
- BTC SMA: 200
- release_mode: either
- crypto_scale: 0%

Default destinations:
- GLD path supplied via --gld-data
- BIL path supplied via --bil-data

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
    _normalized_returns,
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


def _slice_return(equity: pd.Series, start: str, end: str) -> float | None:
    s = equity.loc[(equity.index >= pd.Timestamp(start)) & (equity.index <= pd.Timestamp(end))].dropna()
    if len(s) < 2:
        return None
    return (float(s.iloc[-1]) / float(s.iloc[0]) - 1.0) * 100.0


def _blend_destination_curve(
    gld: pd.Series,
    bil: pd.Series,
    gld_weight: float,
    capital: float,
    label: str,
) -> pd.Series:
    bil_weight = 1.0 - gld_weight
    aligned = pd.DataFrame({"gld": gld, "bil": bil}).dropna(how="any")
    rets = aligned.pct_change(fill_method=None).fillna(0.0)
    blend_rets = gld_weight * rets["gld"] + bil_weight * rets["bil"]
    curve = capital * (1.0 + blend_rets).cumprod()
    curve.name = label
    return curve


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


def _destination_weight(risk_off: pd.Series, crypto_scale: float, overlay_index: pd.Index) -> pd.Series:
    return (risk_off.astype(float) * (1.0 - crypto_scale)).reindex(overlay_index).ffill().fillna(0.0)


def _transition_cost_table(
    overlay: pd.Series,
    risk_off: pd.Series,
    crypto_scale: float,
    gld_weight: float,
    total_friction_bps: float,
    label: str,
) -> pd.DataFrame:
    target_dest_weight = _destination_weight(risk_off, crypto_scale, overlay.index)
    target_gld_weight = target_dest_weight * gld_weight
    target_bil_weight = target_dest_weight * (1.0 - gld_weight)

    prev_gld = target_gld_weight.shift(1).fillna(0.0)
    prev_bil = target_bil_weight.shift(1).fillna(0.0)
    gld_delta = (target_gld_weight - prev_gld).abs()
    bil_delta = (target_bil_weight - prev_bil).abs()
    total_delta = gld_delta + bil_delta

    rows: list[dict[str, Any]] = []
    for ts in overlay.index[total_delta > 0]:
        nav = float(overlay.loc[ts])
        notional = nav * float(total_delta.loc[ts])
        friction = notional * (total_friction_bps / 10_000.0)
        event = "enter_risk_off" if target_dest_weight.loc[ts] > target_dest_weight.shift(1).fillna(0.0).loc[ts] else "exit_risk_off"
        rows.append(
            {
                "label": label,
                "timestamp": ts,
                "event": event,
                "gld_weight": round(gld_weight, 6),
                "bil_weight": round(1.0 - gld_weight, 6),
                "prev_gld_target_weight": round(float(prev_gld.loc[ts]), 6),
                "new_gld_target_weight": round(float(target_gld_weight.loc[ts]), 6),
                "prev_bil_target_weight": round(float(prev_bil.loc[ts]), 6),
                "new_bil_target_weight": round(float(target_bil_weight.loc[ts]), 6),
                "total_weight_delta": round(float(total_delta.loc[ts]), 6),
                "nav_before_cost": round(nav, 4),
                "notional_turned_over": round(notional, 4),
                "friction_bps": total_friction_bps,
                "estimated_friction_cost": round(friction, 4),
            }
        )
    return pd.DataFrame(rows)


def _apply_transition_costs(overlay: pd.Series, costs: pd.Series) -> pd.Series:
    rets = overlay.pct_change(fill_method=None).fillna(0.0)
    aligned_costs = costs.reindex(overlay.index).fillna(0.0)
    adjusted = [float(overlay.iloc[0])]
    for i in range(1, len(overlay)):
        prev_nav = adjusted[-1]
        nav = prev_nav * (1.0 + float(rets.iloc[i]))
        nav -= float(aligned_costs.iloc[i])
        adjusted.append(max(nav, 0.0))
    return pd.Series(adjusted, index=overlay.index, name=f"{overlay.name}_cost_adjusted")


def _episode_table(risk_off: pd.Series) -> pd.DataFrame:
    state = risk_off.astype(bool)
    episodes: list[dict[str, Any]] = []
    in_ep = False
    start = None
    prev_idx = None
    for idx, active in state.items():
        if active and not in_ep:
            in_ep = True
            start = idx
        elif not active and in_ep:
            episodes.append({"episode": len(episodes) + 1, "start": start, "end": prev_idx})
            in_ep = False
            start = None
        prev_idx = idx
    if in_ep and start is not None:
        episodes.append({"episode": len(episodes) + 1, "start": start, "end": prev_idx})
    return pd.DataFrame(episodes)


def _ret(series: pd.Series) -> float | None:
    clean = series.dropna()
    if len(clean) < 2:
        return None
    return (float(clean.iloc[-1]) / float(clean.iloc[0]) - 1.0) * 100.0


def _episode_attribution(
    episodes: pd.DataFrame,
    baseline: pd.Series,
    destination: pd.Series,
    min_episode_days: int,
) -> dict[str, Any]:
    if episodes.empty:
        return {
            "total_episodes": 0,
            "included_episodes": 0,
            "ignored_episodes": 0,
            "win_count": 0,
            "loss_count": 0,
            "win_rate_pct": None,
            "sum_delta_pct_points": None,
            "median_delta_pct_points": None,
        }
    deltas: list[float] = []
    included = 0
    ignored = 0
    for row in episodes.to_dict("records"):
        start = pd.Timestamp(row["start"])
        end = pd.Timestamp(row["end"])
        days = int((end - start).days) + 1
        b = baseline.loc[(baseline.index >= start) & (baseline.index <= end)]
        d = destination.loc[(destination.index >= start) & (destination.index <= end)]
        b_ret = _ret(b)
        d_ret = _ret(d)
        if days < min_episode_days or b_ret is None or d_ret is None:
            ignored += 1
            continue
        included += 1
        deltas.append(d_ret - b_ret)
    if not deltas:
        return {
            "total_episodes": int(len(episodes)),
            "included_episodes": 0,
            "ignored_episodes": int(ignored),
            "win_count": 0,
            "loss_count": 0,
            "win_rate_pct": None,
            "sum_delta_pct_points": None,
            "median_delta_pct_points": None,
        }
    s = pd.Series(deltas)
    wins = int((s > 0).sum())
    losses = int((s < 0).sum())
    return {
        "total_episodes": int(len(episodes)),
        "included_episodes": int(included),
        "ignored_episodes": int(ignored),
        "win_count": wins,
        "loss_count": losses,
        "win_rate_pct": round(wins / max(len(s), 1) * 100.0, 4),
        "sum_delta_pct_points": round(float(s.sum()), 4),
        "median_delta_pct_points": round(float(s.median()), 4),
    }


def _summary_row(
    label: str,
    gld_weight: float | None,
    equity: pd.Series,
    baseline_metrics: Any,
    args: argparse.Namespace,
    transition_count: int,
    gross_turnover: float,
    total_cost: float,
    attribution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metrics = compute_metrics(equity, trades=[], params={"strategy_id": label, "asset": "PORTFOLIO", "initial_capital": args.capital})
    row = {
        "label": label,
        "gld_weight": gld_weight,
        "bil_weight": None if gld_weight is None else 1.0 - gld_weight,
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
        "gross_turnover_notional": gross_turnover,
        "estimated_total_friction_cost": total_cost,
    }
    if attribution:
        row.update({f"episode_{k}": v for k, v in attribution.items()})
    return row


def _sort_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda r: (r["calmar"], r["sharpe"], r["max_drawdown_pct"], r["cagr_pct"]), reverse=True)


def _write_outputs(
    args: argparse.Namespace,
    rows: list[dict[str, Any]],
    transitions: pd.DataFrame,
    curves: pd.DataFrame,
    risk_off: pd.Series,
) -> Path:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sorted_rows = _sort_rows(rows)
    pd.DataFrame(sorted_rows).to_csv(out_dir / "destination_blend_summary.csv", index=False)
    transitions.to_csv(out_dir / "destination_blend_transition_events.csv", index=False)
    curves.to_csv(out_dir / "destination_blend_equity_curves.csv")
    risk_off.astype(int).to_csv(out_dir / "risk_off_state.csv", header=True)
    with open(out_dir / "destination_blend_review.json", "w", encoding="utf-8") as f:
        json.dump({"config": vars(args), "summary": sorted_rows}, f, indent=2, default=str)

    md = out_dir / "destination_blend_review.md"
    with open(md, "w", encoding="utf-8") as f:
        f.write("# State-Confirmed GLD/BIL Destination Blend Review\n\n")
        f.write("Research-only review of GLD/BIL blended destinations during state-confirmed risk-off windows.\n\n")
        f.write("## Candidate Rule\n\n")
        f.write(f"- Trigger / release: `{args.trigger_dd:.0%}` / `{args.release_dd:.0%}`\n")
        f.write(f"- BTC SMA window: `{args.btc_sma_window}`\n")
        f.write(f"- Release mode: `{args.release_mode}`\n")
        f.write(f"- Crypto scale while risk-off: `{args.crypto_scale:.0%}`\n")
        f.write(f"- Friction assumption: `{args.total_friction_bps:.2f}` bps per changed notional\n\n")
        f.write("## Summary\n\n")
        f.write("| Label | GLD Wt | CAGR | MaxDD | Sharpe | Calmar | Stress | Transitions | Cost | Episode Win Rate | Episode Sum Delta |\n")
        f.write("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n")
        for r in sorted_rows:
            f.write(
                f"| {r['label']} | {'' if r['gld_weight'] is None else f'{r['gld_weight']:.0%}'} | "
                f"{_fmt_pct(r['cagr_pct'])} | {_fmt_pct(r['max_drawdown_pct'])} | {r['sharpe']:.3f} | {r['calmar']:.3f} | "
                f"{_fmt_pct(r['stress_return_pct'])} | {r['transition_count']} | {_fmt_money(r['estimated_total_friction_cost'])} | "
                f"{_fmt_pct(r.get('episode_win_rate_pct'))} | {_fmt_pct(r.get('episode_sum_delta_pct_points'))} |\n"
            )
    return md


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Research-only GLD/BIL destination blend review")
    p.add_argument("--baseline-cache", required=True)
    p.add_argument("--btc-daily", required=True)
    p.add_argument("--gld-data", required=True)
    p.add_argument("--bil-data", required=True)
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--trigger-dd", type=float, default=-0.18)
    p.add_argument("--release-dd", type=float, default=-0.12)
    p.add_argument("--crypto-scale", type=float, default=0.0)
    p.add_argument("--btc-sma-window", type=int, default=200)
    p.add_argument("--release-mode", choices=["either", "both"], default="either")
    p.add_argument("--gld-weights", nargs="+", type=float, default=[1.0, 0.75, 0.50, 0.25, 0.0])
    p.add_argument("--total-friction-bps", type=float, default=10.0)
    p.add_argument("--min-episode-days", type=int, default=2)
    p.add_argument("--stress-start", default="2022-01-01")
    p.add_argument("--stress-end", default="2022-12-31")
    p.add_argument("--out-dir", default="artifacts/state_confirmed_destination_blend_review")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    baseline = _load_baseline_cache(args.baseline_cache)
    btc_close = _load_close(args.btc_daily, "BTC", args.start, args.end)
    gld = _buy_hold_curve(args.gld_data, "GLD", args.capital, args.start, args.end)
    bil = _buy_hold_curve(args.bil_data, "BIL", args.capital, args.start, args.end)
    btc_bad = _btc_below_sma(btc_close, baseline.index, args.btc_sma_window)
    risk_off = _state_confirmed_risk_off(baseline, btc_bad, args.trigger_dd, args.release_dd, args.release_mode)
    episodes = _episode_table(risk_off)
    baseline_metrics = compute_metrics(baseline, trades=[], params={"strategy_id": "baseline", "asset": "PORTFOLIO", "initial_capital": args.capital})

    rows: list[dict[str, Any]] = []
    all_transitions: list[pd.DataFrame] = []
    curves: dict[str, pd.Series] = {"baseline": baseline, "gld": gld, "bil": bil}

    rows.append(_summary_row("baseline", None, baseline, baseline_metrics, args, 0, 0.0, 0.0, None))

    for gld_weight in args.gld_weights:
        if gld_weight < 0.0 or gld_weight > 1.0:
            raise ValueError(f"GLD weight must be in [0, 1], got {gld_weight}")
        label = f"gld{int(round(gld_weight * 100))}_bil{int(round((1.0 - gld_weight) * 100))}"
        dest = _blend_destination_curve(gld, bil, gld_weight, args.capital, f"{label}_destination")
        overlay = _overlay_curve(baseline, dest, risk_off, args.crypto_scale, args.capital, f"{label}_pre_cost")
        transition = _transition_cost_table(overlay, risk_off, args.crypto_scale, gld_weight, args.total_friction_bps, label)
        total_cost = float(transition["estimated_friction_cost"].sum()) if not transition.empty else 0.0
        gross_turnover = float(transition["notional_turned_over"].sum()) if not transition.empty else 0.0
        transition_count = int(len(transition))
        costs = transition.groupby("timestamp")["estimated_friction_cost"].sum() if not transition.empty else pd.Series(dtype=float)
        adjusted = _apply_transition_costs(overlay, costs)
        adjusted.name = f"{label}_cost_adjusted"
        attribution = _episode_attribution(episodes, baseline, dest, args.min_episode_days)
        curves[f"{label}_pre_cost"] = overlay
        curves[f"{label}_cost_adjusted"] = adjusted
        all_transitions.append(transition)
        rows.append(
            _summary_row(
                label=f"{label}_cost_adjusted",
                gld_weight=gld_weight,
                equity=adjusted,
                baseline_metrics=baseline_metrics,
                args=args,
                transition_count=transition_count,
                gross_turnover=gross_turnover,
                total_cost=total_cost,
                attribution=attribution,
            )
        )

    transitions = pd.concat(all_transitions, ignore_index=True) if all_transitions else pd.DataFrame()
    curves_df = pd.DataFrame(curves).dropna(how="all")
    md = _write_outputs(args, rows, transitions, curves_df, risk_off)
    sorted_rows = _sort_rows(rows)

    print("=" * 152)
    print("  STATE-CONFIRMED GLD/BIL DESTINATION BLEND REVIEW")
    print("=" * 152)
    print(f"  Trigger / Release: {args.trigger_dd:.0%} / {args.release_dd:.0%}")
    print(f"  BTC trend filter : SMA{args.btc_sma_window}, release={args.release_mode}")
    print(f"  Crypto scale     : {args.crypto_scale:.0%}")
    print(f"  Friction         : {args.total_friction_bps:.2f} bps per changed notional")
    print("-" * 152)
    print(f"  {'Label':<24} {'GLD Wt':>7} {'CAGR%':>9} {'MaxDD%':>9} {'Sharpe':>8} {'Calmar':>8} {'Stress%':>9} {'Cost':>13} {'EpWin':>8} {'EpDelta':>9}")
    print("  " + "-" * 150)
    for r in sorted_rows:
        gld_w = "n/a" if r["gld_weight"] is None else f"{r['gld_weight']:.0%}"
        print(
            f"  {r['label']:<24} {gld_w:>7} {r['cagr_pct']:>8.2f}% {r['max_drawdown_pct']:>8.2f}% "
            f"{r['sharpe']:>8.3f} {r['calmar']:>8.3f} {_fmt_pct(r['stress_return_pct']):>9} "
            f"{_fmt_money(r['estimated_total_friction_cost']):>13} {_fmt_pct(r.get('episode_win_rate_pct')):>8} "
            f"{_fmt_pct(r.get('episode_sum_delta_pct_points')):>9}"
        )
    print("=" * 152)
    print(f"  Summary: {md}")
    print("  Verdict: research output only; review before any integration.\n")


if __name__ == "__main__":
    main()
