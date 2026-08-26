"""List distinct "Market and Exchange Names" values in the COT dataset matching a substring.

A raw text grep across the full CSV is noisy and can mislead -- it matches every column,
including the exchange-code text embedded in unrelated rows (e.g. "NASDAQ" appearing as an
exchange operator on natural gas contracts, not as part of any equity index market's name).
This reads only the "Market and Exchange Names" column and reports each DISTINCT value once,
which is what actually needs checking before passing a name to
scripts/analyze_cot_positioning_signal.py -- the same discipline scripts/fetch_cot_legacy_
futures_history.py's own docstring insists on: never assume a schema/name from memory.
"""

from __future__ import annotations

import argparse

import pandas as pd


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--cot-csv", default="data/cot_legacy_futures_only_1986_present.csv")
    p.add_argument("pattern", help='Case-insensitive substring to search for, e.g. "S&P" or "NASDAQ"')
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    names = pd.read_csv(args.cot_csv, usecols=["Market and Exchange Names"], low_memory=False)
    distinct = names["Market and Exchange Names"].drop_duplicates().sort_values()
    matches = distinct[distinct.str.contains(args.pattern, case=False, na=False, regex=False)]
    if matches.empty:
        print(f"No distinct market names contain {args.pattern!r}.")
        return 1
    print(f"{len(matches)} distinct market name(s) contain {args.pattern!r}:")
    for name in matches:
        print(f"  {name!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
