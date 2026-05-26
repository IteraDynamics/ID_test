#!/usr/bin/env python
"""Run turnover-reduction sweeps around the leading trade idea candidates.

The cost/slippage stress showed that the signal survives, but turnover is too
expensive under Coinbase-style friction. This runner tests whether fewer, more
selective trades can preserve the edge while reducing cost drag.

It reruns replay variants around the two current candidate configurations:

- bucket_cap_60
- looser_stop_12pct

Then, optionally, it runs the existing cost-stress script against the generated
candidate directories.

Research only. No broker/runtime/live execution code is modified.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pandas as pd


DISPLAY_WIDTH = 190

TICKERS = [
    "QQQ", "XLK", "IGV", "XLC", "SPY", "MTUM", "QUAL", "IWF", "IWM",
    "SPLV", "GLD", "XLE", "XLF", "BTC-USD", "ETH-USD",
]

BASE_RISK = {
    "default_notional": 25_000,
    "max_new_trades_per_day": 6,
    "max_open_trades": 18,
    "max_reserved_trades": 26,
    "max_gross_exposure_pct": 250,
    "max_ticker_exposure_pct": 50,
    "max_bucket_exposure_pct": 100,
    "cooldown_days": 1,
    "min_score": 80.0,
    "cancel_pending_after_days": 10,
    "cancel_pending_if_distance_gt_pct": 3.0,
    "default_stop_pct": 0.08,
}

CANDIDATE_BASES: dict[str, dict[str, Any]] = {
    "bucket_cap_60": {
        "max_bucket_exposure_pct": 60,
        "default_stop_pct": 0.08,
    },
    "looser_stop_12pct": {
        "max_bucket_exposure_pct": 100,
        "default_stop_pct": 0.12,
    },
}

# These are intentionally simple first-pass turnover constraints. They focus on
# knobs the replay engine already exposes, so the test stays apples-to-apples.
TURNOVER_VARIANTS: dict[str, dict[str, Any]] = {
    "baseline": {},
    "score85": {"min_score": 85.0},
    "score90": {"min_score": 90.0},
    "max_new_4": {"max_new_trades_per_day": 4},
    "max_new_3": {"max_new_trades_per_day": 3},
    "max_new_2": {"max_new_trades_per_day": 2},
    "reserved20": {"max_reserved_trades": 20},
    "reserved16": {"max_reserved_trades": 16},
    "open14_reserved20": {"max_open_trades": 14, "max_reserved_trades": 20},
    "open12_reserved16": {"max_open_trades": 12, "max_reserved_trades": 16},
    "pending_tight_2pct": {"cancel_pending_if_distance_gt_pct": 2.0},
    "pending_tight_1pct": {"cancel_pending_if_distance_gt_pct": 1.0},
    "pending_age_5d": {"cancel_pending_after_days": 5},
    "pending_age_3d": {"cancel_pending_after_days": 3},
    "quality_combo_a": {
        "min_score": 85.0,
        "max_new_trades_per_day": 3,
        "cancel_pending_if_distance_gt_pct": 2.0,
    },
    "quality_combo_b": {
        "min_score": 85.0,
        "max_new_trades_per_day": 2,
        "max_reserved_trades": 16,
        "cancel_pending_if_distance_gt_pct": 2.0,
    },
    "quality_combo_c": {
        "min_score": 90.0,
        "max_new_trades_per_day": 3,
        "max_reserved_trades": 16,
        "cancel_pending_after_days": 5,
    },
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _safe(value: str) -> str:
    return value.replace(" ", "_").replace("/", "_").replace("\\", "_").replace(":", "_")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    return pd.read_csv(path)


def _fmt(value: Any, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "n/a"


def _risk_for(candidate: str, variant: str) -> dict[str, Any]:
    risk = dict(BASE_RISK)
    risk.update(CANDIDATE_BASES[candidate])
    risk.update(TURNOVER_VARIANTS[variant])
    return risk


def _run(cmd: list[str], cwd: Path, continue_on_error: bool) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True)
    if proc.stdout:
        print(proc.stdout)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr)
    if proc.returncode != 0 and not continue_on_error:
        raise SystemExit(proc.returncode)
    return proc.returncode, proc.stdout, proc.stderr


def _run_replay(candidate: str, variant: str, args: argparse.Namespace) -> dict[str, Any]:
    root = _repo_root()
    risk = _risk_for(candidate, variant)
    scenario_name = f"{candidate}__{variant}"
    out_dir = Path(args.out_dir) / _safe(scenario_name)

    cmd = [
        sys.executable,
        "scripts/replay_trade_idea_desk_cycle.py",
        "--data-dir", args.data_dir,
        "--start", args.start,
        "--end", args.end,
        "--replay-start", args.replay_start,
        "--out-dir", str(out_dir),
        "--capital", str(args.capital),
        "--default-notional", str(risk["default_notional"]),
        "--min-score", str(risk["min_score"]),
        "--max-new-trades-per-day", str(risk["max_new_trades_per_day"]),
        "--max-open-trades", str(risk["max_open_trades"]),
        "--max-reserved-trades", str(risk["max_reserved_trades"]),
        "--max-gross-exposure-pct", str(risk["max_gross_exposure_pct"]),
        "--max-ticker-exposure-pct", str(risk["max_ticker_exposure_pct"]),
        "--max-bucket-exposure-pct", str(risk["max_bucket_exposure_pct"]),
        "--cooldown-days", str(risk["cooldown_days"]),
        "--cancel-pending-after-days", str(risk["cancel_pending_after_days"]),
        "--cancel-pending-if-distance-gt-pct", str(risk["cancel_pending_if_distance_gt_pct"]),
        "--default-stop-pct", str(risk["default_stop_pct"]),
        "--progress-every", str(args.progress_every),
        "--tickers", *TICKERS,
    ]
    if args.record_rejected_orders:
        cmd.append("--record-rejected-orders")
    if args.extra_replay_args:
        cmd.extend(args.extra_replay_args)

    print("\n" + "=" * DISPLAY_WIDTH)
    print(f"  TURNOVER SWEEP — {scenario_name}")
    print("=" * DISPLAY_WIDTH)
    print(
        "  Risk: "
        f"score>={risk['min_score']} new/day={risk['max_new_trades_per_day']} "
        f"open={risk['max_open_trades']} reserved={risk['max_reserved_trades']} "
        f"bucket={risk['max_bucket_exposure_pct']}% stop={risk['default_stop_pct']:.2%} "
        f"pending_age={risk['cancel_pending_after_days']}d pending_dist={risk['cancel_pending_if_distance_gt_pct']}%"
    )
    print("-" * DISPLAY_WIDTH)

    rc, _, _ = _run(cmd, root, args.continue_on_error)
    if rc != 0:
        return {
            "candidate": candidate,
            "variant": variant,
            "scenario": scenario_name,
            "out_dir": str(out_dir),
            "error": f"exit_code_{rc}",
            **risk,
        }

    summary = _read_json(out_dir / "replay_summary.json")
    trades = _read_csv(out_dir / "replay_trades.csv")
    realized = trades[trades.get("status", pd.Series(dtype=str)).astype(str).isin(["target_hit", "stop_hit", "expired", "manual_closed"])] if not trades.empty else pd.DataFrame()
    pending_cancelled = int((trades.get("status", pd.Series(dtype=str)).astype(str) == "cancelled").sum()) if not trades.empty else 0

    row = {
        "candidate": candidate,
        "variant": variant,
        "scenario": scenario_name,
        "out_dir": str(out_dir),
        "ticker_count": len(TICKERS),
        "total_orders": summary.get("total_orders"),
        "realized": summary.get("closed_realized_trades", len(realized)),
        "cancelled": summary.get("cancelled_orders", pending_cancelled),
        "target_hits": summary.get("target_hits"),
        "stop_hits": summary.get("stop_hits"),
        "expired": summary.get("expired_trades"),
        "return_pct": summary.get("total_return_pct_on_capital"),
        "cagr_pct": summary.get("cagr_pct"),
        "maxdd_pct": summary.get("max_drawdown_pct_on_equity"),
        "sharpe": summary.get("sharpe"),
        "sortino": summary.get("sortino"),
        "calmar": summary.get("calmar"),
        "ann_vol_pct": summary.get("annualized_vol_pct"),
        "win_rate_pct": summary.get("win_rate_pct"),
        "expectancy_pct": summary.get("expectancy_pct_per_realized_trade"),
        "worst_day_pct": summary.get("worst_day_pct"),
        "realized_pnl": summary.get("total_realized_pnl"),
        "final_equity": summary.get("final_equity"),
        "max_open_exposure_pct": summary.get("max_open_exposure_pct"),
        "max_reserved_exposure_pct": summary.get("max_reserved_exposure_pct"),
        **risk,
    }
    return row


def _print_replay_table(df: pd.DataFrame) -> None:
    print("\n" + "=" * DISPLAY_WIDTH)
    print("  TRADE IDEA TURNOVER REDUCTION SWEEP — FRICTIONLESS REPLAY")
    print("=" * DISPLAY_WIDTH)
    if df.empty:
        print("  No scenario results.")
        return

    view = df.copy()
    view["calmar_num"] = pd.to_numeric(view.get("calmar"), errors="coerce")
    view["cagr_num"] = pd.to_numeric(view.get("cagr_pct"), errors="coerce")
    view = view.sort_values(["calmar_num", "cagr_num"], ascending=[False, False])

    print(
        f"  {'Scenario':<42} {'Trades':>7} {'CAGR':>8} {'Ret':>8} {'MaxDD':>8} "
        f"{'Sharpe':>8} {'Sortino':>8} {'Calmar':>8} {'Win%':>8} {'Exp':>8} {'Stop':>6} {'FinalEq':>12}"
    )
    for _, r in view.iterrows():
        print(
            f"  {str(r.get('scenario')):<42} {int(r.get('realized') or 0):>7} "
            f"{_fmt(r.get('cagr_pct')):>8} {_fmt(r.get('return_pct')):>8} {_fmt(r.get('maxdd_pct')):>8} "
            f"{_fmt(r.get('sharpe'), 3):>8} {_fmt(r.get('sortino'), 3):>8} {_fmt(r.get('calmar'), 3):>8} "
            f"{_fmt(r.get('win_rate_pct')):>8} {_fmt(r.get('expectancy_pct')):>8} {int(r.get('stop_hits') or 0):>6} "
            f"${float(r.get('final_equity') or 0):>11,.0f}"
        )
    print("=" * DISPLAY_WIDTH)


def _run_cost_stress(rows: list[dict[str, Any]], args: argparse.Namespace) -> None:
    if not args.run_cost_stress:
        return

    dirs = [str(Path(r["out_dir"])) for r in rows if not r.get("error")]
    if not dirs:
        print("\nNo successful replay dirs available for cost stress.")
        return

    cmd = [
        sys.executable,
        "scripts/stress_trade_idea_candidate_costs.py",
        "--candidate-dirs", *dirs,
        "--cost-cases", *args.cost_cases,
        "--out-dir", str(Path(args.out_dir) / "cost_stress"),
        "--capital", str(args.capital),
    ]
    if args.write_adjusted_daily:
        cmd.append("--write-adjusted-daily")

    print("\n" + "=" * DISPLAY_WIDTH)
    print("  RUNNING COST STRESS FOR TURNOVER SWEEP OUTPUTS")
    print("=" * DISPLAY_WIDTH)
    _run(cmd, _repo_root(), args.continue_on_error)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run turnover-reduction sweeps for trade idea candidates")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--start", default="2019-01-01")
    p.add_argument("--end", default="2025-12-30")
    p.add_argument("--replay-start", default="2020-01-01")
    p.add_argument("--out-dir", default="artifacts/trade_idea_turnover_sweep")
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--candidates", nargs="+", default=list(CANDIDATE_BASES.keys()), choices=list(CANDIDATE_BASES.keys()))
    p.add_argument("--variants", nargs="+", default=list(TURNOVER_VARIANTS.keys()), choices=list(TURNOVER_VARIANTS.keys()))
    p.add_argument("--progress-every", type=int, default=0)
    p.add_argument("--record-rejected-orders", action="store_true")
    p.add_argument("--continue-on-error", action="store_true")
    p.add_argument("--run-cost-stress", action="store_true")
    p.add_argument("--cost-cases", nargs="+", default=["harsh", "very_harsh"])
    p.add_argument("--write-adjusted-daily", action="store_true")
    p.add_argument("--extra-replay-args", nargs=argparse.REMAINDER, default=[])
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for candidate in args.candidates:
        for variant in args.variants:
            rows.append(_run_replay(candidate, variant, args))

    df = pd.DataFrame(rows)
    df.to_csv(out / "turnover_sweep_comparison.csv", index=False)
    (out / "turnover_sweep_comparison.json").write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")

    _print_replay_table(df)
    print(f"  Comparison CSV : {out / 'turnover_sweep_comparison.csv'}")
    print(f"  Comparison JSON: {out / 'turnover_sweep_comparison.json'}")
    print("  Verdict        : TURNOVER SWEEP RESEARCH ONLY; no broker/runtime execution.")

    _run_cost_stress(rows, args)


if __name__ == "__main__":
    main()
