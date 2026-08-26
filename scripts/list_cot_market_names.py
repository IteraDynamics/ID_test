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
    p.add_argument("pattern", help='Case-insensitive substring to search for, e.g. "S&P" or "NASDAQ"')
    p.add_argument("--detail", action="store_true",
                   help="Also print row count and date range per match, to disambiguate "
                        "near-identical contract-naming variants instead of guessing.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cols = ["Market and Exchange Names"]
    if args.detail:
        cols.append("As of Date in Form YYYY-MM-DD")
    df = pd.read_csv(args.cot_csv, usecols=cols, low_memory=False)
    distinct = df["Market and Exchange Names"].drop_duplicates().sort_values()
    matches = distinct[distinct.str.contains(args.pattern, case=False, na=False, regex=False)]
    if matches.empty:
        print(f"No distinct market names contain {args.pattern!r}.")
        return 1
    print(f"{len(matches)} distinct market name(s) contain {args.pattern!r}:")
    if not args.detail:
        for name in matches:
            print(f"  {name!r}")
        return 0

    rows = []
    for name in matches:
        subset = df[df["Market and Exchange Names"] == name]
        dates = pd.to_datetime(subset["As of Date in Form YYYY-MM-DD"])
        rows.append((name, len(subset), dates.min().date(), dates.max().date()))
    rows.sort(key=lambda r: r[1], reverse=True)
    for name, n_rows, min_date, max_date in rows:
        print(f"  {n_rows:>5} rows  {min_date} -> {max_date}  {name!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
