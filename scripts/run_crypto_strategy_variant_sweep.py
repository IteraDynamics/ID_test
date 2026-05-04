#!/usr/bin/env python
"""Crypto Risk Budget v2 — implementable strategy-variant sweep.

Research-only runner. Compares existing registered TrendFollowing v8 strategy
variants across the BTC/ETH x 1H/4H Fund v1 sleeve structure.

Purpose:
    Test whether actual, implementable strategy variants can approximate the
    1.50x–1.75x hypothetical risk-budget frontier without simply multiplying
    an existing equity curve.

Default cost assumptions reflect observed Coinbase Advanced-style research
hurdles:
    fee                 = 0.0006  (0.06% per side)
    base_slippage       = 3 bps per side
    slippage_vol_factor = 50
    rebalance_threshold = 0.05

No runtime, paper-trading, production allocation, or execution changes are made.
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
log = logging.getLogger("crypto_strategy_variant_sweep")

BASELINE_STRATEGY = "trend_following_v8_ecap60_add80"
DEFAULT_VARIANTS = [
    "trend_following_v8_ecap50_add70",
    "trend_following_v8_ecap50",
    "trend_following_v8_ecap60",
    "trend_following_v8_ecap60_add80",
    "trend_following_v8_ecap75",
    "trend_following_v8_ecap75_add90",
    "trend_following_v8_cap50",
    "trend_following_v8_cap60",
    "trend_following_v8_cap75",
    "trend_following_v8",
]


@dataclass(frozen=True)
class SleeveConfig:
    label: str
    asset: str
    timeframe: str
    data_path: str
    calibrated: bool = False


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run Fund v1 crypto strategy variant sweep",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--btc-data", required=True, help="Path to BTC/USD 1H OHLCV CSV")
    p.add_argument("--eth-data", required=True, help="Path to ETH/USD 1H OHLCV CSV")
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--calibrate", action="store_true")
    p.add_argument("--calibrators-dir", default=None)
    p.add_argument(
        "--strategies",
        default=",".join(DEFAULT_VARIANTS),
        help="Comma-separated registered strategy IDs to test",
    )
    p.add_argument("--baseline", default=BASELINE_STRATEGY)
    p.add_argument("--fee", type=float, default=0.0006)
    p.add_argument("--base-slippage", type=float, default=3.0)
    p.add_argument("--slippage-vol-factor", type=float, default=50.0)
    p.add_argument("--cooldown", type=int, default=None)
    p.add_argument("--rebalance-threshold", type=float, default=0.05)
    p.add_argument("--out-dir", default="artifacts/crypto_risk_budget_v2_strategy_variant_sweep")
    return p.parse_args()


def _parse_strategies(text: str) -> list[str]:
    strategies = [x.strip() for x in text.split(",") if x.strip()]
    if not strategies:
        raise ValueError("At least one strategy must be provided")
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
            log.info(
                "Resampled %s to 4H: %d bars  %s → %s",
                sleeve.asset,
                len(df),
                df.index[0],
                df.index[-1],
            )
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


def _fund_equity(results: dict[str, BacktestResult], capital: float, label: str) -> pd.Series:
    curves = {name: res.equity_curve for name, res in results.items()}
    aligned = align_equity_curves(curves, base_freq="1h")
    returns = aligned.pct_change().fillna(0.0)
    equity = capital * (1.0 + returns.mean(axis=1)).cumprod()
    equity.name = label
    return equity


def _perf(eq: pd.Series, label: str) -> dict[str, Any]:
    eq = eq.dropna().astype(float)
    if len(eq) < 2:
        return {
            "label": label,
            "total_return_pct": 0.0,
            "cagr_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "sharpe": 0.0,
            "calmar": 0.0,
            "ann_vol_pct": 0.0,
            "worst_90d_return_pct": 0.0,
            "worst_180d_return_pct": 0.0,
        }
    delta_s = (eq.index[-1] - eq.index[0]).total_seconds()
    n_gaps = len(eq) - 1
    bar_sec = delta_s / n_gaps if n_gaps > 0 and delta_s > 0 else 3600.0
    bars_per_year = 365.25 * 24 * 3600 / bar_sec
    years = max(delta_s / (365.25 * 24 * 3600), 1e-9)
    total_return = float(eq.iloc[-1] / eq.iloc[0] - 1.0)
    cagr = float((eq.iloc[-1] / eq.iloc[0]) ** (1.0 / years) - 1.0)
    dd = eq / eq.cummax() - 1.0
    max_dd = float(dd.min())
    rets = eq.pct_change().dropna()
    std = float(rets.std(ddof=0)) if len(rets) else 0.0
    sharpe = float((rets.mean() / std) * np.sqrt(bars_per_year)) if std > 1e-12 else 0.0
    ann_vol = float(std * np.sqrt(bars_per_year)) if std > 0 else 0.0
    calmar = cagr / abs(max_dd) if max_dd < 0 else 0.0
    daily = eq.resample("1D").last().dropna()
    worst_90 = float(daily.pct_change(90).dropna().min()) if len(daily) > 90 else 0.0
    worst_180 = float(daily.pct_change(180).dropna().min()) if len(daily) > 180 else 0.0
    return {
        "label": label,
        "total_return_pct": total_return * 100.0,
        "cagr_pct": cagr * 100.0,
        "max_drawdown_pct": max_dd * 100.0,
        "sharpe": sharpe,
        "calmar": calmar,
        "ann_vol_pct": ann_vol * 100.0,
        "worst_90d_return_pct": worst_90 * 100.0,
        "worst_180d_return_pct": worst_180 * 100.0,
    }


def _trades_summary(results: dict[str, BacktestResult]) -> dict[str, Any]:
    rows = []
    for sleeve, res in results.items():
        trades = getattr(res, "trades", []) or []
        rows.append({"sleeve": sleeve, "trades": len(trades)})
    total = sum(r["trades"] for r in rows)
    return {"total_trades": total, "sleeve_trades": rows}


def _exposure_summary(results: dict[str, BacktestResult]) -> dict[str, Any]:
    rows = []
    for sleeve, res in results.items():
        exposure = getattr(res, "exposure", None)
        if exposure is None:
            # Some BacktestResult versions may not expose an exposure series.
            continue
        s = pd.Series(exposure).dropna().astype(float)
        if s.empty:
            continue
        rows.append({
            "sleeve": sleeve,
            "avg_exposure": float(s.mean()),
            "median_exposure": float(s.median()),
            "max_exposure": float(s.max()),
            "pct_in_market": float((s > 0.05).mean() * 100.0),
        })
    if not rows:
        return {"available": False, "sleeves": []}
    return {"available": True, "sleeves": rows}


def _format_md_value(value: object, floatfmt: str = ".4f") -> str:
    if isinstance(value, float):
        return format(value, floatfmt)
    if pd.isna(value):
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


def _to_markdown_table(df: pd.DataFrame, floatfmt: str = ".4f") -> str:
    if df.empty:
        return "_No rows._"
    columns = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(columns) + " |"]
    lines.append("| " + " | ".join(["---"] * len(columns)) + " |")
    for _, row in df.iterrows():
        vals = [_format_md_value(row[c], floatfmt=floatfmt) for c in df.columns]
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def _write_markdown(out_path: Path, summary: pd.DataFrame, target_rows: pd.DataFrame, args: argparse.Namespace) -> None:
    lines = [
        "# Crypto Risk Budget v2 — Strategy Variant Sweep",
        "",
        "## Status",
        "",
        "Research-only. No runtime or paper-trading changes approved.",
        "",
        "## Cost Assumptions",
        "",
        "```text",
        f"fee = {args.fee}",
        f"base_slippage_bps = {args.base_slippage}",
        f"slippage_vol_factor = {args.slippage_vol_factor}",
        f"rebalance_threshold = {args.rebalance_threshold}",
        "```",
        "",
        "## Variant Summary",
        "",
        _to_markdown_table(summary),
        "",
        "## Target Frontier Candidates",
        "",
        _to_markdown_table(target_rows) if not target_rows.empty else "_No rows met target filters._",
        "",
        "## Guardrail",
        "",
        "```text",
        "These are implementable strategy variants in the research harness, but no live exposure change is approved.",
        "Candidates must still pass additional turnover, slippage, robustness, and live-readiness checks.",
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

    raw_data = _load_data(args)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    equity_curves: dict[str, pd.Series] = {}
    rows: list[dict[str, Any]] = []
    detail_payload: dict[str, Any] = {}

    print("\n" + "=" * 132)
    print("  CRYPTO RISK BUDGET V2 — IMPLEMENTABLE STRATEGY VARIANT SWEEP")
    print(f"  Strategies: {', '.join(strategies)}")
    print(f"  Costs: fee={args.fee * 10000:.1f}bps | base_slippage={args.base_slippage:.1f}bps | vol_factor={args.slippage_vol_factor:.1f} | rebalance_threshold={args.rebalance_threshold:.2f}")
    print("=" * 132)

    for strategy_name in strategies:
        log.info("=== Running strategy variant: %s ===", strategy_name)
        strategy_module = STRATEGY_REGISTRY[strategy_name]
        calibrators = _load_calibrators(strategy_name, args.calibrate, args.calibrators_dir)
        sleeves = _build_sleeves(args, bool(args.calibrate and calibrators))
        results = _run_sleeves(
            sleeves=sleeves,
            raw_data=raw_data,
            strategy_module=strategy_module,
            capital=args.capital,
            exec_config=exec_config,
            rebalance_threshold=args.rebalance_threshold,
            calibrators=calibrators,
        )
        eq = _fund_equity(results, args.capital, strategy_name)
        equity_curves[strategy_name] = eq
        perf = _perf(eq, strategy_name)
        trades = _trades_summary(results)
        exposure = _exposure_summary(results)
        row = {"strategy": strategy_name, **perf, **{"total_trades": trades["total_trades"]}}
        rows.append(row)
        detail_payload[strategy_name] = {
            "performance": perf,
            "trades": trades,
            "exposure": exposure,
        }

    summary = pd.DataFrame(rows)
    if args.baseline in summary["strategy"].values:
        base = summary.loc[summary["strategy"] == args.baseline].iloc[0]
        for col in ["total_return_pct", "cagr_pct", "max_drawdown_pct", "sharpe", "calmar", "ann_vol_pct", "total_trades"]:
            summary[f"delta_{col}_vs_baseline"] = summary[col] - float(base[col])

    target_rows = summary[
        (summary["cagr_pct"] >= 25.0)
        & (summary["max_drawdown_pct"] >= -35.0)
        & (summary["sharpe"] >= 1.0)
        & (summary["calmar"] >= 0.9)
    ].copy()
    target_rows = target_rows.sort_values(["calmar", "cagr_pct"], ascending=[False, False])
    summary = summary.sort_values(["calmar", "cagr_pct"], ascending=[False, False])

    aligned_equity = pd.DataFrame(equity_curves).sort_index()
    aligned_equity.to_csv(out_dir / "variant_equity_curves.csv")
    summary.to_csv(out_dir / "variant_summary.csv", index=False)
    target_rows.to_csv(out_dir / "target_frontier_candidates.csv", index=False)

    payload = {
        "research_status": "research_only_strategy_variant_sweep",
        "baseline": args.baseline,
        "strategies": strategies,
        "cost_assumptions": {
            "fee": args.fee,
            "base_slippage_bps": args.base_slippage,
            "slippage_vol_factor": args.slippage_vol_factor,
            "rebalance_threshold": args.rebalance_threshold,
        },
        "inputs": {
            "btc_data": args.btc_data,
            "eth_data": args.eth_data,
            "capital": args.capital,
            "start": args.start,
            "end": args.end,
            "calibrate": args.calibrate,
        },
        "artifacts": {
            "variant_summary": str(out_dir / "variant_summary.csv"),
            "target_frontier_candidates": str(out_dir / "target_frontier_candidates.csv"),
            "variant_equity_curves": str(out_dir / "variant_equity_curves.csv"),
            "summary_json": str(out_dir / "summary.json"),
            "summary_md": str(out_dir / "summary.md"),
        },
        "details": detail_payload,
        "decision": {
            "status": "diagnostic_only",
            "not_approved": [
                "runtime_change",
                "paper_trading_change",
                "higher_live_exposure",
                "leverage",
                "order_routing_change",
            ],
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    _write_markdown(out_dir / "summary.md", summary, target_rows, args)

    display_cols = [
        "strategy",
        "total_return_pct",
        "cagr_pct",
        "max_drawdown_pct",
        "sharpe",
        "calmar",
        "ann_vol_pct",
        "worst_90d_return_pct",
        "worst_180d_return_pct",
        "total_trades",
    ]
    delta_cols = [c for c in summary.columns if c.startswith("delta_")]
    with pd.option_context("display.max_columns", None, "display.width", 260, "display.float_format", "{:.4f}".format):
        print("\nVariant Summary — ranked by Calmar / CAGR:")
        print(summary[display_cols + delta_cols].to_string(index=False))
        print("\nTarget Frontier Candidates:")
        if target_rows.empty:
            print("No rows met target filters.")
        else:
            print(target_rows[display_cols + delta_cols].to_string(index=False))
    print(f"\nArtifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()
