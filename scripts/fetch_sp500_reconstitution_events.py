"""Campaign #58 (planning) — S&P 500 reconstitution event calendar, Stage 1 of 2.

Fetches Wikipedia's "List of S&P 500 companies" page and extracts its
"Selected changes to the list of S&P 500 components" table into a clean,
long-format event calendar: one row per (date, ticker, action).

This is Stage 1 only. It produces the *event calendar* -- which tickers
changed, when, add or remove. It does NOT pull price data. Stage 2 (a
separate analysis script, not yet written) needs per-ticker daily OHLCV
for every ticker this stage discovers, pulled via the existing
scripts/download_equity_data.py.

UNTESTED against the live page -- this environment cannot reach Wikipedia
to verify (same network policy that blocked Yahoo Finance and Stooq).
Written defensively: it validates its own assumptions about the table's
structure and fails with a specific, readable error rather than silently
parsing garbage if Wikipedia's table layout has changed. If it fails,
send back the exact error -- that tells me which assumption broke.

Known trap, handled here: Wikipedia/S&P notation uses a dot for share
classes (e.g. "BRK.B"); Yahoo Finance (and therefore
download_equity_data.py) uses a hyphen ("BRK-B"). Tickers are normalized
on the way out. If a ticker still fails to price in Stage 2, check this
mapping first before assuming the data is missing.

Uses only the standard library plus BeautifulSoup (already installed
transitively via the yfinance dependency added for Stage 0) -- no new
dependency required.
"""

from __future__ import annotations

import argparse
import csv
import re
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
USER_AGENT = (
    "Mozilla/5.0 (compatible; IteraDynamicsResearch/1.0; research-only, "
    "non-commercial historical index membership lookup)"
)

# Wikipedia/S&P share-class notation ("BRK.B") -> Yahoo Finance notation ("BRK-B").
TICKER_DOT_TO_DASH = re.compile(r"\.")


@dataclass(frozen=True)
class ChangeEvent:
    date: str  # ISO 8601
    ticker: str
    action: str  # "add" | "remove"
    company: str
    reason: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--start-date",
        default="2015-01-01",
        help="Only keep events on or after this date (keeps the Stage 2 ticker list manageable).",
    )
    parser.add_argument("--output-dir", default="data")
    parser.add_argument(
        "--output-name",
        default="sp500_reconstitution_events.csv",
        help="Output CSV filename, written under --output-dir.",
    )
    parser.add_argument(
        "--debug-list-tables",
        action="store_true",
        help="Print every <table> on the page (index, class attribute, header text) and exit, "
        "instead of trying to locate the changes table. Use this to diagnose a "
        "'no wikitable matched' failure by seeing the page's real structure.",
    )
    return parser.parse_args()


def debug_list_tables(soup: BeautifulSoup) -> None:
    all_tables = soup.find_all("table")
    print(f"Found {len(all_tables)} <table> element(s) total on the page (any class).\n")
    for index, table in enumerate(all_tables):
        classes = table.get("class", [])
        header_cells = table.find_all("th")[:8]
        header_preview = [cell.get_text(strip=True) for cell in header_cells]
        caption = table.find("caption")
        caption_text = caption.get_text(strip=True) if caption else ""
        print(f"[{index}] class={classes!r} caption={caption_text!r}")
        print(f"     first ~8 <th> cells: {header_preview}")
        print()


def fetch_page_html(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def find_changes_table(soup: BeautifulSoup):
    """Locate the changes table by header content, not position -- table order
    on the page is not something this script should assume is stable."""
    candidates = soup.find_all("table", class_="wikitable")
    if not candidates:
        raise RuntimeError(
            "No table with class='wikitable' found on the page at all. "
            "Wikipedia's page structure may have changed significantly, or "
            "the fetch did not actually return the article (check for a "
            "login wall, redirect, or CAPTCHA page instead)."
        )

    for table in candidates:
        header_text = " ".join(
            cell.get_text(strip=True).lower() for cell in table.find_all(["th"])
        )
        if "date" in header_text and "ticker" in header_text and (
            "added" in header_text or "removed" in header_text
        ):
            return table

    raise RuntimeError(
        f"Found {len(candidates)} wikitable(s) on the page, but none had header "
        "cells containing ('date' and 'ticker' and ('added' or 'removed')). "
        "The changes table's headers likely changed wording -- inspect the "
        "page manually and update find_changes_table()'s keyword match."
    )


def _clean_cell(cell) -> str:
    return cell.get_text(strip=True)


def parse_changes_table(table) -> list[ChangeEvent]:
    rows = table.find_all("tr")
    if len(rows) < 3:
        raise RuntimeError(
            f"Changes table has only {len(rows)} <tr> rows; expected a two-row "
            "header plus many data rows. Table structure assumption failed."
        )

    # Expect a two-tier header: row 0 has ~5 <th> (Date | Added(colspan2) |
    # Removed(colspan2) | Reason), row 1 has the 4 sub-headers
    # (Ticker, Security, Ticker, Security). Validate this rather than assume it.
    header_row_0 = [c.get_text(strip=True).lower() for c in rows[0].find_all(["th", "td"])]
    header_row_1 = [c.get_text(strip=True).lower() for c in rows[1].find_all(["th", "td"])]
    if "ticker" not in " ".join(header_row_1):
        raise RuntimeError(
            f"Expected row 1 of the changes table to contain sub-headers "
            f"including 'Ticker'; got {header_row_1!r}. The two-tier header "
            f"assumption (row 0: {header_row_0!r}) does not hold -- this "
            "script's column-position logic needs updating for the real layout."
        )

    events: list[ChangeEvent] = []
    skipped: list[str] = []
    data_rows = rows[2:]

    for row in data_rows:
        cells = row.find_all(["td", "th"])
        if len(cells) < 5:
            skipped.append(f"too few cells ({len(cells)}): {[c.get_text(strip=True) for c in cells]}")
            continue

        date_text, added_ticker, added_security, removed_ticker, removed_security = (
            _clean_cell(cells[0]),
            _clean_cell(cells[1]),
            _clean_cell(cells[2]),
            _clean_cell(cells[3]),
            _clean_cell(cells[4]),
        )
        reason = _clean_cell(cells[5]) if len(cells) > 5 else ""

        iso_date = _parse_wikipedia_date(date_text)
        if iso_date is None:
            skipped.append(f"unparseable date {date_text!r} in row: {[c.get_text(strip=True) for c in cells]}")
            continue

        if added_ticker:
            events.append(
                ChangeEvent(
                    date=iso_date,
                    ticker=_normalize_ticker(added_ticker),
                    action="add",
                    company=added_security,
                    reason=reason,
                )
            )
        if removed_ticker:
            events.append(
                ChangeEvent(
                    date=iso_date,
                    ticker=_normalize_ticker(removed_ticker),
                    action="remove",
                    company=removed_security,
                    reason=reason,
                )
            )

    if skipped:
        print(f"WARNING: skipped {len(skipped)} row(s) that did not parse cleanly:")
        for item in skipped[:10]:
            print(f"  - {item}")
        if len(skipped) > 10:
            print(f"  ... and {len(skipped) - 10} more")

    if not events:
        raise RuntimeError(
            "Parsed zero events from a table that passed structural validation. "
            "This means every data row failed to parse -- almost certainly a "
            "date-format assumption is wrong. Inspect the skipped-row list above."
        )

    return events


def _parse_wikipedia_date(text: str) -> str | None:
    text = text.strip()
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%B %d %Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _normalize_ticker(raw: str) -> str:
    ticker = raw.strip().upper()
    ticker = TICKER_DOT_TO_DASH.sub("-", ticker)
    return ticker


def write_events(events: list[ChangeEvent], output_path: Path, start_date: str) -> int:
    filtered = [event for event in events if event.date >= start_date]
    filtered.sort(key=lambda event: (event.date, event.ticker))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "ticker", "action", "company", "reason"])
        for event in filtered:
            writer.writerow([event.date, event.ticker, event.action, event.company, event.reason])

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
        "# Some of these are delisted/renamed and will fail to download individually --\n"
        "# that is expected, not a bug; Stage 2's analysis script should skip missing tickers.\n"
        f"uv run python scripts/download_equity_data.py {asset_flags} "
        f"--start {start_date} --end 2026-08-30 --output-dir data --overwrite\n",
        encoding="utf-8",
    )
    return helper_path


def main() -> None:
    args = parse_args()
    output_path = Path(args.output_dir) / args.output_name

    print(f"Fetching {WIKIPEDIA_URL} ...")
    html = fetch_page_html(WIKIPEDIA_URL)
    print(f"Fetched {len(html):,} bytes. Parsing...")

    soup = BeautifulSoup(html, "html.parser")

    if args.debug_list_tables:
        debug_list_tables(soup)
        return

    table = find_changes_table(soup)
    events = parse_changes_table(table)
    print(f"Parsed {len(events)} raw change events from the page.")

    written = write_events(events, output_path, args.start_date)
    print(f"Wrote {written} events (from {args.start_date} onward) to {output_path}")

    helper_path = write_download_helper(events, output_path, args.start_date)
    unique_tickers = len({e.ticker for e in events if e.date >= args.start_date})
    print(f"Wrote a ready-to-run price-download command for {unique_tickers} unique tickers to {helper_path}")
    print(f"Run it with: pwsh {helper_path}  (or paste its one command directly)")


if __name__ == "__main__":
    main()
