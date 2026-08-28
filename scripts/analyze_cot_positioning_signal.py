"""COT speculative positioning as a signal for a CFTC-tracked instrument's underlying ETF/price
series -- generalized from scripts/analyze_cot_gold_positioning.py (COT gold, CLOSED 2026-08-25
as a clean discovery-stage null against GLD).

Reuses that script's methodology unchanged -- rolling causal percentile (not expanding; the
2026-08-25 gold correction found an expanding window mechanically inflates recent percentiles as
a market's open interest grows over decades), the report-release lag (Tuesday "as of" date not
usable until the following Friday), and the quintile-balance canary -- against a DIFFERENT CFTC
market and a DIFFERENT price series, passed as arguments instead of hardcoded to gold/GLD.

Motivation: the full COT dataset already downloaded (scripts/fetch_cot_legacy_futures_history.py,
287,779 rows, every CFTC-tracked market since 1986) was only ever filtered to gold. Testing the
same hypothesis against equity index futures positioning (S&P 500 / Nasdaq-100) ties it directly
to SPY and QQQ, two of Core v1's six LIVE sleeves -- unlike gold, which was one sleeve chosen
somewhat arbitrarily. No new data acquisition needed for the COT side; the price side reuses
scripts/download_equity_data.py's existing output format.

This is a genuinely separate test from the closed gold result, not a workaround for it: gold's
null was a statistical finding specific to that instrument, not a structural gate failure -- the
same pipeline applied to a different market is ordinary discovery work, not routing around a
failed check.

Observation/analysis only. No trading signal, no economic claim.
"""

from __future__ import annotations

import argparse
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

REPORT_RELEASE_LAG_DAYS = 3  # Tuesday "as of" -> Friday publication, CFTC's standing schedule
MIN_HISTORY_FOR_PERCENTILE = 52  # ~1 year of weekly reports before trusting a percentile rank
ROLLING_PERCENTILE_WINDOW_WEEKS = 156  # 3 years -- see analyze_cot_gold_positioning.py's
                                        # 2026-08-25 correction for why this must be bounded
FORWARD_HORIZONS_WEEKS = (4, 12, 26)
QUINTILE_BALANCE_WARN_THRESHOLD = 0.10  # warn if any quintile's share is off ~20% by more than this


def load_cot_market(cot_csv_path: str, market_name: str) -> pd.DataFrame:
    df = pd.read_csv(cot_csv_path, low_memory=False)
    market = df[df["Market and Exchange Names"] == market_name].copy()
    if market.empty:
        raise ValueError(
            f"No rows matched {market_name!r} -- check the real market name against a fresh "
            f"grep of {cot_csv_path} before assuming this string. Market names in this dataset "
            f"do not always match what you'd guess from memory (this exact mistake already "
            f"happened once this session, with gold's own market name)."
        )
    market["report_date"] = pd.to_datetime(market["As of Date in Form YYYY-MM-DD"])
    market = market.sort_values("report_date").drop_duplicates(subset="report_date", keep="last")

    market["noncomm_net"] = (
        market["Noncommercial Positions-Long (All)"] - market["Noncommercial Positions-Short (All)"]
    )
    market["open_interest"] = market["Open Interest (All)"]
    market["noncomm_net_pct_oi"] = market["noncomm_net"] / market["open_interest"]
    market["usable_date"] = market["report_date"] + timedelta(days=REPORT_RELEASE_LAG_DAYS)

    return market[["report_date", "usable_date", "noncomm_net", "open_interest",
                    "noncomm_net_pct_oi"]].reset_index(drop=True)


def rolling_percentile(series: pd.Series, window: int, min_periods: int) -> pd.Series:
    """Causal percentile rank: at position i, ranks value[i] against value[max(0,i-window):i]
    only (strictly prior history, bounded to the trailing window). Returns NaN before
    min_periods. Unchanged from analyze_cot_gold_positioning.py -- already proven correct there,
    including the quintile-balance canary this script also carries forward."""
    values = series.to_numpy()
    n = len(values)
    out = np.full(n, np.nan)
    for i in range(min_periods, n):
        prior = values[max(0, i - window):i]
        out[i] = (prior < values[i]).mean()
    return pd.Series(out, index=series.index)


def load_price(price_csv_path: str) -> pd.Series:
    df = pd.read_csv(price_csv_path, index_col="timestamp", parse_dates=True)
    # download_equity_data.py writes UTC-aware timestamps; the COT side (plain "YYYY-MM-DD"
    # strings, no offset) parses tz-naive. Normalize to naive here -- the exact fix
    # analyze_cot_gold_positioning.py needed after a real tz-comparison crash (2026-08-25).
    if df.index.tz is not None:
        df.index = df.index.tz_convert(None)
    return df["close"]


def forward_return(price_close: pd.Series, from_date: pd.Timestamp, weeks: int) -> float | None:
    """Return from the first close on/after from_date to the first close on/after
    from_date + weeks*7 days. None if either endpoint is outside the available data."""
    start_candidates = price_close.index[price_close.index >= from_date]
    if len(start_candidates) == 0:
        return None
    start_date = start_candidates[0]
    end_target = start_date + timedelta(weeks=weeks)
    end_candidates = price_close.index[price_close.index >= end_target]
    if len(end_candidates) == 0:
        return None
    end_date = end_candidates[0]
    return float(price_close.loc[end_date] / price_close.loc[start_date] - 1.0)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--cot-csv", default="data/cot_legacy_futures_only_1986_present.csv")
    p.add_argument("--market-name", required=True,
                   help='Exact "Market and Exchange Names" value, e.g. from a grep of --cot-csv. '
                        "Do not guess this from memory.")
    p.add_argument("--price-csv", required=True, help="e.g. data/SPY_1D.csv")
    p.add_argument("--label", default=None, help="Display label, defaults to --market-name.")
    p.add_argument("--dump-weeks", type=int, default=None,
                   help="Print distribution detail, extreme-observation dates, and the "
                        "correlation with/without the single most extreme forward-return "
                        "observation for this horizon (e.g. 12) -- the same outlier-robustness "
                        "check the crypto momentum analysis needed before trusting an aggregate "
                        "number.")
    return p.parse_args(argv)


def dump_extreme_observations(valid: pd.DataFrame, col: str, label: str, weeks: int, top_n: int = 8) -> None:
    """Distribution detail and extreme-date breakdown for one forward-return horizon -- checks
    whether an aggregate correlation is a broad relationship or a few macro episodes (2018 Q4,
    2020 COVID, 2022 bear) doing most of the work, the same category of check that unraveled the
    crypto cross-sectional momentum "reversal" finding on 2026-08-26."""
    print(f"\n{'='*70}")
    print(f"Diagnostic dump: {label}, {weeks}w forward return ({len(valid)} observations)")
    print(f"{'='*70}")
    print(valid[col].describe().to_string())
    print(f"skew: {valid[col].skew():.3f}")

    full_corr = valid["percentile"].corr(valid[col])
    full_spearman = valid["percentile"].corr(valid[col], method="spearman")
    most_extreme_idx = valid[col].abs().idxmax()
    without_extreme = valid.drop(most_extreme_idx)
    corr_excl = without_extreme["percentile"].corr(without_extreme[col])
    spearman_excl = without_extreme["percentile"].corr(without_extreme[col], method="spearman")
    print(f"\nfull pearson: {full_corr:+.4f}   full spearman: {full_spearman:+.4f}")
    print(f"excluding single most extreme observation "
          f"({valid.loc[most_extreme_idx, 'usable_date'].date()}, "
          f"fwd_ret={valid.loc[most_extreme_idx, col]*100:+.2f}%): "
          f"pearson={corr_excl:+.4f}  spearman={spearman_excl:+.4f}")
    print("(pearson can be inflated by a few extreme-MAGNITUDE returns even without one single")
    print("point dominating; spearman only uses rank, so it isn't -- if pearson stays negative")
    print("but spearman is much weaker, the relationship is more magnitude-driven than broad.)")

    print(f"\nTop {top_n} most extreme observations by |{col}|:")
    top = valid.reindex(valid[col].abs().sort_values(ascending=False).index[:top_n])
    for _, row in top.iterrows():
        print(f"  {row['usable_date'].date()}: percentile={row['percentile']:.2f}  "
              f"{col}={row[col]*100:+.2f}%")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    label = args.label or args.market_name

    market = load_cot_market(args.cot_csv, args.market_name)
    print(f"Loaded {len(market)} weekly {label} COT reports, {market['report_date'].min().date()} "
          f"-> {market['report_date'].max().date()}")

    market["percentile"] = rolling_percentile(
        market["noncomm_net_pct_oi"], ROLLING_PERCENTILE_WINDOW_WEEKS, MIN_HISTORY_FOR_PERCENTILE
    )
    market = market.dropna(subset=["percentile"]).reset_index(drop=True)
    print(f"{len(market)} reports have enough trailing history for a percentile rank "
          f"(first {MIN_HISTORY_FOR_PERCENTILE} dropped as warmup, "
          f"{ROLLING_PERCENTILE_WINDOW_WEEKS}-week trailing window)")

    price_close = load_price(args.price_csv)
    print(f"Price data ({args.price_csv}): {price_close.index.min().date()} -> "
          f"{price_close.index.max().date()}")

    for weeks in FORWARD_HORIZONS_WEEKS:
        market[f"fwd_ret_{weeks}w"] = market["usable_date"].apply(
            lambda d: forward_return(price_close, d, weeks)
        )

    print(f"\n{'='*70}")
    print(f"Correlation: percentile rank of speculative net positioning ({label}) vs forward return")
    print("(negative correlation = contrarian signal working: high positioning -> lower forward return)")
    print("Pearson alongside Spearman (rank-based): a real S&P 500/Nasdaq-100 --dump-weeks run")
    print("(2026-08-26) found a handful of forward-return observations clustered in the 2020")
    print("COVID crash driving several of the largest |return| values, without any SINGLE point")
    print("dominating the way a spurious-correlation artifact would. Spearman is structurally")
    print("robust to that -- it only uses rank, not magnitude, so a few extreme-magnitude points")
    print("can't inflate it the way they can inflate Pearson. Compare the two rather than trust")
    print("Pearson alone.")
    print(f"{'='*70}")
    for weeks in FORWARD_HORIZONS_WEEKS:
        col = f"fwd_ret_{weeks}w"
        valid = market.dropna(subset=[col])
        if len(valid) < 30:
            print(f"  {weeks}w horizon: only {len(valid)} valid observations, too few to report")
            continue
        corr = valid["percentile"].corr(valid[col])
        corr_spearman = valid["percentile"].corr(valid[col], method="spearman")
        print(f"  {weeks}w horizon: n={len(valid)}  pearson={corr:+.4f}  spearman={corr_spearman:+.4f}")

    print(f"\n{'='*70}")
    print("Extreme-quintile comparison, 12-week horizon (most standard COT contrarian framing)")
    print(f"{'='*70}")
    col = "fwd_ret_12w"
    valid = market.dropna(subset=[col])
    if len(valid) >= 30:
        top_quintile = valid[valid["percentile"] >= 0.80]
        bottom_quintile = valid[valid["percentile"] <= 0.20]
        middle = valid[(valid["percentile"] > 0.20) & (valid["percentile"] < 0.80)]
        for q_label, subset in (("Top quintile (crowded long)", top_quintile),
                                 ("Bottom quintile (crowded short)", bottom_quintile),
                                 ("Middle 60%", middle)):
            share = len(subset) / len(valid) if len(valid) else 0.0
            if len(subset) == 0:
                print(f"  {q_label}: no observations")
                continue
            print(f"  {q_label}: n={len(subset)} ({share*100:.1f}% of sample)  "
                  f"mean fwd 12w return={subset[col].mean()*100:+.2f}%  "
                  f"median={subset[col].median()*100:+.2f}%")
        top_share = len(top_quintile) / len(valid) if len(valid) else 0.0
        bottom_share = len(bottom_quintile) / len(valid) if len(valid) else 0.0
        if abs(top_share - 0.20) > QUINTILE_BALANCE_WARN_THRESHOLD or \
           abs(bottom_share - 0.20) > QUINTILE_BALANCE_WARN_THRESHOLD:
            print(f"  WARNING: quintile shares are skewed (top={top_share*100:.1f}%, "
                  f"bottom={bottom_share*100:.1f}%, expected ~20% each) -- the percentile is "
                  f"not behaving like a percentile. Do not trust the comparison above until "
                  f"this is understood.")
    else:
        print("  Too few valid observations for the 12w horizon.")

    if args.dump_weeks is not None:
        dump_col = f"fwd_ret_{args.dump_weeks}w"
        if dump_col not in market.columns:
            print(f"\n--dump-weeks {args.dump_weeks}: not one of {FORWARD_HORIZONS_WEEKS}")
        else:
            dump_valid = market.dropna(subset=[dump_col])
            if len(dump_valid) < 30:
                print(f"\n--dump-weeks {args.dump_weeks}: only {len(dump_valid)} valid "
                      f"observations, too few to dump")
            else:
                dump_extreme_observations(dump_valid, dump_col, label, args.dump_weeks)

    print("\nThis is discovery-stage only. No trading signal, no economic claim -- next step if")
    print("this looks real is proper causal-only power/significance testing, not eyeballing a")
    print("correlation coefficient.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
