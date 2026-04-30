#!/usr/bin/env python
"""
Itera Dynamics — SPY Daily Equity Trend Backtest Runner

Research-only runner for equity_spy_trend_v1.

Purpose:
    Validate that the Itera StrategyIntent architecture can run cleanly on
    daily equity ETF data, then compare the strategy against SPY buy-and-hold.

Classification:
    Research-only. This does not affect crypto Fund v1 / Fund v2 runtime.

Outputs:
    artifacts/spy_trend_backtest/
        - equity_curve.csv
        - trades.csv
        - robustness_windows.csv
        - summary.json
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

from research.harness.data_loader import load_ohlcv
from research.regimes.contracts import RegimeLabel
from research.strategies.contracts import Action, StrategyContext
from research.strategies.equity_spy_trend_v1 import STRATEGY_ID, generate_intent

TRADING_DAYS_PER_YEAR = 252

ROBUSTNESS_WINDOWS = [
    ("GFC_2008", "2007-10-01", "2009-03-31"),
    ("COVID_2020", "2020-02-01", "2020-06-30"),
    ("BEAR_2022", "2022-01-01", "2022-12-31"),
    ("POST_2022_RECOVERY", "2023-01-01", "2024-12-31"),
]


@dataclass(frozen=True)
class Metrics:
    total_return_pct: float
    cagr_pct: float
    max_drawdown_pct: float
    sharpe: float
    calmar: float
    ann_vol_pct: float


def compute_metrics(equity: pd.Series) -> Metrics:
    equity = equity.dropna().astype(float)
    returns = equity.pct_change().dropna()

    if len(equity) < 2:
        return Metrics(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    total_return = equity.iloc[-1] / equity.iloc[0] - 1.0
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1e-9)
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1.0 / years) - 1.0

    running_max = equity.cummax()
    drawdown = equity / running_max - 1.0
    max_dd = float(drawdown.min())

    ann_vol = float(returns.std(ddof=0) * math.sqrt(TRADING_DAYS_PER_YEAR)) if len(returns) else 0.0
    sharpe = float((returns.mean() / returns.std(ddof=0)) * math.sqrt(TRADING_DAYS_PER_YEAR)) if len(returns) and returns.std(ddof=0) > 0 else 0.0
    calmar = float(cagr / abs(max_dd)) if max_dd < 0 else 0.0

    return Metrics(
        total_return_pct=total_return * 100.0,
        cagr_pct=cagr * 100.0,
        max_drawdown_pct=max_dd * 100.0,
        sharpe=sharpe,
        calmar=calmar,
        ann_vol_pct=ann_vol * 100.0,
    )


def _window_metrics(equity: pd.Series, start: str, end: str) -> Metrics | None:
    window = equity[(equity.index >= pd.Timestamp(start)) & (equity.index <= pd.Timestamp(end))]
    if len(window) < 2:
        return None
    rebased = window / window.iloc[0] * 100.0
    return compute_metrics(rebased)


def run_backtest(df: pd.DataFrame, capital: float = 100000.0):
    cash = capital
    qty = 0.0
    exposure = 0.0
    trades: list[dict] = []
    equity_curve: list[float] = []
    exposure_curve: list[float] = []

    for i in range(len(df)):
        slice_df = df.iloc[: i + 1]
        ts = slice_df.index[-1]
        price = float(slice_df["close"].iloc[-1])
        nav = cash + qty * price

        ctx = StrategyContext(
            regime=RegimeLabel.UNKNOWN,
            current_exposure_frac=exposure,
            asset="SPY",
            bar_index=i,
        )

        intent = generate_intent(slice_df, ctx, closed_only=True)

        if intent.action == Action.ENTER_LONG and exposure == 0.0:
            target_notional = nav * intent.desired_exposure_frac
            qty = target_notional / price
            cash = nav - target_notional
            exposure = intent.desired_exposure_frac
            trades.append({
                "timestamp": ts,
                "side": "BUY",
                "price": price,
                "qty": qty,
                "notional": target_notional,
                "nav": nav,
                "exposure": exposure,
                "reason": intent.reason,
            })

        elif intent.action in (Action.EXIT_LONG, Action.FLAT) and exposure > 0.0:
            notional = qty * price
            cash = cash + notional
            trades.append({
                "timestamp": ts,
                "side": "SELL",
                "price": price,
                "qty": qty,
                "notional": notional,
                "nav": cash,
                "exposure": 0.0,
                "reason": intent.reason,
            })
            qty = 0.0
            exposure = 0.0

        nav = cash + qty * price
        equity_curve.append(nav)
        exposure_curve.append(exposure)

    equity = pd.Series(equity_curve, index=df.index, name="strategy_equity")
    exposure_s = pd.Series(exposure_curve, index=df.index, name="strategy_exposure")
    trades_df = pd.DataFrame(trades)
    return equity, exposure_s, trades_df


def make_buy_hold(df: pd.DataFrame, capital: float) -> pd.Series:
    close = df["close"].astype(float)
    bh = capital * (close / close.iloc[0])
    bh.name = "buy_hold_equity"
    return bh


def print_metrics(label: str, m: Metrics) -> None:
    print(
        f"  {label:<18}"
        f" {m.total_return_pct:>9.2f}%"
        f" {m.cagr_pct:>9.2f}%"
        f" {m.max_drawdown_pct:>9.2f}%"
        f" {m.sharpe:>8.3f}"
        f" {m.calmar:>8.3f}"
        f" {m.ann_vol_pct:>9.2f}%"
    )


def build_robustness_rows(strategy_equity: pd.Series, buy_hold_equity: pd.Series) -> list[dict]:
    rows: list[dict] = []
    for label, start, end in ROBUSTNESS_WINDOWS:
        strat_m = _window_metrics(strategy_equity, start, end)
        bh_m = _window_metrics(buy_hold_equity, start, end)
        if strat_m is None or bh_m is None:
            continue
        rows.append({
            "window": label,
            "start": start,
            "end": end,
            "strategy_total_return_pct": strat_m.total_return_pct,
            "strategy_max_drawdown_pct": strat_m.max_drawdown_pct,
            "strategy_sharpe": strat_m.sharpe,
            "strategy_calmar": strat_m.calmar,
            "buy_hold_total_return_pct": bh_m.total_return_pct,
            "buy_hold_max_drawdown_pct": bh_m.max_drawdown_pct,
            "buy_hold_sharpe": bh_m.sharpe,
            "buy_hold_calmar": bh_m.calmar,
            "delta_return_pct": strat_m.total_return_pct - bh_m.total_return_pct,
            "delta_max_drawdown_pct": strat_m.max_drawdown_pct - bh_m.max_drawdown_pct,
        })
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run SPY daily equity trend backtest")
    parser.add_argument("--data", required=True, help="Path to SPY daily CSV")
    parser.add_argument("--start", default=None)
    parser.add_argument("--end", default=None)
    parser.add_argument("--capital", type=float, default=100000)
    parser.add_argument("--out-dir", default="artifacts/spy_trend_backtest")

    args = parser.parse_args()

    df = load_ohlcv(args.data, start=args.start, end=args.end, asset="SPY")

    strategy_equity, exposure, trades = run_backtest(df, args.capital)
    buy_hold_equity = make_buy_hold(df, args.capital)

    strategy_m = compute_metrics(strategy_equity)
    buy_hold_m = compute_metrics(buy_hold_equity)
    exposure_pct = float((exposure > 0).mean() * 100.0)
    robustness_rows = build_robustness_rows(strategy_equity, buy_hold_equity)

    print(f"Loaded {len(df)} bars: {df.index[0]} → {df.index[-1]}")
    print("\n" + "=" * 96)
    print("  SPY DAILY EQUITY TREND v1 — Research Backtest")
    print(f"  Strategy: {STRATEGY_ID}")
    print(f"  Capital:  ${args.capital:,.0f}")
    print(f"  Period:   {str(df.index[0])[:10]} → {str(df.index[-1])[:10]}")
    print("=" * 96)

    print("\n  PERFORMANCE")
    print("  " + "-" * 86)
    print(f"  {'Series':<18} {'TotRet':>10} {'CAGR':>10} {'MaxDD':>10} {'Sharpe':>8} {'Calmar':>8} {'AnnVol':>10}")
    print("  " + "-" * 86)
    print_metrics("Strategy", strategy_m)
    print_metrics("SPY Buy&Hold", buy_hold_m)

    print("\n  ACTIVITY")
    print("  " + "-" * 40)
    print(f"  Trades:        {len(trades)}")
    print(f"  Exposure time: {exposure_pct:.1f}%")

    if robustness_rows:
        print("\n  ROBUSTNESS WINDOWS")
        print("  " + "-" * 92)
        print(f"  {'Window':<20} {'StratRet':>9} {'BHRet':>9} {'ΔRet':>9} {'StratDD':>9} {'BHDD':>9} {'ΔDD':>9}")
        print("  " + "-" * 92)
        for row in robustness_rows:
            print(
                f"  {row['window']:<20}"
                f" {row['strategy_total_return_pct']:>8.2f}%"
                f" {row['buy_hold_total_return_pct']:>8.2f}%"
                f" {row['delta_return_pct']:>+8.2f}%"
                f" {row['strategy_max_drawdown_pct']:>8.2f}%"
                f" {row['buy_hold_max_drawdown_pct']:>8.2f}%"
                f" {row['delta_max_drawdown_pct']:>+8.2f}%"
            )

    if not trades.empty:
        print("\n  TRADE SUMMARY")
        print("  " + "-" * 72)
        for _, row in trades.tail(8).iterrows():
            print(
                f"  {str(row['timestamp'])[:10]}  {row['side']:<4} "
                f"{row['qty']:>10.4f} @ ${row['price']:>9.2f}  "
                f"notional=${row['notional']:>10,.0f}"
            )

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    pd.DataFrame({
        "strategy_equity": strategy_equity,
        "buy_hold_equity": buy_hold_equity,
        "strategy_exposure": exposure,
    }).to_csv(out / "equity_curve.csv")

    trades.to_csv(out / "trades.csv", index=False)
    pd.DataFrame(robustness_rows).to_csv(out / "robustness_windows.csv", index=False)

    summary = {
        "strategy_id": STRATEGY_ID,
        "capital": args.capital,
        "start": str(df.index[0]),
        "end": str(df.index[-1]),
        "bars": len(df),
        "trades": len(trades),
        "exposure_time_pct": exposure_pct,
        "strategy": asdict(strategy_m),
        "buy_hold": asdict(buy_hold_m),
        "robustness_windows": robustness_rows,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str))

    print("\n" + "=" * 96)
    print(f"  Artifacts saved to: {out}")
    print("    equity_curve.csv  trades.csv  robustness_windows.csv  summary.json")
    print("=" * 96)
