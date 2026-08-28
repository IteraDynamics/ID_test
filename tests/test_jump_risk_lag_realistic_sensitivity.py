"""Tests for the realistic-lag-distribution Jump Risk sensitivity script.

Covers the pure resampling/lag-application logic in isolation from the real backtest data
(BTC/ETH canonical history and the WFO matrix live only on the operator's machine). These tests
pin: the empirical-lag derivation matches the cadence audit's own effective-lag-1 definition,
block bootstrap preserves real clustering instead of smearing it, variable-lag application is
the correct generalization of a constant `.shift()`, and the gate is the unchanged four-condition
promotion rule from the retired lag-sensitivity script.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.run_jump_risk_lag_realistic_sensitivity import (
    apply_variable_lag,
    block_bootstrap_resample,
    derive_empirical_additional_lag_bars,
    evaluate_gate,
)


# ------------------------------------------------------- derive_empirical_additional_lag_bars


def _cadence_rows(records: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(records)


def test_empirical_lag_zero_when_decision_lands_before_next_bar() -> None:
    """A decision at 0.59h past close is effective lag 1 -- zero ADDITIONAL lag."""
    rows = _cadence_rows(
        [
            {"sleeve": "ETH_1H_trend", "cycle": i, "first_sighting_of_this_bar": True, "bar_close_to_decision_hours": 0.59}
            for i in range(150)
        ]
    )
    lags = derive_empirical_additional_lag_bars(rows, "ETH_1H_trend")
    assert (lags == 0).all()


def test_empirical_lag_counts_full_bars_past_the_next_boundary() -> None:
    """1.2h past close means the next hourly bar already closed -- 1 bar of additional lag."""
    rows = _cadence_rows(
        [
            {"sleeve": "ETH_1H_trend", "cycle": i, "first_sighting_of_this_bar": True, "bar_close_to_decision_hours": 1.2}
            for i in range(150)
        ]
    )
    lags = derive_empirical_additional_lag_bars(rows, "ETH_1H_trend")
    assert (lags == 1).all()


def test_empirical_lag_excludes_stale_relogs() -> None:
    """Only first_sighting_of_this_bar rows count -- re-logs of an already-decided bar aren't
    a fresh measurement of reaction speed."""
    records = [
        {"sleeve": "ETH_1H_trend", "cycle": i, "first_sighting_of_this_bar": True, "bar_close_to_decision_hours": 0.5}
        for i in range(150)
    ]
    records += [
        {"sleeve": "ETH_1H_trend", "cycle": 1000 + i, "first_sighting_of_this_bar": False, "bar_close_to_decision_hours": 5.0}
        for i in range(50)
    ]
    rows = _cadence_rows(records)
    lags = derive_empirical_additional_lag_bars(rows, "ETH_1H_trend")
    assert len(lags) == 150
    assert (lags == 0).all()


def test_empirical_lag_filters_by_sleeve() -> None:
    records = [
        {"sleeve": "ETH_1H_trend", "cycle": i, "first_sighting_of_this_bar": True, "bar_close_to_decision_hours": 0.4}
        for i in range(150)
    ]
    records += [
        {"sleeve": "BTC_4H_trend", "cycle": 2000 + i, "first_sighting_of_this_bar": True, "bar_close_to_decision_hours": 3.9}
        for i in range(150)
    ]
    rows = _cadence_rows(records)
    lags = derive_empirical_additional_lag_bars(rows, "ETH_1H_trend")
    assert len(lags) == 150
    assert (lags == 0).all()


def test_empirical_lag_requires_minimum_rows() -> None:
    rows = _cadence_rows(
        [
            {"sleeve": "ETH_1H_trend", "cycle": i, "first_sighting_of_this_bar": True, "bar_close_to_decision_hours": 0.5}
            for i in range(10)
        ]
    )
    with pytest.raises(ValueError, match="need at least"):
        derive_empirical_additional_lag_bars(rows, "ETH_1H_trend")


# ------------------------------------------------------- block_bootstrap_resample


def test_block_bootstrap_output_length_matches_target() -> None:
    real = np.array([0, 0, 0, 1, 0, 0, 2, 2, 2, 0] * 20)
    rng = np.random.default_rng(1)
    out = block_bootstrap_resample(real, target_length=1000, block_size=15, rng=rng)
    assert len(out) == 1000


def test_block_bootstrap_preserves_contiguous_runs() -> None:
    """A contiguous run of a rare event in the source must survive as a contiguous run
    somewhere in a large-enough resample -- i.i.d. per-position sampling would destroy this."""
    real = np.zeros(200, dtype=int)
    real[50:56] = 3  # a 6-hour "outage" block
    rng = np.random.default_rng(7)
    out = block_bootstrap_resample(real, target_length=5000, block_size=20, rng=rng)
    # Find the longest run of value 3 in the output.
    is_three = out == 3
    if is_three.any():
        # runs of True
        changes = np.diff(np.concatenate(([0], is_three.astype(int), [0])))
        run_starts = np.where(changes == 1)[0]
        run_ends = np.where(changes == -1)[0]
        longest = int((run_ends - run_starts).max())
        assert longest >= 2  # some contiguous chunk survived, not just isolated singletons


def test_block_bootstrap_deterministic_given_seed() -> None:
    real = np.arange(100)
    out1 = block_bootstrap_resample(real, 500, 25, np.random.default_rng(42))
    out2 = block_bootstrap_resample(real, 500, 25, np.random.default_rng(42))
    assert np.array_equal(out1, out2)


def test_block_bootstrap_rejects_empty_source() -> None:
    with pytest.raises(ValueError, match="empty"):
        block_bootstrap_resample(np.array([]), 10, 5, np.random.default_rng(0))


# ------------------------------------------------------- apply_variable_lag


def test_apply_variable_lag_zero_lag_is_identity() -> None:
    series = pd.Series([1.0, 1.15, 1.0, 1.15, 1.0], index=pd.RangeIndex(5))
    lag = np.zeros(5, dtype=int)
    out = apply_variable_lag(series, lag)
    assert list(out) == list(series)


def test_apply_variable_lag_matches_constant_shift() -> None:
    """A uniform additional_lag_bars array must reproduce pandas' own .shift(lag).fillna(1.0),
    the retired script's mechanism -- this is the generalization, not a divergent one."""
    series = pd.Series([1.0, 1.15, 1.15, 1.0, 1.0, 1.15], index=pd.RangeIndex(6))
    for constant_lag in (0, 1, 2, 3):
        lag_array = np.full(len(series), constant_lag, dtype=int)
        via_variable = apply_variable_lag(series, lag_array)
        via_shift = series.shift(constant_lag).fillna(1.0) if constant_lag else series
        assert list(via_variable) == list(via_shift), f"mismatch at constant_lag={constant_lag}"


def test_apply_variable_lag_looks_back_variable_amounts() -> None:
    series = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0], index=pd.RangeIndex(5))
    lag = np.array([0, 1, 2, 0, 1])
    out = apply_variable_lag(series, lag)
    # position 0: lag 0 -> series[0] = 10
    # position 1: lag 1 -> series[0] = 10
    # position 2: lag 2 -> series[0] = 10
    # position 3: lag 0 -> series[3] = 40
    # position 4: lag 1 -> series[3] = 40
    assert list(out) == [10.0, 10.0, 10.0, 40.0, 40.0]


def test_apply_variable_lag_rejects_short_lag_array() -> None:
    series = pd.Series([1.0, 1.0, 1.0])
    with pytest.raises(ValueError, match="too short"):
        apply_variable_lag(series, np.array([0, 0]))


# ------------------------------------------------------- evaluate_gate


def test_evaluate_gate_matches_retired_script_conditions() -> None:
    passing = {"delta_sharpe": 0.01, "delta_calmar": 0.01, "delta_max_drawdown_pct": 0.0, "delta_cagr_pct": -0.4}
    assert evaluate_gate(passing) is True

    failing_sharpe = dict(passing, delta_sharpe=-0.001)
    assert evaluate_gate(failing_sharpe) is False

    failing_cagr_floor = dict(passing, delta_cagr_pct=-0.51)
    assert evaluate_gate(failing_cagr_floor) is False

    boundary_maxdd = dict(passing, delta_max_drawdown_pct=0.0)
    assert evaluate_gate(boundary_maxdd) is True
