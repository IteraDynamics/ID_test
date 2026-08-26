"""Fetch Coinbase Exchange DAILY OHLCV history for a multi-name universe.

Companion to scripts/fetch_coinbase_hourly_history.py (same endpoint, same request pattern,
proven working for BTC/ETH in this repo already) -- this one fetches daily granularity across
many products at once, each from its OWN real earliest-available date rather than one shared
start date, since scripts/probe_coinbase_spot_momentum_universe.py already measured that those
dates differ by up to ~10 years across the universe (BTC ~2015, some 2025-listed names ~1 year).

Per-product start dates are read from the probe's artifact JSON by default
(artifacts/coinbase_spot_momentum_universe_probe.json) rather than typed in by hand -- 51 products
each needing their own correct start date is exactly the kind of thing that gets one of them
wrong if entered manually.

Motivated by the cross-sectional crypto momentum idea (2026-08-26 research session): the named
Core v1 deficiency being addressed is "single-name crypto" (Core v1's only crypto exposure is
BTC 4H / ETH 1H+4H, both single-name trend-following, no relative-value cross-section). This
script only fetches data -- it computes nothing and makes no claim about the idea's validity.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_URL = "https://api.exchange.coinbase.com/products/{product_id}/candles"
GRANULARITY_SECONDS = 86400
CHUNK_DAYS = 290  # stay under the API's ~300-candle-per-request cap with margin
DEFAULT_SLEEP_SECONDS = 0.20
USER_AGENT = "IteraDynamics-research-fetcher/1.0"


@dataclass(frozen=True)
class FetchSummary:
    product_id: str
    out_path: Path
    rows: int
    start: str
    end: str
    warnings: list[str]


def parse_utc(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def coinbase_request(product_id: str, start: datetime, end: datetime, timeout: int = 30) -> list[list[float]]:
    params = urllib.parse.urlencode(
        {"start": iso_z(start), "end": iso_z(end), "granularity": str(GRANULARITY_SECONDS)}
    )
    url = f"{BASE_URL.format(product_id=product_id)}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = resp.read().decode("utf-8")
    return json.loads(payload)


def fetch_chunk_with_retries(
    product_id: str, start: datetime, end: datetime, retries: int, retry_sleep_seconds: float
) -> list[list[float]]:
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return coinbase_request(product_id, start, end)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_exc = exc
            if attempt >= retries:
                break
            time.sleep(retry_sleep_seconds * (attempt + 1))
    raise RuntimeError(f"failed fetching {product_id} {iso_z(start)} -> {iso_z(end)}: {last_exc}")


def fetch_product(product_id, start, end, sleep_seconds, retries, retry_sleep_seconds):
    import pandas as pd

    rows: list[list[float]] = []
    cursor = start
    while cursor < end:
        chunk_end = min(cursor + timedelta(days=CHUNK_DAYS), end)
        print(f"{product_id}: {iso_z(cursor)} -> {iso_z(chunk_end)}", flush=True)
        rows.extend(fetch_chunk_with_retries(product_id, cursor, chunk_end, retries, retry_sleep_seconds))
        cursor = chunk_end
        time.sleep(sleep_seconds)

    if not rows:
        raise RuntimeError(f"no rows returned for {product_id}")

    df = pd.DataFrame(rows, columns=["time", "low", "high", "open", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_localize(None)
    df = df[["timestamp", "open", "high", "low", "close", "volume"]].copy()
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    start_naive, end_naive = start.replace(tzinfo=None), end.replace(tzinfo=None)
    df = df.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last")
    df = df[(df["timestamp"] >= start_naive) & (df["timestamp"] <= end_naive)]
    return df.reset_index(drop=True)


def validate_daily(df, product_id: str) -> list[str]:
    import pandas as pd

    warnings: list[str] = []
    if df.empty:
        return [f"{product_id}: empty dataframe"]
    if df["timestamp"].duplicated().any():
        warnings.append(f"{product_id}: duplicate timestamps remain")
    if not df["timestamp"].is_monotonic_increasing:
        warnings.append(f"{product_id}: timestamps are not monotonic increasing")
    null_counts = df.isna().sum()
    null_counts = null_counts[null_counts > 0]
    if len(null_counts):
        warnings.append(f"{product_id}: null values {null_counts.to_dict()}")
    bad_ohlc = (
        (df["open"] <= 0) | (df["high"] <= 0) | (df["low"] <= 0) | (df["close"] <= 0)
        | (df["high"] < df["low"]) | (df["open"] > df["high"]) | (df["open"] < df["low"])
        | (df["close"] > df["high"]) | (df["close"] < df["low"])
    )
    if bad_ohlc.any():
        warnings.append(f"{product_id}: bad OHLC rows={int(bad_ohlc.sum())}")
    if (df["volume"] < 0).any():
        warnings.append(f"{product_id}: negative volume rows={int((df['volume'] < 0).sum())}")
    gaps = df["timestamp"].diff().dropna()
    missing = gaps[gaps > pd.Timedelta(days=1)]
    if len(missing):
        first_idx = missing.index[0]
        prev_ts = df.loc[first_idx - 1, "timestamp"] if first_idx > 0 else None
        warnings.append(f"{product_id}: {len(missing)} gaps > 1d; first gap {prev_ts} -> {df.loc[first_idx, 'timestamp']}")
    return warnings


def output_name(product_id: str, start: datetime, end: datetime) -> str:
    compact = product_id.lower().replace("-", "")
    return f"{compact}_86400s_{start:%Y-%m-%d}_to_{end:%Y-%m-%d}.csv"


def load_probe_start_dates(probe_json_path: Path) -> dict[str, datetime]:
    payload = json.loads(probe_json_path.read_text(encoding="utf-8"))
    out: dict[str, datetime] = {}
    for entry in payload.get("products", []):
        if entry.get("reachable") and entry.get("earliest_date"):
            out[entry["product_id"]] = parse_utc(entry["earliest_date"])
    return out


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument("--products", nargs="+", default=None,
                     help="Product ids to fetch. Defaults to every reachable product in --probe-json.")
    ap.add_argument("--probe-json", default="artifacts/coinbase_spot_momentum_universe_probe.json",
                     help="Source of per-product earliest-available-date start times.")
    ap.add_argument("--end", default=None, help="UTC end date, defaults to now.")
    ap.add_argument("--out-dir", default="data")
    ap.add_argument("--sleep-seconds", type=float, default=DEFAULT_SLEEP_SECONDS)
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--retry-sleep-seconds", type=float, default=2.0)
    return ap.parse_args(argv)


def run(args: argparse.Namespace) -> list[FetchSummary]:
    starts = load_probe_start_dates(Path(args.probe_json))
    if not starts:
        raise RuntimeError(f"no reachable products with a known start date in {args.probe_json}")

    products = args.products if args.products else sorted(starts.keys())
    end = parse_utc(args.end) if args.end else datetime.now(timezone.utc)

    out_dir = Path(args.out_dir)
    summaries: list[FetchSummary] = []
    for product_id in products:
        if product_id not in starts:
            print(f"SKIP {product_id}: no start date in {args.probe_json} -- run the probe first")
            continue
        start = starts[product_id]
        if end <= start:
            print(f"SKIP {product_id}: end <= start ({iso_z(start)} -> {iso_z(end)})")
            continue
        df = fetch_product(product_id, start, end, args.sleep_seconds, args.retries, args.retry_sleep_seconds)
        warnings = validate_daily(df, product_id)
        out_path = out_dir / output_name(product_id, start, end)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out_path, index=False, quoting=csv.QUOTE_MINIMAL)
        summaries.append(FetchSummary(
            product_id=product_id, out_path=out_path, rows=len(df),
            start=str(df["timestamp"].min()) if len(df) else "",
            end=str(df["timestamp"].max()) if len(df) else "",
            warnings=warnings,
        ))
    return summaries


def main(argv: list[str] | None = None) -> int:
    summaries = run(parse_args(argv))
    print("\n=== FETCH SUMMARY ===")
    clean = 0
    for s in summaries:
        print(f"{s.product_id}: {s.rows} rows, {s.start} -> {s.end}, wrote {s.out_path}")
        if s.warnings:
            for w in s.warnings:
                print(f"  warning: {w}")
        else:
            clean += 1
    print(f"\n{clean}/{len(summaries)} products clean, {len(summaries) - clean} with warnings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
