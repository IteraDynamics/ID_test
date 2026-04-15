"""Integration tests — calibrated confidence pipeline.

Verifies:
1. Full pipeline with calibration runs without crash.
2. Calibrated pipeline is deterministic (same inputs → same equity curve).
3. Unfitted calibrator produces identical results to no calibrator.
4. ExposureGovernor still blocks entries when calibrated confidence < threshold.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.fixtures.data_factory import make_df

from research.harness.backtest_engine import run_backtest
from research.strategies import trend_following, volatility_breakout, mean_reversion
from research.ml.calibration.training_data import (
    extract_calibration_samples,
    samples_to_arrays,
)
from research.ml.calibration.platt_calibrator import PlattCalibrator
from research.ml.calibration import make_calibrated_strategy, _apply_calibration
from research.strategies.contracts import Action, StrategyIntent, StrategyContext
from research.regimes.contracts import RegimeLabel


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_fitted_calibrator(strategy_id: str = "test", n: int = 80) -> PlattCalibrator:
    rng = np.random.default_rng(42)
    raw = rng.uniform(0.4, 0.9, size=n).tolist()
    probs = [0.3 + 0.6 * (v - 0.4) / 0.5 for v in raw]
    labels = [1 if rng.random() < p else 0 for p in probs]
    return PlattCalibrator.fit(raw, labels, strategy_id=strategy_id)


# ── Test 1: Full pipeline with calibration ────────────────────────────────────

class TestFullPipelineWithCalibration:
    def test_trend_following_with_fitted_calibrator(self):
        df = make_df(n=600, seed=1, trend="up")
        cal = _make_fitted_calibrator("trend_following_v1")
        result = run_backtest(
            df,
            trend_following,
            calibrators={"trend_following_v1": cal},
            asset="BTC",
        )
        assert result is not None
        assert len(result.equity_curve) == len(df)
        assert result.equity_curve.iloc[0] > 0

    def test_vol_breakout_with_calibrator(self):
        df = make_df(n=600, seed=2)
        cal = _make_fitted_calibrator("volatility_breakout_v1")
        result = run_backtest(
            df,
            volatility_breakout,
            calibrators={"volatility_breakout_v1": cal},
            asset="BTC",
        )
        assert result is not None
        assert len(result.equity_curve) == len(df)

    def test_calibrated_intents_have_ml_calibration_meta(self):
        df = make_df(n=600, seed=3, trend="up")
        cal = _make_fitted_calibrator("trend_following_v1")
        result = run_backtest(
            df,
            trend_following,
            calibrators={"trend_following_v1": cal},
            asset="BTC",
        )
        # At least some ENTER_LONG intents should have ml_calibration in meta
        entry_intents = [
            i for i in result.intent_series
            if i.action == Action.ENTER_LONG
        ]
        if entry_intents:
            calibrated_intents = [
                i for i in entry_intents
                if "ml_calibration" in i.meta
            ]
            assert len(calibrated_intents) > 0, (
                "Expected at least one ENTER_LONG intent with ml_calibration metadata"
            )

    def test_extract_then_refit_pipeline(self):
        """Train → extract → fit → calibrate in a single end-to-end flow."""
        df = make_df(n=800, seed=10, trend="up")

        # Step 1: baseline backtest to collect training data
        baseline = run_backtest(df, trend_following, asset="BTC")
        samples = extract_calibration_samples(baseline, strategy_id="trend_following_v1")

        if len(samples) < 5:
            pytest.skip("Insufficient trade cycles for this test on synthetic data")

        raw, labels = samples_to_arrays(samples)
        calibrator = PlattCalibrator.fit(
            raw.tolist(), labels.astype(int).tolist(), strategy_id="trend_following_v1"
        )

        # Step 2: calibrated backtest on same data
        calibrated = run_backtest(
            df,
            trend_following,
            calibrators={"trend_following_v1": calibrator},
            asset="BTC",
        )

        # Both should produce valid equity curves
        assert len(calibrated.equity_curve) == len(df)
        assert calibrated.equity_curve.iloc[0] > 0


# ── Test 2: Calibrated pipeline determinism ───────────────────────────────────

class TestCalibratedPipelineDeterminism:
    def test_two_runs_produce_identical_equity(self):
        df = make_df(n=500, seed=5, trend="up")
        cal = _make_fitted_calibrator("trend_following_v1")

        result1 = run_backtest(
            df, trend_following,
            calibrators={"trend_following_v1": cal},
            asset="BTC",
        )
        result2 = run_backtest(
            df, trend_following,
            calibrators={"trend_following_v1": cal},
            asset="BTC",
        )

        np.testing.assert_array_equal(
            result1.equity_curve.values,
            result2.equity_curve.values,
        )

    def test_calibrated_intents_deterministic(self):
        df = make_df(n=200, seed=6, trend="up")
        cal = _make_fitted_calibrator("trend_following_v1")
        wrapped = make_calibrated_strategy(trend_following, cal)

        ctx = StrategyContext(
            regime=RegimeLabel.TREND_UP,
            current_exposure_frac=0.0,
            asset="BTC",
            bar_index=100,
        )

        i1 = wrapped.generate_intent(df, ctx)
        i2 = wrapped.generate_intent(df, ctx)

        assert i1.action == i2.action
        assert i1.confidence == pytest.approx(i2.confidence)


# ── Test 3: Unfitted calibrator ≡ no calibrator ───────────────────────────────

class TestUnfittedEqualsNone:
    def test_unfitted_calibrator_same_as_no_calibrator(self):
        df = make_df(n=500, seed=7)
        unfitted = PlattCalibrator(strategy_id="trend_following_v1")  # not fitted
        assert not unfitted.is_fitted

        baseline = run_backtest(df, trend_following, asset="BTC")
        with_unfitted = run_backtest(
            df, trend_following,
            calibrators={"trend_following_v1": unfitted},
            asset="BTC",
        )

        np.testing.assert_array_equal(
            baseline.equity_curve.values,
            with_unfitted.equity_curve.values,
        )

    def test_none_calibrators_dict_same_as_no_calibrators(self):
        df = make_df(n=500, seed=8)
        baseline = run_backtest(df, trend_following, asset="BTC")
        with_none = run_backtest(df, trend_following, calibrators=None, asset="BTC")

        np.testing.assert_array_equal(
            baseline.equity_curve.values,
            with_none.equity_curve.values,
        )


# ── Test 4: Governor still blocks low calibrated confidence ───────────────────

class TestGovernorBlocksLowCalibratedConfidence:
    def test_apply_calibration_low_output_below_threshold(self):
        """If calibrator maps raw 0.72 → calibrated 0.20, governor should block."""
        # Craft a calibrator that always outputs 0.20 (A very negative, B very negative)
        # This simulates a model that has learned entries rarely win on this data
        low_output_cal = PlattCalibrator(
            A=-10.0,   # steep sigmoid → output near 0 for any input
            B=-5.0,
            strategy_id="test",
            is_fitted=True,
            calibration_method="platt",
        )
        assert low_output_cal.predict(0.72) < 0.35

        intent = StrategyIntent(
            action=Action.ENTER_LONG,
            confidence=0.72,
            desired_exposure_frac=0.6,
            horizon_hours=48,
            reason="test",
            meta={},
            strategy_id="test",
        )
        calibrated = _apply_calibration(intent, low_output_cal)
        assert calibrated.confidence < 0.35

        # Simulate ExposureGovernor threshold check
        from runtime.argus.governors.exposure_governor import ExposureGovernor
        from research.regimes.contracts import RegimeLabel
        gov = ExposureGovernor()

        allowed, _, reason = gov.check_entry(
            intent=calibrated,
            current_nav=100_000.0,
            current_exposure=0.0,
            regime=RegimeLabel.TREND_UP,
            drawdown_governor_allows=True,
        )
        assert not allowed
        assert "confidence" in reason.lower()
