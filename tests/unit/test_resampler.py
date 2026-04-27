"""Unit tests — OHLCV resampler and equity curve alignment."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research.harness.resampler import resample_ohlcv, align_equity_curves


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_1h_ohlcv(n: int = 100, seed: int = 42, price: float = 50_000.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2022-01-01", periods=n, freq="1h")
    closes = price + np.cumsum(rng.normal(0, 200, size=n))
    return pd.DataFrame(
        {
            "open":   closes + rng.normal(0, 50, size=n),
            "high":   closes + rng.uniform(100, 400, size=n),
            "low":    closes - rng.uniform(100, 400, size=n),
            "close":  closes,
            "volume": rng.uniform(10, 100, size=n),
        },
        index=dates,
    )


# ── resample_ohlcv ────────────────────────────────────────────────────────────

class TestResampleOHLCV:
    def setup_method(self):
        self.df = _make_1h_ohlcv(n=240)  # 10 days of 1H data

    def test_output_has_fewer_bars(self):
        df4h = resample_ohlcv(self.df, "4h")
        assert len(df4h) < len(self.df)
        assert len(df4h) == len(self.df) // 4

    def test_output_columns_preserved(self):
        df4h = resample_ohlcv(self.df, "4h")
        assert set(df4h.columns) == set(self.df.columns)

    def test_high_is_max_of_constituent_bars(self):
        df4h = resample_ohlcv(self.df, "4h")
        # First 4H bar should have high = max of first 4 1H highs
        expected_high = self.df["high"].iloc[:4].max()
        assert abs(df4h["high"].iloc[0] - expected_high) < 1e-6

    def test_low_is_min_of_constituent_bars(self):
        df4h = resample_ohlcv(self.df, "4h")
        expected_low = self.df["low"].iloc[:4].min()
        assert abs(df4h["low"].iloc[0] - expected_low) < 1e-6

    def test_open_is_first_constituent_bar(self):
        df4h = resample_ohlcv(self.df, "4h")
        assert abs(df4h["open"].iloc[0] - self.df["open"].iloc[0]) < 1e-6

    def test_close_is_last_constituent_bar(self):
        df4h = resample_ohlcv(self.df, "4h")
        assert abs(df4h["close"].iloc[0] - self.df["close"].iloc[3]) < 1e-6

    def test_volume_is_sum(self):
        df4h = resample_ohlcv(self.df, "4h")
        expected_vol = self.df["volume"].iloc[:4].sum()
        assert abs(df4h["volume"].iloc[0] - expected_vol) < 1e-6

    def test_no_lookahead_label_convention(self):
        """Bar label is the START of the period — a bar labeled T only uses data from [T, T+4H)."""
        df4h = resample_ohlcv(self.df, "4h")
        # First 4H bar labeled at 2022-01-01 00:00 → uses 1H bars 00:00, 01:00, 02:00, 03:00
        expected_label = pd.Timestamp("2022-01-01 00:00:00")
        assert df4h.index[0] == expected_label

    def test_missing_volume_column_handled(self):
        df_no_vol = self.df.drop(columns=["volume"])
        df4h = resample_ohlcv(df_no_vol, "4h")
        assert "volume" not in df4h.columns
        assert "close" in df4h.columns

    def test_raises_on_missing_required_column(self):
        df_bad = self.df.drop(columns=["close"])
        with pytest.raises(ValueError, match="close"):
            resample_ohlcv(df_bad, "4h")

    def test_datetime_index_preserved(self):
        df4h = resample_ohlcv(self.df, "4h")
        assert isinstance(df4h.index, pd.DatetimeIndex)

    def test_no_nans_in_output(self):
        df4h = resample_ohlcv(self.df, "4h")
        assert not df4h[["open", "high", "low", "close"]].isna().any().any()


# ── align_equity_curves ───────────────────────────────────────────────────────

class TestAlignEquityCurves:
    def setup_method(self):
        dates_1h = pd.date_range("2022-01-01", periods=120, freq="1h")
        dates_4h = pd.date_range("2022-01-01", periods=30, freq="4h")
        self.curve_1h = pd.Series(
            np.linspace(100_000, 110_000, 120), index=dates_1h, name="BTC_1H"
        )
        self.curve_4h = pd.Series(
            np.linspace(50_000, 55_000, 30), index=dates_4h, name="BTC_4H"
        )

    def test_output_is_dataframe(self):
        aligned = align_equity_curves({"BTC_1H": self.curve_1h, "BTC_4H": self.curve_4h})
        assert isinstance(aligned, pd.DataFrame)

    def test_both_columns_present(self):
        aligned = align_equity_curves({"BTC_1H": self.curve_1h, "BTC_4H": self.curve_4h})
        assert "BTC_1H" in aligned.columns
        assert "BTC_4H" in aligned.columns

    def test_output_index_is_1h(self):
        aligned = align_equity_curves({"BTC_1H": self.curve_1h, "BTC_4H": self.curve_4h})
        diffs = aligned.index.to_series().diff().dropna()
        assert (diffs == pd.Timedelta("1h")).all()

    def test_no_nans_after_alignment(self):
        aligned = align_equity_curves({"BTC_1H": self.curve_1h, "BTC_4H": self.curve_4h})
        assert not aligned.isna().any().any()

    def test_4h_values_forward_filled(self):
        """Between 4H ticks, the 4H equity should be constant (position unchanged)."""
        aligned = align_equity_curves({"BTC_1H": self.curve_1h, "BTC_4H": self.curve_4h})
        # At 00:00, 01:00, 02:00, 03:00 the 4H equity should be the same (00:00 value)
        v00 = aligned["BTC_4H"].iloc[0]
        v01 = aligned["BTC_4H"].iloc[1]
        v02 = aligned["BTC_4H"].iloc[2]
        v03 = aligned["BTC_4H"].iloc[3]
        assert v00 == v01 == v02 == v03

    def test_common_period_clipped(self):
        """Aligned DataFrame covers only the overlapping period of all input curves."""
        dates_short = pd.date_range("2022-01-02", periods=24, freq="1h")
        short_curve = pd.Series(np.ones(24) * 25_000, index=dates_short)
        aligned = align_equity_curves({"long": self.curve_1h, "short": short_curve})
        assert aligned.index[0] >= pd.Timestamp("2022-01-02")

    def test_raises_on_no_overlap(self):
        dates_future = pd.date_range("2025-01-01", periods=10, freq="1h")
        future_curve = pd.Series(np.ones(10), index=dates_future)
        with pytest.raises(ValueError, match="overlapping"):
            align_equity_curves({"past": self.curve_1h, "future": future_curve})

    def test_raises_on_empty_input(self):
        with pytest.raises(ValueError, match="no curves"):
            align_equity_curves({})
