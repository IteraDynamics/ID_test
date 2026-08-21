"""Campaign #53 confirmation-stage acquisition: log CDE's live funding rate snapshot.

§3a-iii (2026-08-21) redesigned the confirmation stage around live-forward accumulation: CDE's
historical funding endpoint needs a credential type not obtainable on this operator's account,
but the *current* funding rate snapshot -- `future_product_details.funding_rate`, confirmed
accessible with no special credential in the original 2026-08-12 feasibility work and reconfirmed
by `scripts/probe_cde_funding_coverage.py` -- remains available. This builds the confirmation
holdout going forward, one snapshot at a time, since there is nothing to backfill.

Each run appends one row per instrument to a growing CSV -- idempotent by (product_id,
observed_at_hour): re-running within the same UTC hour does not create a duplicate row for that
hour, so this is safe to invoke more often than strictly necessary (e.g. from a retry) without
corrupting the log.

Meant to be scheduled (e.g. Windows Task Scheduler, hourly, matching CDE's own confirmed hourly
funding_rate cadence) rather than run once -- a single invocation logs one point, not a history.

Public, unauthenticated /market/ endpoint. Read-only against Coinbase; the only write is
appending to the log file this script owns.
"""

from __future__ import annotations

import argparse
import csv
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE = "https://api.coinbase.com/api/v3/brokerage/market"
USER_AGENT = "itera-research-fetcher/1.0"
TIMEOUT_SECONDS = 20

PRODUCTS = {"BTC": "BIP-20DEC30-CDE", "ETH": "ETP-20DEC30-CDE"}

FIELDNAMES = ["observed_at_utc", "observed_hour_utc", "asset", "product_id", "funding_rate", "funding_interval", "index_price"]


def http(url: str) -> tuple[int, Any, str | None]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, json.loads(response.read().decode("utf-8")), None
    except urllib.error.HTTPError as exc:
        return exc.code, None, f"HTTP {exc.code}: {exc.reason}"
    except Exception as exc:  # noqa: BLE001
        return 0, None, f"{type(exc).__name__}: {exc}"


def fetch_snapshot(asset: str, product_id: str, now: datetime) -> dict[str, Any]:
    status, payload, error = http(f"{BASE}/products/{product_id}")
    if status != 200 or payload is None:
        raise RuntimeError(f"failed fetching {product_id}: HTTP {status} ({error})")
    fpd = payload.get("future_product_details") or {}
    return {
        "observed_at_utc": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "observed_hour_utc": now.strftime("%Y-%m-%dT%H:00:00Z"),
        "asset": asset,
        "product_id": product_id,
        "funding_rate": fpd.get("funding_rate"),
        "funding_interval": fpd.get("funding_interval"),
        "index_price": fpd.get("index_price"),
    }


def load_existing_hours(log_path: Path) -> set[tuple[str, str]]:
    if not log_path.exists():
        return set()
    seen: set[tuple[str, str]] = set()
    with log_path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            seen.add((row["product_id"], row["observed_hour_utc"]))
    return seen


def append_rows(log_path: Path, rows: list[dict[str, Any]]) -> None:
    write_header = not log_path.exists()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, lineterminator="\n")
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--assets", nargs="+", default=["BTC", "ETH"], choices=list(PRODUCTS))
    p.add_argument("--log-path", default="data/cde_live_funding_rate_log.csv")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    log_path = Path(args.log_path)
    now = datetime.now(timezone.utc)

    already_logged = load_existing_hours(log_path)
    new_rows: list[dict[str, Any]] = []
    skipped: list[str] = []

    for asset in args.assets:
        product_id = PRODUCTS[asset]
        hour_key = now.strftime("%Y-%m-%dT%H:00:00Z")
        if (product_id, hour_key) in already_logged:
            skipped.append(f"{asset} ({product_id}) already logged for {hour_key}, skipping")
            continue
        row = fetch_snapshot(asset, product_id, now)
        new_rows.append(row)
        print(f"{asset} ({product_id}): funding_rate={row['funding_rate']} at {row['observed_at_utc']}")

    if new_rows:
        append_rows(log_path, new_rows)
        print(f"\nAppended {len(new_rows)} row(s) to {log_path}")
    for msg in skipped:
        print(msg)

    total_rows = len(load_existing_hours(log_path))
    print(f"Total distinct (product, hour) observations logged so far: {total_rows}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
