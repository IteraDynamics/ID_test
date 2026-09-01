"""Campaign #59 (planning) — PEAD out-of-sample confirmation + cluster bootstrap, Stage 3.

Reads Stage 2's event-level output (artifacts/pead_forward_drift/event_level_car.csv
-- ticker, date, z_surprise, and the day+1/+5/+20/+60 cumulative abnormal
returns already computed against SPY) and runs two checks the backtest
alone couldn't answer, targeting the two specific caveats flagged after
the winsorization fix held up:

1. TIME-BASED DISCOVERY/CONFIRMATION SPLIT. Quintiles pooled all ~24 years
   of events together in Stage 2 -- part of the spread could reflect which
   stocks happened to land in the top quintile during generally strong
   market periods, not a pure surprise effect. Splits events at
   --split-date (default 2020-01-01), re-forms quintiles SEPARATELY within
   each period's own cross-section (never reusing discovery-period quintile
   boundaries on confirmation data), and reports the Q5-Q1 spread in each
   period side by side. If the effect is real, both periods should show a
   similar-shaped, similarly-signed spread; if it's a period-specific
   artifact, discovery and confirmation should disagree.

2. CLUSTER (BY-TICKER) BOOTSTRAP. Stage 2's t-tests implicitly treat every
   event as independent, but the same ticker contributes many quarters,
   and forward windows can mildly overlap -- the true effective sample
   size is smaller than the raw event count. This resamples TICKERS (not
   individual events) with replacement, keeping each selected ticker's
   full event history intact so within-ticker correlation isn't broken,
   re-forms quintiles fresh on each resampled set, and builds an empirical
   distribution of the Q5-Q1 spread across replicates -- a 90% confidence
   interval and the fraction of replicates where the spread is <= 0, both
   of which are more honest under clustering than the naive t-test's
   i.i.d. assumption.

Deterministic: a fixed RNG seed means the bootstrap replicates are
reproducible byte-for-byte given the same input file, per this repo's
own replay-verification convention.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

FORWARD_DAY_CHECKPOINTS = (1, 5, 20, 60)
N_QUINTILES = 5
MIN_EVENTS_PER_SPLIT = N_QUINTILES * 20  # arbitrary sanity floor before quintiles are meaningful
RNG_SEED = 20260901  # fixed for replay determinism, not tuned


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-level-car-file", default="artifacts/pead_forward_drift/event_level_car.csv")
    parser.add_argument("--split-date", default="2020-01-01")
    parser.add_argument("--bootstrap-replicates", type=int, default=1000)
    parser.add_argument("--output-dir", default="artifacts/pead_oos_bootstrap")
    return parser.parse_args()


def load_events(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run scripts/analyze_pead_forward_drift.py first -- "
            "this reuses its event-level output rather than recomputing CAR from scratch."
        )
    events = pd.read_csv(path, parse_dates=["date"])
    if events["date"].dt.tz is None:
        events["date"] = events["date"].dt.tz_localize("UTC")
    required = {"ticker", "date", "z_surprise"} | {str(cp) for cp in FORWARD_DAY_CHECKPOINTS}
    missing = required - set(events.columns)
    if missing:
        raise ValueError(f"{path} is missing expected columns: {missing}. Actual columns: {list(events.columns)}")
    return events.reset_index(drop=True)


def form_quintiles_and_spread(subset: pd.DataFrame) -> dict:
    """Re-forms quintiles from THIS subset's own z_surprise distribution --
    never reuses quintile boundaries computed elsewhere. Returns the Q5-Q1
    spread and significance at each checkpoint, or {"insufficient": True}
    if the subset is too small for quintiles to be meaningful."""
    if len(subset) < MIN_EVENTS_PER_SPLIT:
        return {"insufficient": True, "n_events": int(len(subset))}

    subset = subset.copy()
    subset["_quintile"] = pd.qcut(subset["z_surprise"], N_QUINTILES, labels=False, duplicates="drop")
    n_quintiles_actual = subset["_quintile"].nunique()
    if n_quintiles_actual < 2:
        return {"insufficient": True, "n_events": int(len(subset)), "reason": "z_surprise too degenerate to split"}

    top = subset[subset["_quintile"] == subset["_quintile"].max()]
    bottom = subset[subset["_quintile"] == subset["_quintile"].min()]

    result: dict = {"n_events": int(len(subset)), "n_top": int(len(top)), "n_bottom": int(len(bottom))}
    for checkpoint in FORWARD_DAY_CHECKPOINTS:
        col = str(checkpoint)
        top_vals = top[col].to_numpy()
        bottom_vals = bottom[col].to_numpy()
        spread = float(top_vals.mean() - bottom_vals.mean())
        t_stat, p_value = stats.ttest_ind(top_vals, bottom_vals, equal_var=False)
        result[f"day_{checkpoint}"] = {"spread": spread, "t_stat": float(t_stat), "p_value": float(p_value)}
    return result


def run_time_split(events: pd.DataFrame, split_date: str) -> dict:
    split_ts = pd.Timestamp(split_date, tz="UTC")
    discovery = events[events["date"] < split_ts]
    confirmation = events[events["date"] >= split_ts]
    return {
        "discovery": {"period": f"< {split_date}", **form_quintiles_and_spread(discovery)},
        "confirmation": {"period": f">= {split_date}", **form_quintiles_and_spread(confirmation)},
    }


def run_cluster_bootstrap(events: pd.DataFrame, n_replicates: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    unique_tickers = events["ticker"].unique()
    n_tickers = len(unique_tickers)
    ticker_to_indices = {ticker: events.index[events["ticker"] == ticker].to_numpy() for ticker in unique_tickers}

    replicate_spreads: dict[int, list[float]] = {cp: [] for cp in FORWARD_DAY_CHECKPOINTS}
    skipped_replicates = 0

    for _ in range(n_replicates):
        sampled_tickers = rng.choice(unique_tickers, size=n_tickers, replace=True)
        sampled_indices = np.concatenate([ticker_to_indices[t] for t in sampled_tickers])
        resample = events.loc[sampled_indices]

        result = form_quintiles_and_spread(resample)
        if result.get("insufficient"):
            skipped_replicates += 1
            continue
        for checkpoint in FORWARD_DAY_CHECKPOINTS:
            replicate_spreads[checkpoint].append(result[f"day_{checkpoint}"]["spread"])

    summary = {"n_replicates_requested": n_replicates, "n_replicates_skipped": skipped_replicates}
    for checkpoint in FORWARD_DAY_CHECKPOINTS:
        values = np.array(replicate_spreads[checkpoint])
        summary[f"day_{checkpoint}"] = {
            "n_valid_replicates": int(len(values)),
            "mean_spread": float(values.mean()),
            "ci_5th_pct": float(np.percentile(values, 5)),
            "ci_95th_pct": float(np.percentile(values, 95)),
            "fraction_replicates_spread_le_zero": float((values <= 0).mean()),
        }
    return summary


def _print_split_result(label: str, result: dict) -> None:
    if result.get("insufficient"):
        print(f"  {label}: insufficient events ({result.get('n_events', 0)}) to form quintiles.")
        return
    print(f"  {label}: n={result['n_events']} (top={result['n_top']}, bottom={result['n_bottom']})")
    for checkpoint in FORWARD_DAY_CHECKPOINTS:
        d = result[f"day_{checkpoint}"]
        print(f"    day+{checkpoint:<3} spread={d['spread']:+.2%} t={d['t_stat']:+.2f} p={d['p_value']:.4f}")


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    events = load_events(Path(args.event_level_car_file))
    print(f"Loaded {len(events)} events with pre-computed CAR from Stage 2.\n")

    print(f"=== Part A: time-based discovery/confirmation split at {args.split_date} ===")
    time_split_result = run_time_split(events, args.split_date)
    print("Discovery (pre-split, quintiles formed on this period alone):")
    _print_split_result("discovery", time_split_result["discovery"])
    print("Confirmation (post-split, quintiles formed independently on this period alone):")
    _print_split_result("confirmation", time_split_result["confirmation"])
    print()

    print(f"=== Part B: cluster (by-ticker) bootstrap, {args.bootstrap_replicates} replicates ===")
    bootstrap_result = run_cluster_bootstrap(events, args.bootstrap_replicates, RNG_SEED)
    print(f"  {bootstrap_result['n_replicates_skipped']}/{args.bootstrap_replicates} replicates skipped (insufficient events after resampling)")
    for checkpoint in FORWARD_DAY_CHECKPOINTS:
        b = bootstrap_result[f"day_{checkpoint}"]
        print(
            f"  day+{checkpoint:<3} mean_spread={b['mean_spread']:+.2%} "
            f"90% CI=[{b['ci_5th_pct']:+.2%}, {b['ci_95th_pct']:+.2%}] "
            f"P(spread<=0)={b['fraction_replicates_spread_le_zero']:.3f}"
        )

    combined = {"time_split": time_split_result, "cluster_bootstrap": bootstrap_result}
    (output_dir / "summary.json").write_text(json.dumps(combined, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote results to {output_dir}/")


if __name__ == "__main__":
    main()
