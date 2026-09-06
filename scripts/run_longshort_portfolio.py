#!/usr/bin/env python
"""IteraDynamics — Long/Short Portfolio Backtest CLI.

Runs a long strategy and a short strategy on independent capital allocations,
then combines their equity curves for portfolio-level reporting.

Design rationale:
    The blend engine's normalised-weight model dilutes long exposure by the
    short sleeve's weight even when the short is flat (i.e., always in bull
    markets).  The correct model for a long/short portfolio is two independent
    capital pools that run concurrently — the combined equity is their sum.

    If long_weight=0.7 and short_weight=0.3:
        - Long sleeve runs on $70k, earns its own P&L
        - Short sleeve runs on $30k, earns its own P&L
        - Portfolio equity = long equity + short equity
        - In bull markets the short is flat and $30k earns nothing;
          the long earns on $70k — no dilution of the active sleeve.

Usage examples:
    # 2022 bear market — default 70/30 split
    python scripts/run_longshort_portfolio.py \\
        --data data/btcusd_3600s_2019-01-01_to_2025-12-30.csv \\
        --start 2022-01-01 --end 2022-12-31

    # Full period with calibration on long sleeve
    python scripts/run_longshort_portfolio.py \\
        --data data/btcusd_3600s_2019-01-01_to_2025-12-30.csv \\
        --calibrate

    # Custom weights
    python scripts/run_longshort_portfolio.py \\
        --data data/btcusd_3600s_2019-01-01_to_2025-12-30.csv \\
        --long-weight 0.6 --short-weight 0.4 --start 2022-01-01 --end 2022-12-31

PowerShell:
    python scripts\\run_longshort_portfolio.py --data data\\btcusd_3600s_2019-01-01_to_2025-12-30.csv --calibrate
"""

from __future__ import annotations

# Preserve direct-file execution; package imports use normal discovery.
if __package__ in (None, ""):
    try:
        from _checkout_bootstrap import bootstrap as _bootstrap_checkout
    except ModuleNotFoundError as _bootstrap_error:
        if _bootstrap_error.name != "_checkout_bootstrap":
            raise
        from scripts._checkout_bootstrap import bootstrap as _bootstrap_checkout
    _bootstrap_checkout(__file__)


import argparse
import logging
import sys
from pathlib import Path


from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("run_longshort")

from research.harness.data_loader import load_ohlcv, validate_ohlcv
from research.harness.backtest_engine import run_backtest, BacktestResult
from research.harness.execution_model import ExecutionConfig
from research.harness.metrics import compute_metrics
from research.harness.artifacts import save_artifacts
from research.strategies import REGISTRY as STRATEGY_REGISTRY


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Long/Short portfolio backtest — independent capital allocation",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--data", required=True, help="Path to OHLCV CSV")
    p.add_argument(
        "--long-strategy",
        default="trend_following_v8_ecap60_add80",
        choices=list(STRATEGY_REGISTRY.keys()),
        help="Long sleeve strategy",
    )
    p.add_argument(
        "--short-strategy",
        default="trend_following_short_v2",
        choices=list(STRATEGY_REGISTRY.keys()),
        help="Short sleeve strategy",
    )
    p.add_argument(
        "--long-weight",
        type=float, default=0.7,
        help="Fraction of capital allocated to the long sleeve [0, 1]",
    )
    p.add_argument(
        "--short-weight",
        type=float, default=0.3,
        help="Fraction of capital allocated to the short sleeve [0, 1]",
    )
    p.add_argument("--capital", type=float, default=100_000.0, help="Total portfolio capital (USD)")
    p.add_argument("--asset", default="BTC")
    p.add_argument("--start", default=None, help="Start date (YYYY-MM-DD)")
    p.add_argument("--end",   default=None, help="End date (YYYY-MM-DD)")
    # Execution cost overrides
    p.add_argument("--fee", type=float, default=None)
    p.add_argument("--base-slippage", type=float, default=None)
    p.add_argument("--slippage-vol-factor", type=float, default=None)
    p.add_argument("--cooldown", type=int, default=None)
    p.add_argument("--rebalance-threshold", type=float, default=None)
    # ML calibration (applied to long sleeve; short uses raw signals)
    p.add_argument(
        "--calibrate",
        action="store_true",
        help="Load ML calibrators for the long sleeve if available",
    )
    p.add_argument("--calibrators-dir", default=None)
    p.add_argument("--out-dir", default=None)
    p.add_argument("--no-chart", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    # Normalise weights
    total_w = args.long_weight + args.short_weight
    if total_w <= 0:
        log.error("Weights must be positive.")
        sys.exit(1)
    lw = args.long_weight / total_w
    sw = args.short_weight / total_w

    # ── Load data ──────────────────────────────────────────────────────
    log.info("Loading data: %s", args.data)
    df = load_ohlcv(args.data, start=args.start, end=args.end, asset=args.asset)
    for w in validate_ohlcv(df):
        log.warning("Data warning: %s", w)
    log.info("Loaded %d bars  %s → %s  [%s]", len(df), df.index[0], df.index[-1], args.asset)

    # ── Resolve strategies ─────────────────────────────────────────────
    long_mod  = STRATEGY_REGISTRY[args.long_strategy]
    short_mod = STRATEGY_REGISTRY[args.short_strategy]

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
    import os
    rebalance_threshold = (
        args.rebalance_threshold
        if args.rebalance_threshold is not None
        else float(os.getenv("REBALANCE_THRESHOLD", "0.02"))
    )

    log.info(
        "Execution: taker_fee=%.4f  base_slip=%.1fbps  cooldown=%d",
        exec_config.taker_fee_rate, exec_config.base_slippage_bps, exec_config.cooldown_bars,
    )

    # ── Optionally load calibrators for long sleeve ────────────────────
    calibrators = None
    if args.calibrate:
        try:
            from research.ml.calibration.model_store import load_calibrator
            calibrators = {}
            for name, mod in [(args.long_strategy, long_mod), (args.short_strategy, short_mod)]:
                sid = getattr(mod, "STRATEGY_ID", name)
                cal = load_calibrator(sid, models_dir=args.calibrators_dir)
                if cal is not None and cal.is_fitted:
                    calibrators[sid] = cal
                    log.info("Calibrator loaded: %s", sid)
        except ImportError:
            log.warning("ML calibration not available — skipping.")

    long_capital  = args.capital * lw
    short_capital = args.capital * sw

    log.info(
        "Sleeves: long=%s (%.0f%% / $%.0f)  short=%s (%.0f%% / $%.0f)",
        args.long_strategy,  lw * 100, long_capital,
        args.short_strategy, sw * 100, short_capital,
    )

    # ── Run long sleeve ────────────────────────────────────────────────
    log.info("Running long sleeve...")
    long_result = run_backtest(
        df=df, strategy_module=long_mod,
        initial_capital=long_capital, exec_config=exec_config,
        rebalance_threshold=rebalance_threshold, asset=args.asset,
        calibrators=calibrators,
    )

    # ── Run short sleeve ───────────────────────────────────────────────
    log.info("Running short sleeve...")
    short_result = run_backtest(
        df=df, strategy_module=short_mod,
        initial_capital=short_capital, exec_config=exec_config,
        rebalance_threshold=rebalance_threshold, asset=args.asset,
    )

    # ── Long-only baseline (full capital, same config) ─────────────────
    log.info("Running long-only baseline...")
    baseline_result = run_backtest(
        df=df, strategy_module=long_mod,
        initial_capital=args.capital, exec_config=exec_config,
        rebalance_threshold=rebalance_threshold, asset=args.asset,
        calibrators=calibrators,
    )

    # ── Combine equity curves ──────────────────────────────────────────
    combined_equity = long_result.equity_curve + short_result.equity_curve
    all_trades      = long_result.trades + short_result.trades

    base_params = {
        "initial_capital": args.capital,
        "taker_fee_rate":   exec_config.taker_fee_rate,
        "base_slippage_bps": exec_config.base_slippage_bps,
        "asset": args.asset,
        "n_bars": len(df),
        "start": str(df.index[0]),
        "end":   str(df.index[-1]),
        "strategy_id": "longshort_portfolio",
    }

    combined_m  = compute_metrics(combined_equity,              all_trades,              base_params)
    baseline_m  = compute_metrics(baseline_result.equity_curve, baseline_result.trades,  base_params)
    long_m      = compute_metrics(long_result.equity_curve,     long_result.trades,      base_params)
    short_m     = compute_metrics(short_result.equity_curve,    short_result.trades,     base_params)

    # ── Print comparison table ─────────────────────────────────────────
    cal_tag = " (cal)" if calibrators else ""
    print("\n" + "=" * 70)
    print(f"  LONG/SHORT PORTFOLIO — {args.asset}{cal_tag}")
    print(f"  Long  ({lw:.0%}): {args.long_strategy}")
    print(f"  Short ({sw:.0%}): {args.short_strategy}")
    print("=" * 70)
    print(f"  {'Metric':<22} {'Long-Only':>12} {'L/S Portfolio':>14} {'Delta':>10}")
    print(f"  {'-'*22} {'-'*12} {'-'*14} {'-'*10}")

    def row(label: str, lo: float, ls: float, fmt: str = "{:>12.2f}", dfmt: str = "{:>+10.2f}") -> None:
        print(f"  {label:<22} {fmt.format(lo)} {fmt.format(ls):>14} {dfmt.format(ls - lo)}")

    row("Total Return %",   baseline_m.total_return_pct,   combined_m.total_return_pct)
    row("CAGR %",           baseline_m.cagr_pct,           combined_m.cagr_pct)
    row("Max Drawdown %",   baseline_m.max_drawdown_pct,   combined_m.max_drawdown_pct)
    row("Sharpe",           baseline_m.sharpe,             combined_m.sharpe,      "{:>12.3f}", "{:>+10.3f}")
    row("Calmar",           baseline_m.calmar,             combined_m.calmar,      "{:>12.3f}", "{:>+10.3f}")
    row("Ann. Vol %",       baseline_m.volatility_ann_pct, combined_m.volatility_ann_pct)
    row("Trades",           float(baseline_m.n_trades),    float(combined_m.n_trades), "{:>12.0f}", "{:>+10.0f}")
    row("Total Fees $",     baseline_m.total_fees_paid,    combined_m.total_fees_paid,    "{:>12,.0f}", "{:>+10,.0f}")
    row("Slippage $",       baseline_m.total_slippage_cost,combined_m.total_slippage_cost,"{:>12,.0f}", "{:>+10,.0f}")

    print("=" * 70)
    print(f"  Period : {combined_m.start[:10]} → {combined_m.end[:10]}   Bars: {combined_m.n_bars:,}")
    print(f"  Capital: ${args.capital:,.0f}  (Long ${long_capital:,.0f} / Short ${short_capital:,.0f})")
    print()
    print(f"  {'Sleeve':<34} {'Return%':>8} {'MaxDD%':>8} {'Sharpe':>7} {'Trades':>7}")
    print(f"  {'-'*34} {'-'*8} {'-'*8} {'-'*7} {'-'*7}")
    print(f"  {'Long  '+args.long_strategy:<34} {long_m.total_return_pct:>+8.2f} "
          f"{long_m.max_drawdown_pct:>8.2f} {long_m.sharpe:>7.3f} {long_m.n_trades:>7}")
    print(f"  {'Short '+args.short_strategy:<34} {short_m.total_return_pct:>+8.2f} "
          f"{short_m.max_drawdown_pct:>8.2f} {short_m.sharpe:>7.3f} {short_m.n_trades:>7}")
    print("=" * 70 + "\n")

    # ── Save artifacts ─────────────────────────────────────────────────
    cal_str = "_cal" if calibrators else ""
    run_id = (
        f"longshort{cal_str}_{lw:.0%}_{sw:.0%}_{args.asset}"
        f"_{combined_m.start[:10]}_{combined_m.end[:10]}"
    )
    bt_result = BacktestResult(
        equity_curve=combined_equity,
        position_series=long_result.position_series,
        regime_series=long_result.regime_series,
        intent_series=[],
        trades=all_trades,
        params={**base_params, "long_weight": lw, "short_weight": sw},
    )
    saved_to = save_artifacts(
        result=bt_result,
        metrics=combined_m,
        run_id=run_id,
        out_dir=args.out_dir,
        save_chart=not args.no_chart,
    )
    log.info("Artifacts saved to: %s", saved_to)
    print(f"  Artifacts: {saved_to}\n")


if __name__ == "__main__":
    main()
