#!/usr/bin/env python
"""Run cost-aware universe pruning sweeps for trade idea candidates.

This runner focuses on the current best candidate family:

- looser_stop_12pct + max_new_3
- bucket_cap_60 + max_new_3

It tests whether pruning weak / low-value parts of the universe improves the
asset-class-specific post-cost profile. The replay remains frictionless; the
runner then invokes the asset-class-aware cost stress script against all scenario
outputs.

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


DISPLAY_WIDTH = 198

ALL_TICKERS = [
    "QQQ", "SMH", "XLK", "IGV", "XLC", "SPY", "RSP", "MTUM", "QUAL", "IWF",
    "IWM", "USMV", "SPLV", "SCHD", "TLT", "IEF", "GLD", "XLE", "XLF", "BTC-USD", "ETH-USD",
]

CURRENT_CORE_TICKERS = [
    "QQQ", "XLK", "IGV", "XLC", "SPY", "MTUM", "QUAL", "IWF", "IWM",
    "SPLV", "GLD", "XLE", "XLF", "BTC-USD", "ETH-USD",
]

CRYPTO = ["BTC-USD", "ETH-USD"]
GROWTH_RISK_ON = ["QQQ", "SMH", "XLK", "IGV", "XLC", "MTUM", "IWF", "IWM"]
GROWTH_CORE = ["QQQ", "XLK", "IGV", "XLC", "IWF"]
GROWTH_TOP_ATTRIBUTION = ["XLK", "IWF", "QQQ", "XLF", "XLC"]
MACRO_RATES_COMMODITIES = ["TLT", "IEF", "GLD", "XLE", "XLF"]
MACRO_LIQUID_ONLY = ["GLD", "XLE", "XLF"]
DEFENSIVE_QUALITY = ["USMV", "SPLV", "SCHD", "QUAL", "RSP", "SPY"]
KNOWN_WEAK = ["SPLV", "IWM", "SMH", "IEF", "SCHD", "RSP", "TLT", "USMV"]

UNIVERSES: dict[str, list[str]] = {
    "current_core": CURRENT_CORE_TICKERS,
    "remove_splv": [t for t in CURRENT_CORE_TICKERS if t != "SPLV"],
    "remove_splv_iwm": [t for t in CURRENT_CORE_TICKERS if t not in {"SPLV", "IWM"}],
    "remove_defensive_quality": [t for t in CURRENT_CORE_TICKERS if t not in set(DEFENSIVE_QUALITY)],
    "remove_known_weak": [t for t in CURRENT_CORE_TICKERS if t not in set(KNOWN_WEAK)],
    "crypto_only": CRYPTO,
    "crypto_plus_growth": sorted(set(CRYPTO + GROWTH_RISK_ON)),
    "crypto_plus_growth_core": sorted(set(CRYPTO + GROWTH_CORE)),
    "crypto_plus_top_equity_names": sorted(set(CRYPTO + GROWTH_TOP_ATTRIBUTION)),
    "crypto_plus_growth_no_weak": sorted(set(CRYPTO + [t for t in GROWTH_RISK_ON if t not in set(KNOWN_WEAK)])),
    "crypto_plus_growth_plus_macro_liquid": sorted(set(CRYPTO + GROWTH_CORE + MACRO_LIQUID_ONLY)),
    "crypto_plus_growth_plus_quality": sorted(set(CRYPTO + GROWTH_CORE + ["QUAL", "SPY"])),
    "crypto_growth_xlf_gld_xle": sorted(set(CRYPTO + GROWTH_CORE + ["XLF", "GLD", "XLE"])),
    "full_all_assets": ALL_TICKERS,
}

CANDIDATES: dict[str, dict[str, Any]] = {
    "looser_stop_12pct_max_new_3": {
        "default_stop_pct": 0.12,
        "max_bucket_exposure_pct": 100,
        "max_new_trades_per_day": 3,
    },
    "bucket_cap_60_max_new_3": {
        "default_stop_pct": 0.08,
        "max_bucket_exposure_pct": 60,
        "max_new_trades_per_day": 3,
    },
}

BASE_RISK: dict[str, Any] = {
    "default_notional": 25_000,
    "min_score": 80.0,
    "max_open_trades": 18,
    "max_reserved_trades": 26,
    "max_gross_exposure_pct": 250,
    "max_ticker_exposure_pct": 50,
    "cooldown_days": 1,
    "cancel_pending_after_days": 10,
    "cancel_pending_if_distance_gt_pct": 3.0,
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


def _run(cmd: list[str], cwd: Path, continue_on_error: bool) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True)
    if proc.stdout:
        print(proc.stdout)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr)
    if proc.returncode != 0 and not continue_on_error:
        raise SystemExit(proc.returncode)
    return proc.returncode, proc.stdout, proc.stderr


def _risk_for(candidate: str) -> dict[str, Any]:
    risk = dict(BASE_RISK)
    risk.update(CANDIDATES[candidate])
    return risk


def _run_replay(candidate: str, universe: str, tickers: list[str], args: argparse.Namespace) -> dict[str, Any]:
    root = _repo_root()
    risk = _risk_for(candidate)
    scenario = f"{candidate}__{universe}"
    out_dir = Path(args.out_dir) / _safe(scenario)

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

    print("\n" + "=" * DISPLAY_WIDTH)
    print(f"  COST-AWARE UNIVERSE PRUNING — {scenario}")
    print("=" * DISPLAY_WIDTH)
    print(f"  Tickers: {', '.join(tickers)}")
    print(
        "  Risk   : "
        f"score>={risk['min_score']} new/day={risk['max_new_trades_per_day']} "
        f"open={risk['max_open_trades']} reserved={risk['max_reserved_trades']} "
        f"bucket={risk['max_bucket_exposure_pct']}% stop={risk['default_stop_pct']:.2%}"
    )
    print("-" * DISPLAY_WIDTH)

    rc, _, _ = _run(cmd, root, args.continue_on_error)
    if rc != 0:
        return {
            "candidate": candidate,
            "universe": universe,
            "scenario": scenario,
            "out_dir": str(out_dir),
            "tickers": ",".join(tickers),
            "ticker_count": len(tickers),
            "error": f"exit_code_{rc}",
            **risk,
        }

    summary = _read_json(out_dir / "replay_summary.json")
    trades = _read_csv(out_dir / "replay_trades.csv")
    realized = trades[trades.get("status", pd.Series(dtype=str)).astype(str).isin(["target_hit", "stop_hit", "expired", "manual_closed"])] if not trades.empty else pd.DataFrame()

    return {
        "candidate": candidate,
        "universe": universe,
        "scenario": scenario,
        "out_dir": str(out_dir),
        "tickers": ",".join(tickers),
        "ticker_count": len(tickers),
        "total_orders": summary.get("total_orders"),
        "realized": summary.get("closed_realized_trades", len(realized)),
        "cancelled": summary.get("cancelled_orders"),
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
        "realized_pnl": summary.get("total_realized_pnl"),
        "final_equity": summary.get("final_equity"),
        "max_open_exposure_pct": summary.get("max_open_exposure_pct"),
        "max_reserved_exposure_pct": summary.get("max_reserved_exposure_pct"),
        **risk,
    }


def _print_replay_table(df: pd.DataFrame) -> None:
    print("\n" + "=" * DISPLAY_WIDTH)
    print("  COST-AWARE UNIVERSE PRUNING — FRICTIONLESS REPLAY SUMMARY")
    print("=" * DISPLAY_WIDTH)
    if df.empty:
        print("  No rows.")
        return
    view = df.copy()
    view["calmar_num"] = pd.to_numeric(view.get("calmar"), errors="coerce")
    view["cagr_num"] = pd.to_numeric(view.get("cagr_pct"), errors="coerce")
    view = view.sort_values(["calmar_num", "cagr_num"], ascending=[False, False])
    print(
        f"  {'Scenario':<58} {'Tick':>4} {'Trades':>7} {'CAGR':>8} {'Ret':>8} {'MaxDD':>8} "
        f"{'Sharpe':>8} {'Sortino':>8} {'Calmar':>8} {'Win%':>8} {'Exp':>8} {'FinalEq':>12}"
    )
    for _, r in view.iterrows():
        print(
            f"  {str(r.get('scenario')):<58} {int(r.get('ticker_count') or 0):>4} {int(r.get('realized') or 0):>7} "
            f"{_fmt(r.get('cagr_pct')):>8} {_fmt(r.get('return_pct')):>8} {_fmt(r.get('maxdd_pct')):>8} "
            f"{_fmt(r.get('sharpe'), 3):>8} {_fmt(r.get('sortino'), 3):>8} {_fmt(r.get('calmar'), 3):>8} "
            f"{_fmt(r.get('win_rate_pct')):>8} {_fmt(r.get('expectancy_pct')):>8} ${float(r.get('final_equity') or 0):>11,.0f}"
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
    print("  RUNNING ASSET-CLASS COST STRESS FOR UNIVERSE PRUNING OUTPUTS")
    print("=" * DISPLAY_WIDTH)
    _run(cmd, _repo_root(), args.continue_on_error)


def _run_attribution(rows: list[dict[str, Any]], args: argparse.Namespace) -> None:
    if not args.run_attribution:
        return
    dirs = [str(Path(r["out_dir"])) for r in rows if not r.get("error")]
    if not dirs:
        print("\nNo successful replay dirs available for attribution.")
        return
    cmd = [
        sys.executable,
        "scripts/analyze_cost_adjusted_trade_attribution.py",
        "--candidate-dirs", *dirs,
        "--cost-cases", *args.attribution_cost_cases,
        "--out-dir", str(Path(args.out_dir) / "cost_attribution"),
        "--capital", str(args.capital),
        "--top-n", str(args.top_n),
    ]
    print("\n" + "=" * DISPLAY_WIDTH)
    print("  RUNNING ASSET-CLASS COST ATTRIBUTION FOR UNIVERSE PRUNING OUTPUTS")
    print("=" * DISPLAY_WIDTH)
    _run(cmd, _repo_root(), args.continue_on_error)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run cost-aware universe pruning sweep for trade idea candidates")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--start", default="2019-01-01")
    p.add_argument("--end", default="2025-12-30")
    p.add_argument("--replay-start", default="2020-01-01")
    p.add_argument("--out-dir", default="artifacts/trade_idea_cost_aware_universe_pruning")
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--candidates", nargs="+", default=list(CANDIDATES.keys()), choices=list(CANDIDATES.keys()))
    p.add_argument("--universes", nargs="+", default=list(UNIVERSES.keys()), choices=list(UNIVERSES.keys()))
    p.add_argument("--progress-every", type=int, default=0)
    p.add_argument("--record-rejected-orders", action="store_true")
    p.add_argument("--continue-on-error", action="store_true")
    p.add_argument("--run-cost-stress", action="store_true")
    p.add_argument("--cost-cases", nargs="+", default=["asset_base", "asset_conservative", "asset_equity_harsh", "asset_very_harsh"])
    p.add_argument("--write-adjusted-daily", action="store_true")
    p.add_argument("--run-attribution", action="store_true")
    p.add_argument("--attribution-cost-cases", nargs="+", default=["asset_base", "asset_conservative", "asset_very_harsh"])
    p.add_argument("--top-n", type=int, default=10)
    p.add_argument("--extra-replay-args", nargs=argparse.REMAINDER, default=[])
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for candidate in args.candidates:
        for universe in args.universes:
            rows.append(_run_replay(candidate, universe, UNIVERSES[universe], args))
    df = pd.DataFrame(rows)
    df.to_csv(out / "universe_pruning_comparison.csv", index=False)
    (out / "universe_pruning_comparison.json").write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
    _print_replay_table(df)
    print(f"  Comparison CSV : {out / 'universe_pruning_comparison.csv'}")
    print(f"  Comparison JSON: {out / 'universe_pruning_comparison.json'}")
    print("  Verdict        : COST-AWARE UNIVERSE PRUNING RESEARCH ONLY; no broker/runtime execution.")
    _run_cost_stress(rows, args)
    _run_attribution(rows, args)


if __name__ == "__main__":
    main()
