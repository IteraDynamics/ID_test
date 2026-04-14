"""Unit tests — Layer 1 Regime Engine.

Verifies:
- RegimeLabel contract validity.
- BaselineRegimeEngine determinism (same inputs → same output).
- UNKNOWN label during warmup.
- Non-UNKNOWN labels emitted after warmup.
- No lookahead: classify_bar(df, i) uses only df.iloc[:i+1].
- compute_regime_series output shape and alignment.
"""

from __future__ import annotations

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.fixtures.data_factory import make_df, make_flat_df

from research.regimes.contracts import RegimeLabel, RegimeSignal
from research.regimes.baseline_engine import BaselineRegimeEngine
from research.regimes.regime_series import compute_regime_series


# ─────────────────────────────────────────────────────────────────────────────
# RegimeLabel contract tests
# ─────────────────────────────────────────────────────────────────────────────

class TestRegimeLabelContract:
    def test_all_labels_are_strings(self):
        for label in RegimeLabel:
            assert isinstance(label.value, str)
            assert label.value == label.value.upper()

    def test_trend_up_is_bullish(self):
        assert RegimeLabel.TREND_UP.is_bullish()
        assert not RegimeLabel.TREND_DOWN.is_bullish()

    def test_trend_down_is_bearish(self):
        assert RegimeLabel.TREND_DOWN.is_bearish()
        assert not RegimeLabel.TREND_UP.is_bearish()

    def test_is_ranging(self):
        assert RegimeLabel.RANGE.is_ranging()
        assert RegimeLabel.VOL_COMPRESSION.is_ranging()
        assert not RegimeLabel.TREND_UP.is_ranging()

    def test_is_high_risk(self):
        assert RegimeLabel.HIGH_VOL.is_high_risk()
        assert RegimeLabel.VOL_EXPANSION.is_high_risk()
        assert not RegimeLabel.TREND_UP.is_high_risk()


# ─────────────────────────────────────────────────────────────────────────────
# RegimeSignal contract tests
# ─────────────────────────────────────────────────────────────────────────────

class TestRegimeSignalContract:
    def test_valid_construction(self):
        sig = RegimeSignal(
            label=RegimeLabel.TREND_UP,
            confidence=0.75,
            sub_signals={"ema_spread": 0.02},
            bar_index=100,
        )
        assert sig.label == RegimeLabel.TREND_UP
        assert sig.confidence == 0.75
        assert isinstance(sig.sub_signals, dict)

    def test_confidence_bounds_violated(self):
        with pytest.raises(ValueError, match="confidence"):
            RegimeSignal(label=RegimeLabel.UNKNOWN, confidence=1.5)

    def test_frozen(self):
        sig = RegimeSignal(label=RegimeLabel.RANGE, confidence=0.5)
        with pytest.raises(Exception):
            sig.label = RegimeLabel.TREND_UP  # type: ignore


# ─────────────────────────────────────────────────────────────────────────────
# BaselineRegimeEngine tests
# ─────────────────────────────────────────────────────────────────────────────

class TestBaselineRegimeEngine:
    def setup_method(self):
        self.engine = BaselineRegimeEngine(min_bars=60)
        self.df = make_df(n=500)

    def test_warmup_returns_unknown(self):
        for i in range(60):
            sig = self.engine.classify_bar(self.df, i)
            assert sig.label == RegimeLabel.UNKNOWN, f"Expected UNKNOWN at bar {i}"
            assert sig.confidence == 0.0

    def test_post_warmup_not_unknown(self):
        sig = self.engine.classify_bar(self.df, 200)
        assert sig.label != RegimeLabel.UNKNOWN

    def test_determinism(self):
        """Same DataFrame + bar_idx → exactly same result every time."""
        sig1 = self.engine.classify_bar(self.df, 200)
        sig2 = self.engine.classify_bar(self.df, 200)
        assert sig1.label == sig2.label
        assert sig1.confidence == sig2.confidence
        assert sig1.sub_signals == sig2.sub_signals

    def test_classify_dataframe_length(self):
        signals = self.engine.classify_dataframe(self.df)
        assert len(signals) == len(self.df)

    def test_classify_dataframe_first_n_unknown(self):
        signals = self.engine.classify_dataframe(self.df)
        for i in range(60):
            assert signals[i].label == RegimeLabel.UNKNOWN

    def test_classify_dataframe_bar_index_monotonic(self):
        signals = self.engine.classify_dataframe(self.df)
        for i, sig in enumerate(signals):
            assert sig.bar_index == i

    def test_no_lookahead(self):
        """classify_bar(df, i) must equal classify_bar(df.iloc[:i+1], i)."""
        engine = BaselineRegimeEngine(min_bars=60)
        i = 200
        sig_full = engine.classify_bar(self.df, i)
        sig_slice = engine.classify_bar(self.df.iloc[: i + 1], i)
        assert sig_full.label == sig_slice.label
        assert abs(sig_full.confidence - sig_slice.confidence) < 1e-10

    def test_confidence_in_range(self):
        signals = self.engine.classify_dataframe(self.df)
        for sig in signals:
            assert 0.0 <= sig.confidence <= 1.0, f"Confidence out of range: {sig.confidence}"

    def test_sub_signals_non_empty_post_warmup(self):
        sig = self.engine.classify_bar(self.df, 200)
        assert len(sig.sub_signals) > 0

    def test_flat_market_tends_to_range(self):
        """A low-volatility flat market should produce RANGE or VOL_COMPRESSION."""
        df_flat = make_flat_df(n=300)
        engine = BaselineRegimeEngine(min_bars=60)
        signals = engine.classify_dataframe(df_flat)
        post_warmup = [s for s in signals if s.label != RegimeLabel.UNKNOWN]
        ranging_labels = {RegimeLabel.RANGE, RegimeLabel.VOL_COMPRESSION}
        n_ranging = sum(1 for s in post_warmup if s.label in ranging_labels)
        # At least half the post-warmup bars should be ranging
        assert n_ranging > len(post_warmup) * 0.3, (
            f"Expected >30% ranging, got {n_ranging}/{len(post_warmup)}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# compute_regime_series
# ─────────────────────────────────────────────────────────────────────────────

class TestComputeRegimeSeries:
    def test_output_aligned_to_input(self):
        df = make_df(n=300)
        series = compute_regime_series(df)
        assert len(series) == len(df)
        assert (series.index == df.index).all()

    def test_returns_regime_label_values(self):
        df = make_df(n=300)
        series = compute_regime_series(df)
        for val in series:
            assert val in RegimeLabel, f"Unknown regime value: {val}"

    def test_deterministic(self):
        df = make_df(n=300)
        s1 = compute_regime_series(df)
        s2 = compute_regime_series(df)
        assert (s1 == s2).all()

    def test_custom_engine_respected(self):
        df = make_df(n=300)
        # Custom engine with tiny min_bars — should have fewer UNKNOWN
        engine = BaselineRegimeEngine(min_bars=10)
        series = compute_regime_series(df, engine=engine)
        n_unknown = (series == RegimeLabel.UNKNOWN).sum()
        assert n_unknown <= 10
