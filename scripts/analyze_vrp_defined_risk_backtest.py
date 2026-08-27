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
1. VIX (a single at-the-money-ish 30-day implied vol figure) is the baseline IV input; real
   option markets price volatility SKEW on top of that -- OTM puts trade at meaningfully higher
   IV than ATM (crash insurance premium), OTM calls often trade lower. Updated 2026-08-26: no
   verified historical per-strike SPY skew dataset exists here, so this is modeled as an
   illustrative sensitivity sweep (SKEW_SLOPE_SCENARIOS, a simple linear-in-log-moneyness
   adjustment) rather than left out entirely -- but it is still NOT a real historical skew
   curve, and real skew varies substantially over time (steeper after crashes) in ways this
   fixed-per-scenario slope can't capture.
2. No bid-ask spread or execution cost is modeled by default (see SPREAD_COST_SCENARIOS for the
   separate cost sensitivity sweep, applied independently of skew). This is otherwise a fair-
   value backtest. Real fills
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
from scipy.stats import norm, t as t_dist

RISK_FREE_RATE = 0.04  # fixed approximation, not a real historical short-rate series
DAYS_TO_EXPIRY = 35  # calendar days; a common 30-45 DTE convention for this kind of structure
TARGET_SHORT_DELTA = 0.16  # standard "16-delta" short strike convention for iron condors
WING_WIDTH_PCT = 0.02  # long wing strikes this far further OTM than the short strikes, as a
                        # fraction of spot -- scale-invariant across SPY's 2014-2026 price range
CONTRACT_MULTIPLIER = 100  # SPY options are on 100 shares
LEG_COUNT = 4  # short put, long put, short call, long call

# Cost overlay (2026-08-26 addition): no verified historical SPY-options bid-ask dataset is
# available here. Rather than assert one "true" spread number from memory -- the exact mistake
# that has cost real time this session (a CSV field name, a venue root filter, an ETF ticker,
# a market name) -- this sweeps a few explicitly labeled, honestly-uncertain assumptions and
# shows how much the result actually depends on the number that can't be verified, instead of
# hiding that uncertainty behind a single figure. Each scenario charges one full bid-ask width
# per leg (approximating a half-spread crossed on entry plus an equivalent-cost exit/assignment
# friction), on all 4 legs, once per cycle -- a simplification, not a mechanically exact model
# of real fills.
SPREAD_COST_SCENARIOS = [
    ("tight (calm, highly liquid strike)", 0.03),
    ("moderate (typical, some far-OTM widening)", 0.08),
    ("wide (crisis period / thin strike)", 0.20),
]
# Commission assumption -- recalled with moderate, not certain, confidence from general
# knowledge of IBKR's typical per-contract US options rate; verify against IBKR's actual current
# rate sheet before this goes anywhere near a frozen specification. Charged once per leg
# (entry only) -- likely understates real total commission if any position is ever closed early
# or incurs an assignment fee.
COMMISSION_PER_CONTRACT_LEG = 0.65

# Volatility skew (2026-08-26 addition): the flat-vol model above prices all four legs off a
# single VIX-derived sigma, but real equity index options price OTM puts richer than ATM (crash-
# insurance demand) and typically OTM calls a bit cheaper -- the "skew"/"smirk" well documented
# in equity derivatives (e.g. CBOE's own literature on SPX skew since 1987). No verified
# historical per-strike SPY skew dataset exists here, so -- same discipline as the cost sweep --
# this sweeps clearly labeled, illustrative skew-steepness assumptions instead of asserting one
# real historical skew curve. Parametrization: a simple, standard linear-in-log-moneyness
# adjustment, sigma(K) = base_sigma - SKEW_SLOPE * ln(K/spot), so K < spot (puts) get higher
# local vol and K > spot (calls) get lower local vol, in vol-point terms per unit of log-
# moneyness. Real skew is also known to vary substantially over time (steeper after crashes,
# flatter in complacent periods) and is not perfectly linear or perfectly antisymmetric between
# puts and calls -- this is a first-order approximation only.
SKEW_SLOPE_SCENARIOS = [
    ("flat (current baseline, no skew)", 0.0),
    ("moderate skew", 0.30),
    ("steep skew", 0.60),
]
MIN_SIGMA = 0.01  # floor to avoid a nonsensical non-positive vol far along a steep skew


def skewed_sigma(spot: float, strike: float, base_sigma: float, skew_slope: float) -> float:
    if skew_slope == 0.0:
        return base_sigma
    log_moneyness = math.log(strike / spot)
    return max(MIN_SIGMA, base_sigma - skew_slope * log_moneyness)


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
    spot: float, t_years: float, sigma: float, r: float, is_call: bool, target_abs_delta: float,
    skew_slope: float = 0.0,
) -> float:
    """Finds the strike whose Black-Scholes delta magnitude matches target_abs_delta, via
    root-finding -- delta is monotonic in strike for fixed spot/T/sigma/r, so this is
    well-posed. Searches a wide bracket around spot to stay robust across vol regimes.

    With skew_slope != 0, sigma is itself a function of the candidate strike (skewed_sigma),
    so this solves the self-consistent problem "find K such that delta(K, sigma(K)) = target" --
    still well-posed via the same root-find, just recomputing local vol at each trial K."""
    target = target_abs_delta if is_call else -target_abs_delta

    def f(k: float) -> float:
        local_sigma = skewed_sigma(spot, k, sigma, skew_slope)
        return bs_delta(spot, k, t_years, local_sigma, r, is_call) - target

    lo, hi = spot * 0.3, spot * 3.0
    return brentq(f, lo, hi, xtol=1e-6)


def iron_condor_entry(
    spot: float, t_years: float, sigma: float, r: float, skew_slope: float = 0.0,
    target_short_delta: float | None = None, wing_width_pct: float | None = None,
) -> dict:
    """Prices one iron condor entry: short strikes at target_short_delta (default
    TARGET_SHORT_DELTA), long wings wing_width_pct (default WING_WIDTH_PCT) of spot further out.
    Returns strikes and the net credit received.

    All optional parameters default to the module constants, so every already-verified test of
    this function's output is unaffected by their addition. They exist so the structure
    robustness sweep (scripts/run_vrp_structure_robustness_sweep.py) can vary the structure
    without duplicating this pricing logic -- the "is the edge only at one lucky parameter
    point?" check."""
    target_short_delta = TARGET_SHORT_DELTA if target_short_delta is None else target_short_delta
    wing_width_pct = WING_WIDTH_PCT if wing_width_pct is None else wing_width_pct

    k_short_put = find_strike_for_delta(spot, t_years, sigma, r, is_call=False, target_abs_delta=target_short_delta, skew_slope=skew_slope)
    k_short_call = find_strike_for_delta(spot, t_years, sigma, r, is_call=True, target_abs_delta=target_short_delta, skew_slope=skew_slope)
    k_long_put = k_short_put * (1 - wing_width_pct)
    k_long_call = k_short_call * (1 + wing_width_pct)

    sigma_short_put = skewed_sigma(spot, k_short_put, sigma, skew_slope)
    sigma_long_put = skewed_sigma(spot, k_long_put, sigma, skew_slope)
    sigma_short_call = skewed_sigma(spot, k_short_call, sigma, skew_slope)
    sigma_long_call = skewed_sigma(spot, k_long_call, sigma, skew_slope)

    short_put_price = bs_price(spot, k_short_put, t_years, sigma_short_put, r, is_call=False)
    long_put_price = bs_price(spot, k_long_put, t_years, sigma_long_put, r, is_call=False)
    short_call_price = bs_price(spot, k_short_call, t_years, sigma_short_call, r, is_call=True)
    long_call_price = bs_price(spot, k_long_call, t_years, sigma_long_call, r, is_call=True)

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


def cost_per_cycle(spread_cost_per_leg: float, commission_per_leg: float) -> float:
    """Total assumed cost for one 4-leg cycle. spread_cost_per_leg is quoted PER SHARE (like a
    real option's bid-ask width, e.g. "$0.03 wide") and needs CONTRACT_MULTIPLIER to become a
    per-contract dollar cost -- commission_per_leg is already quoted PER CONTRACT and must NOT
    be multiplied again, or it silently becomes 100x too large."""
    return LEG_COUNT * (spread_cost_per_leg * CONTRACT_MULTIPLIER + commission_per_leg)


def one_sample_t_test(values: pd.Series) -> tuple[float, float]:
    """Standard one-sample t-test against zero. Legitimate here (unlike every overlapping-
    window time-series test elsewhere this session) because run_backtest's cycles are
    genuinely non-overlapping by construction -- see run_backtest's own docstring."""
    n = len(values)
    if n < 2:
        return float("nan"), float("nan")
    mean = values.mean()
    se = values.std(ddof=1) / math.sqrt(n)
    if se == 0:
        return float("inf") if mean != 0 else 0.0, 0.0 if mean != 0 else 1.0
    stat = mean / se
    p = 2 * t_dist.sf(abs(stat), df=n - 1)
    return stat, p


def load_close_series(csv_path: str) -> pd.Series:
    df = pd.read_csv(csv_path, index_col="timestamp", parse_dates=True)
    if df.index.tz is not None:
        df.index = df.index.tz_convert(None)
    return df["close"].sort_index()


def run_backtest(
    spy_close: pd.Series, vix_close: pd.Series, skew_slope: float = 0.0,
    days_to_expiry: int | None = None, target_short_delta: float | None = None,
    wing_width_pct: float | None = None,
) -> pd.DataFrame:
    """Non-overlapping days_to_expiry-day cycles across the full history both series cover.
    Non-overlapping (rather than weekly-rolled, like every other analysis this session) is a
    deliberate choice here: it keeps this first pass free of the overlapping-window
    effective-sample-size problem that has recurred all day (COT gold, crypto momentum, COT
    index), at the cost of a smaller raw n -- the right tradeoff for a first honest look, not a
    frozen specification.

    All optional parameters default to the module constants, so omitting them reproduces the
    original backtest exactly."""
    days_to_expiry = DAYS_TO_EXPIRY if days_to_expiry is None else days_to_expiry
    common_dates = spy_close.index.intersection(vix_close.index)
    spy_close = spy_close.loc[common_dates].sort_index()
    vix_close = vix_close.loc[common_dates].sort_index()

    rows = []
    cursor = spy_close.index.min()
    end = spy_close.index.max()
    t_years = days_to_expiry / 365.0

    while True:
        entry_candidates = spy_close.index[spy_close.index >= cursor]
        if len(entry_candidates) == 0:
            break
        entry_date = entry_candidates[0]
        expiry_target = entry_date + timedelta(days=days_to_expiry)
        expiry_candidates = spy_close.index[spy_close.index >= expiry_target]
        if len(expiry_candidates) == 0:
            break
        expiry_date = expiry_candidates[0]

        spot = float(spy_close.loc[entry_date])
        sigma = float(vix_close.loc[entry_date]) / 100.0
        entry = iron_condor_entry(
            spot, t_years, sigma, RISK_FREE_RATE, skew_slope=skew_slope,
            target_short_delta=target_short_delta, wing_width_pct=wing_width_pct,
        )
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

    print(f"\n{'='*70}")
    print("Diagnostic: are losing cycles clustered in known vol events, or spread out?")
    print(f"{'='*70}")
    losers = df[df["pnl_dollars"] < 0].sort_values("pnl_dollars")
    print(f"{len(losers)}/{len(df)} losing cycles:")
    for _, row in losers.iterrows():
        print(f"  {row['entry_date'].date()} -> {row['expiry_date'].date()}  "
              f"vix_entry={row['vix_entry']:.1f}  pnl=${row['pnl_dollars']:.2f}")

    full_mean = df["pnl_dollars"].mean()
    worst_idx = df["pnl_dollars"].idxmin()
    without_worst = df.drop(worst_idx)
    print(f"\nfull mean: ${full_mean:.2f}   "
          f"mean excluding single worst cycle ({df.loc[worst_idx, 'entry_date'].date()}, "
          f"${df.loc[worst_idx, 'pnl_dollars']:.2f}): ${without_worst['pnl_dollars'].mean():.2f}")

    corr_vix_pnl = df["vix_entry"].corr(df["pnl_dollars"])
    print(f"\ncorr(VIX at entry, cycle pnl): {corr_vix_pnl:+.4f}")
    print("(a real premium-harvesting structure entered at higher VIX should collect more credit")
    print("for the same risk, i.e. a positive relationship here is expected and reassuring; a")
    print("strongly negative one would suggest the flat-vol model is most wrong exactly where it")
    print("matters most -- high-vol entries.)")

    t_gross, p_gross = one_sample_t_test(df["pnl_dollars"])
    print(f"\n{'='*70}")
    print("Significance (legitimate here: cycles are genuinely non-overlapping, unlike every")
    print("other time-series test this session)")
    print(f"{'='*70}")
    print(f"fair-value (no costs): t={t_gross:.3f}  df={len(df)-1}  two-tailed p={p_gross:.6f}")

    print(f"\n{'='*70}")
    print("Skew sensitivity: NO verified historical per-strike SPY skew dataset exists here.")
    print("Sweeping illustrative skew-steepness assumptions (linear-in-log-moneyness, OTM puts")
    print("get higher local vol, OTM calls lower) instead of asserting one real historical skew")
    print("curve. Re-runs the FULL backtest under each assumption -- fair value, no execution")
    print("costs yet, isolating skew's effect before combining it with the cost sweep above.")
    print(f"{'='*70}")
    for label, slope in SKEW_SLOPE_SCENARIOS:
        skew_df = run_backtest(spy_close, vix_close, skew_slope=slope) if slope != 0.0 else df
        t_skew, p_skew = one_sample_t_test(skew_df["pnl_dollars"])
        print(f"\n{label} (slope={slope}): n={len(skew_df)}  "
              f"mean=${skew_df['pnl_dollars'].mean():.2f}  median=${skew_df['pnl_dollars'].median():.2f}  "
              f"win rate={(skew_df['pnl_dollars'] > 0).mean()*100:.1f}%")
        print(f"  t={t_skew:.3f}  p={p_skew:.6f}")

    print(f"\n{'='*70}")
    print("Cost sensitivity: NO verified historical SPY-options bid-ask dataset exists here.")
    print(f"Sweeping stated, honestly-uncertain spread assumptions instead of asserting one")
    print(f"'true' number. Commission assumption (${COMMISSION_PER_CONTRACT_LEG:.2f}/contract/leg,")
    print(f"entry only) recalled with moderate confidence -- verify against IBKR's real current")
    print(f"rate sheet before this goes near a frozen spec.")
    print(f"{'='*70}")
    for label, spread_cost in SPREAD_COST_SCENARIOS:
        cost = cost_per_cycle(spread_cost, COMMISSION_PER_CONTRACT_LEG)
        net = df["pnl_dollars"] - cost
        t_net, p_net = one_sample_t_test(net)
        print(f"\n{label}  (${spread_cost:.2f}/contract/leg spread, ${cost:.2f}/cycle total cost)")
        print(f"  net mean/cycle: ${net.mean():.2f}  median: ${net.median():.2f}  "
              f"win rate: {(net > 0).mean()*100:.1f}%")
        print(f"  annualized (1 contract): ${net.mean() * (365/DAYS_TO_EXPIRY):.2f}")
        print(f"  t={t_net:.3f}  p={p_net:.5f}")

    print("\nThis is a first-principles backtest with illustrative skew and cost sensitivity")
    print("sweeps, not a calibration against real historical options-market data. See this")
    print("script's docstring for the full list of modeling limitations before treating any")
    print("number here as an economic claim.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
