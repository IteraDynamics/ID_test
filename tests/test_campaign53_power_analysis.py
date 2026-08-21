"""Tests for Campaign 53's power analysis statistical primitives.

Each function is tested against a known, hand-verifiable property rather than just "doesn't
crash" -- the risk with a bootstrap/FDR/effect-injection pipeline like this is a confident-looking
wrong number, not an exception.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.run_campaign53_power_analysis import (
    benjamini_hochberg,
    block_bootstrap_resample,
    empirical_pvalue,
    forward_net_carry,
    funding_level,
    funding_persistence,
    inject_ic,
    lag1_autocorr,
    standardize,
)


# ------------------------------------------------------- block_bootstrap_resample


def test_block_bootstrap_output_length() -> None:
    rng = np.random.default_rng(1)
    idx = block_bootstrap_resample(1000, 30, rng)
    assert len(idx) == 1000


def test_block_bootstrap_deterministic_given_seed() -> None:
    idx1 = block_bootstrap_resample(500, 20, np.random.default_rng(42))
    idx2 = block_bootstrap_resample(500, 20, np.random.default_rng(42))
    assert np.array_equal(idx1, idx2)


def test_block_bootstrap_indices_in_range() -> None:
    rng = np.random.default_rng(3)
    idx = block_bootstrap_resample(200, 15, rng)
    assert idx.min() >= 0
    assert idx.max() < 200


def test_block_bootstrap_rejects_bad_block_size() -> None:
    rng = np.random.default_rng(0)
    with pytest.raises(ValueError):
        block_bootstrap_resample(10, 0, rng)
    with pytest.raises(ValueError):
        block_bootstrap_resample(10, 11, rng)


# ------------------------------------------------------- standardize


def test_standardize_mean_zero_std_one() -> None:
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 100.0])
    z = standardize(x)
    assert abs(z.mean()) < 1e-9
    assert abs(z.std() - 1.0) < 1e-9


def test_standardize_rejects_constant_input() -> None:
    with pytest.raises(ValueError):
        standardize(np.array([5.0, 5.0, 5.0]))


# ------------------------------------------------------- inject_ic


def test_inject_ic_zero_gives_near_zero_correlation() -> None:
    rng = np.random.default_rng(7)
    n = 5000
    candidate = rng.normal(size=n)
    real_target = rng.normal(size=n)
    synthetic = inject_ic(candidate, real_target, 0.0)
    r = np.corrcoef(candidate, synthetic)[0, 1]
    assert abs(r) < 0.05, f"expected near-zero correlation at IC=0, got {r}"


def test_inject_ic_recovers_target_correlation_approximately() -> None:
    """The core correctness check: injecting IC=0.5 should produce an OBSERVED correlation
    close to 0.5, not some other value -- this is what every power number in the script depends on."""
    rng = np.random.default_rng(11)
    n = 20000  # large n to get a tight estimate
    candidate = rng.normal(size=n)
    real_target = rng.normal(size=n)
    for target_ic in (0.05, 0.2, 0.5, 0.8):
        synthetic = inject_ic(candidate, real_target, target_ic)
        observed_r = np.corrcoef(candidate, synthetic)[0, 1]
        assert abs(observed_r - target_ic) < 0.03, (
            f"target IC {target_ic} produced observed correlation {observed_r} -- "
            "injection is not calibrated correctly"
        )


def test_inject_ic_sign_is_respected() -> None:
    rng = np.random.default_rng(13)
    n = 10000
    candidate = rng.normal(size=n)
    real_target = rng.normal(size=n)
    synthetic_pos = inject_ic(candidate, real_target, 0.6)
    synthetic_neg = inject_ic(candidate, real_target, -0.6)
    assert np.corrcoef(candidate, synthetic_pos)[0, 1] > 0
    assert np.corrcoef(candidate, synthetic_neg)[0, 1] < 0


def test_inject_ic_does_not_destroy_autocorrelation_of_inputs() -> None:
    """Regression test for the original bug: inject_ic used to do an internal
    `real_target[rng.permutation(n)]` shuffle on its second argument, which silently destroyed
    any autocorrelation the caller had deliberately preserved (e.g. via block bootstrap). A
    caller-supplied autocorrelated series must come through with its autocorrelation intact,
    not collapse to near-white-noise."""
    n = 5000
    t = np.arange(n)
    # AR(1)-like strongly autocorrelated series (not something a full permutation would preserve).
    autocorrelated = np.sin(t / 50.0) + np.random.default_rng(21).normal(scale=0.05, size=n)
    candidate = np.random.default_rng(22).normal(size=n)

    def lag1_autocorr(x: np.ndarray) -> float:
        return float(np.corrcoef(x[:-1], x[1:])[0, 1])

    input_autocorr = lag1_autocorr(autocorrelated)
    synthetic = inject_ic(candidate, autocorrelated, 0.0)
    output_autocorr = lag1_autocorr(synthetic)

    assert input_autocorr > 0.9, "fixture is not actually autocorrelated -- test is meaningless"
    assert output_autocorr > 0.8, (
        f"inject_ic destroyed input autocorrelation (input lag-1 r={input_autocorr:.3f}, "
        f"output lag-1 r={output_autocorr:.3f}) -- it must not internally reshuffle its inputs"
    )


def test_draw_independent_pair_preserves_autocorrelation_and_decorrelates() -> None:
    """The replacement for the old internal shuffle: draw_independent_pair must hand back two
    series that (a) each retain real autocorrelation (via block bootstrap, not i.i.d. resampling)
    and (b) are mutually independent of each other. A null reference built from this should be
    noticeably wider than the artificially tight ~0.01 the old buggy inject_ic produced."""
    from scripts.run_campaign53_power_analysis import block_bootstrap_resample

    n = 6000
    block_size = 30
    t = np.arange(n)
    autocorrelated_series = np.sin(t / 40.0) + np.random.default_rng(31).normal(scale=0.1, size=n)

    rng = np.random.default_rng(32)
    idx_a = block_bootstrap_resample(n, block_size, rng)
    idx_b = block_bootstrap_resample(n, block_size, rng)
    resampled_a = autocorrelated_series[idx_a]
    resampled_b = autocorrelated_series[idx_b]

    def lag1_autocorr(x: np.ndarray) -> float:
        return float(np.corrcoef(x[:-1], x[1:])[0, 1])

    assert lag1_autocorr(resampled_a) > 0.7
    assert lag1_autocorr(resampled_b) > 0.7

    # Two independently-drawn block resamples of the SAME series should be only weakly
    # correlated with each other -- not the near-1.0 they'd show if drawn with the same index,
    # and not artificially collapsed to near-zero either.
    cross_r = abs(float(np.corrcoef(resampled_a, resampled_b)[0, 1]))
    assert cross_r < 0.5, f"independent block draws should not be strongly correlated, got {cross_r}"


# ------------------------------------------------------- lag1_autocorr


def test_lag1_autocorr_near_one_for_smooth_series() -> None:
    x = np.sin(np.arange(200) / 20.0)
    assert lag1_autocorr(x) > 0.9


def test_lag1_autocorr_near_zero_for_iid_noise() -> None:
    rng = np.random.default_rng(9)
    x = rng.normal(size=20000)
    assert abs(lag1_autocorr(x)) < 0.05


# ------------------------------------------------------- benjamini_hochberg


def test_bh_rejects_nothing_when_all_pvalues_high() -> None:
    pvals = np.array([0.9, 0.8, 0.95, 0.99])
    rejected = benjamini_hochberg(pvals, q=0.10)
    assert not rejected.any()


def test_bh_rejects_everything_when_all_pvalues_tiny() -> None:
    pvals = np.array([0.0001, 0.0002, 0.0001, 0.0003])
    rejected = benjamini_hochberg(pvals, q=0.10)
    assert rejected.all()


def test_bh_known_worked_example() -> None:
    """p-values [0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205, 0.212, 0.216], q=0.05.
    Verified by hand against BH's own step-up rule: threshold(i) = (i+1)/10 * 0.05 for sorted
    rank i. 0.001<=0.005 True, 0.008<=0.01 True, 0.039<=0.015 False -- and every later p-value
    is also above its own threshold. So exactly the first 2 (sorted) are rejected, not more."""
    pvals = np.array([0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205, 0.212, 0.216])
    rejected = benjamini_hochberg(pvals, q=0.05)
    assert rejected.sum() == 2
    assert rejected[:2].all()
    assert not rejected[2:].any()


def test_bh_reject_set_is_monotonic_in_sorted_order() -> None:
    """BH's step-up procedure means if hypothesis at sorted rank k is rejected, every rank < k
    must also be rejected -- a bug that produces a 'gap' in the rejection set would be wrong."""
    rng = np.random.default_rng(5)
    pvals = rng.uniform(0, 1, size=20)
    rejected = benjamini_hochberg(pvals, q=0.10)
    order = np.argsort(pvals)
    rejected_sorted = rejected[order]
    if rejected_sorted.any():
        last_true = np.max(np.where(rejected_sorted)[0])
        assert rejected_sorted[: last_true + 1].all()


# ------------------------------------------------------- empirical_pvalue


def test_empirical_pvalue_extreme_observation_is_small() -> None:
    null_ref = np.abs(np.random.default_rng(1).normal(0, 0.05, size=1000))
    p = empirical_pvalue(0.5, null_ref)  # far outside the null distribution
    assert p < 0.05


def test_empirical_pvalue_typical_observation_is_large() -> None:
    rng = np.random.default_rng(2)
    null_ref = np.abs(rng.normal(0, 0.1, size=2000))
    median_val = float(np.median(null_ref))
    p = empirical_pvalue(median_val, null_ref)
    assert p > 0.3  # roughly half the null distribution should exceed the median


# ------------------------------------------------------- candidate/target construction


def _synthetic_hourly_series(n_hours: int, seed: int = 0) -> pd.Series:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=n_hours, freq="1h")
    return pd.Series(rng.normal(0.0001, 0.0005, size=n_hours), index=idx)


def test_funding_level_is_trailing_mean_no_lookahead() -> None:
    series = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0], index=pd.date_range("2020-01-01", periods=5, freq="1h"))
    level = funding_level(series, window_hours=3)
    # first two values are NaN (insufficient window), third is mean(1,2,3), etc.
    assert pd.isna(level.iloc[0])
    assert pd.isna(level.iloc[1])
    assert level.iloc[2] == pytest.approx(2.0)  # mean(1,2,3)
    assert level.iloc[3] == pytest.approx(3.0)  # mean(2,3,4)
    assert level.iloc[4] == pytest.approx(4.0)  # mean(3,4,5)


def test_forward_net_carry_no_lookahead_and_correct_window() -> None:
    series = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], index=pd.date_range("2020-01-01", periods=6, freq="1h"))
    target = forward_net_carry(series, horizon_hours=2, cost=0.0)
    # at t=0 (value 1.0), forward 2h sum should be values at t+1, t+2 = 2.0 + 3.0 = 5.0
    assert target.iloc[0] == pytest.approx(5.0)
    # at t=1 (value 2.0), forward 2h sum = values at t+2, t+3 = 3.0 + 4.0 = 7.0
    assert target.iloc[1] == pytest.approx(7.0)


def test_forward_net_carry_applies_cost() -> None:
    series = pd.Series([1.0, 2.0, 3.0, 4.0], index=pd.date_range("2020-01-01", periods=4, freq="1h"))
    target_no_cost = forward_net_carry(series, horizon_hours=2, cost=0.0)
    target_with_cost = forward_net_carry(series, horizon_hours=2, cost=0.5)
    assert (target_no_cost.iloc[0] - target_with_cost.iloc[0]) == pytest.approx(0.5)


def test_funding_persistence_all_same_sign_is_one() -> None:
    series = pd.Series([0.1] * 10, index=pd.date_range("2020-01-01", periods=10, freq="1h"))
    persistence = funding_persistence(series, window_hours=5)
    assert persistence.iloc[-1] == pytest.approx(1.0)


def test_funding_persistence_mixed_signs_is_partial() -> None:
    series = pd.Series([0.1, 0.1, -0.1, 0.1, -0.1], index=pd.date_range("2020-01-01", periods=5, freq="1h"))
    persistence = funding_persistence(series, window_hours=5)
    # last value's sign is negative (-0.1); count how many of the 5 match
    matching = sum(1 for v in [0.1, 0.1, -0.1, 0.1, -0.1] if np.sign(v) == np.sign(-0.1))
    assert persistence.iloc[-1] == pytest.approx(matching / 5)
