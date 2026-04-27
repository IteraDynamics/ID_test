#!/usr/bin/env python
"""ETH/BTC relative-rotation standalone backtest.

Runs the ETH/BTC relative-rotation strategy (v1) against BTC and ETH 1H OHLCV
data.  Uses a custom dual-asset portfolio runner — the single-asset
backtest_engine cannot model simultaneous BTC + ETH positions correctly.

Reuses: load_ohlcv, validate_ohlcv, ExecutionConfig, compute_fill,
        compute_atr_pct_series from the existing research harness.

Output: equity_curve.csv compatible with scripts/run_blend_analysis.py.

Usage
-----
python scripts/run_ethbtc_rotation_backtest.py \\
    --btc-data data/btcusd_3600s_2019-01-01_to_2025-12-30.csv \\
    --eth-data data/ethusd_3600s_2019-01-01_to_2025-12-30.csv

PowerShell (single line):
    python scripts\\run_ethbtc_rotation_backtest.py --btc-data "data\\btcusd_3600s_2019-01-01_to_2025-12-30.csv" --eth-data "data\\ethusd_3600s_2019-01-01_to_2025-12-30.csv"
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from research.harness.data_loader import load_ohlcv, validate_ohlcv
from research.harness.execution_model import (
    ExecutionConfig,
    compute_atr_pct_series,
    compute_fill,
)
from research.strategies.ethbtc_ratio import build_ratio_df
from research.strategies.ethbtc_relative_rotation_v1 import (
    BTC_FAVORED,
    CONFIRM_BARS,
    ETH_FAVORED,
    FAST_EMA,
    MIN_HOLD_BARS,
    MIN_REL_SPREAD,
    NEUTRAL,
    SLOW_EMA,
    STRATEGY_ID,
    compute_rotation_signal,
    signal_to_allocation,
)


# ── Trade record ───────────────────────────────────────────────────────────────

@dataclass
class RotationTrade:
    bar_index: int
    timestamp: str
    asset: str
    direction: str
    notional_usd: float
    fee_usd: float
    slippage_usd: float
    spread_usd: float
    cost_bps: float
    nav_before: float
    btc_frac_after: float
    eth_frac_after: float
    signal_label: str


# ── Performance helpers ────────────────────────────────────────────────────────

def _perf(eq: pd.Series, label: str) -> dict[str, Any]:
    """Compute standard metrics directly from an equity curve series."""
    eq = eq.dropna()
    if len(eq) < 2:
        return {k: 0.0 for k in ("label", "total_ret", "cagr", "max_dd", "sharpe", "calmar", "ann_vol")}

    delta_s = (eq.index[-1] - eq.index[0]).total_seconds()
    n_gaps = len(eq) - 1
    bar_sec = delta_s / n_gaps if n_gaps > 0 and delta_s > 0 else 3600.0
    bars_per_year = 365.25 * 24 * 3600 / bar_sec

    initial, final = float(eq.iloc[0]), float(eq.iloc[-1])
    years = len(eq) / bars_per_year
    total_ret = (final / initial - 1.0) * 100.0
    cagr = ((final / initial) ** (1.0 / max(years, 1 / 365)) - 1.0) * 100.0

    running_max = eq.cummax()
    max_dd = float(((eq - running_max) / running_max).min()) * 100.0

    bar_rets = eq.pct_change().dropna()
    std = float(bar_rets.std())
    ann_vol = std * np.sqrt(bars_per_year) * 100.0
    sharpe = float(bar_rets.mean() / std * np.sqrt(bars_per_year)) if std > 1e-12 else 0.0
    calmar = cagr / abs(max_dd) if abs(max_dd) > 1e-6 else 0.0

    return {
        "label": label,
        "total_ret": total_ret,
        "cagr": cagr,
        "max_dd": max_dd,
        "sharpe": sharpe,
        "calmar": calmar,
        "ann_vol": ann_vol,
    }


def _print_row(d: dict, corr: float | None = None) -> None:
    corr_str = f"{corr:>+.3f}" if corr is not None else "   n/a"
    print(
        f"  {d['label']:<32}"
        f"  {d['total_ret']:>+8.2f}%"
        f"  {d['cagr']:>+7.2f}%"
        f"  {d['max_dd']:>8.2f}%"
        f"  {d['sharpe']:>7.3f}"
        f"  {d['calmar']:>7.3f}"
        f"  {d['ann_vol']:>7.2f}%"
        f"  {corr_str}"
    )


# ── Core backtest ──────────────────────────────────────────────────────────────

def run_rotation_backtest(
    btc_df: pd.DataFrame,
    eth_df: pd.DataFrame,
    exec_config: ExecutionConfig,
    initial_capital: float,
    rebalance_threshold: float,
) -> tuple[pd.Series, pd.Series, pd.Series, list[RotationTrade], dict[str, Any]]:
    """Run the dual-asset rotation backtest.

    Returns
    -------
    equity_curve : pd.Series
        NAV at every bar (same index as common period).
    btc_alloc_series : pd.Series
        BTC allocation fraction at every bar.
    signal_series : pd.Series
        Rotation signal (+1, 0, -1) at every bar.
    trades : list[RotationTrade]
        Every individual asset trade executed.
    stats : dict
        Aggregate rotation statistics (fees, slippage, rotation count, etc.).
    """
    ratio_df = build_ratio_df(btc_df, eth_df)
    common_idx = ratio_df.index
    btc_a = btc_df.loc[common_idx]
    eth_a = eth_df.loc[common_idx]

    signal_series = compute_rotation_signal(ratio_df)
    btc_atr = compute_atr_pct_series(btc_a)
    eth_atr = compute_atr_pct_series(eth_a)

    n = len(common_idx)
    equity_arr = np.zeros(n, dtype=float)
    btc_alloc_arr = np.zeros(n, dtype=float)

    cash = float(initial_capital)
    btc_units = 0.0
    eth_units = 0.0
    trades: list[RotationTrade] = []

    total_fees = 0.0
    total_slippage = 0.0
    n_rotation_events = 0
    prev_signal = NEUTRAL

    btc_close = btc_a["close"].values
    eth_close = eth_a["close"].values
    btc_atr_v = btc_atr.values
    eth_atr_v = eth_atr.values
    signal_v = signal_series.values

    for i in range(n):
        bp = float(btc_close[i])
        ep = float(eth_close[i])
        ab = float(btc_atr_v[i])
        ae = float(eth_atr_v[i])
        ts = str(common_idx[i])

        nav = cash + btc_units * bp + eth_units * ep

        sig = int(signal_v[i])
        alloc = signal_to_allocation(sig)
        target_btc = alloc.btc_frac
        target_eth = alloc.eth_frac

        curr_btc = (btc_units * bp / nav) if nav > 1e-9 else 0.0
        curr_eth = (eth_units * ep / nav) if nav > 1e-9 else 0.0

        d_btc = target_btc - curr_btc
        d_eth = target_eth - curr_eth

        if abs(d_btc) >= rebalance_threshold or abs(d_eth) >= rebalance_threshold:
            if sig != prev_signal and i > 0:
                n_rotation_events += 1
            nav_before = nav

            # ── BTC leg ───────────────────────────────────────────────
            if abs(d_btc) >= 0.001:
                btc_notional = abs(d_btc * nav)
                btc_dir = "BUY" if d_btc > 0 else "SELL"
                fill_b = compute_fill(bp, btc_notional, nav, ab, btc_dir, exec_config)

                if btc_dir == "BUY":
                    btc_units += btc_notional / fill_b.effective_price
                    cash -= btc_notional + fill_b.fee_usd
                else:
                    btc_units = max(0.0, btc_units - btc_notional / fill_b.effective_price)
                    cash += btc_notional - fill_b.fee_usd

                total_fees += fill_b.fee_usd
                total_slippage += fill_b.slippage_usd + fill_b.spread_usd
                trades.append(RotationTrade(
                    bar_index=i, timestamp=ts, asset="BTC", direction=btc_dir,
                    notional_usd=btc_notional, fee_usd=fill_b.fee_usd,
                    slippage_usd=fill_b.slippage_usd, spread_usd=fill_b.spread_usd,
                    cost_bps=fill_b.cost_bps, nav_before=nav_before,
                    btc_frac_after=target_btc, eth_frac_after=target_eth,
                    signal_label=alloc.label,
                ))

            # Re-mark after BTC leg before sizing ETH
            nav = cash + btc_units * bp + eth_units * ep

            # ── ETH leg ───────────────────────────────────────────────
            if abs(d_eth) >= 0.001:
                eth_notional = abs(d_eth * nav)
                eth_dir = "BUY" if d_eth > 0 else "SELL"
                fill_e = compute_fill(ep, eth_notional, nav, ae, eth_dir, exec_config)

                if eth_dir == "BUY":
                    eth_units += eth_notional / fill_e.effective_price
                    cash -= eth_notional + fill_e.fee_usd
                else:
                    eth_units = max(0.0, eth_units - eth_notional / fill_e.effective_price)
                    cash += eth_notional - fill_e.fee_usd

                total_fees += fill_e.fee_usd
                total_slippage += fill_e.slippage_usd + fill_e.spread_usd
                trades.append(RotationTrade(
                    bar_index=i, timestamp=ts, asset="ETH", direction=eth_dir,
                    notional_usd=eth_notional, fee_usd=fill_e.fee_usd,
                    slippage_usd=fill_e.slippage_usd, spread_usd=fill_e.spread_usd,
                    cost_bps=fill_e.cost_bps, nav_before=nav_before,
                    btc_frac_after=target_btc, eth_frac_after=target_eth,
                    signal_label=alloc.label,
                ))

        prev_signal = sig
        nav = cash + btc_units * bp + eth_units * ep
        equity_arr[i] = nav
        btc_alloc_arr[i] = (btc_units * bp / nav) if nav > 1e-9 else 0.0

    total_notional = sum(t.notional_usd for t in trades)
    years_elapsed = (
        (common_idx[-1] - common_idx[0]).total_seconds() / (365.25 * 24 * 3600)
        if len(common_idx) > 1 else 1.0
    )

    # Compute rotation event count from signal transitions (more robust than loop counter)
    signal_arr = signal_series.values
    n_transitions = int(np.sum(np.diff(signal_arr.astype(int)) != 0))

    stats: dict[str, Any] = {
        "n_rotation_events": n_transitions,
        "rotations_per_year": round(n_transitions / max(years_elapsed, 0.01), 1),
        "n_trades": len(trades),
        "total_fees_usd": round(total_fees, 2),
        "total_slippage_usd": round(total_slippage, 2),
        "total_cost_usd": round(total_fees + total_slippage, 2),
        "total_notional_usd": round(total_notional, 2),
        "avg_btc_alloc_pct": round(float(np.mean(btc_alloc_arr)) * 100, 1),
        "avg_eth_alloc_pct": round((1.0 - float(np.mean(btc_alloc_arr))) * 100, 1),
        "pct_time_eth_favored": round(float(np.mean(signal_arr == ETH_FAVORED)) * 100, 1),
        "pct_time_neutral": round(float(np.mean(signal_arr == NEUTRAL)) * 100, 1),
        "pct_time_btc_favored": round(float(np.mean(signal_arr == BTC_FAVORED)) * 100, 1),
    }

    equity_series = pd.Series(equity_arr, index=common_idx, name="equity")
    btc_alloc_series = pd.Series(btc_alloc_arr, index=common_idx, name="btc_alloc")

    return equity_series, btc_alloc_series, signal_series, trades, stats


# ── Baselines ──────────────────────────────────────────────────────────────────

def _compute_baselines(
    btc_df: pd.DataFrame,
    eth_df: pd.DataFrame,
    initial_capital: float,
    common_idx: pd.DatetimeIndex,
) -> dict[str, pd.Series]:
    """Buy-and-hold baselines (no costs, no rebalancing)."""
    btc_close = btc_df.loc[common_idx, "close"]
    eth_close = eth_df.loc[common_idx, "close"]

    btc_norm = btc_close / float(btc_close.iloc[0]) * initial_capital
    eth_norm = eth_close / float(eth_close.iloc[0]) * initial_capital
    half_half = 0.5 * btc_norm + 0.5 * eth_norm

    return {
        "BTC_BnH": btc_norm.rename("equity"),
        "ETH_BnH": eth_norm.rename("equity"),
        "50_50_BnH": half_half.rename("equity"),
    }


# ── Year-slice helper ──────────────────────────────────────────────────────────

def _year_perf(eq: pd.Series, year: int) -> str:
    """Return CAGR string for a single calendar year, or 'n/a' if no data."""
    ys = str(year)
    sl = eq[ys] if ys in eq.index.year.astype(str).values else pd.Series([], dtype=float)
    if len(sl) < 2:
        return "  n/a "
    r = (float(sl.iloc[-1]) / float(sl.iloc[0]) - 1.0) * 100.0
    return f"{r:>+7.1f}%"


# ── CLI ────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="ETH/BTC relative-rotation backtest",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--btc-data", required=True, help="Path to BTC 1H OHLCV CSV")
    p.add_argument("--eth-data", required=True, help="Path to ETH 1H OHLCV CSV")
    p.add_argument("--start", default=None, help="Start date YYYY-MM-DD")
    p.add_argument("--end", default=None, help="End date YYYY-MM-DD")
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--fee", type=float, default=0.0006)
    p.add_argument("--base-slippage", type=float, default=3.0, help="bps")
    p.add_argument("--slippage-vol-factor", type=float, default=50.0)
    p.add_argument("--rebalance-threshold", type=float, default=0.05,
                   help="Min absolute allocation change to trigger a trade")
    p.add_argument("--out-dir", default=None, help="Artifact output directory")
    p.add_argument("--no-save", action="store_true", help="Skip saving artifacts")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    # ── Load data ─────────────────────────────────────────────────────
    print(f"\nLoading BTC:  {args.btc_data}")
    btc_df = load_ohlcv(args.btc_data, start=args.start, end=args.end, asset="BTC")
    for w in validate_ohlcv(btc_df):
        print(f"  [WARN] BTC: {w}")

    print(f"Loading ETH:  {args.eth_data}")
    eth_df = load_ohlcv(args.eth_data, start=args.start, end=args.end, asset="ETH")
    for w in validate_ohlcv(eth_df):
        print(f"  [WARN] ETH: {w}")

    common_idx = btc_df.index.intersection(eth_df.index)
    print(
        f"Common period: {str(common_idx[0])[:10]} → {str(common_idx[-1])[:10]}"
        f"  ({len(common_idx):,} bars)"
    )

    exec_config = ExecutionConfig(
        taker_fee_rate=args.fee,
        base_slippage_bps=args.base_slippage,
        slippage_vol_factor=args.slippage_vol_factor,
    )

    # ── Run rotation strategy ──────────────────────────────────────────
    equity, btc_alloc, signal, trades, stats = run_rotation_backtest(
        btc_df=btc_df,
        eth_df=eth_df,
        exec_config=exec_config,
        initial_capital=args.capital,
        rebalance_threshold=args.rebalance_threshold,
    )

    # ── Baselines ──────────────────────────────────────────────────────
    baselines = _compute_baselines(btc_df, eth_df, args.capital, common_idx)

    # ── Performance metrics ────────────────────────────────────────────
    rotation_perf = _perf(equity, "ETHBTC_Rotation_v1")
    btc_perf = _perf(baselines["BTC_BnH"], "BTC Buy-and-Hold")
    eth_perf = _perf(baselines["ETH_BnH"], "ETH Buy-and-Hold")
    half_perf = _perf(baselines["50_50_BnH"], "50/50 Buy-and-Hold")

    # Correlations vs 50/50
    def _corr(a: pd.Series, b: pd.Series) -> float:
        da = a.resample("1D").last().dropna().pct_change().dropna()
        db = b.resample("1D").last().dropna().pct_change().dropna()
        common = da.index.intersection(db.index)
        if len(common) < 5:
            return float("nan")
        return float(da.loc[common].corr(db.loc[common]))

    # ── Print summary ──────────────────────────────────────────────────
    w = 110
    sep = "=" * w
    print("\n" + sep)
    print(f"  ETH/BTC RELATIVE ROTATION v1 — Standalone Backtest")
    print(f"  Period: {str(common_idx[0])[:10]} → {str(common_idx[-1])[:10]}  "
          f"({len(common_idx):,} bars)")
    print(f"  Capital: ${args.capital:,.0f}  "
          f"Fee: {args.fee*10000:.1f}bps  "
          f"BaseSlip: {args.base_slippage:.0f}bps  "
          f"VolFactor: {args.slippage_vol_factor:.0f}")
    print(sep)
    print(f"  Strategy params: FAST_EMA={FAST_EMA}  SLOW_EMA={SLOW_EMA}  "
          f"CONFIRM={CONFIRM_BARS}  MIN_HOLD={MIN_HOLD_BARS}  "
          f"MIN_SPREAD={MIN_REL_SPREAD*100:.1f}%")
    print(sep)
    print(
        f"  {'Strategy':<32}  {'TotRet':>9}  {'CAGR':>8}  {'MaxDD':>9}"
        f"  {'Sharpe':>8}  {'Calmar':>8}  {'AnnVol':>8}  {'CorrHalf':>8}"
    )
    print("  " + "-" * (w - 2))

    corr_rot_half = _corr(equity, baselines["50_50_BnH"])
    _print_row(rotation_perf, corr_rot_half)
    _print_row(half_perf, 1.0)
    _print_row(btc_perf, _corr(baselines["BTC_BnH"], baselines["50_50_BnH"]))
    _print_row(eth_perf, _corr(baselines["ETH_BnH"], baselines["50_50_BnH"]))
    print(sep)

    # ── Rotation stats ─────────────────────────────────────────────────
    print(f"\n  ROTATION STATISTICS")
    print("  " + "-" * 60)
    print(f"  Signal:  {stats['pct_time_eth_favored']:.1f}% ETH favored  "
          f"{stats['pct_time_neutral']:.1f}% neutral  "
          f"{stats['pct_time_btc_favored']:.1f}% BTC favored")
    print(f"  Avg alloc:   BTC {stats['avg_btc_alloc_pct']:.1f}%  "
          f"ETH {stats['avg_eth_alloc_pct']:.1f}%")
    print(f"  Rotations:   {stats['n_rotation_events']} total  "
          f"({stats['rotations_per_year']:.1f}/yr)")
    print(f"  Trades:      {stats['n_trades']} total  "
          f"(2 per rotation: BTC + ETH legs)")
    print(f"  Total fees:  ${stats['total_fees_usd']:>10,.2f}")
    print(f"  Total slip:  ${stats['total_slippage_usd']:>10,.2f}")
    print(f"  Total cost:  ${stats['total_cost_usd']:>10,.2f}")

    # ── Calendar year breakdown ────────────────────────────────────────
    daily_eq = equity.resample("1D").last().dropna()
    daily_50 = baselines["50_50_BnH"].resample("1D").last().dropna()

    print(f"\n  CALENDAR YEAR RETURNS")
    print("  " + "-" * 60)
    print(f"  {'Year':<6}  {'Rotation':>10}  {'50/50 BnH':>10}  {'Delta':>8}")
    print("  " + "-" * 42)
    years_in_period = sorted(set(daily_eq.index.year))
    for yr in years_in_period:
        rot_r = _year_perf(daily_eq, yr)
        bnh_r = _year_perf(daily_50, yr)
        try:
            rot_v = float(rot_r.strip().replace("%", ""))
            bnh_v = float(bnh_r.strip().replace("%", ""))
            delta = f"{rot_v - bnh_v:>+7.1f}%"
        except ValueError:
            delta = "   n/a"
        print(f"  {yr:<6}  {rot_r:>10}  {bnh_r:>10}  {delta:>8}")
    print(sep)

    # ── Blend hint ─────────────────────────────────────────────────────
    run_id = (
        f"{STRATEGY_ID}_{str(common_idx[0])[:10]}_{str(common_idx[-1])[:10]}"
    )
    out_dir = Path(args.out_dir) if args.out_dir else Path("artifacts") / run_id

    if not args.no_save:
        out_dir.mkdir(parents=True, exist_ok=True)

        # equity_curve.csv — compatible with run_blend_analysis.py
        out_df = pd.DataFrame({
            "equity": equity.values,
            "btc_alloc": btc_alloc.values,
            "signal": signal.values,
        }, index=common_idx)
        out_df.index.name = "timestamp"
        out_df.to_csv(out_dir / "equity_curve.csv")

        # stats JSON
        summary = {
            "strategy_id": STRATEGY_ID,
            "start": str(common_idx[0])[:10],
            "end": str(common_idx[-1])[:10],
            "n_bars": len(common_idx),
            "initial_capital": args.capital,
            "execution": {
                "fee_rate": args.fee,
                "base_slippage_bps": args.base_slippage,
                "slippage_vol_factor": args.slippage_vol_factor,
                "rebalance_threshold": args.rebalance_threshold,
            },
            "signal_params": {
                "fast_ema": FAST_EMA,
                "slow_ema": SLOW_EMA,
                "confirm_bars": CONFIRM_BARS,
                "min_hold_bars": MIN_HOLD_BARS,
                "min_rel_spread": MIN_REL_SPREAD,
            },
            "performance": rotation_perf,
            "rotation_stats": stats,
        }
        with open(out_dir / "summary.json", "w") as f:
            json.dump(summary, f, indent=2, default=str)

        print(f"\n  Artifacts saved: {out_dir}")
        print(f"    equity_curve.csv  summary.json")

        print(f"\n  Blend command (PowerShell):")
        print(
            f'    python scripts\\run_blend_analysis.py '
            f'--fund-equity "artifacts\\fund_equal_cal_4s_2019-03-08_2025-12-30\\equity_curves.csv" '
            f'--sleeve-equity "{str(out_dir)}\\equity_curve.csv" '
            f'--sleeve-label ETHBTC_Rotation_v1'
        )

    print()


if __name__ == "__main__":
    main()
