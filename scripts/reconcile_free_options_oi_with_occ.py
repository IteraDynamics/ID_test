"""Diagnose OCC open-interest semantics for the dealer-gamma sandbox.

Research-only source-governance probe. It does not compute gamma exposure,
generate alpha, or touch runtime/portfolio state.

Important correction: OCC's `daily-open-interest` batch endpoint is a monthly
aggregate daily-open-interest report. It is NOT a historical series-level file
containing symbol/expiration/strike/call/put rows. Therefore it cannot be used
for an exact historical SPY contract-by-contract reconciliation.

OCC's public Series Search does expose current series-level open interest and
states that displayed OI is derived from the previous day's settlement, but it
does not provide a historical report-date parameter in the documented batch
interface.

This script now fails closed with an explicit classification when the aggregate
report format is encountered rather than attempting to parse its title row as a
contract schema.

For sandbox causality, the downstream gamma-state screen must lag every mirror
state by one full trading day before measuring any outcome. That conservative
lag makes the test causal whether the mirror's observation-date OI represents
same-day EOD OI or prior-settlement OI.
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
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request

import pandas as pd

# Keep standalone script execution working until the separate packaging migration.



OCC_ENDPOINT = "https://marketdata.theocc.com/daily-open-interest"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--occ-report-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--mirror-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--symbol", default="SPY")
    parser.add_argument("--output-dir", default="artifacts/free_options_occ_reconciliation")
    return parser.parse_args()


def sha256_bytes(payload: bytes) -> str:
    from research.artifact_io.v1 import sha256_bytes_v1
    return sha256_bytes_v1(payload, factory=hashlib.sha256)


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    occ_dt = pd.Timestamp(args.occ_report_date)
    query = urllib.parse.urlencode(
        {
            "reportDate": occ_dt.strftime("%m/%d/%Y"),
            "action": "download",
            "format": "csv",
        }
    )
    url = f"{OCC_ENDPOINT}?{query}"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "IteraDynamics-research-source-probe/1.0"},
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = response.read()
            content_type = response.headers.get("Content-Type")
    except Exception as exc:
        report = {
            "status": "NOT_USABLE",
            "reason": "OCC_DOWNLOAD_FAILED",
            "url": url,
            "error": f"{type(exc).__name__}: {exc}",
        }
        print(json.dumps(report, indent=2, sort_keys=True))
        return 3

    raw_path = output_dir / f"occ_daily_oi_{args.occ_report_date}.csv"
    raw_path.write_bytes(payload)
    text = payload.decode("utf-8-sig", errors="replace")
    first_nonempty = next((line.strip() for line in text.splitlines() if line.strip()), "")

    # The downloaded report begins with a title such as
    # "Daily Open Interest - January 2024" and contains aggregate daily totals,
    # not historical series-level strike/expiry rows.
    aggregate_report = "daily" in first_nonempty.lower() and "open" in first_nonempty.lower() and "interest" in first_nonempty.lower()

    report = {
        "status": "SEMANTICS_CONFIRMED_SERIES_RECONCILIATION_UNAVAILABLE" if aggregate_report else "NOT_USABLE",
        "reason": "OCC_DAILY_OPEN_INTEREST_IS_AGGREGATE_NOT_SERIES_LEVEL" if aggregate_report else "OCC_FORMAT_UNRECOGNIZED",
        "symbol": args.symbol.upper(),
        "occ_report_date": args.occ_report_date,
        "mirror_observation_date": args.mirror_date,
        "url": url,
        "bytes": len(payload),
        "sha256": sha256_bytes(payload),
        "content_type": content_type,
        "first_nonempty_line": first_nonempty,
        "occ_public_semantics": (
            "OCC Series Search states open-interest figures are derived from the previous day's settlement. "
            "The documented Series Search batch interface accepts symbolType and symbol, but no historical report-date parameter."
        ),
        "sandbox_causal_rule": (
            "Lag every mirror-derived dealer-gamma state by one full trading day before evaluating 1/2/5-day outcomes. "
            "Do not use observation-date state to predict that same trading day's return."
        ),
        "boundary": (
            "This result does not validate mirror OI values contract-by-contract. It establishes that the attempted OCC batch endpoint "
            "cannot provide that historical check for free and freezes the conservative one-day lag required for sandbox use."
        ),
    }

    report_path = output_dir / f"occ_{args.occ_report_date}_diagnostic.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if aggregate_report else 5


if __name__ == "__main__":
    raise SystemExit(main())
