#!/usr/bin/env python
"""Standalone SPY/QQQ equity sleeve research runner.

Research-only. This script runs daily, single-asset equity sleeve backtests,
buy-and-hold benchmarks, yearly attribution, and stress-window diagnostics.
It does not modify runtime, paper trading, allocators, brokers, governors, or
Fund v1 behavior.
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

from research.harness.artifacts import save_artifacts
from research.harness.backtest_engine import BacktestResult, run_backtest
from research.harness.data_loader import load_ohlcv, validate_ohlcv
from research.harness.execution_model import ExecutionConfig
from research.harness.metrics import BacktestMetrics, compute_metrics
from research.strategies import REGISTRY as STRATEGY_REGISTRY

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("equity_research")

EQUITY_EXEC = ExecutionConfig(
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
class RunSpec:
    asset: str
    strategy_name: str
    data_path: str
    label: str
    kind: str = "strategy"


@dataclass(frozen=True)
class RunOutput:
    spec: RunSpec
    equity_curve: pd.Series
    metrics: BacktestMetrics
    artifact_dir: Path | None = None
    result: BacktestResult | None = None


def _build_specs(args: argparse.Namespace) -> list[RunSpec]:
    assets = [a.upper() for a in args.assets]
    specs: list[RunSpec] = []

    def add_strategy(asset: str, strategy_name: str, data_path: str) -> None:
        specs.append(RunSpec(asset, strategy_name, data_path, f"{asset}_1D_{strategy_name}"))

    def add_benchmark(asset: str, data_path: str) -> None:
        specs.append(RunSpec(asset, "buy_and_hold", data_path, f"{asset}_1D_buy_and_hold", kind="benchmark"))

    if "SPY" in assets:
        if not args.spy_data:
            raise ValueError("--spy-data is required when assets include SPY")
        if args.include_benchmarks:
            add_benchmark("SPY", args.spy_data)
        if args.strategy_profile in ("sma_band", "all"):
            add_strategy("SPY", "equity_spy_sma_band_v1", args.spy_data)
        if args.strategy_profile == "qqq_growth":
            raise ValueError("qqq_growth is only valid for QQQ")

    if "QQQ" in assets:
        if not args.qqq_data:
            raise ValueError("--qqq-data is required when assets include QQQ")
        if args.include_benchmarks:
            add_benchmark("QQQ", args.qqq_data)
        if args.strategy_profile in ("sma_band", "all"):
            add_strategy("QQQ", "equity_qqq_sma_band_v1", args.qqq_data)
        if args.strategy_profile in ("qqq_growth", "all"):
            add_strategy("QQQ", "equity_qqq_trend_v1", args.qqq_data)

    if not specs:
        raise ValueError("No runs selected")
    return specs


def _load_df(spec: RunSpec, start: str | None, end: str | None) -> pd.DataFrame:
    df = load_ohlcv(spec.data_path, start=start, end=end, asset=spec.asset)
    for warning in validate_ohlcv(df):
        log.warning("Data warning [%s]: %s", spec.asset, warning)
    if len(df) < 200:
        raise ValueError(f"Insufficient {spec.asset} daily data: {len(df)} bars")
    return df


def _benchmark_equity(df: pd.DataFrame, initial_capital: float) -> pd.Series:
    close = pd.to_numeric(df["close"], errors="coerce").dropna()
    equity = initial_capital * (close / float(close.iloc[0]))
    equity.name = "equity"
    return equity


def _run_benchmark(spec: RunSpec, args: argparse.Namespace) -> RunOutput:
    df = _load_df(spec, args.start, args.end)
    log.info("Running %s benchmark on %d bars", spec.label, len(df))
    equity = _benchmark_equity(df, args.capital)
    metrics = compute_metrics(
        equity,
        trades=[],
        params={
            "strategy_id": spec.strategy_name,
            "asset": spec.asset,
            "initial_capital": args.capital,
            "benchmark": True,
        },
    )
    return RunOutput(spec=spec, equity_curve=equity, metrics=metrics)


def _run_strategy(spec: RunSpec, args: argparse.Namespace, exec_config: ExecutionConfig) -> RunOutput:
    if spec.strategy_name not in STRATEGY_REGISTRY:
        raise KeyError(f"Strategy not registered: {spec.strategy_name}")

    df = _load_df(spec, args.start, args.end)
    strategy = STRATEGY_REGISTRY[spec.strategy_name]
    log.info("Running %s on %d bars", spec.label, len(df))

    result = run_backtest(
        df=df,
        strategy_module=strategy,
        asset=spec.asset,
        initial_capital=args.capital,
        exec_config=exec_config,
    )
    metrics = compute_metrics(result.equity_curve, result.trades, result.params)
    artifact_dir = save_artifacts(
        result=result,
        metrics=metrics,
        run_id=spec.label,
        out_dir=Path(args.out_dir) / spec.label,
        save_chart=not args.no_chart,
    )
    return RunOutput(
        spec=spec,
        result=result,
        equity_curve=result.equity_curve,
        metrics=metrics,
        artifact_dir=artifact_dir,
    )


def _run(spec: RunSpec, args: argparse.Namespace, exec_config: ExecutionConfig) -> RunOutput:
    if spec.kind == "benchmark":
        return _run_benchmark(spec, args)
    return _run_strategy(spec, args, exec_config)


def _slice_return(equity: pd.Series, start: str, end: str) -> float | None:
    s = equity.loc[(equity.index >= pd.Timestamp(start)) & (equity.index <= pd.Timestamp(end))].dropna()
    if len(s) < 2:
        return None
    return round((float(s.iloc[-1]) / float(s.iloc[0]) - 1.0) * 100.0, 4)


def _yearly_returns(equity: pd.Series) -> dict[str, float]:
    out: dict[str, float] = {}
    for year, group in equity.dropna().groupby(equity.dropna().index.year):
        if len(group) < 2:
            continue
        out[str(year)] = round((float(group.iloc[-1]) / float(group.iloc[0]) - 1.0) * 100.0, 4)
    return out


def _row(output: RunOutput, stress_start: str, stress_end: str) -> dict[str, Any]:
    m = output.metrics
    return {
        "label": output.spec.label,
        "asset": output.spec.asset,
        "kind": output.spec.kind,
        "strategy": output.spec.strategy_name,
        "start": m.start,
        "end": m.end,
        "bars": m.n_bars,
        "total_return_pct": m.total_return_pct,
        "cagr_pct": m.cagr_pct,
        "max_drawdown_pct": m.max_drawdown_pct,
        "sharpe": m.sharpe,
        "calmar": m.calmar,
        "ann_vol_pct": m.volatility_ann_pct,
        "trades": m.n_trades,
        "turnover_x": m.turnover_x,
        "fees_usd": m.total_fees_paid,
        "slippage_spread_usd": m.total_slippage_cost,
        "costs_usd": m.total_fees_paid + m.total_slippage_cost,
        "stress_return_pct": _slice_return(output.equity_curve, stress_start, stress_end),
        "yearly_returns_pct": _yearly_returns(output.equity_curve),
        "artifact_dir": str(output.artifact_dir) if output.artifact_dir else "",
    }


def _write_summary(outputs: list[RunOutput], out_dir: Path, args: argparse.Namespace) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [_row(o, args.stress_start, args.stress_end) for o in outputs]
    flat_rows = [{**r, "yearly_returns_pct": json.dumps(r["yearly_returns_pct"], sort_keys=True)} for r in rows]
    pd.DataFrame(flat_rows).to_csv(out_dir / "summary.csv", index=False)
    with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, default=str)

    md_path = out_dir / "summary.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Equity Sleeve Research Summary\n\n")
        f.write("Research-only standalone daily SPY/QQQ sleeve backtests.\n\n")
        f.write(f"Stress window: `{args.stress_start}` to `{args.stress_end}`.\n\n")
        f.write("## Headline results\n\n")
        f.write("| Label | Kind | CAGR | MaxDD | Sharpe | Calmar | Stress | Trades | Turnover | Costs |\n")
        f.write("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|\n")
        for r in rows:
            stress = "n/a" if r["stress_return_pct"] is None else f"{r['stress_return_pct']:.2f}%"
            f.write(
                f"| {r['label']} | {r['kind']} | {r['cagr_pct']:.2f}% | {r['max_drawdown_pct']:.2f}% | "
                f"{r['sharpe']:.3f} | {r['calmar']:.3f} | {stress} | {r['trades']} | "
                f"{r['turnover_x']:.2f}x | ${r['costs_usd']:,.0f} |\n"
            )

        f.write("\n## Yearly returns\n\n")
        years = sorted({year for r in rows for year in r["yearly_returns_pct"].keys()})
        f.write("| Label | " + " | ".join(years) + " |\n")
        f.write("|---" + "|---:" * len(years) + "|\n")
        for r in rows:
            vals = []
            for year in years:
                val = r["yearly_returns_pct"].get(year)
                vals.append("n/a" if val is None else f"{val:.2f}%")
            f.write(f"| {r['label']} | " + " | ".join(vals) + " |\n")

        f.write("\n## Artifacts\n\n")
        for r in rows:
            if r["artifact_dir"]:
                f.write(f"- `{r['label']}`: `{r['artifact_dir']}`\n")
        f.write("\nThese are standalone strategy results only. Review against the correct Fund v1 baseline before any fund integration.\n")
    return md_path


def _print(outputs: list[RunOutput], summary_path: Path, args: argparse.Namespace) -> None:
    print("\n" + "=" * 112)
    print("  EQUITY SLEEVE RESEARCH — STANDALONE DAILY BACKTESTS + BENCHMARKS")
    print("=" * 112)
    print(
        f"  {'Label':<36} {'Kind':<10} {'CAGR%':>9} {'MaxDD%':>9} {'Sharpe':>8} "
        f"{'Calmar':>8} {'Stress%':>9} {'Trades':>7} {'Costs $':>10}"
    )
    print("  " + "-" * 110)
    for o in outputs:
        m = o.metrics
        costs = m.total_fees_paid + m.total_slippage_cost
        stress = _slice_return(o.equity_curve, args.stress_start, args.stress_end)
        stress_txt = "n/a" if stress is None else f"{stress:>8.2f}%"
        print(
            f"  {o.spec.label:<36} {o.spec.kind:<10} {m.cagr_pct:>8.2f}% {m.max_drawdown_pct:>8.2f}% "
            f"{m.sharpe:>8.3f} {m.calmar:>8.3f} {stress_txt:>9} {m.n_trades:>7} ${costs:>9,.0f}"
        )
    print("=" * 112)
    print(f"  Stress window: {args.stress_start} -> {args.stress_end}")
    print(f"  Summary: {summary_path}")
    print("  Verdict: research output only; do not wire into Fund v1 from this script.\n")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Standalone SPY/QQQ equity sleeve research runner")
    p.add_argument("--spy-data", default=None)
    p.add_argument("--qqq-data", default=None)
    p.add_argument("--assets", nargs="+", choices=["SPY", "QQQ"], default=["SPY", "QQQ"])
    p.add_argument("--strategy-profile", choices=["sma_band", "qqq_growth", "all"], default="sma_band")
    p.add_argument("--capital", type=float, default=25_000.0)
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--stress-start", default="2022-01-01")
    p.add_argument("--stress-end", default="2022-12-31")
    p.add_argument("--out-dir", default="artifacts/equity_sleeve_research")
    p.add_argument("--no-chart", action="store_true")
    p.add_argument("--include-benchmarks", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--fee", type=float, default=None)
    p.add_argument("--base-slippage", type=float, default=None)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    exec_config = EQUITY_EXEC
    if args.fee is not None:
        exec_config.taker_fee_rate = args.fee
    if args.base_slippage is not None:
        exec_config.base_slippage_bps = args.base_slippage

    print("\nEquity Sleeve Research Runner")
    print("Role: Layer 2 standalone strategy / sleeve research")
    print("Runtime impact: none")
    print("Fund v1 impact: none")
    print(f"Benchmarks included: {args.include_benchmarks}\n")

    outputs = [_run(spec, args, exec_config) for spec in _build_specs(args)]
    summary_path = _write_summary(outputs, Path(args.out_dir), args)
    _print(outputs, summary_path, args)


if __name__ == "__main__":
    main()
