from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


POLYGON_BASE_URL = "https://api.polygon.io"
SUPPORTED_INTERVALS = {
    "1h": (1, "hour", "3600s"),
    "1d": (1, "day", "1D"),
}


@dataclass(frozen=True)
class DownloadRequest:
    asset: str
    start: str
    end: str
    interval: str
    adjusted: bool
    provider: str


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Canonical research-only equity/ETF OHLCV downloader. Downloads one or more assets "
            "into Itera's normalized timestamp,open,high,low,close,volume CSV schema."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--asset",
        action="append",
        required=True,
        help="Ticker to download. Repeat this option for multiple assets, e.g. --asset SPY --asset QQQ.",
    )
    p.add_argument("--interval", choices=sorted(SUPPORTED_INTERVALS), default="1h")
    p.add_argument("--start", default="2018-01-01")
    p.add_argument("--end", default="2025-12-31")
    p.add_argument("--provider", choices=["polygon"], default="polygon")
    p.add_argument("--api-key", help="Provider API key. Defaults to POLYGON_API_KEY.")
    p.add_argument("--output-dir", default="data")
    p.add_argument("--adjusted", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--sleep-seconds", type=float, default=0.25, help="Delay between provider requests")
    p.add_argument("--max-retries", type=int, default=5)
    return p.parse_args()


def _parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Expected YYYY-MM-DD date, received {value!r}") from exc


def _validate_range(start: str, end: str) -> tuple[date, date]:
    start_date = _parse_iso_date(start)
    end_date = _parse_iso_date(end)
    if end_date < start_date:
        raise ValueError(f"End date {end} is before start date {start}")
    return start_date, end_date


def _output_path(output_dir: Path, request: DownloadRequest) -> Path:
    asset = request.asset.upper()
    if request.interval == "1d" and request.start == "2018-01-01" and request.end == "2025-12-31":
        return output_dir / f"{asset}_1D.csv"
    suffix = SUPPORTED_INTERVALS[request.interval][2]
    return output_dir / f"{asset.lower()}_{suffix}_{request.start}_to_{request.end}.csv"


def _chunk_ranges(start: date, end: date, interval: str) -> Iterable[tuple[date, date]]:
    # Year-sized chunks keep responses manageable and avoid silently truncating large intraday requests.
    cursor = start
    while cursor <= end:
        if interval == "1h":
            chunk_end = min(end, date(cursor.year, 12, 31))
        else:
            chunk_end = min(end, cursor + timedelta(days=3650))
        yield cursor, chunk_end
        cursor = chunk_end + timedelta(days=1)


def _request_json(url: str, max_retries: int) -> dict[str, Any]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "IteraDynamics-ResearchDownloader/1.0",
    }
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, dict):
                raise RuntimeError(f"Unexpected non-object response from provider: {type(payload).__name__}")
            return payload
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            last_error = RuntimeError(f"Provider HTTP {exc.code}: {body[:500]}")
            if exc.code not in {429, 500, 502, 503, 504} or attempt >= max_retries:
                raise last_error from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt >= max_retries:
                raise RuntimeError(f"Provider request failed after {max_retries + 1} attempts: {exc}") from exc
        time.sleep(min(30.0, 2.0**attempt))
    raise RuntimeError(f"Provider request failed: {last_error}")


def _polygon_url(
    asset: str,
    multiplier: int,
    timespan: str,
    start: date,
    end: date,
    adjusted: bool,
    api_key: str,
) -> str:
    ticker = urllib.parse.quote(asset.upper(), safe="")
    query = urllib.parse.urlencode(
        {
            "adjusted": str(adjusted).lower(),
            "sort": "asc",
            "limit": 50000,
            "apiKey": api_key,
        }
    )
    return (
        f"{POLYGON_BASE_URL}/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/"
        f"{start.isoformat()}/{end.isoformat()}?{query}"
    )


def _append_api_key(url: str, api_key: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    if not any(key == "apiKey" for key, _ in query):
        query.append(("apiKey", api_key))
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), parsed.fragment)
    )


def _polygon_download(request: DownloadRequest, api_key: str, sleep_seconds: float, max_retries: int) -> list[dict[str, Any]]:
    multiplier, timespan, _ = SUPPORTED_INTERVALS[request.interval]
    start_date, end_date = _validate_range(request.start, request.end)
    rows_by_timestamp: dict[int, dict[str, Any]] = {}

    chunks = list(_chunk_ranges(start_date, end_date, request.interval))
    for chunk_number, (chunk_start, chunk_end) in enumerate(chunks, start=1):
        print(
            f"  chunk {chunk_number}/{len(chunks)}: {chunk_start.isoformat()} -> {chunk_end.isoformat()}",
            flush=True,
        )
        url: str | None = _polygon_url(
            request.asset,
            multiplier,
            timespan,
            chunk_start,
            chunk_end,
            request.adjusted,
            api_key,
        )
        while url:
            payload = _request_json(url, max_retries=max_retries)
            status = str(payload.get("status", "")).upper()
            if status not in {"OK", "DELAYED"}:
                message = payload.get("error") or payload.get("message") or payload
                raise RuntimeError(f"Polygon returned status={status!r}: {message}")

            for item in payload.get("results") or []:
                timestamp_ms = int(item["t"])
                rows_by_timestamp[timestamp_ms] = {
                    "timestamp": datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc).isoformat(),
                    "open": float(item["o"]),
                    "high": float(item["h"]),
                    "low": float(item["l"]),
                    "close": float(item["c"]),
                    "volume": float(item.get("v", 0.0)),
                }

            next_url = payload.get("next_url")
            url = _append_api_key(str(next_url), api_key) if next_url else None
            if url and sleep_seconds > 0:
                time.sleep(sleep_seconds)

        if sleep_seconds > 0 and chunk_number < len(chunks):
            time.sleep(sleep_seconds)

    return [rows_by_timestamp[key] for key in sorted(rows_by_timestamp)]


def _validate_rows(rows: list[dict[str, Any]], request: DownloadRequest) -> dict[str, Any]:
    if not rows:
        raise RuntimeError(f"Provider returned no rows for {request.asset}")

    timestamps = [datetime.fromisoformat(str(row["timestamp"])) for row in rows]
    if timestamps != sorted(timestamps):
        raise RuntimeError("Downloaded timestamps are not sorted")
    if len(set(timestamps)) != len(timestamps):
        raise RuntimeError("Downloaded data contains duplicate timestamps")

    requested_start, requested_end = _validate_range(request.start, request.end)
    actual_start = timestamps[0].date()
    actual_end = timestamps[-1].date()
    if actual_start > requested_start + timedelta(days=10):
        print(
            f"  WARNING: first returned bar is {actual_start}, materially later than requested {requested_start}",
            file=sys.stderr,
        )
    if actual_end < requested_end - timedelta(days=10):
        print(
            f"  WARNING: last returned bar is {actual_end}, materially earlier than requested {requested_end}",
            file=sys.stderr,
        )

    return {
        "rows": len(rows),
        "actual_start": timestamps[0].isoformat(),
        "actual_end": timestamps[-1].isoformat(),
        "requested_start": request.start,
        "requested_end": request.end,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]], overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing file without --overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["timestamp", "open", "high", "low", "close", "volume"])
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(path)


def _write_manifest(path: Path, request: DownloadRequest, validation: dict[str, Any]) -> None:
    manifest_path = path.with_suffix(path.suffix + ".manifest.json")
    payload = {
        "request": asdict(request),
        "output": str(path),
        "validation": validation,
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "schema": ["timestamp", "open", "high", "low", "close", "volume"],
    }
    temp = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    temp.replace(manifest_path)


def main() -> None:
    args = parse_args()
    _validate_range(args.start, args.end)
    api_key = args.api_key or os.getenv("POLYGON_API_KEY")
    if args.provider == "polygon" and not api_key:
        raise RuntimeError(
            "Polygon API key is required. Set POLYGON_API_KEY or pass --api-key. "
            "Deep multi-year 1-hour ETF history cannot be obtained reliably from the existing free Yahoo path."
        )

    output_dir = Path(args.output_dir)
    assets = list(dict.fromkeys(asset.strip().upper() for asset in args.asset if asset.strip()))
    if not assets:
        raise ValueError("At least one non-empty --asset is required")

    print("Itera equity/ETF OHLCV downloader")
    print(f"Provider: {args.provider}")
    print(f"Assets: {assets}")
    print(f"Interval: {args.interval}")
    print(f"Window: {args.start} -> {args.end}")
    print()

    for position, asset in enumerate(assets, start=1):
        request = DownloadRequest(
            asset=asset,
            start=args.start,
            end=args.end,
            interval=args.interval,
            adjusted=bool(args.adjusted),
            provider=args.provider,
        )
        path = _output_path(output_dir, request)
        print(f"[{position}/{len(assets)}] {asset} -> {path}", flush=True)
        rows = _polygon_download(request, api_key, args.sleep_seconds, args.max_retries)
        validation = _validate_rows(rows, request)
        _write_csv(path, rows, overwrite=args.overwrite)
        _write_manifest(path, request, validation)
        print(
            f"  wrote {validation['rows']:,} rows | {validation['actual_start']} -> {validation['actual_end']}",
            flush=True,
        )
        print()

    print("Download complete")


if __name__ == "__main__":
    main()
