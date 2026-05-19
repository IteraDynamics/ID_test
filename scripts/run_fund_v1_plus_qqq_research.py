#!/usr/bin/env python
"""Research-only Fund v1 + QQQ SMA blend runner.

Compares the current 4-sleeve crypto Fund v1 baseline against static allocations
that add QQQ_1D equity_sma_band_v1 as a separate, tradeable equity sleeve.

This script does not modify runtime, paper trading, brokers, allocators,
governors, or Fund v1 behavior.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from research.harness.backtest_engine import BacktestResult, run_backtest
from research.harness.data_loader import load_ohlcv, validate_ohlcv
from research.harness.execution_model import ExecutionConfig
from research.harness.metrics import BacktestMetrics, compute_metrics
from research.harness.resampler import resample_ohlcv
from research.strategies import REGISTRY as STRATEGY_REGISTRY

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s — %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("fund_v1_plus_qqq")

FUND_V1_STRATEGY = "trend_following_v8_ecap60_add80"
QQQ_STRATEGY = "equity_qqq_sma_band_v1"

CRYPTO_EXEC = ExecutionConfig.from_env()
QQQ_EXEC = ExecutionConfig(
    taker_fee_rate=0.0002,
    maker_fee_rate=0.0001,
    use_maker_fees=False,
    base_slippage_bps=7.5,
    slippage_size_factor=5.0,
    slippage_vol_factor=20.0,
    min_slippage_bps=1.0,
    max_slippage_bps=30.0,
    spread_k=0.25,
    min_spread_bps=0.5,
    large_trade_threshold=0.25,
    cooldown_bars=0,
)


@dataclass(frozen=True)
class SleeveRun:
    label: str
    asset: str
    result: BacktestResult
    metrics: BacktestMetrics


def _load(path: str, asset: str, start: str | None, end: str | None) -> pd.DataFrame:
    df = load_ohlcv(path, start=start, end=end, asset=asset)
    for warning in validate_ohlcv(df):
        log.warning("Data warning [%s]: %s", asset, warning)
    return df


def _run_sleeve(label: str, asset: str, df: pd.DataFrame, strategy_name: str, capital: float, exec_config: ExecutionConfig) -> SleeveRun:
    strategy = STRATEGY_REGISTRY[strategy_name]
    log.info("Running %s — $%.0f on %d bars", label, capital, len(df))
    result = run_backtest(df=df, strategy_module=strategy, asset=asset, initial_capital=capital, exec_config=exec_config)
    metrics = compute_metrics(result.equity_curve, result.trades, {"strategy_id": strategy_name, "asset": asset, "initial_capital": capital})
    return SleeveRun(label=label, asset=asset, result=result, metrics=metrics)


def _daily_equity(series: pd.Series) -> pd.Series:
    return series.resample("1D").last().ffill().dropna()


def _blend_metrics(sleeves: list[SleeveRun], capital: float, label: str) -> tuple[pd.Series, BacktestMetrics]:
    daily = pd.DataFrame({s.label: _daily_equity(s.result.equity_curve) for s in sleeves}).dropna(how="any")
    portfolio = daily.sum(axis=1)
    portfolio.name = label
    trades = [t for s in sleeves for t in s.result.trades]
    metrics = compute_metrics(portfolio, trades, {"strategy_id": label, "asset": "PORTFOLIO", "initial_capital": capital})
    return portfolio, metrics


def _slice_return(equity: pd.Series, start: str, end: str) -> float | None:
    s = equity.loc[(equity.index >= pd.Timestamp(start)) & (equity.index <= pd.Timestamp(end))].dropna()
    if len(s) < 2:
        return None
    return round((float(s.iloc[-1]) / float(s.iloc[0]) - 1.0) * 100.0, 4)


def _run_all_sleeves(args: argparse.Namespace, qqq_weight: float) -> tuple[list[SleeveRun], pd.Series, BacktestMetrics]:
    crypto_weight = 1.0 - qqq_weight
    crypto_cap = args.capital * crypto_weight / 4.0
    qqq_cap = args.capital * qqq_weight

    btc_1h = _load(args.btc_data, "BTC", args.start, args.end)
    eth_1h = _load(args.eth_data, "ETH", args.start, args.end)
    qqq_1d = _load(args.qqq_data, "QQQ", args.start, args.end)

    sleeves = [
        _run_sleeve("BTC_1H", "BTC", btc_1h, FUND_V1_STRATEGY, crypto_cap, CRYPTO_EXEC),
        _run_sleeve("BTC_4H", "BTC", resample_ohlcv(btc_1h, "4h"), FUND_V1_STRATEGY, crypto_cap, CRYPTO_EXEC),
        _run_sleeve("ETH_1H", "ETH", eth_1h, FUND_V1_STRATEGY, crypto_cap, CRYPTO_EXEC),
        _run_sleeve("ETH_4H", "ETH", resample_ohlcv(eth_1h, "4h"), FUND_V1_STRATEGY, crypto_cap, CRYPTO_EXEC),
    ]
    if qqq_weight > 0:
        sleeves.append(_run_sleeve("QQQ_1D", "QQQ", qqq_1d, QQQ_STRATEGY, qqq_cap, QQQ_EXEC))

    label = f"fund_v1_plus_qqq_{int(round(qqq_weight * 100))}pct"
    equity, metrics = _blend_metrics(sleeves, args.capital, label)
    return sleeves, equity, metrics


def _row(label: str, qqq_weight: float, equity: pd.Series, metrics: BacktestMetrics, args: argparse.Namespace, baseline: pd.Series | None) -> dict[str, Any]:
    corr = None
    if baseline is not None:
        joined = pd.concat([baseline.pct_change(), equity.pct_change()], axis=1).dropna()
        if len(joined) > 2:
            corr = round(float(joined.iloc[:, 0].corr(joined.iloc[:, 1])), 4)
    return {
        "label": label,
        "qqq_weight": qqq_weight,
        "crypto_weight": 1.0 - qqq_weight,
        "cagr_pct": metrics.cagr_pct,
        "max_drawdown_pct": metrics.max_drawdown_pct,
        "sharpe": metrics.sharpe,
        "calmar": metrics.calmar,
        "trades": metrics.n_trades,
        "costs_usd": round(metrics.total_fees_paid + metrics.total_slippage_cost, 2),
        "stress_return_pct": _slice_return(equity, args.stress_start, args.stress_end),
        "corr_to_baseline": corr,
        "start": metrics.start,
        "end": metrics.end,
    }


def _write_outputs(rows: list[dict[str, Any]], curves: dict[str, pd.Series], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out_dir / "summary.csv", index=False)
    pd.DataFrame(curves).dropna(how="all").to_csv(out_dir / "equity_curves.csv")
    with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, default=str)
    md = out_dir / "summary.md"
    with open(md, "w", encoding="utf-8") as f:
        f.write("# Fund v1 + QQQ SMA Research Summary\n\n")
        f.write("Research-only static-weight portfolio blend test.\n\n")
        f.write("| Label | QQQ Wt | CAGR | MaxDD | Sharpe | Calmar | Stress | Trades | Costs | Corr vs Base |\n")
        f.write("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n")
        for r in rows:
            stress = "n/a" if r["stress_return_pct"] is None else f"{r['stress_return_pct']:.2f}%"
            corr = "n/a" if r["corr_to_baseline"] is None else f"{r['corr_to_baseline']:.3f}"
            f.write(f"| {r['label']} | {r['qqq_weight']:.0%} | {r['cagr_pct']:.2f}% | {r['max_drawdown_pct']:.2f}% | {r['sharpe']:.3f} | {r['calmar']:.3f} | {stress} | {r['trades']} | ${r['costs_usd']:,.0f} | {corr} |\n")
    return md


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Research-only Fund v1 + QQQ SMA static blend runner")
    p.add_argument("--btc-data", required=True)
    p.add_argument("--eth-data", required=True)
    p.add_argument("--qqq-data", required=True)
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--qqq-weights", nargs="+", type=float, default=[0.0, 0.10, 0.15, 0.20, 0.25])
    p.add_argument("--stress-start", default="2022-01-01")
    p.add_argument("--stress-end", default="2022-12-31")
    p.add_argument("--out-dir", default="artifacts/fund_v1_plus_qqq_research")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    print("\nFund v1 + QQQ SMA Research Runner")
    print("Role: portfolio blend research")
    print("Runtime impact: none")
    print("Fund v1 paper-trading impact: none\n")

    rows: list[dict[str, Any]] = []
    curves: dict[str, pd.Series] = {}
    baseline_curve: pd.Series | None = None

    for weight in args.qqq_weights:
        sleeves, equity, metrics = _run_all_sleeves(args, weight)
        label = f"qqq_{int(round(weight * 100))}pct"
        if weight == 0:
            baseline_curve = equity
        curves[label] = equity
        rows.append(_row(label, weight, equity, metrics, args, baseline_curve if weight > 0 else None))

    summary = _write_outputs(rows, curves, Path(args.out_dir))

    print("=" * 118)
    print("  FUND V1 + QQQ SMA — STATIC BLEND RESEARCH")
    print("=" * 118)
    print(f"  {'Label':<12} {'QQQ Wt':>7} {'CAGR%':>9} {'MaxDD%':>9} {'Sharpe':>8} {'Calmar':>8} {'Stress%':>9} {'Trades':>7} {'Costs $':>10} {'Corr':>7}")
    print("  " + "-" * 116)
    for r in rows:
        stress = "n/a" if r["stress_return_pct"] is None else f"{r['stress_return_pct']:>8.2f}%"
        corr = "n/a" if r["corr_to_baseline"] is None else f"{r['corr_to_baseline']:>7.3f}"
        print(f"  {r['label']:<12} {r['qqq_weight']:>6.0%} {r['cagr_pct']:>8.2f}% {r['max_drawdown_pct']:>8.2f}% {r['sharpe']:>8.3f} {r['calmar']:>8.3f} {stress:>9} {r['trades']:>7} ${r['costs_usd']:>9,.0f} {corr:>7}")
    print("=" * 118)
    print(f"  Summary: {summary}")
    print("  Verdict: research output only; review before any integration.\n")


if __name__ == "__main__":
    main()
