"""Campaign #59 (planning) — PEAD beta-confound test, ONE pre-committed check.

Per the fork left open after Stage 3: the confirmation period (2020+)
showed a dramatically larger Q5-Q1 spread than discovery (2002-2020),
and the honest open question was WHY -- a genuine regime shift, or a
disguised market-beta/momentum confound from an unusually strong,
one-directional 2020-2026 market. This is that one check, run once, not
iteratively -- re-slicing the same historical sample repeatedly looking
for a story is exactly the multiplicity trap this fund's own standing
amendments exist to prevent.

The precise, testable version of the confound: Stage 2's abnormal returns
are already (stock return - SPY return) over each window, which already
removes SPY's own return equally from every event -- so "the market went
up, so everything looks better" is NOT a live explanation by construction.
What COULD still explain the spread: if Q5 (positive-surprise) stocks are
structurally higher-beta than Q1 (negative-surprise) stocks, they would
show larger abnormal returns specifically because the market rallied hard
in 2020-2026 -- a beta effect wearing a surprise-effect costume, not
idiosyncratic drift from the earnings news itself.

Test: within the confirmation period only, for Q5 and Q1 events (re-formed
independently within that period, same as Stage 3's own split), regress
each event's abnormal return on SPY's own contemporaneous forward return
over the identical window, with a quintile interaction term:

    abnormal_return ~ spy_forward_return + is_Q5 + spy_forward_return:is_Q5

The interaction coefficient is the test: does Q5's sensitivity to the
market's own return differ from Q1's? A significant positive interaction
is the beta-confound signature. A near-zero, insignificant interaction is
evidence the spread isn't just differential market exposure.

Plain OLS via normal equations (numpy only, no new dependency) with
proper heteroskedasticity-naive standard errors -- adequate for a single
pre-committed test, not offered as a publication-grade estimator.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

FORWARD_DAY_CHECKPOINTS = (1, 5, 20, 60)
N_QUINTILES = 5
CONFIRMATION_SPLIT_DATE = "2020-01-01"  # matches Stage 3's own split, not re-chosen here


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-level-car-file", default="artifacts/pead_forward_drift/event_level_car.csv")
    parser.add_argument("--benchmark", default="SPY")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--output-dir", default="artifacts/pead_beta_confound")
    return parser.parse_args()


def load_confirmation_q5_q1(path: Path, split_date: str) -> pd.DataFrame:
    events = pd.read_csv(path, parse_dates=["date"])
    if events["date"].dt.tz is None:
        events["date"] = events["date"].dt.tz_localize("UTC")

    confirmation = events[events["date"] >= pd.Timestamp(split_date, tz="UTC")].copy()
    confirmation["_quintile"] = pd.qcut(confirmation["z_surprise"], N_QUINTILES, labels=False, duplicates="drop")
    n_quintiles_actual = confirmation["_quintile"].nunique()

    top = confirmation[confirmation["_quintile"] == confirmation["_quintile"].max()].copy()
    bottom = confirmation[confirmation["_quintile"] == confirmation["_quintile"].min()].copy()
    top["is_q5"] = 1
    bottom["is_q5"] = 0
    print(f"Confirmation period (>= {split_date}): Q5 n={len(top)}, Q1 n={len(bottom)} (of {n_quintiles_actual} quintiles formed)")
    return pd.concat([top, bottom], ignore_index=True)


def load_daily_returns(data_dir: Path, ticker: str) -> pd.Series | None:
    path = data_dir / f"{ticker.upper()}_1D.csv"
    if not path.exists():
        return None
    frame = pd.read_csv(path, parse_dates=["timestamp"])
    frame = frame.sort_values("timestamp").drop_duplicates(subset="timestamp").set_index("timestamp")
    returns = frame["close"].pct_change()
    return returns.dropna()


def spy_forward_return(benchmark_returns: pd.Series, event_date: pd.Timestamp, checkpoint: int) -> float | None:
    """SPY's own cumulative return over the identical window used for that
    event's abnormal return -- not abnormal, the raw benchmark move itself."""
    anchor_pos = int(benchmark_returns.index.searchsorted(event_date))
    if anchor_pos + checkpoint >= len(benchmark_returns):
        return None
    window = benchmark_returns.iloc[anchor_pos : anchor_pos + checkpoint + 1].to_numpy()
    return float(np.cumsum(window)[-1])


def ols_with_stats(X: np.ndarray, y: np.ndarray) -> dict:
    n, k = X.shape
    XtX_inv = np.linalg.inv(X.T @ X)
    beta = XtX_inv @ X.T @ y
    residuals = y - X @ beta
    dof = n - k
    sigma2 = float(residuals @ residuals) / dof
    se = np.sqrt(np.diag(sigma2 * XtX_inv))
    t_stats = beta / se
    p_values = 2 * (1 - stats.t.cdf(np.abs(t_stats), df=dof))
    r_squared = 1 - (residuals @ residuals) / np.sum((y - y.mean()) ** 2)
    return {"beta": beta, "se": se, "t_stats": t_stats, "p_values": p_values, "r_squared": float(r_squared), "n": n}


def run_checkpoint_regression(q5_q1_events: pd.DataFrame, benchmark_returns: pd.Series, checkpoint: int) -> dict:
    col = str(checkpoint)
    spy_returns = []
    valid_rows = []
    for _, event in q5_q1_events.iterrows():
        spy_ret = spy_forward_return(benchmark_returns, event["date"], checkpoint)
        if spy_ret is None:
            continue
        spy_returns.append(spy_ret)
        valid_rows.append(event)

    if len(valid_rows) < 20:
        return {"insufficient": True, "n": len(valid_rows)}

    subset = pd.DataFrame(valid_rows).reset_index(drop=True)
    subset["spy_forward_return"] = spy_returns

    y = subset[col].to_numpy()
    spy_x = subset["spy_forward_return"].to_numpy()
    is_q5 = subset["is_q5"].to_numpy()
    interaction = spy_x * is_q5

    X = np.column_stack([np.ones(len(y)), spy_x, is_q5, interaction])
    fit = ols_with_stats(X, y)

    labels = ["intercept", "spy_forward_return (Q1 slope)", "is_Q5", "spy_forward_return:is_Q5 (slope difference)"]
    result = {"n": fit["n"], "r_squared": fit["r_squared"], "coefficients": {}}
    for label, b, se, t, p in zip(labels, fit["beta"], fit["se"], fit["t_stats"], fit["p_values"]):
        result["coefficients"][label] = {"estimate": float(b), "se": float(se), "t_stat": float(t), "p_value": float(p)}

    q5_slope = fit["beta"][1] + fit["beta"][3]
    result["implied_q1_slope_on_market_return"] = float(fit["beta"][1])
    result["implied_q5_slope_on_market_return"] = float(q5_slope)
    return result


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    q5_q1_events = load_confirmation_q5_q1(Path(args.event_level_car_file), CONFIRMATION_SPLIT_DATE)

    benchmark_returns = load_daily_returns(data_dir, args.benchmark)
    if benchmark_returns is None:
        raise FileNotFoundError(f"Benchmark {args.benchmark}_1D.csv not found in {data_dir}.")

    print(f"\nRegression: abnormal_return ~ spy_forward_return + is_Q5 + spy_forward_return:is_Q5")
    print("The interaction term is the test -- does Q5's market sensitivity differ from Q1's?\n")

    results = {}
    for checkpoint in FORWARD_DAY_CHECKPOINTS:
        print(f"--- day+{checkpoint} ---")
        result = run_checkpoint_regression(q5_q1_events, benchmark_returns, checkpoint)
        results[f"day_{checkpoint}"] = result

        if result.get("insufficient"):
            print(f"  insufficient events with valid forward window ({result['n']})")
            print()
            continue

        interaction = result["coefficients"]["spy_forward_return:is_Q5 (slope difference)"]
        print(f"  n={result['n']}, R²={result['r_squared']:.3f}")
        print(
            f"  Q1 slope on market return: {result['implied_q1_slope_on_market_return']:+.3f}"
        )
        print(
            f"  Q5 slope on market return: {result['implied_q5_slope_on_market_return']:+.3f}"
        )
        print(
            f"  slope difference (interaction): {interaction['estimate']:+.3f} "
            f"t={interaction['t_stat']:+.2f} p={interaction['p_value']:.4f}"
        )
        print()

    (output_dir / "summary.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"Wrote results to {output_dir}/")
    print(
        "\nReading this result: a significant, positive slope-difference at the checkpoints that "
        "drove the confirmation-period spread (day+20/day+60) is the beta-confound signature. A "
        "small, insignificant slope difference is evidence the spread is not simply differential "
        "market exposure. Either way -- this was the one pre-committed check; the fork should be "
        "read from what this actually shows, not re-sliced further."
    )


if __name__ == "__main__":
    main()
