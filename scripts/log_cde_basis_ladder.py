"""Campaign #53 structural family (basis): live ladder logger.

The first real snapshot (2026-08-25, scripts/probe_cde_basis_snapshot.py) found liquidity
concentrated almost entirely in the front-month dated contract, which also had only ~3 days left
to expiry -- not a good moment to judge this candidate from a single observation. Per §3a-ii/§3b,
this specification deliberately left the mark-to-market risk tolerance and roll-timing N unset
pending real data; setting either from one snapshot would be exactly the kind of premature
conclusion this program has otherwise been careful to avoid.

Logs the FULL dated-contract ladder for BTC and ETH (not just one "chosen" candidate) plus each
root's perp-style leg, every run -- idempotent by (product_id, observed_hour), same pattern as
scripts/log_cde_live_funding_rate.py. Not backfillable (same reason CDE's funding confirmation
holdout isn't): this is a live market's contract listing and liquidity, not history. The point is
to watch at least one full roll cycle (~1 month, front contract expires 2026-08-28) before setting
anything.

Public, unauthenticated /market/ endpoint. Read-only against Coinbase; the only write is
appending to the log file this script owns.
"""

from __future__ import annotations

# Preserve direct-file execution; package imports use normal discovery.
if __package__ in (None, ""):
    try:
        from _checkout_bootstrap import bootstrap as _bootstrap_checkout
    except ModuleNotFoundError as _bootstrap_error:
        if _bootstrap_error.name != "_checkout_bootstrap":
            raise
        from scripts._checkout_bootstrap import bootstrap as _bootstrap_checkout
    _bootstrap_checkout(__file__)


import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


from scripts.probe_cde_basis_snapshot import (
    BASE,
    ROOTS,
    dated_ladder,
    find_current_pair,
    http,
    to_float,
)

FIELDNAMES = [
    "observed_at_utc", "observed_hour_utc", "root", "product_id", "leg_type",
    "contract_expiry", "days_to_expiry", "price", "index_price", "funding_rate", "volume_24h",
]


def days_to_expiry(fpd: dict) -> float | None:
    tte_ms = to_float(fpd.get("time_to_expiry_ms"))
    return tte_ms / 1000 / 86400 if tte_ms is not None else None


def row_from_product(p: dict, leg_type: str, now: datetime) -> dict[str, Any]:
    fpd = p.get("future_product_details") or {}
    return {
        "observed_at_utc": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "observed_hour_utc": now.strftime("%Y-%m-%dT%H:00:00Z"),
        "root": fpd.get("contract_root_unit", ""),
        "product_id": p.get("product_id"),
        "leg_type": leg_type,
        "contract_expiry": fpd.get("contract_expiry", ""),
        "days_to_expiry": days_to_expiry(fpd),
        "price": to_float(p.get("price")),
        "index_price": to_float(fpd.get("index_price")),
        "funding_rate": to_float(fpd.get("funding_rate")),
        "volume_24h": to_float(p.get("approximate_quote_24h_volume")),
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
    p.add_argument("--log-path", default="data/cde_basis_ladder_log.csv")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    log_path = Path(args.log_path)
    now = datetime.now(timezone.utc)

    status, payload, error = http(f"{BASE}/products?product_type=FUTURE&contract_expiry_type=EXPIRING")
    if not isinstance(payload, dict):
        print(f"Universe fetch failed: HTTP {status} ({error})")
        return 1
    products = [p for p in payload.get("products", []) if isinstance(p, dict)]
    cde = [p for p in products
           if str((p.get("future_product_details") or {}).get("venue", "")).lower() == "cde"]

    already_logged = load_existing_hours(log_path)
    new_rows: list[dict[str, Any]] = []
    skipped = 0

    for r in ROOTS:
        perp, _ = find_current_pair(cde, r)
        candidates: list[tuple[dict, str]] = []
        if perp:
            candidates.append((perp, "perp"))
        candidates.extend((p, "dated") for p in dated_ladder(cde, r))

        for p, leg_type in candidates:
            product_id = str(p.get("product_id"))
            hour_key = now.strftime("%Y-%m-%dT%H:00:00Z")
            if (product_id, hour_key) in already_logged:
                skipped += 1
                continue
            row = row_from_product(p, leg_type, now)
            new_rows.append(row)
            vol_str = f"${row['volume_24h']:,.0f}" if row["volume_24h"] is not None else "?"
            print(f"{r} {leg_type:<5} {product_id:<18} price={row['price']} "
                  f"days_to_expiry={row['days_to_expiry']} vol_24h={vol_str}")

    if new_rows:
        append_rows(log_path, new_rows)
        print(f"\nAppended {len(new_rows)} row(s) to {log_path}")
    if skipped:
        print(f"Skipped {skipped} row(s) already logged for this hour.")

    total_rows = len(load_existing_hours(log_path))
    print(f"Total distinct (product, hour) observations logged so far: {total_rows}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
