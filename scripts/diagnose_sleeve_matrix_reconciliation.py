"""Diagnose why a fold's sleeve matrix fails to reconcile against fund NAV.

Read-only. Prints the evidence needed to distinguish a pure rebasing
difference (the captured matrix is unscaled while the fund NAV is rebased to
starting capital) from a genuine structural mismatch (different sleeves,
different index, or drifting composition).

Usage:
    python scripts/diagnose_sleeve_matrix_reconciliation.py \
        --fold-dir artifacts/trend_persistence_v0/portfolio_integration/core_wfo/<scenario>/folds/2020
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
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent

from scripts.export_core_v1_canonical_sleeve_matrix import _read_matrix, _read_series


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fold-dir", required=True)
    p.add_argument("--start", default=None, help="Optional slice start (default: fold NAV start).")
    p.add_argument("--end", default=None, help="Optional slice end (default: fold NAV end).")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    fold_dir = Path(args.fold_dir)

    matrix = _read_matrix(fold_dir / "canonical_full_sleeve_equity_matrix.csv")
    fold_nav = _read_series(fold_dir / "stitched_fund_nav_from_sleeves.csv")

    print(f"captured matrix : {len(matrix):,} rows x {len(matrix.columns)} cols")
    print(f"  columns       : {sorted(matrix.columns)}")
    print(f"  index range   : {matrix.index.min()} .. {matrix.index.max()}")
    print(f"fold NAV        : {len(fold_nav):,} rows")
    print(f"  index range   : {fold_nav.index.min()} .. {fold_nav.index.max()}")

    start = pd.Timestamp(args.start) if args.start else fold_nav.index.min()
    end = pd.Timestamp(args.end) if args.end else fold_nav.index.max()
    sliced = matrix.loc[start:end].dropna(how="any")
    common = sliced.index.intersection(fold_nav.index)
    sliced = sliced.loc[common]
    nav = fold_nav.loc[common]
    print(f"\ncommon timestamps: {len(common):,}")
    if common.empty:
        print("VERDICT: no overlapping timestamps — structural mismatch, not a rebasing issue.")
        return 1

    total = sliced.sum(axis=1)
    print(f"  matrix sum first: {total.iloc[0]:,.6f}")
    print(f"  fund NAV first  : {nav.iloc[0]:,.6f}")

    raw_delta = (total - nav).abs().max()
    print(f"\nraw max delta (current check): {raw_delta:,.6f}")

    implied_scale = float(nav.iloc[0]) / float(total.iloc[0])
    rebased_delta = (total * implied_scale - nav).abs().max()
    print(f"implied constant scale       : {implied_scale:.12f}")
    print(f"rebased max delta            : {rebased_delta:,.12f}")

    ratio = (nav / total)
    print(f"pointwise ratio min/max      : {ratio.min():.12f} / {ratio.max():.12f}")
    print(f"pointwise ratio spread       : {ratio.max() - ratio.min():.3e}")

    print()
    if rebased_delta <= 1e-6:
        print("VERDICT: PURE REBASING DIFFERENCE.")
        print("  The captured matrix is unscaled; the fund NAV is rebased to starting capital.")
        print("  Sleeve composition is intact. The reconciliation check is comparing")
        print("  apples to oranges and should rebase before differencing.")
        return 0
    print("VERDICT: STRUCTURAL MISMATCH — not explained by a constant scale factor.")
    print("  The sleeve set, index, or composition genuinely differs from the fund NAV.")
    print("  Do NOT paper over this; the reconciliation guard is correct to fail.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
