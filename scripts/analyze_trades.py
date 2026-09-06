#!/usr/bin/env python
"""IteraDynamics — Trade diagnostics and turnover analysis.

Reads backtest artifact directories and produces a detailed side-by-side
comparison of trade-level statistics, notional sizes, holding periods, and
turnover metrics.  Designed to answer:

    Why did turnover increase despite fewer trades?

Specifically isolates whether the cause is:
  - Larger trades (full round-trips vs. incremental resizes)
  - Larger exits (position appreciation during long holds)
  - Different exposure levels (0.75 fixed vs. 0.40-0.80 variable)
  - Timing effects (trades concentrated when NAV is larger)

Usage (Windows PowerShell):
    python scripts\\analyze_trades.py ^
        artifacts\\trend_following_BTC_... ^
        artifacts\\trend_following_v2_BTC_... ^
        artifacts\\trend_following_v3_BTC_...

Usage (bash/zsh):
    python scripts/analyze_trades.py \\
        artifacts/trend_following_BTC_... \\
        artifacts/trend_following_v2_BTC_... \\
        artifacts/trend_following_v3_BTC_...
"""

from __future__ import annotations

# Preserve direct-file execution; package imports use normal discovery.
if __package__ in (None, ""):
    try:
        from _checkout_bootstrap import bootstrap as _bootstrap_checkout
    except ModuleNotFoundError as _bootstrap_error:
        if _bootstrap_error.name != "_checkout_bootstrap":
            raise
        from scripts._checkout_bootstrap import bootstrap as _bootstrap_checkout
    _bootstrap_checkout(__file__)


import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd



# ── Data loading ──────────────────────────────────────────────────────────────

def load_artifact(directory: str) -> dict:
    """Load equity_curve.csv, trades.csv, and summary.json from an artifact dir."""
    d = Path(directory)

    summary_path = d / "summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"No summary.json found in: {d}")
    with open(summary_path, encoding="utf-8") as f:
        summary = json.load(f)

    eq_path = d / "equity_curve.csv"
    if not eq_path.exists():
        raise FileNotFoundError(f"No equity_curve.csv found in: {d}")
    eq_df = pd.read_csv(eq_path, index_col=0, parse_dates=True)

    trades_path = d / "trades.csv"
    if not trades_path.exists():
        raise FileNotFoundError(f"No trades.csv found in: {d}")
    trades_df = pd.read_csv(trades_path)

    return {
        "summary": summary,
        "equity": eq_df,
        "trades": trades_df,
        "directory": str(d),
    }


# ── Analysis ──────────────────────────────────────────────────────────────────

def analyze(data: dict) -> dict:
    """Compute all diagnostic metrics for one strategy's artifacts."""
    summary = data["summary"]
    eq_df = data["equity"]
    trades_df = data["trades"]

    strategy_id = summary.get("strategy_id", "unknown")

    # NAV series as a numpy array (bar 0 = index 0)
    eq = eq_df["equity"].values.astype(float)
    mean_nav = float(np.mean(eq))
    initial_nav = float(eq[0]) if len(eq) > 0 else 1.0

    if trades_df.empty or len(trades_df) == 0:
        return {
            "strategy_id": strategy_id,
            "directory": data["directory"],
            "n_trades": 0, "n_buy": 0, "n_sell": 0,
            "buy_notional_avg": 0.0, "buy_notional_med": 0.0, "buy_notional_p90": 0.0,
            "sell_notional_avg": 0.0, "sell_notional_med": 0.0, "sell_notional_p90": 0.0,
            "exit_entry_notional_ratio": 0.0,
            "buy_pct_nav_avg": 0.0, "buy_pct_nav_med": 0.0, "buy_pct_nav_p90": 0.0,
            "sell_pct_nav_avg": 0.0, "sell_pct_nav_med": 0.0, "sell_pct_nav_p90": 0.0,
            "exit_entry_pct_nav_ratio": 0.0,
            "avg_delta_exposure": 0.0,
            "avg_hold_bars": 0.0,
            "turnover_x": 0.0, "turnover_x_nav_adj": 0.0,
            "avg_price_buy": 0.0, "avg_price_sell": 0.0,
            "initial_nav": initial_nav, "mean_nav": mean_nav,
        }

    # Attach NAV at each trade's bar_index
    def nav_at(bar_idx: int) -> float:
        bar_idx = int(bar_idx)
        return float(eq[bar_idx]) if 0 <= bar_idx < len(eq) else mean_nav

    trades_df = trades_df.copy()
    trades_df["nav_at_trade"] = trades_df["bar_index"].apply(nav_at)
    trades_df["notional_pct_nav"] = (
        trades_df["notional_usd"] / trades_df["nav_at_trade"]
    )

    buys = trades_df[trades_df["direction"] == "BUY"]
    sells = trades_df[trades_df["direction"] == "SELL"]

    def pct_stats(series: pd.Series) -> tuple[float, float, float]:
        if series.empty:
            return 0.0, 0.0, 0.0
        a = series.dropna().values
        return float(np.mean(a)), float(np.median(a)), float(np.percentile(a, 90))

    buy_notional_avg, buy_notional_med, buy_notional_p90 = pct_stats(buys["notional_usd"])
    sell_notional_avg, sell_notional_med, sell_notional_p90 = pct_stats(sells["notional_usd"])
    buy_pct_avg, buy_pct_med, buy_pct_p90 = pct_stats(buys["notional_pct_nav"])
    sell_pct_avg, sell_pct_med, sell_pct_p90 = pct_stats(sells["notional_pct_nav"])

    exit_entry_notional_ratio = (
        sell_notional_avg / buy_notional_avg if buy_notional_avg > 0 else 0.0
    )
    exit_entry_pct_nav_ratio = (
        sell_pct_avg / buy_pct_avg if buy_pct_avg > 0 else 0.0
    )

    # Average |delta exposure| per trade — distinguishes full round-trips from resizes
    if "prev_exposure" in trades_df.columns and "new_exposure" in trades_df.columns:
        delta_exp = (trades_df["new_exposure"] - trades_df["prev_exposure"]).abs()
        avg_delta_exposure = float(delta_exp.mean())
    else:
        avg_delta_exposure = 0.0

    # Holding period: pair each BUY with the next SELL bar after it
    sorted_trades = trades_df.sort_values("bar_index")
    buy_bars = sorted_trades[sorted_trades["direction"] == "BUY"]["bar_index"].tolist()
    sell_bars = sorted_trades[sorted_trades["direction"] == "SELL"]["bar_index"].tolist()
    holding_periods: list[int] = []
    si = 0
    for bb in buy_bars:
        while si < len(sell_bars) and sell_bars[si] <= bb:
            si += 1
        if si < len(sell_bars):
            holding_periods.append(sell_bars[si] - bb)
    avg_hold_bars = float(np.mean(holding_periods)) if holding_periods else 0.0

    # Turnover (both denominators)
    total_notional = float(trades_df["notional_usd"].sum())
    turnover_x = total_notional / initial_nav if initial_nav > 0 else 0.0
    turnover_x_nav_adj = total_notional / mean_nav if mean_nav > 0 else 0.0

    # Average BTC price at BUY vs SELL — reveals timing concentration
    avg_price_buy = float(buys["mid_price"].mean()) if not buys.empty else 0.0
    avg_price_sell = float(sells["mid_price"].mean()) if not sells.empty else 0.0

    return {
        "strategy_id": strategy_id,
        "directory": data["directory"],
        # Counts
        "n_trades": len(trades_df),
        "n_buy": len(buys),
        "n_sell": len(sells),
        # Notional USD
        "buy_notional_avg": buy_notional_avg,
        "buy_notional_med": buy_notional_med,
        "buy_notional_p90": buy_notional_p90,
        "sell_notional_avg": sell_notional_avg,
        "sell_notional_med": sell_notional_med,
        "sell_notional_p90": sell_notional_p90,
        "exit_entry_notional_ratio": exit_entry_notional_ratio,
        # Notional as % of NAV at trade time
        "buy_pct_nav_avg": buy_pct_avg,
        "buy_pct_nav_med": buy_pct_med,
        "buy_pct_nav_p90": buy_pct_p90,
        "sell_pct_nav_avg": sell_pct_avg,
        "sell_pct_nav_med": sell_pct_med,
        "sell_pct_nav_p90": sell_pct_p90,
        "exit_entry_pct_nav_ratio": exit_entry_pct_nav_ratio,
        # Resize behavior
        "avg_delta_exposure": avg_delta_exposure,
        # Holding period
        "avg_hold_bars": avg_hold_bars,
        # Turnover
        "turnover_x": turnover_x,
        "turnover_x_nav_adj": turnover_x_nav_adj,
        # Timing
        "avg_price_buy": avg_price_buy,
        "avg_price_sell": avg_price_sell,
        # NAV context
        "initial_nav": initial_nav,
        "mean_nav": mean_nav,
    }


# ── Formatted output ──────────────────────────────────────────────────────────

def print_comparison(results: list[dict]) -> None:
    """Print a formatted side-by-side comparison table."""
    n = len(results)
    strategies = [r["strategy_id"] for r in results]
    col_w = max(24, max(len(s) for s in strategies) + 4)

    def header_str(label: str, *vals) -> str:
        cols = "".join(str(v).rjust(col_w) for v in vals)
        return f"  {label:<44}{cols}"

    def row(label: str, *vals) -> None:
        print(header_str(label, *vals))

    def section(title: str) -> None:
        print()
        width = 44 + col_w * n
        print(f"  {'─' * 3} {title} " + "─" * max(0, width - 7 - len(title)))

    def usd(v: float) -> str:
        return f"${v:>12,.0f}"

    def pct(v: float) -> str:
        return f"{v * 100:>11.1f}%"

    def x_(v: float) -> str:
        return f"{v:>11.2f}x"

    def ratio(v: float) -> str:
        return f"{v:>11.3f}"

    def hrs(v: float) -> str:
        if v >= 24 * 7:
            return f"{v / 24:>10.0f}d"
        return f"{v:>10.0f}h"

    total_w = 46 + col_w * n
    divider = "=" * total_w

    print()
    print(divider)
    print("  TURNOVER DIAGNOSTIC REPORT — IteraDynamics")
    print(divider)
    row("Strategy", *strategies)

    # Trade counts
    section("Trade Counts")
    row("Total trades", *[r["n_trades"] for r in results])
    row("  BUY trades", *[r["n_buy"] for r in results])
    row("  SELL trades", *[r["n_sell"] for r in results])

    # Notional in USD
    section("Notional per Trade — USD at mid-price")
    row("BUY   avg", *[usd(r["buy_notional_avg"]) for r in results])
    row("BUY   median", *[usd(r["buy_notional_med"]) for r in results])
    row("BUY   P90", *[usd(r["buy_notional_p90"]) for r in results])
    row("SELL  avg", *[usd(r["sell_notional_avg"]) for r in results])
    row("SELL  median", *[usd(r["sell_notional_med"]) for r in results])
    row("SELL  P90", *[usd(r["sell_notional_p90"]) for r in results])
    row("Exit / Entry ratio  (USD)", *[ratio(r["exit_entry_notional_ratio"]) for r in results])

    # Notional as % of NAV at trade time
    section("Notional per Trade — % of NAV at trade time")
    print("  (Normalises for portfolio growth; 75% = full-size round-trip)")
    row("BUY   avg", *[pct(r["buy_pct_nav_avg"]) for r in results])
    row("BUY   median", *[pct(r["buy_pct_nav_med"]) for r in results])
    row("BUY   P90", *[pct(r["buy_pct_nav_p90"]) for r in results])
    row("SELL  avg", *[pct(r["sell_pct_nav_avg"]) for r in results])
    row("SELL  median", *[pct(r["sell_pct_nav_med"]) for r in results])
    row("SELL  P90", *[pct(r["sell_pct_nav_p90"]) for r in results])
    row("Exit / Entry ratio  (% NAV)", *[ratio(r["exit_entry_pct_nav_ratio"]) for r in results])

    # Resize behavior
    section("Resize Behavior")
    print("  (Large delta = full round-trips; small delta = incremental resizing)")
    row("Avg |delta exposure| per trade", *[pct(r["avg_delta_exposure"]) for r in results])

    # Holding period
    section("Holding Period")
    row("Avg hold (BUY → next SELL)", *[hrs(r["avg_hold_bars"]) for r in results])

    # Trade timing
    section("Trade Timing — avg BTC price at execution")
    row("Avg BTC price at BUY", *[usd(r["avg_price_buy"]) for r in results])
    row("Avg BTC price at SELL", *[usd(r["avg_price_sell"]) for r in results])

    # NAV context
    section("NAV Context")
    row("Initial NAV", *[usd(r["initial_nav"]) for r in results])
    row("Mean NAV over period", *[usd(r["mean_nav"]) for r in results])
    row("NAV growth factor", *[x_(r["mean_nav"] / r["initial_nav"]) for r in results])

    # Turnover
    section("Turnover")
    print("  turnover_x         = sum(notional) / initial_capital  [standard]")
    print("  turnover_x_nav_adj = sum(notional) / mean(NAV)        [NAV-normalised]")
    row("Turnover  (/ initial capital)", *[x_(r["turnover_x"]) for r in results])
    row("Turnover  (/ mean NAV)", *[x_(r["turnover_x_nav_adj"]) for r in results])

    print()
    print(divider)
    print()
    print("  KEY:")
    print("  Exit/Entry ratio > 1.0  → exits are larger than entries")
    print("                            (position appreciated during hold)")
    print("  Exit/Entry ratio ≈ 1.0  → quick exits with minimal price change")
    print("                            (v1-style whipsaw behaviour)")
    print("  Large avg |delta|       → full binary round-trips (v2/v3)")
    print("  Small avg |delta|       → incremental resizing (v1)")
    print("  Turnover_x_nav_adj      → fairer comparison when equity growth differs")
    print()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(
        description="IteraDynamics trade diagnostics — compare turnover across strategies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "directories",
        nargs="+",
        help="One or more artifact directories (e.g. artifacts/trend_following_BTC_...)",
    )
    args = p.parse_args()

    results = []
    for d in args.directories:
        try:
            data = load_artifact(d)
            result = analyze(data)
            results.append(result)
        except FileNotFoundError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"ERROR processing {d}: {e}", file=sys.stderr)
            sys.exit(1)

    print_comparison(results)


if __name__ == "__main__":
    main()
