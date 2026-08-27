"""Cash-secured SPY put selling -- the lower-approval-tier fallback for harvesting the VRP.

Motivation (2026-08-26): the defined-risk iron condor candidate requires spread-level options
approval. If that approval is unavailable, the question is whether a structure at the LOWEST
approval tier -- selling cash-secured puts, where the broker's risk is minimal because the cash
to buy the shares is already posted -- harvests enough of the same premium to be worth running.
Answering that BEFORE an approval decision converts an open risk into a known quantity.

This is not a consolation prize on its face. The volatility risk premium is concentrated on the
PUT side: OTM puts carry the crash-insurance bid, which is exactly what the skew sweep
demonstrated when steeper skew REDUCED the condor's edge (the condor must buy that expensive put
wing back as protection). A naked-but-cash-secured put seller keeps it.

FALSIFIABLE PREDICTION, stated before running: skew should IMPROVE the cash-secured put result,
where it DEGRADED the condor result. If it does not, either that reasoning or this code is
wrong, and which one needs finding out.

That prediction had a confound worth disentangling rather than assuming away: at a FIXED STRIKE
the claim is unambiguous (higher local vol on an OTM put means more credit for the same real
risk), but this script targets a fixed DELTA, and under skew the delta-matched strike moves
further OTM -- which cuts credit and opposes the vol effect. Both framings were checked directly
before the real run. Fixed strike: credit $1.932 -> $2.696 -> $3.554/share across flat/moderate/
steep skew. Fixed 0.16 delta: $3.129 -> $3.423 -> $3.780/share, with the strike simultaneously
moving from 4.88% to 5.87% OTM. The higher local vol dominates, so under skew the delta-targeted
put seller collects MORE credit at a SAFER strike -- better on both axes, and the opposite of
what skew did to the condor.

What the fallback costs, and this is not small:
  - Capital intensity. One contract requires strike x 100 in posted cash -- with SPY in the
    hundreds of dollars, that is a large fraction of a ~$100k book for a SINGLE contract, versus
    roughly $550 of max risk for one condor. Position count, and therefore materiality, is capped
    by capital rather than by risk appetite.
  - No defined-risk floor. The condor's loss is capped by its long wing. A put seller's loss is
    bounded only by the strike falling to zero, and assignment means owning SPY through the
    decline. Bounded, but far worse in the tail.
  - Offsetting advantages: ONE leg instead of four (a quarter of the spread/commission drag,
    which matters because execution cost was the condor's binding constraint), and the posted
    collateral sits in cash earning interest, so the option premium is INCREMENTAL to a cash
    yield rather than replacing it.

Comparison discipline: return on collateral here is not the same quantity as the condor's return
on max risk, and the two must not be read as directly comparable -- collateral is capital
committed but largely safe, whereas max risk is capital genuinely at risk. Both are reported in
dollars per year at a ~$100k book so the economically meaningful comparison is possible.

Inherits every modeling limitation of scripts/analyze_vrp_defined_risk_backtest.py. Observation
only; no recommendation, no frozen specification.
"""

from __future__ import annotations

import argparse
import math
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from analyze_vrp_defined_risk_backtest import (  # noqa: E402
    COMMISSION_PER_CONTRACT_LEG,
    CONTRACT_MULTIPLIER,
    DAYS_TO_EXPIRY,
    RISK_FREE_RATE,
    SKEW_SLOPE_SCENARIOS,
    SPREAD_COST_SCENARIOS,
    bs_price,
    cost_per_cycle,
    find_strike_for_delta,
    load_close_series,
    one_sample_t_test,
    skewed_sigma,
)

PUT_DELTA_GRID = (0.10, 0.16, 0.20, 0.30)
DEFAULT_CAPITAL = 100_000.0


def run_csp_backtest(
    spy_close: pd.Series, vix_close: pd.Series, target_delta: float,
    skew_slope: float = 0.0, days_to_expiry: int = DAYS_TO_EXPIRY,
) -> pd.DataFrame:
    """Non-overlapping cycles: sell one cash-secured put at target_delta, hold to expiration.

    Same non-overlapping construction as the condor backtest, so the two speak to the same
    population of periods and a plain t-test stays legitimate."""
    common = spy_close.index.intersection(vix_close.index)
    spy_close = spy_close.loc[common].sort_index()
    vix_close = vix_close.loc[common].sort_index()

    t_years = days_to_expiry / 365.0
    rows = []
    cursor = spy_close.index.min()
    last = spy_close.index.max()

    while True:
        entry_candidates = spy_close.index[spy_close.index >= cursor]
        if len(entry_candidates) == 0:
            break
        entry = entry_candidates[0]
        expiry_candidates = spy_close.index[spy_close.index >= entry + timedelta(days=days_to_expiry)]
        if len(expiry_candidates) == 0:
            break
        expiry = expiry_candidates[0]

        spot = float(spy_close.loc[entry])
        sigma = float(vix_close.loc[entry]) / 100.0
        strike = find_strike_for_delta(
            spot, t_years, sigma, RISK_FREE_RATE, is_call=False,
            target_abs_delta=target_delta, skew_slope=skew_slope,
        )
        local_sigma = skewed_sigma(spot, strike, sigma, skew_slope)
        credit = bs_price(spot, strike, t_years, local_sigma, RISK_FREE_RATE, is_call=False)

        spot_expiry = float(spy_close.loc[expiry])
        # Settlement: the short put is assigned if it finishes in the money.
        assigned_loss = max(0.0, strike - spot_expiry)
        pnl_per_share = credit - assigned_loss

        rows.append({
            "entry_date": entry, "expiry_date": expiry,
            "spot_entry": spot, "spot_expiry": spot_expiry, "vix_entry": sigma * 100,
            "strike": strike, "credit_per_share": credit,
            "collateral": strike * CONTRACT_MULTIPLIER,
            "assigned": spot_expiry < strike,
            "pnl_dollars": pnl_per_share * CONTRACT_MULTIPLIER,
        })
        cursor = expiry + timedelta(days=1)
        if cursor > last:
            break

    return pd.DataFrame(rows)


def report(df: pd.DataFrame, label: str, spread_cost: float, capital: float, days_to_expiry: int) -> dict:
    cost = cost_per_cycle(spread_cost, COMMISSION_PER_CONTRACT_LEG, n_legs=1)
    net = df["pnl_dollars"] - cost
    t_stat, p_value = one_sample_t_test(net)
    cycles_per_year = 365 / days_to_expiry
    mean_collateral = float(df["collateral"].mean())
    contracts_affordable = int(capital // mean_collateral)
    annual_per_contract = float(net.mean() * cycles_per_year)

    print(f"\n{label}")
    print(f"  cycles={len(df)}  assignment rate={df['assigned'].mean()*100:.1f}%  "
          f"win rate={(net > 0).mean()*100:.1f}%")
    print(f"  mean net=${net.mean():.2f}/cycle  median=${net.median():.2f}  "
          f"worst=${net.min():.2f}")
    print(f"  mean collateral=${mean_collateral:,.0f}/contract  "
          f"contracts affordable at ${capital:,.0f}: {contracts_affordable}")
    print(f"  annualized per contract=${annual_per_contract:,.0f}  "
          f"return on collateral={annual_per_contract/mean_collateral*100:.2f}%/yr")
    print(f"  AT FULL SIZE ({contracts_affordable} contract(s)): "
          f"${annual_per_contract*contracts_affordable:,.0f}/yr "
          f"= {annual_per_contract*contracts_affordable/capital*100:.2f}% of a ${capital:,.0f} book")
    print(f"  t={t_stat:.3f}  p={p_value:.6f}")
    return {
        "annual_per_contract": annual_per_contract,
        "contracts": contracts_affordable,
        "annual_at_size": annual_per_contract * contracts_affordable,
        "mean_collateral": mean_collateral,
        "worst_cycle": float(net.min()),
        "p_value": p_value,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--spy-csv", default="data/SPY_1D.csv")
    p.add_argument("--vix-csv", default="data/VIX_1D.csv")
    p.add_argument("--capital", type=float, default=DEFAULT_CAPITAL)
    p.add_argument("--days-to-expiry", type=int, default=DAYS_TO_EXPIRY)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    spy = load_close_series(args.spy_csv)
    vix = load_close_series(args.vix_csv)
    print(f"SPY: {spy.index.min().date()} -> {spy.index.max().date()} ({len(spy)} rows)")
    print(f"VIX: {vix.index.min().date()} -> {vix.index.max().date()} ({len(vix)} rows)")
    print(f"\nCash-secured SPY put, {args.days_to_expiry} DTE, held to expiration, "
          f"ONE leg (vs the condor's four).")
    print(f"Latest SPY close ${spy.iloc[-1]:,.2f} -- collateral scales with the strike, which is")
    print("the fallback's central constraint at a ~$100k book.")

    moderate_spread = SPREAD_COST_SCENARIOS[1][1]

    print(f"\n{'='*74}")
    print(f"Delta sweep (flat vol, moderate execution cost ${moderate_spread:.2f}/leg)")
    print(f"{'='*74}")
    for delta in PUT_DELTA_GRID:
        df = run_csp_backtest(spy, vix, delta, skew_slope=0.0, days_to_expiry=args.days_to_expiry)
        if len(df) < 10:
            print(f"\n{delta:.2f} delta: only {len(df)} cycles, too few")
            continue
        report(df, f"{delta:.2f} delta put:", moderate_spread, args.capital, args.days_to_expiry)

    print(f"\n{'='*74}")
    print("SKEW SENSITIVITY -- the pre-registered falsifiable prediction")
    print("Skew should IMPROVE this result (the put seller keeps the crash-insurance bid),")
    print("where it DEGRADED the condor (which must buy that expensive put wing back).")
    print("If credit does not rise with skew steepness, the reasoning or the code is wrong.")
    print(f"{'='*74}")
    for label, slope in SKEW_SLOPE_SCENARIOS:
        df = run_csp_backtest(spy, vix, 0.16, skew_slope=slope, days_to_expiry=args.days_to_expiry)
        cost = cost_per_cycle(moderate_spread, COMMISSION_PER_CONTRACT_LEG, n_legs=1)
        net = df["pnl_dollars"] - cost
        t_stat, p_value = one_sample_t_test(net)
        print(f"\n{label} (slope={slope}): mean credit=${df['credit_per_share'].mean():.3f}/share  "
              f"mean net=${net.mean():.2f}/cycle  p={p_value:.6f}")

    print(f"\n{'='*74}")
    print("HONEST COMPARISON vs the defined-risk condor")
    print(f"{'='*74}")
    print("Read these as different capital profiles, NOT as one number beating another:")
    print("  - condor max risk (~$550/contract) is capital genuinely AT RISK;")
    print("  - CSP collateral is capital COMMITTED but largely safe, and earns cash interest,")
    print("    so the option premium is incremental to a cash yield rather than replacing it;")
    print("  - the CSP's tail is far worse: no long wing, assignment means owning SPY through")
    print("    the decline, bounded only by the strike going to zero;")
    print("  - the CSP pays a quarter of the execution drag (1 leg vs 4), which matters because")
    print("    execution cost was the condor's binding constraint;")
    print("  - and the CSP needs only the LOWEST options approval tier, which is the entire")
    print("    reason this fallback was tested.")
    print("\nObservation only. Inherits every modeling limitation of the condor backtest.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
