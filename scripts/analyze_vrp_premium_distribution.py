"""Characterize the volatility risk premium's own distribution -- mean vs median.

Motivated by a real tension surfaced 2026-08-26 by the structure sweep's dose-response control
(`scripts/run_vrp_structure_robustness_sweep.py`): in a synthetic world with CONSTANT volatility,
the iron condor's break-even sits at roughly +3 to +4 vol points of premium. The measured
real-world VRP averages +3.53 points (VIX vs trailing realized SPY vol, 2014-2026, recorded on
the campaign board 2026-08-25) -- right at that break-even. Yet the real-data backtest returned a
strongly profitable $103.52/cycle at p<0.000001. Those two facts do not obviously fit together,
and until they do, the headline number is not fully understood.

The hypothesis this script tests: realized volatility is RIGHT-SKEWED -- most periods are calm
with realized vol well below the VIX priced at entry, punctuated by rare violent spikes where
realized vastly exceeds it. If so, the MEDIAN premium exceeds the MEAN premium, and a
held-to-expiry premium seller wins in the frequent calm majority while the mean is dragged down
by the rare spikes. That is the classic VRP shape, and it would reconcile both facts: the
constant-vol synthetic control has no such skew to harvest, so its break-even sits higher.

Falsification: if the median premium is NOT meaningfully above the mean premium, this explanation
is wrong and the tension stands unresolved -- which would be a genuine reason to distrust the
backtest's headline figure until something else explains it.

Method (no options pricing involved, deliberately -- this characterizes the premium itself, so it
can be checked independently of every modeling assumption in the backtest):
  - non-overlapping windows of the same length the backtest uses, over the same history;
  - "premium" at each window = VIX at the window's entry (what the seller is paid, in vol points)
    minus the FORWARD realized volatility actually delivered over that window (what the seller is
    exposed to), annualized from daily log returns.

Forward realized vol -- not trailing -- is the correct comparison: an option seller is paid for
the volatility that arrives AFTER entry, not the volatility that preceded it. Using trailing
realized vol here would be a subtly different (and easier) question than the one that matters.

Observation/analysis only. No trading signal, no economic claim.
"""

from __future__ import annotations

# Preserve direct-file execution; package imports use normal discovery.
if __package__ in (None, ""):
    try:
        from _checkout_bootstrap import bootstrap as _bootstrap_checkout
    except ModuleNotFoundError as _bootstrap_error:
        if _bootstrap_error.name != "_checkout_bootstrap":
            raise
        from scripts._checkout_bootstrap import bootstrap as _bootstrap_checkout
    _bootstrap_checkout(__file__)


import argparse
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent

from scripts.analyze_vrp_defined_risk_backtest import DAYS_TO_EXPIRY, load_close_series

TRADING_DAYS_PER_YEAR = 252
MIN_OBSERVATIONS_FOR_VOL = 10  # a window with fewer real closes than this can't give a usable vol


def forward_realized_vol(spy_close: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> float | None:
    """Annualized realized volatility of daily log returns strictly within (start, end].
    None if the window holds too few observations to be meaningful."""
    window = spy_close.loc[(spy_close.index > start) & (spy_close.index <= end)]
    if len(window) < MIN_OBSERVATIONS_FOR_VOL:
        return None
    prior = spy_close.loc[spy_close.index <= start]
    if len(prior) == 0:
        return None
    # Include the return from the entry close into the window so the first day isn't dropped.
    prices = pd.concat([prior.iloc[[-1]], window])
    log_returns = np.log(prices / prices.shift(1)).dropna()
    if len(log_returns) < MIN_OBSERVATIONS_FOR_VOL:
        return None
    return float(log_returns.std(ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR) * 100.0)


def build_premium_series(spy_close: pd.Series, vix_close: pd.Series, window_days: int) -> pd.DataFrame:
    """Non-overlapping windows matching the backtest's cycle structure, so this speaks to the
    same population of periods the backtest traded -- not a different, overlapping sample."""
    common = spy_close.index.intersection(vix_close.index)
    spy_close = spy_close.loc[common].sort_index()
    vix_close = vix_close.loc[common].sort_index()

    rows = []
    cursor = spy_close.index.min()
    last = spy_close.index.max()
    while True:
        entry_candidates = spy_close.index[spy_close.index >= cursor]
        if len(entry_candidates) == 0:
            break
        entry = entry_candidates[0]
        exit_candidates = spy_close.index[spy_close.index >= entry + timedelta(days=window_days)]
        if len(exit_candidates) == 0:
            break
        exit_date = exit_candidates[0]

        realized = forward_realized_vol(spy_close, entry, exit_date)
        if realized is not None:
            vix_entry = float(vix_close.loc[entry])
            rows.append({
                "entry_date": entry, "exit_date": exit_date,
                "vix_entry": vix_entry, "forward_realized_vol": realized,
                "premium_points": vix_entry - realized,
            })
        cursor = exit_date + timedelta(days=1)
        if cursor > last:
            break
    return pd.DataFrame(rows)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--spy-csv", default="data/SPY_1D.csv")
    p.add_argument("--vix-csv", default="data/VIX_1D.csv")
    p.add_argument("--window-days", type=int, default=DAYS_TO_EXPIRY,
                   help="Window length; defaults to the backtest's own cycle length.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    spy_close = load_close_series(args.spy_csv)
    vix_close = load_close_series(args.vix_csv)
    print(f"SPY: {spy_close.index.min().date()} -> {spy_close.index.max().date()} ({len(spy_close)} rows)")
    print(f"VIX: {vix_close.index.min().date()} -> {vix_close.index.max().date()} ({len(vix_close)} rows)")

    df = build_premium_series(spy_close, vix_close, args.window_days)
    if len(df) < 10:
        print(f"\nOnly {len(df)} usable windows -- too few to characterize the distribution.")
        return 1

    prem = df["premium_points"]
    print(f"\n{'='*74}")
    print(f"VRP distribution over {len(df)} non-overlapping {args.window_days}-day windows")
    print(f"(premium = VIX at entry minus FORWARD realized vol over the window, in vol points)")
    print(f"{'='*74}")
    print(f"mean VIX at entry:          {df['vix_entry'].mean():>7.2f}")
    print(f"mean forward realized vol:  {df['forward_realized_vol'].mean():>7.2f}")
    print(f"\nmean premium:               {prem.mean():>+7.2f} points")
    print(f"MEDIAN premium:             {prem.median():>+7.2f} points")
    print(f"std:                        {prem.std():>7.2f}")
    print(f"skew:                       {prem.skew():>+7.3f}")
    print(f"min / max:                  {prem.min():>+7.2f} / {prem.max():>+7.2f}")
    print(f"positive in:                {(prem > 0).mean()*100:>6.1f}% of windows")
    print(f"\npercentiles: p10={prem.quantile(0.10):+.2f}  p25={prem.quantile(0.25):+.2f}  "
          f"p50={prem.quantile(0.50):+.2f}  p75={prem.quantile(0.75):+.2f}  p90={prem.quantile(0.90):+.2f}")

    gap = prem.median() - prem.mean()
    print(f"\n{'='*74}")
    print("HYPOTHESIS TEST: does the median premium exceed the mean?")
    print(f"{'='*74}")
    print(f"median - mean = {gap:+.2f} points")
    if gap > 0.25:
        print("SUPPORTED. Realized vol is right-skewed: the typical window delivers a LARGER")
        print("premium than the average window, because rare volatility spikes drag the mean down")
        print("without affecting the median. A held-to-expiry premium seller collects the typical")
        print("case far more often than the average case -- which reconciles the strongly")
        print("profitable backtest with a mean premium that sits near the constant-vol break-even.")
        print("This also means the risk is real and concentrated: the same skew that makes the")
        print("median attractive is what produces the rare large losing cycles.")
    elif gap < -0.25:
        print("CONTRADICTED, and in the opposite direction -- the median premium is BELOW the")
        print("mean. The proposed explanation is wrong and the tension stands unresolved. Do not")
        print("trust the backtest's headline figure until something else accounts for it.")
    else:
        print("NOT SUPPORTED. Median and mean are close, so skew does not explain the gap between")
        print("the constant-vol break-even and the profitable backtest. The tension stands")
        print("unresolved -- treat the headline figure as not yet understood.")

    worst = df.nsmallest(8, "premium_points")
    print(f"\n8 worst windows (realized vol most exceeded the VIX priced at entry):")
    for _, r in worst.iterrows():
        print(f"  {r['entry_date'].date()} -> {r['exit_date'].date()}: VIX={r['vix_entry']:.1f} "
              f"realized={r['forward_realized_vol']:.1f}  premium={r['premium_points']:+.1f}")

    print("\nObservation only. This characterizes the premium itself and involves no options")
    print("pricing, so it is independent of every modeling assumption in the backtest.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
