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

Examples:
    Single symbol, legacy-compatible:
        python scripts/download_equity_data.py --symbol SPY --start 2005-01-01 --out data/SPY_1D.csv

    Batch symbols to the default data directory:
        python scripts/download_equity_data.py --symbols SPY,QQQ,IWM,MDY --start 2005-01-01 --out-dir data

    Repeated --symbol flags are also supported:
        python scripts/download_equity_data.py --symbol SPY --symbol QQQ --symbol IWM --start 2005-01-01
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import pandas as pd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Download daily equity OHLCV data from Yahoo Finance",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--symbol",
        action="append",
        default=[],
        help="Ticker symbol. May be supplied multiple times. Also accepts comma-separated values.",
    )
    p.add_argument(
        "--symbols",
        default=None,
        help="Comma-separated ticker symbols, e.g. SPY,QQQ,IWM,MDY.",
    )
    p.add_argument("--start", default="2000-01-01", help="Start date YYYY-MM-DD")
    p.add_argument("--end", default=None, help="End date YYYY-MM-DD. Omit for latest available.")
    p.add_argument(
        "--out",
        default=None,
        help="Output CSV path for single-symbol mode. Defaults to data/<SYMBOL>_1D.csv. Not valid with multiple symbols.",
    )
    p.add_argument("--out-dir", default="data", help="Output directory for generated <SYMBOL>_1D.csv files.")
    p.add_argument(
        "--raw-close",
        action="store_true",
        help="Use Yahoo raw Close instead of adjusted/auto-adjusted prices.",
    )
    p.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue downloading remaining symbols if one symbol fails.",
    )
    return p.parse_args()


def _split_symbols(values: Iterable[str] | None) -> list[str]:
    out: list[str] = []
    for raw in values or []:
        for part in str(raw).split(","):
            symbol = part.strip().upper()
            if symbol:
                out.append(symbol)
    return list(dict.fromkeys(out))


def _resolve_symbols(args: argparse.Namespace) -> list[str]:
    symbols = _split_symbols(args.symbol)
    if args.symbols:
        symbols.extend(_split_symbols([args.symbols]))
    symbols = list(dict.fromkeys(symbols))
    if not symbols:
        raise SystemExit("No symbols supplied. Use --symbol SPY or --symbols SPY,QQQ,IWM")
    if args.out and len(symbols) != 1:
        raise SystemExit("--out can only be used with exactly one symbol. Use --out-dir for batch downloads.")
    return symbols


def _normalize_yahoo_frame(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if df is None or df.empty:
        raise ValueError(f"No data returned for {symbol}")

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
        raise ValueError(f"Yahoo data missing required columns for {symbol}: {missing}. Got: {list(df.columns)}")

    out = df[required].copy()
    out = out.dropna(subset=["open", "high", "low", "close"])
    out = out[out["volume"].fillna(0) >= 0]
    if out.empty:
        raise ValueError(f"No valid OHLC rows after cleanup for {symbol}")
    out.index = pd.to_datetime(out.index).tz_localize(None)
    out.index.name = "timestamp"
    return out


def _download_one(yf, symbol: str, args: argparse.Namespace, out_path: Path) -> dict[str, object]:
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

    out = _normalize_yahoo_frame(df, symbol)
    out.to_csv(out_path)

    print(f"Saved {len(out):,} daily bars to: {out_path}")
    print(f"Period: {out.index[0].date()} → {out.index[-1].date()}")
    print("Columns: timestamp, open, high, low, close, volume")
    return {
        "symbol": symbol,
        "status": "ok",
        "rows": int(len(out)),
        "start": str(out.index[0].date()),
        "end": str(out.index[-1].date()),
        "out": str(out_path),
    }


def main() -> None:
    args = parse_args()
    symbols = _resolve_symbols(args)

    try:
        import yfinance as yf
    except ImportError as exc:
        raise SystemExit("Missing dependency: yfinance. Install with: pip install yfinance") from exc

    results: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    for symbol in symbols:
        out_path = Path(args.out) if args.out else Path(args.out_dir) / f"{symbol}_1D.csv"
        try:
            results.append(_download_one(yf, symbol, args, out_path))
        except Exception as exc:
            failure = {"symbol": symbol, "status": "failed", "error": str(exc)}
            failures.append(failure)
            print(f"ERROR downloading {symbol}: {exc}")
            if not args.continue_on_error:
                break

    print("\n=== Equity data download summary ===")
    for row in results:
        print(f"OK     {row['symbol']}: {row['rows']} rows -> {row['out']} ({row['start']} → {row['end']})")
    for row in failures:
        print(f"FAILED {row['symbol']}: {row['error']}")

    if failures:
        raise SystemExit(f"Completed with {len(failures)} failure(s).")
    print(f"Completed successfully for {len(results)} symbol(s).")


if __name__ == "__main__":
    main()
