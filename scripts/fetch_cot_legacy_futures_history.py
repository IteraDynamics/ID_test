"""CFTC Commitment of Traders (COT) — Legacy Futures-Only report, historical bulk acquisition.

Motivated by 2026-08-25's research session: a contrarian positioning signal (extreme speculative
positioning tends to mean-revert) is a candidate for GLD, an existing live Core v1 sleeve, using a
data source this program has never touched -- free, public, weekly since 1986, no venue/account
dependency of any kind, unlike everything crypto-related this session has had to fight for.

URL pattern confirmed directly against the real `cot_reports` PyPI package's source (not guessed,
not documentation -- read the actual requests.get() calls in its source): the combined historical
file covers 1986-2016, then one zip per year from 2017 onward. Both are public CFTC hosting, no
authentication, no API key.

    https://cftc.gov/files/dea/history/deacot1986_2016.zip   -> contains FUT86_16.txt
    https://cftc.gov/files/dea/history/deacot{year}.zip      -> contains annual.txt

This script downloads and extracts every year's raw CSV, writes one consolidated raw CSV plus a
SHA-256 manifest, per this repo's own acquisition convention (see fetch_deribit_funding_history.py).
It does NOT filter for Gold or compute anything -- the real column schema for this report has not
been confirmed against an actual downloaded file in this repo yet, and guessing column names before
seeing them is exactly the mistake this session already made once (a CSV field name, a venue root
filter, an ETF ticker) and corrected only by checking. The next script, built after this one's
output is inspected, does the actual Gold-specific filtering and signal construction.

Public, unauthenticated CFTC hosting. Read-only.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import urllib.error
import urllib.request
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

BASE = "https://cftc.gov/files/dea/history"
USER_AGENT = "itera-research-fetcher/1.0"
TIMEOUT_SECONDS = 60

COMBINED_HISTORICAL = ("deacot1986_2016.zip", "FUT86_16.txt")
YEARLY_PATTERN = ("deacot{year}.zip", "annual.txt")
FIRST_YEARLY_YEAR = 2017


def http_get(url: str) -> tuple[int, bytes | None, str | None]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, response.read(), None
    except urllib.error.HTTPError as exc:
        return exc.code, None, f"HTTP {exc.code}: {exc.reason}"
    except Exception as exc:  # noqa: BLE001
        return 0, None, f"{type(exc).__name__}: {exc}"


def fetch_zip_csv(zip_name: str, inner_txt: str) -> tuple[list[list[str]], str | None]:
    """Downloads one zip, extracts the named inner file, returns its rows (including header)."""
    url = f"{BASE}/{zip_name}"
    status, content, error = http_get(url)
    if status != 200 or content is None:
        return [], f"failed fetching {url}: HTTP {status} ({error})"
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            names = zf.namelist()
            # The inner filename's case/exact form has drifted across CFTC's own zips before;
            # match case-insensitively rather than assume the documented name is exact.
            match = next((n for n in names if n.lower() == inner_txt.lower()), None)
            if match is None:
                return [], f"{zip_name}: expected {inner_txt!r} inside, found {names}"
            with zf.open(match) as f:
                text = io.TextIOWrapper(f, encoding="utf-8", errors="replace")
                rows = list(csv.reader(text))
                return rows, None
    except zipfile.BadZipFile as exc:
        return [], f"{zip_name}: not a valid zip ({exc})"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--end-year", type=int, default=date.today().year,
                   help="Last year to fetch (inclusive). Defaults to the current year.")
    p.add_argument("--out-dir", default="data")
    p.add_argument("--out-name", default="cot_legacy_futures_only_1986_present.csv")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    all_rows: list[list[str]] = []
    header: list[str] | None = None
    warnings: list[str] = []

    print(f"Fetching combined historical file (1986-2016): {COMBINED_HISTORICAL[0]}")
    rows, error = fetch_zip_csv(*COMBINED_HISTORICAL)
    if error:
        print(f"  FAILED: {error}")
        warnings.append(error)
    elif rows:
        header = rows[0]
        all_rows.extend(rows[1:])
        print(f"  {len(rows) - 1} rows")

    for year in range(FIRST_YEARLY_YEAR, args.end_year + 1):
        zip_name = YEARLY_PATTERN[0].format(year=year)
        print(f"Fetching {year}: {zip_name}")
        rows, error = fetch_zip_csv(zip_name, YEARLY_PATTERN[1])
        if error:
            print(f"  FAILED: {error}")
            warnings.append(f"{year}: {error}")
            continue
        if not rows:
            continue
        year_header = rows[0]
        if header is None:
            header = year_header
        elif year_header != header:
            msg = (f"{year}: header differs from the combined-file header -- schema may have "
                   f"changed. Combined: {header[:5]}... this year: {year_header[:5]}...")
            print(f"  WARNING: {msg}")
            warnings.append(msg)
        all_rows.extend(rows[1:])
        print(f"  {len(rows) - 1} rows")

    if header is None or not all_rows:
        print("\nNo data acquired at all -- every fetch failed. Nothing written.")
        return 1

    out_path = out_dir / args.out_name
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(all_rows)

    digest = hashlib.sha256(out_path.read_bytes()).hexdigest()
    manifest = {
        "source": "CFTC Commitment of Traders -- Legacy Futures-Only report",
        "source_url_pattern": f"{BASE}/deacot{{1986_2016|<year>}}.zip",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "rows": len(all_rows),
        "columns": len(header),
        "column_names": header,
        "years_attempted": f"1986-{args.end_year}",
        "sha256": digest,
        "warnings": warnings,
    }
    manifest_path = out_dir / f"{args.out_name}.source_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"\nWrote {len(all_rows)} rows, {len(header)} columns, to {out_path}")
    print(f"Manifest: {manifest_path}")
    print(f"SHA-256: {digest}")
    if warnings:
        print(f"\n{len(warnings)} warning(s) -- see manifest for details.")
    print("\nColumn names (first 15):")
    for name in header[:15]:
        print(f"  {name}")
    print("\nNext step: inspect these real column names (and a few real rows) before building any")
    print("Gold-specific filtering or signal logic -- do not assume the schema from memory.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
