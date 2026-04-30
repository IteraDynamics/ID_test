#!/usr/bin/env python
"""
Itera Dynamics — SPY Daily Equity Trend Backtest Runner

Research-only runner for equity_spy_trend_v1.

Purpose:
    Validate that the Itera StrategyIntent architecture can run cleanly on
    daily equity ETF data.

Classification:
    Research-only. This does not affect crypto Fund v1 / Fund v2 runtime.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from research.harness.data_loader import load_ohlcv
from research.regimes.contracts import RegimeLabel
from research.strategies.contracts import Action, StrategyContext
from research.strategies.equity_spy_trend_v1 import generate_intent


def run_backtest(df: pd.DataFrame, capital: float = 100000.0):
    equity = capital
    exposure = 0.0
    entry_price = None
    trades = 0

    equity_curve = []

    for i in range(len(df)):
        slice_df = df.iloc[: i + 1]

        ctx = StrategyContext(
            regime=RegimeLabel.UNKNOWN,
            current_exposure_frac=exposure,
            asset="SPY",
            bar_index=i,
        )

        intent = generate_intent(slice_df, ctx, closed_only=True)
        price = float(slice_df["close"].iloc[-1])

        if intent.action == Action.ENTER_LONG and exposure == 0.0:
            exposure = intent.desired_exposure_frac
            entry_price = price
            trades += 1

        elif intent.action in (Action.EXIT_LONG, Action.FLAT) and exposure > 0.0:
            pnl = (price / entry_price - 1.0) * exposure
            equity *= (1.0 + pnl)
            exposure = 0.0
            entry_price = None
            trades += 1

        equity_curve.append(equity)

    return equity_curve, trades


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run SPY daily equity trend backtest")
    parser.add_argument("--data", required=True, help="Path to SPY daily CSV")
    parser.add_argument("--start", default=None)
    parser.add_argument("--end", default=None)
    parser.add_argument("--capital", type=float, default=100000)

    args = parser.parse_args()

    df = load_ohlcv(args.data, start=args.start, end=args.end, asset="SPY")

    print(f"Loaded {len(df)} bars: {df.index[0]} → {df.index[-1]}")

    equity_curve, trades = run_backtest(df, args.capital)

    total_return = equity_curve[-1] / args.capital - 1.0

    print("\n=== SPY TREND BACKTEST ===")
    print(f"Capital: ${args.capital:,.0f}")
    print(f"Total Return: {total_return * 100:.2f}%")
    print(f"Trades: {trades}")

    out = Path("artifacts/spy_trend_backtest")
    out.mkdir(parents=True, exist_ok=True)

    pd.DataFrame({"equity": equity_curve}, index=df.index).to_csv(out / "equity_curve.csv")

    print(f"Saved to {out}")
