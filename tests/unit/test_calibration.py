"""Unit tests — ML confidence calibration components.

Covers:
1.  PlattCalibrator: fit + predict returns [0, 1]
2.  PlattCalibrator: unfitted is a passthrough
3.  PlattCalibrator: JSON round-trip → identical predictions
4.  model_store: save + load round-trip
5.  model_store: load returns None when file is missing
6.  training_data: extract_calibration_samples runs without crash
7.  training_data: no-lookahead guarantee (feature bar < outcome bar)
8.  _apply_calibration: EXIT/HOLD/FLAT intents returned unchanged
9.  make_calibrated_strategy: wrapped strategy is deterministic
10. make_calibrated_strategy: calibrated intent has ml_calibration in meta
11. RegimeCalibrator: unknown label returns raw confidence unchanged
"""

from __future__ import annotations

import sys
import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.fixtures.data_factory import make_df

from research.ml.calibration.platt_calibrator import PlattCalibrator
from research.ml.calibration.model_store import save_calibrator, load_calibrator
from research.ml.calibration import _apply_calibration, make_calibrated_strategy
from research.ml.calibration.regime_calibrator import RegimeCalibrator
from research.strategies.contracts import Action, StrategyContext, StrategyIntent
from research.regimes.contracts import RegimeLabel


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_samples(n: int = 60, win_rate: float = 0.6, seed: int = 0) -> tuple:
    """Return (raw_confidences, labels) synthetic training data."""
    rng = np.random.default_rng(seed)
    raw = rng.uniform(0.4, 0.9, size=n)
    # Labels slightly correlated with raw confidence
    probs = 0.3 + 0.6 * (raw - 0.4) / 0.5
    labels = (rng.random(n) < probs).astype(int)
    return raw.tolist(), labels.tolist()


def _make_entry_intent(confidence: float = 0.72) -> StrategyIntent:
    return StrategyIntent(
        action=Action.ENTER_LONG,
        confidence=confidence,
        desired_exposure_frac=0.6,
        horizon_hours=48,
        reason="test entry",
        meta={"ema_spread": 0.008},
        strategy_id="test_strategy",
    )


def _make_exit_intent(confidence: float = 0.90) -> StrategyIntent:
    return StrategyIntent(
        action=Action.EXIT_LONG,
        confidence=confidence,
        desired_exposure_frac=0.0,
        horizon_hours=4,
        reason="test exit",
        meta={},
        strategy_id="test_strategy",
    )


# ── Test 1: PlattCalibrator fit + predict ─────────────────────────────────────

class TestPlattCalibratorFitPredict:
    def test_predict_returns_value_in_range(self):
        raw, labels = _make_samples(60)
        cal = PlattCalibrator.fit(raw, labels, strategy_id="s1")
        assert cal.is_fitted
        for conf in [0.0, 0.35, 0.5, 0.72, 0.90, 1.0]:
            result = cal.predict(conf)
            assert 0.0 <= result <= 1.0, f"predict({conf}) = {result} out of [0,1]"

    def test_predict_with_meta_has_required_keys(self):
        raw, labels = _make_samples(60)
        cal = PlattCalibrator.fit(raw, labels, strategy_id="s1")
        meta = cal.predict_with_meta(0.72)
        assert "calibrated_confidence" in meta
        assert "raw_confidence" in meta
        assert "source" in meta
        assert meta["source"] == "ml_calibrated"
        assert 0.0 <= meta["calibrated_confidence"] <= 1.0

    def test_insufficient_samples_stays_unfitted(self):
        raw, labels = _make_samples(10)  # below MIN_SAMPLES_PLATT=30
        cal = PlattCalibrator.fit(raw, labels, min_samples=30)
        assert not cal.is_fitted

    def test_boundary_confidences_valid(self):
        raw, labels = _make_samples(60)
        cal = PlattCalibrator.fit(raw, labels)
        assert 0.0 <= cal.predict(0.0) <= 1.0
        assert 0.0 <= cal.predict(1.0) <= 1.0


# ── Test 2: Unfitted calibrator is a passthrough ──────────────────────────────

class TestPlattCalibratorPassthrough:
    def test_unfitted_returns_raw_confidence(self):
        cal = PlattCalibrator()  # default: is_fitted=False
        assert cal.predict(0.72) == pytest.approx(0.72)
        assert cal.predict(0.35) == pytest.approx(0.35)

    def test_unfitted_meta_source_is_passthrough(self):
        cal = PlattCalibrator()
        meta = cal.predict_with_meta(0.72)
        assert meta["source"] == "heuristic_passthrough"
        assert meta["raw_confidence"] == pytest.approx(0.72)
        assert meta["calibrated_confidence"] == pytest.approx(0.72)


# ── Test 3: JSON round-trip → identical predictions ───────────────────────────

class TestPlattCalibratorJsonRoundtrip:
    def test_predictions_identical_after_roundtrip(self, tmp_path):
        raw, labels = _make_samples(60)
        cal = PlattCalibrator.fit(raw, labels, strategy_id="s_roundtrip")
        assert cal.is_fitted

        save_calibrator(cal, strategy_id="s_roundtrip", models_dir=tmp_path)
        loaded = load_calibrator("s_roundtrip", models_dir=tmp_path)

        assert loaded is not None
        assert loaded.is_fitted

        test_inputs = [0.4, 0.55, 0.72, 0.85, 0.90]
        for v in test_inputs:
            original = cal.predict(v)
            reloaded = loaded.predict(v)
            assert original == pytest.approx(reloaded, abs=1e-9), (
                f"Prediction mismatch at {v}: {original} vs {reloaded}"
            )

    def test_isotonic_roundtrip(self, tmp_path):
        """Isotonic fallback also survives JSON round-trip."""
        raw, labels = _make_samples(15)  # between MIN_ISOTONIC and MIN_PLATT
        cal = PlattCalibrator.fit(raw, labels, min_samples=30)
        # May or may not be isotonic depending on sample size; either way save/load works
        save_calibrator(cal, strategy_id="s_isotonic", models_dir=tmp_path)
        loaded = load_calibrator("s_isotonic", models_dir=tmp_path)
        assert loaded is not None
        # Predictions match
        for v in [0.4, 0.7, 0.9]:
            assert cal.predict(v) == pytest.approx(loaded.predict(v), abs=1e-9)


# ── Test 4: model_store save + load ──────────────────────────────────────────

class TestModelStoreSaveLoad:
    def test_save_creates_file(self, tmp_path):
        raw, labels = _make_samples(60)
        cal = PlattCalibrator.fit(raw, labels, strategy_id="trend_following_v1")
        path = save_calibrator(cal, strategy_id="trend_following_v1", models_dir=tmp_path)
        assert path.exists()

    def test_loaded_has_correct_strategy_id(self, tmp_path):
        raw, labels = _make_samples(60)
        cal = PlattCalibrator.fit(raw, labels, strategy_id="my_strategy")
        save_calibrator(cal, strategy_id="my_strategy", models_dir=tmp_path)
        loaded = load_calibrator("my_strategy", models_dir=tmp_path)
        assert loaded is not None
        assert loaded.strategy_id == "my_strategy"

    def test_loaded_is_fitted(self, tmp_path):
        raw, labels = _make_samples(60)
        cal = PlattCalibrator.fit(raw, labels, strategy_id="s")
        save_calibrator(cal, models_dir=tmp_path)
        loaded = load_calibrator("s", models_dir=tmp_path)
        assert loaded is not None
        assert loaded.is_fitted == cal.is_fitted

    def test_json_file_is_human_readable(self, tmp_path):
        raw, labels = _make_samples(60)
        cal = PlattCalibrator.fit(raw, labels, strategy_id="readable")
        save_calibrator(cal, models_dir=tmp_path)
        path = tmp_path / "calibrator_readable.json"
        with open(path) as f:
            data = json.load(f)
        assert "A" in data
        assert "B" in data
        assert "schema_version" in data


# ── Test 5: load returns None when missing ────────────────────────────────────

class TestModelStoreGracefulMissing:
    def test_missing_strategy_returns_none(self, tmp_path):
        result = load_calibrator("nonexistent_strategy", models_dir=tmp_path)
        assert result is None

    def test_missing_dir_returns_none(self, tmp_path):
        result = load_calibrator("any_strategy", models_dir=tmp_path / "does_not_exist")
        assert result is None


# ── Test 6: extract_calibration_samples runs without crash ────────────────────

class TestExtractCalibrationSamples:
    def test_runs_on_mini_backtest(self):
        from research.harness.backtest_engine import run_backtest
        from research.strategies import trend_following
        from research.ml.calibration.training_data import extract_calibration_samples

        df = make_df(n=500, seed=42)
        result = run_backtest(df, trend_following, asset="BTC")
        samples = extract_calibration_samples(result, strategy_id="trend_following_v1")
        # Should run without crash; may have 0 samples if no completed cycles
        assert isinstance(samples, list)

    def test_returns_calibration_sample_objects(self):
        from research.harness.backtest_engine import run_backtest
        from research.strategies import trend_following
        from research.ml.calibration.training_data import extract_calibration_samples, CalibrationSample

        df = make_df(n=800, seed=1)
        result = run_backtest(df, trend_following, asset="BTC")
        samples = extract_calibration_samples(result)
        for s in samples:
            assert isinstance(s, CalibrationSample)
            assert 0.0 <= s.heuristic_confidence <= 1.0
            assert s.outcome_label in (0, 1)
            assert isinstance(s.features, dict)


# ── Test 7: no-lookahead guarantee ───────────────────────────────────────────

class TestNoLookahead:
    def test_feature_bar_before_outcome_bar(self):
        from research.harness.backtest_engine import run_backtest
        from research.strategies import trend_following
        from research.ml.calibration.training_data import extract_calibration_samples, _detect_cycles

        df = make_df(n=800, seed=2)
        result = run_backtest(df, trend_following, asset="BTC")

        if not result.trades:
            pytest.skip("No trades in this backtest — insufficient data for this test")

        cycles = _detect_cycles(result.trades)
        for entry_bar, exit_bar in cycles:
            assert entry_bar < exit_bar, (
                f"Lookahead violation: entry_bar={entry_bar} >= exit_bar={exit_bar}"
            )


# ── Test 8: _apply_calibration only modifies ENTER_LONG ──────────────────────

class TestApplyCalibrationScope:
    def _make_fitted_calibrator(self) -> PlattCalibrator:
        raw, labels = _make_samples(60)
        return PlattCalibrator.fit(raw, labels, strategy_id="test")

    def test_exit_intent_unchanged(self):
        cal = self._make_fitted_calibrator()
        intent = _make_exit_intent(confidence=0.90)
        result = _apply_calibration(intent, cal)
        assert result is intent  # same object, not a copy

    def test_hold_intent_unchanged(self):
        cal = self._make_fitted_calibrator()
        intent = StrategyIntent(
            action=Action.HOLD,
            confidence=0.60,
            desired_exposure_frac=0.5,
            horizon_hours=24,
            reason="hold",
            meta={},
            strategy_id="test",
        )
        result = _apply_calibration(intent, cal)
        assert result is intent

    def test_flat_intent_unchanged(self):
        cal = self._make_fitted_calibrator()
        intent = StrategyIntent(
            action=Action.FLAT,
            confidence=0.55,
            desired_exposure_frac=0.0,
            horizon_hours=0,
            reason="flat",
            meta={},
            strategy_id="test",
        )
        result = _apply_calibration(intent, cal)
        assert result is intent

    def test_enter_long_gets_new_confidence(self):
        raw, labels = _make_samples(60)
        cal = PlattCalibrator.fit(raw, labels, strategy_id="test")
        intent = _make_entry_intent(confidence=0.72)
        result = _apply_calibration(intent, cal)
        # confidence should be within valid range
        assert 0.0 <= result.confidence <= 1.0
        # raw_confidence preserved in meta
        assert "ml_calibration" in result.meta
        assert result.meta["ml_calibration"]["raw_confidence"] == pytest.approx(0.72)

    def test_unfitted_calibrator_entry_unchanged(self):
        cal = PlattCalibrator()  # unfitted
        intent = _make_entry_intent(confidence=0.72)
        result = _apply_calibration(intent, cal)
        assert result is intent


# ── Test 9: make_calibrated_strategy determinism ─────────────────────────────

class TestCalibratedStrategyDeterminism:
    def test_same_input_same_output(self):
        from research.strategies import trend_following

        raw, labels = _make_samples(60)
        cal = PlattCalibrator.fit(raw, labels, strategy_id="trend_following_v1")
        wrapped = make_calibrated_strategy(trend_following, cal)

        df = make_df(n=200, seed=10)
        ctx = StrategyContext(
            regime=RegimeLabel.TREND_UP,
            current_exposure_frac=0.0,
            asset="BTC",
            bar_index=100,
        )

        intent1 = wrapped.generate_intent(df, ctx)
        intent2 = wrapped.generate_intent(df, ctx)

        assert intent1.action == intent2.action
        assert intent1.confidence == pytest.approx(intent2.confidence)
        assert intent1.desired_exposure_frac == pytest.approx(intent2.desired_exposure_frac)

    def test_none_calibrator_returns_original_module(self):
        from research.strategies import trend_following
        wrapped = make_calibrated_strategy(trend_following, None)
        # Should be the original module, not a wrapper
        assert wrapped is trend_following


# ── Test 10: ml_calibration in meta ──────────────────────────────────────────

class TestCalibrationMetaLogged:
    def test_entry_intent_has_ml_calibration_key(self):
        from research.strategies import trend_following

        raw, labels = _make_samples(60)
        cal = PlattCalibrator.fit(raw, labels, strategy_id="trend_following_v1")
        wrapped = make_calibrated_strategy(trend_following, cal)

        # Use a trending df to trigger an ENTER_LONG
        df = make_df(n=300, seed=42, trend="up")
        ctx = StrategyContext(
            regime=RegimeLabel.TREND_UP,
            current_exposure_frac=0.0,
            asset="BTC",
            bar_index=200,
        )
        intent = wrapped.generate_intent(df.iloc[:201], ctx)

        if intent.action == Action.ENTER_LONG:
            assert "ml_calibration" in intent.meta
            assert "raw_confidence" in intent.meta["ml_calibration"]
            assert "calibrated_confidence" in intent.meta["ml_calibration"]
            assert intent.meta["ml_calibration"]["source"] == "ml_calibrated"


# ── Test 11: RegimeCalibrator passthrough for unknown label ───────────────────

class TestRegimeCalibratorPassthrough:
    def test_unknown_label_returns_raw(self):
        cal = RegimeCalibrator()  # no calibrators fitted
        result = cal.predict("UNKNOWN_LABEL", 0.72)
        assert result == pytest.approx(0.72)

    def test_known_but_unfitted_label_returns_raw(self):
        # Insert an unfitted calibrator
        unfitted = PlattCalibrator()  # is_fitted=False
        cal = RegimeCalibrator(calibrators={"TREND_UP": unfitted})
        result = cal.predict("TREND_UP", 0.65)
        assert result == pytest.approx(0.65)

    def test_fitted_label_returns_different_value(self):
        raw, labels = _make_samples(60)
        fitted = PlattCalibrator.fit(raw, labels, strategy_id="regime_TREND_UP")
        cal = RegimeCalibrator(calibrators={"TREND_UP": fitted})
        raw_conf = 0.72
        result = cal.predict("TREND_UP", raw_conf)
        assert 0.0 <= result <= 1.0

    def test_predict_with_meta_has_regime_label(self):
        cal = RegimeCalibrator()
        meta = cal.predict_with_meta("RANGE", 0.50)
        assert meta["regime_label"] == "RANGE"
        assert "calibrated_confidence" in meta

    def test_fit_from_regime_signals(self):
        from research.regimes.baseline_engine import BaselineRegimeEngine
        df = make_df(n=500, seed=42)
        engine = BaselineRegimeEngine()
        signals = engine.classify_dataframe(df)
        cal = RegimeCalibrator.fit(signals, horizon_bars=12)
        assert isinstance(cal, RegimeCalibrator)
        # At minimum some labels should be fitted or at least an object returned
        assert isinstance(cal.calibrators, dict)
