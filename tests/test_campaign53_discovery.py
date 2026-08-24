"""Tests for Campaign 53's real discovery-stage computation.

compute_discovery() reuses already-tested machinery from run_campaign53_power_analysis (BH FDR,
empirical p-values, block-bootstrapped null references) -- these tests focus on the NEW assembly
logic: does a real, strongly-correlated candidate actually get discovered and shortlisted, does a
null candidate not, and is the shortlist correctly bounded to FDR-discovered hypotheses only.
"""

from __future__ import annotations

import numpy as np
import pytest

from scripts.run_campaign53_discovery import compute_discovery
from scripts.run_campaign53_power_analysis import CONFIRMATION_TOP_K


def _autocorrelated_series(n: int, seed: int, scale: float = 0.1) -> np.ndarray:
    t = np.arange(n)
    return np.sin(t / 40.0) + np.random.default_rng(seed).normal(scale=scale, size=n)


def _independent_ar1_series(n: int, seed: int, phi: float = 0.9) -> np.ndarray:
    """AR(1) process built entirely from its own independent shocks -- unlike two sine waves of
    the same frequency (which share a deterministic component and are NOT independent regardless
    of seed), two of these with different seeds have no real relationship to each other while
    each still carries genuine autocorrelation."""
    rng = np.random.default_rng(seed)
    x = np.zeros(n)
    shocks = rng.normal(size=n)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + shocks[i]
    return x


def test_strongly_correlated_hypothesis_is_discovered_and_shortlisted() -> None:
    rng = np.random.default_rng(1)
    n = 3000
    candidate = _autocorrelated_series(n, seed=10)
    # Target is a noisy but real linear function of candidate -- a genuine, strong relationship.
    target = 3.0 * candidate + np.random.default_rng(11).normal(scale=0.3, size=n)

    hyp = [{"name": "strong", "candidate": candidate, "target": target}]
    result = compute_discovery(hyp, block_size=30, n_null=200, rng=rng)

    h = result["hypotheses"][0]
    assert h["fdr_discovered"] is True
    assert h["confirmation_shortlist"] is True
    assert abs(h["observed_correlation"]) > 0.5
    assert h["empirical_pvalue"] < 0.10


def test_null_hypothesis_is_not_discovered() -> None:
    rng = np.random.default_rng(2)
    n = 3000
    candidate = _independent_ar1_series(n, seed=20)
    target = _independent_ar1_series(n, seed=21)  # genuinely independent, no shared component

    hyp = [{"name": "null", "candidate": candidate, "target": target}]
    result = compute_discovery(hyp, block_size=30, n_null=200, rng=rng)

    h = result["hypotheses"][0]
    assert h["fdr_discovered"] is False
    assert h["confirmation_shortlist"] is False


def test_shortlist_only_contains_fdr_discovered_hypotheses() -> None:
    """Even if CONFIRMATION_TOP_K exceeds the number of discovered hypotheses, the shortlist
    must never include a hypothesis that failed FDR discovery."""
    rng = np.random.default_rng(3)
    n = 2500
    strong_candidate = _autocorrelated_series(n, seed=30)
    strong_target = 3.0 * strong_candidate + np.random.default_rng(31).normal(scale=0.3, size=n)

    null_candidate_a = _independent_ar1_series(n, seed=32)
    null_target_a = _independent_ar1_series(n, seed=33)

    null_candidate_b = _independent_ar1_series(n, seed=34)
    null_target_b = _independent_ar1_series(n, seed=35)

    hyps = [
        {"name": "strong", "candidate": strong_candidate, "target": strong_target},
        {"name": "null_a", "candidate": null_candidate_a, "target": null_target_a},
        {"name": "null_b", "candidate": null_candidate_b, "target": null_target_b},
    ]
    result = compute_discovery(hyps, block_size=30, n_null=200, rng=rng)

    shortlisted_names = {h["name"] for h in result["hypotheses"] if h["confirmation_shortlist"]}
    discovered_names = {h["name"] for h in result["hypotheses"] if h["fdr_discovered"]}
    assert shortlisted_names <= discovered_names
    assert "strong" in discovered_names


def test_shortlist_bounded_by_confirmation_top_k() -> None:
    rng = np.random.default_rng(4)
    n = 2500
    hyps = []
    for i in range(5):
        candidate = _autocorrelated_series(n, seed=100 + i)
        target = (5.0 - i) * candidate + np.random.default_rng(200 + i).normal(scale=0.2, size=n)
        hyps.append({"name": f"h{i}", "candidate": candidate, "target": target})

    result = compute_discovery(hyps, block_size=30, n_null=200, rng=rng)
    n_shortlisted = sum(1 for h in result["hypotheses"] if h["confirmation_shortlist"])
    assert n_shortlisted <= CONFIRMATION_TOP_K


def test_discovery_deterministic_given_seed() -> None:
    n = 2000
    candidate = _autocorrelated_series(n, seed=50)
    target = 2.0 * candidate + np.random.default_rng(51).normal(scale=0.3, size=n)
    hyp = [{"name": "h", "candidate": candidate, "target": target}]

    result_a = compute_discovery(hyp, block_size=30, n_null=100, rng=np.random.default_rng(999))
    result_b = compute_discovery(hyp, block_size=30, n_null=100, rng=np.random.default_rng(999))

    assert result_a["hypotheses"][0]["empirical_pvalue"] == pytest.approx(
        result_b["hypotheses"][0]["empirical_pvalue"]
    )
    assert result_a["hypotheses"][0]["null_reference_median_abs_r"] == pytest.approx(
        result_b["hypotheses"][0]["null_reference_median_abs_r"]
    )
