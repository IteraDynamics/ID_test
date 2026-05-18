#!/usr/bin/env python
"""Fetch and incrementally persist BTC-USD and ETH-USD OHLCV price data.

First run: fetches ~950 1H bars of history from the Coinbase Exchange public
API and writes data/BTC_USD_1H.csv, data/ETH_USD_1H.csv, and their 4H
equivalents derived via the project resampler.

Subsequent runs: loads each existing CSV, finds the latest stored timestamp,
fetches only bars that have closed since then, and appends them.  The 4H
files are rebuilt from the full updated 1H data each run.

The last bar from each Coinbase fetch is always dropped because it may still
be forming — only fully closed bars are written.

Usage:
    python scripts/fetch_price_data.py
    python scripts/fetch_price_data.py --bars 950 --data-dir data
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from research.harness.resampler import resample_ohlcv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("fetch_price_data")

COINBASE_CANDLES_URL = "https://api.exchange.coinbase.com/products/{product}/candles"
PRODUCTS = ["BTC-USD", "ETH-USD"]
GRANULARITY_1H = 3600
DEFAULT_BARS = 950


def _parse_candles(raw: list) -> pd.DataFrame:
    df = pd.DataFrame(raw, columns=["time", "low", "high", "open", "close", "volume"])
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_localize(None)
    df = df.set_index("time").rename_axis("timestamp")
    df = df[["open", "high", "low", "close", "volume"]].astype(float)
    df = df.sort_index()
    return df[~df.index.duplicated(keep="last")]


def fetch_candles_paginated(
    product_id: str,
    granularity: int = GRANULARITY_1H,
    n_candles: int = DEFAULT_BARS,
    after: datetime | None = None,
) -> pd.DataFrame:
    """Fetch up to n_candles 1H bars, optionally only bars after `after`.

    When `after` is provided only one page is needed in most cases (up to 300
    bars since the last stored timestamp).  For the initial full fetch the
    function pages backward in time until n_candles are collected.
    """
    all_frames: list[pd.DataFrame] = []
    end_time: datetime | None = None
    remaining = n_candles

    while remaining > 0:
        url = f"{COINBASE_CANDLES_URL.format(product=product_id)}?granularity={granularity}"

        if after is not None:
            # Single forward-range request: from the bar after our last stored
            # bar up to now.
            start_dt = after + timedelta(seconds=granularity)
            end_dt = datetime.now(timezone.utc).replace(tzinfo=None)
            url += (
                f"&start={start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')}"
                f"&end={end_dt.strftime('%Y-%m-%dT%H:%M:%SZ')}"
            )
        elif end_time is not None:
            start_dt = end_time - timedelta(seconds=300 * granularity)
            url += (
                f"&start={start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')}"
                f"&end={end_time.strftime('%Y-%m-%dT%H:%M:%SZ')}"
            )

        req = urllib.request.Request(url, headers={"User-Agent": "IteraDynamics/fetch-price-data"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = json.loads(resp.read().decode())
        except urllib.error.URLError as exc:
            if all_frames:
                log.warning("%s: pagination stopped early (API error: %s)", product_id, exc)
                break
            raise RuntimeError(f"Coinbase fetch failed for {product_id}: {exc}") from exc

        if not raw:
            break

        page_df = _parse_candles(raw)
        all_frames.append(page_df)
        remaining -= len(page_df)

        # For incremental fetches or when the API returns fewer than a full
        # page, there are no more bars to fetch.
        if after is not None or len(page_df) < 300:
            break

        oldest = page_df.index[0]
        end_time = oldest.to_pydatetime() - timedelta(seconds=granularity)
        time.sleep(0.25)

    if not all_frames:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    combined = pd.concat(all_frames)
    combined = combined[~combined.index.duplicated(keep="last")]
    return combined.sort_index()


def load_existing(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path, index_col="timestamp", parse_dates=True)
        df.index = pd.to_datetime(df.index)
        log.info("Loaded %d existing bars from %s (last: %s)", len(df), path, df.index[-1])
        return df
    except Exception as exc:
        log.warning("Could not read %s (%s) — will re-fetch from scratch.", path, exc)
        return None


def save_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index_label="timestamp")


def update_product(product_id: str, data_dir: Path, n_bars: int) -> pd.DataFrame:
    """Fetch and persist 1H data for one product. Returns the updated 1H DataFrame."""
    label = product_id.replace("-", "_")
    path_1h = data_dir / f"{label}_1H.csv"
    path_4h = data_dir / f"{label}_4H.csv"

    existing = load_existing(path_1h)

    if existing is not None:
        last_ts: datetime = existing.index[-1].to_pydatetime()
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        hours_since = (now_utc - last_ts).total_seconds() / 3600

        if hours_since < 1.0:
            log.info("%s: last bar is only %.1fh old — nothing new to fetch.", product_id, hours_since)
            df_1h = existing
        else:
            log.info(
                "%s: fetching new bars since %s (%.1fh ago).",
                product_id, last_ts, hours_since,
            )
            new_bars = fetch_candles_paginated(product_id, after=last_ts)

            if new_bars.empty:
                log.info("%s: no new bars returned.", product_id)
                df_1h = existing
            else:
                # Drop the last bar — it may still be forming.
                new_bars = new_bars.iloc[:-1]
                # Strip any bars already in existing to avoid duplicates.
                new_bars = new_bars[new_bars.index > existing.index[-1]]

                if new_bars.empty:
                    log.info("%s: no completed new bars to append.", product_id)
                    df_1h = existing
                else:
                    df_1h = pd.concat([existing, new_bars])
                    df_1h = df_1h[~df_1h.index.duplicated(keep="last")].sort_index()
                    log.info(
                        "%s: appended %d new bars → %d total (up to %s).",
                        product_id, len(new_bars), len(df_1h), df_1h.index[-1],
                    )
    else:
        log.info("%s: no existing data — fetching full history (%d bars).", product_id, n_bars)
        df_raw = fetch_candles_paginated(product_id, n_candles=n_bars)
        if df_raw.empty:
            raise RuntimeError(f"No candles returned for {product_id}")
        # Drop the last bar — it may still be forming.
        df_1h = df_raw.iloc[:-1]
        log.info(
            "%s: fetched %d 1H bars (%s → %s).",
            product_id, len(df_1h), df_1h.index[0], df_1h.index[-1],
        )

    save_csv(df_1h, path_1h)
    log.info("%s: saved %d 1H bars to %s", product_id, len(df_1h), path_1h)

    # Rebuild 4H from the full 1H dataset each run.
    df_4h = resample_ohlcv(df_1h, "4h")
    # Drop the trailing 4H bar if it has fewer than 4 constituent 1H bars.
    if not df_4h.empty:
        last_4h_start = df_4h.index[-1]
        n_constituent = int(
            (
                (df_1h.index >= last_4h_start)
                & (df_1h.index < last_4h_start + pd.Timedelta(hours=4))
            ).sum()
        )
        if n_constituent < 4:
            df_4h = df_4h.iloc[:-1]

    save_csv(df_4h, path_4h)
    log.info("%s: saved %d 4H bars to %s", product_id, len(df_4h), path_4h)

    return df_1h


def main() -> None:
    p = argparse.ArgumentParser(
        description="Incrementally fetch and persist BTC/ETH OHLCV price data.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--bars", type=int, default=DEFAULT_BARS,
                   help="Number of 1H bars to fetch on the initial run")
    p.add_argument("--data-dir", default="data",
                   help="Directory to write CSV files")
    p.add_argument("--products", nargs="+", default=PRODUCTS,
                   help="Coinbase product IDs to fetch")
    args = p.parse_args()

    data_dir = Path(args.data_dir)

    for product_id in args.products:
        try:
            update_product(product_id, data_dir, args.bars)
        except Exception as exc:
            log.error("%s: failed — %s", product_id, exc)


if __name__ == "__main__":
    main()
