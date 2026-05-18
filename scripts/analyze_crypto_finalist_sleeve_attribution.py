#!/usr/bin/env python
"""Crypto Risk Budget v2 — finalist sleeve-level attribution.

Research-only analyzer. Re-runs selected crypto finalist strategies across the
BTC/ETH x 1H/4H Fund v1 sleeve structure and attributes performance, drawdown,
turnover, costs, and exposure by sleeve.

Primary use case:
    Compare trend_following_v8_ecap75 vs trend_following_v8_cap75 to determine
    where cap75's extra return, drawdown, and turnover come from.

No runtime, paper-trading, production allocation, or execution changes are made.
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

from dotenv import load_dotenv
load_dotenv()

import numpy as np
import pandas as pd

from research.harness.backtest_engine import BacktestResult, run_backtest
from research.harness.data_loader import load_ohlcv, validate_ohlcv
from research.harness.execution_model import ExecutionConfig
from research.harness.resampler import align_equity_curves, resample_ohlcv
from research.strategies import REGISTRY as STRATEGY_REGISTRY

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("crypto_finalist_sleeve_attribution")

DEFAULT_STRATEGIES = ["trend_following_v8_ecap75", "trend_following_v8_cap75"]
DEFAULT_BASELINE = "trend_following_v8_ecap75"


@dataclass(frozen=True)
class SleeveConfig:
    label: str
    asset: str
    timeframe: str
    data_path: str
    calibrated: bool = False


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run crypto finalist sleeve-level attribution",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--btc-data", required=True, help="Path to BTC/USD 1H OHLCV CSV")
    p.add_argument("--eth-data", required=True, help="Path to ETH/USD 1H OHLCV CSV")
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--calibrate", action="store_true")
    p.add_argument("--calibrators-dir", default=None)
    p.add_argument("--strategies", default=",".join(DEFAULT_STRATEGIES))
    p.add_argument("--baseline", default=DEFAULT_BASELINE)
    p.add_argument("--fee", type=float, default=0.0008)
    p.add_argument("--base-slippage", type=float, default=5.0)
    p.add_argument("--slippage-vol-factor", type=float, default=80.0)
    p.add_argument("--cooldown", type=int, default=2)
    p.add_argument("--rebalance-threshold", type=float, default=0.05)
    p.add_argument("--out-dir", default="artifacts/crypto_risk_budget_v2_finalist_sleeve_attribution")
    return p.parse_args()


def _parse_strategies(text: str) -> list[str]:
    strategies = [s.strip() for s in text.split(",") if s.strip()]
    if not strategies:
        raise ValueError("At least one strategy is required")
    missing = [s for s in strategies if s not in STRATEGY_REGISTRY]
    if missing:
        raise ValueError(f"Unknown strategies: {missing}. Available={sorted(STRATEGY_REGISTRY)}")
    return strategies


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
    except ImportError:
        log.warning("ML calibration not available — running uncalibrated")
    return None


def _load_data(args: argparse.Namespace) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for asset, path in (("BTC", args.btc_data), ("ETH", args.eth_data)):
        log.info("Loading %s data: %s", asset, path)
        df = load_ohlcv(path, start=args.start, end=args.end, asset=asset)
        for warning in validate_ohlcv(df):
            log.warning("Data warning [%s]: %s", asset, warning)
        log.info("Loaded %d bars  %s → %s  [%s]", len(df), df.index[0], df.index[-1], asset)
        out[asset] = df
    return out


def _build_sleeves(args: argparse.Namespace, calibrate: bool) -> list[SleeveConfig]:
    return [
        SleeveConfig("BTC_1H", "BTC", "1H", args.btc_data, calibrate),
        SleeveConfig("BTC_4H", "BTC", "4H", args.btc_data, calibrate),
        SleeveConfig("ETH_1H", "ETH", "1H", args.eth_data, calibrate),
        SleeveConfig("ETH_4H", "ETH", "4H", args.eth_data, calibrate),
    ]


def _run_sleeves(
    sleeves: list[SleeveConfig],
    raw_data: dict[str, pd.DataFrame],
    strategy_module: Any,
    capital: float,
    exec_config: ExecutionConfig,
    rebalance_threshold: float,
    calibrators: dict | None,
) -> dict[str, BacktestResult]:
    results: dict[str, BacktestResult] = {}
    for sleeve in sleeves:
        df = raw_data[sleeve.asset]
        if sleeve.timeframe == "4H":
            df = resample_ohlcv(df, "4h")
            log.info("Resampled %s to 4H: %d bars %s → %s", sleeve.asset, len(df), df.index[0], df.index[-1])
        log.info("Running sleeve %s", sleeve.label)
        results[sleeve.label] = run_backtest(
            df=df,
            strategy_module=strategy_module,
            initial_capital=capital,
            exec_config=exec_config,
            rebalance_threshold=rebalance_threshold,
            asset=sleeve.asset,
            calibrators=calibrators if sleeve.calibrated else None,
        )
    return results


def _bars_per_year(index: pd.DatetimeIndex) -> float:
    if len(index) < 3:
        return 365.25
    deltas = index.to_series().diff().dropna().dt.total_seconds()
    if deltas.empty:
        return 365.25
    med = float(deltas.median())
    if med <= 0:
        return 365.25
    return float(365.25 * 24 * 3600 / med)


def _perf(eq: pd.Series) -> dict[str, float]:
    eq = eq.dropna().astype(float)
    if len(eq) < 2:
        return {
            "total_return_pct": 0.0,
            "cagr_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "sharpe": 0.0,
            "calmar": 0.0,
            "ann_vol_pct": 0.0,
            "worst_90d_return_pct": 0.0,
            "worst_180d_return_pct": 0.0,
            "time_underwater_pct": 0.0,
        }
    years = max((eq.index[-1] - eq.index[0]).total_seconds() / (365.25 * 24 * 3600), 1e-9)
    total_return = float(eq.iloc[-1] / eq.iloc[0] - 1.0)
    cagr = float((eq.iloc[-1] / eq.iloc[0]) ** (1.0 / years) - 1.0)
    dd = eq / eq.cummax() - 1.0
    max_dd = float(dd.min())
    rets = eq.pct_change().dropna()
    std = float(rets.std(ddof=0)) if len(rets) else 0.0
    bpy = _bars_per_year(eq.index)
    sharpe = float((rets.mean() / std) * np.sqrt(bpy)) if std > 1e-12 else 0.0
    ann_vol = float(std * np.sqrt(bpy)) if std > 0 else 0.0
    calmar = float(cagr / abs(max_dd)) if max_dd < 0 else 0.0
    daily = eq.resample("1D").last().dropna()
    worst_90 = float(daily.pct_change(90).dropna().min()) if len(daily) > 90 else 0.0
    worst_180 = float(daily.pct_change(180).dropna().min()) if len(daily) > 180 else 0.0
    return {
        "total_return_pct": total_return * 100.0,
        "cagr_pct": cagr * 100.0,
        "max_drawdown_pct": max_dd * 100.0,
        "sharpe": sharpe,
        "calmar": calmar,
        "ann_vol_pct": ann_vol * 100.0,
        "worst_90d_return_pct": worst_90 * 100.0,
        "worst_180d_return_pct": worst_180 * 100.0,
        "time_underwater_pct": float((dd < 0).mean() * 100.0),
    }


def _trade_costs(result: BacktestResult) -> dict[str, float | int]:
    trades = getattr(result, "trades", []) or []
    if not trades:
        return {
            "trade_count": 0,
            "total_notional_usd": 0.0,
            "total_fee_usd": 0.0,
            "total_slippage_usd": 0.0,
            "total_spread_usd": 0.0,
            "total_cost_usd": 0.0,
            "avg_cost_bps": 0.0,
            "avg_trade_notional_usd": 0.0,
        }
    total_notional = float(sum(float(t.notional_usd) for t in trades))
    total_fee = float(sum(float(t.fee_usd) for t in trades))
    total_slip = float(sum(float(t.slippage_usd) for t in trades))
    total_spread = float(sum(float(t.spread_usd) for t in trades))
    total_cost = total_fee + total_slip + total_spread
    avg_cost_bps = float(np.mean([float(t.cost_bps) for t in trades])) if trades else 0.0
    avg_notional = total_notional / len(trades) if trades else 0.0
    return {
        "trade_count": len(trades),
        "total_notional_usd": total_notional,
        "total_fee_usd": total_fee,
        "total_slippage_usd": total_slip,
        "total_spread_usd": total_spread,
        "total_cost_usd": total_cost,
        "avg_cost_bps": avg_cost_bps,
        "avg_trade_notional_usd": avg_notional,
    }


def _exposure_stats(result: BacktestResult) -> dict[str, float]:
    s = result.position_series.dropna().astype(float)
    if s.empty:
        return {
            "avg_exposure": 0.0,
            "median_exposure": 0.0,
            "max_exposure": 0.0,
            "pct_in_market": 0.0,
            "pct_at_or_above_50": 0.0,
            "pct_at_or_above_75": 0.0,
        }
    return {
        "avg_exposure": float(s.mean()),
        "median_exposure": float(s.median()),
        "max_exposure": float(s.max()),
        "pct_in_market": float((s > 0.05).mean() * 100.0),
        "pct_at_or_above_50": float((s >= 0.50).mean() * 100.0),
        "pct_at_or_above_75": float((s >= 0.75).mean() * 100.0),
    }


def _portfolio_equity(results: dict[str, BacktestResult], capital: float, name: str) -> pd.Series:
    aligned = align_equity_curves({label: r.equity_curve for label, r in results.items()}, base_freq="1h")
    returns = aligned.pct_change().fillna(0.0)
    eq = capital * (1.0 + returns.mean(axis=1)).cumprod()
    eq.name = name
    return eq


def _format_md_value(value: object, floatfmt: str = ".4f") -> str:
    if isinstance(value, float):
        return format(value, floatfmt)
    if pd.isna(value):
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


def _to_markdown_table(df: pd.DataFrame, floatfmt: str = ".4f") -> str:
    if df.empty:
        return "_No rows._"
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |"]
    lines.append("| " + " | ".join(["---"] * len(cols)) + " |")
    for _, row in df.iterrows():
        vals = [_format_md_value(row[c], floatfmt=floatfmt) for c in df.columns]
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def _delta_table(sleeve_summary: pd.DataFrame, baseline: str) -> pd.DataFrame:
    if baseline not in set(sleeve_summary["strategy"]):
        return pd.DataFrame()
    rows = []
    metric_cols = [
        "total_return_pct",
        "cagr_pct",
        "max_drawdown_pct",
        "sharpe",
        "calmar",
        "ann_vol_pct",
        "worst_90d_return_pct",
        "worst_180d_return_pct",
        "trade_count",
        "total_cost_usd",
        "avg_exposure",
        "pct_in_market",
    ]
    for sleeve in sorted(set(sleeve_summary["sleeve"])):
        base_rows = sleeve_summary[(sleeve_summary["strategy"] == baseline) & (sleeve_summary["sleeve"] == sleeve)]
        if base_rows.empty:
            continue
        base = base_rows.iloc[0]
        for _, cand in sleeve_summary[sleeve_summary["sleeve"] == sleeve].iterrows():
            if cand["strategy"] == baseline:
                continue
            row = {"strategy": cand["strategy"], "baseline": baseline, "sleeve": sleeve}
            for col in metric_cols:
                if col in cand.index and col in base.index:
                    row[f"delta_{col}"] = float(cand[col]) - float(base[col])
            rows.append(row)
    return pd.DataFrame(rows)


def _write_markdown(out_path: Path, portfolio_summary: pd.DataFrame, sleeve_summary: pd.DataFrame, deltas: pd.DataFrame, args: argparse.Namespace) -> None:
    display_port_cols = [
        "strategy", "total_return_pct", "cagr_pct", "max_drawdown_pct", "sharpe", "calmar", "ann_vol_pct",
        "worst_90d_return_pct", "worst_180d_return_pct", "trade_count", "total_cost_usd",
    ]
    display_sleeve_cols = [
        "strategy", "sleeve", "total_return_pct", "cagr_pct", "max_drawdown_pct", "sharpe", "calmar", "ann_vol_pct",
        "trade_count", "total_cost_usd", "avg_exposure", "pct_in_market", "pct_at_or_above_75",
    ]
    display_delta_cols = [
        "strategy", "baseline", "sleeve", "delta_cagr_pct", "delta_max_drawdown_pct", "delta_sharpe", "delta_calmar",
        "delta_trade_count", "delta_total_cost_usd", "delta_avg_exposure", "delta_pct_in_market",
    ]
    lines = [
        "# Crypto Risk Budget v2 — Finalist Sleeve Attribution",
        "",
        "Research-only. No runtime or paper-trading changes approved.",
        "",
        "## Cost Assumptions",
        "",
        "```text",
        f"fee = {args.fee}",
        f"base_slippage_bps = {args.base_slippage}",
        f"slippage_vol_factor = {args.slippage_vol_factor}",
        f"cooldown = {args.cooldown}",
        f"rebalance_threshold = {args.rebalance_threshold}",
        "```",
        "",
        "## Portfolio Summary",
        "",
        _to_markdown_table(portfolio_summary[[c for c in display_port_cols if c in portfolio_summary.columns]]),
        "",
        "## Sleeve Summary",
        "",
        _to_markdown_table(sleeve_summary[[c for c in display_sleeve_cols if c in sleeve_summary.columns]]),
        "",
        "## Sleeve Delta vs Baseline",
        "",
        _to_markdown_table(deltas[[c for c in display_delta_cols if c in deltas.columns]]) if not deltas.empty else "_No delta rows._",
        "",
        "## Guardrail",
        "",
        "```text",
        "This attribution identifies sources of return/drawdown/turnover only.",
        "It does not approve strategy promotion, paper-trading changes, live exposure changes, or leverage.",
        "```",
        "",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    strategies = _parse_strategies(args.strategies)
    if args.baseline not in strategies:
        strategies.append(args.baseline)

    exec_config = ExecutionConfig.from_env()
    exec_config.taker_fee_rate = args.fee
    exec_config.base_slippage_bps = args.base_slippage
    exec_config.slippage_vol_factor = args.slippage_vol_factor
    if args.cooldown is not None:
        exec_config.cooldown_bars = args.cooldown

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_data = _load_data(args)

    portfolio_rows: list[dict[str, Any]] = []
    sleeve_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    sleeve_curves: dict[str, pd.Series] = {}
    portfolio_curves: dict[str, pd.Series] = {}

    print("\n=== CRYPTO RISK BUDGET V2 — FINALIST SLEEVE ATTRIBUTION ===")
    print(f"Strategies: {', '.join(strategies)}")
    print(f"Baseline:   {args.baseline}")
    print(f"Costs:      fee={args.fee}, base_slippage={args.base_slippage}, vol_factor={args.slippage_vol_factor}, cooldown={args.cooldown}")

    for strategy_name in strategies:
        log.info("=== Running finalist strategy: %s ===", strategy_name)
        module = STRATEGY_REGISTRY[strategy_name]
        calibrators = _load_calibrators(strategy_name, args.calibrate, args.calibrators_dir)
        sleeves = _build_sleeves(args, bool(args.calibrate and calibrators))
        results = _run_sleeves(
            sleeves=sleeves,
            raw_data=raw_data,
            strategy_module=module,
            capital=args.capital,
            exec_config=exec_config,
            rebalance_threshold=args.rebalance_threshold,
            calibrators=calibrators,
        )

        p_eq = _portfolio_equity(results, args.capital, strategy_name)
        portfolio_curves[strategy_name] = p_eq
        p_costs = {
            "trade_count": int(sum(len(r.trades) for r in results.values())),
            "total_cost_usd": float(sum(_trade_costs(r)["total_cost_usd"] for r in results.values())),
        }
        portfolio_rows.append({"strategy": strategy_name, **_perf(p_eq), **p_costs})

        for sleeve, result in results.items():
            curve_name = f"{strategy_name}__{sleeve}"
            sleeve_curves[curve_name] = result.equity_curve.rename(curve_name)
            costs = _trade_costs(result)
            exposure = _exposure_stats(result)
            sleeve_rows.append({
                "strategy": strategy_name,
                "sleeve": sleeve,
                **_perf(result.equity_curve),
                **costs,
                **exposure,
            })
            for trade in result.trades:
                trade_rows.append({
                    "strategy": strategy_name,
                    "sleeve": sleeve,
                    "timestamp": trade.timestamp,
                    "direction": trade.direction,
                    "notional_usd": trade.notional_usd,
                    "fee_usd": trade.fee_usd,
                    "slippage_usd": trade.slippage_usd,
                    "spread_usd": trade.spread_usd,
                    "cost_bps": trade.cost_bps,
                    "prev_exposure": trade.prev_exposure,
                    "new_exposure": trade.new_exposure,
                    "reason": trade.reason,
                })

    portfolio_summary = pd.DataFrame(portfolio_rows).sort_values(["calmar", "cagr_pct"], ascending=[False, False])
    sleeve_summary = pd.DataFrame(sleeve_rows).sort_values(["sleeve", "strategy"])
    deltas = _delta_table(sleeve_summary, args.baseline)
    trade_log = pd.DataFrame(trade_rows)

    pd.DataFrame(portfolio_curves).sort_index().to_csv(out_dir / "portfolio_equity_curves.csv")
    pd.DataFrame(sleeve_curves).sort_index().to_csv(out_dir / "sleeve_equity_curves.csv")
    portfolio_summary.to_csv(out_dir / "portfolio_summary.csv", index=False)
    sleeve_summary.to_csv(out_dir / "sleeve_summary.csv", index=False)
    deltas.to_csv(out_dir / "sleeve_delta_vs_baseline.csv", index=False)
    trade_log.to_csv(out_dir / "trade_log.csv", index=False)

    payload = {
        "research_status": "research_only_finalist_sleeve_attribution",
        "strategies": strategies,
        "baseline": args.baseline,
        "cost_assumptions": {
            "fee": args.fee,
            "base_slippage_bps": args.base_slippage,
            "slippage_vol_factor": args.slippage_vol_factor,
            "cooldown": args.cooldown,
            "rebalance_threshold": args.rebalance_threshold,
        },
        "inputs": {
            "btc_data": args.btc_data,
            "eth_data": args.eth_data,
            "capital": args.capital,
            "start": args.start,
            "end": args.end,
            "calibrate": args.calibrate,
            "calibrators_dir": args.calibrators_dir,
        },
        "artifacts": {
            "portfolio_summary": str(out_dir / "portfolio_summary.csv"),
            "sleeve_summary": str(out_dir / "sleeve_summary.csv"),
            "sleeve_delta_vs_baseline": str(out_dir / "sleeve_delta_vs_baseline.csv"),
            "portfolio_equity_curves": str(out_dir / "portfolio_equity_curves.csv"),
            "sleeve_equity_curves": str(out_dir / "sleeve_equity_curves.csv"),
            "trade_log": str(out_dir / "trade_log.csv"),
            "summary_json": str(out_dir / "summary.json"),
            "summary_md": str(out_dir / "summary.md"),
        },
        "decision": {
            "status": "diagnostic_only",
            "not_approved": ["runtime_change", "paper_trading_change", "higher_live_exposure", "leverage", "order_routing_change"],
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    _write_markdown(out_dir / "summary.md", portfolio_summary, sleeve_summary, deltas, args)

    port_cols = ["strategy", "total_return_pct", "cagr_pct", "max_drawdown_pct", "sharpe", "calmar", "ann_vol_pct", "trade_count", "total_cost_usd"]
    sleeve_cols = ["strategy", "sleeve", "total_return_pct", "cagr_pct", "max_drawdown_pct", "sharpe", "calmar", "trade_count", "total_cost_usd", "avg_exposure", "pct_in_market"]
    delta_cols = ["strategy", "baseline", "sleeve", "delta_cagr_pct", "delta_max_drawdown_pct", "delta_sharpe", "delta_calmar", "delta_trade_count", "delta_total_cost_usd", "delta_avg_exposure", "delta_pct_in_market"]
    with pd.option_context("display.max_columns", None, "display.width", 260, "display.float_format", "{:.4f}".format):
        print("\nPortfolio Summary:")
        print(portfolio_summary[[c for c in port_cols if c in portfolio_summary.columns]].to_string(index=False))
        print("\nSleeve Summary:")
        print(sleeve_summary[[c for c in sleeve_cols if c in sleeve_summary.columns]].to_string(index=False))
        print("\nSleeve Delta vs Baseline:")
        if deltas.empty:
            print("No delta rows.")
        else:
            print(deltas[[c for c in delta_cols if c in deltas.columns]].to_string(index=False))
    print(f"\nArtifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()
