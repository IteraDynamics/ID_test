"""Campaign #59 (planning) — PEAD dollar materiality at ~$100k capital, Gate 3.

Per CLAUDE.md's standing operating fact: "Every edge examined so far lands at
roughly $400-1,500/yr. Say so plainly." This runs that same discipline against
PEAD before any charter is drafted, using Stage 2/3's own event-level output
(artifacts/pead_forward_drift/event_level_car.csv) rather than eyeballing the
percentage spread from the printed summaries.

Strategy modeled: each Q5 (top-surprise) event is a market-neutral LONG
(long stock, short SPY of equal notional); each Q1 (bottom-surprise) event is
a market-neutral SHORT (short stock, long SPY). Because Stage 2's abnormal
return is already (stock - SPY), the position's dollar P&L per event is
+abnormal_return for a Q5 long and -abnormal_return for a Q1 short (a
negative abnormal return realized as profit on the short side). This is the
same construction Stage 3's beta-confound test already assumes; it is not
invented here.

Default period is CONFIRMATION ONLY (>= --split-date), re-forming quintiles
independently within that period -- same OOS discipline as
validate_pead_oos_bootstrap.py's Part A. Using the full pooled sample would
overstate materiality with a number partly drawn from the discovery period
that already got the multiplicity treatment; the confirmation period is the
honest one to size a position against.

Capacity, modeled rather than assumed: equal-weighting every event at
capital / N events ignores that positions overlap in time (earnings cluster
in four seasonal windows/year), so many can be open simultaneously -- true
per-position size is much smaller than capital / (events/year) would imply.
This runs a sweep-line max-concurrent-open-positions count over each event's
[entry, exit] window and sizes positions at capital / max_concurrent -- an
UPPER BOUND (fully invested at the single worst-case peak-overlap moment),
not a robust operating point with any buffer.

Two explicit approximations, stated rather than hidden:
  1. Exit date is entry + round(checkpoint_trading_days * 7/5) calendar days
     -- a fixed weekday ratio, not each ticker's actual trading calendar
     (Stage 2 has that per-ticker, but reloading ~200 price files just to
     get an exact exit date is not worth it for a materiality estimate).
  2. The stock/SPY hedge leg is assumed frictionless beyond the stated
     cost-bps scenario -- no separate hedge-leg slippage or borrow cost is
     modeled. Short-borrow cost/availability for the Q1 leg specifically is
     NOT modeled at all and would only make this number worse, never better.

Cost scenarios are round-trip, all-in (both legs, entry+exit) in bps of
position notional -- deliberately a single scenario knob rather than
decomposed commission/slippage, because at this stage the point is the
order of magnitude, not a precise execution model.

This is a Gate-3 materiality estimate for chartering purposes only. It is
not a backtest, not an execution plan, and not a claim that this is
tradeable today -- tradeability (venue, shorting mechanics for individual
equities, actual borrow cost) is a separate, unresolved gate.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

N_QUINTILES = 5
MIN_EVENTS_FOR_QUINTILES = N_QUINTILES * 20  # same sanity floor as validate_pead_oos_bootstrap.py
TRADING_TO_CALENDAR_DAY_RATIO = 7 / 5  # approximation -- see module docstring


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--event-level-car-file", default="artifacts/pead_forward_drift/event_level_car.csv")
    parser.add_argument(
        "--checkpoint",
        type=int,
        default=60,
        choices=(1, 5, 20, 60),
        help="Forward-day checkpoint to size the holding period and P&L on. Default 60 -- the "
        "beta-confound test's own focus was day+20/day+60, where the confirmation-period spread "
        "actually lives.",
    )
    parser.add_argument(
        "--period",
        choices=("confirmation", "discovery", "full"),
        default="confirmation",
        help="Which slice of events to size against. Default confirmation-only (OOS), matching "
        "Stage 3's discipline -- see module docstring for why full/discovery would overstate this.",
    )
    parser.add_argument("--split-date", default="2020-01-01")
    parser.add_argument("--capital-scenarios", type=float, nargs="+", default=[50_000, 100_000, 150_000])
    parser.add_argument(
        "--cost-bps-scenarios",
        type=float,
        nargs="+",
        default=[10.0, 25.0, 50.0],
        help="Round-trip, all-in cost per position in bps of notional (both legs, entry+exit combined).",
    )
    parser.add_argument("--output-dir", default="artifacts/pead_dollar_materiality")
    return parser.parse_args()


def load_period_events(path: Path, period: str, split_date: str) -> tuple[pd.DataFrame, float]:
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run scripts/analyze_pead_forward_drift.py first -- this reuses "
            "its event-level output rather than recomputing CAR from scratch."
        )
    events = pd.read_csv(path, parse_dates=["date"])
    if events["date"].dt.tz is None:
        events["date"] = events["date"].dt.tz_localize("UTC")

    split_ts = pd.Timestamp(split_date, tz="UTC")
    if period == "confirmation":
        events = events[events["date"] >= split_ts].copy()
    elif period == "discovery":
        events = events[events["date"] < split_ts].copy()
    # "full" keeps everything.

    if len(events) < MIN_EVENTS_FOR_QUINTILES:
        raise RuntimeError(
            f"Only {len(events)} events in period={period!r} -- below the {MIN_EVENTS_FOR_QUINTILES}-event "
            "floor for quintiles to be meaningful. Try --period full or check Stage 1/2 ran to completion."
        )

    span_days = (events["date"].max() - events["date"].min()).days
    period_years = max(span_days / 365.25, 1e-9)
    return events.reset_index(drop=True), period_years


def form_positions(events: pd.DataFrame, checkpoint: int) -> pd.DataFrame:
    """Re-forms quintiles on THIS slice's own z_surprise distribution (never
    reuses boundaries from elsewhere -- same rule as Stage 3). Returns one
    row per Q5-long / Q1-short position with entry/exit dates and the
    dollar-per-$1-notional P&L contribution."""
    events = events.copy()
    events["_quintile"] = pd.qcut(events["z_surprise"], N_QUINTILES, labels=False, duplicates="drop")
    n_quintiles_actual = events["_quintile"].nunique()
    if n_quintiles_actual < 2:
        raise RuntimeError("z_surprise too degenerate in this period to split into quintiles.")

    top = events[events["_quintile"] == events["_quintile"].max()].copy()
    bottom = events[events["_quintile"] == events["_quintile"].min()].copy()

    col = str(checkpoint)
    top["side"] = "long_Q5"
    top["notional_return"] = top[col]
    bottom["side"] = "short_Q1"
    bottom["notional_return"] = -bottom[col]

    positions = pd.concat([top, bottom], ignore_index=True)
    hold_calendar_days = round(checkpoint * TRADING_TO_CALENDAR_DAY_RATIO)
    positions["entry_date"] = positions["date"]
    positions["exit_date"] = positions["date"] + pd.Timedelta(days=hold_calendar_days)
    return positions[["ticker", "side", "entry_date", "exit_date", "notional_return"]]


def max_concurrent_positions(positions: pd.DataFrame) -> int:
    """Sweep-line over entry/exit events -- the true peak number of positions
    open at any single instant, not an average."""
    events = []
    for _, pos in positions.iterrows():
        events.append((pos["entry_date"], 1))
        events.append((pos["exit_date"], -1))
    events.sort(key=lambda e: (e[0], e[1]))  # exits (-1) before entries (+1) on a tie -- conservative

    concurrent = 0
    peak = 0
    for _, delta in events:
        concurrent += delta
        peak = max(peak, concurrent)
    return peak


def compute_materiality_table(
    positions: pd.DataFrame,
    period_years: float,
    max_concurrent: int,
    capital_scenarios: list[float],
    cost_bps_scenarios: list[float],
) -> dict:
    gross_return_sum = float(positions["notional_return"].sum())
    n_positions = int(len(positions))

    table: dict = {
        "n_positions": n_positions,
        "n_long_q5": int((positions["side"] == "long_Q5").sum()),
        "n_short_q1": int((positions["side"] == "short_Q1").sum()),
        "period_years": period_years,
        "max_concurrent_positions": max_concurrent,
        "scenarios": {},
    }

    for capital in capital_scenarios:
        position_size = capital / max_concurrent
        gross_dollar_per_yr = position_size * gross_return_sum / period_years

        capital_key = f"${capital:,.0f}"
        table["scenarios"][capital_key] = {"position_size": position_size, "cost_scenarios": {}}

        for cost_bps in cost_bps_scenarios:
            cost_per_position = position_size * (cost_bps / 10_000.0)
            total_cost = cost_per_position * n_positions
            net_dollar_per_yr = gross_dollar_per_yr - (total_cost / period_years)
            table["scenarios"][capital_key]["cost_scenarios"][f"{cost_bps:.0f}bps"] = {
                "gross_per_yr": gross_dollar_per_yr,
                "cost_per_yr": total_cost / period_years,
                "net_per_yr": net_dollar_per_yr,
            }

    return table


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    events, period_years = load_period_events(Path(args.event_level_car_file), args.period, args.split_date)
    print(f"Period: {args.period} ({period_years:.2f} years), {len(events)} events with valid forward windows.\n")

    positions = form_positions(events, args.checkpoint)
    max_concurrent = max_concurrent_positions(positions)
    hold_calendar_days = round(args.checkpoint * TRADING_TO_CALENDAR_DAY_RATIO)

    print(f"Checkpoint: day+{args.checkpoint} trading (~{hold_calendar_days} calendar days held per position)")
    print(f"Positions: {len(positions)} ({(positions['side'] == 'long_Q5').sum()} long Q5, "
          f"{(positions['side'] == 'short_Q1').sum()} short Q1)")
    print(f"Peak concurrent open positions (sweep-line): {max_concurrent}")
    print(
        "  -- sizing below is capital / peak_concurrent: fully invested at the single worst-case "
        "overlap moment, an upper bound on position size, not a buffered operating point.\n"
    )

    table = compute_materiality_table(
        positions, period_years, max_concurrent, args.capital_scenarios, args.cost_bps_scenarios
    )

    header = f"{'Capital':>12} | {'Position $':>12} | " + " | ".join(f"{b:.0f}bps net/yr" for b in args.cost_bps_scenarios)
    print(header)
    print("-" * len(header))
    for capital in args.capital_scenarios:
        capital_key = f"${capital:,.0f}"
        scenario = table["scenarios"][capital_key]
        row = f"{capital_key:>12} | {scenario['position_size']:>12,.0f} | "
        row += " | ".join(
            f"${scenario['cost_scenarios'][f'{b:.0f}bps']['net_per_yr']:>+11,.0f}" for b in args.cost_bps_scenarios
        )
        print(row)

    gross_at_100k = None
    for capital in args.capital_scenarios:
        if abs(capital - 100_000) < 1.0:
            gross_at_100k = table["scenarios"][f"${capital:,.0f}"]["cost_scenarios"][
                f"{args.cost_bps_scenarios[0]:.0f}bps"
            ]["gross_per_yr"]
    if gross_at_100k is not None:
        print(f"\nGross (pre-cost) at $100k: ${gross_at_100k:+,.0f}/yr.")
    print(
        "\nReading this against the fund's own operating fact: every edge examined so far lands "
        "at roughly $400-1,500/yr at this capital scale. If the net figures above sit in or below "
        "that band, this is a diversification/Sharpe candidate, not an alpha engine -- say so "
        "plainly rather than round up. If they sit meaningfully above it, that is itself a reason "
        "for more scrutiny (short-borrow cost is NOT modeled here and equity shorting mechanics "
        "are a separate, unresolved tradeability gate), not a reason to charter faster."
    )

    (output_dir / "summary.json").write_text(json.dumps(table, indent=2, default=str), encoding="utf-8")
    positions.to_csv(output_dir / "positions.csv", index=False)
    print(f"\nWrote results to {output_dir}/")


if __name__ == "__main__":
    main()
