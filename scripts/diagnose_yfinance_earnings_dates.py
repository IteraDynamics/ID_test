"""Campaign #59 (planning) — diagnostic: how much earnings-date history does
yfinance actually give us for free, and does it include a usable surprise
proxy?

This is NOT a fetcher. It exists to answer one question cheaply before any
PEAD pipeline gets designed around an assumption: is yfinance's earnings-date
data deep enough (multi-year, not just trailing/upcoming quarters) and rich
enough (EPS estimate/actual, or at minimum just real dates) to build on --
same "check reality before building the pipeline" discipline as
--debug-list-tables and --debug-show-header in the last two scripts, applied
here before the fetcher is even drafted.

Uses yfinance's Ticker.get_earnings_dates(), already installed via the
dependency added earlier this session.
"""

from __future__ import annotations

import argparse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=["AAPL", "MSFT", "SPY"],
        help="Test tickers to check. SPY is included deliberately -- ETFs don't have "
        "earnings, so it should return nothing/empty, which confirms the method "
        "behaves sanely on a ticker it doesn't apply to rather than erroring oddly.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Requested row limit. 100 is Yahoo's own hard cap (confirmed by a real "
        "run: requesting 400 raised 'Yahoo caps limit at 100' rather than silently "
        "truncating) -- 100 quarters is 25 years if that many actually exist and are "
        "returned, which is itself part of what this diagnostic checks.",
    )
    return parser.parse_args()


def diagnose_ticker(ticker_symbol: str, limit: int) -> None:
    import yfinance as yf

    print(f"=== {ticker_symbol} ===")
    ticker = yf.Ticker(ticker_symbol)

    try:
        earnings = ticker.get_earnings_dates(limit=limit)
    except Exception as exc:  # noqa: BLE001 -- diagnostic, report and move to the next ticker
        print(f"  get_earnings_dates() raised: {exc}")
        print()
        return

    if earnings is None or earnings.empty:
        print("  get_earnings_dates() returned None or an empty frame.")
        print()
        return

    print(f"  rows returned: {len(earnings)} (requested limit={limit})")
    print(f"  date range: {earnings.index.min()} .. {earnings.index.max()}")
    print(f"  columns: {list(earnings.columns)}")

    for column in earnings.columns:
        non_null = earnings[column].notna().sum()
        print(f"    {column}: {non_null}/{len(earnings)} non-null ({non_null / len(earnings):.0%})")

    print("  first 3 rows:")
    print(earnings.head(3).to_string())
    print("  last 3 rows (oldest available):")
    print(earnings.tail(3).to_string())
    print()


def main() -> None:
    args = parse_args()
    print(f"yfinance earnings-date diagnostic. Tickers: {args.tickers}, limit={args.limit}\n")
    for ticker_symbol in args.tickers:
        diagnose_ticker(ticker_symbol, args.limit)


if __name__ == "__main__":
    main()
