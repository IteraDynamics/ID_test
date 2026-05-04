#!/usr/bin/env python
"""Crypto Risk Budget v2 — direct hybrid finalist backtest.

Research-only runner. Confirms synthetic hybrid candidates by directly running
sleeve-specific strategy assignments through the existing research harness.

Primary candidates:
    hybrid_eth4h_cap75_only:
        BTC_1H ecap75 / BTC_4H ecap75 / ETH_1H ecap75 / ETH_4H cap75

    hybrid_4h_cap75_1h_ecap75:
        BTC_1H ecap75 / BTC_4H cap75 / ETH_1H ecap75 / ETH_4H cap75

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
log = logging.getLogger("crypto_hybrid_finalist_backtest")

ECAP75 = "trend_following_v8_ecap75"
CAP75 = "trend_following_v8_cap75"
SLEEVES = ["BTC_1H", "BTC_4H", "ETH_1H", "ETH_4H"]


@dataclass(frozen=True)
class SleeveRunConfig:
    label: str
    asset: str
    timeframe: str
    strategy: str


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Directly backtest Crypto Risk Budget v2 hybrid finalists",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--btc-data", required=True)
    p.add_argument("--eth-data", required=True)
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--calibrate", action="store_true")
    p.add_argument("--calibrators-dir", default=None)
    p.add_argument("--fee", type=float, default=0.0008)
    p.add_argument("--base-slippage", type=float, default=5.0)
    p.add_argument("--slippage-vol-factor", type=float, default=80.0)
    p.add_argument("--cooldown", type=int, default=2)
    p.add_argument("--rebalance-threshold", type=float, default=0.05)
    p.add_argument("--out-dir", default="artifacts/crypto_risk_budget_v2_hybrid_direct_confirmation")
    return p.parse_args()


def _candidate_definitions() -> dict[str, dict[str, str]]:
    return {
        "hybrid_eth4h_cap75_only": {
            "BTC_1H": ECAP75,
            "BTC_4H": ECAP75,
            "ETH_1H": ECAP75,
            "ETH_4H": CAP75,
        },
        "hybrid_4h_cap75_1h_ecap75": {
            "BTC_1H": ECAP75,
            "BTC_4H": CAP75,
            "ETH_1H": ECAP75,
            "ETH_4H": CAP75,
        },
        "full_ecap75_reference": {
            "BTC_1H": ECAP75,
            "BTC_4H": ECAP75,
            "ETH_1H": ECAP75,
            "ETH_4H": ECAP75,
        },
        "full_cap75_reference": {
            "BTC_1H": CAP75,
            "BTC_4H": CAP75,
            "ETH_1H": CAP75,
            "ETH_4H": CAP75,
        },
    }


def _load_data(args: argparse.Namespace) -> dict[str, pd.DataFrame]:
    data = {}
    for asset, path in (("BTC", args.btc_data), ("ETH", args.eth_data)):
        log.info("Loading %s data: %s", asset, path)
        df = load_ohlcv(path, start=args.start, end=args.end, asset=asset)
        for warning in validate_ohlcv(df):
            log.warning("Data warning [%s]: %s", asset, warning)
        log.info("Loaded %d bars %s → %s [%s]", len(df), df.index[0], df.index[-1], asset)
        data[asset] = df
    return data


def _load_calibrator(strategy_name: str, calibrate: bool, calibrators_dir: str | None) -> dict | None:
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


def _exec_config(args: argparse.Namespace) -> ExecutionConfig:
    cfg = ExecutionConfig.from_env()
    cfg.taker_fee_rate = args.fee
    cfg.base_slippage_bps = args.base_slippage
    cfg.slippage_vol_factor = args.slippage_vol_factor
    if args.cooldown is not None:
        cfg.cooldown_bars = args.cooldown
    return cfg


def _run_sleeve(
    raw_data: dict[str, pd.DataFrame],
    sleeve: SleeveRunConfig,
    args: argparse.Namespace,
    cfg: ExecutionConfig,
) -> BacktestResult:
    if sleeve.strategy not in STRATEGY_REGISTRY:
        raise ValueError(f"Unknown strategy {sleeve.strategy}; available={sorted(STRATEGY_REGISTRY)}")
    df = raw_data[sleeve.asset]
    if sleeve.timeframe == "4H":
        df = resample_ohlcv(df, "4h")
        log.info("Resampled %s to 4H: %d bars %s → %s", sleeve.asset, len(df), df.index[0], df.index[-1])
    module = STRATEGY_REGISTRY[sleeve.strategy]
    calibrators = _load_calibrator(sleeve.strategy, args.calibrate, args.calibrators_dir)
    log.info("Running %s with %s", sleeve.label, sleeve.strategy)
    return run_backtest(
        df=df,
        strategy_module=module,
        initial_capital=args.capital,
        exec_config=cfg,
        rebalance_threshold=args.rebalance_threshold,
        asset=sleeve.asset,
        calibrators=calibrators,
    )


def _portfolio_equity(results: dict[str, BacktestResult], capital: float, name: str) -> pd.Series:
    aligned = align_equity_curves({label: res.equity_curve for label, res in results.items()}, base_freq="1h")
    returns = aligned.pct_change().fillna(0.0)
    eq = capital * (1.0 + returns.mean(axis=1)).cumprod()
    eq.name = name
    return eq


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


def _max_time_underwater_days(eq: pd.Series) -> float:
    eq = eq.dropna().astype(float)
    dd = eq / eq.cummax() - 1.0
    underwater = dd < 0
    max_days = 0.0
    start = None
    for ts, flag in underwater.items():
        if flag and start is None:
            start = ts
        elif not flag and start is not None:
            max_days = max(max_days, (ts - start).total_seconds() / 86400.0)
            start = None
    if start is not None and len(eq):
        max_days = max(max_days, (eq.index[-1] - start).total_seconds() / 86400.0)
    return float(max_days)


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
            "max_time_underwater_days": 0.0,
        }
    total_return = float(eq.iloc[-1] / eq.iloc[0] - 1.0)
    years = max((eq.index[-1] - eq.index[0]).total_seconds() / (365.25 * 24 * 3600), 1e-9)
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
        "max_time_underwater_days": _max_time_underwater_days(eq),
    }


def _trade_costs(result: BacktestResult) -> dict[str, float | int]:
    trades = result.trades or []
    if not trades:
        return {
            "trade_count": 0,
            "total_notional_usd": 0.0,
            "total_fee_usd": 0.0,
            "total_slippage_usd": 0.0,
            "total_spread_usd": 0.0,
            "total_cost_usd": 0.0,
        }
    return {
        "trade_count": len(trades),
        "total_notional_usd": float(sum(t.notional_usd for t in trades)),
        "total_fee_usd": float(sum(t.fee_usd for t in trades)),
        "total_slippage_usd": float(sum(t.slippage_usd for t in trades)),
        "total_spread_usd": float(sum(t.spread_usd for t in trades)),
        "total_cost_usd": float(sum(t.fee_usd + t.slippage_usd + t.spread_usd for t in trades)),
    }


def _exposure_stats(result: BacktestResult) -> dict[str, float]:
    s = result.position_series.dropna().astype(float)
    if s.empty:
        return {"avg_exposure": 0.0, "pct_in_market": 0.0, "pct_at_or_above_75": 0.0}
    return {
        "avg_exposure": float(s.mean()),
        "pct_in_market": float((s > 0.05).mean() * 100.0),
        "pct_at_or_above_75": float((s >= 0.75).mean() * 100.0),
    }


def _mapping_text(mapping: dict[str, str]) -> str:
    return ", ".join(f"{sleeve}={mapping[sleeve].replace('trend_following_v8_', '')}" for sleeve in SLEEVES)


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


def _write_markdown(out_path: Path, summary: pd.DataFrame, sleeve_summary: pd.DataFrame) -> None:
    summary_cols = [
        "candidate", "total_return_pct", "cagr_pct", "max_drawdown_pct", "sharpe", "calmar", "ann_vol_pct",
        "worst_90d_return_pct", "worst_180d_return_pct", "max_time_underwater_days", "trade_count", "total_cost_usd", "mapping",
    ]
    sleeve_cols = [
        "candidate", "sleeve", "strategy", "total_return_pct", "cagr_pct", "max_drawdown_pct", "sharpe", "calmar",
        "trade_count", "total_cost_usd", "avg_exposure", "pct_in_market", "pct_at_or_above_75",
    ]
    lines = [
        "# Crypto Risk Budget v2 — Direct Hybrid Finalist Confirmation",
        "",
        "Research-only direct hybrid backtest. No runtime or paper-trading changes approved.",
        "",
        "## Candidate Summary",
        "",
        _to_markdown_table(summary[[c for c in summary_cols if c in summary.columns]]),
        "",
        "## Sleeve Summary",
        "",
        _to_markdown_table(sleeve_summary[[c for c in sleeve_cols if c in sleeve_summary.columns]]),
        "",
        "## Guardrail",
        "",
        "```text",
        "This directly confirms hybrid behavior through the research harness, but does not approve promotion.",
        "Any winning candidate still requires research documentation and explicit paper-trading approval before runtime use.",
        "```",
        "",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    data = _load_data(args)
    cfg = _exec_config(args)
    definitions = _candidate_definitions()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    candidate_curves: dict[str, pd.Series] = {}
    sleeve_curves: dict[str, pd.Series] = {}
    summary_rows: list[dict[str, Any]] = []
    sleeve_rows: list[dict[str, Any]] = []

    print("\n=== CRYPTO RISK BUDGET V2 — DIRECT HYBRID FINALIST CONFIRMATION ===")
    print(f"Candidates: {', '.join(definitions)}")
    print(f"Costs: fee={args.fee}, base_slippage={args.base_slippage}, vol_factor={args.slippage_vol_factor}, cooldown={args.cooldown}")

    # Cache identical sleeve runs across candidate definitions.
    result_cache: dict[tuple[str, str], BacktestResult] = {}

    for candidate, mapping in definitions.items():
        log.info("=== Running candidate: %s ===", candidate)
        results: dict[str, BacktestResult] = {}
        for sleeve_label in SLEEVES:
            asset, timeframe = sleeve_label.split("_")
            strategy = mapping[sleeve_label]
            key = (sleeve_label, strategy)
            if key not in result_cache:
                result_cache[key] = _run_sleeve(
                    raw_data=data,
                    sleeve=SleeveRunConfig(label=sleeve_label, asset=asset, timeframe=timeframe, strategy=strategy),
                    args=args,
                    cfg=cfg,
                )
            results[sleeve_label] = result_cache[key]

        portfolio_eq = _portfolio_equity(results, args.capital, candidate)
        candidate_curves[candidate] = portfolio_eq
        p_costs = {
            "trade_count": int(sum(len(r.trades) for r in results.values())),
            "total_cost_usd": float(sum(_trade_costs(r)["total_cost_usd"] for r in results.values())),
        }
        summary_rows.append({"candidate": candidate, **_perf(portfolio_eq), **p_costs, "mapping": _mapping_text(mapping)})

        for sleeve_label, result in results.items():
            strategy = mapping[sleeve_label]
            col_name = f"{candidate}__{sleeve_label}__{strategy}"
            sleeve_curves[col_name] = result.equity_curve.rename(col_name)
            sleeve_rows.append({
                "candidate": candidate,
                "sleeve": sleeve_label,
                "strategy": strategy,
                **_perf(result.equity_curve),
                **_trade_costs(result),
                **_exposure_stats(result),
            })

    summary = pd.DataFrame(summary_rows).sort_values(["calmar", "cagr_pct"], ascending=[False, False])
    sleeve_summary = pd.DataFrame(sleeve_rows).sort_values(["candidate", "sleeve"])
    target = summary[
        (summary["cagr_pct"] >= 25.0)
        & (summary["max_drawdown_pct"] >= -35.0)
        & (summary["sharpe"] >= 1.0)
        & (summary["calmar"] >= 0.9)
    ].copy().sort_values(["calmar", "cagr_pct"], ascending=[False, False])

    pd.DataFrame(candidate_curves).sort_index().to_csv(out_dir / "candidate_equity_curves.csv")
    pd.DataFrame(sleeve_curves).sort_index().to_csv(out_dir / "sleeve_equity_curves.csv")
    summary.to_csv(out_dir / "candidate_summary.csv", index=False)
    target.to_csv(out_dir / "target_frontier_candidates.csv", index=False)
    sleeve_summary.to_csv(out_dir / "sleeve_summary.csv", index=False)

    payload = {
        "research_status": "research_only_direct_hybrid_confirmation",
        "definitions": definitions,
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
            "calibrate": args.calibrate,
            "calibrators_dir": args.calibrators_dir,
        },
        "artifacts": {
            "candidate_summary": str(out_dir / "candidate_summary.csv"),
            "target_frontier_candidates": str(out_dir / "target_frontier_candidates.csv"),
            "sleeve_summary": str(out_dir / "sleeve_summary.csv"),
            "candidate_equity_curves": str(out_dir / "candidate_equity_curves.csv"),
            "sleeve_equity_curves": str(out_dir / "sleeve_equity_curves.csv"),
            "summary_json": str(out_dir / "summary.json"),
            "summary_md": str(out_dir / "summary.md"),
        },
        "decision": {
            "status": "diagnostic_only",
            "not_approved": ["runtime_change", "paper_trading_change", "higher_live_exposure", "leverage", "order_routing_change"],
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    _write_markdown(out_dir / "summary.md", summary, sleeve_summary)

    display_cols = [
        "candidate", "total_return_pct", "cagr_pct", "max_drawdown_pct", "sharpe", "calmar", "ann_vol_pct",
        "worst_90d_return_pct", "worst_180d_return_pct", "max_time_underwater_days", "trade_count", "total_cost_usd", "mapping",
    ]
    sleeve_cols = [
        "candidate", "sleeve", "strategy", "cagr_pct", "max_drawdown_pct", "sharpe", "calmar", "trade_count", "total_cost_usd", "avg_exposure", "pct_in_market",
    ]
    with pd.option_context("display.max_columns", None, "display.width", 280, "display.float_format", "{:.4f}".format):
        print("\nCandidate Summary — ranked by Calmar / CAGR:")
        print(summary[[c for c in display_cols if c in summary.columns]].to_string(index=False))
        print("\nTarget Frontier Candidates:")
        if target.empty:
            print("No rows met target filters.")
        else:
            print(target[[c for c in display_cols if c in target.columns]].to_string(index=False))
        print("\nSleeve Summary:")
        print(sleeve_summary[[c for c in sleeve_cols if c in sleeve_summary.columns]].to_string(index=False))
    print(f"\nArtifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()
