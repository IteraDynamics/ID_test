#!/usr/bin/env python

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from research.strategies.equity_spy_trend_v2 import generate_intent
from research.strategies.contracts import StrategyContext


def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df[df.columns[0]] = pd.to_datetime(df[df.columns[0]])
    df = df.set_index(df.columns[0])
    return df


def run_backtest(df: pd.DataFrame, capital: float):
    exposure = 0.0
    cash = capital
    shares = 0.0
    equity_curve = []

    for i in range(len(df)):
        slice_df = df.iloc[: i + 1]

        ctx = StrategyContext(
            current_exposure_frac=exposure,
            asset="SPY",
            regime="UNKNOWN",
        )

        intent = generate_intent(slice_df, ctx, closed_only=True)

        price = float(slice_df["close"].iloc[-1])

        target_exposure = intent.desired_exposure_frac
        target_value = target_exposure * (cash + shares * price)
        current_value = shares * price

        delta_value = target_value - current_value

        if abs(delta_value) > 1e-6:
            delta_shares = delta_value / price
            shares += delta_shares
            cash -= delta_value

        exposure = target_exposure

        nav = cash + shares * price
        equity_curve.append(nav)

    return pd.Series(equity_curve, index=df.index)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True)
    p.add_argument("--capital", type=float, default=100000)
    args = p.parse_args()

    df = load_data(args.data)

    equity = run_backtest(df, args.capital)

    out = Path("artifacts/spy_trend_v2")
    out.mkdir(parents=True, exist_ok=True)

    equity.to_csv(out / "equity_curve.csv")

    print("Saved Equity v2 backtest to artifacts/spy_trend_v2")


if __name__ == "__main__":
    main()
