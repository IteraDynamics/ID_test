#!/usr/bin/env python
"""Itera Dynamics — Equity SPY Trend v2b Backtest Runner.

Runs Equity Sleeve v2b and prints full fund-style diagnostics.

Outputs:
    artifacts/spy_trend_v2/
        equity_curve.csv
        trades.csv
        summary.json
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
REBALANCE_THRESHOLD = 0.10


@dataclass(frozen=True)
class Metrics:
    total_return_pct: float
    cagr_pct: float
    max_drawdown_pct: float
    sharpe: float
    calmar: float
    ann_vol_pct: float


def load_data(path: str, start: str | None = None, end: str | None = None) -> pd.DataFrame:
    df = pd.read_csv(path)
    ts = df.columns[0]
    df[ts] = pd.to_datetime(df[ts])
    df = df.set_index(ts).sort_index()
    df.index = df.index.tz_localize(None) if getattr(df.index, "tz", None) is not None else df.index
    df = df.rename(columns={c: c.lower() for c in df.columns})

    if start:
        df = df[df.index >= pd.Timestamp(start)]
    if end:
        df = df[df.index <= pd.Timestamp(end)]
    return df


def compute_metrics(equity: pd.Series) -> Metrics:
    equity = equity.dropna().astype(float)
    returns = equity.pct_change().dropna()
    if len(equity) < 2:
        return Metrics(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    total_return = equity.iloc[-1] / equity.iloc[0] - 1.0
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1e-9)
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1.0 / years) - 1.0
    dd = equity / equity.cummax() - 1.0
    max_dd = float(dd.min())

    if len(returns) and returns.std(ddof=0) > 0:
        ann_vol = float(returns.std(ddof=0) * math.sqrt(TRADING_DAYS_PER_YEAR))
        sharpe = float((returns.mean() / returns.std(ddof=0)) * math.sqrt(TRADING_DAYS_PER_YEAR))
    else:
        ann_vol = 0.0
        sharpe = 0.0

    calmar = float(cagr / abs(max_dd)) if max_dd < 0 else 0.0
    return Metrics(total_return * 100, cagr * 100, max_dd * 100, sharpe, calmar, ann_vol * 100)


def make_buy_hold(df: pd.DataFrame, capital: float) -> pd.Series:
    close = df["close"].astype(float)
    return pd.Series(capital * (close / close.iloc[0]), index=df.index, name="buy_hold_equity")


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


def main():
    p = argparse.ArgumentParser(description="Run Equity SPY Trend v2b backtest")
    p.add_argument("--data", required=True)
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--capital", type=float, default=100000)
    p.add_argument("--out-dir", default="artifacts/spy_trend_v2")
    args = p.parse_args()

    df = load_data(args.data, start=args.start, end=args.end)
    if df.empty:
        raise SystemExit("No data loaded. Check --data/--start/--end.")

    equity, exposure, trades = run_backtest(df, args.capital)
    buy_hold = make_buy_hold(df, args.capital)

    strategy_m = compute_metrics(equity)
    buy_hold_m = compute_metrics(buy_hold)
    exposure_pct = float((exposure > 0).mean() * 100.0)
    avg_exposure = float(exposure.mean() * 100.0)

    print(f"Loaded {len(df)} bars: {df.index[0]} → {df.index[-1]}")
    print("\n" + "=" * 96)
    print("  SPY DAILY EQUITY TREND v2b — State-Disciplined Partial Exposure Backtest")
    print(f"  Strategy: {STRATEGY_ID}")
    print(f"  Capital:  ${args.capital:,.0f}")
    print(f"  Period:   {str(df.index[0])[:10]} → {str(df.index[-1])[:10]}")
    print(f"  Rebalance threshold: {REBALANCE_THRESHOLD:.0%} of NAV")
    print("=" * 96)

    print("\n  PERFORMANCE")
    print("  " + "-" * 86)
    print(f"  {'Series':<18} {'TotRet':>10} {'CAGR':>10} {'MaxDD':>10} {'Sharpe':>8} {'Calmar':>8} {'AnnVol':>10}")
    print("  " + "-" * 86)
    print_metrics("Strategy v2b", strategy_m)
    print_metrics("SPY Buy&Hold", buy_hold_m)

    print("\n  ACTIVITY")
    print("  " + "-" * 40)
    print(f"  Trades/Rebalances: {len(trades)}")
    print(f"  Exposure time:     {exposure_pct:.1f}%")
    print(f"  Average exposure:  {avg_exposure:.1f}%")
    print("  Exposure distribution:")
    for value, count in exposure.round(2).value_counts().sort_index().items():
        print(f"    {value:.0%}: {count} days")

    if not trades.empty:
        print("\n  RECENT REBALANCES")
        print("  " + "-" * 80)
        for _, row in trades.tail(10).iterrows():
            print(
                f"  {str(row['timestamp'])[:10]} {row['side']:<4} "
                f"delta=${row['delta_notional']:>10,.0f} "
                f"target={row['target_exposure']:>5.0%} @ ${row['price']:>9.2f}"
            )

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({
        "strategy_equity": equity,
        "buy_hold_equity": buy_hold,
        "strategy_exposure": exposure,
    }).to_csv(out / "equity_curve.csv")
    trades.to_csv(out / "trades.csv", index=False)

    summary = {
        "strategy_id": STRATEGY_ID,
        "capital": args.capital,
        "start": str(df.index[0]),
        "end": str(df.index[-1]),
        "bars": len(df),
        "rebalance_threshold_nav_pct": REBALANCE_THRESHOLD * 100.0,
        "trades_or_rebalances": len(trades),
        "exposure_time_pct": exposure_pct,
        "average_exposure_pct": avg_exposure,
        "strategy": asdict(strategy_m),
        "buy_hold": asdict(buy_hold_m),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str))

    print("\n" + "=" * 96)
    print(f"  Artifacts saved to: {out}")
    print("    equity_curve.csv  trades.csv  summary.json")
    print("=" * 96)


if __name__ == "__main__":
    main()
