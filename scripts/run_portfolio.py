#!/usr/bin/env python
"""IteraDynamics — Portfolio Backtest CLI.

Runs a multi-strategy blended portfolio backtest with optional ML calibration.

Usage examples:
    # Equal-weight all 5 strategies, default execution params
    python scripts/run_portfolio.py --data data/btc_1h.csv

    # Custom strategy mix with calibration
    python scripts/run_portfolio.py --data data/btc_1h.csv \\
        --strategies trend_following_v3,volatility_breakout,mean_reversion \\
        --weights 0.5,0.3,0.2 \\
        --calibrate

    # Full params matching individual calibrated backtests
    python scripts/run_portfolio.py --data data/btc_1h.csv \\
        --strategies trend_following_v3,volatility_breakout,mean_reversion \\
        --weights 0.5,0.3,0.2 \\
        --fee 0.0008 --base-slippage 5 --slippage-vol-factor 80 \\
        --cooldown 2 --rebalance-threshold 0.05 \\
        --calibrate

PowerShell:
    python scripts\\run_portfolio.py --data data\\btc_1h.csv --calibrate
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
from research.harness.execution_model import ExecutionConfig
from research.harness.artifacts import save_artifacts
from research.harness.backtest_engine import BacktestResult
from research.portfolio.blend import run_portfolio_backtest, SleeveConfig
from research.strategies import REGISTRY as STRATEGY_REGISTRY

_DEFAULT_STRATEGIES = "trend_following_v3,volatility_breakout,mean_reversion"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="IteraDynamics multi-strategy portfolio backtest",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--data", required=True, help="Path to OHLCV CSV")
    p.add_argument("--asset", default="BTC", help="Asset label")
    p.add_argument("--start", default=None, help="Start date (YYYY-MM-DD)")
    p.add_argument("--end", default=None, help="End date (YYYY-MM-DD)")
    p.add_argument("--capital", type=float, default=100_000.0, help="Initial capital (USD)")
    p.add_argument(
        "--strategies",
        default=_DEFAULT_STRATEGIES,
        help="Comma-separated strategy names from REGISTRY",
    )
    p.add_argument(
        "--weights",
        default=None,
        help="Comma-separated sleeve weights (must match --strategies count). "
             "Defaults to equal weights. Need not sum to 1 — normalised automatically.",
    )
    p.add_argument(
        "--max-exposure",
        type=float,
        default=1.0,
        help="Hard cap on blended portfolio exposure [0, 1]",
    )
    # Execution cost params
    p.add_argument("--fee", type=float, default=None,
                   help="Taker fee rate (e.g. 0.0008 = 8 bps)")
    p.add_argument("--base-slippage", type=float, default=None,
                   help="Base slippage floor in bps (default 3)")
    p.add_argument("--slippage-vol-factor", type=float, default=None,
                   help="Slippage bps per 100%% ATR (default 50)")
    p.add_argument("--cooldown", type=int, default=None,
                   help="Minimum bars between trades (default 0)")
    p.add_argument("--rebalance-threshold", type=float, default=None,
                   help="Min exposure delta to trigger a trade (default 0.02)")
    # Calibration
    p.add_argument(
        "--calibrate",
        action="store_true",
        help="Load ML calibrators from artifacts/ml_models/ and apply to each sleeve",
    )
    p.add_argument(
        "--calibrators-dir",
        default=None,
        help="Path to calibrator JSON files (default: artifacts/ml_models/)",
    )
    p.add_argument("--out-dir", default=None, help="Artifact output directory")
    p.add_argument("--no-chart", action="store_true", help="Skip chart PNG generation")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    # ── Load data ─────────────────────────────────────────────────────
    log.info("Loading data: %s", args.data)
    df = load_ohlcv(args.data, start=args.start, end=args.end, asset=args.asset)
    for w in validate_ohlcv(df):
        log.warning("Data warning: %s", w)
    log.info("Loaded %d bars  %s → %s  [%s]", len(df), df.index[0], df.index[-1], args.asset)

    # ── Resolve strategies ─────────────────────────────────────────────
    strategy_names = [s.strip() for s in args.strategies.split(",") if s.strip()]
    modules = []
    for name in strategy_names:
        mod = STRATEGY_REGISTRY.get(name)
        if mod is None:
            log.error("Unknown strategy '%s'. Available: %s", name, list(STRATEGY_REGISTRY))
            sys.exit(1)
        modules.append((name, mod))

    # ── Resolve weights ────────────────────────────────────────────────
    if args.weights:
        raw_weights = [float(x.strip()) for x in args.weights.split(",")]
        if len(raw_weights) != len(modules):
            log.error(
                "--weights has %d values but --strategies has %d. They must match.",
                len(raw_weights), len(modules),
            )
            sys.exit(1)
    else:
        raw_weights = [1.0] * len(modules)

    # ── Build execution config ─────────────────────────────────────────
    exec_config = ExecutionConfig.from_env()
    if args.fee is not None:
        exec_config.taker_fee_rate = args.fee
    if args.base_slippage is not None:
        exec_config.base_slippage_bps = args.base_slippage
    if args.slippage_vol_factor is not None:
        exec_config.slippage_vol_factor = args.slippage_vol_factor
    if args.cooldown is not None:
        exec_config.cooldown_bars = args.cooldown

    log.info(
        "Execution model: taker_fee=%.4f  base_slip=%.1fbps  vol_factor=%.1f  cooldown=%d",
        exec_config.taker_fee_rate, exec_config.base_slippage_bps,
        exec_config.slippage_vol_factor, exec_config.cooldown_bars,
    )

    # ── Optionally load calibrators ────────────────────────────────────
    calibrators = None
    if args.calibrate:
        try:
            from research.ml.calibration.model_store import load_calibrator
            calibrators = {}
            for name, mod in modules:
                sid = getattr(mod, "STRATEGY_ID", name)
                cal = load_calibrator(sid, models_dir=args.calibrators_dir)
                if cal is not None and cal.is_fitted:
                    calibrators[sid] = cal
                    log.info(
                        "  Calibrator loaded: %s (method=%s  n=%d)",
                        sid, cal.calibration_method, cal.n_samples,
                    )
                else:
                    log.warning(
                        "  No fitted calibrator for '%s' — sleeve runs uncalibrated.", sid,
                    )
            if not calibrators:
                log.warning("--calibrate specified but no fitted models found — running uncalibrated.")
                calibrators = None
        except ImportError:
            log.warning("ML calibration package not available — skipping.")

    # ── Build sleeves ──────────────────────────────────────────────────
    total_w = sum(raw_weights)
    sleeves = [
        SleeveConfig(
            strategy_module=mod,
            weight=w,
            label=name,
        )
        for (name, mod), w in zip(modules, raw_weights)
    ]

    sleeve_summary = "  ".join(f"{name}={w/total_w:.0%}" for (name, _), w in zip(modules, raw_weights))
    log.info("Portfolio sleeves: %s", sleeve_summary)

    # ── Run portfolio backtest ─────────────────────────────────────────
    import os
    rebalance_threshold = (
        args.rebalance_threshold
        if args.rebalance_threshold is not None
        else float(os.getenv("REBALANCE_THRESHOLD", "0.02"))
    )

    port_result, metrics = run_portfolio_backtest(
        df=df,
        sleeves=sleeves,
        initial_capital=args.capital,
        exec_config=exec_config,
        max_portfolio_exposure=args.max_exposure,
        rebalance_threshold=rebalance_threshold,
        asset=args.asset,
        calibrators=calibrators,
    )

    # ── Print summary ──────────────────────────────────────────────────
    calibrated_tag = " (CALIBRATED)" if calibrators else ""
    print("\n" + "=" * 60)
    print(f"  PORTFOLIO BACKTEST — {args.asset}{calibrated_tag}")
    print("=" * 60)
    print(f"  Sleeves:      {sleeve_summary}")
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
    print("=" * 60)

    # ── Save artifacts ─────────────────────────────────────────────────
    bt_result = BacktestResult(
        equity_curve=port_result.equity_curve,
        position_series=port_result.blended_exposure,
        regime_series=port_result.regime_series,
        intent_series=[],
        trades=port_result.trades,
        params=port_result.params,
    )
    cal_tag = "_calibrated" if calibrators else ""
    run_id = f"portfolio{cal_tag}_{args.asset}_{metrics.start[:10]}_{metrics.end[:10]}"
    saved_to = save_artifacts(
        result=bt_result,
        metrics=metrics,
        run_id=run_id,
        out_dir=args.out_dir,
        save_chart=not args.no_chart,
    )
    log.info("Artifacts saved to: %s", saved_to)
    print(f"\n  Artifacts: {saved_to}\n")


if __name__ == "__main__":
    main()
