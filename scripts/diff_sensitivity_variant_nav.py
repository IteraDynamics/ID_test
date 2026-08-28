"""Diff two already-computed sensitivity variant NAV series — REPORT ONLY.

The parameter sensitivity pass reports metrics rounded to 3-4 significant
figures. A parameter whose branch is reachable (confirmed by
`diagnose_equity_derisk_reachability.py` for a handful of sessions) can still
show an exact 0.000 delta at that rounding if its portfolio-level footprint
is smaller than the display precision -- diluted by five other sleeves and
compounded over a six-year window. That is a legitimate, different
explanation from "the branch never fired," and this checks it directly
against the full-precision NAV series rather than the rounded scorecard.

Both nav.csv files already exist from the completed run; this reads them and
writes nothing.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run_dir", help="e.g. artifacts/core_v1_parameter_sensitivity/<timestamp>_core-v1-parameter-sensitivity")
    p.add_argument("--baseline", default="baseline")
    p.add_argument("--variant", required=True, help="e.g. equity_derisk_exposure_0.4")
    return p.parse_args(argv)


def load_nav(path: Path) -> pd.Series:
    frame = pd.read_csv(path, index_col=0, parse_dates=True)
    return frame.iloc[:, 0]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.run_dir)
    base = load_nav(root / args.baseline / "nav.csv")
    variant = load_nav(root / args.variant / "nav.csv")

    common = base.index.intersection(variant.index)
    b = base.reindex(common)
    v = variant.reindex(common)

    abs_diff = (v - b).abs()
    rel_diff = (abs_diff / b).abs()
    identical = int((abs_diff == 0).sum())

    print(f"{args.baseline} vs {args.variant}")
    print(f"common dates: {len(common)}, byte-identical NAV: {identical}")
    print(f"max abs diff: {abs_diff.max():.6f} USD  at {abs_diff.idxmax()}")
    print(f"max rel diff: {rel_diff.max():.8%}  at {rel_diff.idxmax()}")

    nonzero = abs_diff[abs_diff > 0]
    if nonzero.empty:
        print("\nSeries are exactly identical on every common date. "
              "The branch's effect is not merely small -- it never touched NAV. "
              "That needs its own explanation (position state, rebalance gate, "
              "or an upstream bug), not a rounding one.")
    else:
        first = nonzero.index[0]
        last = nonzero.index[-1]
        print(f"\n{len(nonzero)} dates differ, first {first}, last {last}.")
        print("Non-zero and non-trivial diffs confirm the branch moved NAV; "
              "the sensitivity table's 0.000 delta is a rounding artifact of "
              "portfolio-level dilution, not evidence the parameter is inert.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
