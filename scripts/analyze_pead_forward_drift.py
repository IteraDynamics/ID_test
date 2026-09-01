"""Campaign #59 (planning) — post-earnings-announcement drift, Stage 2 of 2.

Reads Stage 1's combined earnings-surprise history plus the existing daily
price data, and tests the actual PEAD hypothesis: do stocks with the most
positive earnings surprises keep drifting up over the following weeks, and
the most negative keep drifting down, relative to the SPY benchmark (same
abnormal-return design as the reconstitution-effect script).

Real methodological choice, made deliberately rather than defaulted into:
ranks are built from each ticker's own STANDARDIZED surprise (z-score
against that ticker's own trailing history), not raw surprise_pct pooled
across tickers. Raw surprise magnitudes aren't comparable across companies
of very different scale, and this fund has hit the "unstandardized
cross-sectional ranking gets dominated by a few extreme observations"
failure mode more than once already this session (the COT gold percentile
bug, the crypto momentum outlier bug) -- standardizing up front is cheaper
than discovering the same failure a third time.

Causality: each event's z-score uses only that ticker's PRIOR earnings
events (a trailing/expanding window before the current one), never future
ones -- avoids the exact lookahead-in-a-percentile-computation bug the COT
gold campaign found and fixed. Events without enough prior history
(MIN_PRIOR_EVENTS_FOR_STANDARDIZATION) are excluded rather than
standardized against too little data.

Known simplification, stated rather than hidden: quintiles are formed by
pooling standardized surprises across ALL tickers and ALL time periods
together, not matched within the same earnings season. A more rigorous
design would rank only against other companies reporting in the same
window, controlling for market/sector-wide moves in that specific quarter.
Worth doing as a follow-up if this shows anything -- not done here.

No lookahead in the forward-return legs themselves: each checkpoint uses
only real subsequent trading days, and events without enough real forward
history (near the end of the priced data) are skipped, not padded.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

FORWARD_DAY_CHECKPOINTS = (1, 5, 20, 60)
MIN_PRIOR_EVENTS_FOR_STANDARDIZATION = 4
N_QUINTILES = 5


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events-file", default="data/earnings_surprise_history.csv")
    parser.add_argument("--benchmark", default="SPY")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--output-dir", default="artifacts/pead_forward_drift")
    return parser.parse_args()


def load_events(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run scripts/fetch_earnings_surprise_history.py first.")
    events = pd.read_csv(path, parse_dates=["date"])
    events["date"] = events["date"].dt.tz_localize("UTC")
    events["surprise_pct"] = pd.to_numeric(events["surprise_pct"], errors="coerce")
    events = events.dropna(subset=["surprise_pct"]).sort_values(["ticker", "date"]).reset_index(drop=True)
    return events


def add_standardized_surprise(events: pd.DataFrame) -> pd.DataFrame:
    """Per-ticker z-score against that ticker's own PRIOR surprise history
    only -- strictly causal, no lookahead into future quarters."""
    z_scores = []
    kept_mask = []

    for ticker, group in events.groupby("ticker", sort=False):
        surprises = group["surprise_pct"].to_numpy()
        for i in range(len(surprises)):
            prior = surprises[:i]
            if len(prior) < MIN_PRIOR_EVENTS_FOR_STANDARDIZATION:
                z_scores.append(np.nan)
                kept_mask.append(False)
                continue
            prior_mean = prior.mean()
            prior_std = prior.std(ddof=1)
            if prior_std == 0 or np.isnan(prior_std):
                z_scores.append(np.nan)
                kept_mask.append(False)
                continue
            z_scores.append((surprises[i] - prior_mean) / prior_std)
            kept_mask.append(True)

    events = events.copy()
    events["z_surprise"] = z_scores
    events["_standardizable"] = kept_mask
    excluded = int((~events["_standardizable"]).sum())
    print(f"Excluded {excluded}/{len(events)} events with fewer than {MIN_PRIOR_EVENTS_FOR_STANDARDIZATION} "
          f"prior same-ticker observations to standardize against.")
    return events[events["_standardizable"]].drop(columns="_standardizable").reset_index(drop=True)


def load_daily_returns(data_dir: Path, ticker: str) -> pd.Series | None:
    path = data_dir / f"{ticker.upper()}_1D.csv"
    if not path.exists():
        return None
    frame = pd.read_csv(path, parse_dates=["timestamp"])
    frame = frame.sort_values("timestamp").drop_duplicates(subset="timestamp").set_index("timestamp")
    returns = frame["close"].pct_change()
    returns.name = ticker.upper()
    return returns.dropna()


def extract_forward_abnormal_returns(
    stock_returns: pd.Series,
    benchmark_returns: pd.Series,
    event_date: pd.Timestamp,
    checkpoints: tuple[int, ...],
) -> dict[int, float] | None:
    """Cumulative abnormal return (stock - benchmark) from the trading day at
    or after event_date through each forward checkpoint. None if there isn't
    enough real forward history to reach the largest checkpoint."""
    aligned = pd.DataFrame({"stock": stock_returns, "benchmark": benchmark_returns}).dropna()
    if aligned.empty:
        return None

    trading_dates = aligned.index
    anchor_pos = int(trading_dates.searchsorted(event_date))
    max_checkpoint = max(checkpoints)
    if anchor_pos + max_checkpoint >= len(trading_dates):
        return None  # not enough real future data yet -- do not pad or extrapolate

    abnormal = (aligned["stock"] - aligned["benchmark"]).to_numpy()
    cumulative = np.cumsum(abnormal[anchor_pos : anchor_pos + max_checkpoint + 1])
    return {day: float(cumulative[day]) for day in checkpoints}


def summarize_quintile(car_by_checkpoint: pd.DataFrame, label: str) -> dict:
    n_events = int(len(car_by_checkpoint))
    if n_events == 0:
        return {"label": label, "n_events": 0}

    result: dict = {"label": label, "n_events": n_events}
    for checkpoint in FORWARD_DAY_CHECKPOINTS:
        values = car_by_checkpoint[checkpoint].to_numpy()
        t_stat, p_value = stats.ttest_1samp(values, popmean=0.0)
        result[f"day_{checkpoint}"] = {
            "mean_car": float(values.mean()),
            "median_car": float(np.median(values)),
            "t_stat": float(t_stat),
            "p_value": float(p_value),
            "win_rate": float((values > 0).mean()),
        }
    return result


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    events = load_events(Path(args.events_file))
    events = add_standardized_surprise(events)
    print(f"{len(events)} events with a valid, causally-standardized surprise z-score.\n")

    benchmark_returns = load_daily_returns(data_dir, args.benchmark)
    if benchmark_returns is None:
        raise FileNotFoundError(f"Benchmark {args.benchmark}_1D.csv not found in {data_dir}.")

    price_cache: dict[str, pd.Series | None] = {}
    rows = []
    missing_tickers: set[str] = set()
    insufficient_window = 0

    for _, event in events.iterrows():
        ticker = event["ticker"]
        if ticker not in price_cache:
            price_cache[ticker] = load_daily_returns(data_dir, ticker)
        stock_returns = price_cache[ticker]
        if stock_returns is None:
            missing_tickers.add(ticker)
            continue

        forward = extract_forward_abnormal_returns(
            stock_returns, benchmark_returns, event["date"], FORWARD_DAY_CHECKPOINTS
        )
        if forward is None:
            insufficient_window += 1
            continue

        row = {"ticker": ticker, "date": event["date"], "z_surprise": event["z_surprise"]}
        row.update(forward)
        rows.append(row)

    print(f"Tickers with no local price file: {len(missing_tickers)}")
    print(f"Events skipped for insufficient forward window: {insufficient_window}")

    if not rows:
        raise RuntimeError("No events survived filtering -- nothing to analyze.")

    car_frame = pd.DataFrame(rows)
    car_frame["quintile"] = pd.qcut(car_frame["z_surprise"], N_QUINTILES, labels=False, duplicates="drop")
    n_quintiles_actual = car_frame["quintile"].nunique()
    print(f"\n{len(car_frame)} events with a full forward window, split into {n_quintiles_actual} quintiles by z-surprise.\n")

    results = {}
    for quintile in sorted(car_frame["quintile"].dropna().unique()):
        subset = car_frame[car_frame["quintile"] == quintile]
        label = f"Q{int(quintile) + 1}"
        results[label] = summarize_quintile(subset, label)

        r = results[label]
        z_range = f"[{subset['z_surprise'].min():.2f}, {subset['z_surprise'].max():.2f}]"
        print(f"--- {label} (n={r['n_events']}, z_surprise range {z_range}) ---")
        for checkpoint in FORWARD_DAY_CHECKPOINTS:
            d = r[f"day_{checkpoint}"]
            print(
                f"  day+{checkpoint:<3} mean_car={d['mean_car']:+.2%} t={d['t_stat']:+.2f} "
                f"p={d['p_value']:.4f} win_rate={d['win_rate']:.2%}"
            )
        print()

    # The actual PEAD test: does the top quintile minus bottom quintile spread
    # grow over time (drift), and is it significant at the longest checkpoint?
    top_label = f"Q{n_quintiles_actual}"
    bottom_label = "Q1"
    if top_label in results and bottom_label in results:
        top_subset = car_frame[car_frame["quintile"] == n_quintiles_actual - 1]
        bottom_subset = car_frame[car_frame["quintile"] == 0]
        print(f"--- Spread: {top_label} (highest surprise) minus {bottom_label} (lowest) ---")
        for checkpoint in FORWARD_DAY_CHECKPOINTS:
            top_vals = top_subset[checkpoint].to_numpy()
            bottom_vals = bottom_subset[checkpoint].to_numpy()
            t_stat, p_value = stats.ttest_ind(top_vals, bottom_vals, equal_var=False)
            spread = top_vals.mean() - bottom_vals.mean()
            print(f"  day+{checkpoint:<3} spread={spread:+.2%} t={t_stat:+.2f} p={p_value:.4f}")

    (output_dir / "summary.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    car_frame.to_csv(output_dir / "event_level_car.csv", index=False)
    print(f"\nWrote results to {output_dir}/")


if __name__ == "__main__":
    main()
