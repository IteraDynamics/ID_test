#!/usr/bin/env python
"""Research-only diagnostic for one state-confirmed risk-off candidate.

This script explains a selected allocator candidate episode-by-episode instead
of sweeping parameters. It compares baseline Fund v1 returns versus the selected
destination during each risk-off episode and writes auditable artifacts.

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
from scripts.run_state_confirmed_risk_off_sweep import (
    _btc_below_sma,
    _load_close,
    _row,
    _state_confirmed_risk_off,
)
from scripts.run_risk_off_trigger_sweep import (
    _buy_hold_curve,
    _load_baseline_cache,
    _normalized_returns,
    _overlay_curve,
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


def _fmt_num(value: Any, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if math.isnan(v):
        return "n/a"
    return f"{v:.{digits}f}"


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


def _max_dd(series: pd.Series) -> float | None:
    clean = series.dropna()
    if len(clean) < 2:
        return None
    dd = clean / clean.cummax() - 1.0
    return float(dd.min()) * 100.0


def _valid_return(value: Any) -> bool:
    if value is None:
        return False
    try:
        return not math.isnan(float(value))
    except (TypeError, ValueError):
        return False


def _annotate_episodes(
    episodes: pd.DataFrame,
    baseline: pd.Series,
    destination: pd.Series,
    overlay: pd.Series,
    btc_close: pd.Series,
    btc_sma_window: int,
    min_episode_days: int,
) -> pd.DataFrame:
    if episodes.empty:
        return episodes

    btc_daily = btc_close.resample("1D").last().ffill()
    btc_sma = btc_daily.rolling(btc_sma_window, min_periods=btc_sma_window).mean()
    rows: list[dict[str, Any]] = []

    for row in episodes.to_dict("records"):
        start = pd.Timestamp(row["start"])
        end = pd.Timestamp(row["end"])
        days = int((end - start).days) + 1
        b = baseline.loc[(baseline.index >= start) & (baseline.index <= end)]
        d = destination.loc[(destination.index >= start) & (destination.index <= end)]
        o = overlay.loc[(overlay.index >= start) & (overlay.index <= end)]
        btc_slice = btc_daily.loc[(btc_daily.index >= start) & (btc_daily.index <= end)]
        sma_slice = btc_sma.loc[(btc_sma.index >= start) & (btc_sma.index <= end)]

        baseline_ret = _ret(b)
        dest_ret = _ret(d)
        overlay_ret = _ret(o)
        delta = None if baseline_ret is None or dest_ret is None else dest_ret - baseline_ret
        include = days >= min_episode_days and _valid_return(baseline_ret) and _valid_return(dest_ret)

        rows.append(
            {
                "episode": row["episode"],
                "start": start.date().isoformat(),
                "end": end.date().isoformat(),
                "days": days,
                "included_in_attribution": include,
                "baseline_return_pct": None if baseline_ret is None else round(baseline_ret, 4),
                "destination_return_pct": None if dest_ret is None else round(dest_ret, 4),
                "overlay_return_pct": None if overlay_ret is None else round(overlay_ret, 4),
                "return_delta_dest_vs_baseline_pct": None if delta is None else round(delta, 4),
                "baseline_episode_maxdd_pct": None if _max_dd(b) is None else round(_max_dd(b), 4),
                "destination_episode_maxdd_pct": None if _max_dd(d) is None else round(_max_dd(d), 4),
                "overlay_episode_maxdd_pct": None if _max_dd(o) is None else round(_max_dd(o), 4),
                "btc_start": None if btc_slice.empty else round(float(btc_slice.iloc[0]), 4),
                "btc_end": None if btc_slice.empty else round(float(btc_slice.iloc[-1]), 4),
                "btc_return_pct": None if _ret(btc_slice) is None else round(_ret(btc_slice), 4),
                "btc_sma_start": None if sma_slice.dropna().empty else round(float(sma_slice.dropna().iloc[0]), 4),
                "btc_sma_end": None if sma_slice.dropna().empty else round(float(sma_slice.dropna().iloc[-1]), 4),
            }
        )
    return pd.DataFrame(rows)


def _episode_attribution(episode_df: pd.DataFrame, min_episode_days: int) -> dict[str, Any]:
    if episode_df.empty:
        return {
            "total_episodes": 0,
            "included_episodes": 0,
            "ignored_episodes": 0,
            "min_episode_days": min_episode_days,
        }

    included = episode_df[episode_df["included_in_attribution"]].copy()
    ignored = episode_df[~episode_df["included_in_attribution"]].copy()
    if included.empty:
        return {
            "total_episodes": int(len(episode_df)),
            "included_episodes": 0,
            "ignored_episodes": int(len(ignored)),
            "min_episode_days": min_episode_days,
        }

    deltas = pd.to_numeric(included["return_delta_dest_vs_baseline_pct"], errors="coerce").dropna()
    baseline_rets = pd.to_numeric(included["baseline_return_pct"], errors="coerce").dropna()
    dest_rets = pd.to_numeric(included["destination_return_pct"], errors="coerce").dropna()
    wins = int((deltas > 0).sum())
    losses = int((deltas < 0).sum())
    flats = int((deltas == 0).sum())
    biggest_win = included.loc[pd.to_numeric(included["return_delta_dest_vs_baseline_pct"], errors="coerce").idxmax()].to_dict()
    biggest_loss = included.loc[pd.to_numeric(included["return_delta_dest_vs_baseline_pct"], errors="coerce").idxmin()].to_dict()

    return {
        "total_episodes": int(len(episode_df)),
        "included_episodes": int(len(included)),
        "ignored_episodes": int(len(ignored)),
        "min_episode_days": min_episode_days,
        "win_count": wins,
        "loss_count": losses,
        "flat_count": flats,
        "win_rate_pct": round(wins / max(len(deltas), 1) * 100.0, 4),
        "sum_delta_pct_points": round(float(deltas.sum()), 4),
        "mean_delta_pct_points": round(float(deltas.mean()), 4),
        "median_delta_pct_points": round(float(deltas.median()), 4),
        "sum_baseline_episode_returns_pct": round(float(baseline_rets.sum()), 4),
        "sum_destination_episode_returns_pct": round(float(dest_rets.sum()), 4),
        "biggest_win": biggest_win,
        "biggest_loss": biggest_loss,
    }


def _write_outputs(
    args: argparse.Namespace,
    summary_row: dict[str, Any],
    episode_df: pd.DataFrame,
    attribution: dict[str, Any],
    baseline: pd.Series,
    destination: pd.Series,
    overlay: pd.Series,
    risk_off: pd.Series,
) -> Path:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pd.DataFrame([summary_row]).to_csv(out_dir / "candidate_summary.csv", index=False)
    pd.DataFrame([attribution]).to_csv(out_dir / "episode_attribution_summary.csv", index=False)
    episode_df.to_csv(out_dir / "risk_off_episodes.csv", index=False)
    pd.DataFrame({"baseline": baseline, args.destination_label.lower(): destination, "overlay": overlay}).dropna(how="all").to_csv(out_dir / "candidate_equity_curves.csv")
    risk_off.astype(int).to_csv(out_dir / "risk_off_state.csv", header=True)

    payload = {"candidate": summary_row, "episode_attribution": attribution, "episodes": episode_df.to_dict("records")}
    with open(out_dir / "candidate_diagnostic.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)

    md = out_dir / "candidate_diagnostic.md"
    with open(md, "w", encoding="utf-8") as f:
        f.write("# State-Confirmed Candidate Diagnostic\n\n")
        f.write("Research-only diagnostic for one Layer 3 allocator candidate.\n\n")
        f.write("## Candidate\n\n")
        f.write(f"- Destination: `{args.destination_label.upper()}`\n")
        f.write(f"- Trigger drawdown: `{args.trigger_dd:.0%}`\n")
        f.write(f"- Release drawdown: `{args.release_dd:.0%}`\n")
        f.write(f"- BTC SMA window: `{args.btc_sma_window}`\n")
        f.write(f"- Release mode: `{args.release_mode}`\n")
        f.write(f"- Crypto scale while risk-off: `{args.crypto_scale:.0%}`\n")
        f.write(f"- Minimum episode days for attribution: `{args.min_episode_days}`\n")
        f.write("\n## Portfolio Summary\n\n")
        f.write("| CAGR | MaxDD | Sharpe | Calmar | Stress | RiskOff Days | RiskOff % |\n")
        f.write("|---:|---:|---:|---:|---:|---:|---:|\n")
        stress = summary_row.get("stress_return_pct")
        f.write(
            f"| {summary_row['cagr_pct']:.2f}% | {summary_row['max_drawdown_pct']:.2f}% | "
            f"{summary_row['sharpe']:.3f} | {summary_row['calmar']:.3f} | "
            f"{'n/a' if stress is None else f'{stress:.2f}%'} | {summary_row['risk_off_days']} | "
            f"{summary_row['risk_off_pct_days']:.1f}% |\n"
        )
        f.write("\n## Episode Attribution Summary\n\n")
        f.write("| Total Episodes | Included | Ignored | Wins | Losses | Win Rate | Sum Delta | Median Delta | Biggest Win | Biggest Loss |\n")
        f.write("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n")
        biggest_win = attribution.get("biggest_win", {}) or {}
        biggest_loss = attribution.get("biggest_loss", {}) or {}
        f.write(
            f"| {attribution.get('total_episodes', 0)} | {attribution.get('included_episodes', 0)} | "
            f"{attribution.get('ignored_episodes', 0)} | {attribution.get('win_count', 0)} | "
            f"{attribution.get('loss_count', 0)} | {_fmt_pct(attribution.get('win_rate_pct'))} | "
            f"{_fmt_pct(attribution.get('sum_delta_pct_points'))} | {_fmt_pct(attribution.get('median_delta_pct_points'))} | "
            f"{_fmt_pct(biggest_win.get('return_delta_dest_vs_baseline_pct'))} | "
            f"{_fmt_pct(biggest_loss.get('return_delta_dest_vs_baseline_pct'))} |\n"
        )
        f.write("\n## Risk-Off Episodes\n\n")
        f.write("| # | Include | Start | End | Days | Fund v1 Ret | Dest Ret | Delta | BTC Ret |\n")
        f.write("|---:|---|---|---|---:|---:|---:|---:|---:|\n")
        for r in episode_df.to_dict("records"):
            f.write(
                f"| {r['episode']} | {'YES' if r['included_in_attribution'] else 'NO'} | "
                f"{r['start']} | {r['end']} | {r['days']} | "
                f"{_fmt_pct(r.get('baseline_return_pct'))} | {_fmt_pct(r.get('destination_return_pct'))} | "
                f"{_fmt_pct(r.get('return_delta_dest_vs_baseline_pct'))} | {_fmt_pct(r.get('btc_return_pct'))} |\n"
            )
    return md


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Research-only diagnostic for one state-confirmed risk-off candidate")
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
    p.add_argument("--min-episode-days", type=int, default=2)
    p.add_argument("--stress-start", default="2022-01-01")
    p.add_argument("--stress-end", default="2022-12-31")
    p.add_argument("--out-dir", default="artifacts/state_confirmed_candidate_diagnostic")
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
    overlay = _overlay_curve(baseline, destination, risk_off, args.crypto_scale, args.capital, "candidate_overlay")

    baseline_metrics = compute_metrics(baseline, trades=[], params={"strategy_id": "baseline", "asset": "PORTFOLIO", "initial_capital": args.capital})
    summary_row = _row(
        destination_label=args.destination_label.lower(),
        trigger_dd=args.trigger_dd,
        release_dd=args.release_dd,
        crypto_scale=args.crypto_scale,
        sma_window=args.btc_sma_window,
        release_mode=args.release_mode,
        equity=overlay,
        destination=destination,
        baseline=baseline,
        risk_off=risk_off,
        baseline_metrics=baseline_metrics,
        args=args,
    )
    episodes = _annotate_episodes(
        _episode_table(risk_off),
        baseline,
        destination,
        overlay,
        btc_close,
        args.btc_sma_window,
        args.min_episode_days,
    )
    attribution = _episode_attribution(episodes, args.min_episode_days)
    md = _write_outputs(args, summary_row, episodes, attribution, baseline, destination, overlay, risk_off)

    print("=" * 132)
    print("  STATE-CONFIRMED CANDIDATE DIAGNOSTIC")
    print("=" * 132)
    print(f"  Destination      : {args.destination_label}")
    print(f"  Trigger / Release: {args.trigger_dd:.0%} / {args.release_dd:.0%}")
    print(f"  BTC trend filter : SMA{args.btc_sma_window}, release={args.release_mode}")
    print(f"  Crypto scale     : {args.crypto_scale:.0%}")
    print(f"  Min episode days : {args.min_episode_days}")
    print("-" * 132)
    print(
        f"  CAGR={summary_row['cagr_pct']:.2f}%  MaxDD={summary_row['max_drawdown_pct']:.2f}%  "
        f"Sharpe={summary_row['sharpe']:.3f}  Calmar={summary_row['calmar']:.3f}  "
        f"Stress={summary_row['stress_return_pct']:.2f}%  RiskOff={summary_row['risk_off_pct_days']:.1f}%"
    )
    print("-" * 132)
    print(
        f"  Episodes: {attribution.get('total_episodes', 0)} total | "
        f"{attribution.get('included_episodes', 0)} included | {attribution.get('ignored_episodes', 0)} ignored"
    )
    if attribution.get("included_episodes", 0):
        print(
            f"  Episode attribution: wins={attribution.get('win_count', 0)} losses={attribution.get('loss_count', 0)} "
            f"win_rate={_fmt_pct(attribution.get('win_rate_pct'))} "
            f"sum_delta={_fmt_pct(attribution.get('sum_delta_pct_points'))} "
            f"median_delta={_fmt_pct(attribution.get('median_delta_pct_points'))}"
        )
    print("-" * 132)
    if not episodes.empty:
        for r in episodes.to_dict("records"):
            include = "Y" if r["included_in_attribution"] else "N"
            print(
                f"  #{r['episode']:>2} [{include}] {r['start']} -> {r['end']} ({r['days']:>4}d)  "
                f"FundV1={_fmt_pct(r.get('baseline_return_pct')):>8}  "
                f"{args.destination_label}={_fmt_pct(r.get('destination_return_pct')):>8}  "
                f"Delta={_fmt_pct(r.get('return_delta_dest_vs_baseline_pct')):>8}  "
                f"BTC={_fmt_pct(r.get('btc_return_pct')):>8}"
            )
    print("=" * 132)
    print(f"  Summary: {md}")
    print("  Verdict: research output only; review before any integration.\n")


if __name__ == "__main__":
    main()
