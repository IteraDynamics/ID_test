#!/usr/bin/env python
"""IteraDynamics — Walk-Forward Validation CLI.

Evaluates whether confidence calibration genuinely improves out-of-sample
strategy behaviour across multiple chronological folds.

Usage examples
--------------
# Default 4-fold annual walk-forward on the primary strategy:
python scripts/run_walk_forward.py \\
    --data data/btcusd_3600s_2019-01-01_to_2025-12-30.csv \\
    --strategy trend_following_v8_ecap75_add90

# Custom date range and fold parameters:
python scripts/run_walk_forward.py \\
    --data data/btcusd_3600s_2019-01-01_to_2025-12-30.csv \\
    --strategy trend_following_v8_ecap75_add90 \\
    --start 2019-01-01 --end 2025-12-31 \\
    --train-min-years 2 --test-years 1

# Custom folds from JSON file:
python scripts/run_walk_forward.py \\
    --data data/btcusd_3600s_2019-01-01_to_2025-12-30.csv \\
    --strategy trend_following_v8_ecap75_add90 \\
    --fold-mode custom \\
    --custom-folds-json '[{"train_start":"2019-01-01","train_end":"2021-12-31","test_start":"2022-01-01","test_end":"2022-12-31"}]'

# With custom execution cost overrides:
python scripts/run_walk_forward.py \\
    --data data/btcusd_3600s_2019-01-01_to_2025-12-30.csv \\
    --strategy trend_following_v8_ecap75_add90 \\
    --fee 0.0006 --base-slippage 3.0 --slippage-vol-factor 50.0
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
import time
from pathlib import Path


from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("walk_forward")

from research.harness.data_loader import load_ohlcv, validate_ohlcv
from research.harness.execution_model import ExecutionConfig
from research.strategies import REGISTRY
from research.ml.validation.fold_spec import build_annual_folds, from_custom_json
from research.ml.validation.walk_forward import run_walk_forward
from research.ml.validation.report import aggregate, to_markdown, save_report


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Walk-forward validation of confidence calibration.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--data", required=True, help="Path to OHLCV CSV file")
    p.add_argument(
        "--strategy",
        default="trend_following_v8_ecap75_add90",
        help="Strategy name (must be in REGISTRY)",
    )
    p.add_argument("--asset", default="BTC", help="Asset label for logging")
    p.add_argument("--start", default=None, help="Override data start date (YYYY-MM-DD)")
    p.add_argument("--end", default=None, help="Override data end date (YYYY-MM-DD)")
    p.add_argument(
        "--fold-mode",
        choices=["annual", "custom"],
        default="annual",
        help="Fold generation mode",
    )
    p.add_argument(
        "--train-min-years",
        type=int,
        default=2,
        help="Minimum training years before first test fold",
    )
    p.add_argument(
        "--test-years",
        type=int,
        default=1,
        help="Test window length in years (annual mode)",
    )
    p.add_argument(
        "--custom-folds-json",
        default=None,
        help="JSON string or file path defining custom folds (fold-mode=custom)",
    )
    p.add_argument(
        "--output",
        default="artifacts/walk_forward",
        help="Base output directory",
    )
    p.add_argument("--capital", type=float, default=100_000.0, help="Starting capital per fold")
    p.add_argument("--rebalance-threshold", type=float, default=None,
                   help="Minimum exposure change to trigger a trade")
    # Execution cost overrides
    p.add_argument("--fee", type=float, default=None, help="Taker fee rate (e.g. 0.0006)")
    p.add_argument("--base-slippage", type=float, default=None, help="Base slippage bps")
    p.add_argument("--slippage-vol-factor", type=float, default=None,
                   help="Slippage vol factor")
    p.add_argument("--cooldown", type=int, default=None, help="Cooldown bars between trades")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    t0 = time.time()

    # ── Load strategy ──────────────────────────────────────────────────────
    strategy_module = REGISTRY.get(args.strategy)
    if strategy_module is None:
        log.error("Unknown strategy '%s'. Available: %s", args.strategy, sorted(REGISTRY))
        sys.exit(1)
    strategy_id = getattr(strategy_module, "STRATEGY_ID", args.strategy)
    log.info("Strategy: %s  (id=%s)", args.strategy, strategy_id)

    # ── Load data ──────────────────────────────────────────────────────────
    log.info("Loading data: %s", args.data)
    df = load_ohlcv(args.data, start=args.start, end=args.end)
    validate_ohlcv(df)
    data_start = str(df.index[0].date())
    data_end = str(df.index[-1].date())
    log.info("Loaded %d bars  %s → %s", len(df), data_start, data_end)

    # ── Build execution config ─────────────────────────────────────────────
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
        "Execution model: fee=%.4f  base_slip=%.1fbps  vol_factor=%.1f  cooldown=%d",
        exec_config.taker_fee_rate,
        exec_config.base_slippage_bps,
        exec_config.slippage_vol_factor,
        exec_config.cooldown_bars,
    )

    rebalance_threshold = args.rebalance_threshold or 0.05

    # ── Build folds ────────────────────────────────────────────────────────
    if args.fold_mode == "custom":
        if args.custom_folds_json is None:
            log.error("--custom-folds-json required when --fold-mode=custom")
            sys.exit(1)
        # Accept either raw JSON or a file path
        json_src = args.custom_folds_json
        if Path(json_src).is_file():
            json_src = Path(json_src).read_text()
        folds = from_custom_json(json_src)
    else:
        folds = build_annual_folds(
            data_start=data_start,
            data_end=data_end,
            train_min_years=args.train_min_years,
            test_years=args.test_years,
        )

    if not folds:
        log.error("No folds generated. Check --start/--end and --train-min-years.")
        sys.exit(1)

    log.info("Walk-forward: %d folds", len(folds))
    for f in folds:
        log.info("  %s", f)

    # ── Run walk-forward ───────────────────────────────────────────────────
    fold_results = run_walk_forward(
        df=df,
        strategy_module=strategy_module,
        folds=folds,
        exec_config=exec_config,
        initial_capital=args.capital,
        rebalance_threshold=rebalance_threshold,
        asset=args.asset,
    )

    # ── Aggregate and report ───────────────────────────────────────────────
    agg = aggregate(fold_results)
    md = to_markdown(fold_results, agg)

    # Print summary to console
    log.info("═" * 60)
    active = [r for r in fold_results if not r.skipped]
    log.info("Walk-forward complete. %d / %d folds ran.", len(active), len(fold_results))
    log.info(
        "Calibration improved Sharpe: %d/%d  Calmar: %d/%d  DD: %d/%d  Slippage: %d/%d",
        agg.get("improved_sharpe", 0), len(active),
        agg.get("improved_calmar", 0), len(active),
        agg.get("improved_dd", 0), len(active),
        agg.get("improved_slippage", 0), len(active),
    )
    log.info("Conclusion: %s", agg.get("conclusion", "—").upper())
    log.info("Elapsed: %.1fs", time.time() - t0)

    # Save artifacts
    out_dir = save_report(
        fold_results=fold_results,
        strategy_id=strategy_id,
        out_dir=args.output,
    )
    log.info("Artifacts saved to: %s", out_dir)
    log.info("  fold_results.json  fold_results.csv  summary.json  summary.md")
    log.info("  chart_performance.png  chart_calibration.png")

    # Print markdown to stdout for immediate review
    print("\n" + "=" * 60)
    print(md)


if __name__ == "__main__":
    main()
