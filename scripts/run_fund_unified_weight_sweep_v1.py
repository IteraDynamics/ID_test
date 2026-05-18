#!/usr/bin/env python
"""Fund Unified Weight Sweep v1.

Research-only sleeve-weight sensitivity harness for the unified crypto + equity
MR overlay fund book.

Purpose:
    Determine how much crypto sleeve allocation the fund can carry before it
    violates drawdown governance.

This script imports the single-run unified backtest harness and runs a grid of
crypto/equity sleeve weights under the same closed-bar target streams and cost
assumptions. It does not mutate Fund Target Book v3, crypto target streams,
runtime code, broker state, or paper-broker state.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from research.harness.execution_model import ExecutionConfig
from scripts.run_fund_unified_backtest_v1 import (
    _combine_targets,
    _load_crypto_targets,
    _load_equity_target_book,
    _read_price,
    _run_backtest,
)

DEFAULT_OUT = "artifacts/fund_unified_weight_sweep_v1"
DEFAULT_CRYPTO_GRID = "0.50,0.40,0.30,0.25,0.20,0.15,0.10,0.05,0.00"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run unified fund sleeve-weight sweep with modeled costs",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--crypto-targets", default="artifacts/crypto_target_stream_v1/crypto_target_exposure_daily.csv")
    p.add_argument("--equity-target-book", default="artifacts/equity_mr_overlay_target_book_v1/equity_mr_overlay_target_book.csv")
    p.add_argument("--btc-data", default="data/BTC_1D.csv")
    p.add_argument("--eth-data", default="data/ETH_1D.csv")
    p.add_argument("--spy-data", default="data/SPY_1D.csv")
    p.add_argument("--qqq-data", default="data/QQQ_1D.csv")
    p.add_argument("--bil-data", default="data/BIL_1D.csv")
    p.add_argument("--crypto-weight-grid", default=DEFAULT_CRYPTO_GRID)
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--equity-slippage-bps", type=float, default=5.0)
    p.add_argument("--equity-commission-bps", type=float, default=0.0)
    p.add_argument("--rebalance-frequency", choices=["D", "W", "M", "Q"], default="M")
    p.add_argument("--rebalance-threshold-bps", type=float, default=25.0)
    p.add_argument("--charge-initial-costs", action="store_true")
    p.add_argument("--max-dd-gate-pct", type=float, default=-30.0)
    p.add_argument("--accounting-tolerance", type=float, default=1e-6)
    p.add_argument("--out-dir", default=DEFAULT_OUT)
    return p.parse_args()


def _parse_grid(raw: str) -> list[float]:
    vals: list[float] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        val = float(part)
        if val < 0.0 or val > 1.0:
            raise ValueError(f"crypto weight must be between 0 and 1: {val}")
        vals.append(val)
    if not vals:
        raise ValueError("crypto-weight-grid produced no values")
    return sorted(set(vals), reverse=True)


def _summary_row(summary: pd.DataFrame, series: str) -> dict[str, Any]:
    match = summary[summary["series"] == series]
    if match.empty:
        raise ValueError(f"summary missing series={series}")
    return match.iloc[0].to_dict()


def _md_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    if df.empty:
        return "_No rows._"
    if max_rows is not None:
        df = df.head(max_rows)
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        vals = []
        for c in df.columns:
            v = row[c]
            if isinstance(v, float):
                vals.append(f"{v:.6f}")
            else:
                vals.append(str(v).replace("|", "\\|").replace("\n", " "))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    crypto_grid = _parse_grid(args.crypto_weight_grid)
    crypto_targets = _load_crypto_targets(Path(args.crypto_targets))
    equity_targets = _load_equity_target_book(Path(args.equity_target_book))
    prices = {
        "BTC": _read_price(Path(args.btc_data), "BTC"),
        "ETH": _read_price(Path(args.eth_data), "ETH"),
        "SPY": _read_price(Path(args.spy_data), "SPY"),
        "QQQ": _read_price(Path(args.qqq_data), "QQQ"),
        "BIL": _read_price(Path(args.bil_data), "BIL"),
    }
    crypto_config = ExecutionConfig.from_env()

    rows: list[dict[str, Any]] = []
    all_summary_rows: list[dict[str, Any]] = []
    for crypto_w in crypto_grid:
        equity_w = 1.0 - crypto_w
        targets = _combine_targets(
            crypto_targets,
            equity_targets,
            crypto_w=crypto_w,
            equity_w=equity_w,
            tol=args.accounting_tolerance,
        )
        if not bool(targets["accounting_ok"].all()):
            bad_count = int((~targets["accounting_ok"]).sum())
            rows.append({
                "crypto_weight": crypto_w,
                "equity_weight": equity_w,
                "research_ready": False,
                "fail_reason": f"accounting_failed_{bad_count}_rows",
            })
            continue
        curves, trades, summary = _run_backtest(
            targets=targets,
            prices=prices,
            capital=args.capital,
            equity_slip_bps=args.equity_slippage_bps,
            equity_commission_bps=args.equity_commission_bps,
            crypto_config=crypto_config,
            rebalance_frequency=args.rebalance_frequency,
            rebalance_threshold_bps=args.rebalance_threshold_bps,
            charge_initial_costs=args.charge_initial_costs,
        )
        net = _summary_row(summary, "net_after_costs")
        gross = _summary_row(summary, "gross_before_costs")
        cost = _summary_row(summary, "cost_summary")
        pass_dd = bool(float(net["max_drawdown_pct"]) >= args.max_dd_gate_pct)
        rows.append({
            "crypto_weight": crypto_w,
            "equity_weight": equity_w,
            "research_ready": True,
            "dd_gate_pass": pass_dd,
            "max_dd_gate_pct": args.max_dd_gate_pct,
            "net_total_return_pct": float(net["total_return_pct"]),
            "net_cagr_pct": float(net["cagr_pct"]),
            "net_max_drawdown_pct": float(net["max_drawdown_pct"]),
            "net_sharpe": float(net["sharpe"]),
            "net_sortino": float(net["sortino"]),
            "net_calmar": float(net["calmar"]),
            "net_worst_90d_return_pct": float(net["worst_90d_return_pct"]),
            "net_worst_180d_return_pct": float(net["worst_180d_return_pct"]),
            "gross_cagr_pct": float(gross["cagr_pct"]),
            "gross_max_drawdown_pct": float(gross["max_drawdown_pct"]),
            "total_cost_usd": float(cost.get("total_cost_usd", 0.0)),
            "total_cost_pct_start_nav": float(cost.get("total_cost_pct_start_nav", 0.0)),
            "total_executed_turnover": float(cost.get("total_executed_turnover", 0.0)),
            "executed_rebalance_count": int(cost.get("executed_rebalance_count", 0)),
            "fail_reason": "none",
        })
        tagged = summary.copy()
        tagged.insert(0, "crypto_weight", crypto_w)
        tagged.insert(1, "equity_weight", equity_w)
        all_summary_rows.extend(tagged.to_dict("records"))

    sweep = pd.DataFrame(rows).sort_values(["dd_gate_pass", "net_calmar", "net_cagr_pct"], ascending=[False, False, False])
    detailed = pd.DataFrame(all_summary_rows)
    pass_rows = sweep[(sweep["research_ready"] == True) & (sweep["dd_gate_pass"] == True)]
    recommended = pass_rows.iloc[0].to_dict() if not pass_rows.empty else None

    sweep.to_csv(out_dir / "fund_unified_weight_sweep_summary.csv", index=False)
    detailed.to_csv(out_dir / "fund_unified_weight_sweep_detail.csv", index=False)
    payload = {
        "research_status": "research_only_unified_fund_weight_sweep_v1",
        "max_dd_gate_pct": args.max_dd_gate_pct,
        "recommended_candidate": recommended,
        "crypto_cost_model": crypto_config.__dict__,
        "equity_cost_model": {
            "equity_slippage_bps": args.equity_slippage_bps,
            "equity_commission_bps": args.equity_commission_bps,
        },
        "execution_policy": {
            "rebalance_frequency": args.rebalance_frequency,
            "rebalance_threshold_bps": args.rebalance_threshold_bps,
            "charge_initial_costs": args.charge_initial_costs,
        },
        "inputs": vars(args),
        "outputs": {
            "summary": str(out_dir / "fund_unified_weight_sweep_summary.csv"),
            "detail": str(out_dir / "fund_unified_weight_sweep_detail.csv"),
            "summary_md": str(out_dir / "summary.md"),
            "summary_json": str(out_dir / "summary.json"),
        },
        "guardrails": {
            "research_only": True,
            "broker_ready": False,
            "mutates_target_book": False,
            "generates_orders": False,
            "dynamic_allocator_approved": False,
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    (out_dir / "summary.md").write_text("\n".join([
        "# Fund Unified Weight Sweep v1",
        "",
        "Research-only sleeve-weight sweep for unified crypto + equity MR overlay fund book.",
        "",
        "## Governance Gate",
        "",
        "```text",
        f"MaxDD gate pct: {args.max_dd_gate_pct}",
        f"Rebalance frequency: {args.rebalance_frequency}",
        f"Rebalance threshold bps: {args.rebalance_threshold_bps}",
        f"Charge initial costs: {args.charge_initial_costs}",
        "```",
        "",
        "## Recommended Candidate",
        "",
        "```json",
        json.dumps(recommended, indent=2, default=str),
        "```",
        "",
        "## Sweep Summary",
        "",
        _md_table(sweep, max_rows=100),
        "",
        "## Guardrail",
        "",
        "```text",
        "Research only. No fund target book change, no crypto stream mutation, no broker integration, no order generation, and no dynamic allocator approval.",
        "```",
        "",
    ]), encoding="utf-8")

    with pd.option_context("display.max_columns", None, "display.width", 1200, "display.float_format", "{:.6f}".format):
        print("\n=== FUND UNIFIED WEIGHT SWEEP V1 ===")
        print(f"MaxDD gate: {args.max_dd_gate_pct:.2f}%")
        print(f"Execution policy: frequency={args.rebalance_frequency}, threshold_bps={args.rebalance_threshold_bps}, charge_initial_costs={args.charge_initial_costs}")
        print("\nSweep Summary:")
        print(sweep.to_string(index=False))
        print("\nRecommended Candidate:")
        print(json.dumps(recommended, indent=2, default=str))
    print(f"\nArtifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()
