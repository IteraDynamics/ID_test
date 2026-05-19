#!/usr/bin/env python
"""Research-only SPY risk-off capital destination runner.

This is the equity pivot test: SPY is not treated as a permanent alpha sleeve.
Instead, it is tested as a destination for capital reduced from Fund v1 during
crypto drawdown/risk-off states.

Variants
--------
- baseline: full Fund v1 crypto portfolio.
- risk_off_cash: reduce crypto exposure during risk-off; parked capital earns 0%.
- risk_off_spy_bh: reduced capital goes to SPY buy-and-hold exposure.
- risk_off_spy_sma: reduced capital goes to SPY SMA sleeve exposure.

The risk-off state is computed from the prior day's Fund v1 drawdown to avoid
same-bar lookahead. This script is research-only and does not modify runtime,
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
log = logging.getLogger("spy_risk_off_destination")

FUND_V1_STRATEGY = "trend_following_v8_ecap60_add80"
SPY_SMA_STRATEGY = "equity_spy_sma_band_v1"
FULL_CAPITAL = 100_000.0

CRYPTO_EXEC = ExecutionConfig.from_env()
SPY_EXEC = ExecutionConfig(
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
    strategy_name: str
    result: BacktestResult
    metrics: BacktestMetrics


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
    out.name = "fund_v1_baseline"
    return out


def _buy_hold_curve(df: pd.DataFrame, capital: float) -> pd.Series:
    close = pd.to_numeric(df["close"], errors="coerce").dropna()
    out = capital * (close / float(close.iloc[0]))
    out.name = "spy_buy_and_hold"
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


def _yearly_returns(equity: pd.Series) -> dict[str, float]:
    out: dict[str, float] = {}
    clean = equity.dropna()
    for year, group in clean.groupby(clean.index.year):
        if len(group) < 2:
            continue
        out[str(year)] = round((float(group.iloc[-1]) / float(group.iloc[0]) - 1.0) * 100.0, 4)
    return out


def _build_cached(args: argparse.Namespace) -> tuple[dict[str, SleeveRun], pd.Series, pd.Series]:
    btc_1h = _load(args.btc_data, "BTC", args.start, args.end)
    eth_1h = _load(args.eth_data, "ETH", args.start, args.end)
    spy_1d = _load(args.spy_data, "SPY", args.start, args.end)

    cached = {
        "BTC_1H": _run_sleeve("BTC_1H", "BTC", btc_1h, FUND_V1_STRATEGY, CRYPTO_EXEC),
        "BTC_4H": _run_sleeve("BTC_4H", "BTC", resample_ohlcv(btc_1h, "4h"), FUND_V1_STRATEGY, CRYPTO_EXEC),
        "ETH_1H": _run_sleeve("ETH_1H", "ETH", eth_1h, FUND_V1_STRATEGY, CRYPTO_EXEC),
        "ETH_4H": _run_sleeve("ETH_4H", "ETH", resample_ohlcv(eth_1h, "4h"), FUND_V1_STRATEGY, CRYPTO_EXEC),
        "SPY_SMA": _run_sleeve("SPY_SMA", "SPY", spy_1d, SPY_SMA_STRATEGY, SPY_EXEC),
    }
    spy_bh = _buy_hold_curve(spy_1d, FULL_CAPITAL)
    return cached, spy_bh, spy_1d["close"]


def _row(label: str, equity: pd.Series, metrics: BacktestMetrics, args: argparse.Namespace, baseline: pd.Series, risk_off: pd.Series) -> dict[str, Any]:
    joined = pd.concat([baseline.pct_change(fill_method=None), equity.pct_change(fill_method=None)], axis=1).dropna()
    corr = round(float(joined.iloc[:, 0].corr(joined.iloc[:, 1])), 4) if len(joined) > 2 else None
    active_days = int(risk_off.loc[equity.index].sum()) if set(equity.index).issubset(set(risk_off.index)) else int(risk_off.sum())
    return {
        "label": label,
        "cagr_pct": metrics.cagr_pct,
        "max_drawdown_pct": metrics.max_drawdown_pct,
        "sharpe": metrics.sharpe,
        "calmar": metrics.calmar,
        "stress_return_pct": _slice_return(equity, args.stress_start, args.stress_end),
        "corr_to_baseline": corr,
        "risk_off_days": active_days,
        "risk_off_pct_days": round(active_days / max(len(equity), 1) * 100.0, 2),
        "yearly_returns_pct": _yearly_returns(equity),
    }


def _write_outputs(rows: list[dict[str, Any]], curves: dict[str, pd.Series], risk_off: pd.Series, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    flat_rows = [{**r, "yearly_returns_pct": json.dumps(r["yearly_returns_pct"], sort_keys=True)} for r in rows]
    pd.DataFrame(flat_rows).to_csv(out_dir / "summary.csv", index=False)
    pd.DataFrame(curves).dropna(how="all").to_csv(out_dir / "equity_curves.csv")
    risk_off.astype(int).to_csv(out_dir / "risk_off_state.csv", header=True)
    with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, default=str)

    md = out_dir / "summary.md"
    with open(md, "w", encoding="utf-8") as f:
        f.write("# SPY Risk-Off Destination Research Summary\n\n")
        f.write("Research-only Layer 3 capital destination test.\n\n")
        f.write("| Label | CAGR | MaxDD | Sharpe | Calmar | Stress | Risk-Off Days | Corr vs Base |\n")
        f.write("|---|---:|---:|---:|---:|---:|---:|---:|\n")
        for r in rows:
            stress = "n/a" if r["stress_return_pct"] is None else f"{r['stress_return_pct']:.2f}%"
            corr = "n/a" if r["corr_to_baseline"] is None else f"{r['corr_to_baseline']:.3f}"
            f.write(f"| {r['label']} | {r['cagr_pct']:.2f}% | {r['max_drawdown_pct']:.2f}% | {r['sharpe']:.3f} | {r['calmar']:.3f} | {stress} | {r['risk_off_days']} ({r['risk_off_pct_days']:.1f}%) | {corr} |\n")

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
    return md


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Research-only SPY risk-off destination runner")
    p.add_argument("--btc-data", required=True)
    p.add_argument("--eth-data", required=True)
    p.add_argument("--spy-data", required=True)
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--trigger-dd", type=float, default=-0.20, help="Risk-off trigger drawdown, e.g. -0.20")
    p.add_argument("--release-dd", type=float, default=-0.10, help="Risk-off release drawdown, e.g. -0.10")
    p.add_argument("--crypto-scale", type=float, default=0.75, help="Crypto weight during risk-off")
    p.add_argument("--stress-start", default="2022-01-01")
    p.add_argument("--stress-end", default="2022-12-31")
    p.add_argument("--out-dir", default="artifacts/spy_risk_off_destination_research")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    print("\nSPY Risk-Off Destination Research Runner")
    print("Role: Layer 3 capital destination research")
    print("Runtime impact: none")
    print("Fund v1 paper-trading impact: none")
    print(f"Risk-off rule: prior-day Fund v1 drawdown <= {args.trigger_dd:.0%}; release >= {args.release_dd:.0%}")
    print(f"Risk-off crypto scale: {args.crypto_scale:.0%}; destination scale: {1 - args.crypto_scale:.0%}\n")

    cached, spy_bh, _ = _build_cached(args)
    baseline = _build_fund_v1_curve(cached, args.capital)
    risk_off = _risk_off_state(baseline, args.trigger_dd, args.release_dd)
    spy_sma = _daily_equity(cached["SPY_SMA"].result.equity_curve)

    curves = {
        "baseline": baseline,
        "risk_off_cash": _overlay_curve(baseline, None, risk_off, args.crypto_scale, args.capital, "risk_off_cash"),
        "risk_off_spy_bh": _overlay_curve(baseline, spy_bh, risk_off, args.crypto_scale, args.capital, "risk_off_spy_bh"),
        "risk_off_spy_sma": _overlay_curve(baseline, spy_sma, risk_off, args.crypto_scale, args.capital, "risk_off_spy_sma"),
    }

    rows: list[dict[str, Any]] = []
    for label, curve in curves.items():
        metrics = compute_metrics(curve, trades=[], params={"strategy_id": label, "asset": "PORTFOLIO", "initial_capital": args.capital})
        rows.append(_row(label, curve, metrics, args, baseline, risk_off))

    summary = _write_outputs(rows, curves, risk_off, Path(args.out_dir))

    print("=" * 112)
    print("  SPY RISK-OFF DESTINATION — CAPITAL PARKING RESEARCH")
    print("=" * 112)
    print(f"  {'Label':<20} {'CAGR%':>9} {'MaxDD%':>9} {'Sharpe':>8} {'Calmar':>8} {'Stress%':>9} {'RiskOff':>9} {'Corr':>7}")
    print("  " + "-" * 110)
    for r in rows:
        stress = "n/a" if r["stress_return_pct"] is None else f"{r['stress_return_pct']:>8.2f}%"
        corr = "n/a" if r["corr_to_baseline"] is None else f"{r['corr_to_baseline']:>7.3f}"
        risk_txt = f"{r['risk_off_pct_days']:.1f}%"
        print(f"  {r['label']:<20} {r['cagr_pct']:>8.2f}% {r['max_drawdown_pct']:>8.2f}% {r['sharpe']:>8.3f} {r['calmar']:>8.3f} {stress:>9} {risk_txt:>9} {corr:>7}")
    print("=" * 112)
    print(f"  Summary: {summary}")
    print("  Verdict: research output only; review before any integration.\n")


if __name__ == "__main__":
    main()
