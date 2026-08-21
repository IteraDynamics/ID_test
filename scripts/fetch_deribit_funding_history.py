"""Campaign #53 discovery-stage acquisition: Deribit multi-year BTC/ETH funding history.

Authorized by the 2026-08-20 board transition (docs/ITERA_CAMPAIGN_BOARD.md): Section 3/4 of
docs/research/CAMPAIGN_53_FUNDING_CARRY_PLANNING_CHARTER.md are frozen, and per that document's
Decided-2026-08-14 option 3, discovery runs on Deribit's multi-year funding history while
confirmation runs on CDE's own data. §3a-iii (2026-08-21) redesigned the confirmation stage
around live-forward accumulation since CDE's historical funding endpoint requires a credential
type not obtainable on this operator's account -- that does not affect this script, which is
discovery-side acquisition only and was never blocked by the CDE finding.

Endpoint (`https://www.deribit.com/api/v2/public/get_funding_rate_history`), symbol format
(`BTC-PERPETUAL`, `ETH-PERPETUAL`), and response field name (`interest_8h`, Deribit's own name
for the 8-hour funding rate, not "funding_rate") are all reused exactly as already validated in
`scripts/probe_funding_data_sources.py`'s `deribit()` function -- not re-derived here.

Public, unauthenticated endpoint. Fetches in bounded time-window chunks (Deribit's own per-call
record limits are undocumented from this environment; a conservative chunk size stays well under
any plausible cap) with retries, validates the result (monotonic timestamps, no duplicates, gap
detection against the expected 8-hour cadence), and writes a source manifest with a SHA-256
digest of the output, per this repo's canonical-artifact convention (CLAUDE.md: "Canonical
artifacts are LF-only with SHA-256 digests").

Writes to `data/` (gitignored, per repo convention) -- not `artifacts/`, since this is acquired
research input, not a derived research result.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE_URL = "https://www.deribit.com/api/v2/public/get_funding_rate_history"
USER_AGENT = "itera-research-fetcher/1.0"
TIMEOUT_SECONDS = 25
EXPECTED_CADENCE_HOURS = 8

SYMBOLS = {"BTC": "BTC-PERPETUAL", "ETH": "ETH-PERPETUAL"}


@dataclass(frozen=True)
class FetchSummary:
    asset: str
    symbol: str
    out_path: Path
    manifest_path: Path
    rows: int
    start: str
    end: str
    sha256: str
    warnings: list[str]


def parse_utc(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def http(url: str) -> tuple[int, Any, str | None]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, json.loads(response.read().decode("utf-8")), None
    except urllib.error.HTTPError as exc:
        return exc.code, None, f"HTTP {exc.code}: {exc.reason}"
    except Exception as exc:  # noqa: BLE001
        return 0, None, f"{type(exc).__name__}: {exc}"


def fetch_chunk_with_retries(symbol: str, start_ms: int, end_ms: int, retries: int, retry_sleep: float) -> list[tuple[int, float]]:
    url = f"{BASE_URL}?instrument_name={symbol}&start_timestamp={start_ms}&end_timestamp={end_ms}"
    last_error: str | None = None
    for attempt in range(retries + 1):
        status, payload, error = http(url)
        if status == 200 and payload is not None:
            rows = payload.get("result", []) or []
            return [(int(r["timestamp"]), float(r["interest_8h"])) for r in rows]
        last_error = error
        if attempt < retries:
            time.sleep(retry_sleep * (attempt + 1))
    raise RuntimeError(f"failed fetching {symbol} {start_ms}..{end_ms} after {retries + 1} attempts: {last_error}")


def fetch_symbol(symbol: str, start: datetime, end: datetime, chunk_days: int, sleep_seconds: float, retries: int, retry_sleep: float) -> list[tuple[int, float]]:
    all_points: dict[int, float] = {}
    cursor = start
    chunk = timedelta(days=chunk_days)
    while cursor < end:
        chunk_end = min(cursor + chunk, end)
        start_ms = int(cursor.timestamp() * 1000)
        end_ms = int(chunk_end.timestamp() * 1000)
        print(f"{symbol}: {cursor.date()} -> {chunk_end.date()}", flush=True)
        points = fetch_chunk_with_retries(symbol, start_ms, end_ms, retries, retry_sleep)
        for ts, rate in points:
            all_points[ts] = rate
        cursor = chunk_end
        time.sleep(sleep_seconds)
    return sorted(all_points.items())


def validate(points: list[tuple[int, float]], symbol: str) -> list[str]:
    warnings: list[str] = []
    if not points:
        return [f"{symbol}: no data returned at all"]
    timestamps = [p[0] for p in points]
    if timestamps != sorted(set(timestamps)):
        warnings.append(f"{symbol}: duplicate or out-of-order timestamps present")
    expected_ms = EXPECTED_CADENCE_HOURS * 3_600_000
    gaps = 0
    for i in range(1, len(timestamps)):
        delta = timestamps[i] - timestamps[i - 1]
        if delta > expected_ms * 1.5:
            gaps += 1
    if gaps:
        warnings.append(f"{symbol}: {gaps} gaps larger than 1.5x the expected {EXPECTED_CADENCE_HOURS}h cadence")
    return warnings


def write_csv(points: list[tuple[int, float]], out_path: Path) -> bytes:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["timestamp,funding_rate_8h\n"]
    for ts_ms, rate in points:
        iso = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        lines.append(f"{iso},{rate}\n")
    content = "".join(lines).encode("utf-8")
    out_path.write_bytes(content)
    return content


def write_manifest(manifest_path: Path, *, asset: str, symbol: str, source_url_pattern: str, start: datetime, end: datetime, rows: int, sha256: str, warnings: list[str]) -> None:
    manifest = {
        "asset": asset,
        "symbol": symbol,
        "source": "deribit",
        "source_url_pattern": source_url_pattern,
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "requested_start": start.isoformat(),
        "requested_end": end.isoformat(),
        "rows": rows,
        "sha256": sha256,
        "warnings": warnings,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--assets", nargs="+", default=["BTC", "ETH"], choices=list(SYMBOLS))
    p.add_argument("--start", default="2019-01-01", help="UTC start date, e.g. 2019-01-01")
    p.add_argument("--end", default=None, help="UTC end date; default now")
    p.add_argument("--out-dir", default="data")
    p.add_argument("--chunk-days", type=int, default=30)
    p.add_argument("--sleep-seconds", type=float, default=0.3)
    p.add_argument("--retries", type=int, default=3)
    p.add_argument("--retry-sleep-seconds", type=float, default=2.0)
    return p.parse_args(argv)


def run(args: argparse.Namespace) -> list[FetchSummary]:
    start = parse_utc(args.start)
    end = parse_utc(args.end) if args.end else datetime.now(timezone.utc)
    if end <= start:
        raise ValueError("--end must be after --start")

    out_dir = Path(args.out_dir)
    summaries: list[FetchSummary] = []
    for asset in args.assets:
        symbol = SYMBOLS[asset]
        points = fetch_symbol(symbol, start, end, args.chunk_days, args.sleep_seconds, args.retries, args.retry_sleep_seconds)
        warnings = validate(points, symbol)

        out_name = f"deribit_funding_{asset.lower()}_{start:%Y-%m-%d}_to_{end:%Y-%m-%d}.csv"
        out_path = out_dir / out_name
        content = write_csv(points, out_path)
        digest = hashlib.sha256(content).hexdigest()

        manifest_path = out_dir / f"{out_name}.source_manifest.json"
        write_manifest(
            manifest_path,
            asset=asset, symbol=symbol,
            source_url_pattern=f"{BASE_URL}?instrument_name={symbol}&start_timestamp=...&end_timestamp=...",
            start=start, end=end, rows=len(points), sha256=digest, warnings=warnings,
        )

        summaries.append(FetchSummary(
            asset=asset, symbol=symbol, out_path=out_path, manifest_path=manifest_path,
            rows=len(points),
            start=datetime.fromtimestamp(points[0][0] / 1000, tz=timezone.utc).isoformat() if points else "",
            end=datetime.fromtimestamp(points[-1][0] / 1000, tz=timezone.utc).isoformat() if points else "",
            sha256=digest, warnings=warnings,
        ))
    return summaries


def main(argv: list[str] | None = None) -> int:
    summaries = run(parse_args(argv))
    print("\n=== FETCH SUMMARY ===")
    for s in summaries:
        print(f"{s.asset} ({s.symbol})")
        print(f"  wrote:    {s.out_path}")
        print(f"  manifest: {s.manifest_path}")
        print(f"  rows:     {s.rows}")
        print(f"  range:    {s.start} -> {s.end}")
        print(f"  sha256:   {s.sha256}")
        if s.warnings:
            print("  warnings:")
            for w in s.warnings:
                print(f"    - {w}")
        else:
            print("  validation: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
