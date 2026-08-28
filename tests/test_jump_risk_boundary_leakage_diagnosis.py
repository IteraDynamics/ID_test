"""Tests for the Jump Risk train/test boundary leakage severity measurement.

Pins that the leaking rows are exactly the training set's last `horizon_bars` rows (provable
from `_future_window_stat`'s purely positional label window -- see the script's own docstring),
and that the degenerate small-training-set case is handled explicitly rather than producing a
fraction over 1.0 or a divide-by-zero.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.diagnose_jump_risk_train_test_boundary_leakage import boundary_leakage_rows


def _frame(years_and_counts: list[tuple[int, int]], positive_rate_by_year: dict[int, float], seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for year, count in years_and_counts:
        index = pd.date_range(f"{year}-01-01", periods=count, freq="h")
        rate = positive_rate_by_year.get(year, 0.1)
        labels = (rng.random(count) < rate).astype(int)
        rows.append(pd.DataFrame({"jump_up": labels}, index=index))
    return pd.concat(rows)


def test_leaking_rows_is_exactly_the_training_tail() -> None:
    frame = _frame([(2020, 1000)], {2020: 0.1})
    result = boundary_leakage_rows(frame, "jump_up", year=2021, horizon_bars=120, min_train_rows=500)
    assert result is not None
    assert result["train_rows"] == 1000
    assert result["leaking_rows"] == 120
    assert result["leaking_fraction"] == pytest.approx(120 / 1000, abs=1e-9)


def test_leaking_fraction_shrinks_as_training_set_grows() -> None:
    """Horizon is fixed; a larger expanding-window training set means a smaller leaking share --
    the leakage's proportional severity should decrease across later folds, not stay constant."""
    frame = _frame([(2018, 8760), (2019, 8760), (2020, 8760)], {2018: 0.1, 2019: 0.1, 2020: 0.1})
    early = boundary_leakage_rows(frame, "jump_up", year=2019, horizon_bars=120, min_train_rows=500)
    later = boundary_leakage_rows(frame, "jump_up", year=2021, horizon_bars=120, min_train_rows=500)
    assert early is not None and later is not None
    assert later["leaking_fraction"] < early["leaking_fraction"]
    assert early["leaking_rows"] == later["leaking_rows"] == 120  # absolute count is fixed


def test_returns_none_below_minimum_training_rows() -> None:
    frame = _frame([(2020, 100)], {2020: 0.1})
    result = boundary_leakage_rows(frame, "jump_up", year=2021, horizon_bars=120, min_train_rows=500)
    assert result is None


def test_degenerate_case_training_set_smaller_than_horizon() -> None:
    """If the whole training set is shorter than the horizon, every row leaks -- report that
    explicitly (fraction == 1.0, empty clean comparison) rather than raising or dividing by zero."""
    frame = _frame([(2020, 600)], {2020: 0.1})
    result = boundary_leakage_rows(frame, "jump_up", year=2021, horizon_bars=800, min_train_rows=500)
    assert result is not None
    assert result["leaking_rows"] == result["train_rows"] == 600
    assert result["leaking_fraction"] == pytest.approx(1.0, abs=1e-9)
    assert result["clean_positive_rate"] is None
    assert result["positive_rate_delta"] is None


def test_positive_rate_delta_detects_a_contaminated_tail() -> None:
    """A tail with a much higher positive rate than the rest of training should show up as a
    large positive delta -- the case the charter's own concern is actually about."""
    rng = np.random.default_rng(1)
    index = pd.date_range("2020-01-01", periods=1000, freq="h")
    labels = np.zeros(1000, dtype=int)
    labels[:880] = (rng.random(880) < 0.02).astype(int)  # sparse events in the "clean" bulk
    labels[880:] = 1  # the leaking tail is entirely positive -- a contaminated boundary
    frame = pd.DataFrame({"jump_up": labels}, index=index)

    result = boundary_leakage_rows(frame, "jump_up", year=2021, horizon_bars=120, min_train_rows=500)
    assert result is not None
    assert result["leaking_positive_rate"] == pytest.approx(1.0, abs=1e-9)
    assert result["clean_positive_rate"] < 0.05
    assert result["positive_rate_delta"] > 0.9
