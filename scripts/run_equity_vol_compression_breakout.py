#!/usr/bin/env python
"""Equity volatility-compression breakout research runner.

First-pass equity alpha test plus mechanics audit. Applies a post-compression
breakout structure to ETF data and compares the resulting trade profiles against
equity benchmarks.

Research-only. No runtime, broker, or live execution code.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from research.harness.metrics import compute_metrics
from scripts.run_state_confirmed_risk_off_sweep import _load_close


DEFAULT_ASSETS = ["QQQ", "SMH", "XLK", "IGV", "XLC"]
DEFAULT_BENCHMARKS = ["SPY", "QQQ", "RSP"]


def fmt_pct(x: Any) -> str:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "n/a"
    return "n/a" if math.isnan(v) else f"{v:.2f}%"


def fmt_money(x: Any) -> str:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "n/a"
    return "n/a" if math.isnan(v) else f"${v:,.2f}"


def data_path(data_dir: Path, symbol: str) -> Path:
    return data_dir / f"{symbol}_1D.csv"


def equity_from_returns(rets: pd.Series, capital: float, name: str) -> pd.Series:
    out = capital * (1.0 + rets.fillna(0.0)).cumprod()
    out.name = name
    return out


def metrics(label: str, eq: pd.Series, capital: float) -> dict[str, Any]:
    s = eq.dropna()
    m = compute_metrics(s, trades=[], params={"strategy_id": label, "asset": "PORTFOLIO", "initial_capital": capital})
    return {
        "label": label,
        "final_nav": float(s.iloc[-1]),
        "cagr_pct": m.cagr_pct,
        "max_drawdown_pct": m.max_drawdown_pct,
        "sharpe": m.sharpe,
        "calmar": m.calmar,
    }


def window_return(eq: pd.Series, start: str, end: str) -> float | None:
    s = eq.loc[(eq.index >= pd.Timestamp(start)) & (eq.index <= pd.Timestamp(end))].dropna()
    if len(s) < 2:
        return None
    return (float(s.iloc[-1]) / float(s.iloc[0]) - 1.0) * 100.0


def load_prices(data_dir: Path, symbols: list[str], start: str, end: str) -> dict[str, pd.Series]:
    prices: dict[str, pd.Series] = {}
    for sym in symbols:
        p = data_path(data_dir, sym)
        if not p.exists():
            raise FileNotFoundError(f"Missing required data file: {p}")
        prices[sym] = _load_close(str(p), sym, start, end)
    return prices


def _entry_index(signal_i: int, delay_days: int, max_i: int) -> int | None:
    idx = signal_i + delay_days
    return idx if idx <= max_i else None


def simulate(
    close: pd.Series,
    asset: str,
    vol_window: int,
    rank_window: int,
    pctile: float,
    channel: int,
    max_hold: int,
    stop: float,
    memory: int,
    entry_delay_days: int,
    capital: float,
    fee_bps: float,
) -> tuple[pd.Series, list[dict[str, Any]], float]:
    close = close.dropna()
    dates = list(close.index)
    rets = close.pct_change(fill_method=None).fillna(0.0)
    vol = rets.rolling(vol_window, min_periods=vol_window).std() * math.sqrt(252.0)
    vol_rank = vol.rolling(rank_window, min_periods=rank_window).rank(pct=True)
    compression_recent = (vol_rank <= pctile).rolling(memory, min_periods=1).max().fillna(0).astype(bool)
    high = close.shift(1).rolling(channel, min_periods=channel).max()
    low = close.shift(1).rolling(channel, min_periods=channel).min()

    label = (
        f"{asset}_evcb_v{vol_window}_r{rank_window}_p{int(pctile*100)}_"
        f"ch{channel}_h{max_hold}_s{int(abs(stop)*100)}_m{memory}_d{entry_delay_days}"
    )
    nav = capital
    in_pos = False
    entry_px = 0.0
    entry_dt = None
    signal_dt = None
    held = 0
    peak_px = 0.0
    pos_days = 0
    pending_entry_i: int | None = None
    pending_signal_dt = None
    nav_rows = []
    trades: list[dict[str, Any]] = []

    for i, dt in enumerate(dates):
        px = float(close.loc[dt])

        if in_pos:
            nav *= 1.0 + float(rets.loc[dt])
            held += 1
            pos_days += 1
            peak_px = max(peak_px, px)

        exit_reason = None
        if in_pos:
            if pd.notna(low.loc[dt]) and px < float(low.loc[dt]):
                exit_reason = "channel_low"
            elif px / peak_px - 1.0 <= stop:
                exit_reason = "trail_stop"
            elif held >= max_hold:
                exit_reason = "time_stop"
            if exit_reason:
                nav *= 1.0 - fee_bps / 10000.0
                trade_ret = (px / entry_px - 1.0 - 2.0 * fee_bps / 10000.0) * 100.0
                trades.append(
                    {
                        "label": label,
                        "asset": asset,
                        "signal_date": signal_dt.date().isoformat() if signal_dt is not None else "",
                        "entry_date": entry_dt.date().isoformat(),
                        "exit_date": dt.date().isoformat(),
                        "entry_year": int(entry_dt.year),
                        "exit_year": int(dt.year),
                        "entry_price": entry_px,
                        "exit_price": px,
                        "return_pct": trade_ret,
                        "hold_days": held,
                        "exit_reason": exit_reason,
                        "entry_delay_days": entry_delay_days,
                    }
                )
                in_pos = False
                held = 0
                entry_px = 0.0
                entry_dt = None
                signal_dt = None
                peak_px = 0.0
                pending_entry_i = None
                pending_signal_dt = None

        if not in_pos and pending_entry_i is not None and i >= pending_entry_i:
            nav *= 1.0 - fee_bps / 10000.0
            in_pos = True
            entry_px = px
            entry_dt = dt
            signal_dt = pending_signal_dt
            peak_px = px
            held = 0
            pending_entry_i = None
            pending_signal_dt = None

        if not in_pos and pending_entry_i is None:
            signal = pd.notna(high.loc[dt]) and bool(compression_recent.loc[dt]) and px > float(high.loc[dt])
            if signal:
                eidx = _entry_index(i, entry_delay_days, len(dates) - 1)
                if eidx is not None:
                    pending_entry_i = eidx
                    pending_signal_dt = dt

        nav_rows.append((dt, nav))

    eq = pd.Series([x[1] for x in nav_rows], index=[x[0] for x in nav_rows], name=label)
    exposure = pos_days / max(len(close), 1) * 100.0
    return eq, trades, exposure


def trade_stats(trades: list[dict[str, Any]]) -> dict[str, Any]:
    if not trades:
        return {"trade_count": 0, "win_rate_pct": None, "avg_trade_return_pct": None, "median_trade_return_pct": None, "avg_hold_days": None}
    r = pd.Series([t["return_pct"] for t in trades], dtype=float)
    h = pd.Series([t["hold_days"] for t in trades], dtype=float)
    return {
        "trade_count": len(trades),
        "win_rate_pct": float((r > 0).mean() * 100.0),
        "avg_trade_return_pct": float(r.mean()),
        "median_trade_return_pct": float(r.median()),
        "avg_hold_days": float(h.mean()),
    }


def yearly_trade_summary(trades: list[dict[str, Any]]) -> pd.DataFrame:
    if not trades:
        return pd.DataFrame(columns=["label", "asset", "entry_year", "trade_count", "win_rate_pct", "sum_return_pct", "avg_return_pct", "median_return_pct", "avg_hold_days"])
    df = pd.DataFrame(trades)
    rows = []
    for (label, asset, year), g in df.groupby(["label", "asset", "entry_year"]):
        rets = g["return_pct"].astype(float)
        holds = g["hold_days"].astype(float)
        rows.append(
            {
                "label": label,
                "asset": asset,
                "entry_year": int(year),
                "trade_count": int(len(g)),
                "win_rate_pct": float((rets > 0).mean() * 100.0),
                "sum_return_pct": float(rets.sum()),
                "avg_return_pct": float(rets.mean()),
                "median_return_pct": float(rets.median()),
                "avg_hold_days": float(holds.mean()),
            }
        )
    return pd.DataFrame(rows).sort_values(["label", "entry_year"])


def add_windows(row: dict[str, Any], eq: pd.Series, args: argparse.Namespace) -> dict[str, Any]:
    row["crash_2020_pct"] = window_return(eq, args.crash_2020_start, args.crash_2020_end)
    row["bear_2022_pct"] = window_return(eq, args.bear_2022_start, args.bear_2022_end)
    row["bull_2023_2025_pct"] = window_return(eq, args.bull_2023_start, args.bull_2023_end)
    return row


def rank(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def safe(x: Any) -> float:
        try:
            v = float(x)
        except (TypeError, ValueError):
            return -9999.0
        return -9999.0 if math.isnan(v) else v
    return sorted(rows, key=lambda r: (safe(r.get("calmar")), safe(r.get("sharpe")), safe(r.get("cagr_pct"))), reverse=True)


def print_rows(rows: list[dict[str, Any]], limit: int) -> None:
    print(f"  {'Rank':>4} {'Label':<67} {'Final NAV':>14} {'CAGR%':>9} {'MaxDD%':>9} {'Sharpe':>8} {'Calmar':>8} {'Trades':>7} {'Win%':>8} {'AvgTr%':>8} {'Expo%':>8}")
    print("  " + "-" * 162)
    for i, r in enumerate(rows[:limit], start=1):
        print(
            f"  {i:>4} {r['label']:<67} {fmt_money(r['final_nav']):>14} {fmt_pct(r['cagr_pct']):>9} "
            f"{fmt_pct(r['max_drawdown_pct']):>9} {r['sharpe']:>8.3f} {r['calmar']:>8.3f} "
            f"{r.get('trade_count', 0):>7} {fmt_pct(r.get('win_rate_pct')):>8} {fmt_pct(r.get('avg_trade_return_pct')):>8} {fmt_pct(r.get('exposure_pct')):>8}"
        )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Equity volatility-compression breakout research")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--assets", nargs="+", default=DEFAULT_ASSETS)
    p.add_argument("--benchmarks", nargs="+", default=DEFAULT_BENCHMARKS)
    p.add_argument("--start", default="2019-01-01")
    p.add_argument("--end", default="2025-12-30")
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--fee-bps", type=float, default=10.0)
    p.add_argument("--vol-windows", nargs="+", type=int, default=[20, 30, 60])
    p.add_argument("--rank-windows", nargs="+", type=int, default=[90, 180])
    p.add_argument("--pctiles", nargs="+", type=float, default=[0.20, 0.30])
    p.add_argument("--channels", nargs="+", type=int, default=[20, 30, 40])
    p.add_argument("--max-holds", nargs="+", type=int, default=[20, 40, 60])
    p.add_argument("--stops", nargs="+", type=float, default=[-0.10, -0.15, -0.20])
    p.add_argument("--memories", nargs="+", type=int, default=[5, 10, 20])
    p.add_argument("--entry-delays", nargs="+", type=int, default=[0, 1])
    p.add_argument("--top-n", type=int, default=25)
    p.add_argument("--crash-2020-start", default="2020-02-19")
    p.add_argument("--crash-2020-end", default="2020-03-23")
    p.add_argument("--bear-2022-start", default="2022-01-01")
    p.add_argument("--bear-2022-end", default="2022-12-31")
    p.add_argument("--bull-2023-start", default="2023-01-01")
    p.add_argument("--bull-2023-end", default="2025-12-30")
    p.add_argument("--out-dir", default="artifacts/equity_vol_compression_breakout")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    symbols = sorted(set(args.assets + args.benchmarks))
    prices = load_prices(data_dir, symbols, args.start, args.end)

    curves: dict[str, pd.Series] = {}
    rows: list[dict[str, Any]] = []
    trades_all: list[dict[str, Any]] = []

    for sym in args.benchmarks:
        close = prices[sym]
        eq = equity_from_returns(close.pct_change(fill_method=None).fillna(0.0), args.capital, f"{sym.lower()}_bh")
        curves[eq.name] = eq
        row = add_windows(metrics(eq.name, eq, args.capital), eq, args)
        row.update(trade_stats([]))
        row.update({"asset": sym, "type": "benchmark", "exposure_pct": 100.0, "entry_delay_days": None})
        rows.append(row)

    common_idx = None
    for sym in args.assets:
        common_idx = prices[sym].index if common_idx is None else common_idx.intersection(prices[sym].index)
    if common_idx is not None and len(common_idx) > 0:
        ew_rets = pd.DataFrame({sym: prices[sym].reindex(common_idx).pct_change(fill_method=None).fillna(0.0) for sym in args.assets}).mean(axis=1)
        eq = equity_from_returns(ew_rets, args.capital, "equal_weight_tested_assets")
        curves[eq.name] = eq
        row = add_windows(metrics(eq.name, eq, args.capital), eq, args)
        row.update(trade_stats([]))
        row.update({"asset": "EQUAL_WEIGHT", "type": "benchmark", "exposure_pct": 100.0, "entry_delay_days": None})
        rows.append(row)

    for asset in args.assets:
        close = prices[asset]
        for vw in args.vol_windows:
            for rw in args.rank_windows:
                if rw <= vw:
                    continue
                for pct in args.pctiles:
                    for ch in args.channels:
                        for hold in args.max_holds:
                            for stop in args.stops:
                                for mem in args.memories:
                                    for delay in args.entry_delays:
                                        eq, trades, exposure = simulate(close, asset, vw, rw, pct, ch, hold, stop, mem, delay, args.capital, args.fee_bps)
                                        curves[eq.name] = eq
                                        row = add_windows(metrics(eq.name, eq, args.capital), eq, args)
                                        row.update(
                                            {
                                                "asset": asset,
                                                "type": "evcb",
                                                "vol_window": vw,
                                                "rank_window": rw,
                                                "pctile": pct,
                                                "channel": ch,
                                                "max_hold": hold,
                                                "stop": stop,
                                                "memory": mem,
                                                "entry_delay_days": delay,
                                                "exposure_pct": exposure,
                                            }
                                        )
                                        row.update(trade_stats(trades))
                                        rows.append(row)
                                        trades_all.extend(trades)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(curves).to_csv(out / "equity_curves.csv")
    pd.DataFrame(rows).to_csv(out / "results.csv", index=False)
    trades_df = pd.DataFrame(trades_all)
    trades_df.to_csv(out / "trades.csv", index=False)
    yearly_trade_summary(trades_all).to_csv(out / "trade_attribution_by_year.csv", index=False)

    ranked = rank(rows)
    (out / "summary.json").write_text(json.dumps({"config": vars(args), "results": rows}, indent=2, default=str), encoding="utf-8")
    with (out / "summary.md").open("w", encoding="utf-8") as f:
        f.write("# Equity Volatility Compression Breakout Summary\n\n")
        f.write("Research-only equity ETF volatility-compression breakout test with delayed-entry audit.\n\n")
        f.write("| Rank | Label | Final NAV | CAGR | MaxDD | Sharpe | Calmar | Trades | Win Rate | Avg Trade | Exposure |\n")
        f.write("|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n")
        for i, r in enumerate(ranked[: args.top_n], start=1):
            f.write(
                f"| {i} | {r['label']} | {fmt_money(r['final_nav'])} | {fmt_pct(r['cagr_pct'])} | {fmt_pct(r['max_drawdown_pct'])} | "
                f"{r['sharpe']:.3f} | {r['calmar']:.3f} | {r.get('trade_count', 0)} | {fmt_pct(r.get('win_rate_pct'))} | "
                f"{fmt_pct(r.get('avg_trade_return_pct'))} | {fmt_pct(r.get('exposure_pct'))} |\n"
            )
        f.write("\nAdditional audit artifacts:\n\n")
        f.write("```text\ntrades.csv\ntrade_attribution_by_year.csv\n```\n\n")
        f.write("```text\nRESEARCH ONLY\nNO RUNTIME WORK\nNO BROKER WORK\n```\n")

    print("=" * 156)
    print("  EQUITY VOL COMPRESSION BREAKOUT — MECHANICS AUDIT")
    print("=" * 156)
    print(f"  Date range   : {args.start} -> {args.end}")
    print(f"  Assets       : {', '.join(args.assets)}")
    print(f"  Fee bps      : {args.fee_bps:.2f}")
    print(f"  Entry delays : {', '.join(str(x) for x in args.entry_delays)} day(s)")
    print("-" * 156)
    print_rows(ranked, args.top_n)
    print("=" * 156)
    print(f"  Summary: {out / 'summary.md'}")
    print(f"  Results: {out / 'results.csv'}")
    print(f"  Trades : {out / 'trades.csv'}")
    print(f"  Yearly : {out / 'trade_attribution_by_year.csv'}")
    print("  Verdict: research output only; review before integration.\n")


if __name__ == "__main__":
    main()
