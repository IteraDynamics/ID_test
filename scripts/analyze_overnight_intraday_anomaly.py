"""Campaign #57 (planning) — overnight vs. intraday return anomaly, SPY/QQQ.

Reads data/{ASSET}_1D.csv (produced by scripts/download_equity_data.py) and
splits each daily bar into its overnight leg (prior close -> today's open)
and intraday leg (today's open -> today's close). Reports whether holding
only overnight, only intraday, or continuously (buy-and-hold) would have
performed differently over the same window -- the real, falsifiable form
of the "overnight anomaly" hypothesis.

No lookahead: overnight_return[t] uses only close[t-1] and open[t], both
known before the market opens on day t. intraday_return[t] uses open[t]
and close[t], both realized by the close of day t. Neither series peeks
past its own bar.

Overnight-only requires two trades per day (sell at the open, buy back at
the close) to re-establish the position -- one round trip per day, ~252/yr,
against buy-and-hold's near-zero turnover. Every run automatically reports
three explicitly labeled, honestly-uncertain round-trip cost scenarios
applied to the overnight-only leg only (tight/moderate/wide, see
COST_SCENARIOS_BPS below), the same discipline this fund used on the VRP
options backtest: no verified historical SPY/QQQ spread dataset exists
here, so the assumptions are stated, not measured.

--exclude-start/--exclude-end lets a single episode be excluded and the
full pipeline re-run on the remainder, to check the result isn't one
extreme window doing all the work (this fund has hit that failure mode
more than once). Pass 2020-02-15/2020-04-30 to test the COVID crash
specifically; the flag is general-purpose, not COVID-specific.

Deterministic and replay-safe: same input CSV -> byte-identical output,
per this repo's own convention.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


TRADING_DAYS_PER_YEAR = 252

# Round-trip cost in basis points applied once per day to the overnight-only
# leg (sell at open, buy back at close). Explicitly labeled assumptions, not
# a measured historical spread/commission dataset -- same honesty discipline
# as the VRP options backtest's cost sweep.
COST_SCENARIOS_BPS = {
    "tight": 1.0,      # near-institutional spread capture on the most liquid ETFs in existence
    "moderate": 5.0,   # realistic retail market/limit-order slippage at the open/close auctions
    "wide": 20.0,       # stressed-liquidity / adverse-fill assumption
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset", action="append", required=True)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--output-dir", default="artifacts/overnight_intraday_anomaly")
    parser.add_argument(
        "--exclude-start",
        default=None,
        help="ISO date (e.g. 2020-02-15). Rows in [exclude-start, exclude-end] are dropped "
        "and the full pipeline re-run on the remainder, reported alongside the full sample.",
    )
    parser.add_argument("--exclude-end", default=None)
    return parser.parse_args()


def load_bars(data_dir: Path, asset: str) -> pd.DataFrame:
    path = data_dir / f"{asset.upper()}_1D.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run scripts/download_equity_data.py first "
            f"(requires network access this environment does not have)."
        )
    frame = pd.read_csv(path, parse_dates=["timestamp"])
    frame = frame.sort_values("timestamp").reset_index(drop=True)
    required = {"timestamp", "open", "high", "low", "close"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"{path} missing columns: {missing}")
    return frame


def compute_legs(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    prior_close = out["close"].shift(1)
    out["overnight_return"] = out["open"] / prior_close - 1.0
    out["intraday_return"] = out["close"] / out["open"] - 1.0
    out["close_to_close_return"] = out["close"] / prior_close - 1.0
    return out.dropna(subset=["overnight_return", "intraday_return", "close_to_close_return"])


def summarize(returns: pd.Series, label: str, cost_bps: float = 0.0) -> dict:
    net_returns = returns - (cost_bps / 10_000.0) if cost_bps else returns

    n = int(len(net_returns))
    mean_daily = float(net_returns.mean())
    std_daily = float(net_returns.std(ddof=1))
    t_stat, p_value = stats.ttest_1samp(net_returns.to_numpy(), popmean=0.0)

    ann_return = float((1.0 + mean_daily) ** TRADING_DAYS_PER_YEAR - 1.0)
    ann_vol = float(std_daily * np.sqrt(TRADING_DAYS_PER_YEAR))
    sharpe = float(ann_return / ann_vol) if ann_vol > 0 else float("nan")

    cumulative = float((1.0 + net_returns).prod())
    win_rate = float((net_returns > 0).mean())

    return {
        "label": label,
        "cost_bps_round_trip": cost_bps,
        "n_days": n,
        "mean_daily_return": mean_daily,
        "std_daily_return": std_daily,
        "t_stat": float(t_stat),
        "p_value": float(p_value),
        "annualized_return": ann_return,
        "annualized_vol": ann_vol,
        "annualized_sharpe": sharpe,
        "cumulative_growth_of_1": cumulative,
        "win_rate": win_rate,
    }


def summarize_core(legs: pd.DataFrame, sample_label: str) -> dict:
    """The three unlevered legs, no cost applied -- same as the original report."""
    return {
        "sample": sample_label,
        "window_start": legs["timestamp"].min().isoformat(),
        "window_end": legs["timestamp"].max().isoformat(),
        "n_days": int(len(legs)),
        "overnight_only": summarize(legs["overnight_return"], "overnight_only"),
        "intraday_only": summarize(legs["intraday_return"], "intraday_only"),
        "buy_and_hold": summarize(legs["close_to_close_return"], "buy_and_hold"),
        "overnight_only_costed": {
            scenario: summarize(legs["overnight_return"], f"overnight_only_{scenario}", cost_bps=bps)
            for scenario, bps in COST_SCENARIOS_BPS.items()
        },
    }


def run_asset(
    data_dir: Path,
    output_dir: Path,
    asset: str,
    exclude_start: str | None,
    exclude_end: str | None,
) -> dict:
    bars = load_bars(data_dir, asset)
    legs = compute_legs(bars)

    result = {"asset": asset.upper(), "full_sample": summarize_core(legs, "full_sample")}

    if exclude_start and exclude_end:
        window_start = pd.Timestamp(exclude_start, tz="UTC")
        window_end = pd.Timestamp(exclude_end, tz="UTC")
        in_window = (legs["timestamp"] >= window_start) & (legs["timestamp"] <= window_end)
        excluded_n = int(in_window.sum())
        legs_ex = legs.loc[~in_window]
        result["excluded_window"] = {"start": exclude_start, "end": exclude_end, "n_days_excluded": excluded_n}
        result["ex_window_sample"] = summarize_core(legs_ex, f"excluding_{exclude_start}_to_{exclude_end}")

    output_dir.mkdir(parents=True, exist_ok=True)
    legs.to_csv(output_dir / f"{asset.upper()}_daily_legs.csv", index=False)
    (output_dir / f"{asset.upper()}_summary.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8"
    )
    return result


def _print_sample(tag: str, sample: dict) -> None:
    print(f"  [{tag}] n={sample['n_days']} window={sample['window_start']}..{sample['window_end']}")
    for leg in ("overnight_only", "intraday_only", "buy_and_hold"):
        s = sample[leg]
        print(
            f"    {leg:14s} sharpe={s['annualized_sharpe']:+.3f} "
            f"ann_return={s['annualized_return']:+.2%} t={s['t_stat']:+.2f} p={s['p_value']:.4f}"
        )
    print(f"    overnight_only, cost-adjusted (round trip, daily):")
    for scenario, s in sample["overnight_only_costed"].items():
        print(
            f"      {scenario:9s} ({s['cost_bps_round_trip']:.0f}bps) "
            f"sharpe={s['annualized_sharpe']:+.3f} ann_return={s['annualized_return']:+.2%} "
            f"p={s['p_value']:.4f}"
        )


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)

    all_results = {}
    for asset in dict.fromkeys(a.strip().upper() for a in args.asset if a.strip()):
        print(f"--- {asset} ---")
        result = run_asset(data_dir, output_dir, asset, args.exclude_start, args.exclude_end)
        all_results[asset] = result

        _print_sample("full_sample", result["full_sample"])
        if "ex_window_sample" in result:
            excl = result["excluded_window"]
            print(f"  Excluding {excl['start']}..{excl['end']} ({excl['n_days_excluded']} days dropped):")
            _print_sample("ex_window", result["ex_window_sample"])
        print()

    (output_dir / "combined_summary.json").write_text(
        json.dumps(all_results, indent=2, default=str), encoding="utf-8"
    )
    print(f"Wrote results to {output_dir}/")


if __name__ == "__main__":
    main()
