"""Cross-sectional crypto momentum -- first real look, discovery-stage only.

Named deficiency (Core v2 charter clarification, 2026-08-11): "single-name crypto." Core v1's
only crypto exposure is BTC 4H and ETH 1H/4H, each traded on its own trend in isolation -- no
relative-value exposure across a basket at all. This tests whether ranking a basket of coins by
trailing return and separating winners from losers produces a real forward-return spread, which
would be a genuinely different return source from anything Core v1 already runs.

Falsification: if the top-momentum and bottom-momentum baskets show no statistically
distinguishable forward-return spread (or a spread with the wrong sign) across the declared
horizon grid, the hypothesis is rejected and the idea is closed -- same standard already applied
to the COT gold contrarian idea this session, which failed exactly this test.

Universe and point-in-time eligibility (the part that matters most here): the candidate list in
scripts/probe_coinbase_spot_momentum_universe.py spans coins with wildly different real listing
dates -- BTC since 2015, some names for barely a year. A coin is only ELIGIBLE to enter the
cross-sectional ranking on a given rebalance date once it has at least
MIN_ELIGIBILITY_HISTORY_DAYS of its own real trailing price history as of that date -- using each
coin's own true data, never a shared start date. This means the ranked universe starts as just
BTC (2015) and grows over the years as more coins list and accrue enough history, which is the
standard, correct way to handle an expanding investable universe without assuming knowledge that
didn't exist yet (the same causal discipline as the COT gold analysis's report-lag handling, just
applied to universe membership instead of a data-release lag).

Known, unquantified bias NOT corrected here: this candidate list was built from Coinbase's
CURRENTLY tradable products (2026-08-26). Any coin that existed and was later delisted before
today is invisible to this analysis -- correcting that needs a point-in-time delisted-coin data
source this program doesn't have. This biases results in the optimistic direction (the universe
implicitly conditions on "still exists"), and that bias is not measured, only disclosed.

Rebalance cadence, formation and holding horizons are declared here BEFORE looking at any output,
not tuned after seeing a result -- same discipline as the COT gold script's fixed 4/12/26-week
horizon grid.

Observation/analysis only. No execution costs modeled (altcoin spreads/slippage on this venue
have not been checked and are very unlikely to be free -- a real backtest against the harness's
execution model is a separate, later step if this discovery-stage look is promising). No trading
signal, no economic claim.
"""

from __future__ import annotations

import argparse
import glob
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

REBALANCE_FREQ_DAYS = 7  # weekly, matching Gate 1's horizon-feasibility framing for this idea
FORMATION_WINDOWS_DAYS = (14, 28, 84)  # 2w / 4w / 12w trailing return as the ranking signal
HOLDING_HORIZONS_DAYS = (7, 28, 84)  # 1w / 4w / 12w forward return, measured from each rebalance
MIN_ELIGIBILITY_HISTORY_DAYS = 84  # a coin needs at least the longest formation window of real
                                    # history before it's ranked at all
TOP_BOTTOM_FRACTION = 0.30  # top/bottom 30% by rank
# Correction, 2026-08-26: was 10. The first real run's 84d-formation/84d-holding "central
# finding" (-5.69% spread) turned out to be almost entirely an artifact of Dec 2020 - Mar 2021
# (the well-known crypto alt-season), when the eligible universe was near this old threshold --
# a 30% tercile of 10 names is only 3 coins, and a single coin's few-hundred-percent alt-season
# move dominates a 3-name average outright (individual coin spreads of -313%, -287%, -256% showed
# up in the per-rebalance dump, only possible with that few names per leg). Raised so a tercile
# has at least 7 names (25 * 0.30 = 7) before a rebalance date counts at all -- a structural fix
# to what counts as a "cross-section," decided before re-examining how the headline numbers move,
# the same discipline as the COT gold percentile-window fix.
MIN_ELIGIBLE_UNIVERSE = 25


def discover_price_files(data_dir: Path) -> dict[str, Path]:
    """Maps product_id (e.g. BTC-USD) -> its daily CSV, from fetch_coinbase_daily_history.py's
    output naming (<compact>_86400s_<start>_to_<end>.csv). Picks the widest-date-range file if
    more than one exists for the same product (e.g. from a re-fetch)."""
    candidates: dict[str, list[Path]] = {}
    for path in sorted(data_dir.glob("*_86400s_*_to_*.csv")):
        compact = path.name.split("_86400s_")[0]
        candidates.setdefault(compact, []).append(path)
    out: dict[str, Path] = {}
    for compact, paths in candidates.items():
        widest = max(paths, key=lambda p: p.stat().st_size)
        # Recover PRODUCT-USD form from the compact filename token (e.g. "btcusd" -> "BTC-USD").
        # Coinbase product ids here are all "<BASE>-USD"; the compact form drops the hyphen.
        base = compact[:-3].upper() if compact.endswith("usd") else compact.upper()
        product_id = f"{base}-USD"
        out[product_id] = widest
    return out


def load_daily_close(path: Path) -> pd.Series:
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df = df.sort_values("timestamp").drop_duplicates(subset="timestamp", keep="last")
    return df.set_index("timestamp")["close"]


def build_panel(price_files: dict[str, Path]) -> pd.DataFrame:
    """Wide DataFrame of daily close prices, index=date, columns=product_id. Outer-joined, so a
    coin's column is NaN before its own real listing date -- that NaN is exactly what eligibility
    filtering below keys off, never filled or interpolated across it."""
    series = {}
    for product_id, path in price_files.items():
        s = load_daily_close(path)
        s.index = s.index.normalize()
        series[product_id] = s
    panel = pd.DataFrame(series)
    return panel.sort_index()


def rebalance_dates(panel: pd.DataFrame) -> list[pd.Timestamp]:
    all_dates = panel.index
    start = all_dates.min() + timedelta(days=MIN_ELIGIBILITY_HISTORY_DAYS)
    dates = []
    cursor = start
    end_cutoff = all_dates.max() - timedelta(days=max(HOLDING_HORIZONS_DAYS))
    while cursor <= end_cutoff:
        # Snap to the nearest available trading date on/after cursor.
        candidates = all_dates[all_dates >= cursor]
        if len(candidates) == 0:
            break
        dates.append(candidates[0])
        cursor = candidates[0] + timedelta(days=REBALANCE_FREQ_DAYS)
    return dates


def trailing_return(panel: pd.DataFrame, as_of: pd.Timestamp, window_days: int) -> pd.Series:
    """Causal by construction: only uses prices at as_of and as_of-window_days, never anything
    after as_of. Returns NaN for a coin without a real price at either endpoint (i.e. not yet
    listed, or missing data) -- never fabricated or forward-filled."""
    prior_candidates = panel.index[panel.index <= as_of - timedelta(days=window_days)]
    if len(prior_candidates) == 0:
        return pd.Series(np.nan, index=panel.columns)
    prior_date = prior_candidates[-1]
    if as_of not in panel.index:
        return pd.Series(np.nan, index=panel.columns)
    return panel.loc[as_of] / panel.loc[prior_date] - 1.0


def forward_return(panel: pd.DataFrame, as_of: pd.Timestamp, horizon_days: int) -> pd.Series:
    """Same causal direction as trailing_return but looking forward from as_of -- used only to
    SCORE the already-formed ranking after the fact, never to form it."""
    future_candidates = panel.index[panel.index >= as_of + timedelta(days=horizon_days)]
    if len(future_candidates) == 0 or as_of not in panel.index:
        return pd.Series(np.nan, index=panel.columns)
    future_date = future_candidates[0]
    return panel.loc[future_date] / panel.loc[as_of] - 1.0


def eligible_mask(panel: pd.DataFrame, as_of: pd.Timestamp) -> pd.Series:
    """A coin is eligible at as_of only if it has a real (non-NaN) price at least
    MIN_ELIGIBILITY_HISTORY_DAYS before as_of AND at as_of itself -- i.e. it was actually listed
    and trading, using nothing but that coin's own real history."""
    history_start = panel.index[panel.index <= as_of - timedelta(days=MIN_ELIGIBILITY_HISTORY_DAYS)]
    if len(history_start) == 0 or as_of not in panel.index:
        return pd.Series(False, index=panel.columns)
    has_old = panel.loc[history_start[-1]].notna()
    has_now = panel.loc[as_of].notna()
    return has_old & has_now


def compute_spread_series(
    panel: pd.DataFrame, dates: list[pd.Timestamp], formation_days: int, holding_days: int
) -> pd.Series:
    """Date-indexed top-minus-bottom spread per rebalance, for one formation/holding combo. Same
    computation run_analysis aggregates inline -- factored out so a diagnostic dump can inspect
    the raw per-date series instead of only ever seeing the mean."""
    out: dict[pd.Timestamp, float] = {}
    for d in dates:
        elig = eligible_mask(panel, d)
        if int(elig.sum()) < MIN_ELIGIBLE_UNIVERSE:
            continue
        tr = trailing_return(panel, d, formation_days)[elig]
        fr = forward_return(panel, d, holding_days)[elig]
        valid = tr.notna() & fr.notna()
        tr, fr = tr[valid], fr[valid]
        if len(tr) < MIN_ELIGIBLE_UNIVERSE:
            continue
        n_leg = max(1, int(len(tr) * TOP_BOTTOM_FRACTION))
        ranked = tr.sort_values(ascending=False)
        top_names, bottom_names = ranked.index[:n_leg], ranked.index[-n_leg:]
        out[d] = fr[top_names].mean() - fr[bottom_names].mean()
    return pd.Series(out)


def dump_spread_diagnostic(panel: pd.DataFrame, dates: list[pd.Timestamp], formation_days: int, holding_days: int) -> None:
    """Prints distributional detail (not just the mean) for one formation/holding combo, and the
    most extreme individual rebalances -- the direct check for whether a small number of events
    are driving an otherwise-unremarkable average, the same category of check that caught the
    COT gold quintile-median coincidence."""
    series = compute_spread_series(panel, dates, formation_days, holding_days)
    print(f"\n{'='*70}")
    print(f"Diagnostic dump: formation={formation_days}d holding={holding_days}d "
          f"({len(series)} rebalances)")
    print(f"{'='*70}")
    print(series.describe().to_string())
    print(f"skew: {series.skew():.3f}")
    print(f"|spread| > 10%: {(series.abs() > 0.10).sum()} rebalances")
    print(f"|spread| > 20%: {(series.abs() > 0.20).sum()} rebalances")

    # Effect of dropping the single most extreme rebalance on the overall mean -- if the mean
    # swings by more than a small fraction from removing ONE date, the average is not a stable
    # summary of a broad effect.
    full_mean = series.mean()
    most_extreme_date = series.abs().idxmax()
    without_extreme = series.drop(most_extreme_date)
    print(f"\nfull mean: {full_mean*100:+.2f}%   "
          f"mean excluding single most extreme rebalance ({most_extreme_date.date()}, "
          f"spread={series[most_extreme_date]*100:+.2f}%): {without_extreme.mean()*100:+.2f}%")

    print("\nTop 8 most extreme rebalances by |spread|:")
    top8 = series.reindex(series.abs().sort_values(ascending=False).index[:8])
    for d, v in top8.items():
        print(f"  {d.date()}: {v*100:+.2f}%")


def run_analysis(panel: pd.DataFrame, dump_formation_days: int | None = None, dump_holding_days: int | None = None) -> None:
    dates = rebalance_dates(panel)
    print(f"{len(dates)} rebalance dates from {dates[0].date()} to {dates[-1].date()} "
          f"(weekly, {REBALANCE_FREQ_DAYS}-day spacing)")

    panel_sizes = []
    for d in dates:
        panel_sizes.append(int(eligible_mask(panel, d).sum()))
    panel_sizes_s = pd.Series(panel_sizes, index=dates)
    print(f"\nEligible universe size over time (canary: should GROW, never shrink except from "
          f"real data gaps -- a bug here would silently bias every result downstream):")
    for label, d in (("first", dates[0]), ("25%", dates[len(dates)//4]),
                      ("50%", dates[len(dates)//2]), ("75%", dates[3*len(dates)//4]),
                      ("last", dates[-1])):
        print(f"  {label} ({d.date()}): {int(eligible_mask(panel, d).sum())} eligible coins")
    n_dropped = sum(1 for n in panel_sizes if n < MIN_ELIGIBLE_UNIVERSE)
    print(f"  {n_dropped}/{len(dates)} rebalance dates dropped for having fewer than "
          f"{MIN_ELIGIBLE_UNIVERSE} eligible coins")

    print(f"\n{'='*70}")
    print("Formation window x holding horizon grid: top-tercile minus bottom-tercile spread")
    print(f"(top {int(TOP_BOTTOM_FRACTION*100)}% by trailing return minus bottom "
          f"{int(TOP_BOTTOM_FRACTION*100)}%, mean forward return, at each rebalance)")
    print(f"{'='*70}")

    for formation_days in FORMATION_WINDOWS_DAYS:
        for holding_days in HOLDING_HORIZONS_DAYS:
            series = compute_spread_series(panel, dates, formation_days, holding_days)
            if len(series) < 10:
                print(f"  formation={formation_days}d holding={holding_days}d: only "
                      f"{len(series)} usable rebalances, too few to report")
                continue
            mean_spread = series.mean()
            pct_positive = (series > 0).mean()
            print(f"  formation={formation_days:>3}d holding={holding_days:>3}d: "
                  f"n={len(series):>4}  mean top-minus-bottom spread={mean_spread*100:+.2f}%  "
                  f"positive in {pct_positive*100:.1f}% of rebalances")

    print("\nThis is discovery-stage only. No execution costs modeled, no significance/power test")
    print("run, survivorship bias from today's-listings sourcing not corrected. Next step if any")
    print("cell above looks real: check it survives realistic altcoin spread/slippage costs before")
    print("anything else -- this venue's cost structure for smaller-cap names has not been checked.")

    if dump_formation_days is not None and dump_holding_days is not None:
        dump_spread_diagnostic(panel, dates, dump_formation_days, dump_holding_days)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--data-dir", default="data")
    p.add_argument("--dump-formation-days", type=int, default=None,
                   help="Print the raw per-rebalance spread series (distribution, skew, extreme "
                        "dates) for this formation window, instead of only the grid summary. "
                        "Requires --dump-holding-days too.")
    p.add_argument("--dump-holding-days", type=int, default=None)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    data_dir = Path(args.data_dir)
    price_files = discover_price_files(data_dir)
    if len(price_files) < MIN_ELIGIBLE_UNIVERSE:
        print(f"Only found {len(price_files)} daily price files in {data_dir} matching "
              f"*_86400s_*_to_*.csv -- run scripts/fetch_coinbase_daily_history.py first.")
        return 1
    print(f"Loaded {len(price_files)} product price files: {sorted(price_files.keys())}")
    panel = build_panel(price_files)
    print(f"Panel: {panel.shape[0]} calendar days x {panel.shape[1]} products, "
          f"{panel.index.min().date()} -> {panel.index.max().date()}")
    run_analysis(panel, args.dump_formation_days, args.dump_holding_days)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
