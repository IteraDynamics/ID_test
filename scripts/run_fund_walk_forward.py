#!/usr/bin/env python
"""IteraDynamics — Fund-Level Walk-Forward CLI.

Runs chronological walk-forward validation for the current fund architecture:
BTC/ETH × 1H/4H, equal-weight, using the selected trend-following strategy.

Examples
--------
Global calibration baseline (BTC_1H calibrator cross-applied):

python scripts\run_fund_walk_forward.py `
  --btc-data data\btcusd_3600s_2019-01-01_to_2025-12-30.csv `
  --eth-data data\ethusd_3600s_2019-01-01_to_2025-12-30.csv `
  --strategy trend_following_v8_ecap60_add80 `
  --calibration-mode global `
  --fee 0.0006 --base-slippage 3 --slippage-vol-factor 50 `
  --rebalance-threshold 0.05

Per-sleeve calibration experiment:

python scripts\run_fund_walk_forward.py `
  --btc-data data\btcusd_3600s_2019-01-01_to_2025-12-30.csv `
  --eth-data data\ethusd_3600s_2019-01-01_to_2025-12-30.csv `
  --strategy trend_following_v8_ecap60_add80 `
  --calibration-mode per_sleeve `
  --fee 0.0006 --base-slippage 3 --slippage-vol-factor 50 `
  --rebalance-threshold 0.05
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
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any


from dotenv import load_dotenv
load_dotenv()

import pandas as pd

from research.harness.data_loader import load_ohlcv, validate_ohlcv
from research.harness.execution_model import ExecutionConfig
from research.ml.validation.fold_spec import build_annual_folds, from_custom_json
from research.ml.validation.fund_walk_forward import FundFoldResult, run_fund_walk_forward
from research.strategies import REGISTRY

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("fund_walk_forward")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Fund-level walk-forward validation for BTC/ETH × 1H/4H portfolio.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--btc-data", required=True, help="Path to BTC/USD 1H OHLCV CSV")
    p.add_argument("--eth-data", required=True, help="Path to ETH/USD 1H OHLCV CSV")
    p.add_argument(
        "--strategy",
        default="trend_following_v8_ecap60_add80",
        help="Strategy name in research.strategies.REGISTRY",
    )
    p.add_argument("--capital", type=float, default=100_000.0, help="Portfolio capital per fold")
    p.add_argument("--start", default=None, help="Optional start date YYYY-MM-DD")
    p.add_argument("--end", default=None, help="Optional end date YYYY-MM-DD")
    p.add_argument(
        "--calibration-mode",
        choices=["global", "per_sleeve"],
        default="global",
        help="global = BTC_1H calibrator cross-applied; per_sleeve = train one calibrator per sleeve",
    )
    p.add_argument(
        "--fold-mode",
        choices=["annual", "custom"],
        default="annual",
        help="Fold generation mode",
    )
    p.add_argument("--train-min-years", type=int, default=2)
    p.add_argument("--test-years", type=int, default=1)
    p.add_argument(
        "--custom-folds-json",
        default=None,
        help="JSON string or file path defining custom folds when --fold-mode=custom",
    )
    p.add_argument("--min-train-samples", type=int, default=30)
    p.add_argument("--rebalance-threshold", type=float, default=0.05)
    p.add_argument("--fee", type=float, default=None, help="Taker fee rate, e.g. 0.0006")
    p.add_argument("--base-slippage", type=float, default=None, help="Base slippage in bps")
    p.add_argument("--slippage-vol-factor", type=float, default=None)
    p.add_argument("--cooldown", type=int, default=None)
    p.add_argument("--output", default="artifacts/fund_walk_forward")
    return p.parse_args()


def _load_data(args: argparse.Namespace) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for asset, path in [("BTC", args.btc_data), ("ETH", args.eth_data)]:
        log.info("Loading %s data: %s", asset, path)
        df = load_ohlcv(path, start=args.start, end=args.end, asset=asset)
        for warning in validate_ohlcv(df):
            log.warning("Data warning [%s]: %s", asset, warning)
        log.info("Loaded %d bars  %s → %s  [%s]", len(df), df.index[0], df.index[-1], asset)
        out[asset] = df
    return out


def _build_exec_config(args: argparse.Namespace) -> ExecutionConfig:
    cfg = ExecutionConfig.from_env()
    if args.fee is not None:
        cfg.taker_fee_rate = args.fee
    if args.base_slippage is not None:
        cfg.base_slippage_bps = args.base_slippage
    if args.slippage_vol_factor is not None:
        cfg.slippage_vol_factor = args.slippage_vol_factor
    if args.cooldown is not None:
        cfg.cooldown_bars = args.cooldown
    return cfg


def _build_folds(args: argparse.Namespace, raw_data: dict[str, pd.DataFrame]):
    common_start = max(df.index[0] for df in raw_data.values()).date().isoformat()
    common_end = min(df.index[-1] for df in raw_data.values()).date().isoformat()

    if args.fold_mode == "custom":
        if args.custom_folds_json is None:
            raise SystemExit("--custom-folds-json is required when --fold-mode=custom")
        src = args.custom_folds_json
        if Path(src).is_file():
            src = Path(src).read_text()
        return from_custom_json(src)

    return build_annual_folds(
        data_start=common_start,
        data_end=common_end,
        train_min_years=args.train_min_years,
        test_years=args.test_years,
    )


def _fold_to_dict(r: FundFoldResult) -> dict[str, Any]:
    return {
        "fold": r.fold_spec.to_dict(),
        "skipped": r.skipped,
        "skip_reason": r.skip_reason,
        "baseline": r.baseline,
        "calibrated": r.calibrated,
        "delta": r.delta,
        "improvements": {
            "sharpe": r.cal_improved_sharpe,
            "calmar": r.cal_improved_calmar,
            "drawdown": r.cal_improved_dd,
            "slippage": r.cal_improved_slippage,
        },
        "sleeves": [s.__dict__ for s in r.sleeves],
        "baseline_corr": r.baseline_corr,
        "calibrated_corr": r.calibrated_corr,
    }


def _rows(results: list[FundFoldResult]) -> list[dict[str, Any]]:
    rows = []
    for r in results:
        if r.skipped:
            rows.append({"fold_id": r.fold_spec.fold_id, "skipped": True, "skip_reason": r.skip_reason})
            continue
        rows.append({
            "fold_id": r.fold_spec.fold_id,
            "train_period": f"{r.fold_spec.train_start}->{r.fold_spec.train_end}",
            "test_period": f"{r.fold_spec.test_start}->{r.fold_spec.test_end}",
            "skipped": False,
            "base_cagr": r.baseline.get("cagr_pct"),
            "base_dd": r.baseline.get("max_drawdown_pct"),
            "base_sharpe": r.baseline.get("sharpe"),
            "base_calmar": r.baseline.get("calmar"),
            "base_slippage": r.baseline.get("total_slippage_cost"),
            "cal_cagr": r.calibrated.get("cagr_pct"),
            "cal_dd": r.calibrated.get("max_drawdown_pct"),
            "cal_sharpe": r.calibrated.get("sharpe"),
            "cal_calmar": r.calibrated.get("calmar"),
            "cal_slippage": r.calibrated.get("total_slippage_cost"),
            "delta_cagr": r.delta.get("delta_cagr_pct"),
            "delta_dd": r.delta.get("delta_max_drawdown_pct"),
            "delta_sharpe": r.delta.get("delta_sharpe"),
            "delta_calmar": r.delta.get("delta_calmar"),
            "delta_slippage": r.delta.get("delta_total_slippage_cost"),
        })
    return rows


def _aggregate(results: list[FundFoldResult]) -> dict[str, Any]:
    active = [r for r in results if not r.skipped]
    n = len(active)
    if not active:
        return {"n_folds_active": 0, "conclusion": "no active folds"}

    def mean_delta(key: str) -> float | None:
        vals = [r.delta.get(key) for r in active if r.delta.get(key) is not None]
        if not vals:
            return None
        return round(float(sum(vals) / len(vals)), 6)

    return {
        "n_folds_total": len(results),
        "n_folds_active": n,
        "improved_sharpe": sum(1 for r in active if r.cal_improved_sharpe),
        "improved_calmar": sum(1 for r in active if r.cal_improved_calmar),
        "improved_drawdown": sum(1 for r in active if r.cal_improved_dd),
        "improved_slippage": sum(1 for r in active if r.cal_improved_slippage),
        "mean_delta_cagr": mean_delta("delta_cagr_pct"),
        "mean_delta_dd": mean_delta("delta_max_drawdown_pct"),
        "mean_delta_sharpe": mean_delta("delta_sharpe"),
        "mean_delta_calmar": mean_delta("delta_calmar"),
        "mean_delta_slippage": mean_delta("delta_total_slippage_cost"),
    }


def _print_summary(results: list[FundFoldResult], agg: dict[str, Any], args: argparse.Namespace) -> None:
    print("\n" + "=" * 96)
    print("  FUND WALK-FORWARD — BTC/ETH × 1H/4H")
    print(f"  Strategy: {args.strategy}")
    print(f"  Calibration mode: {args.calibration_mode}")
    print("=" * 96)
    print("  Fold  Test Period              Base CAGR  Base DD  Base Shp  Base Cal   Cal CAGR   Cal DD   Cal Shp   Cal Cal")
    print("  " + "-" * 92)
    for r in results:
        if r.skipped:
            print(f"  {r.fold_spec.fold_id:<5} {r.fold_spec.test_start}->{r.fold_spec.test_end:<10} SKIPPED: {r.skip_reason}")
            continue
        print(
            f"  {r.fold_spec.fold_id:<5} "
            f"{r.fold_spec.test_start}->{r.fold_spec.test_end:<10} "
            f"{r.baseline.get('cagr_pct', 0):>9.2f}% "
            f"{r.baseline.get('max_drawdown_pct', 0):>7.2f}% "
            f"{r.baseline.get('sharpe', 0):>8.3f} "
            f"{r.baseline.get('calmar', 0):>8.3f} "
            f"{r.calibrated.get('cagr_pct', 0):>9.2f}% "
            f"{r.calibrated.get('max_drawdown_pct', 0):>7.2f}% "
            f"{r.calibrated.get('sharpe', 0):>8.3f} "
            f"{r.calibrated.get('calmar', 0):>8.3f}"
        )
    print("=" * 96)
    active = agg.get("n_folds_active", 0)
    print(f"  Active folds: {active}/{agg.get('n_folds_total', len(results))}")
    print(f"  Improved Sharpe:   {agg.get('improved_sharpe', 0)}/{active}")
    print(f"  Improved Calmar:   {agg.get('improved_calmar', 0)}/{active}")
    print(f"  Improved Drawdown: {agg.get('improved_drawdown', 0)}/{active}")
    print(f"  Improved Slippage: {agg.get('improved_slippage', 0)}/{active}")
    print(f"  Mean ΔSharpe:      {agg.get('mean_delta_sharpe')}")
    print(f"  Mean ΔCalmar:      {agg.get('mean_delta_calmar')}")
    print("=" * 96 + "\n")


def _save(results: list[FundFoldResult], agg: dict[str, Any], args: argparse.Namespace) -> Path:
    run_id = time.strftime("%Y%m%d_%H%M%S")
    out = Path(args.output) / args.strategy / args.calibration_mode / run_id
    out.mkdir(parents=True, exist_ok=True)

    payload = {
        "schema_version": "1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "strategy": args.strategy,
        "calibration_mode": args.calibration_mode,
        "folds": [_fold_to_dict(r) for r in results],
        "aggregate": agg,
    }
    (out / "fund_walk_forward.json").write_text(json.dumps(payload, indent=2, default=str))
    pd.DataFrame(_rows(results)).to_csv(out / "fold_results.csv", index=False)
    (out / "summary.json").write_text(json.dumps(agg, indent=2, default=str))
    return out


def main() -> None:
    args = parse_args()
    t0 = time.time()

    strategy_module = REGISTRY.get(args.strategy)
    if strategy_module is None:
        log.error("Unknown strategy '%s'. Available: %s", args.strategy, sorted(REGISTRY))
        sys.exit(1)

    raw_data = _load_data(args)
    exec_config = _build_exec_config(args)
    log.info(
        "Execution: fee=%.4f base_slip=%.1fbps vol_factor=%.1f cooldown=%d rebalance=%.3f",
        exec_config.taker_fee_rate,
        exec_config.base_slippage_bps,
        exec_config.slippage_vol_factor,
        exec_config.cooldown_bars,
        args.rebalance_threshold,
    )

    folds = _build_folds(args, raw_data)
    if not folds:
        raise SystemExit("No walk-forward folds generated. Check date range and fold settings.")
    log.info("Generated %d folds", len(folds))
    for f in folds:
        log.info("  %s", f)

    results = run_fund_walk_forward(
        raw_data=raw_data,
        strategy_module=strategy_module,
        folds=folds,
        exec_config=exec_config,
        initial_capital=args.capital,
        rebalance_threshold=args.rebalance_threshold,
        min_train_samples=args.min_train_samples,
        calibration_mode=args.calibration_mode,
    )
    agg = _aggregate(results)
    _print_summary(results, agg, args)
    out = _save(results, agg, args)

    log.info("Elapsed: %.1fs", time.time() - t0)
    log.info("Artifacts saved to: %s", out)
    log.info("  fund_walk_forward.json  fold_results.csv  summary.json")


if __name__ == "__main__":
    main()
