#!/usr/bin/env python
"""IteraDynamics — Fund v1 ETH/BTC allocator overlay runner.

This script tests ETH/BTC relative rotation as an INTERNAL allocator overlay for
Fund v1, not as a separate capital sleeve.

Base Fund v1:
    BTC_1H, BTC_4H, ETH_1H, ETH_4H using trend_following_v8_ecap60_add80

Overlay:
    ETHBTC_Rotation_v1 changes the sleeve weights between BTC and ETH while
    preserving the same underlying strategy signals.  It asks: should the
    existing crypto risk budget lean toward BTC sleeves or ETH sleeves?

Important limitation:
    This runner recombines independently backtested sleeve equity curves using
    time-varying weights.  It does not model extra transaction costs caused by
    reallocating capital between sleeves.  It is therefore a research test of
    allocator usefulness, not a final live execution model.

PowerShell:
python scripts\run_fund_allocator_overlay.py `
  --btc-data "data\btcusd_3600s_2019-01-01_to_2025-12-30.csv" `
  --eth-data "data\ethusd_3600s_2019-01-01_to_2025-12-30.csv" `
  --strategy trend_following_v8_ecap60_add80 `
  --calibrate `
  --fee 0.0006 `
  --base-slippage 3 `
  --slippage-vol-factor 50 `
  --rebalance-threshold 0.05
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("fund_allocator_overlay")

import numpy as np
import pandas as pd

from research.harness.backtest_engine import BacktestResult, run_backtest
from research.harness.data_loader import load_ohlcv, validate_ohlcv
from research.harness.execution_model import ExecutionConfig
from research.harness.metrics import BacktestMetrics, compute_metrics
from research.harness.resampler import align_equity_curves, resample_ohlcv
from research.strategies import REGISTRY as STRATEGY_REGISTRY
from research.strategies.ethbtc_ratio import build_ratio_df
from research.strategies.ethbtc_relative_rotation_v1 import (
    BTC_FAVORED,
    ETH_FAVORED,
    NEUTRAL,
    STRATEGY_ID as ALLOCATOR_ID,
    compute_rotation_signal,
)

DEFAULT_STRATEGY = "trend_following_v8_ecap60_add80"


@dataclass(frozen=True)
class SleeveConfig:
    label: str
    asset: str
    timeframe: str
    data_path: str
    calibrated: bool = False


@dataclass(frozen=True)
class TiltSchedule:
    name: str
    btc_total_when_btc_favored: float
    btc_total_when_eth_favored: float

    def weights_for_signal(self, signal: int) -> dict[str, float]:
        if signal == BTC_FAVORED:
            btc_total = self.btc_total_when_btc_favored
        elif signal == ETH_FAVORED:
            btc_total = self.btc_total_when_eth_favored
        else:
            btc_total = 0.50
        eth_total = 1.0 - btc_total
        return {
            "BTC_1H": btc_total / 2.0,
            "BTC_4H": btc_total / 2.0,
            "ETH_1H": eth_total / 2.0,
            "ETH_4H": eth_total / 2.0,
        }


SCHEDULES: list[TiltSchedule] = [
    TiltSchedule("A_mild_60_40", btc_total_when_btc_favored=0.60, btc_total_when_eth_favored=0.40),
    TiltSchedule("B_moderate_65_35", btc_total_when_btc_favored=0.65, btc_total_when_eth_favored=0.35),
    TiltSchedule("C_strong_70_30", btc_total_when_btc_favored=0.70, btc_total_when_eth_favored=0.30),
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Test ETH/BTC relative rotation as a Fund v1 allocator overlay",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--btc-data", required=True, help="Path to BTC/USD 1H OHLCV CSV")
    p.add_argument("--eth-data", required=True, help="Path to ETH/USD 1H OHLCV CSV")
    p.add_argument("--strategy", default=DEFAULT_STRATEGY)
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--calibrate", action="store_true")
    p.add_argument("--calibrators-dir", default=None)
    p.add_argument("--fee", type=float, default=None)
    p.add_argument("--base-slippage", type=float, default=None)
    p.add_argument("--slippage-vol-factor", type=float, default=None)
    p.add_argument("--cooldown", type=int, default=None)
    p.add_argument("--rebalance-threshold", type=float, default=None)
    p.add_argument("--out-dir", default=None)
    return p.parse_args()


def _perf(eq: pd.Series, label: str) -> dict[str, Any]:
    eq = eq.dropna()
    if len(eq) < 2:
        return {
            "label": label,
            "total_ret": 0.0,
            "cagr": 0.0,
            "max_dd": 0.0,
            "sharpe": 0.0,
            "calmar": 0.0,
            "ann_vol": 0.0,
        }

    delta_s = (eq.index[-1] - eq.index[0]).total_seconds()
    n_gaps = len(eq) - 1
    bar_sec = delta_s / n_gaps if n_gaps > 0 and delta_s > 0 else 3600.0
    bars_per_year = 365.25 * 24 * 3600 / bar_sec

    initial = float(eq.iloc[0])
    final = float(eq.iloc[-1])
    years = len(eq) / bars_per_year
    total_ret = (final / initial - 1.0) * 100.0
    cagr = ((final / initial) ** (1.0 / max(years, 1 / 365)) - 1.0) * 100.0

    running_max = eq.cummax()
    max_dd = float(((eq - running_max) / running_max).min()) * 100.0

    bar_rets = eq.pct_change().dropna()
    std = float(bar_rets.std())
    ann_vol = std * np.sqrt(bars_per_year) * 100.0
    sharpe = float(bar_rets.mean() / std * np.sqrt(bars_per_year)) if std > 1e-12 else 0.0
    calmar = cagr / abs(max_dd) if abs(max_dd) > 1e-6 else 0.0

    return {
        "label": label,
        "total_ret": total_ret,
        "cagr": cagr,
        "max_dd": max_dd,
        "sharpe": sharpe,
        "calmar": calmar,
        "ann_vol": ann_vol,
    }


def _year_return(eq: pd.Series, year: int) -> float | None:
    sl = eq[eq.index.year == year]
    if len(sl) < 2:
        return None
    return (float(sl.iloc[-1]) / float(sl.iloc[0]) - 1.0) * 100.0


def _year_maxdd(eq: pd.Series, year: int) -> float | None:
    sl = eq[eq.index.year == year]
    if len(sl) < 2:
        return None
    running_max = sl.cummax()
    return float(((sl - running_max) / running_max).min()) * 100.0


def _print_perf_row(d: dict[str, Any], delta: dict[str, float] | None = None) -> None:
    if delta is None:
        delta_text = ""
    else:
        delta_text = (
            f" | ΔCAGR {delta['cagr']:+6.2f}"
            f" ΔDD {delta['max_dd']:+6.2f}"
            f" ΔSharpe {delta['sharpe']:+6.3f}"
            f" ΔCalmar {delta['calmar']:+6.3f}"
        )
    print(
        f"  {d['label']:<24}"
        f" {d['total_ret']:>+9.2f}%"
        f" {d['cagr']:>+8.2f}%"
        f" {d['max_dd']:>9.2f}%"
        f" {d['sharpe']:>8.3f}"
        f" {d['calmar']:>8.3f}"
        f" {d['ann_vol']:>8.2f}%"
        f"{delta_text}"
    )


def _load_calibrators(strategy_name: str, calibrate: bool, calibrators_dir: str | None) -> dict | None:
    if not calibrate:
        return None
    try:
        from research.ml.calibration.model_store import load_calibrator
        cal = load_calibrator(strategy_name, models_dir=calibrators_dir)
        if cal is not None and cal.is_fitted:
            log.info("Calibrator loaded for %s", strategy_name)
            return {strategy_name: cal}
        log.warning("No fitted calibrator found for %s — running uncalibrated", strategy_name)
        return None
    except ImportError:
        log.warning("ML calibration not available — running uncalibrated")
        return None


def _build_sleeves(args: argparse.Namespace) -> list[SleeveConfig]:
    return [
        SleeveConfig("BTC_1H", "BTC", "1H", args.btc_data, args.calibrate),
        SleeveConfig("BTC_4H", "BTC", "4H", args.btc_data, args.calibrate),
        SleeveConfig("ETH_1H", "ETH", "1H", args.eth_data, args.calibrate),
        SleeveConfig("ETH_4H", "ETH", "4H", args.eth_data, args.calibrate),
    ]


def _load_data(args: argparse.Namespace) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for asset, path in (("BTC", args.btc_data), ("ETH", args.eth_data)):
        log.info("Loading %s data: %s", asset, path)
        df = load_ohlcv(path, start=args.start, end=args.end, asset=asset)
        for w in validate_ohlcv(df):
            log.warning("Data warning [%s]: %s", asset, w)
        log.info("Loaded %d bars  %s → %s  [%s]", len(df), df.index[0], df.index[-1], asset)
        out[asset] = df
    return out


def _run_sleeves(
    sleeves: list[SleeveConfig],
    raw_data: dict[str, pd.DataFrame],
    strategy_module: Any,
    strategy_name: str,
    capital: float,
    exec_config: ExecutionConfig,
    rebalance_threshold: float,
    calibrators: dict | None,
) -> dict[str, BacktestResult]:
    results: dict[str, BacktestResult] = {}
    # All sleeves are run at full initial capital. Weighting happens later at the
    # portfolio-combination layer. This avoids re-running sleeves for each weight
    # schedule and makes time-varying recombination straightforward.
    for s in sleeves:
        df = raw_data[s.asset]
        if s.timeframe == "4H":
            df = resample_ohlcv(df, "4h")
            log.info("Resampled %s to 4H: %d bars  %s → %s", s.asset, len(df), df.index[0], df.index[-1])

        log.info("Running sleeve %s at full notional capital%s", s.label, " (calibrated)" if calibrators else "")
        results[s.label] = run_backtest(
            df=df,
            strategy_module=strategy_module,
            initial_capital=capital,
            exec_config=exec_config,
            rebalance_threshold=rebalance_threshold,
            asset=s.asset,
            calibrators=calibrators if s.calibrated else None,
        )
    return results


def _normalised_sleeve_returns(results: dict[str, BacktestResult]) -> pd.DataFrame:
    curves = {label: result.equity_curve for label, result in results.items()}
    aligned = align_equity_curves(curves, base_freq="1h")
    returns = aligned.pct_change().fillna(0.0)
    return returns


def _weights_frame(signal: pd.Series, schedule: TiltSchedule) -> pd.DataFrame:
    rows = [schedule.weights_for_signal(int(sig)) for sig in signal.values]
    weights = pd.DataFrame(rows, index=signal.index)
    return weights[["BTC_1H", "BTC_4H", "ETH_1H", "ETH_4H"]]


def _apply_weights(
    returns: pd.DataFrame,
    weights: pd.DataFrame,
    capital: float,
    label: str,
) -> pd.Series:
    common = returns.index.intersection(weights.index)
    r = returns.loc[common]
    # Use previous bar's allocator weights for current bar returns to avoid
    # same-bar lookahead. Backfill the first row with its own starting weights.
    w = weights.loc[common].shift(1)
    w.iloc[0] = weights.loc[common].iloc[0]
    port_ret = (r * w).sum(axis=1)
    equity = capital * (1.0 + port_ret).cumprod()
    equity.name = label
    return equity


def _save_outputs(
    out_dir: Path,
    baseline_eq: pd.Series,
    schedule_equities: dict[str, pd.Series],
    schedule_summaries: dict[str, dict[str, Any]],
    signal: pd.Series,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    eq_df = pd.DataFrame({"baseline_equal": baseline_eq, **schedule_equities})
    eq_df.to_csv(out_dir / "equity_curves.csv")
    sig_df = pd.DataFrame({"signal": signal})
    sig_df.to_csv(out_dir / "allocator_signal.csv")
    (out_dir / "summary.json").write_text(json.dumps(schedule_summaries, indent=2, default=str))


def main() -> None:
    args = parse_args()

    exec_config = ExecutionConfig.from_env()
    if args.fee is not None:
        exec_config.taker_fee_rate = args.fee
    if args.base_slippage is not None:
        exec_config.base_slippage_bps = args.base_slippage
    if args.slippage_vol_factor is not None:
        exec_config.slippage_vol_factor = args.slippage_vol_factor
    if args.cooldown is not None:
        exec_config.cooldown_bars = args.cooldown
    rebalance_threshold = (
        args.rebalance_threshold
        if args.rebalance_threshold is not None
        else float(os.getenv("REBALANCE_THRESHOLD", "0.02"))
    )

    raw_data = _load_data(args)
    ratio_df = build_ratio_df(raw_data["BTC"], raw_data["ETH"])
    allocator_signal = compute_rotation_signal(ratio_df)

    strategy_module = STRATEGY_REGISTRY[args.strategy]
    calibrators = _load_calibrators(args.strategy, args.calibrate, args.calibrators_dir)
    sleeves = _build_sleeves(args)
    sleeve_results = _run_sleeves(
        sleeves=sleeves,
        raw_data=raw_data,
        strategy_module=strategy_module,
        strategy_name=args.strategy,
        capital=args.capital,
        exec_config=exec_config,
        rebalance_threshold=rebalance_threshold,
        calibrators=calibrators,
    )

    returns = _normalised_sleeve_returns(sleeve_results)
    common_idx = returns.index.intersection(allocator_signal.index)
    returns = returns.loc[common_idx]
    allocator_signal = allocator_signal.loc[common_idx]

    equal_weights = pd.DataFrame(
        {"BTC_1H": 0.25, "BTC_4H": 0.25, "ETH_1H": 0.25, "ETH_4H": 0.25},
        index=common_idx,
    )
    baseline_eq = _apply_weights(returns, equal_weights, args.capital, "baseline_equal")
    baseline_perf = _perf(baseline_eq, "Baseline Equal")

    schedule_equities: dict[str, pd.Series] = {}
    schedule_summaries: dict[str, dict[str, Any]] = {
        "baseline_equal": baseline_perf,
        "allocator_id": {"strategy_id": ALLOCATOR_ID},
    }

    sig_values = allocator_signal.values
    sig_stats = {
        "pct_eth_favored": float(np.mean(sig_values == ETH_FAVORED) * 100),
        "pct_neutral": float(np.mean(sig_values == NEUTRAL) * 100),
        "pct_btc_favored": float(np.mean(sig_values == BTC_FAVORED) * 100),
        "switches": int(np.sum(np.diff(sig_values.astype(int)) != 0)),
    }

    print("\n" + "=" * 112)
    print("  FUND V1 ALLOCATOR OVERLAY — ETH/BTC Relative Rotation")
    print(f"  Period: {str(common_idx[0])[:10]} → {str(common_idx[-1])[:10]}  ({len(common_idx):,} bars)")
    print(f"  Strategy: {args.strategy}  |  Calibrated: {bool(args.calibrate and calibrators)}")
    print(f"  Signal: {sig_stats['pct_eth_favored']:.1f}% ETH_FAVORED  {sig_stats['pct_neutral']:.1f}% NEUTRAL  {sig_stats['pct_btc_favored']:.1f}% BTC_FAVORED  switches={sig_stats['switches']}")
    print("=" * 112)
    print(
        f"  {'Portfolio':<24} {'TotRet':>10} {'CAGR':>9} {'MaxDD':>10} {'Sharpe':>8} {'Calmar':>8} {'AnnVol':>9}  Deltas vs Equal"
    )
    print("  " + "-" * 108)
    _print_perf_row(baseline_perf)

    years = sorted(set(baseline_eq.index.year))
    year_rows: list[dict[str, Any]] = []

    for schedule in SCHEDULES:
        weights = _weights_frame(allocator_signal, schedule)
        eq = _apply_weights(returns, weights, args.capital, schedule.name)
        perf = _perf(eq, schedule.name)
        schedule_equities[schedule.name] = eq
        delta = {
            "cagr": perf["cagr"] - baseline_perf["cagr"],
            "max_dd": perf["max_dd"] - baseline_perf["max_dd"],
            "sharpe": perf["sharpe"] - baseline_perf["sharpe"],
            "calmar": perf["calmar"] - baseline_perf["calmar"],
        }
        schedule_summaries[schedule.name] = {
            "performance": perf,
            "delta_vs_equal": delta,
            "avg_btc_weight": float(_weights_frame(allocator_signal, schedule)[["BTC_1H", "BTC_4H"]].sum(axis=1).mean()),
            "avg_eth_weight": float(_weights_frame(allocator_signal, schedule)[["ETH_1H", "ETH_4H"]].sum(axis=1).mean()),
        }
        _print_perf_row(perf, delta)

        for yr in years:
            year_rows.append({
                "schedule": schedule.name,
                "year": yr,
                "return_pct": _year_return(eq, yr),
                "maxdd_pct": _year_maxdd(eq, yr),
                "baseline_return_pct": _year_return(baseline_eq, yr),
                "baseline_maxdd_pct": _year_maxdd(baseline_eq, yr),
            })

    print("=" * 112)
    print("\n  2022 STRESS CHECK")
    print("  " + "-" * 72)
    base_2022_r = _year_return(baseline_eq, 2022)
    base_2022_dd = _year_maxdd(baseline_eq, 2022)
    print(f"  Baseline Equal       return={base_2022_r:+7.2f}%  maxDD={base_2022_dd:7.2f}%")
    for name, eq in schedule_equities.items():
        r = _year_return(eq, 2022)
        dd = _year_maxdd(eq, 2022)
        print(f"  {name:<20} return={r:+7.2f}%  maxDD={dd:7.2f}%")

    print("\n  LIMITATION")
    print("  " + "-" * 72)
    print("  This research overlay recombines sleeve return streams with time-varying weights.")
    print("  It does not model additional transaction costs from reallocating capital between sleeves.")
    print("  Treat positive results as allocator signal evidence, not final live execution PnL.")

    run_id = f"fund_allocator_overlay_{str(common_idx[0])[:10]}_{str(common_idx[-1])[:10]}"
    out_dir = Path(args.out_dir) if args.out_dir else Path("artifacts") / run_id
    schedule_summaries["signal_stats"] = sig_stats
    schedule_summaries["year_rows"] = year_rows
    schedule_summaries["limitation"] = "Recombines sleeve return streams with time-varying weights; does not model additional realloc costs."
    _save_outputs(out_dir, baseline_eq, schedule_equities, schedule_summaries, allocator_signal)
    log.info("Artifacts saved to: %s", out_dir)
    print(f"\n  Artifacts: {out_dir}")
    print("    equity_curves.csv  allocator_signal.csv  summary.json\n")


if __name__ == "__main__":
    main()
