#!/usr/bin/env python
"""Compare research overlay vs paper replay for DefensiveDestinationAllocator.

This script reconciles the validated research-style GLD/BIL overlay against the
paper replay artifact emitted by scripts/run_defensive_destination_paper_replay.py.

It is diagnostic-only. It does not modify runtime, broker, governor, or state
files.
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
from scripts.run_risk_off_trigger_sweep import _buy_hold_curve, _load_baseline_cache, _normalized_returns
from scripts.run_state_confirmed_risk_off_sweep import _btc_below_sma, _load_close, _state_confirmed_risk_off


def _day(ts: Any) -> pd.Timestamp:
    return pd.Timestamp(ts).tz_localize(None).normalize()


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


def _load_paper_equity(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    first_col = df.columns[0]
    df[first_col] = pd.to_datetime(df[first_col]).map(_day)
    df = df.set_index(first_col).sort_index()
    required = {"paper_allocator_nav", "weight_GLD", "weight_BIL", "weight_fund_v1_exposure"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Paper equity file missing required columns: {sorted(missing)}")
    return df


def _blend_destination_curve(gld: pd.Series, bil: pd.Series, gld_weight: float, capital: float) -> pd.Series:
    aligned = pd.DataFrame({"gld": gld, "bil": bil}).dropna(how="any")
    rets = aligned.pct_change(fill_method=None).fillna(0.0)
    blend_rets = gld_weight * rets["gld"] + (1.0 - gld_weight) * rets["bil"]
    out = capital * (1.0 + blend_rets).cumprod()
    out.name = "research_destination"
    return out


def _overlay_curve(
    baseline: pd.Series,
    destination: pd.Series,
    risk_off: pd.Series,
    crypto_scale: float,
    capital: float,
) -> pd.Series:
    aligned = pd.DataFrame(
        {
            "baseline": baseline,
            "destination": destination,
            "risk_off": risk_off.astype(float),
        }
    ).dropna(how="any")
    crypto_ret = _normalized_returns(aligned["baseline"])
    dest_ret = _normalized_returns(aligned["destination"])
    active = aligned["risk_off"].astype(bool)
    weight_crypto = pd.Series(1.0, index=aligned.index)
    weight_dest = pd.Series(0.0, index=aligned.index)
    weight_crypto.loc[active] = crypto_scale
    weight_dest.loc[active] = 1.0 - crypto_scale
    portfolio_ret = weight_crypto * crypto_ret + weight_dest * dest_ret
    out = capital * (1.0 + portfolio_ret).cumprod()
    out.name = "research_overlay_nav"
    return out


def _slice_return(equity: pd.Series, start: str, end: str) -> float | None:
    s = equity.loc[(equity.index >= pd.Timestamp(start)) & (equity.index <= pd.Timestamp(end))].dropna()
    if len(s) < 2:
        return None
    return (float(s.iloc[-1]) / float(s.iloc[0]) - 1.0) * 100.0


def _metrics_row(label: str, equity: pd.Series, args: argparse.Namespace) -> dict[str, Any]:
    m = compute_metrics(equity, trades=[], params={"strategy_id": label, "asset": "PORTFOLIO", "initial_capital": args.capital})
    return {
        "label": label,
        "final_nav": float(equity.dropna().iloc[-1]),
        "cagr_pct": m.cagr_pct,
        "max_drawdown_pct": m.max_drawdown_pct,
        "sharpe": m.sharpe,
        "calmar": m.calmar,
        "stress_return_pct": _slice_return(equity, args.stress_start, args.stress_end),
    }


def _transition_dates_from_state(active: pd.Series) -> list[pd.Timestamp]:
    state = active.astype(bool)
    prev = state.shift(1).fillna(False).astype(bool)
    changed = state != prev
    return list(state.index[changed])


def _write_outputs(
    args: argparse.Namespace,
    comparison: pd.DataFrame,
    metrics_rows: list[dict[str, Any]],
    state_summary: dict[str, Any],
    gap_summary: dict[str, Any],
) -> Path:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(out_dir / "research_vs_paper_curves.csv")
    pd.DataFrame(metrics_rows).to_csv(out_dir / "research_vs_paper_metrics.csv", index=False)
    with open(out_dir / "research_vs_paper_summary.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "config": vars(args),
                "metrics": metrics_rows,
                "state_summary": state_summary,
                "gap_summary": gap_summary,
            },
            f,
            indent=2,
            default=str,
        )

    md = out_dir / "research_vs_paper_summary.md"
    with open(md, "w", encoding="utf-8") as f:
        f.write("# Defensive Destination Research vs Paper Reconciliation\n\n")
        f.write("Diagnostic-only comparison of research overlay and paper replay artifacts.\n\n")
        f.write("## Metrics\n\n")
        f.write("| Label | Final NAV | CAGR | MaxDD | Sharpe | Calmar | Stress |\n")
        f.write("|---|---:|---:|---:|---:|---:|---:|\n")
        for row in metrics_rows:
            f.write(
                f"| {row['label']} | {_fmt_money(row['final_nav'])} | {_fmt_pct(row['cagr_pct'])} | "
                f"{_fmt_pct(row['max_drawdown_pct'])} | {row['sharpe']:.3f} | {row['calmar']:.3f} | "
                f"{_fmt_pct(row['stress_return_pct'])} |\n"
            )
        f.write("\n## State Comparison\n\n")
        for k, v in state_summary.items():
            f.write(f"- {k}: `{v}`\n")
        f.write("\n## Gap Summary\n\n")
        for k, v in gap_summary.items():
            f.write(f"- {k}: `{v}`\n")
        f.write("\n## Interpretation Guide\n\n")
        f.write("```text\n")
        f.write("If state mismatches are high, the paper state machine timing differs from research overlay timing.\n")
        f.write("If state mismatches are low but NAV gap remains large, cost model / fill timing / return application are the likely causes.\n")
        f.write("If both states and curves align closely, the paper replay is reconciled with research overlay assumptions.\n")
        f.write("```\n")
    return md


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Compare DefensiveDestinationAllocator research overlay vs paper replay")
    p.add_argument("--baseline-cache", required=True)
    p.add_argument("--btc-daily", required=True)
    p.add_argument("--gld-data", required=True)
    p.add_argument("--bil-data", required=True)
    p.add_argument("--paper-equity", default="artifacts/defensive_destination_allocator/equity_curves.csv")
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--trigger-dd", type=float, default=-0.18)
    p.add_argument("--release-dd", type=float, default=-0.12)
    p.add_argument("--btc-sma-window", type=int, default=200)
    p.add_argument("--crypto-scale", type=float, default=0.0)
    p.add_argument("--gld-weight", type=float, default=0.50)
    p.add_argument("--release-mode", choices=["either", "both"], default="either")
    p.add_argument("--stress-start", default="2022-01-01")
    p.add_argument("--stress-end", default="2022-12-31")
    p.add_argument("--out-dir", default="artifacts/defensive_destination_allocator_reconciliation")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    baseline = _load_baseline_cache(args.baseline_cache)
    btc_close = _load_close(args.btc_daily, "BTC", args.start, args.end)
    gld = _buy_hold_curve(args.gld_data, "GLD", args.capital, args.start, args.end)
    bil = _buy_hold_curve(args.bil_data, "BIL", args.capital, args.start, args.end)
    paper = _load_paper_equity(args.paper_equity)

    common_dates = baseline.index.intersection(gld.index).intersection(bil.index).intersection(paper.index).sort_values()
    baseline = baseline.reindex(common_dates).dropna()
    common_dates = baseline.index
    gld = gld.reindex(common_dates).dropna()
    bil = bil.reindex(common_dates).dropna()
    paper = paper.reindex(common_dates).dropna(subset=["paper_allocator_nav"])
    common_dates = baseline.index.intersection(gld.index).intersection(bil.index).intersection(paper.index).sort_values()

    baseline = baseline.reindex(common_dates)
    gld = gld.reindex(common_dates)
    bil = bil.reindex(common_dates)
    paper = paper.reindex(common_dates)

    btc_bad = _btc_below_sma(btc_close, baseline.index, args.btc_sma_window)
    research_risk_off = _state_confirmed_risk_off(baseline, btc_bad, args.trigger_dd, args.release_dd, args.release_mode)
    destination = _blend_destination_curve(gld, bil, args.gld_weight, args.capital)
    research_overlay = _overlay_curve(baseline, destination, research_risk_off, args.crypto_scale, args.capital)

    comparison = pd.DataFrame(
        {
            "baseline": baseline,
            "research_overlay_nav": research_overlay,
            "paper_allocator_nav": paper["paper_allocator_nav"],
            "research_risk_off": research_risk_off.astype(int),
            "paper_risk_off": ((paper["weight_GLD"] + paper["weight_BIL"]) > 0).astype(int),
            "paper_weight_fund_v1_exposure": paper["weight_fund_v1_exposure"],
            "paper_weight_GLD": paper["weight_GLD"],
            "paper_weight_BIL": paper["weight_BIL"],
        }
    ).dropna(how="any")
    comparison["nav_gap_paper_minus_research"] = comparison["paper_allocator_nav"] - comparison["research_overlay_nav"]
    comparison["nav_gap_pct_of_research"] = comparison["nav_gap_paper_minus_research"] / comparison["research_overlay_nav"] * 100.0
    comparison["state_match"] = comparison["research_risk_off"] == comparison["paper_risk_off"]

    metrics_rows = [
        _metrics_row("baseline", comparison["baseline"], args),
        _metrics_row("research_overlay", comparison["research_overlay_nav"], args),
        _metrics_row("paper_allocator", comparison["paper_allocator_nav"], args),
    ]

    research_transitions = _transition_dates_from_state(comparison["research_risk_off"].astype(bool))
    paper_transitions = _transition_dates_from_state(comparison["paper_risk_off"].astype(bool))
    mismatch = comparison[~comparison["state_match"]]
    state_summary = {
        "rows_compared": int(len(comparison)),
        "state_match_days": int(comparison["state_match"].sum()),
        "state_mismatch_days": int(len(mismatch)),
        "state_match_pct": round(float(comparison["state_match"].mean() * 100.0), 4) if len(comparison) else None,
        "research_transition_count": int(len(research_transitions)),
        "paper_transition_count": int(len(paper_transitions)),
        "first_state_mismatch": None if mismatch.empty else mismatch.index[0].date().isoformat(),
        "last_state_mismatch": None if mismatch.empty else mismatch.index[-1].date().isoformat(),
    }

    gap_summary = {
        "final_nav_gap_paper_minus_research": float(comparison["nav_gap_paper_minus_research"].iloc[-1]),
        "final_nav_gap_pct_of_research": float(comparison["nav_gap_pct_of_research"].iloc[-1]),
        "max_abs_nav_gap": float(comparison["nav_gap_paper_minus_research"].abs().max()),
        "mean_abs_nav_gap": float(comparison["nav_gap_paper_minus_research"].abs().mean()),
        "worst_paper_underperformance_date": comparison["nav_gap_paper_minus_research"].idxmin().date().isoformat(),
        "worst_paper_underperformance": float(comparison["nav_gap_paper_minus_research"].min()),
        "best_paper_outperformance_date": comparison["nav_gap_paper_minus_research"].idxmax().date().isoformat(),
        "best_paper_outperformance": float(comparison["nav_gap_paper_minus_research"].max()),
    }

    md = _write_outputs(args, comparison, metrics_rows, state_summary, gap_summary)

    print("=" * 148)
    print("  DEFENSIVE DESTINATION — RESEARCH VS PAPER RECONCILIATION")
    print("=" * 148)
    print(f"  Blend            : {args.gld_weight:.0%} GLD / {1.0 - args.gld_weight:.0%} BIL")
    print(f"  Trigger / Release: {args.trigger_dd:.0%} / {args.release_dd:.0%}")
    print(f"  BTC SMA          : {args.btc_sma_window}")
    print("-" * 148)
    print(f"  {'Label':<18} {'Final NAV':>14} {'CAGR%':>9} {'MaxDD%':>9} {'Sharpe':>8} {'Calmar':>8} {'Stress%':>9}")
    print("  " + "-" * 146)
    for row in metrics_rows:
        print(
            f"  {row['label']:<18} {_fmt_money(row['final_nav']):>14} {row['cagr_pct']:>8.2f}% "
            f"{row['max_drawdown_pct']:>8.2f}% {row['sharpe']:>8.3f} {row['calmar']:>8.3f} "
            f"{_fmt_pct(row['stress_return_pct']):>9}"
        )
    print("-" * 148)
    print(f"  State match       : {state_summary['state_match_days']} / {state_summary['rows_compared']} days ({state_summary['state_match_pct']}%)")
    print(f"  Research transitions: {state_summary['research_transition_count']}")
    print(f"  Paper transitions   : {state_summary['paper_transition_count']}")
    print(f"  Final NAV gap       : {_fmt_money(gap_summary['final_nav_gap_paper_minus_research'])} ({gap_summary['final_nav_gap_pct_of_research']:.2f}% of research)")
    print(f"  Max abs NAV gap     : {_fmt_money(gap_summary['max_abs_nav_gap'])}")
    print("=" * 148)
    print(f"  Summary: {md}")
    print("  Verdict: diagnostic only; use to reconcile paper mechanics before implementation.\n")


if __name__ == "__main__":
    main()
