"""Campaign #58 (planning) — S&P 500 reconstitution effect, Stage 2 of 2.

Reads data/sp500_reconstitution_events.csv (Stage 1's event calendar) and,
for every event with available price data, computes the stock's abnormal
return around the event date -- its own return minus SPY's return over the
same trading days, isolating the reconstitution-specific price pressure
from ordinary market movement.

Date semantics caveat, stated honestly rather than assumed: the source
event calendar's date column was not independently confirmed to be the
announcement date specifically (vs. the effective date) -- see Stage 1's
own docstring. This script treats it as "the anchor date" and reports the
full day-by-day cumulative abnormal return (CAR) shape around it, which
lets the announcement-vs-effective question be read off the actual shape
(a pop concentrated before day 0 looks different from one concentrated
after it) rather than asserted in advance.

No lookahead in the per-day return computation itself: each day's return
uses only that day's own close-to-close move. The event STUDY design
looks at days after the anchor date by construction (that is the point --
whether price pressure continues after the event becomes public) and is
not a trading strategy by itself; whether any of this is tradeable in
real time is a separate question this script does not answer.

Missing tickers (delisted, renamed, or otherwise unavailable) are skipped
with a logged count, not silently dropped -- expected per Stage 1's own
docstring, not a bug here either.

Deterministic and replay-safe: same input files -> byte-identical output.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


PRE_EVENT_DAYS = 5
POST_EVENT_DAYS = 20
MIN_WINDOW_DAYS = PRE_EVENT_DAYS + POST_EVENT_DAYS  # require a full window, no partial-window events


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events-file", default="data/sp500_reconstitution_events.csv")
    parser.add_argument("--benchmark", default="SPY", help="Ticker used as the market-return benchmark.")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--output-dir", default="artifacts/sp500_reconstitution_effect")
    return parser.parse_args()


def load_daily_returns(data_dir: Path, ticker: str) -> pd.Series | None:
    path = data_dir / f"{ticker.upper()}_1D.csv"
    if not path.exists():
        return None
    frame = pd.read_csv(path, parse_dates=["timestamp"])
    frame = frame.sort_values("timestamp").drop_duplicates(subset="timestamp")
    frame = frame.set_index("timestamp")
    returns = frame["close"].pct_change()
    returns.name = ticker.upper()
    return returns.dropna()


def extract_event_window(
    stock_returns: pd.Series,
    benchmark_returns: pd.Series,
    event_date: pd.Timestamp,
) -> pd.Series | None:
    """Abnormal daily returns for [-PRE_EVENT_DAYS, +POST_EVENT_DAYS] trading days
    around event_date, aligned on shared trading dates. None if either series
    lacks enough history on either side of the event to fill the full window."""
    aligned = pd.DataFrame({"stock": stock_returns, "benchmark": benchmark_returns}).dropna()
    if aligned.empty:
        return None

    trading_dates = aligned.index
    anchor_positions = trading_dates.searchsorted(event_date)
    if anchor_positions >= len(trading_dates):
        return None  # event is after all available data
    anchor_pos = int(anchor_positions)

    start_pos = anchor_pos - PRE_EVENT_DAYS
    end_pos = anchor_pos + POST_EVENT_DAYS
    if start_pos < 0 or end_pos >= len(trading_dates):
        return None  # not enough history on one side to fill the full window

    window = aligned.iloc[start_pos : end_pos + 1]
    if len(window) != MIN_WINDOW_DAYS + 1:
        return None

    abnormal = window["stock"] - window["benchmark"]
    abnormal.index = range(-PRE_EVENT_DAYS, POST_EVENT_DAYS + 1)  # relative trading-day offset
    return abnormal


def summarize_group(car_by_offset: pd.DataFrame, label: str) -> dict:
    """car_by_offset: rows = events, columns = relative trading-day offset,
    values = that day's abnormal return. Aggregates into the day-by-day mean
    abnormal return and its cumulative sum (the CAR curve), plus a t-test on
    total window abnormal return per event."""
    n_events = int(len(car_by_offset))
    if n_events == 0:
        return {"label": label, "n_events": 0}

    mean_abnormal_by_day = car_by_offset.mean(axis=0)
    cumulative_abnormal_by_day = mean_abnormal_by_day.cumsum()

    total_car_per_event = car_by_offset.sum(axis=1)  # one number per event: full-window CAR
    t_stat, p_value = stats.ttest_1samp(total_car_per_event.to_numpy(), popmean=0.0)

    return {
        "label": label,
        "n_events": n_events,
        "mean_total_car": float(total_car_per_event.mean()),
        "median_total_car": float(total_car_per_event.median()),
        "t_stat": float(t_stat),
        "p_value": float(p_value),
        "win_rate": float((total_car_per_event > 0).mean()),
        "car_curve_by_offset": {int(k): float(v) for k, v in cumulative_abnormal_by_day.items()},
    }


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    events_path = Path(args.events_file)
    if not events_path.exists():
        raise FileNotFoundError(
            f"{events_path} not found. Run scripts/fetch_sp500_reconstitution_events.py first."
        )
    events = pd.read_csv(events_path, parse_dates=["date"])
    # Price data (download_equity_data.py's output) carries UTC-aware timestamps;
    # the events CSV's plain "YYYY-MM-DD" parses tz-naive by default. Localize to
    # match, or every comparison against the price index raises downstream.
    events["date"] = events["date"].dt.tz_localize("UTC")

    benchmark_returns = load_daily_returns(data_dir, args.benchmark)
    if benchmark_returns is None:
        raise FileNotFoundError(
            f"Benchmark {args.benchmark}_1D.csv not found in {data_dir}. "
            "This is the market-return series every abnormal-return calculation needs."
        )

    price_cache: dict[str, pd.Series | None] = {}
    windows_by_action: dict[str, list[pd.Series]] = {"add": [], "remove": []}
    missing_tickers: set[str] = set()
    insufficient_window_events = 0

    for _, event in events.iterrows():
        ticker = str(event["ticker"])
        action = str(event["action"])
        if action not in windows_by_action:
            continue

        if ticker not in price_cache:
            price_cache[ticker] = load_daily_returns(data_dir, ticker)
        stock_returns = price_cache[ticker]

        if stock_returns is None:
            missing_tickers.add(ticker)
            continue

        window = extract_event_window(stock_returns, benchmark_returns, event["date"])
        if window is None:
            insufficient_window_events += 1
            continue

        windows_by_action[action].append(window)

    print(f"Events in calendar: {len(events)}")
    print(f"Tickers with no local price file: {len(missing_tickers)}")
    if missing_tickers:
        preview = sorted(missing_tickers)[:15]
        print(f"  e.g.: {preview}{' ...' if len(missing_tickers) > 15 else ''}")
    print(f"Events skipped for insufficient window history: {insufficient_window_events}")
    print()

    results = {}
    for action, windows in windows_by_action.items():
        if not windows:
            results[action] = {"label": action, "n_events": 0}
            continue
        car_by_offset = pd.DataFrame(windows)
        results[action] = summarize_group(car_by_offset, action)

        r = results[action]
        print(f"--- {action} (n={r['n_events']}) ---")
        if r["n_events"] > 0:
            print(
                f"  mean_total_car={r['mean_total_car']:+.2%} "
                f"median={r['median_total_car']:+.2%} "
                f"t={r['t_stat']:+.2f} p={r['p_value']:.4f} "
                f"win_rate={r['win_rate']:.2%}"
            )
            print(
                f"  CAR at day 0 (event date close): {r['car_curve_by_offset'][0]:+.2%} | "
                f"CAR at day +{POST_EVENT_DAYS}: {r['car_curve_by_offset'][POST_EVENT_DAYS]:+.2%}"
            )
        print()

    (output_dir / "summary.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    (output_dir / "missing_tickers.json").write_text(
        json.dumps(sorted(missing_tickers), indent=2), encoding="utf-8"
    )
    print(f"Wrote results to {output_dir}/")


if __name__ == "__main__":
    main()
