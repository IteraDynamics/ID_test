"""Defined-risk equity volatility risk premium -- first real options-payoff backtest.

Continues the VRP idea CLOSED 2026-08-25 at Gate 2 (tradeability): the operator's brokerage at
the time didn't support multi-leg options, so the idea was recorded as blocked, not disproven,
and never chartered past Gate 1. The operator has since decided to open an Interactive Brokers
account (which does support multi-leg spreads) -- Gate 2 is now PENDING an external, clock-bound
approval process, not failed. Per the destination charter's own build-bound/clock-bound
distinction, the research that doesn't need a live account can proceed now, so the spec is
frozen and ready the day the account clears rather than starting cold.

What existed before this script: a VIX-vs-trailing-realized-SPY-vol read (mean VRP +3.53 points,
positive 85.1% of days) and a JEPI (real options-overlay income ETF) proxy backtest -- both real,
but neither actually modeled a defined-risk options structure's payoff. This script does: a
SPY iron condor (short strikes near a target delta, long wings for defined risk), priced via
Black-Scholes using VIX as the implied-volatility input, held to expiration, against real
historical SPY closes.

Explicit model limitations, stated up front rather than discovered later:
1. VIX (a single at-the-money-ish 30-day implied vol figure) is used as the IV input for ALL
   four legs, including far-OTM strikes. Real option markets price volatility SKEW -- OTM puts
   trade at meaningfully higher IV than ATM (crash insurance premium), OTM calls often trade
   lower. A flat-vol model therefore likely UNDERSTATES the true put-side credit and OVERSTATES
   the call-side credit relative to real market pricing. Net effect on total credit is not
   obviously biased in one direction without real skew data, but the STRUCTURE'S true risk
   profile (skewed, not symmetric) is not captured here.
2. No bid-ask spread or execution cost is modeled. This is a fair-value backtest. Real fills
   are worse -- this session's own TLT lesson (crypto-calibrated spread costs massively
   overstating a liquid instrument's real cost) does NOT apply here in the same direction; if
   anything options spreads are typically wider relative to fair value than most equity/ETF
   spreads, so this backtest's numbers are more likely optimistic than pessimistic.
3. Fixed risk-free rate approximation (see RISK_FREE_RATE), not a real historical short-rate
   series.
4. No early exit/profit-taking/stop-loss management -- held to expiration every cycle. Real
   defined-risk vol-selling systems often manage positions before expiration; this changes the
   realized return/risk profile in ways not modeled here.
5. American-style SPY options priced via the European Black-Scholes model -- a standard,
   commonly-accepted first-pass approximation, not exact.

Observation/analysis only. No trading signal, no position sizing recommendation, no economic
claim beyond what the printed numbers say.
"""

from __future__ import annotations

import argparse
import math
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.stats import norm

RISK_FREE_RATE = 0.04  # fixed approximation, not a real historical short-rate series
DAYS_TO_EXPIRY = 35  # calendar days; a common 30-45 DTE convention for this kind of structure
TARGET_SHORT_DELTA = 0.16  # standard "16-delta" short strike convention for iron condors
WING_WIDTH_PCT = 0.02  # long wing strikes this far further OTM than the short strikes, as a
                        # fraction of spot -- scale-invariant across SPY's 2014-2026 price range
CONTRACT_MULTIPLIER = 100  # SPY options are on 100 shares


def bs_price(spot: float, strike: float, t_years: float, sigma: float, r: float, is_call: bool) -> float:
    if t_years <= 0 or sigma <= 0:
        intrinsic = max(0.0, spot - strike) if is_call else max(0.0, strike - spot)
        return intrinsic
    d1 = (math.log(spot / strike) + (r + 0.5 * sigma**2) * t_years) / (sigma * math.sqrt(t_years))
    d2 = d1 - sigma * math.sqrt(t_years)
    if is_call:
        return spot * norm.cdf(d1) - strike * math.exp(-r * t_years) * norm.cdf(d2)
    return strike * math.exp(-r * t_years) * norm.cdf(-d2) - spot * norm.cdf(-d1)


def bs_delta(spot: float, strike: float, t_years: float, sigma: float, r: float, is_call: bool) -> float:
    if t_years <= 0 or sigma <= 0:
        if is_call:
            return 1.0 if spot > strike else 0.0
        return -1.0 if spot < strike else 0.0
    d1 = (math.log(spot / strike) + (r + 0.5 * sigma**2) * t_years) / (sigma * math.sqrt(t_years))
    return norm.cdf(d1) if is_call else norm.cdf(d1) - 1.0


def find_strike_for_delta(
    spot: float, t_years: float, sigma: float, r: float, is_call: bool, target_abs_delta: float
) -> float:
    """Finds the strike whose Black-Scholes delta magnitude matches target_abs_delta, via
    root-finding -- delta is monotonic in strike for fixed spot/T/sigma/r, so this is
    well-posed. Searches a wide bracket around spot to stay robust across vol regimes."""
    target = target_abs_delta if is_call else -target_abs_delta

    def f(k: float) -> float:
        return bs_delta(spot, k, t_years, sigma, r, is_call) - target

    lo, hi = spot * 0.3, spot * 3.0
    return brentq(f, lo, hi, xtol=1e-6)


def iron_condor_entry(spot: float, t_years: float, sigma: float, r: float) -> dict:
    """Prices one iron condor entry: short strikes at TARGET_SHORT_DELTA, long wings
    WING_WIDTH_PCT of spot further out. Returns strikes and the net credit received."""
    k_short_put = find_strike_for_delta(spot, t_years, sigma, r, is_call=False, target_abs_delta=TARGET_SHORT_DELTA)
    k_short_call = find_strike_for_delta(spot, t_years, sigma, r, is_call=True, target_abs_delta=TARGET_SHORT_DELTA)
    k_long_put = k_short_put * (1 - WING_WIDTH_PCT)
    k_long_call = k_short_call * (1 + WING_WIDTH_PCT)

    short_put_price = bs_price(spot, k_short_put, t_years, sigma, r, is_call=False)
    long_put_price = bs_price(spot, k_long_put, t_years, sigma, r, is_call=False)
    short_call_price = bs_price(spot, k_short_call, t_years, sigma, r, is_call=True)
    long_call_price = bs_price(spot, k_long_call, t_years, sigma, r, is_call=True)

    net_credit = (short_put_price - long_put_price) + (short_call_price - long_call_price)
    return {
        "k_short_put": k_short_put, "k_long_put": k_long_put,
        "k_short_call": k_short_call, "k_long_call": k_long_call,
        "net_credit": net_credit,
    }


def iron_condor_expiration_pnl(entry: dict, spot_at_expiry: float) -> float:
    """Deterministic settlement value at expiration -- no more optionality, just intrinsic
    value on each of the 4 legs, netted against the credit received at entry."""
    put_spread_settlement = (
        -max(0.0, entry["k_short_put"] - spot_at_expiry) + max(0.0, entry["k_long_put"] - spot_at_expiry)
    )
    call_spread_settlement = (
        -max(0.0, spot_at_expiry - entry["k_short_call"]) + max(0.0, spot_at_expiry - entry["k_long_call"])
    )
    return entry["net_credit"] + put_spread_settlement + call_spread_settlement


def load_close_series(csv_path: str) -> pd.Series:
    df = pd.read_csv(csv_path, index_col="timestamp", parse_dates=True)
    if df.index.tz is not None:
        df.index = df.index.tz_convert(None)
    return df["close"].sort_index()


def run_backtest(spy_close: pd.Series, vix_close: pd.Series) -> pd.DataFrame:
    """Non-overlapping DAYS_TO_EXPIRY-day cycles across the full history both series cover.
    Non-overlapping (rather than weekly-rolled, like every other analysis this session) is a
    deliberate choice here: it keeps this first pass free of the overlapping-window
    effective-sample-size problem that has recurred all day (COT gold, crypto momentum, COT
    index), at the cost of a smaller raw n -- the right tradeoff for a first honest look, not a
    frozen specification."""
    common_dates = spy_close.index.intersection(vix_close.index)
    spy_close = spy_close.loc[common_dates].sort_index()
    vix_close = vix_close.loc[common_dates].sort_index()

    rows = []
    cursor = spy_close.index.min()
    end = spy_close.index.max()
    t_years = DAYS_TO_EXPIRY / 365.0

    while True:
        entry_candidates = spy_close.index[spy_close.index >= cursor]
        if len(entry_candidates) == 0:
            break
        entry_date = entry_candidates[0]
        expiry_target = entry_date + timedelta(days=DAYS_TO_EXPIRY)
        expiry_candidates = spy_close.index[spy_close.index >= expiry_target]
        if len(expiry_candidates) == 0:
            break
        expiry_date = expiry_candidates[0]

        spot = float(spy_close.loc[entry_date])
        sigma = float(vix_close.loc[entry_date]) / 100.0
        entry = iron_condor_entry(spot, t_years, sigma, RISK_FREE_RATE)
        spot_at_expiry = float(spy_close.loc[expiry_date])
        pnl_per_share = iron_condor_expiration_pnl(entry, spot_at_expiry)
        rows.append({
            "entry_date": entry_date, "expiry_date": expiry_date,
            "spot_entry": spot, "spot_expiry": spot_at_expiry, "vix_entry": sigma * 100,
            "k_short_put": entry["k_short_put"], "k_long_put": entry["k_long_put"],
            "k_short_call": entry["k_short_call"], "k_long_call": entry["k_long_call"],
            "net_credit_per_share": entry["net_credit"],
            "pnl_per_share": pnl_per_share,
            "pnl_dollars": pnl_per_share * CONTRACT_MULTIPLIER,
        })
        cursor = expiry_date + timedelta(days=1)
        if cursor > end:
            break

    return pd.DataFrame(rows)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--spy-csv", default="data/SPY_1D.csv")
    p.add_argument("--vix-csv", default="data/VIX_1D.csv")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    spy_close = load_close_series(args.spy_csv)
    vix_close = load_close_series(args.vix_csv)
    print(f"SPY: {spy_close.index.min().date()} -> {spy_close.index.max().date()} ({len(spy_close)} rows)")
    print(f"VIX: {vix_close.index.min().date()} -> {vix_close.index.max().date()} ({len(vix_close)} rows)")

    df = run_backtest(spy_close, vix_close)
    if len(df) < 10:
        print(f"\nOnly {len(df)} non-overlapping {DAYS_TO_EXPIRY}-day cycles available -- too few to report.")
        return 1

    print(f"\n{'='*70}")
    print(f"Iron condor backtest: {DAYS_TO_EXPIRY}-day cycles, {TARGET_SHORT_DELTA:.0%} short delta, "
          f"{WING_WIDTH_PCT:.0%} wings, held to expiration, Black-Scholes fair value")
    print(f"{'='*70}")
    print(f"cycles: {len(df)}  ({df['entry_date'].min().date()} -> {df['expiry_date'].max().date()})")
    print(f"win rate (pnl > 0): {(df['pnl_dollars'] > 0).mean()*100:.1f}%")
    print(f"mean pnl/cycle: ${df['pnl_dollars'].mean():.2f}  median: ${df['pnl_dollars'].median():.2f}")
    print(f"total pnl over full sample: ${df['pnl_dollars'].sum():.2f}")
    print(f"worst single cycle: ${df['pnl_dollars'].min():.2f}  best: ${df['pnl_dollars'].max():.2f}")
    print(f"std(pnl/cycle): ${df['pnl_dollars'].std():.2f}")

    cycles_per_year = 365 / DAYS_TO_EXPIRY
    years_covered = (df["expiry_date"].max() - df["entry_date"].min()).days / 365.25
    print(f"\napprox cycles/year: {cycles_per_year:.1f}   years covered: {years_covered:.1f}")
    print(f"annualized pnl (1 contract, mean-per-cycle x cycles/year): "
          f"${df['pnl_dollars'].mean() * cycles_per_year:.2f}")

    print("\nThis is a fair-value, held-to-expiration, flat-vol first pass. See this script's")
    print("docstring for the five explicit modeling limitations before treating any number here")
    print("as an economic claim -- especially the missing volatility skew and execution costs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
