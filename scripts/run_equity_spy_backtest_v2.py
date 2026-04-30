#!/usr/bin/env python
"""Itera Dynamics — Equity SPY Trend v2b Backtest Runner.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from research.regimes.contracts import RegimeLabel
from research.strategies.contracts import StrategyContext
from research.strategies.equity_spy_trend_v2 import STRATEGY_ID, generate_intent

TRADING_DAYS_PER_YEAR = 252
REBALANCE_THRESHOLD = 0.10  # 10% NAV minimum change

@dataclass(frozen=True)
class Metrics:
    total_return_pct: float
    cagr_pct: float
    max_drawdown_pct: float
    sharpe: float
    calmar: float
    ann_vol_pct: float

# (rest unchanged for brevity)

# ONLY change inside run_backtest

def run_backtest(df: pd.DataFrame, capital: float):
    exposure = 0.0
    cash = capital
    shares = 0.0
    equity_curve = []
    exposure_curve = []
    trades = []

    for i in range(len(df)):
        slice_df = df.iloc[: i + 1]
        ts = slice_df.index[-1]
        price = float(slice_df["close"].iloc[-1])
        nav_before = cash + shares * price

        ctx = StrategyContext(
            regime=RegimeLabel.UNKNOWN,
            current_exposure_frac=exposure,
            asset="SPY",
            bar_index=i,
        )

        intent = generate_intent(slice_df, ctx, closed_only=True)
        target_exposure = float(intent.desired_exposure_frac)
        target_value = target_exposure * nav_before
        current_value = shares * price
        delta_value = target_value - current_value

        # NEW: threshold filter
        if abs(delta_value) > (REBALANCE_THRESHOLD * nav_before):
            delta_shares = delta_value / price
            shares += delta_shares
            cash -= delta_value
            trades.append({
                "timestamp": ts,
                "side": "BUY" if delta_value > 0 else "SELL",
                "price": price,
                "delta_shares": delta_shares,
                "delta_notional": delta_value,
                "target_exposure": target_exposure,
                "nav_before": nav_before,
                "reason": intent.reason,
            })

        exposure = target_exposure
        nav = cash + shares * price
        equity_curve.append(nav)
        exposure_curve.append(exposure)

    equity = pd.Series(equity_curve, index=df.index, name="strategy_equity")
    exposure_s = pd.Series(exposure_curve, index=df.index, name="strategy_exposure")
    trades_df = pd.DataFrame(trades)
    return equity, exposure_s, trades_df

# rest of file unchanged
