#!/usr/bin/env python
"""IteraDynamics — Backtest CLI.

Runs a single-strategy backtest on OHLCV CSV data and outputs artifacts.

Usage examples:
    python scripts/run_backtest.py --data data/btc_1h.csv --strategy trend_following
    python scripts/run_backtest.py --data data/btc_1h.csv --strategy vol_breakout --start 2022-01-01 --end 2023-12-31
    python scripts/run_backtest.py --data data/btc_1h.csv --strategy mean_reversion --capital 50000

PowerShell:
    python scripts/run_backtest.py --data data\\btc_1h.csv --strategy trend_following
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# ── Ensure project root on path ───────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("run_backtest")

from research.harness.data_loader import load_ohlcv, validate_ohlcv
from research.harness.backtest_engine import run_backtest
from research.harness.execution_model import ExecutionConfig
from research.harness.metrics import compute_metrics
from research.harness.artifacts import save_artifacts
from research.strategies import REGISTRY as STRATEGY_REGISTRY


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="IteraDynamics single-strategy backtest",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--data", required=True, help="Path to OHLCV CSV")
    p.add_argument(
        "--strategy",
        default="trend_following",
        choices=list(STRATEGY_REGISTRY.keys()),
        help="Strategy to backtest",
    )
    p.add_argument("--asset", default="BTC", help="Asset label")
    p.add_argument("--start", default=None, help="Start date (YYYY-MM-DD)")
    p.add_argument("--end", default=None, help="End date (YYYY-MM-DD)")
    p.add_argument("--capital", type=float, default=100_000.0, help="Initial capital (USD)")

    # ── Execution cost overrides (all optional — defaults from .env or ExecutionConfig) ──
    p.add_argument("--fee", type=float, default=None,
                   help="Taker fee rate (e.g. 0.0006 = 6 bps)")
    p.add_argument("--maker-fees", action="store_true",
                   help="Use maker fee rate instead of taker")
    p.add_argument("--maker-fee", type=float, default=None,
                   help="Maker fee rate (e.g. 0.0002 = 2 bps)")
    p.add_argument("--base-slippage", type=float, default=None,
                   help="Base slippage floor in bps (default 3)")
    p.add_argument("--slippage-size-factor", type=float, default=None,
                   help="Slippage bps per 100%% NAV turnover (default 10)")
    p.add_argument("--slippage-vol-factor", type=float, default=None,
                   help="Slippage bps per 100%% ATR (default 50)")
    p.add_argument("--cooldown", type=int, default=None,
                   help="Minimum bars between trades (default 0)")
    p.add_argument("--rebalance-threshold", type=float, default=None,
                   help="Min exposure delta to trigger a trade (default 0.02 = 2%%)")

    p.add_argument(
        "--out-dir", default=None, help="Artifact output directory (default: artifacts/<strategy>)"
    )
    p.add_argument("--no-chart", action="store_true", help="Skip chart PNG generation")
    p.add_argument(
        "--calibrate",
        action="store_true",
        help="Apply ML confidence calibration if a trained model exists in artifacts/ml_models/",
    )
    p.add_argument(
        "--calibrators-dir",
        default=None,
        help="Path to calibrator JSON files (default: artifacts/ml_models/)",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    # ── Load data ─────────────────────────────────────────────────────
    log.info("Loading data: %s", args.data)
    df = load_ohlcv(args.data, start=args.start, end=args.end, asset=args.asset)
    warnings = validate_ohlcv(df)
    for w in warnings:
        log.warning("Data warning: %s", w)

    log.info(
        "Loaded %d bars  %s → %s  [%s]",
        len(df), df.index[0], df.index[-1], args.asset,
    )

    # ── Build execution config ────────────────────────────────────────
    exec_config = ExecutionConfig.from_env()
    if args.fee is not None:
        exec_config.taker_fee_rate = args.fee
    if args.maker_fees:
        exec_config.use_maker_fees = True
    if args.maker_fee is not None:
        exec_config.maker_fee_rate = args.maker_fee
    if args.base_slippage is not None:
        exec_config.base_slippage_bps = args.base_slippage
    if args.slippage_size_factor is not None:
        exec_config.slippage_size_factor = args.slippage_size_factor
    if args.slippage_vol_factor is not None:
        exec_config.slippage_vol_factor = args.slippage_vol_factor
    if args.cooldown is not None:
        exec_config.cooldown_bars = args.cooldown

    log.info(
        "Execution model: taker_fee=%.4f  base_slip=%.1fbps  "
        "size_factor=%.1f  vol_factor=%.1f  cooldown=%d",
        exec_config.taker_fee_rate, exec_config.base_slippage_bps,
        exec_config.slippage_size_factor, exec_config.slippage_vol_factor,
        exec_config.cooldown_bars,
    )

    # ── Optionally load ML calibrators ───────────────────────────────
    calibrators = None
    if args.calibrate:
        try:
            from research.ml.calibration.model_store import load_calibrator
            sid = args.strategy
            cal = load_calibrator(sid, models_dir=args.calibrators_dir)
            if cal is not None and cal.is_fitted:
                calibrators = {sid: cal}
                log.info(
                    "Loaded calibrator for %s (method=%s  n_samples=%d)",
                    sid, cal.calibration_method, cal.n_samples,
                )
            else:
                log.warning(
                    "--calibrate specified but no fitted model found for '%s' in %s  "
                    "— running without calibration.",
                    sid,
                    args.calibrators_dir or "artifacts/ml_models/",
                )
        except ImportError:
            log.warning("ML calibration package not available — skipping.")

    # ── Run backtest ──────────────────────────────────────────────────
    strategy_module = STRATEGY_REGISTRY[args.strategy]
    log.info("Running backtest: strategy=%s  capital=$%.2f", args.strategy, args.capital)

    rebalance_threshold = (
        args.rebalance_threshold
        if args.rebalance_threshold is not None
        else float(os.getenv("REBALANCE_THRESHOLD", "0.02"))
    )

    result = run_backtest(
        df=df,
        strategy_module=strategy_module,
        initial_capital=args.capital,
        exec_config=exec_config,
        rebalance_threshold=rebalance_threshold,
        asset=args.asset,
        calibrators=calibrators,
    )

    # ── Compute metrics ───────────────────────────────────────────────
    metrics = compute_metrics(result.equity_curve, result.trades, result.params)

    # ── Print summary ─────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"  BACKTEST COMPLETE — {args.strategy} / {args.asset}")
    print("=" * 60)
    print(f"  Period:       {metrics.start[:10]} → {metrics.end[:10]}")
    print(f"  Bars:         {metrics.n_bars:,}")
    print(f"  Initial:      ${metrics.initial_equity:>12,.2f}")
    print(f"  Final:        ${metrics.final_equity:>12,.2f}")
    print(f"  Total Return: {metrics.total_return_pct:>+.2f}%")
    print(f"  CAGR:         {metrics.cagr_pct:>+.2f}%")
    print(f"  Max Drawdown: {metrics.max_drawdown_pct:.2f}%")
    print(f"  Sharpe:       {metrics.sharpe:.3f}")
    print(f"  Calmar:       {metrics.calmar:.3f}")
    print(f"  Ann. Vol:     {metrics.volatility_ann_pct:.2f}%")
    print(f"  Trades:       {metrics.n_trades}")
    print(f"  Win Rate:     {metrics.win_rate_pct:.1f}%")
    print(f"  Total Fees:   ${metrics.total_fees_paid:>12,.2f}")
    print(f"  Slippage:     ${metrics.total_slippage_cost:>12,.2f}")
    print(f"  Avg Cost:     {metrics.avg_cost_per_trade_bps:.1f} bps/trade")
    print(f"  Turnover:     {metrics.turnover_x:.2f}x  (initial capital)")
    print(f"  Turnover NAV: {metrics.turnover_x_nav_adj:.2f}x  (mean NAV adjusted)")
    print(f"  Avg BUY:      ${metrics.avg_entry_notional_usd:>10,.0f}  ({metrics.avg_entry_notional_pct_nav*100:.1f}% NAV)")
    print(f"  Avg SELL:     ${metrics.avg_exit_notional_usd:>10,.0f}  ({metrics.avg_exit_notional_pct_nav*100:.1f}% NAV)")
    print(f"  Exit/Entry:   {metrics.avg_exit_entry_notional_ratio:.3f}x  (notional ratio)")
    print("=" * 60)

    # ── Save artifacts ────────────────────────────────────────────────
    run_id = f"{args.strategy}_{args.asset}_{str(df.index[0])[:10]}_{str(df.index[-1])[:10]}"
    out_dir = args.out_dir or None
    saved_to = save_artifacts(
        result=result,
        metrics=metrics,
        run_id=run_id,
        out_dir=out_dir,
        save_chart=not args.no_chart,
    )
    log.info("Artifacts saved to: %s", saved_to)
    print(f"\n  Artifacts: {saved_to}")
    print(f"    equity_curve.csv  trades.csv  summary.json  summary.md  chart.png\n")


if __name__ == "__main__":
    main()
