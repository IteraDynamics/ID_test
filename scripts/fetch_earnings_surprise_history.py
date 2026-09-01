"""Campaign #59 (planning) — earnings surprise history fetcher, Stage 1.

For every ticker already priced in data/ (the same 217-ticker universe
pulled for the reconstitution-effect work), fetches its earnings-date
history via yfinance's Ticker.get_earnings_dates() -- EPS estimate,
reported EPS, and surprise % -- confirmed by a real diagnostic run to
return ~24 years of history with 87-100% field coverage for large,
long-listed names (docs/... see diagnose_yfinance_earnings_dates.py).

Universe: read from data/sp500_reconstitution_events.csv (the ticker set
idea #2 already established and priced), not a fresh ticker list -- reuses
already-downloaded price data rather than acquiring a new universe.

Per-ticker caching + retry/backoff, same pattern as
download_equity_data.py's bulk-download fixes: each ticker's result is
cached to data/earnings_dates/{TICKER}.csv individually, so a partial run
(rate limit, crash, network blip) can be resumed by re-running the exact
same command -- already-cached tickers are skipped, not re-fetched.

Timezone/anchor-day caveat, stated honestly rather than assumed: yfinance
returns each earnings datetime in US/Eastern with a specific time (e.g.
16:00 = market close), but does not label whether a given report was
before-market-open or after-market-close. This script normalizes to a
plain calendar date (dropping the time/timezone) rather than guess at
that distinction -- Stage 2's event-window anchor-day convention should
account for this as an open assumption, not a resolved one.

Uses yfinance + lxml, both already added as dependencies this session.
"""

from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events-file", default="data/sp500_reconstitution_events.csv")
    parser.add_argument("--price-data-dir", default="data")
    parser.add_argument("--cache-dir", default="data/earnings_dates")
    parser.add_argument(
        "--combined-output",
        default="data/earnings_surprise_history.csv",
        help="Final combined CSV across all tickers, written after per-ticker caching completes.",
    )
    parser.add_argument("--limit", type=int, default=100, help="Yahoo's own hard cap; see the diagnostic.")
    parser.add_argument("--retry-count", type=int, default=3)
    parser.add_argument("--retry-delay-seconds", type=float, default=3.0)
    parser.add_argument("--request-delay-seconds", type=float, default=1.0)
    return parser.parse_args()


def load_universe(events_path: Path, price_data_dir: Path) -> list[str]:
    if not events_path.exists():
        raise FileNotFoundError(
            f"{events_path} not found. This reuses idea #2's ticker universe -- "
            "run scripts/fetch_sp500_reconstitution_events.py first if it doesn't exist."
        )

    with events_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        all_tickers = sorted({row["ticker"] for row in reader})

    priced_tickers = [
        ticker for ticker in all_tickers if (price_data_dir / f"{ticker}_1D.csv").exists()
    ]
    missing = len(all_tickers) - len(priced_tickers)
    print(f"Universe: {len(all_tickers)} tickers in the event calendar, {len(priced_tickers)} have local price data.")
    if missing:
        print(f"  ({missing} skipped -- no local {price_data_dir}/{{TICKER}}_1D.csv, matches idea #2's own gaps)")
    return priced_tickers


def fetch_one_ticker(yf_module, ticker: str, limit: int) -> list[dict]:
    """Returns a list of row-dicts, one per earnings event. Empty list if the
    ticker genuinely has none (should not happen for anything in this
    universe, since they're all real S&P 500-history stocks, but handled
    the same as SPY's negative-control case rather than assumed impossible."""
    earnings = yf_module.Ticker(ticker).get_earnings_dates(limit=limit)
    if earnings is None or earnings.empty:
        return []

    rows = []
    for earnings_date, row in earnings.iterrows():
        rows.append(
            {
                "ticker": ticker,
                # Calendar date only -- see module docstring on why the time/tz is dropped.
                "date": earnings_date.date().isoformat(),
                "eps_estimate": row.get("EPS Estimate"),
                "reported_eps": row.get("Reported EPS"),
                "surprise_pct": row.get("Surprise(%)"),
            }
        )
    return rows


def write_ticker_cache(cache_dir: Path, ticker: str, rows: list[dict]) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{ticker}.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["ticker", "date", "eps_estimate", "reported_eps", "surprise_pct"])
        writer.writeheader()
        writer.writerows(rows)


def combine_caches(cache_dir: Path, universe: list[str], output_path: Path) -> int:
    total_rows = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as out_handle:
        writer = csv.DictWriter(
            out_handle, fieldnames=["ticker", "date", "eps_estimate", "reported_eps", "surprise_pct"]
        )
        writer.writeheader()
        for ticker in universe:
            cache_path = cache_dir / f"{ticker}.csv"
            if not cache_path.exists():
                continue
            with cache_path.open(newline="", encoding="utf-8") as in_handle:
                reader = csv.DictReader(in_handle)
                for row in reader:
                    writer.writerow(row)
                    total_rows += 1
    return total_rows


def main() -> None:
    args = parse_args()
    import yfinance as yf

    events_path = Path(args.events_file)
    price_data_dir = Path(args.price_data_dir)
    cache_dir = Path(args.cache_dir)

    universe = load_universe(events_path, price_data_dir)
    if not universe:
        raise RuntimeError("No tickers with local price data found -- nothing to fetch.")

    failed: list[tuple[str, str]] = []
    skipped_cached = 0
    fetched = 0

    for position, ticker in enumerate(universe, start=1):
        cache_path = cache_dir / f"{ticker}.csv"
        print(f"[{position}/{len(universe)}] {ticker}", flush=True)

        if cache_path.exists():
            print("  already cached, skipping", flush=True)
            skipped_cached += 1
            continue

        last_error: Exception | None = None
        rows: list[dict] = []
        for attempt in range(1, args.retry_count + 1):
            try:
                rows = fetch_one_ticker(yf, ticker, args.limit)
                last_error = None
                break
            except Exception as exc:  # noqa: BLE001 -- bulk pulls must not die on one bad ticker
                last_error = exc
                if attempt < args.retry_count:
                    print(
                        f"  attempt {attempt}/{args.retry_count} failed ({exc}); "
                        f"retrying in {args.retry_delay_seconds:.0f}s...",
                        flush=True,
                    )
                    time.sleep(args.retry_delay_seconds)

        if last_error is not None:
            print(f"  FAILED after {args.retry_count} attempts: {last_error}", flush=True)
            failed.append((ticker, str(last_error)))
            time.sleep(args.request_delay_seconds)
            continue

        write_ticker_cache(cache_dir, ticker, rows)
        print(f"  cached {len(rows)} earnings events", flush=True)
        fetched += 1
        time.sleep(args.request_delay_seconds)

    print()
    print(
        f"Fetch complete: {fetched} newly fetched, {skipped_cached} already cached, "
        f"{len(failed)} failed after {args.retry_count} attempts each."
    )
    if failed:
        print("Failed tickers -- re-run this exact command to retry only these (cached ones are skipped):")
        for ticker, reason in failed:
            print(f"  - {ticker}: {reason}")

    combined_path = Path(args.combined_output)
    total_rows = combine_caches(cache_dir, universe, combined_path)
    print(f"\nCombined {total_rows} earnings events across all cached tickers into {combined_path}")


if __name__ == "__main__":
    main()
