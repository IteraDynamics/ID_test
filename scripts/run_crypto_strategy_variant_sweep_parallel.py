#!/usr/bin/env python
"""Crypto Risk Budget v2 — parallel strategy-variant sweep wrapper.

This wrapper launches one existing `run_crypto_strategy_variant_sweep.py` process
per strategy variant, with an isolated output directory for each strategy, then
collates the per-strategy `variant_summary.csv` files into a combined summary.

Why this exists:
    Full variant sweeps are slow because each strategy runs BTC_1H, BTC_4H,
    ETH_1H, and ETH_4H serially. Strategy variants are independent, so we can
    safely run multiple single-strategy sweeps in parallel on machines with
    enough CPU/RAM.

Research-only. No runtime, paper-trading, production allocation, or execution
changes are made.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import pandas as pd


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
BASELINE_STRATEGY = "trend_following_v8_ecap60_add80"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run crypto strategy variant sweep variants in parallel",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--btc-data", required=True)
    p.add_argument("--eth-data", required=True)
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--calibrate", action="store_true")
    p.add_argument("--calibrators-dir", default=None)
    p.add_argument("--strategies", default=",".join(DEFAULT_VARIANTS))
    p.add_argument("--baseline", default=BASELINE_STRATEGY)
    p.add_argument("--fee", type=float, default=0.0006)
    p.add_argument("--base-slippage", type=float, default=3.0)
    p.add_argument("--slippage-vol-factor", type=float, default=50.0)
    p.add_argument("--cooldown", type=int, default=None)
    p.add_argument("--rebalance-threshold", type=float, default=0.05)
    p.add_argument("--max-workers", type=int, default=2, help="Parallel strategy jobs. Start with 2 on a desktop; use 3-4 only if CPU/RAM allow.")
    p.add_argument("--out-dir", default="artifacts/crypto_risk_budget_v2_strategy_variant_sweep_parallel")
    p.add_argument("--python", default=sys.executable, help="Python executable used to launch child processes")
    return p.parse_args()


def _parse_strategies(raw: str) -> list[str]:
    out = [x.strip() for x in raw.split(",") if x.strip()]
    if not out:
        raise ValueError("No strategies provided")
    return out


def _strategy_out_dir(root: Path, strategy: str) -> Path:
    return root / "per_strategy" / strategy


def _run_one(args: argparse.Namespace, strategy: str, root: Path) -> dict[str, Any]:
    strategy_dir = _strategy_out_dir(root, strategy)
    strategy_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        args.python,
        "scripts/run_crypto_strategy_variant_sweep.py",
        "--btc-data", args.btc_data,
        "--eth-data", args.eth_data,
        "--capital", str(args.capital),
        "--strategies", strategy,
        # Use itself as baseline in the child so the child does not append the global baseline.
        # Global baseline deltas are recomputed by this wrapper during collation.
        "--baseline", strategy,
        "--fee", str(args.fee),
        "--base-slippage", str(args.base_slippage),
        "--slippage-vol-factor", str(args.slippage_vol_factor),
        "--rebalance-threshold", str(args.rebalance_threshold),
        "--out-dir", str(strategy_dir),
    ]
    if args.start:
        cmd.extend(["--start", args.start])
    if args.end:
        cmd.extend(["--end", args.end])
    if args.calibrate:
        cmd.append("--calibrate")
    if args.calibrators_dir:
        cmd.extend(["--calibrators-dir", args.calibrators_dir])
    if args.cooldown is not None:
        cmd.extend(["--cooldown", str(args.cooldown)])

    log_path = strategy_dir / "run.log"
    with log_path.open("w", encoding="utf-8") as log_file:
        proc = subprocess.run(
            cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )

    return {
        "strategy": strategy,
        "returncode": proc.returncode,
        "out_dir": str(strategy_dir),
        "log": str(log_path),
        "summary_csv": str(strategy_dir / "variant_summary.csv"),
    }


def _rank_and_delta(summary: pd.DataFrame, baseline: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    out = summary.copy()
    if baseline in out["strategy"].values:
        base = out.loc[out["strategy"] == baseline].iloc[0]
        for col in ["total_return_pct", "cagr_pct", "max_drawdown_pct", "sharpe", "calmar", "ann_vol_pct", "total_trades"]:
            if col in out.columns:
                out[f"delta_{col}_vs_baseline"] = out[col] - float(base[col])
    target_rows = out[
        (out["cagr_pct"] >= 25.0)
        & (out["max_drawdown_pct"] >= -35.0)
        & (out["sharpe"] >= 1.0)
        & (out["calmar"] >= 0.9)
    ].copy()
    target_rows = target_rows.sort_values(["calmar", "cagr_pct"], ascending=[False, False])
    out = out.sort_values(["calmar", "cagr_pct"], ascending=[False, False])
    return out, target_rows


def _format_md_value(value: object, floatfmt: str = ".4f") -> str:
    if isinstance(value, float):
        return format(value, floatfmt)
    if pd.isna(value):
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


def _to_markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No rows._"
    columns = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(columns) + " |"]
    lines.append("| " + " | ".join(["---"] * len(columns)) + " |")
    for _, row in df.iterrows():
        vals = [_format_md_value(row[c]) for c in df.columns]
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def _collate(args: argparse.Namespace, root: Path, job_results: list[dict[str, Any]]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for result in job_results:
        csv_path = Path(result["summary_csv"])
        if result["returncode"] != 0 or not csv_path.exists():
            continue
        df = pd.read_csv(csv_path)
        if df.empty:
            continue
        # Each child should have exactly one strategy row.
        rows.append(df.iloc[0].to_dict())

    if not rows:
        return pd.DataFrame(), pd.DataFrame()

    summary = pd.DataFrame(rows)
    ranked, target_rows = _rank_and_delta(summary, args.baseline)
    ranked.to_csv(root / "variant_summary.csv", index=False)
    target_rows.to_csv(root / "target_frontier_candidates.csv", index=False)

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
    delta_cols = [c for c in ranked.columns if c.startswith("delta_")]
    cols = [c for c in display_cols + delta_cols if c in ranked.columns]
    md = [
        "# Crypto Risk Budget v2 — Parallel Strategy Variant Sweep",
        "",
        "Research-only. No runtime or paper-trading changes approved.",
        "",
        "## Variant Summary",
        "",
        _to_markdown_table(ranked[cols]),
        "",
        "## Target Frontier Candidates",
        "",
        _to_markdown_table(target_rows[cols]) if not target_rows.empty else "_No rows met target filters._",
        "",
    ]
    (root / "summary.md").write_text("\n".join(md), encoding="utf-8")
    return ranked, target_rows


def main() -> None:
    args = parse_args()
    strategies = _parse_strategies(args.strategies)
    root = Path(args.out_dir)
    root.mkdir(parents=True, exist_ok=True)

    print("\n=== CRYPTO RISK BUDGET V2 — PARALLEL STRATEGY VARIANT SWEEP ===")
    print(f"Strategies:   {', '.join(strategies)}")
    print(f"Max workers:  {args.max_workers}")
    print(f"Out dir:      {root}")
    print("Child process logs are written under per_strategy/<strategy>/run.log")

    job_results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, int(args.max_workers))) as pool:
        futures = {pool.submit(_run_one, args, strategy, root): strategy for strategy in strategies}
        for future in as_completed(futures):
            strategy = futures[future]
            try:
                result = future.result()
            except Exception as exc:  # pragma: no cover - defensive CLI logging
                result = {"strategy": strategy, "returncode": -1, "error": repr(exc)}
            job_results.append(result)
            status = "OK" if result.get("returncode") == 0 else f"FAILED rc={result.get('returncode')}"
            print(f"[{status}] {strategy}  log={result.get('log')}")
            # Collate after every finished child so partial summary is available.
            ranked, target_rows = _collate(args, root, job_results)
            if not ranked.empty:
                print("Current ranked summary saved to:", root / "variant_summary.csv")

    ranked, target_rows = _collate(args, root, job_results)
    payload = {
        "research_status": "research_only_parallel_strategy_variant_sweep",
        "strategies": strategies,
        "baseline": args.baseline,
        "max_workers": args.max_workers,
        "jobs": job_results,
        "cost_assumptions": {
            "fee": args.fee,
            "base_slippage_bps": args.base_slippage,
            "slippage_vol_factor": args.slippage_vol_factor,
            "rebalance_threshold": args.rebalance_threshold,
        },
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
    (root / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    if ranked.empty:
        print("No successful strategy summaries found. Check per-strategy run.log files.")
        return

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
    delta_cols = [c for c in ranked.columns if c.startswith("delta_")]
    cols = [c for c in display_cols + delta_cols if c in ranked.columns]
    with pd.option_context("display.max_columns", None, "display.width", 260, "display.float_format", "{:.4f}".format):
        print("\nVariant Summary — ranked by Calmar / CAGR:")
        print(ranked[cols].to_string(index=False))
        print("\nTarget Frontier Candidates:")
        if target_rows.empty:
            print("No rows met target filters.")
        else:
            print(target_rows[cols].to_string(index=False))
    print(f"\nArtifacts saved to: {root}")


if __name__ == "__main__":
    main()
