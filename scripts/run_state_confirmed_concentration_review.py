#!/usr/bin/env python
"""Research-only concentration / exclusion-window review.

This script evaluates whether a state-confirmed risk-off allocator candidate is
being carried by one or two major contribution windows.

Default comparison:
- baseline Fund v1
- GLD-only destination
- 50/50 GLD/BIL destination

Default candidate rule:
- trigger_dd: -18%
- release_dd: -12%
- BTC SMA: 200
- release_mode: either
- crypto_scale: 0%

Default exclusion windows:
- 2022 bear/stress window
- late-2025 stress/recovery window
- both windows together

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


def _fmt_num(value: Any, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if math.isnan(v):
        return "n/a"
    return f"{v:.{digits}f}"


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


def _parse_windows(raw: list[str]) -> dict[str, tuple[pd.Timestamp, pd.Timestamp]]:
    windows: dict[str, tuple[pd.Timestamp, pd.Timestamp]] = {}
    for item in raw:
        parts = item.split(":")
        if len(parts) != 3:
            raise ValueError(f"Exclusion window must be NAME:YYYY-MM-DD:YYYY-MM-DD, got {item!r}")
        name, start, end = parts
        windows[name.strip()] = (pd.Timestamp(start.strip()), pd.Timestamp(end.strip()))
    return windows


def _exclude_windows(series: pd.Series, windows: list[tuple[pd.Timestamp, pd.Timestamp]]) -> pd.Series:
    out = series.copy()
    mask = pd.Series(True, index=out.index)
    for start, end in windows:
        mask &= ~((out.index >= start) & (out.index <= end))
    return out.loc[mask]


def _rebase_after_exclusion(equity: pd.Series, capital: float) -> pd.Series:
    clean = equity.dropna()
    if clean.empty:
        return clean
    rets = clean.pct_change(fill_method=None).fillna(0.0)
    rebased = capital * (1.0 + rets).cumprod()
    rebased.name = equity.name
    return rebased


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


def _episode_rows(
    episodes: pd.DataFrame,
    baseline: pd.Series,
    candidates: dict[str, pd.Series],
    min_episode_days: int,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if episodes.empty:
        return pd.DataFrame(rows)
    for ep in episodes.to_dict("records"):
        start = pd.Timestamp(ep["start"])
        end = pd.Timestamp(ep["end"])
        days = int((end - start).days) + 1
        base_slice = baseline.loc[(baseline.index >= start) & (baseline.index <= end)]
        base_ret = _ret(base_slice)
        row: dict[str, Any] = {
            "episode": ep["episode"],
            "start": start.date().isoformat(),
            "end": end.date().isoformat(),
            "days": days,
            "included": days >= min_episode_days and base_ret is not None,
            "baseline_return_pct": base_ret,
        }
        for label, curve in candidates.items():
            s = curve.loc[(curve.index >= start) & (curve.index <= end)]
            c_ret = _ret(s)
            row[f"{label}_return_pct"] = c_ret
            row[f"{label}_delta_vs_baseline_pct"] = None if base_ret is None or c_ret is None else c_ret - base_ret
        rows.append(row)
    return pd.DataFrame(rows)


def _episode_attribution_summary(episode_df: pd.DataFrame, candidate_labels: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if episode_df.empty:
        return rows
    included = episode_df[episode_df["included"]].copy()
    for label in candidate_labels:
        col = f"{label}_delta_vs_baseline_pct"
        if col not in included.columns:
            continue
        deltas = pd.to_numeric(included[col], errors="coerce").dropna()
        if deltas.empty:
            rows.append({"label": label, "included_episodes": 0})
            continue
        wins = int((deltas > 0).sum())
        losses = int((deltas < 0).sum())
        rows.append(
            {
                "label": label,
                "included_episodes": int(len(deltas)),
                "win_count": wins,
                "loss_count": losses,
                "win_rate_pct": round(wins / max(len(deltas), 1) * 100.0, 4),
                "sum_delta_pct_points": round(float(deltas.sum()), 4),
                "mean_delta_pct_points": round(float(deltas.mean()), 4),
                "median_delta_pct_points": round(float(deltas.median()), 4),
                "largest_positive_delta_pct_points": round(float(deltas.max()), 4),
                "largest_negative_delta_pct_points": round(float(deltas.min()), 4),
            }
        )
    return rows


def _metrics_row(
    scenario: str,
    label: str,
    equity: pd.Series,
    baseline_equity: pd.Series,
    args: argparse.Namespace,
) -> dict[str, Any]:
    metrics = compute_metrics(equity, trades=[], params={"strategy_id": label, "asset": "PORTFOLIO", "initial_capital": args.capital})
    baseline_metrics = compute_metrics(baseline_equity, trades=[], params={"strategy_id": "baseline", "asset": "PORTFOLIO", "initial_capital": args.capital})
    return {
        "scenario": scenario,
        "label": label,
        "rows": int(len(equity)),
        "cagr_pct": metrics.cagr_pct,
        "max_drawdown_pct": metrics.max_drawdown_pct,
        "sharpe": metrics.sharpe,
        "calmar": metrics.calmar,
        "stress_return_pct": _slice_return(equity, args.stress_start, args.stress_end),
        "delta_cagr_vs_baseline": metrics.cagr_pct - baseline_metrics.cagr_pct,
        "delta_maxdd_vs_baseline": metrics.max_drawdown_pct - baseline_metrics.max_drawdown_pct,
        "delta_sharpe_vs_baseline": metrics.sharpe - baseline_metrics.sharpe,
        "delta_calmar_vs_baseline": metrics.calmar - baseline_metrics.calmar,
    }


def _scenario_windows(windows: dict[str, tuple[pd.Timestamp, pd.Timestamp]]) -> dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]]:
    scenarios = {"full_sample": []}
    for name, window in windows.items():
        scenarios[f"exclude_{name}"] = [window]
    if len(windows) > 1:
        scenarios["exclude_all_specified"] = list(windows.values())
    return scenarios


def _write_outputs(
    args: argparse.Namespace,
    metrics_rows: list[dict[str, Any]],
    episode_df: pd.DataFrame,
    episode_summary: list[dict[str, Any]],
    curves: pd.DataFrame,
    risk_off: pd.Series,
    windows: dict[str, tuple[pd.Timestamp, pd.Timestamp]],
) -> Path:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    metrics_df = pd.DataFrame(metrics_rows)
    metrics_df.to_csv(out_dir / "concentration_metrics.csv", index=False)
    episode_df.to_csv(out_dir / "concentration_episode_details.csv", index=False)
    pd.DataFrame(episode_summary).to_csv(out_dir / "concentration_episode_summary.csv", index=False)
    curves.to_csv(out_dir / "concentration_equity_curves.csv")
    risk_off.astype(int).to_csv(out_dir / "risk_off_state.csv", header=True)
    with open(out_dir / "concentration_review.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "config": vars(args),
                "exclusion_windows": {k: [str(v[0].date()), str(v[1].date())] for k, v in windows.items()},
                "metrics": metrics_rows,
                "episode_summary": episode_summary,
            },
            f,
            indent=2,
            default=str,
        )

    md = out_dir / "concentration_review.md"
    with open(md, "w", encoding="utf-8") as f:
        f.write("# State-Confirmed Concentration / Exclusion-Window Review\n\n")
        f.write("Research-only review to test whether allocator results are overly dependent on specified contribution windows.\n\n")
        f.write("## Candidate Rule\n\n")
        f.write(f"- Trigger / release: `{args.trigger_dd:.0%}` / `{args.release_dd:.0%}`\n")
        f.write(f"- BTC SMA window: `{args.btc_sma_window}`\n")
        f.write(f"- Release mode: `{args.release_mode}`\n")
        f.write(f"- Crypto scale while risk-off: `{args.crypto_scale:.0%}`\n")
        f.write("\n## Exclusion Windows\n\n")
        for name, (start, end) in windows.items():
            f.write(f"- `{name}`: `{start.date().isoformat()}` to `{end.date().isoformat()}`\n")
        f.write("\n## Metrics By Scenario\n\n")
        f.write("| Scenario | Label | CAGR | MaxDD | Sharpe | Calmar | dCalmar vs Baseline | Rows |\n")
        f.write("|---|---|---:|---:|---:|---:|---:|---:|\n")
        for row in metrics_rows:
            f.write(
                f"| {row['scenario']} | {row['label']} | {_fmt_pct(row['cagr_pct'])} | "
                f"{_fmt_pct(row['max_drawdown_pct'])} | {_fmt_num(row['sharpe'])} | {_fmt_num(row['calmar'])} | "
                f"{_fmt_num(row['delta_calmar_vs_baseline'])} | {row['rows']} |\n"
            )
        f.write("\n## Episode Attribution Summary\n\n")
        f.write("| Label | Included | Wins | Losses | Win Rate | Sum Delta | Median Delta | Largest Win | Largest Loss |\n")
        f.write("|---|---:|---:|---:|---:|---:|---:|---:|---:|\n")
        for row in episode_summary:
            f.write(
                f"| {row['label']} | {row.get('included_episodes', 0)} | {row.get('win_count', 0)} | "
                f"{row.get('loss_count', 0)} | {_fmt_pct(row.get('win_rate_pct'))} | "
                f"{_fmt_pct(row.get('sum_delta_pct_points'))} | {_fmt_pct(row.get('median_delta_pct_points'))} | "
                f"{_fmt_pct(row.get('largest_positive_delta_pct_points'))} | {_fmt_pct(row.get('largest_negative_delta_pct_points'))} |\n"
            )
    return md


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Research-only concentration / exclusion-window review")
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
    p.add_argument("--blend-gld-weight", type=float, default=0.50)
    p.add_argument("--min-episode-days", type=int, default=2)
    p.add_argument("--exclude-window", action="append", default=["2022:2022-01-01:2022-12-31", "late_2025:2025-11-01:2025-12-30"], help="NAME:YYYY-MM-DD:YYYY-MM-DD. Repeatable.")
    p.add_argument("--stress-start", default="2022-01-01")
    p.add_argument("--stress-end", default="2022-12-31")
    p.add_argument("--out-dir", default="artifacts/state_confirmed_concentration_review")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.blend_gld_weight < 0.0 or args.blend_gld_weight > 1.0:
        raise ValueError("--blend-gld-weight must be in [0, 1]")

    baseline = _load_baseline_cache(args.baseline_cache)
    btc_close = _load_close(args.btc_daily, "BTC", args.start, args.end)
    gld = _buy_hold_curve(args.gld_data, "GLD", args.capital, args.start, args.end)
    bil = _buy_hold_curve(args.bil_data, "BIL", args.capital, args.start, args.end)
    blend = _blend_destination_curve(gld, bil, args.blend_gld_weight, args.capital, "gld_bil_blend_destination")

    btc_bad = _btc_below_sma(btc_close, baseline.index, args.btc_sma_window)
    risk_off = _state_confirmed_risk_off(baseline, btc_bad, args.trigger_dd, args.release_dd, args.release_mode)

    candidates = {
        "gld_only": _overlay_curve(baseline, gld, risk_off, args.crypto_scale, args.capital, "gld_only"),
        "gld_bil_blend": _overlay_curve(baseline, blend, risk_off, args.crypto_scale, args.capital, "gld_bil_blend"),
    }
    all_curves = {"baseline": baseline, "gld": gld, "bil": bil, "gld_bil_destination": blend, **candidates}
    curves = pd.DataFrame(all_curves).dropna(how="all")

    episodes = _episode_table(risk_off)
    episode_df = _episode_rows(episodes, baseline, candidates, args.min_episode_days)
    episode_summary = _episode_attribution_summary(episode_df, list(candidates.keys()))

    windows = _parse_windows(args.exclude_window)
    scenarios = _scenario_windows(windows)
    metrics_rows: list[dict[str, Any]] = []
    for scenario, exclusion_windows in scenarios.items():
        base_s = _rebase_after_exclusion(_exclude_windows(baseline, exclusion_windows), args.capital)
        metrics_rows.append(_metrics_row(scenario, "baseline", base_s, base_s, args))
        for label, curve in candidates.items():
            c_s = _rebase_after_exclusion(_exclude_windows(curve, exclusion_windows), args.capital)
            # Align baseline to same kept dates for fair delta calculation.
            aligned_base = base_s.reindex(c_s.index).dropna()
            aligned_candidate = c_s.reindex(aligned_base.index).dropna()
            aligned_base = aligned_base.reindex(aligned_candidate.index).dropna()
            metrics_rows.append(_metrics_row(scenario, label, aligned_candidate, aligned_base, args))

    md = _write_outputs(args, metrics_rows, episode_df, episode_summary, curves, risk_off, windows)

    print("=" * 152)
    print("  STATE-CONFIRMED CONCENTRATION / EXCLUSION-WINDOW REVIEW")
    print("=" * 152)
    print(f"  Trigger / Release: {args.trigger_dd:.0%} / {args.release_dd:.0%}")
    print(f"  BTC trend filter : SMA{args.btc_sma_window}, release={args.release_mode}")
    print(f"  Crypto scale     : {args.crypto_scale:.0%}")
    print(f"  Blend            : {args.blend_gld_weight:.0%} GLD / {1.0 - args.blend_gld_weight:.0%} BIL")
    print("-" * 152)
    print(f"  {'Scenario':<24} {'Label':<16} {'CAGR%':>9} {'MaxDD%':>9} {'Sharpe':>8} {'Calmar':>8} {'dCalmar':>9}")
    print("  " + "-" * 150)
    for row in metrics_rows:
        print(
            f"  {row['scenario']:<24} {row['label']:<16} {row['cagr_pct']:>8.2f}% {row['max_drawdown_pct']:>8.2f}% "
            f"{row['sharpe']:>8.3f} {row['calmar']:>8.3f} {row['delta_calmar_vs_baseline']:>9.3f}"
        )
    print("-" * 152)
    print("  Episode attribution:")
    for row in episode_summary:
        print(
            f"  {row['label']:<16} wins={row.get('win_count', 0):>2} losses={row.get('loss_count', 0):>2} "
            f"win_rate={_fmt_pct(row.get('win_rate_pct')):>8} sum_delta={_fmt_pct(row.get('sum_delta_pct_points')):>9} "
            f"median_delta={_fmt_pct(row.get('median_delta_pct_points')):>9}"
        )
    print("=" * 152)
    print(f"  Summary: {md}")
    print("  Verdict: research output only; review before any integration.\n")


if __name__ == "__main__":
    main()
