"""COT gold positioning as a contrarian signal for GLD -- first real look, not a strategy yet.

Candidate: CFTC Commitment of Traders (Legacy Futures-Only) report for "GOLD - COMMODITY
EXCHANGE INC." (standard 100oz COMEX contract -- the one GLD's own price is fundamentally
anchored to). Signal: Non-Commercial (speculative) net position as a percentage of open
interest, ranked against its own trailing history -- extreme readings are the candidate
contrarian indicator, not the raw level, since gold's market size and participant base have
changed enormously since 1986.

Lookahead discipline -- the one thing this analysis cannot get wrong: the COT report's "as of"
date is a Tuesday, but the report is not PUBLISHED until the following Friday (CFTC's own
long-standing weekly release schedule, 3:30pm ET). A signal computed from a report is not
actually usable/tradeable until that Friday release, not the Tuesday the positions describe.
This script shifts every report's usable date forward by that lag before comparing to any
forward GLD return -- using the Tuesday date directly would be lookahead, the same mistake
this program's own governance exists to catch elsewhere (Campaign #52's whole premise).

Percentile ranking is computed against a TRAILING ROLLING window (causal) -- at each report
date, the percentile is computed only against reports strictly before it and within the
trailing window, never using future data to rank a past observation.

Correction, 2026-08-25: the first real run used an EXPANDING (since-1986) window instead of a
rolling one, and it was wrong. Gold's speculative open interest has grown roughly monotonically
as the market matured over 40 years, so ranking a recent reading against mostly-thin, mostly-
smaller early-history data mechanically inflates recent percentiles regardless of whether
positioning is actually extreme for the market's current scale. This showed up as a real,
checkable failure: the "top quintile" (percentile >= 0.80) held 864 of 1866 observations (46%,
not the ~20% a real quintile split implies) -- the percentile was not behaving like a percentile.
Fixed by bounding the ranking window to ROLLING_PERCENTILE_WINDOW_WEEKS trailing reports, which
adapts to the market's current scale instead of comparing across eras. A quintile-balance
canary (see main()) now prints a warning if any quintile still deviates far from ~20%, so this
failure mode cannot silently recur.

Observation/analysis only. Computes no trading signal, makes no economic claim -- this is
discovery-stage exploration of whether the premise is worth pursuing further, not a backtest
of a tradeable rule.
"""

from __future__ import annotations

import argparse
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

GOLD_MARKET_NAME = "GOLD - COMMODITY EXCHANGE INC."
REPORT_RELEASE_LAG_DAYS = 3  # Tuesday "as of" -> Friday publication, CFTC's standing schedule
MIN_HISTORY_FOR_PERCENTILE = 52  # ~1 year of weekly reports before trusting a percentile rank
# Trailing window for the percentile rank, in weekly reports. 156 = 3 years: long enough for a
# stable rank distribution, short enough to adapt to the market's current scale rather than
# comparing today's positioning against 1986-era open interest (see the 2026-08-25 correction
# above -- the expanding-window version this replaced was demonstrably not producing a uniform
# percentile). Chosen once and documented, not tuned against the correlation result.
ROLLING_PERCENTILE_WINDOW_WEEKS = 156
FORWARD_HORIZONS_WEEKS = (4, 12, 26)
QUINTILE_BALANCE_WARN_THRESHOLD = 0.10  # warn if any quintile's share is off ~20% by more than this


def load_cot_gold(cot_csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(cot_csv_path, low_memory=False)
    gold = df[df["Market and Exchange Names"] == GOLD_MARKET_NAME].copy()
    if gold.empty:
        raise ValueError(
            f"No rows matched {GOLD_MARKET_NAME!r} -- the market name may have changed. "
            f"Re-check scripts/fetch_cot_legacy_futures_history.py's output for the real name."
        )
    gold["report_date"] = pd.to_datetime(gold["As of Date in Form YYYY-MM-DD"])
    gold = gold.sort_values("report_date").drop_duplicates(subset="report_date", keep="last")

    gold["noncomm_net"] = (
        gold["Noncommercial Positions-Long (All)"] - gold["Noncommercial Positions-Short (All)"]
    )
    gold["open_interest"] = gold["Open Interest (All)"]
    gold["noncomm_net_pct_oi"] = gold["noncomm_net"] / gold["open_interest"]

    gold["usable_date"] = gold["report_date"] + timedelta(days=REPORT_RELEASE_LAG_DAYS)

    return gold[["report_date", "usable_date", "noncomm_net", "open_interest", "noncomm_net_pct_oi"]].reset_index(drop=True)


def rolling_percentile(series: pd.Series, window: int, min_periods: int) -> pd.Series:
    """Causal percentile rank: at position i, ranks value[i] against value[max(0,i-window):i]
    only (strictly prior history, bounded to the trailing window, never including itself or the
    future). Returns NaN before min_periods.

    Bounding the window (rather than using all prior history back to 1986) matters for a series
    like gold's speculative open interest that has grown roughly monotonically as the market
    matured -- an unbounded expanding window ranks recent readings against a mostly thinner,
    smaller-market past, inflating recent percentiles independent of whether positioning is
    actually extreme for the market's current scale. See the 2026-08-25 correction note at the
    top of this file for the real, checkable failure this produced (a 46%-vs-20% quintile)."""
    values = series.to_numpy()
    n = len(values)
    out = np.full(n, np.nan)
    for i in range(min_periods, n):
        prior = values[max(0, i - window):i]
        out[i] = (prior < values[i]).mean()
    return pd.Series(out, index=series.index)


def load_gld(gld_csv_path: str) -> pd.Series:
    df = pd.read_csv(gld_csv_path, index_col="timestamp", parse_dates=True)
    # download_equity_data.py writes UTC-aware timestamps; the COT side (plain "YYYY-MM-DD"
    # strings, no offset) parses tz-naive. Normalize to naive here rather than duplicate
    # research/harness/data_loader.py's own tz handling for a single price column.
    if df.index.tz is not None:
        df.index = df.index.tz_convert(None)
    return df["close"]


def forward_return(gld_close: pd.Series, from_date: pd.Timestamp, weeks: int) -> float | None:
    """Return from the first GLD close on/after from_date to the first GLD close on/after
    from_date + weeks*7 days. None if either endpoint is outside the available data."""
    start_candidates = gld_close.index[gld_close.index >= from_date]
    if len(start_candidates) == 0:
        return None
    start_date = start_candidates[0]
    end_target = start_date + timedelta(weeks=weeks)
    end_candidates = gld_close.index[gld_close.index >= end_target]
    if len(end_candidates) == 0:
        return None
    end_date = end_candidates[0]
    return float(gld_close.loc[end_date] / gld_close.loc[start_date] - 1.0)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--cot-csv", default="data/cot_legacy_futures_only_1986_present.csv")
    p.add_argument("--gld-csv", default="data/GLD_1D.csv")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    gold = load_cot_gold(args.cot_csv)
    print(f"Loaded {len(gold)} weekly Gold COT reports, {gold['report_date'].min().date()} -> "
          f"{gold['report_date'].max().date()}")

    gold["percentile"] = rolling_percentile(
        gold["noncomm_net_pct_oi"], ROLLING_PERCENTILE_WINDOW_WEEKS, MIN_HISTORY_FOR_PERCENTILE
    )
    gold = gold.dropna(subset=["percentile"]).reset_index(drop=True)
    print(f"{len(gold)} reports have enough trailing history for a percentile rank "
          f"(first {MIN_HISTORY_FOR_PERCENTILE} dropped as warmup, "
          f"{ROLLING_PERCENTILE_WINDOW_WEEKS}-week trailing window)")

    gld_close = load_gld(args.gld_csv)
    print(f"GLD price data: {gld_close.index.min().date()} -> {gld_close.index.max().date()}")

    for weeks in FORWARD_HORIZONS_WEEKS:
        gold[f"fwd_ret_{weeks}w"] = gold["usable_date"].apply(
            lambda d: forward_return(gld_close, d, weeks)
        )

    print(f"\n{'='*70}")
    print("Correlation: percentile rank of speculative net positioning vs forward GLD return")
    print("(negative correlation = contrarian signal working: high positioning -> lower forward return)")
    print(f"{'='*70}")
    for weeks in FORWARD_HORIZONS_WEEKS:
        col = f"fwd_ret_{weeks}w"
        valid = gold.dropna(subset=[col])
        if len(valid) < 30:
            print(f"  {weeks}w horizon: only {len(valid)} valid observations, too few to report")
            continue
        corr = valid["percentile"].corr(valid[col])
        print(f"  {weeks}w horizon: n={len(valid)}  corr(percentile, fwd_ret)={corr:+.4f}")

    print(f"\n{'='*70}")
    print("Extreme-quintile comparison, 12-week horizon (most standard COT contrarian framing)")
    print(f"{'='*70}")
    col = "fwd_ret_12w"
    valid = gold.dropna(subset=[col])
    if len(valid) >= 30:
        top_quintile = valid[valid["percentile"] >= 0.80]
        bottom_quintile = valid[valid["percentile"] <= 0.20]
        middle = valid[(valid["percentile"] > 0.20) & (valid["percentile"] < 0.80)]
        for label, subset in (("Top quintile (crowded long)", top_quintile),
                               ("Bottom quintile (crowded short)", bottom_quintile),
                               ("Middle 60%", middle)):
            share = len(subset) / len(valid) if len(valid) else 0.0
            if len(subset) == 0:
                print(f"  {label}: no observations")
                continue
            print(f"  {label}: n={len(subset)} ({share*100:.1f}% of sample)  "
                  f"mean fwd 12w return={subset[col].mean()*100:+.2f}%  "
                  f"median={subset[col].median()*100:+.2f}%")
        # Canary: a real quintile split should land near 20%/20%/60%. If the rolling window is
        # still not producing a roughly uniform percentile (the exact failure the expanding-
        # window version had), say so loudly instead of letting a skewed split pass unnoticed.
        top_share = len(top_quintile) / len(valid) if len(valid) else 0.0
        bottom_share = len(bottom_quintile) / len(valid) if len(valid) else 0.0
        if abs(top_share - 0.20) > QUINTILE_BALANCE_WARN_THRESHOLD or \
           abs(bottom_share - 0.20) > QUINTILE_BALANCE_WARN_THRESHOLD:
            print(f"  WARNING: quintile shares are skewed (top={top_share*100:.1f}%, "
                  f"bottom={bottom_share*100:.1f}%, expected ~20% each) -- the percentile is "
                  f"still not behaving like a percentile. Do not trust the comparison above "
                  f"until this is understood.")
    else:
        print("  Too few valid observations for the 12w horizon.")

    print("\nThis is discovery-stage only. No trading signal, no economic claim -- next step if")
    print("this looks real is proper causal-only power/significance testing, not eyeballing a")
    print("correlation coefficient.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
