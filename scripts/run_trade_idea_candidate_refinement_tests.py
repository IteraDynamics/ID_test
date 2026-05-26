#!/usr/bin/env python
"""Run focused refinement tests for the current best trade idea candidate.

The candidate tear sheet showed two obvious weaknesses:

1. 2022/bear-regime weakness and long underwater periods.
2. Large crypto stop-hit damage.

This runner does not change live/runtime code. It runs controlled replay variants
around the candidate configuration to see whether the weak points can be reduced
without destroying return.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pandas as pd


ALL_TICKERS = [
    "QQQ", "XLK", "IGV", "XLC", "SPY", "MTUM", "QUAL", "IWF", "IWM",
    "SPLV", "GLD", "XLE", "XLF", "BTC-USD", "ETH-USD",
]
CRYPTO = ["BTC-USD", "ETH-USD"]
GROWTH_CORE = ["QQQ", "XLK", "IGV", "XLC", "IWF", "XLF"]
GROWTH_EXTENDED = ["QQQ", "XLK", "IGV", "XLC", "SPY", "MTUM", "QUAL", "IWF", "IWM", "XLF"]
NON_CRYPTO = [x for x in ALL_TICKERS if x not in CRYPTO]

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

SCENARIOS: dict[str, dict[str, Any]] = {
    # Baseline we are trying to improve.
    "baseline_remove_weak_very_aggressive": {
        "tickers": ALL_TICKERS,
        "risk": {},
    },
    # Bucket / concentration controls. These are blunt, but useful first-pass tests.
    "bucket_cap_80": {
        "tickers": ALL_TICKERS,
        "risk": {"max_bucket_exposure_pct": 80},
    },
    "bucket_cap_60": {
        "tickers": ALL_TICKERS,
        "risk": {"max_bucket_exposure_pct": 60},
    },
    "bucket_cap_40": {
        "tickers": ALL_TICKERS,
        "risk": {"max_bucket_exposure_pct": 40},
    },
    "ticker_cap_35": {
        "tickers": ALL_TICKERS,
        "risk": {"max_ticker_exposure_pct": 35},
    },
    "ticker_cap_25": {
        "tickers": ALL_TICKERS,
        "risk": {"max_ticker_exposure_pct": 25},
    },
    # Quality gates: if weak regimes are mostly lower-quality signals, this should help.
    "min_score_85": {
        "tickers": ALL_TICKERS,
        "risk": {"min_score": 85.0},
    },
    "min_score_90": {
        "tickers": ALL_TICKERS,
        "risk": {"min_score": 90.0},
    },
    # Stop/exit sensitivity. If stop hits are the main damage, these expose whether default stop architecture is too loose/tight.
    "tighter_stop_6pct": {
        "tickers": ALL_TICKERS,
        "risk": {"default_stop_pct": 0.06},
    },
    "looser_stop_10pct": {
        "tickers": ALL_TICKERS,
        "risk": {"default_stop_pct": 0.10},
    },
    "looser_stop_12pct": {
        "tickers": ALL_TICKERS,
        "risk": {"default_stop_pct": 0.12},
    },
    # Cooldown sensitivity: prevents immediate re-entry after stop/cancelled stress.
    "cooldown_5d": {
        "tickers": ALL_TICKERS,
        "risk": {"cooldown_days": 5},
    },
    "cooldown_10d": {
        "tickers": ALL_TICKERS,
        "risk": {"cooldown_days": 10},
    },
    # Universe identity checks.
    "non_crypto_only": {
        "tickers": NON_CRYPTO,
        "risk": {},
    },
    "crypto_only": {
        "tickers": CRYPTO,
        "risk": {},
    },
    "crypto_plus_growth_core": {
        "tickers": CRYPTO + GROWTH_CORE,
        "risk": {},
    },
    "crypto_plus_growth_extended": {
        "tickers": CRYPTO + GROWTH_EXTENDED,
        "risk": {},
    },
    # Combined candidate attempts.
    "combined_bucket60_score85": {
        "tickers": ALL_TICKERS,
        "risk": {"max_bucket_exposure_pct": 60, "min_score": 85.0},
    },
    "combined_bucket60_cooldown5": {
        "tickers": ALL_TICKERS,
        "risk": {"max_bucket_exposure_pct": 60, "cooldown_days": 5},
    },
    "combined_score85_cooldown5": {
        "tickers": ALL_TICKERS,
        "risk": {"min_score": 85.0, "cooldown_days": 5},
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


def _fmt(value: Any, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "n/a"


def _risk_for(scenario: dict[str, Any]) -> dict[str, Any]:
    risk = dict(BASE_RISK)
    risk.update(scenario.get("risk", {}))
    return risk


def _run_one(name: str, scenario: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    root = _repo_root()
    out_dir = Path(args.out_dir) / _safe(name)
    risk = _risk_for(scenario)
    tickers = scenario["tickers"]

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
        "--tickers", *tickers,
    ]
    if args.record_rejected_orders:
        cmd.append("--record-rejected-orders")
    if args.extra_replay_args:
        cmd.extend(args.extra_replay_args)

    print("\n" + "=" * 170)
    print(f"  CANDIDATE REFINEMENT — {name}")
    print("=" * 170)
    print("  Tickers: " + ", ".join(tickers))
    print(
        "  Risk   : "
        f"notional={risk['default_notional']} gross={risk['max_gross_exposure_pct']}% "
        f"ticker={risk['max_ticker_exposure_pct']}% bucket={risk['max_bucket_exposure_pct']}% "
        f"score>={risk['min_score']} stop={risk['default_stop_pct']:.2%} cooldown={risk['cooldown_days']}d"
    )
    print("-" * 170)

    proc = subprocess.run(cmd, cwd=str(root), text=True, capture_output=True)
    if proc.stdout:
        print(proc.stdout)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr)
    if proc.returncode != 0:
        result = {"scenario": name, "error": f"exit_code_{proc.returncode}", "out_dir": str(out_dir)}
        if args.continue_on_error:
            return result
        raise SystemExit(proc.returncode)

    summary = _read_json(out_dir / "replay_summary.json")
    summary["scenario"] = name
    summary["ticker_count"] = len(tickers)
    summary["tickers"] = ",".join(tickers)
    summary["out_dir"] = str(out_dir)
    summary["risk_settings"] = risk
    return summary


def _row(summary: dict[str, Any]) -> dict[str, Any]:
    risk = summary.get("risk_settings") or {}
    return {
        "scenario": summary.get("scenario"),
        "ticker_count": summary.get("ticker_count"),
        "default_notional": risk.get("default_notional"),
        "max_gross_exposure_pct": risk.get("max_gross_exposure_pct"),
        "max_ticker_exposure_pct": risk.get("max_ticker_exposure_pct"),
        "max_bucket_exposure_pct": risk.get("max_bucket_exposure_pct"),
        "min_score": risk.get("min_score"),
        "default_stop_pct": risk.get("default_stop_pct"),
        "cooldown_days": risk.get("cooldown_days"),
        "orders": summary.get("total_orders"),
        "realized": summary.get("closed_realized_trades"),
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
        "out_dir": summary.get("out_dir"),
        "error": summary.get("error"),
    }


def _print_table(df: pd.DataFrame) -> None:
    print("\n" + "=" * 190)
    print("  TRADE IDEA CANDIDATE — REFINEMENT COMPARISON")
    print("=" * 190)
    if df.empty:
        print("  No scenario results.")
        return
    view = df.copy()
    view["calmar_num"] = pd.to_numeric(view.get("calmar"), errors="coerce")
    view["cagr_num"] = pd.to_numeric(view.get("cagr_pct"), errors="coerce")
    view = view.sort_values(["calmar_num", "cagr_num"], ascending=[False, False])
    print(
        f"  {'Scenario':<34} {'Tkr':>4} {'CAGR':>8} {'Ret':>8} {'MaxDD':>8} "
        f"{'Sharpe':>8} {'Sortino':>8} {'Calmar':>8} {'AnnVol':>8} {'Win%':>8} {'Exp':>8} {'Stop':>6} {'Real':>6}"
    )
    for _, r in view.iterrows():
        print(
            f"  {str(r.get('scenario')):<34} {int(r.get('ticker_count') or 0):>4} "
            f"{_fmt(r.get('cagr_pct')):>8} {_fmt(r.get('return_pct')):>8} {_fmt(r.get('maxdd_pct')):>8} "
            f"{_fmt(r.get('sharpe'), 3):>8} {_fmt(r.get('sortino'), 3):>8} {_fmt(r.get('calmar'), 3):>8} {_fmt(r.get('ann_vol_pct')):>8} "
            f"{_fmt(r.get('win_rate_pct')):>8} {_fmt(r.get('expectancy_pct')):>8} {int(r.get('stop_hits') or 0):>6} {int(r.get('realized') or 0):>6}"
        )
    print("=" * 190)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run focused refinement tests for the trade idea candidate")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--start", default="2019-01-01")
    p.add_argument("--end", default="2025-12-30")
    p.add_argument("--replay-start", default="2020-01-01")
    p.add_argument("--out-dir", default="artifacts/trade_idea_candidate_refinement")
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--scenarios", nargs="+", default=list(SCENARIOS.keys()), choices=list(SCENARIOS.keys()))
    p.add_argument("--progress-every", type=int, default=0)
    p.add_argument("--record-rejected-orders", action="store_true")
    p.add_argument("--continue-on-error", action="store_true")
    p.add_argument("--extra-replay-args", nargs=argparse.REMAINDER, default=[])
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    summaries = []
    for name in args.scenarios:
        summaries.append(_run_one(name, SCENARIOS[name], args))

    rows = [_row(x) for x in summaries]
    df = pd.DataFrame(rows)
    df.to_csv(out / "candidate_refinement_comparison.csv", index=False)
    (out / "candidate_refinement_comparison.json").write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")

    _print_table(df)
    print(f"  Comparison CSV : {out / 'candidate_refinement_comparison.csv'}")
    print(f"  Comparison JSON: {out / 'candidate_refinement_comparison.json'}")
    print("  Verdict        : REFINEMENT RESEARCH ONLY; no broker/runtime execution.\n")


if __name__ == "__main__":
    main()
