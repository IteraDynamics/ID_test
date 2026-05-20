#!/usr/bin/env python
"""Research-only robustness sweep for state-confirmed GLD/BIL blend candidates.

This script tests whether the current leading 50/50 GLD/BIL destination result
is part of a stable parameter cluster or a narrow tuned point.

Default sweep area:
- trigger_dds: -18%, -20%, -22%
- release_dds: -8%, -10%, -12%
- BTC SMA windows: 180, 200, 220
- GLD weights: 75%, 50%, 25%
- crypto_scale: 0%
- transition cost: 10 bps per changed notional

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
    destination: pd.Series,
    risk_off: pd.Series,
    crypto_scale: float,
    capital: float,
    label: str,
) -> pd.Series:
    aligned = pd.DataFrame({"baseline": baseline, "destination": destination, "risk_off": risk_off.astype(float)}).dropna(how="any")
    crypto_ret = _normalized_returns(aligned["baseline"])
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


def _transition_costs(
    overlay: pd.Series,
    risk_off: pd.Series,
    crypto_scale: float,
    gld_weight: float,
    total_friction_bps: float,
) -> tuple[pd.Series, int, float, float]:
    target_dest_weight = _destination_weight(risk_off, crypto_scale, overlay.index)
    target_gld_weight = target_dest_weight * gld_weight
    target_bil_weight = target_dest_weight * (1.0 - gld_weight)

    prev_gld = target_gld_weight.shift(1).fillna(0.0)
    prev_bil = target_bil_weight.shift(1).fillna(0.0)
    total_delta = (target_gld_weight - prev_gld).abs() + (target_bil_weight - prev_bil).abs()

    cost_units = pd.Series(0.0, index=overlay.index)
    gross_turnover = 0.0
    total_cost = 0.0
    transition_count = 0
    for ts in overlay.index[total_delta > 0]:
        nav = float(overlay.loc[ts])
        notional = nav * float(total_delta.loc[ts])
        cost = notional * (total_friction_bps / 10_000.0)
        cost_units.loc[ts] += cost
        gross_turnover += notional
        total_cost += cost
        transition_count += 1

    rets = overlay.pct_change(fill_method=None).fillna(0.0)
    adjusted = [float(overlay.iloc[0])]
    for i in range(1, len(overlay)):
        prev_nav = adjusted[-1]
        nav = prev_nav * (1.0 + float(rets.iloc[i]))
        nav -= float(cost_units.iloc[i])
        adjusted.append(max(nav, 0.0))
    adjusted_series = pd.Series(adjusted, index=overlay.index, name=f"{overlay.name}_cost_adjusted")
    return adjusted_series, transition_count, gross_turnover, total_cost


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
            "included_episodes": 0,
            "win_count": 0,
            "loss_count": 0,
            "win_rate_pct": None,
            "sum_delta_pct_points": None,
            "median_delta_pct_points": None,
        }
    deltas: list[float] = []
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
        deltas.append(d_ret - b_ret)
    if not deltas:
        return {
            "included_episodes": 0,
            "ignored_episodes": ignored,
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
        "included_episodes": int(len(s)),
        "ignored_episodes": ignored,
        "win_count": wins,
        "loss_count": losses,
        "win_rate_pct": round(wins / max(len(s), 1) * 100.0, 4),
        "sum_delta_pct_points": round(float(s.sum()), 4),
        "median_delta_pct_points": round(float(s.median()), 4),
    }


def _passes_guardrails(row: dict[str, Any], args: argparse.Namespace) -> bool:
    return (
        row["calmar"] >= args.min_calmar
        and row["max_drawdown_pct"] >= args.max_allowed_drawdown * 100.0
        and row["risk_off_pct_days"] <= args.max_risk_off_pct
        and row["risk_off_pct_days"] >= args.min_risk_off_pct
        and (row.get("episode_win_rate_pct") is None or row["episode_win_rate_pct"] >= args.min_episode_win_rate_pct)
    )


def _summary_row(
    label: str,
    trigger_dd: float,
    release_dd: float,
    sma_window: int,
    gld_weight: float,
    equity: pd.Series,
    baseline_metrics: Any,
    risk_off: pd.Series,
    transition_count: int,
    gross_turnover: float,
    total_cost: float,
    attribution: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    metrics = compute_metrics(equity, trades=[], params={"strategy_id": label, "asset": "PORTFOLIO", "initial_capital": args.capital})
    risk_off_days = int(risk_off.reindex(equity.index).ffill().fillna(False).astype(bool).sum())
    row = {
        "label": label,
        "trigger_dd": trigger_dd,
        "release_dd": release_dd,
        "btc_sma_window": sma_window,
        "gld_weight": gld_weight,
        "bil_weight": 1.0 - gld_weight,
        "crypto_scale": args.crypto_scale,
        "cagr_pct": metrics.cagr_pct,
        "max_drawdown_pct": metrics.max_drawdown_pct,
        "sharpe": metrics.sharpe,
        "calmar": metrics.calmar,
        "stress_return_pct": _slice_return(equity, args.stress_start, args.stress_end),
        "delta_cagr_vs_baseline": metrics.cagr_pct - baseline_metrics.cagr_pct,
        "delta_maxdd_vs_baseline": metrics.max_drawdown_pct - baseline_metrics.max_drawdown_pct,
        "delta_sharpe_vs_baseline": metrics.sharpe - baseline_metrics.sharpe,
        "delta_calmar_vs_baseline": metrics.calmar - baseline_metrics.calmar,
        "risk_off_days": risk_off_days,
        "risk_off_pct_days": round(risk_off_days / max(len(equity), 1) * 100.0, 4),
        "transition_count": transition_count,
        "gross_turnover_notional": gross_turnover,
        "estimated_total_friction_cost": total_cost,
    }
    row.update({f"episode_{k}": v for k, v in attribution.items()})
    return row


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


def _write_outputs(args: argparse.Namespace, rows: list[dict[str, Any]]) -> Path:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sorted_rows = _sort_rows(rows, args)
    pd.DataFrame(sorted_rows).to_csv(out_dir / "blend_robustness_summary.csv", index=False)
    with open(out_dir / "blend_robustness_summary.json", "w", encoding="utf-8") as f:
        json.dump({"config": vars(args), "summary": sorted_rows}, f, indent=2, default=str)

    md = out_dir / "blend_robustness_summary.md"
    with open(md, "w", encoding="utf-8") as f:
        f.write("# State-Confirmed GLD/BIL Blend Robustness Sweep\n\n")
        f.write("Research-only sweep testing nearby trigger/release/SMA/blend settings.\n\n")
        f.write("## Guardrails\n\n")
        f.write(f"- Minimum Calmar: `{args.min_calmar}`\n")
        f.write(f"- Max allowed drawdown: `{args.max_allowed_drawdown:.0%}`\n")
        f.write(f"- Risk-off active range: `{args.min_risk_off_pct}%` to `{args.max_risk_off_pct}%`\n")
        f.write(f"- Minimum episode win rate: `{args.min_episode_win_rate_pct}%`\n\n")
        f.write("## Top Rows\n\n")
        f.write("| Pass | Trigger | Release | SMA | GLD Wt | CAGR | MaxDD | Sharpe | Calmar | Stress | RiskOff | Cost | EpWin | EpDelta |\n")
        f.write("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n")
        for r in sorted_rows[: args.report_top_n]:
            f.write(
                f"| {'YES' if _passes_guardrails(r, args) else 'NO'} | {r['trigger_dd']:.0%} | {r['release_dd']:.0%} | "
                f"{r['btc_sma_window']} | {r['gld_weight']:.0%} | {_fmt_pct(r['cagr_pct'])} | "
                f"{_fmt_pct(r['max_drawdown_pct'])} | {r['sharpe']:.3f} | {r['calmar']:.3f} | "
                f"{_fmt_pct(r['stress_return_pct'])} | {r['risk_off_pct_days']:.1f}% | "
                f"{_fmt_money(r['estimated_total_friction_cost'])} | {_fmt_pct(r.get('episode_win_rate_pct'))} | "
                f"{_fmt_pct(r.get('episode_sum_delta_pct_points'))} |\n"
            )
    return md


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Research-only GLD/BIL blend robustness sweep")
    p.add_argument("--baseline-cache", required=True)
    p.add_argument("--btc-daily", required=True)
    p.add_argument("--gld-data", required=True)
    p.add_argument("--bil-data", required=True)
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--trigger-dds", nargs="+", type=float, default=[-0.18, -0.20, -0.22])
    p.add_argument("--release-dds", nargs="+", type=float, default=[-0.08, -0.10, -0.12])
    p.add_argument("--btc-sma-windows", nargs="+", type=int, default=[180, 200, 220])
    p.add_argument("--gld-weights", nargs="+", type=float, default=[0.75, 0.50, 0.25])
    p.add_argument("--crypto-scale", type=float, default=0.0)
    p.add_argument("--release-mode", choices=["either", "both"], default="either")
    p.add_argument("--total-friction-bps", type=float, default=10.0)
    p.add_argument("--min-episode-days", type=int, default=2)
    p.add_argument("--stress-start", default="2022-01-01")
    p.add_argument("--stress-end", default="2022-12-31")
    p.add_argument("--min-calmar", type=float, default=1.20)
    p.add_argument("--max-allowed-drawdown", type=float, default=-0.30)
    p.add_argument("--min-risk-off-pct", type=float, default=5.0)
    p.add_argument("--max-risk-off-pct", type=float, default=35.0)
    p.add_argument("--min-episode-win-rate-pct", type=float, default=55.0)
    p.add_argument("--report-top-n", type=int, default=40)
    p.add_argument("--out-dir", default="artifacts/state_confirmed_blend_robustness_sweep")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    baseline = _load_baseline_cache(args.baseline_cache)
    btc_close = _load_close(args.btc_daily, "BTC", args.start, args.end)
    gld = _buy_hold_curve(args.gld_data, "GLD", args.capital, args.start, args.end)
    bil = _buy_hold_curve(args.bil_data, "BIL", args.capital, args.start, args.end)
    baseline_metrics = compute_metrics(baseline, trades=[], params={"strategy_id": "baseline", "asset": "PORTFOLIO", "initial_capital": args.capital})

    btc_bad_by_sma = {window: _btc_below_sma(btc_close, baseline.index, window) for window in args.btc_sma_windows}
    destinations = {
        gld_weight: _blend_destination_curve(gld, bil, gld_weight, args.capital, f"gld{int(gld_weight * 100)}_bil{int((1.0 - gld_weight) * 100)}_destination")
        for gld_weight in args.gld_weights
    }

    rows: list[dict[str, Any]] = []
    for trigger_dd in args.trigger_dds:
        for release_dd in args.release_dds:
            if release_dd <= trigger_dd:
                continue
            for sma_window, btc_bad in btc_bad_by_sma.items():
                risk_off = _state_confirmed_risk_off(baseline, btc_bad, trigger_dd, release_dd, args.release_mode)
                episodes = _episode_table(risk_off)
                for gld_weight, destination in destinations.items():
                    label = f"trig{int(abs(trigger_dd) * 100)}_rel{int(abs(release_dd) * 100)}_sma{sma_window}_gld{int(round(gld_weight * 100))}"
                    overlay = _overlay_curve(baseline, destination, risk_off, args.crypto_scale, args.capital, label)
                    adjusted, transition_count, gross_turnover, total_cost = _transition_costs(
                        overlay,
                        risk_off,
                        args.crypto_scale,
                        gld_weight,
                        args.total_friction_bps,
                    )
                    attribution = _episode_attribution(episodes, baseline, destination, args.min_episode_days)
                    rows.append(
                        _summary_row(
                            label=label,
                            trigger_dd=trigger_dd,
                            release_dd=release_dd,
                            sma_window=sma_window,
                            gld_weight=gld_weight,
                            equity=adjusted,
                            baseline_metrics=baseline_metrics,
                            risk_off=risk_off,
                            transition_count=transition_count,
                            gross_turnover=gross_turnover,
                            total_cost=total_cost,
                            attribution=attribution,
                            args=args,
                        )
                    )

    md = _write_outputs(args, rows)
    sorted_rows = _sort_rows(rows, args)

    print("=" * 168)
    print("  STATE-CONFIRMED GLD/BIL BLEND ROBUSTNESS SWEEP")
    print("=" * 168)
    print(f"  Rows tested       : {len(rows)}")
    print(f"  Friction          : {args.total_friction_bps:.2f} bps per changed notional")
    print(f"  Guardrails        : Calmar >= {args.min_calmar:.2f}, MaxDD >= {args.max_allowed_drawdown:.0%}, RiskOff {args.min_risk_off_pct:.1f}%->{args.max_risk_off_pct:.1f}%")
    print("-" * 168)
    print(f"  {'Pass':<5} {'Trig':>6} {'Rel':>6} {'SMA':>5} {'GLD':>5} {'CAGR%':>9} {'MaxDD%':>9} {'Sharpe':>8} {'Calmar':>8} {'Stress%':>9} {'RiskOff':>8} {'Cost':>13} {'EpWin':>8} {'EpDelta':>9}")
    print("  " + "-" * 166)
    for r in sorted_rows[: args.report_top_n]:
        print(
            f"  {('YES' if _passes_guardrails(r, args) else 'NO'):<5} {r['trigger_dd']:>6.0%} {r['release_dd']:>6.0%} "
            f"{r['btc_sma_window']:>5} {r['gld_weight']:>5.0%} {r['cagr_pct']:>8.2f}% {r['max_drawdown_pct']:>8.2f}% "
            f"{r['sharpe']:>8.3f} {r['calmar']:>8.3f} {_fmt_pct(r['stress_return_pct']):>9} {r['risk_off_pct_days']:>7.1f}% "
            f"{_fmt_money(r['estimated_total_friction_cost']):>13} {_fmt_pct(r.get('episode_win_rate_pct')):>8} {_fmt_pct(r.get('episode_sum_delta_pct_points')):>9}"
        )
    print("=" * 168)
    print(f"  Summary: {md}")
    print("  Verdict: research output only; review before any integration.\n")


if __name__ == "__main__":
    main()
