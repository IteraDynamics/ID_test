"""Campaign #58 (planning) — S&P 500 reconstitution event calendar, Stage 1 of 2.

Pulls a purpose-built S&P 500 change-event log and normalizes it into a
clean, long-format event calendar: one row per (date, ticker, action).

Revision note: this originally scraped Wikipedia's "List of S&P 500
companies" page directly. A real run found that page no longer has a
separate "Selected changes" table -- only the current-constituents table,
which cannot supply removal events or additions of companies later
removed (survivorship bias baked in). Verified via WebSearch/WebFetch
(not this environment's blocked direct network access) that a
purpose-built dataset exists instead: fja05680/sp500 on GitHub maintains
sp500_changes_since_2019.csv specifically for this, built by supplementing
Wikipedia's own incomplete "Selected changes" list with researched exact
dates. This script pulls that file directly -- no HTML table-structure
guessing required, since it's already structured data.

Real constraint this file's own scope imposes: it only covers changes
since 2019, not further back. --start-date below 2019-01-01 will simply
yield nothing before that date; it is not a bug in this script.

This is Stage 1 only. It produces the *event calendar* -- which tickers
changed, when, add or remove. It does NOT pull price data. Stage 2 (a
separate analysis script, not yet written) needs per-ticker daily OHLCV
for every ticker this stage discovers, pulled via the existing
scripts/download_equity_data.py.

UNTESTED against the live file -- this environment's direct network
access is blocked for exactly this kind of fetch (same policy that
blocked Yahoo Finance and Stooq); only the WebFetch/WebSearch tools used
to research and confirm the source could reach GitHub, and those don't
substitute for actually running this script. Written defensively: the
CSV's exact column names were not independently confirmed (the source
repo's README describes the file's purpose but not its schema), so this
script inspects the real header at runtime, tries several plausible
column-name matches, and fails with a specific, readable error naming
the actual header found if none match -- rather than silently
misreading columns.

Known trap, handled here: Wikipedia/S&P notation uses a dot for share
classes (e.g. "BRK.B"); Yahoo Finance (and therefore
download_equity_data.py) uses a hyphen ("BRK-B"). Tickers are normalized
on the way out. This source dataset is itself built by supplementing
Wikipedia, so the same dot notation is expected here too.

Uses only the standard library (urllib, csv) -- no new dependency.
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

SOURCE_URL = "https://raw.githubusercontent.com/fja05680/sp500/master/sp500_changes_since_2019.csv"
USER_AGENT = (
    "Mozilla/5.0 (compatible; IteraDynamicsResearch/1.0; research-only, "
    "non-commercial historical index membership lookup)"
)

TICKER_DOT_TO_DASH = re.compile(r"\.")

# Candidate substrings (checked case-insensitively) for identifying each
# semantic column in a header whose exact names were not independently
# confirmed before writing this script.
DATE_COL_HINTS = ("date",)
ADD_TICKER_COL_HINTS = ("add",)
REMOVE_TICKER_COL_HINTS = ("remov", "delet", "drop")


@dataclass(frozen=True)
class ChangeEvent:
    date: str  # ISO 8601
    ticker: str
    action: str  # "add" | "remove"
    reason: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--start-date",
        default="2019-01-01",
        help="Only keep events on or after this date. The source file itself starts in 2019 -- "
        "an earlier date here will not recover earlier events.",
    )
    parser.add_argument("--output-dir", default="data")
    parser.add_argument(
        "--output-name",
        default="sp500_reconstitution_events.csv",
        help="Output CSV filename, written under --output-dir.",
    )
    parser.add_argument(
        "--debug-show-header",
        action="store_true",
        help="Print the raw source file's header row and first 3 data rows, then exit, "
        "without attempting to parse. Use this if column matching fails.",
    )
    return parser.parse_args()


def fetch_source_csv(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def _find_column(fieldnames: list[str], hints: tuple[str, ...]) -> str | None:
    for name in fieldnames:
        lowered = name.lower()
        if any(hint in lowered for hint in hints):
            return name
    return None


def _parse_date(text: str) -> str | None:
    text = text.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _normalize_ticker(raw: str) -> str:
    ticker = raw.strip().upper()
    if not ticker:
        return ticker
    return TICKER_DOT_TO_DASH.sub("-", ticker)


def _split_tickers(raw_cell: str) -> list[str]:
    """A single row's add/remove cell can hold multiple comma-joined tickers
    (several simultaneous changes on one date, e.g. a large reconstitution
    day) -- split first, normalize each piece independently. A real run
    surfaced this: cells like "ABNB,BX" or "APO,WDAY,LII" were being passed
    through whole as one invalid ticker before this fix."""
    return [_normalize_ticker(piece) for piece in raw_cell.split(",") if piece.strip()]


def parse_events(raw_csv: str) -> list[ChangeEvent]:
    reader = csv.DictReader(io.StringIO(raw_csv))
    fieldnames = reader.fieldnames or []

    date_col = _find_column(fieldnames, DATE_COL_HINTS)
    add_col = _find_column(fieldnames, ADD_TICKER_COL_HINTS)
    remove_col = _find_column(fieldnames, REMOVE_TICKER_COL_HINTS)

    if date_col is None or (add_col is None and remove_col is None):
        raise RuntimeError(
            f"Could not identify the needed columns in the source file. "
            f"Actual header: {fieldnames!r}. "
            f"Matched date_col={date_col!r}, add_col={add_col!r}, remove_col={remove_col!r}. "
            "Re-run with --debug-show-header to see real rows, then update "
            "DATE_COL_HINTS/ADD_TICKER_COL_HINTS/REMOVE_TICKER_COL_HINTS above "
            "to match the actual column names."
        )

    events: list[ChangeEvent] = []
    skipped: list[str] = []

    for row in reader:
        date_text = row.get(date_col, "")
        iso_date = _parse_date(date_text)
        if iso_date is None:
            skipped.append(f"unparseable date {date_text!r} in row: {row}")
            continue

        reason = row.get("reason", "") or row.get("Reason", "") or ""

        if add_col is not None:
            for added_ticker in _split_tickers(row.get(add_col, "")):
                events.append(ChangeEvent(date=iso_date, ticker=added_ticker, action="add", reason=reason))

        if remove_col is not None:
            for removed_ticker in _split_tickers(row.get(remove_col, "")):
                events.append(ChangeEvent(date=iso_date, ticker=removed_ticker, action="remove", reason=reason))

    if skipped:
        print(f"WARNING: skipped {len(skipped)} row(s) that did not parse cleanly:")
        for item in skipped[:10]:
            print(f"  - {item}")
        if len(skipped) > 10:
            print(f"  ... and {len(skipped) - 10} more")

    if not events:
        raise RuntimeError(
            "Parsed zero events despite matching column names -- every row's date or "
            "ticker value was empty/unparseable. Inspect the skipped-row list above, "
            "or re-run with --debug-show-header to see real raw rows."
        )

    return events


def write_events(events: list[ChangeEvent], output_path: Path, start_date: str) -> int:
    filtered = [event for event in events if event.date >= start_date]
    filtered.sort(key=lambda event: (event.date, event.ticker))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "ticker", "action", "reason"])
        for event in filtered:
            writer.writerow([event.date, event.ticker, event.action, event.reason])

    return len(filtered)


def write_download_helper(events: list[ChangeEvent], output_path: Path, start_date: str) -> Path:
    """Emit a ready-to-run PowerShell command listing every unique ticker
    Stage 2 needs, so nothing has to be hand-copied from the CSV."""
    tickers = sorted({event.ticker for event in events if event.date >= start_date})
    asset_flags = " ".join(f"--asset {ticker}" for ticker in tickers)
    helper_path = output_path.with_name("download_reconstitution_tickers.ps1")
    helper_path.write_text(
        "# Auto-generated by scripts/fetch_sp500_reconstitution_events.py\n"
        f"# {len(tickers)} unique tickers from reconstitution events since {start_date}.\n"
        "# Some of these are genuinely delisted/renamed and will fail even after retries --\n"
        "# expected, not a bug; Stage 2's analysis script skips missing tickers and logs them.\n"
        "# --skip-existing (not --overwrite): re-running this exact command after a partial\n"
        "# failure resumes cleanly, only retrying tickers that didn't succeed last time,\n"
        "# instead of re-downloading everything and wasting requests/rate-limit budget.\n"
        f"uv run python scripts/download_equity_data.py {asset_flags} "
        f"--start {start_date} --end 2026-08-30 --output-dir data --skip-existing\n",
        encoding="utf-8",
    )
    return helper_path


def main() -> None:
    args = parse_args()
    output_path = Path(args.output_dir) / args.output_name

    print(f"Fetching {SOURCE_URL} ...")
    raw_csv = fetch_source_csv(SOURCE_URL)
    print(f"Fetched {len(raw_csv):,} bytes.")

    if args.debug_show_header:
        reader = csv.reader(io.StringIO(raw_csv))
        rows = list(reader)
        print(f"Header: {rows[0] if rows else '(empty file)'}")
        print("First 3 data rows:")
        for row in rows[1:4]:
            print(f"  {row}")
        return

    events = parse_events(raw_csv)
    print(f"Parsed {len(events)} raw change events from the source file.")

    written = write_events(events, output_path, args.start_date)
    print(f"Wrote {written} events (from {args.start_date} onward) to {output_path}")

    helper_path = write_download_helper(events, output_path, args.start_date)
    unique_tickers = len({e.ticker for e in events if e.date >= args.start_date})
    print(f"Wrote a ready-to-run price-download command for {unique_tickers} unique tickers to {helper_path}")
    print(f"Run it with: pwsh {helper_path}  (or paste its one command directly)")


if __name__ == "__main__":
    main()
