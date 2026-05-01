#!/usr/bin/env python
"""
Itera Dynamics — Yahoo Finance Equity Data Downloader

Purpose:
    Download free daily OHLCV data from Yahoo Finance and normalize it to the
    CSV schema expected by the Itera research harness:

        timestamp,open,high,low,close,volume

Classification:
    Research utility. This script does not affect runtime or paper trading.

Notes:
    - Uses yfinance, which is free and convenient for research.
    - Yahoo adjusted data is usually adequate for ETF/index-sleeve experiments.
    - Do not treat Yahoo data as institutional-grade execution data.
    - For serious live equity deployment, validate against broker/vendor data.

Example:
    python scripts/download_equity_data.py --symbol SPY --start 2005-01-01 --out data/SPY_1D.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Download daily equity OHLCV data from Yahoo Finance",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--symbol", required=True, help="Ticker symbol, e.g. SPY, QQQ, AAPL")
    p.add_argument("--start", default="2000-01-01", help="Start date YYYY-MM-DD")
    p.add_argument("--end", default=None, help="End date YYYY-MM-DD. Omit for latest available.")
    p.add_argument("--out", default=None, help="Output CSV path. Defaults to data/<SYMBOL>_1D.csv")
    p.add_argument(
        "--raw-close",
        action="store_true",
        help="Use Yahoo raw Close instead of adjusted/auto-adjusted prices.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    symbol = args.symbol.upper().strip()

    try:
        import yfinance as yf
    except ImportError as exc:
        raise SystemExit(
            "Missing dependency: yfinance. Install with: pip install yfinance"
        ) from exc

    out_path = Path(args.out) if args.out else Path("data") / f"{symbol}_1D.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Downloading {symbol} from Yahoo Finance: start={args.start}, end={args.end or 'latest'}")

    df = yf.download(
        symbol,
        start=args.start,
        end=args.end,
        interval="1d",
        auto_adjust=not args.raw_close,
        progress=False,
        group_by="column",
        threads=False,
    )

    if df is None or df.empty:
        raise SystemExit(f"No data returned for {symbol}")

    # yfinance can return MultiIndex columns depending on version/options.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

    rename = {
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Adj Close": "close",
        "Volume": "volume",
    }
    df = df.rename(columns=rename)

    required = ["open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SystemExit(f"Yahoo data missing required columns: {missing}. Got: {list(df.columns)}")

    out = df[required].copy()
    out = out.dropna(subset=["open", "high", "low", "close"])
    out = out[out["volume"].fillna(0) >= 0]
    out.index = pd.to_datetime(out.index).tz_localize(None)
    out.index.name = "timestamp"

    out.to_csv(out_path)

    print(f"Saved {len(out):,} daily bars to: {out_path}")
    print(f"Period: {out.index[0].date()} → {out.index[-1].date()}")
    print("Columns: timestamp, open, high, low, close, volume")


if __name__ == "__main__":
    main()
