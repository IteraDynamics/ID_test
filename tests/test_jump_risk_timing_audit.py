"""Tests for the corrected Jump Risk timing audit.

The audit's purpose is to prove that every input used by a decision was
available before the simulated order timestamp. Its earlier implementation
derived both sides of that comparison from the action timestamp, making the
check a tautology that could not fail. These tests pin the corrected behavior,
including a regression case reproducing the exact lookahead frame that the
original audit passed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.run_jump_risk_timing_audit import (
    _audit_prediction_frame,
    lookahead_canary,
    verify_shift_provenance,
)

BAR = pd.Timedelta(hours=1)


def unshifted_frame(n: int = 50) -> pd.DataFrame:
    """Pre-shift pipeline output: row T holds the value computed from bar T."""
    index = pd.date_range("2024-01-01", periods=n, freq="h")
    return pd.DataFrame(
        {"probability": np.linspace(0.1, 0.9, n), "train_threshold": 0.5},
        index=index,
    )


def served_from(unshifted: pd.DataFrame) -> pd.DataFrame:
    """Apply the production shift: row T holds bar T-1's value."""
    out = unshifted.copy()
    out["probability"] = out["probability"].shift(1)
    out["train_threshold"] = out["train_threshold"].shift(1)
    out = out.dropna(subset=["probability", "train_threshold"])
    out.index.name = "action_bar_end"
    return out


# ------------------------------------------------------- provenance


def test_correctly_shifted_series_verifies() -> None:
    unshifted = unshifted_frame()
    served = served_from(unshifted)
    source_bars, failures = verify_shift_provenance(served, unshifted)
    assert failures == 0
    assert source_bars.notna().all()
    # Every source bar precedes its action bar by exactly one bar.
    assert ((served.index - pd.DatetimeIndex(source_bars)) == BAR).all()


def test_missing_shift_is_detected() -> None:
    """Serving the current bar's own probability is same-bar lookahead."""
    unshifted = unshifted_frame()
    unshifted_served = unshifted.copy()
    unshifted_served.index.name = "action_bar_end"
    _, failures = verify_shift_provenance(unshifted_served, unshifted)
    assert failures > 0


def test_doubled_shift_is_detected() -> None:
    unshifted = unshifted_frame()
    doubled = unshifted.copy()
    doubled["probability"] = doubled["probability"].shift(2)
    doubled = doubled.dropna(subset=["probability"])
    doubled.index.name = "action_bar_end"
    _, failures = verify_shift_provenance(doubled, unshifted)
    assert failures > 0


def test_foreign_series_is_detected() -> None:
    """Values that never came from the pipeline cannot be verified."""
    unshifted = unshifted_frame()
    foreign = served_from(unshifted)
    foreign["probability"] = 0.42
    _, failures = verify_shift_provenance(foreign, unshifted)
    assert failures > 0


# ------------------------------------------------------- F1 regression


def test_regression_five_bar_lookahead_now_fails() -> None:
    """Regression for the defect this audit correction closed.

    The original ``_audit_prediction_frame`` returned availability_failures=0,
    same_bar_source_failures=0 and status=PASS for this exact frame, whose
    probability at bar T is taken from bar T+5.
    """
    n = 50
    index = pd.date_range("2024-01-01", periods=n, freq="h")
    unshifted = unshifted_frame(n)
    leaked = pd.DataFrame(
        {"probability": np.linspace(0, 1, n + 5)[5:], "train_threshold": 0.5},
        index=index,
    )
    leaked.index.name = "action_bar_end"

    _, checks = _audit_prediction_frame(leaked, "BTC", "medium_up", BAR, unshifted)

    assert checks["shift_provenance_failures"] > 0
    assert checks["availability_failures"] > 0
    assert checks["same_bar_source_failures"] > 0
    assert checks["status"] == "FAIL"


def test_valid_frame_passes_the_audit() -> None:
    unshifted = unshifted_frame()
    served = served_from(unshifted)
    _, checks = _audit_prediction_frame(served, "BTC", "medium_up", BAR, unshifted)
    assert checks["shift_provenance_failures"] == 0
    assert checks["availability_failures"] == 0
    assert checks["same_bar_source_failures"] == 0
    assert checks["status"] == "PASS"


# ------------------------------------------------------- canary


def test_canary_detects_injected_lookahead() -> None:
    """The audit must demonstrate, on every run, that its detector can fail."""
    result = lookahead_canary(unshifted_frame())
    assert result["detected_failures"] > 0
    assert result["status"] == "PASS"
    assert result["rows_tested"] > 0
