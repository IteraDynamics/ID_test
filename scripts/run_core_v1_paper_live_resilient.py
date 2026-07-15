#!/usr/bin/env python
"""Resilient launcher for the Core v1 paper runtime.

Adds two operational safeguards without changing strategy logic:
1. If Yahoo's daily chart feed has a missing/null completed session, retry the
   symbol from Stooq and require that the expected completed NYSE session exists.
2. A failed cycle logs, makes no trades, sleeps, and retries instead of killing
   the long-running process.
"""
from __future__ import annotations

import io
import sys
import time
import urllib.parse
from datetime import timedelta
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import scripts.run_core_v1_paper_live as core


_ORIGINAL_YAHOO_FETCH = core.fetch_stooq_daily
_STOOQ_SYMBOLS = {
    "SPY": "spy.us",
    "QQQ": "qqq.us",
    "GLD": "gld.us",
    "BIL": "bil.us",
}


def fetch_stooq_csv_daily(symbol: str, days: int = 520) -> pd.DataFrame:
    now = core.utc_now()
    end = pd.Timestamp(now.date())
    start = end - pd.Timedelta(days=max(days + 30, 60))
    stooq_symbol = _STOOQ_SYMBOLS.get(symbol.upper(), f"{symbol.lower()}.us")
    params = urllib.parse.urlencode(
        {
            "s": stooq_symbol,
            "d1": start.strftime("%Y%m%d"),
            "d2": end.strftime("%Y%m%d"),
            "i": "d",
        }
    )
    text = core.fetch_text(f"{core.STOOQ_URL}?{params}")
    df = pd.read_csv(io.StringIO(text))
    if df.empty or "Date" not in df.columns:
        raise RuntimeError(f"No Stooq daily data returned for {symbol}")
    df.columns = [str(c).strip().lower() for c in df.columns]
    required = {"date", "open", "high", "low", "close"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise RuntimeError(f"Stooq {symbol} response missing columns: {missing}")
    df["timestamp"] = pd.to_datetime(df["date"], errors="coerce")
    if "volume" not in df.columns:
        df["volume"] = 0.0
    df = (
        df.dropna(subset=["timestamp", "open", "high", "low", "close"])
        .drop_duplicates("timestamp")
        .set_index("timestamp")
        .sort_index()[["open", "high", "low", "close", "volume"]]
        .astype(float)
    )
    df = core.drop_incomplete_bars(df, timedelta(days=1), now)
    cutoff = pd.Timestamp(now.replace(tzinfo=None)) - pd.Timedelta(days=days)
    df = df.loc[df.index >= cutoff]
    if df.empty:
        raise RuntimeError(f"No completed Stooq daily bars available for {symbol}")
    return df


def fetch_daily_with_fallback(symbol: str, days: int = 520) -> pd.DataFrame:
    yahoo_error: Exception | None = None
    try:
        yahoo = _ORIGINAL_YAHOO_FETCH(symbol, days=days)
        status, detail = core.daily_etf_freshness_status(yahoo, core.utc_now())
        if status != "FAIL":
            return yahoo
        yahoo_error = RuntimeError(f"Yahoo freshness failed: {detail}")
        print(f"[provider] {symbol}: Yahoo unusable — {detail}; trying Stooq", file=sys.stderr)
    except Exception as exc:
        yahoo_error = exc
        print(f"[provider] {symbol}: Yahoo fetch failed — {exc}; trying Stooq", file=sys.stderr)

    stooq = fetch_stooq_csv_daily(symbol, days=days)
    status, detail = core.daily_etf_freshness_status(stooq, core.utc_now())
    if status == "FAIL":
        raise RuntimeError(
            f"Both daily providers unusable for {symbol}; Yahoo={yahoo_error}; Stooq={detail}"
        )
    print(
        f"[provider] {symbol}: using Stooq fallback — last={stooq.index[-1].date()} status={status}",
        file=sys.stderr,
    )
    return stooq


def main() -> None:
    core.fetch_stooq_daily = fetch_daily_with_fallback
    args = core.parse_args()
    cycles = 0
    while True:
        try:
            event = core.run_cycle(args)
            print(
                f"{event['timestamp']} Core v1 cycle={event['cycle']} NAV=${event['total_nav']:,.2f} "
                f"DD={event['drawdown_frac']:.2%} today={event['today_pnl']:+,.2f} fills={len(event['fills'])}",
                flush=True,
            )
            for signal in event["signals"]:
                changed = " changed" if signal.get("action_changed") else ""
                print(
                    f"  {signal['sleeve']}: {signal['action']}{changed} "
                    f"target={signal['target_exposure']:.3f} price={signal['price']:.2f} "
                    f"regime={signal['regime']} uPnL={signal['unrealized_pnl']:+,.2f} | {signal['reason']}",
                    flush=True,
                )
        except Exception as exc:
            err = {
                "timestamp": core.utc_now().isoformat(),
                "error": str(exc),
                "version": core.STATE_VERSION,
                "launcher": "resilient",
            }
            core.append_jsonl(Path(args.signals_log).with_name("core_v1_errors.jsonl"), err)
            print(
                f"ERROR Core v1 cycle skipped safely: {exc}; retrying in {args.poll}s",
                file=sys.stderr,
                flush=True,
            )
        cycles += 1
        if args.max_cycles is not None and cycles >= args.max_cycles:
            break
        time.sleep(args.poll)


if __name__ == "__main__":
    main()
