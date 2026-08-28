"""List distinct "Market and Exchange Names" values in the COT dataset matching a substring.

A raw text grep across the full CSV is noisy and can mislead -- it matches every column,
including the exchange-code text embedded in unrelated rows (e.g. "NASDAQ" appearing as an
exchange operator on natural gas contracts, not as part of any equity index market's name).
This reads only the "Market and Exchange Names" column and reports each DISTINCT value once,
which is what actually needs checking before passing a name to
scripts/analyze_cot_positioning_signal.py -- the same discipline scripts/fetch_cot_legacy_
futures_history.py's own docstring insists on: never assume a schema/name from memory.

--detail (2026-08-26 addition): a single search term can match several near-identical variants
of the "same" contract under different historical exchange-naming conventions (e.g. CME's old
"INTERNATIONAL MONETARY MARKET" financial-futures division name vs. its later "CHICAGO
MERCANTILE EXCHANGE" branding, or an E-mini vs. its full-size predecessor) -- exactly the kind
of ambiguity gold had (COMEX standard vs. micro vs. a CBOT variant). Guessing which variant is
the continuously-reported "real" one is the same mistake this session already made once with
gold's own market name. --detail prints each match's row count and date range instead, so the
right choice (typically: the one with by far the most rows and the longest continuous span) is
observable rather than assumed.
"""

from __future__ import annotations

import argparse

import pandas as pd


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--cot-csv", default="data/cot_legacy_futures_only_1986_present.csv")
    p.add_argument("pattern", nargs="?", default="",
                   help='Case-insensitive substring, e.g. "S&P" or "NASDAQ". Omit to match ALL '
                        "markets, which combined with --min-reports/--current-within-days "
                        "enumerates the real investable universe instead of guessing at it.")
    p.add_argument("--detail", action="store_true",
                   help="Also print row count and date range per match, to disambiguate "
                        "near-identical contract-naming variants instead of guessing.")
    p.add_argument("--min-reports", type=int, default=0,
                   help="Only show markets with at least this many weekly reports. Implies --detail.")
    p.add_argument("--current-within-days", type=int, default=None,
                   help="Only show markets still reported within this many days of the dataset's "
                        "own end. Implies --detail. Use this to find which naming variant of a "
                        "market is the LIVE one -- CFTC renamed a large batch of markets on "
                        "2026-08-26's evidence around 2022-02-01, retiring the old names.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    detail = args.detail or args.min_reports > 0 or args.current_within_days is not None
    cols = ["Market and Exchange Names"]
    if detail:
        cols.append("As of Date in Form YYYY-MM-DD")
    df = pd.read_csv(args.cot_csv, usecols=cols, low_memory=False)
    distinct = df["Market and Exchange Names"].drop_duplicates().sort_values()
    matches = distinct[distinct.str.contains(args.pattern, case=False, na=False, regex=False)]
    if matches.empty:
        print(f"No distinct market names contain {args.pattern!r}.")
        return 1
    args.detail = detail
    print(f"{len(matches)} distinct market name(s) contain {args.pattern!r}:")
    if not args.detail:
        for name in matches:
            print(f"  {name!r}")
        return 0

    all_dates = pd.to_datetime(df["As of Date in Form YYYY-MM-DD"])
    dataset_end = all_dates.max()

    rows = []
    for name in matches:
        subset = df[df["Market and Exchange Names"] == name]
        dates = pd.to_datetime(subset["As of Date in Form YYYY-MM-DD"])
        staleness = (dataset_end - dates.max()).days
        rows.append((name, len(subset), dates.min().date(), dates.max().date(), staleness))

    kept = [r for r in rows
            if r[1] >= args.min_reports
            and (args.current_within_days is None or r[4] <= args.current_within_days)]
    kept.sort(key=lambda r: r[1], reverse=True)

    if args.min_reports > 0 or args.current_within_days is not None:
        print(f"  (filtered to {len(kept)} of {len(rows)}: "
              f">= {args.min_reports} reports"
              + (f", reported within {args.current_within_days}d of {dataset_end.date()}"
                 if args.current_within_days is not None else "") + ")")
    for name, n_rows, min_date, max_date, staleness in kept:
        print(f"  {n_rows:>5} rows  {min_date} -> {max_date}  (stale {staleness:>5}d)  {name!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
