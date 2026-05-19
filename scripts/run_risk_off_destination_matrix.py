#!/usr/bin/env python
"""Research-only risk-off destination matrix runner.

Tests a flexible set of capital destinations during Fund v1 crypto risk-off
states. Destinations are treated as buy-and-hold return streams during the
risk-off window and are compared against cash.

This is Layer 3 capital destination research. It does not modify runtime,
paper trading, brokers, allocators, governors, or Fund v1 behavior.
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
log = logging.getLogger("risk_off_destination_matrix")

FUND_V1_STRATEGY = "trend_following_v8_ecap60_add80"
FULL_CAPITAL = 100_000.0
CRYPTO_EXEC = ExecutionConfig.from_env()


@dataclass(frozen=True)
class SleeveRun:
    label: str
    asset: str
    strategy_name: str
    result: BacktestResult
    metrics: BacktestMetrics


@dataclass(frozen=True)
class DestinationSpec:
    ticker: str
    path: str


def _parse_destinations(raw: list[str]) -> list[DestinationSpec]:
    specs: list[DestinationSpec] = []
    seen: set[str] = set()
    for item in raw:
        if "=" not in item:
            raise ValueError(f"Destination must be TICKER=path, got {item!r}")
        ticker, path = item.split("=", 1)
        ticker = ticker.strip().upper()
        path = path.strip()
        if not ticker or not path:
            raise ValueError(f"Destination must be TICKER=path, got {item!r}")
        if ticker in seen:
            raise ValueError(f"Duplicate destination ticker: {ticker}")
        seen.add(ticker)
        specs.append(DestinationSpec(ticker=ticker, path=path))
    return specs


def _load(path: str, asset: str, start: str | None, end: str | None) -> pd.DataFrame:
    df = load_ohlcv(path, start=start, end=end, asset=asset)
    for warning in validate_ohlcv(df):
        log.warning("Data warning [%s]: %s", asset, warning)
    return df


def _run_sleeve(label: str, asset: str, df: pd.DataFrame, strategy_name: str, exec_config: ExecutionConfig) -> SleeveRun:
    strategy = STRATEGY_REGISTRY[strategy_name]
    log.info("Running cached sleeve %s — $%.0f on %d bars", label, FULL_CAPITAL, len(df))
    result = run_backtest(df=df, strategy_module=strategy, asset=asset, initial_capital=FULL_CAPITAL, exec_config=exec_config)
    metrics = compute_metrics(result.equity_curve, result.trades, {"strategy_id": strategy_name, "asset": asset, "initial_capital": FULL_CAPITAL})
    return SleeveRun(label=label, asset=asset, strategy_name=strategy_name, result=result, metrics=metrics)


def _daily_equity(series: pd.Series) -> pd.Series:
    return series.resample("1D").last().ffill().dropna()


def _build_fund_v1_curve(cached: dict[str, SleeveRun], capital: float) -> pd.Series:
    curves = {}
    for label in ("BTC_1H", "BTC_4H", "ETH_1H", "ETH_4H"):
        base = _daily_equity(cached[label].result.equity_curve)
        curves[label] = (base / float(base.iloc[0])) * (capital / 4.0)
    daily = pd.DataFrame(curves).dropna(how="any")
    out = daily.sum(axis=1)
    out.name = "baseline"
    return out


def _save_baseline_cache(baseline: pd.Series, path: str | None) -> None:
    if not path:
        return
    cache_path = Path(path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    baseline.to_frame("baseline").to_csv(cache_path)
    log.info("Saved baseline cache: %s", cache_path)


def _load_baseline_cache(path: str) -> pd.Series:
    cache_path = Path(path)
    if not cache_path.exists():
        raise FileNotFoundError(f"Baseline cache not found: {cache_path}")
    df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
    if "baseline" not in df.columns:
        raise ValueError(f"Baseline cache must include a 'baseline' column: {cache_path}")
    baseline = pd.to_numeric(df["baseline"], errors="coerce").dropna()
    baseline.name = "baseline"
    if len(baseline) < 2:
        raise ValueError(f"Baseline cache has insufficient rows: {cache_path}")
    log.info("Loaded baseline cache: %s (%d rows)", cache_path, len(baseline))
    return baseline


def _buy_hold_curve(df: pd.DataFrame, capital: float, label: str) -> pd.Series:
    close = pd.to_numeric(df["close"], errors="coerce").dropna()
    out = capital * (close / float(close.iloc[0]))
    out.name = label
    return out


def _normalized_returns(equity: pd.Series) -> pd.Series:
    return equity.pct_change(fill_method=None).fillna(0.0)


def _risk_off_state(baseline: pd.Series, trigger_dd: float, release_dd: float) -> pd.Series:
    dd = baseline / baseline.cummax() - 1.0
    prior_dd = dd.shift(1).fillna(0.0)
    active = False
    states = []
    for value in prior_dd:
        if not active and value <= trigger_dd:
            active = True
        elif active and value >= release_dd:
            active = False
        states.append(active)
    return pd.Series(states, index=baseline.index, name="risk_off")


def _overlay_curve(
    baseline: pd.Series,
    destination: pd.Series | None,
    risk_off: pd.Series,
    crypto_scale: float,
    capital: float,
    label: str,
) -> pd.Series:
    aligned = pd.DataFrame({"baseline": baseline, "risk_off": risk_off.astype(float)})
    if destination is not None:
        aligned["destination"] = destination
    aligned = aligned.dropna(how="any")

    crypto_ret = _normalized_returns(aligned["baseline"])
    if destination is None:
        dest_ret = pd.Series(0.0, index=aligned.index)
    else:
        dest_ret = _normalized_returns(aligned["destination"])

    active = aligned["risk_off"].astype(bool)
    weight_crypto = pd.Series(1.0, index=aligned.index)
    weight_dest = pd.Series(0.0, index=aligned.index)
    weight_crypto.loc[active] = crypto_scale
    weight_dest.loc[active] = 1.0 - crypto_scale

    portfolio_ret = weight_crypto * crypto_ret + weight_dest * dest_ret
    equity = capital * (1.0 + portfolio_ret).cumprod()
    equity.name = label
    return equity


def _slice_return(equity: pd.Series, start: str, end: str) -> float | None:
    s = equity.loc[(equity.index >= pd.Timestamp(start)) & (equity.index <= pd.Timestamp(end))].dropna()
    if len(s) < 2:
        return None
    return round((float(s.iloc[-1]) / float(s.iloc[0]) - 1.0) * 100.0, 4)


def _risk_off_destination_return(destination: pd.Series | None, risk_off: pd.Series) -> float | None:
    if destination is None:
        return 0.0
    aligned = pd.DataFrame({"destination": destination, "risk_off": risk_off.astype(bool)}).dropna(how="any")
    active = aligned[aligned["risk_off"]]
    if len(active) < 2:
        return None
    ret = _normalized_returns(aligned["destination"])
    active_rets = ret.loc[active.index]
    return round(((1.0 + active_rets).prod() - 1.0) * 100.0, 4)


def _yearly_returns(equity: pd.Series) -> dict[str, float]:
    out: dict[str, float] = {}
    clean = equity.dropna()
    for year, group in clean.groupby(clean.index.year):
        if len(group) < 2:
            continue
        out[str(year)] = round((float(group.iloc[-1]) / float(group.iloc[0]) - 1.0) * 100.0, 4)
    return out


def _build_cached_crypto(args: argparse.Namespace) -> dict[str, SleeveRun]:
    btc_1h = _load(args.btc_data, "BTC", args.start, args.end)
    eth_1h = _load(args.eth_data, "ETH", args.start, args.end)
    return {
        "BTC_1H": _run_sleeve("BTC_1H", "BTC", btc_1h, FUND_V1_STRATEGY, CRYPTO_EXEC),
        "BTC_4H": _run_sleeve("BTC_4H", "BTC", resample_ohlcv(btc_1h, "4h"), FUND_V1_STRATEGY, CRYPTO_EXEC),
        "ETH_1H": _run_sleeve("ETH_1H", "ETH", eth_1h, FUND_V1_STRATEGY, CRYPTO_EXEC),
        "ETH_4H": _run_sleeve("ETH_4H", "ETH", resample_ohlcv(eth_1h, "4h"), FUND_V1_STRATEGY, CRYPTO_EXEC),
    }


def _get_baseline(args: argparse.Namespace) -> pd.Series:
    if args.load_baseline_cache:
        return _load_baseline_cache(args.load_baseline_cache)
    cached = _build_cached_crypto(args)
    baseline = _build_fund_v1_curve(cached, args.capital)
    _save_baseline_cache(baseline, args.save_baseline_cache)
    return baseline


def _load_destination_curves(specs: list[DestinationSpec], args: argparse.Namespace) -> dict[str, pd.Series]:
    curves: dict[str, pd.Series] = {}
    for spec in specs:
        df = _load(spec.path, spec.ticker, args.start, args.end)
        curves[spec.ticker] = _buy_hold_curve(df, FULL_CAPITAL, spec.ticker)
    return curves


def _row(
    label: str,
    equity: pd.Series,
    destination: pd.Series | None,
    metrics: BacktestMetrics,
    args: argparse.Namespace,
    baseline: pd.Series,
    risk_off: pd.Series,
    cash_metrics: BacktestMetrics | None,
) -> dict[str, Any]:
    joined = pd.concat([baseline.pct_change(fill_method=None), equity.pct_change(fill_method=None)], axis=1).dropna()
    corr = round(float(joined.iloc[:, 0].corr(joined.iloc[:, 1])), 4) if len(joined) > 2 else None
    active_days = int(risk_off.loc[equity.index].sum()) if set(equity.index).issubset(set(risk_off.index)) else int(risk_off.sum())
    row = {
        "label": label,
        "cagr_pct": metrics.cagr_pct,
        "max_drawdown_pct": metrics.max_drawdown_pct,
        "sharpe": metrics.sharpe,
        "calmar": metrics.calmar,
        "stress_return_pct": _slice_return(equity, args.stress_start, args.stress_end),
        "corr_to_baseline": corr,
        "risk_off_days": active_days,
        "risk_off_pct_days": round(active_days / max(len(equity), 1) * 100.0, 2),
        "destination_risk_off_return_pct": _risk_off_destination_return(destination, risk_off),
        "yearly_returns_pct": _yearly_returns(equity),
    }
    if cash_metrics is not None:
        row.update(
            {
                "delta_cagr_vs_cash": metrics.cagr_pct - cash_metrics.cagr_pct,
                "delta_maxdd_vs_cash": metrics.max_drawdown_pct - cash_metrics.max_drawdown_pct,
                "delta_sharpe_vs_cash": metrics.sharpe - cash_metrics.sharpe,
                "delta_calmar_vs_cash": metrics.calmar - cash_metrics.calmar,
            }
        )
    else:
        row.update(
            {
                "delta_cagr_vs_cash": None,
                "delta_maxdd_vs_cash": None,
                "delta_sharpe_vs_cash": None,
                "delta_calmar_vs_cash": None,
            }
        )
    return row


def _sort_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    baseline = [r for r in rows if r["label"] == "baseline"]
    others = [r for r in rows if r["label"] != "baseline"]
    others.sort(key=lambda r: (r["calmar"], r["sharpe"], r["max_drawdown_pct"]), reverse=True)
    return baseline + others


def _write_outputs(rows: list[dict[str, Any]], curves: dict[str, pd.Series], risk_off: pd.Series, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = _sort_rows(rows)
    flat_rows = [{**r, "yearly_returns_pct": json.dumps(r["yearly_returns_pct"], sort_keys=True)} for r in rows]
    pd.DataFrame(flat_rows).to_csv(out_dir / "summary.csv", index=False)
    pd.DataFrame(curves).dropna(how="all").to_csv(out_dir / "equity_curves.csv")
    risk_off.astype(int).to_csv(out_dir / "risk_off_state.csv", header=True)
    with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, default=str)

    md = out_dir / "summary.md"
    with open(md, "w", encoding="utf-8") as f:
        f.write("# Risk-Off Destination Matrix\n\n")
        f.write("Research-only Layer 3 capital destination matrix. Destinations are compared against cash during Fund v1 risk-off states.\n\n")
        f.write("| Label | CAGR | MaxDD | Sharpe | Calmar | Stress | Dest Risk-Off Ret | dCalmar vs Cash | Corr vs Base |\n")
        f.write("|---|---:|---:|---:|---:|---:|---:|---:|---:|\n")
        for r in rows:
            stress = "n/a" if r["stress_return_pct"] is None else f"{r['stress_return_pct']:.2f}%"
            dest_ro = "n/a" if r["destination_risk_off_return_pct"] is None else f"{r['destination_risk_off_return_pct']:.2f}%"
            dcalmar = "n/a" if r["delta_calmar_vs_cash"] is None else f"{r['delta_calmar_vs_cash']:.3f}"
            corr = "n/a" if r["corr_to_baseline"] is None else f"{r['corr_to_baseline']:.3f}"
            f.write(f"| {r['label']} | {r['cagr_pct']:.2f}% | {r['max_drawdown_pct']:.2f}% | {r['sharpe']:.3f} | {r['calmar']:.3f} | {stress} | {dest_ro} | {dcalmar} | {corr} |\n")
    return md


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Research-only risk-off destination matrix runner")
    p.add_argument("--btc-data", required=False, help="BTC hourly CSV; required unless --load-baseline-cache is used")
    p.add_argument("--eth-data", required=False, help="ETH hourly CSV; required unless --load-baseline-cache is used")
    p.add_argument("--destination", action="append", default=[], help="Destination in TICKER=path form. Repeatable.")
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--trigger-dd", type=float, default=-0.20)
    p.add_argument("--release-dd", type=float, default=-0.10)
    p.add_argument("--crypto-scale", type=float, default=0.75)
    p.add_argument("--stress-start", default="2022-01-01")
    p.add_argument("--stress-end", default="2022-12-31")
    p.add_argument("--out-dir", default="artifacts/risk_off_destination_matrix")
    p.add_argument("--save-baseline-cache", default="artifacts/risk_off_destination_matrix/baseline_cache.csv")
    p.add_argument("--load-baseline-cache", default=None)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if not args.load_baseline_cache and (not args.btc_data or not args.eth_data):
        raise ValueError("--btc-data and --eth-data are required unless --load-baseline-cache is used")

    destination_specs = _parse_destinations(args.destination)

    print("\nRisk-Off Destination Matrix Runner")
    print("Role: Layer 3 capital destination research")
    print("Runtime impact: none")
    print("Fund v1 paper-trading impact: none")
    print(f"Risk-off rule: prior-day Fund v1 drawdown <= {args.trigger_dd:.0%}; release >= {args.release_dd:.0%}")
    print(f"Risk-off crypto scale: {args.crypto_scale:.0%}; destination scale: {1 - args.crypto_scale:.0%}")
    print(f"Destinations: {', '.join(spec.ticker for spec in destination_specs) if destination_specs else 'cash only'}")
    print(f"Baseline cache load: {args.load_baseline_cache or 'none'}")
    print(f"Baseline cache save: {args.save_baseline_cache if not args.load_baseline_cache else 'disabled because load cache is active'}\n")

    baseline = _get_baseline(args)
    risk_off = _risk_off_state(baseline, args.trigger_dd, args.release_dd)
    destinations = _load_destination_curves(destination_specs, args)

    curves: dict[str, pd.Series] = {"baseline": baseline}
    rows: list[dict[str, Any]] = []

    baseline_metrics = compute_metrics(baseline, trades=[], params={"strategy_id": "baseline", "asset": "PORTFOLIO", "initial_capital": args.capital})
    rows.append(_row("baseline", baseline, None, baseline_metrics, args, baseline, risk_off, None))

    cash_curve = _overlay_curve(baseline, None, risk_off, args.crypto_scale, args.capital, "cash")
    curves["cash"] = cash_curve
    cash_metrics = compute_metrics(cash_curve, trades=[], params={"strategy_id": "cash", "asset": "PORTFOLIO", "initial_capital": args.capital})
    rows.append(_row("cash", cash_curve, None, cash_metrics, args, baseline, risk_off, None))

    for ticker, destination_curve in destinations.items():
        label = ticker.lower()
        overlay = _overlay_curve(baseline, destination_curve, risk_off, args.crypto_scale, args.capital, label)
        curves[label] = overlay
        metrics = compute_metrics(overlay, trades=[], params={"strategy_id": label, "asset": "PORTFOLIO", "initial_capital": args.capital})
        rows.append(_row(label, overlay, destination_curve, metrics, args, baseline, risk_off, cash_metrics))

    summary = _write_outputs(rows, curves, risk_off, Path(args.out_dir))
    printed = _sort_rows(rows)

    print("=" * 128)
    print("  RISK-OFF DESTINATION MATRIX")
    print("=" * 128)
    print(f"  {'Label':<12} {'CAGR%':>9} {'MaxDD%':>9} {'Sharpe':>8} {'Calmar':>8} {'Stress%':>9} {'DestRO%':>9} {'dCalmar':>9} {'Corr':>7}")
    print("  " + "-" * 126)
    for r in printed:
        stress = "n/a" if r["stress_return_pct"] is None else f"{r['stress_return_pct']:>8.2f}%"
        dest_ro = "n/a" if r["destination_risk_off_return_pct"] is None else f"{r['destination_risk_off_return_pct']:>8.2f}%"
        dcalmar = "n/a" if r["delta_calmar_vs_cash"] is None else f"{r['delta_calmar_vs_cash']:>8.3f}"
        corr = "n/a" if r["corr_to_baseline"] is None else f"{r['corr_to_baseline']:>7.3f}"
        print(f"  {r['label']:<12} {r['cagr_pct']:>8.2f}% {r['max_drawdown_pct']:>8.2f}% {r['sharpe']:>8.3f} {r['calmar']:>8.3f} {stress:>9} {dest_ro:>9} {dcalmar:>9} {corr:>7}")
    print("=" * 128)
    print(f"  Summary: {summary}")
    print("  Verdict: research output only; review before any integration.\n")


if __name__ == "__main__":
    main()
