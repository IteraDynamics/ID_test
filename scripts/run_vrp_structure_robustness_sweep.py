"""VRP iron condor -- structure robustness sweep with JOINT skew+cost application.

Closes the two gaps named in the campaign board's 2026-08-26 VRP corrections:

1. **Structure robustness.** The headline result (127 cycles, 88.2% win rate, p<0.000001) used
   ONE structure: 35 DTE, 16-delta short strikes, 2% wings. Those are reasonable conventions,
   but they were still a pick. A real premium should show up across the neighbourhood of that
   choice, not only at it. This sweeps a grid and reports the DISTRIBUTION -- explicitly
   including where the original pick ranks within it. If the original sits at the top of the
   grid, that is evidence the headline number was a lucky draw, and this script is built to
   surface that rather than hide it. The grid is NOT a search for the best cell: reporting a
   max would be exactly the overfitting this program's governance exists to prevent, and no
   cell here is a recommendation.

2. **Joint skew+cost.** Previously swept independently, then combined by hand. For the MEAN
   that hand-combination was exact arithmetic, not an approximation -- cost is a constant per
   cycle, so mean(pnl - cost) == mean(pnl) - cost. What is NOT recoverable that way is the win
   rate and the t-statistic, which need the real joint series. This applies both together, per
   cycle, so those two are honest.

Comparability across cells (this matters more than it looks): different DTEs produce different
numbers of cycles per year, and different wing widths risk different capital per cycle -- so raw
per-cycle P&L cannot be compared across the grid. Two normalized metrics are reported instead:
annualized P&L per contract, and annualized return on max risk (the capital-efficiency figure
that actually governs sizing at a ~$100k book). For an iron condor only one side can be breached
at expiration, so max risk per cycle = max(put spread width, call spread width) - net credit.

Inherits every modeling limitation of scripts/analyze_vrp_defined_risk_backtest.py (flat
risk-free rate, held-to-expiration, European pricing of American options, illustrative rather
than historical skew and spread assumptions). Observation/analysis only; no recommendation, no
frozen specification, no economic claim beyond what the printed distribution says.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from analyze_vrp_defined_risk_backtest import (  # noqa: E402
    COMMISSION_PER_CONTRACT_LEG,
    CONTRACT_MULTIPLIER,
    DAYS_TO_EXPIRY,
    TARGET_SHORT_DELTA,
    WING_WIDTH_PCT,
    cost_per_cycle,
    load_close_series,
    one_sample_t_test,
    run_backtest,
)

DTE_GRID = (21, 28, 35, 45, 60)
SHORT_DELTA_GRID = (0.10, 0.16, 0.20, 0.30)
WING_WIDTH_GRID = (0.01, 0.02, 0.03)

# (label, skew_slope, spread_cost_per_leg) -- the two assumption sets that bracket the honest
# range established by the independent sweeps on 2026-08-26.
ASSUMPTION_SETS = (
    ("representative (moderate skew, moderate cost)", 0.30, 0.08),
    ("pessimistic (steep skew, wide/crisis cost)", 0.60, 0.20),
)

SIGNIFICANCE_ALPHA = 0.05


def max_risk_per_cycle(df: pd.DataFrame) -> pd.Series:
    """Max loss per cycle in dollars. Only one side of an iron condor can be breached at
    expiration, so the risk is the wider of the two vertical spreads, less the credit taken in."""
    put_width = df["k_short_put"] - df["k_long_put"]
    call_width = df["k_long_call"] - df["k_short_call"]
    worst_width = np.maximum(put_width, call_width)
    return (worst_width - df["net_credit_per_share"]) * CONTRACT_MULTIPLIER


def evaluate_cell(
    spy_close: pd.Series, vix_close: pd.Series, dte: int, delta: float, wing: float,
    skew_slope: float, spread_cost: float,
) -> dict | None:
    df = run_backtest(
        spy_close, vix_close, skew_slope=skew_slope,
        days_to_expiry=dte, target_short_delta=delta, wing_width_pct=wing,
    )
    if len(df) < 10:
        return None

    cost = cost_per_cycle(spread_cost, COMMISSION_PER_CONTRACT_LEG)
    net = df["pnl_dollars"] - cost
    t_stat, p_value = one_sample_t_test(net)

    cycles_per_year = 365 / dte
    risk = max_risk_per_cycle(df)
    mean_risk = float(risk.mean())

    return {
        "dte": dte, "short_delta": delta, "wing_width": wing,
        "cycles": len(df),
        "mean_net_per_cycle": float(net.mean()),
        "win_rate": float((net > 0).mean()),
        "annualized_pnl": float(net.mean() * cycles_per_year),
        "mean_max_risk": mean_risk,
        "annualized_return_on_risk": float(net.mean() * cycles_per_year / mean_risk) if mean_risk > 0 else float("nan"),
        "worst_cycle": float(net.min()),
        "t_stat": t_stat,
        "p_value": p_value,
        "is_original": (dte == DAYS_TO_EXPIRY and abs(delta - TARGET_SHORT_DELTA) < 1e-9
                        and abs(wing - WING_WIDTH_PCT) < 1e-9),
    }


def summarize(results: pd.DataFrame, label: str) -> None:
    print(f"\n{'='*78}")
    print(f"GRID SUMMARY -- {label}")
    print(f"{'='*78}")
    n = len(results)
    pos = int((results["annualized_pnl"] > 0).sum())
    sig = int((results["p_value"] < SIGNIFICANCE_ALPHA).sum())
    sig_pos = int(((results["p_value"] < SIGNIFICANCE_ALPHA) & (results["annualized_pnl"] > 0)).sum())
    print(f"cells evaluated: {n}")
    print(f"  positive annualized P&L:            {pos}/{n} ({pos/n*100:.0f}%)")
    print(f"  significant at p<{SIGNIFICANCE_ALPHA}:              {sig}/{n} ({sig/n*100:.0f}%)")
    print(f"  significant AND positive:           {sig_pos}/{n} ({sig_pos/n*100:.0f}%)")

    ror = results["annualized_return_on_risk"] * 100
    print(f"\nannualized return on max risk across the grid:")
    print(f"  min={ror.min():+.1f}%  p25={ror.quantile(0.25):+.1f}%  median={ror.median():+.1f}%  "
          f"p75={ror.quantile(0.75):+.1f}%  max={ror.max():+.1f}%")

    original = results[results["is_original"]]
    if len(original) == 1:
        row = original.iloc[0]
        pct_rank = float((results["annualized_return_on_risk"] < row["annualized_return_on_risk"]).mean())
        print(f"\nANTI-CHERRY-PICK CHECK -- where the originally-chosen structure sits")
        print(f"  original ({DAYS_TO_EXPIRY}d, {TARGET_SHORT_DELTA:.2f}delta, {WING_WIDTH_PCT:.0%} wing): "
              f"return on risk={row['annualized_return_on_risk']*100:+.1f}%/yr, p={row['p_value']:.5f}")
        print(f"  percentile rank within the grid: {pct_rank*100:.0f}th")
        if pct_rank > 0.90:
            print("  WARNING: the original pick sits in the top decile of the grid. That is what a")
            print("  lucky parameter draw looks like -- treat the headline number as optimistic and")
            print("  weight the grid median far more heavily than the original cell.")
        elif pct_rank < 0.10:
            print("  NOTE: the original pick sits in the BOTTOM decile -- the headline understated")
            print("  what this structure family does; still not a reason to switch to a better cell,")
            print("  which would be selecting on the same data.")
        else:
            print("  Original pick is unremarkable within the grid -- the headline number reflects")
            print("  the structure family, not a lucky point. This is the reassuring outcome.")

    print(f"\nworst cell by return on risk:")
    worst = results.loc[results["annualized_return_on_risk"].idxmin()]
    print(f"  {int(worst['dte'])}d / {worst['short_delta']:.2f}delta / {worst['wing_width']:.0%} wing: "
          f"{worst['annualized_return_on_risk']*100:+.1f}%/yr  p={worst['p_value']:.4f}")
    print(f"best cell by return on risk (NOT a recommendation -- reported so the spread is visible):")
    best = results.loc[results["annualized_return_on_risk"].idxmax()]
    print(f"  {int(best['dte'])}d / {best['short_delta']:.2f}delta / {best['wing_width']:.0%} wing: "
          f"{best['annualized_return_on_risk']*100:+.1f}%/yr  p={best['p_value']:.4f}")


def print_full_grid(results: pd.DataFrame) -> None:
    print(f"\n{'DTE':>4} {'delta':>6} {'wing':>5} {'cyc':>4} {'net/cyc':>9} {'win%':>6} "
          f"{'ann.P&L':>9} {'maxrisk':>8} {'ann.RoR':>8} {'p':>9}")
    print("-" * 78)
    for _, r in results.sort_values(["dte", "short_delta", "wing_width"]).iterrows():
        marker = " *" if r["is_original"] else "  "
        print(f"{int(r['dte']):>4} {r['short_delta']:>6.2f} {r['wing_width']:>5.0%} {int(r['cycles']):>4} "
              f"${r['mean_net_per_cycle']:>8.2f} {r['win_rate']*100:>5.1f}% "
              f"${r['annualized_pnl']:>8.2f} ${r['mean_max_risk']:>7.0f} "
              f"{r['annualized_return_on_risk']*100:>7.1f}% {r['p_value']:>9.5f}{marker}")
    print("  (* = the originally-chosen structure)")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--spy-csv", default="data/SPY_1D.csv")
    p.add_argument("--vix-csv", default="data/VIX_1D.csv")
    p.add_argument("--full-grid", action="store_true",
                   help="Print every cell, not just the distribution summary.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    spy_close = load_close_series(args.spy_csv)
    vix_close = load_close_series(args.vix_csv)
    print(f"SPY: {spy_close.index.min().date()} -> {spy_close.index.max().date()} ({len(spy_close)} rows)")
    print(f"VIX: {vix_close.index.min().date()} -> {vix_close.index.max().date()} ({len(vix_close)} rows)")

    total_cells = len(DTE_GRID) * len(SHORT_DELTA_GRID) * len(WING_WIDTH_GRID)
    print(f"\nSweeping {total_cells} structures "
          f"({len(DTE_GRID)} DTE x {len(SHORT_DELTA_GRID)} delta x {len(WING_WIDTH_GRID)} wing) "
          f"under {len(ASSUMPTION_SETS)} joint skew+cost assumption sets.")
    print("The metric of interest is the DISTRIBUTION, not the best cell -- see this script's")
    print("docstring for why reporting a max would be the exact overfitting this is testing for.")

    for label, skew_slope, spread_cost in ASSUMPTION_SETS:
        rows = []
        for dte in DTE_GRID:
            for delta in SHORT_DELTA_GRID:
                for wing in WING_WIDTH_GRID:
                    cell = evaluate_cell(spy_close, vix_close, dte, delta, wing, skew_slope, spread_cost)
                    if cell is not None:
                        rows.append(cell)
        results = pd.DataFrame(rows)
        if results.empty:
            print(f"\n{label}: no cells produced enough cycles to evaluate.")
            continue
        summarize(results, label)
        if args.full_grid:
            print_full_grid(results)

    print("\nInherits every modeling limitation of analyze_vrp_defined_risk_backtest.py. No cell")
    print("above is a recommendation; selecting the best-performing structure from this grid on")
    print("the same data that produced it would be precisely the error this sweep exists to detect.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
