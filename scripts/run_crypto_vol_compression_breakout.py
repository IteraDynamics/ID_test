#!/usr/bin/env python
"""Compact crypto volatility-compression breakout research runner.

Research-only alpha test. No runtime, broker, or live execution code.
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


def simulate(close: pd.Series, asset: str, vol_window: int, rank_window: int, pctile: float, channel: int, max_hold: int, stop: float, memory: int, capital: float, fee_bps: float) -> tuple[pd.Series, list[dict[str, Any]], float]:
    close = close.dropna()
    rets = close.pct_change(fill_method=None).fillna(0.0)
    vol = rets.rolling(vol_window, min_periods=vol_window).std() * math.sqrt(365.0)
    vol_rank = vol.rolling(rank_window, min_periods=rank_window).rank(pct=True)
    compression_recent = (vol_rank <= pctile).rolling(memory, min_periods=1).max().fillna(0).astype(bool)
    high = close.shift(1).rolling(channel, min_periods=channel).max()
    low = close.shift(1).rolling(channel, min_periods=channel).min()

    label = f"{asset}_vcb_v{vol_window}_r{rank_window}_p{int(pctile*100)}_ch{channel}_h{max_hold}_s{int(abs(stop)*100)}_m{memory}"
    nav = capital
    in_pos = False
    entry_px = 0.0
    entry_dt = None
    held = 0
    peak_px = 0.0
    trades: list[dict[str, Any]] = []
    nav_rows = []
    pos_days = 0

    for i, dt in enumerate(close.index):
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
                trades.append({"label": label, "asset": asset, "entry_date": entry_dt.date().isoformat(), "exit_date": dt.date().isoformat(), "entry_price": entry_px, "exit_price": px, "return_pct": trade_ret, "hold_days": held, "exit_reason": exit_reason})
                in_pos = False
                held = 0
                entry_px = 0.0
                entry_dt = None
                peak_px = 0.0

        if not in_pos and pd.notna(high.loc[dt]) and bool(compression_recent.loc[dt]) and px > float(high.loc[dt]):
            nav *= 1.0 - fee_bps / 10000.0
            in_pos = True
            entry_px = px
            entry_dt = dt
            peak_px = px
            held = 0

        nav_rows.append((dt, nav))

    eq = pd.Series([x[1] for x in nav_rows], index=[x[0] for x in nav_rows], name=label)
    exposure = pos_days / max(len(close), 1) * 100.0
    return eq, trades, exposure


def trade_stats(trades: list[dict[str, Any]]) -> dict[str, Any]:
    if not trades:
        return {"trade_count": 0, "win_rate_pct": None, "avg_trade_return_pct": None, "median_trade_return_pct": None, "avg_hold_days": None}
    r = pd.Series([t["return_pct"] for t in trades])
    h = pd.Series([t["hold_days"] for t in trades])
    return {"trade_count": len(trades), "win_rate_pct": float((r > 0).mean() * 100), "avg_trade_return_pct": float(r.mean()), "median_trade_return_pct": float(r.median()), "avg_hold_days": float(h.mean())}


def rank(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda r: (r.get("calmar") or -9999, r.get("sharpe") or -9999, r.get("cagr_pct") or -9999), reverse=True)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--btc-data", required=True)
    p.add_argument("--eth-data", required=True)
    p.add_argument("--start", default="2019-01-01")
    p.add_argument("--end", default="2025-12-30")
    p.add_argument("--capital", type=float, default=100000.0)
    p.add_argument("--fee-bps", type=float, default=10.0)
    p.add_argument("--top-n", type=int, default=25)
    p.add_argument("--out-dir", default="artifacts/crypto_vol_compression_breakout")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    btc = _load_close(args.btc_data, "BTC", args.start, args.end)
    eth = _load_close(args.eth_data, "ETH", args.start, args.end)
    idx = btc.index.intersection(eth.index).sort_values()
    prices = {"BTC": btc.reindex(idx).dropna(), "ETH": eth.reindex(idx).dropna()}

    curves = {}
    rows = []
    trades_all = []

    for asset, close in prices.items():
        bh = equity_from_returns(close.pct_change(fill_method=None).fillna(0.0), args.capital, f"{asset.lower()}_bh")
        curves[bh.name] = bh
        row = metrics(bh.name, bh, args.capital)
        row.update(trade_stats([]))
        row["asset"] = asset
        row["exposure_pct"] = 100.0
        rows.append(row)

    blend_rets = 0.5 * prices["BTC"].pct_change(fill_method=None).fillna(0.0) + 0.5 * prices["ETH"].pct_change(fill_method=None).fillna(0.0)
    blend = equity_from_returns(blend_rets, args.capital, "static_btc50_eth50")
    curves[blend.name] = blend
    row = metrics(blend.name, blend, args.capital)
    row.update(trade_stats([]))
    row["asset"] = "BTC_ETH"
    row["exposure_pct"] = 100.0
    rows.append(row)

    for asset, close in prices.items():
        for vw in [20, 30, 60]:
            for rw in [90, 180]:
                for pct in [0.2, 0.3]:
                    for ch in [20, 30, 40]:
                        for hold in [20, 40, 60]:
                            for stop in [-0.15, -0.25]:
                                for mem in [5, 10, 20]:
                                    eq, trades, exposure = simulate(close, asset, vw, rw, pct, ch, hold, stop, mem, args.capital, args.fee_bps)
                                    curves[eq.name] = eq
                                    row = metrics(eq.name, eq, args.capital)
                                    row.update({"asset": asset, "vol_window": vw, "rank_window": rw, "pctile": pct, "channel": ch, "max_hold": hold, "stop": stop, "memory": mem, "exposure_pct": exposure})
                                    row.update(trade_stats(trades))
                                    rows.append(row)
                                    trades_all.extend(trades)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(curves).to_csv(out / "equity_curves.csv")
    pd.DataFrame(rows).to_csv(out / "results.csv", index=False)
    pd.DataFrame(trades_all).to_csv(out / "trades.csv", index=False)
    ranked = rank(rows)
    (out / "summary.json").write_text(json.dumps({"config": vars(args), "results": rows}, indent=2, default=str), encoding="utf-8")
    (out / "summary.md").write_text("# Crypto Vol Compression Breakout\n\nResearch-only output. See results.csv and trades.csv.\n", encoding="utf-8")

    print("=" * 150)
    print("  CRYPTO VOL COMPRESSION BREAKOUT — FIRST PASS ALPHA RESEARCH")
    print("=" * 150)
    print(f"  Date range: {args.start} -> {args.end}")
    print(f"  Fee bps   : {args.fee_bps:.2f}")
    print("-" * 150)
    print(f"  {'Rank':>4} {'Label':<62} {'Final NAV':>14} {'CAGR%':>9} {'MaxDD%':>9} {'Sharpe':>8} {'Calmar':>8} {'Trades':>7} {'Win%':>8} {'AvgTr%':>8} {'Expo%':>8}")
    print("  " + "-" * 148)
    for i, r in enumerate(ranked[: args.top_n], start=1):
        print(f"  {i:>4} {r['label']:<62} {fmt_money(r['final_nav']):>14} {fmt_pct(r['cagr_pct']):>9} {fmt_pct(r['max_drawdown_pct']):>9} {r['sharpe']:>8.3f} {r['calmar']:>8.3f} {r.get('trade_count',0):>7} {fmt_pct(r.get('win_rate_pct')):>8} {fmt_pct(r.get('avg_trade_return_pct')):>8} {fmt_pct(r.get('exposure_pct')):>8}")
    print("=" * 150)
    print(f"  Summary: {out / 'summary.md'}")
    print(f"  Trades : {out / 'trades.csv'}")
    print("  Verdict: research output only; review before integration.\n")


if __name__ == "__main__":
    main()
