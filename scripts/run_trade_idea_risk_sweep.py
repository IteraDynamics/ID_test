#!/usr/bin/env python
"""Run risk-band sweeps for the trade idea replay engine.

This harness answers a specific research question:

    Is the trade idea radar underpowered because the signal is weak, or because
    the current portfolio risk bands are too conservative?

It runs selected universe scenarios across several risk bands, then aggregates
portfolio-level metrics into one comparison table.

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
WEAK_TICKERS = {"USMV", "SMH", "IEF", "SCHD", "RSP", "TLT"}

UNIVERSES = {
    "all_assets": ALL_TICKERS,
    "remove_known_weak_tickers": [x for x in ALL_TICKERS if x not in WEAK_TICKERS],
    "crypto_plus_growth": CRYPTO + GROWTH,
    "crypto_plus_growth_core": CRYPTO + GROWTH_CORE,
    "crypto_only": CRYPTO,
}

RISK_BANDS = {
    "conservative": {
        "default_notional": 10_000,
        "max_new_trades_per_day": 3,
        "max_open_trades": 10,
        "max_reserved_trades": 15,
        "max_gross_exposure_pct": 100,
        "max_ticker_exposure_pct": 20,
        "max_bucket_exposure_pct": 40,
        "cooldown_days": 5,
    },
    "moderate": {
        "default_notional": 15_000,
        "max_new_trades_per_day": 4,
        "max_open_trades": 12,
        "max_reserved_trades": 18,
        "max_gross_exposure_pct": 150,
        "max_ticker_exposure_pct": 30,
        "max_bucket_exposure_pct": 60,
        "cooldown_days": 3,
    },
    "aggressive_institutional": {
        "default_notional": 20_000,
        "max_new_trades_per_day": 5,
        "max_open_trades": 15,
        "max_reserved_trades": 22,
        "max_gross_exposure_pct": 200,
        "max_ticker_exposure_pct": 40,
        "max_bucket_exposure_pct": 80,
        "cooldown_days": 2,
    },
    "very_aggressive": {
        "default_notional": 25_000,
        "max_new_trades_per_day": 6,
        "max_open_trades": 18,
        "max_reserved_trades": 26,
        "max_gross_exposure_pct": 250,
        "max_ticker_exposure_pct": 50,
        "max_bucket_exposure_pct": 100,
        "cooldown_days": 1,
    },
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _safe_name(value: str) -> str:
    return value.replace(" ", "_").replace("/", "_").replace("\\", "_").replace(":", "_")


def _read_summary(path: Path) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _fmt(value: Any, digits: int = 2) -> str:
    try:
        v = float(value)
        return f"{v:.{digits}f}"
    except (TypeError, ValueError):
        return "n/a"


def _run_one(universe_name: str, tickers: list[str], risk_name: str, risk: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    root = _repo_root()
    scenario_name = f"{universe_name}__{risk_name}"
    out_dir = Path(args.out_dir) / _safe_name(scenario_name)

    cmd = [
        sys.executable,
        "scripts/replay_trade_idea_desk_cycle.py",
        "--data-dir", args.data_dir,
        "--start", args.start,
        "--end", args.end,
        "--out-dir", str(out_dir),
        "--capital", str(args.capital),
        "--default-notional", str(risk["default_notional"]),
        "--min-score", str(args.min_score),
        "--max-new-trades-per-day", str(risk["max_new_trades_per_day"]),
        "--max-open-trades", str(risk["max_open_trades"]),
        "--max-reserved-trades", str(risk["max_reserved_trades"]),
        "--max-gross-exposure-pct", str(risk["max_gross_exposure_pct"]),
        "--max-ticker-exposure-pct", str(risk["max_ticker_exposure_pct"]),
        "--max-bucket-exposure-pct", str(risk["max_bucket_exposure_pct"]),
        "--cooldown-days", str(risk["cooldown_days"]),
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

    print("\n" + "=" * 156)
    print(f"  RISK SWEEP — {universe_name} / {risk_name}")
    print("=" * 156)
    print("  Tickers: " + ", ".join(tickers))
    print(
        "  Risk   : "
        f"notional={risk['default_notional']} "
        f"gross={risk['max_gross_exposure_pct']}% "
        f"ticker={risk['max_ticker_exposure_pct']}% "
        f"bucket={risk['max_bucket_exposure_pct']}% "
        f"open={risk['max_open_trades']} reserved={risk['max_reserved_trades']}"
    )
    print("-" * 156)

    proc = subprocess.run(cmd, cwd=str(root), text=True, capture_output=True)
    if proc.stdout:
        print(proc.stdout)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr)
    if proc.returncode != 0:
        result = {
            "scenario": scenario_name,
            "universe": universe_name,
            "risk_band": risk_name,
            "error": f"exit_code_{proc.returncode}",
            "out_dir": str(out_dir),
        }
        if args.continue_on_error:
            return result
        raise SystemExit(proc.returncode)

    summary = _read_summary(out_dir / "replay_summary.json")
    summary["scenario"] = scenario_name
    summary["universe"] = universe_name
    summary["risk_band"] = risk_name
    summary["ticker_count"] = len(tickers)
    summary["tickers"] = ",".join(tickers)
    summary["out_dir"] = str(out_dir)
    summary["risk_settings"] = risk
    return summary


def _row(summary: dict[str, Any]) -> dict[str, Any]:
    risk = summary.get("risk_settings") or {}
    return {
        "scenario": summary.get("scenario"),
        "universe": summary.get("universe"),
        "risk_band": summary.get("risk_band"),
        "ticker_count": summary.get("ticker_count"),
        "default_notional": risk.get("default_notional"),
        "max_gross_exposure_pct": risk.get("max_gross_exposure_pct"),
        "max_ticker_exposure_pct": risk.get("max_ticker_exposure_pct"),
        "max_bucket_exposure_pct": risk.get("max_bucket_exposure_pct"),
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
        "max_open_exposure_pct": summary.get("max_open_exposure_pct"),
        "max_reserved_exposure_pct": summary.get("max_reserved_exposure_pct"),
        "best_day_pct": summary.get("best_day_pct"),
        "worst_day_pct": summary.get("worst_day_pct"),
        "out_dir": summary.get("out_dir"),
        "tickers": summary.get("tickers"),
        "error": summary.get("error"),
    }


def _print_table(df: pd.DataFrame) -> None:
    print("\n" + "=" * 190)
    print("  TRADE IDEA REPLAY — RISK SWEEP COMPARISON")
    print("=" * 190)
    if df.empty:
        print("  No scenario results.")
        return

    view = df.copy()
    view["score"] = pd.to_numeric(view.get("calmar"), errors="coerce").fillna(-999) + pd.to_numeric(view.get("cagr_pct"), errors="coerce").fillna(0) / 100.0
    view = view.sort_values(["score", "cagr_pct"], ascending=[False, False])

    print(
        f"  {'Universe':<29} {'Risk':<26} {'Tkr':>4} "
        f"{'CAGR':>8} {'Ret':>8} {'MaxDD':>8} {'Sharpe':>8} {'Sortino':>8} {'Calmar':>8} "
        f"{'AnnVol':>8} {'Win%':>8} {'Exp':>8} {'WorstD':>8} {'Realized':>9}"
    )
    for _, r in view.iterrows():
        print(
            f"  {str(r.get('universe')):<29} {str(r.get('risk_band')):<26} {int(r.get('ticker_count') or 0):>4} "
            f"{_fmt(r.get('cagr_pct')):>8} {_fmt(r.get('return_pct')):>8} {_fmt(r.get('maxdd_pct')):>8} "
            f"{_fmt(r.get('sharpe'), 3):>8} {_fmt(r.get('sortino'), 3):>8} {_fmt(r.get('calmar'), 3):>8} "
            f"{_fmt(r.get('ann_vol_pct')):>8} {_fmt(r.get('win_rate_pct')):>8} {_fmt(r.get('expectancy_pct')):>8} "
            f"{_fmt(r.get('worst_day_pct')):>8} {int(r.get('realized') or 0):>9}"
        )
    print("=" * 190)


def _print_best_by_universe(df: pd.DataFrame) -> None:
    if df.empty or "universe" not in df.columns:
        return
    print("\n" + "=" * 190)
    print("  BEST RISK BAND BY UNIVERSE")
    print("=" * 190)
    numeric = df.copy()
    numeric["calmar_num"] = pd.to_numeric(numeric.get("calmar"), errors="coerce")
    numeric["cagr_num"] = pd.to_numeric(numeric.get("cagr_pct"), errors="coerce")
    for universe, g in numeric.groupby("universe"):
        g = g.sort_values(["calmar_num", "cagr_num"], ascending=[False, False])
        top = g.iloc[0]
        print(
            f"  {universe:<29} -> {str(top.get('risk_band')):<26} "
            f"CAGR={_fmt(top.get('cagr_pct')):>7}%  "
            f"MaxDD={_fmt(top.get('maxdd_pct')):>7}%  "
            f"Sharpe={_fmt(top.get('sharpe'), 3):>7}  "
            f"Calmar={_fmt(top.get('calmar'), 3):>7}"
        )
    print("=" * 190)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run risk-band sweeps against trade idea replay")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--start", default="2019-01-01")
    p.add_argument("--end", default="2025-12-30")
    p.add_argument("--replay-start", default="2020-01-01")
    p.add_argument("--out-dir", default="artifacts/trade_idea_risk_sweep")
    p.add_argument("--universes", nargs="+", default=["all_assets", "remove_known_weak_tickers", "crypto_plus_growth_core", "crypto_plus_growth"], choices=list(UNIVERSES.keys()))
    p.add_argument("--risk-bands", nargs="+", default=list(RISK_BANDS.keys()), choices=list(RISK_BANDS.keys()))
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--min-score", type=float, default=80.0)
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
    for universe_name in args.universes:
        tickers = UNIVERSES[universe_name]
        for risk_name in args.risk_bands:
            summaries.append(_run_one(universe_name, tickers, risk_name, RISK_BANDS[risk_name], args))

    rows = [_row(x) for x in summaries]
    df = pd.DataFrame(rows)
    df.to_csv(out / "risk_sweep_comparison.csv", index=False)
    (out / "risk_sweep_comparison.json").write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")

    _print_table(df)
    _print_best_by_universe(df)
    print(f"  Comparison CSV : {out / 'risk_sweep_comparison.csv'}")
    print(f"  Comparison JSON: {out / 'risk_sweep_comparison.json'}")
    print("  Verdict        : RISK SWEEP RESEARCH ONLY; no broker/runtime execution.\n")


if __name__ == "__main__":
    main()
