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

import pandas as pd


BASE_URL = "https://api.exchange.coinbase.com/products/{product_id}/candles"
GRANULARITY_SECONDS = 3600
CHUNK_HOURS = 250
DEFAULT_SLEEP_SECONDS = 0.20


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
        {
            "start": iso_z(start),
            "end": iso_z(end),
            "granularity": str(GRANULARITY_SECONDS),
        }
    )
    url = f"{BASE_URL.format(product_id=product_id)}?{params}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "IteraDynamics-research-fetcher/1.0",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = resp.read().decode("utf-8")
    return json.loads(payload)


def fetch_chunk_with_retries(
    product_id: str,
    start: datetime,
    end: datetime,
    retries: int,
    retry_sleep_seconds: float,
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


def fetch_product(
    product_id: str,
    start: datetime,
    end: datetime,
    sleep_seconds: float,
    retries: int,
    retry_sleep_seconds: float,
) -> pd.DataFrame:
    rows: list[list[float]] = []
    cursor = start

    while cursor < end:
        chunk_end = min(cursor + timedelta(hours=CHUNK_HOURS), end)
        print(f"{product_id}: {iso_z(cursor)} -> {iso_z(chunk_end)}", flush=True)
        rows.extend(fetch_chunk_with_retries(product_id, cursor, chunk_end, retries, retry_sleep_seconds))
        cursor = chunk_end
        time.sleep(sleep_seconds)

    if not rows:
        raise RuntimeError(f"no rows returned for {product_id}")

    # Coinbase Exchange response rows are [time, low, high, open, close, volume].
    df = pd.DataFrame(rows, columns=["time", "low", "high", "open", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_localize(None)
    df = df[["timestamp", "open", "high", "low", "close", "volume"]].copy()

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    start_naive = start.replace(tzinfo=None)
    end_naive = end.replace(tzinfo=None)
    df = df.sort_values("timestamp")
    df = df.drop_duplicates(subset=["timestamp"], keep="last")
    df = df[(df["timestamp"] >= start_naive) & (df["timestamp"] <= end_naive)]
    return df.reset_index(drop=True)


def validate_hourly(df: pd.DataFrame, product_id: str) -> list[str]:
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
        (df["open"] <= 0)
        | (df["high"] <= 0)
        | (df["low"] <= 0)
        | (df["close"] <= 0)
        | (df["high"] < df["low"])
        | (df["open"] > df["high"])
        | (df["open"] < df["low"])
        | (df["close"] > df["high"])
        | (df["close"] < df["low"])
    )
    if bad_ohlc.any():
        warnings.append(f"{product_id}: bad OHLC rows={int(bad_ohlc.sum())}")

    if (df["volume"] < 0).any():
        warnings.append(f"{product_id}: negative volume rows={int((df['volume'] < 0).sum())}")

    gaps = df["timestamp"].diff().dropna()
    missing = gaps[gaps > pd.Timedelta(hours=1)]
    if len(missing):
        first_idx = missing.index[0]
        prev_ts = df.loc[first_idx - 1, "timestamp"] if first_idx > 0 else None
        warnings.append(
            f"{product_id}: {len(missing)} gaps > 1h; first gap {prev_ts} -> {df.loc[first_idx, 'timestamp']}"
        )

    return warnings


def output_name(product_id: str, start: datetime, end: datetime) -> str:
    compact = product_id.lower().replace("-", "")
    return f"{compact}_3600s_{start:%Y-%m-%d}_to_{end:%Y-%m-%d}.csv"


def write_csv(df: pd.DataFrame, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False, quoting=csv.QUOTE_MINIMAL)


def run(args: argparse.Namespace) -> list[FetchSummary]:
    start = parse_utc(args.start)
    end = parse_utc(args.end)
    if end <= start:
        raise ValueError("--end must be after --start")

    out_dir = Path(args.out_dir)
    summaries: list[FetchSummary] = []
    for product_id in args.products:
        df = fetch_product(
            product_id=product_id,
            start=start,
            end=end,
            sleep_seconds=args.sleep_seconds,
            retries=args.retries,
            retry_sleep_seconds=args.retry_sleep_seconds,
        )
        warnings = validate_hourly(df, product_id)
        out_path = out_dir / output_name(product_id, start, end)
        write_csv(df, out_path)
        summaries.append(
            FetchSummary(
                product_id=product_id,
                out_path=out_path,
                rows=len(df),
                start=str(df["timestamp"].min()) if len(df) else "",
                end=str(df["timestamp"].max()) if len(df) else "",
                warnings=warnings,
            )
        )
    return summaries


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Fetch Coinbase Exchange hourly OHLCV history into research CSV format.")
    ap.add_argument("--products", nargs="+", default=["BTC-USD", "ETH-USD"])
    ap.add_argument("--start", required=True, help="UTC start date/datetime, e.g. 2018-01-01")
    ap.add_argument("--end", required=True, help="UTC end date/datetime, e.g. 2025-12-31")
    ap.add_argument("--out-dir", default="data")
    ap.add_argument("--sleep-seconds", type=float, default=DEFAULT_SLEEP_SECONDS)
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--retry-sleep-seconds", type=float, default=2.0)
    return ap.parse_args()


def main() -> None:
    summaries = run(parse_args())
    print("\n=== FETCH SUMMARY ===")
    for summary in summaries:
        print(f"{summary.product_id}")
        print(f"  wrote: {summary.out_path}")
        print(f"  rows:  {summary.rows}")
        print(f"  start: {summary.start}")
        print(f"  end:   {summary.end}")
        if summary.warnings:
            print("  warnings:")
            for warning in summary.warnings:
                print(f"    - {warning}")
        else:
            print("  validation: clean")


if __name__ == "__main__":
    main()
