"""Tests for the fold sleeve-matrix reconciliation guard.

The captured sleeve matrix is unscaled while the fund NAV written beside it has
been rebased to starting capital. Reconciliation must forgive that single
global scale factor while still rejecting any genuine divergence in sleeve set,
index, or composition.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.export_core_v1_canonical_sleeve_matrix import reconcile_fold_matrix


def sleeve_matrix(n: int = 100, sleeves: int = 3) -> pd.DataFrame:
    index = pd.date_range("2020-01-01", periods=n, freq="h")
    rng = np.random.default_rng(7)
    return pd.DataFrame(
        {f"sleeve_{i}": 30_000 + np.cumsum(rng.normal(0, 5, n)) for i in range(sleeves)},
        index=index,
    )


def test_pure_rebasing_difference_reconciles() -> None:
    """The real-world case: matrix unscaled, NAV rebased to 100,000."""
    matrix = sleeve_matrix()
    totals = matrix.sum(axis=1)
    nav = totals * (100_000.0 / float(totals.iloc[0]))

    rebased = reconcile_fold_matrix(matrix, nav, "2020")

    assert float(rebased.sum(axis=1).iloc[0]) == pytest.approx(100_000.0)
    assert (rebased.sum(axis=1) - nav).abs().max() < 1e-6
    # Sleeve proportions are untouched by rebasing.
    assert np.allclose(
        rebased.div(rebased.sum(axis=1), axis=0),
        matrix.div(matrix.sum(axis=1), axis=0),
    )


def test_identical_series_reconcile() -> None:
    matrix = sleeve_matrix()
    nav = matrix.sum(axis=1)
    rebased = reconcile_fold_matrix(matrix, nav, "2020")
    assert (rebased.sum(axis=1) - nav).abs().max() < 1e-6


def test_missing_sleeve_still_fails() -> None:
    """Rebasing must not paper over a genuine composition mismatch."""
    matrix = sleeve_matrix()
    nav = matrix.sum(axis=1)
    dropped = matrix.drop(columns=["sleeve_2"])
    with pytest.raises(RuntimeError, match="does not reconcile"):
        reconcile_fold_matrix(dropped, nav, "2020")


def test_drifting_composition_still_fails() -> None:
    """A time-varying divergence breaks ratio constancy and must be rejected."""
    matrix = sleeve_matrix()
    nav = matrix.sum(axis=1)
    drifting = matrix.copy()
    drifting["sleeve_0"] = drifting["sleeve_0"] + np.linspace(0, 500, len(drifting))
    with pytest.raises(RuntimeError, match="ratio spread"):
        reconcile_fold_matrix(drifting, nav, "2020")


def test_non_positive_first_total_fails_closed() -> None:
    matrix = sleeve_matrix(n=10)
    matrix.iloc[0] = 0.0
    nav = pd.Series(100_000.0, index=matrix.index)
    with pytest.raises(RuntimeError, match="non-positive"):
        reconcile_fold_matrix(matrix, nav, "2020")


def test_empty_overlap_fails_closed() -> None:
    matrix = sleeve_matrix(n=0)
    nav = pd.Series(dtype=float)
    with pytest.raises(RuntimeError, match="no rows in common"):
        reconcile_fold_matrix(matrix, nav, "2020")
