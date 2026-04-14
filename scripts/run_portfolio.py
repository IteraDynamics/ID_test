#!/usr/bin/env python
"""IteraDynamics — Portfolio Backtest CLI.

Runs a multi-strategy blended portfolio backtest.

Usage:
    python scripts/run_portfolio.py --data data/btc_1h.csv
    python scripts/run_portfolio.py --data data/btc_1h.csv --weights "0.5,0.3,0.2" --start 2022-01-01
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("run_portfolio")

from research.harness.data_loader import load_ohlcv, validate_ohlcv
from research.harness.artifacts import save_artifacts
from research.portfolio.blend import run_portfolio_backtest, SleeveConfig
from research.strategies import trend_following, volatility_breakout, mean_reversion


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="IteraDynamics multi-strategy portfolio backtest",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--data", required=True, help="Path to OHLCV CSV")
    p.add_argument("--asset", default="BTC", help="Asset label")
    p.add_argument("--start", default=None, help="Start date (YYYY-MM-DD)")
    p.add_argument("--end", default=None, help="End date (YYYY-MM-DD)")
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--fee", type=float, default=0.0006)
    p.add_argument("--slippage", type=float, default=5.0)
    p.add_argument(
        "--weights",
        default="0.5,0.3,0.2",
        help="Comma-separated sleeve weights: trend,volbreak,meanrev",
    )
    p.add_argument("--out-dir", default=None)
    p.add_argument("--no-chart", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    # ── Load data ─────────────────────────────────────────────────────
    log.info("Loading data: %s", args.data)
    df = load_ohlcv(args.data, start=args.start, end=args.end, asset=args.asset)
    warnings = validate_ohlcv(df)
    for w in warnings:
        log.warning("Data warning: %s", w)

    log.info("Loaded %d bars  %s → %s", len(df), df.index[0], df.index[-1])

    # ── Parse weights ─────────────────────────────────────────────────
    try:
        w_trend, w_vol, w_rev = [float(x.strip()) for x in args.weights.split(",")]
    except Exception:
        log.error("--weights must be 3 comma-separated floats, e.g. '0.5,0.3,0.2'")
        sys.exit(1)

    sleeves = [
        SleeveConfig(strategy_module=trend_following, weight=w_trend, label="trend_following"),
        SleeveConfig(strategy_module=volatility_breakout, weight=w_vol, label="vol_breakout"),
        SleeveConfig(strategy_module=mean_reversion, weight=w_rev, label="mean_reversion"),
    ]

    log.info(
        "Portfolio sleeves: trend=%.2f vol=%.2f rev=%.2f",
        w_trend, w_vol, w_rev,
    )

    # ── Run portfolio backtest ────────────────────────────────────────
    port_result, metrics = run_portfolio_backtest(
        df=df,
        sleeves=sleeves,
        initial_capital=args.capital,
        fee_rate=args.fee,
        slippage_bps=args.slippage,
        asset=args.asset,
    )

    # ── Fake a BacktestResult-like object for the artifact writer ─────
    # PortfolioResult is compatible for artifact writing
    from research.harness.backtest_engine import BacktestResult
    bt_result = BacktestResult(
        equity_curve=port_result.equity_curve,
        position_series=port_result.blended_exposure,
        regime_series=port_result.regime_series,
        intent_series=[],
        trades=port_result.trades,
        params=port_result.params,
    )

    # ── Print summary ─────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"  PORTFOLIO BACKTEST — {args.asset}")
    print("=" * 60)
    print(f"  Sleeves:      trend={w_trend}  vol={w_vol}  rev={w_rev}")
    print(f"  Period:       {metrics.start[:10]} → {metrics.end[:10]}")
    print(f"  Bars:         {metrics.n_bars:,}")
    print(f"  Initial:      ${metrics.initial_equity:>12,.2f}")
    print(f"  Final:        ${metrics.final_equity:>12,.2f}")
    print(f"  Total Return: {metrics.total_return_pct:>+.2f}%")
    print(f"  CAGR:         {metrics.cagr_pct:>+.2f}%")
    print(f"  Max Drawdown: {metrics.max_drawdown_pct:.2f}%")
    print(f"  Sharpe:       {metrics.sharpe:.3f}")
    print(f"  Calmar:       {metrics.calmar:.3f}")
    print(f"  Trades:       {metrics.n_trades}")
    print("=" * 60)

    # ── Save artifacts ────────────────────────────────────────────────
    run_id = f"portfolio_{args.asset}_{metrics.start[:10]}_{metrics.end[:10]}"
    saved_to = save_artifacts(
        result=bt_result,
        metrics=metrics,
        run_id=run_id,
        out_dir=args.out_dir,
        save_chart=not args.no_chart,
    )
    print(f"\n  Artifacts: {saved_to}\n")


if __name__ == "__main__":
    main()
