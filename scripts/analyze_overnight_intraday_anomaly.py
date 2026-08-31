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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset", action="append", required=True)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--output-dir", default="artifacts/overnight_intraday_anomaly")
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


def summarize(returns: pd.Series, label: str) -> dict:
    n = int(len(returns))
    mean_daily = float(returns.mean())
    std_daily = float(returns.std(ddof=1))
    t_stat, p_value = stats.ttest_1samp(returns.to_numpy(), popmean=0.0)

    ann_return = float((1.0 + mean_daily) ** TRADING_DAYS_PER_YEAR - 1.0)
    ann_vol = float(std_daily * np.sqrt(TRADING_DAYS_PER_YEAR))
    sharpe = float(ann_return / ann_vol) if ann_vol > 0 else float("nan")

    cumulative = float((1.0 + returns).prod())
    win_rate = float((returns > 0).mean())

    return {
        "label": label,
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


def run_asset(data_dir: Path, output_dir: Path, asset: str) -> dict:
    bars = load_bars(data_dir, asset)
    legs = compute_legs(bars)

    result = {
        "asset": asset.upper(),
        "window_start": legs["timestamp"].min().isoformat(),
        "window_end": legs["timestamp"].max().isoformat(),
        "overnight_only": summarize(legs["overnight_return"], "overnight_only"),
        "intraday_only": summarize(legs["intraday_return"], "intraday_only"),
        "buy_and_hold": summarize(legs["close_to_close_return"], "buy_and_hold"),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    legs.to_csv(output_dir / f"{asset.upper()}_daily_legs.csv", index=False)
    (output_dir / f"{asset.upper()}_summary.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8"
    )
    return result


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)

    all_results = {}
    for asset in dict.fromkeys(a.strip().upper() for a in args.asset if a.strip()):
        print(f"--- {asset} ---")
        result = run_asset(data_dir, output_dir, asset)
        all_results[asset] = result
        for leg in ("overnight_only", "intraday_only", "buy_and_hold"):
            s = result[leg]
            print(
                f"  {leg:14s} n={s['n_days']:>5} "
                f"ann_return={s['annualized_return']:+.2%} "
                f"ann_vol={s['annualized_vol']:.2%} "
                f"sharpe={s['annualized_sharpe']:+.3f} "
                f"t={s['t_stat']:+.2f} p={s['p_value']:.4f} "
                f"win_rate={s['win_rate']:.2%}"
            )
        print()

    (output_dir / "combined_summary.json").write_text(
        json.dumps(all_results, indent=2, default=str), encoding="utf-8"
    )
    print(f"Wrote results to {output_dir}/")


if __name__ == "__main__":
    main()
