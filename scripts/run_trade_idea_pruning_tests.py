#!/usr/bin/env python
"""Run pruning scenarios for the trade idea replay engine.

This is a convenience harness around replay_trade_idea_desk_cycle.py. It runs a
small suite of focused universe-pruning tests and aggregates portfolio metrics
so we can quickly compare whether the radar improves when weak sleeves/tickers
are removed.

Research/paper only. No runtime, broker, or live execution code is modified.
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
    "QQQ", "SMH", "XLK", "IGV", "XLC",
    "SPY", "RSP", "MTUM", "QUAL", "IWF", "IWM",
    "USMV", "SPLV", "SCHD",
    "TLT", "IEF", "GLD", "XLE", "XLF",
    "BTC-USD", "ETH-USD",
]

CRYPTO = ["BTC-USD", "ETH-USD"]
GROWTH = ["QQQ", "SMH", "XLK", "IGV", "XLC", "MTUM", "IWF", "IWM"]
GROWTH_CORE = ["QQQ", "XLK", "IGV", "XLC", "IWF", "XLF"]
MACRO = ["TLT", "IEF", "GLD", "XLE", "XLF"]
DEFENSIVE = ["USMV", "SPLV", "SCHD", "QUAL", "RSP", "SPY"]
WEAK_TICKERS = {"USMV", "SMH", "IEF", "SCHD", "RSP", "TLT"}

SCENARIOS = {
    "all_assets": ALL_TICKERS,
    "crypto_only": CRYPTO,
    "growth_only": GROWTH,
    "crypto_plus_growth": CRYPTO + GROWTH,
    "crypto_plus_growth_core": CRYPTO + GROWTH_CORE,
    "no_defensive_quality": [x for x in ALL_TICKERS if x not in DEFENSIVE],
    "no_macro_no_defensive": [x for x in ALL_TICKERS if x not in set(MACRO + DEFENSIVE)],
    "remove_known_weak_tickers": [x for x in ALL_TICKERS if x not in WEAK_TICKERS],
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _read_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _run_replay(name: str, tickers: list[str], args: argparse.Namespace) -> dict[str, Any]:
    root = _repo_root()
    out_dir = Path(args.out_dir) / name
    cmd = [
        sys.executable,
        "scripts/replay_trade_idea_desk_cycle.py",
        "--data-dir", args.data_dir,
        "--start", args.start,
        "--end", args.end,
        "--out-dir", str(out_dir),
        "--capital", str(args.capital),
        "--default-notional", str(args.default_notional),
        "--min-score", str(args.min_score),
        "--max-new-trades-per-day", str(args.max_new_trades_per_day),
        "--max-open-trades", str(args.max_open_trades),
        "--max-reserved-trades", str(args.max_reserved_trades),
        "--max-gross-exposure-pct", str(args.max_gross_exposure_pct),
        "--max-ticker-exposure-pct", str(args.max_ticker_exposure_pct),
        "--max-bucket-exposure-pct", str(args.max_bucket_exposure_pct),
        "--cooldown-days", str(args.cooldown_days),
        "--cancel-pending-after-days", str(args.cancel_pending_after_days),
        "--cancel-pending-if-distance-gt-pct", str(args.cancel_pending_if_distance_gt_pct),
        "--progress-every", str(args.progress_every),
        "--tickers", *tickers,
    ]
    if args.replay_start:
        cmd.extend(["--replay-start", args.replay_start])
    if not args.open_watchlist:
        cmd.append("--no-open-watchlist")
    if not args.cancel_stale_pending:
        cmd.append("--no-cancel-stale-pending")
    if args.allow_multiple_trades_per_ticker:
        cmd.append("--allow-multiple-trades-per-ticker")
    if args.record_rejected_orders:
        cmd.append("--record-rejected-orders")
    if args.extra_replay_args:
        cmd.extend(args.extra_replay_args)

    print("\n" + "=" * 150)
    print(f"  PRUNING SCENARIO — {name}")
    print("=" * 150)
    print("  Tickers: " + ", ".join(tickers))
    print("-" * 150)
    proc = subprocess.run(cmd, cwd=str(root), text=True, capture_output=True)
    if proc.stdout:
        print(proc.stdout)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr)
    if proc.returncode != 0:
        if args.continue_on_error:
            return {"scenario": name, "error": f"exit_code_{proc.returncode}", "tickers": ",".join(tickers)}
        raise SystemExit(proc.returncode)
    summary = _read_summary(out_dir / "replay_summary.json")
    summary["scenario"] = name
    summary["ticker_count"] = len(tickers)
    summary["tickers"] = ",".join(tickers)
    summary["out_dir"] = str(out_dir)
    return summary


def _row(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "scenario": summary.get("scenario"),
        "ticker_count": summary.get("ticker_count"),
        "orders": summary.get("total_orders"),
        "realized": summary.get("closed_realized_trades"),
        "cancelled": summary.get("cancelled_orders"),
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
        "out_dir": summary.get("out_dir"),
        "tickers": summary.get("tickers"),
        "error": summary.get("error"),
    }


def _fmt(value: Any, digits: int = 2) -> str:
    try:
        v = float(value)
        return f"{v:.{digits}f}"
    except (TypeError, ValueError):
        return "n/a"


def _print_table(df: pd.DataFrame) -> None:
    print("\n" + "=" * 174)
    print("  TRADE IDEA REPLAY — PRUNING COMPARISON")
    print("=" * 174)
    if df.empty:
        print("  No scenario results.")
        return
    view = df.sort_values(["calmar", "cagr_pct"], ascending=[False, False])
    print(f"  {'Scenario':<28} {'Tkr':>4} {'CAGR':>8} {'Ret':>8} {'MaxDD':>8} {'Sharpe':>8} {'Sortino':>8} {'Calmar':>8} {'Win%':>8} {'Exp':>8} {'Realized':>9}")
    for _, r in view.iterrows():
        print(
            f"  {str(r.get('scenario')):<28} {int(r.get('ticker_count') or 0):>4} "
            f"{_fmt(r.get('cagr_pct')):>8} {_fmt(r.get('return_pct')):>8} {_fmt(r.get('maxdd_pct')):>8} "
            f"{_fmt(r.get('sharpe'), 3):>8} {_fmt(r.get('sortino'), 3):>8} {_fmt(r.get('calmar'), 3):>8} "
            f"{_fmt(r.get('win_rate_pct')):>8} {_fmt(r.get('expectancy_pct')):>8} {int(r.get('realized') or 0):>9}"
        )
    print("=" * 174)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run pruning scenarios against trade idea replay")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--start", default="2019-01-01")
    p.add_argument("--end", default="2025-12-30")
    p.add_argument("--replay-start", default="2020-01-01")
    p.add_argument("--out-dir", default="artifacts/trade_idea_pruning")
    p.add_argument("--scenarios", nargs="+", default=list(SCENARIOS.keys()), choices=list(SCENARIOS.keys()))
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--default-notional", type=float, default=10_000.0)
    p.add_argument("--min-score", type=float, default=80.0)
    p.add_argument("--max-new-trades-per-day", type=int, default=3)
    p.add_argument("--max-open-trades", type=int, default=10)
    p.add_argument("--max-reserved-trades", type=int, default=15)
    p.add_argument("--max-gross-exposure-pct", type=float, default=100.0)
    p.add_argument("--max-ticker-exposure-pct", type=float, default=20.0)
    p.add_argument("--max-bucket-exposure-pct", type=float, default=40.0)
    p.add_argument("--cooldown-days", type=int, default=5)
    p.add_argument("--cancel-pending-after-days", type=int, default=10)
    p.add_argument("--cancel-pending-if-distance-gt-pct", type=float, default=3.0)
    p.add_argument("--open-watchlist", action="store_true", default=True)
    p.add_argument("--no-open-watchlist", dest="open_watchlist", action="store_false")
    p.add_argument("--cancel-stale-pending", action="store_true", default=True)
    p.add_argument("--no-cancel-stale-pending", dest="cancel_stale_pending", action="store_false")
    p.add_argument("--allow-multiple-trades-per-ticker", action="store_true")
    p.add_argument("--record-rejected-orders", action="store_true")
    p.add_argument("--progress-every", type=int, default=0)
    p.add_argument("--continue-on-error", action="store_true")
    p.add_argument("--extra-replay-args", nargs=argparse.REMAINDER, default=[])
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    summaries = []
    for name in args.scenarios:
        summaries.append(_run_replay(name, SCENARIOS[name], args))
    rows = [_row(x) for x in summaries]
    df = pd.DataFrame(rows)
    df.to_csv(out / "pruning_comparison.csv", index=False)
    (out / "pruning_comparison.json").write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
    _print_table(df)
    print(f"  Comparison CSV : {out / 'pruning_comparison.csv'}")
    print(f"  Comparison JSON: {out / 'pruning_comparison.json'}")
    print("  Verdict        : PRUNING RESEARCH ONLY; no broker/runtime execution.\n")


if __name__ == "__main__":
    main()
