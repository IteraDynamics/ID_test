from __future__ import annotations

import numpy as np
import pandas as pd


def _safe_ratio(a: pd.Series, b: pd.Series) -> pd.Series:
    return a / b.replace(0, np.nan)


def _rolling_rank_pct(series: pd.Series, window: int, min_periods: int) -> pd.Series:
    return series.rolling(window, min_periods=min_periods).rank(pct=True)


def _consecutive_count(flag: pd.Series) -> pd.Series:
    clean = flag.fillna(False).astype(bool)
    groups = clean.ne(clean.shift(fill_value=False)).cumsum()
    counts = clean.groupby(groups).cumcount() + 1
    return counts.where(clean, 0).astype(float)


def _rolling_sum_when(value: pd.Series, flag: pd.Series, window: int, min_periods: int = 1) -> pd.Series:
    return value.where(flag.fillna(False), 0.0).rolling(window, min_periods=min_periods).sum()


def add_market_energy_features(
    frame: pd.DataFrame,
    *,
    close: pd.Series,
    high: pd.Series,
    low: pd.Series,
    ret: pd.Series,
    realized_vol: pd.Series,
    fast_vol: pd.Series,
    slow_vol: pd.Series,
    vol_rank: pd.Series,
    range_rank: pd.Series,
    fast_window: int,
    slow_window: int,
) -> pd.DataFrame:
    """Add market-energy features to a feature/label frame.

    These features describe pressure build-up rather than only instantaneous
    state. They are intentionally derived entirely from history available at t.
    """
    out = frame.copy()
    min_fast = max(5, fast_window // 2)
    min_slow = max(20, slow_window // 2)

    rolling_std_fast = close.rolling(fast_window, min_periods=min_fast).std()
    rolling_std_slow = close.rolling(slow_window, min_periods=min_slow).std()
    sma_fast = close.rolling(fast_window, min_periods=min_fast).mean()
    sma_slow = close.rolling(slow_window, min_periods=min_slow).mean()

    bb_width_fast = (4.0 * rolling_std_fast) / sma_fast
    bb_width_slow = (4.0 * rolling_std_slow) / sma_slow
    bb_width_rank = _rolling_rank_pct(bb_width_fast, slow_window, min_slow)
    bb_compression = 1.0 - bb_width_rank
    vol_compression = 1.0 - vol_rank

    range_fast = high.rolling(fast_window, min_periods=min_fast).max() / low.rolling(fast_window, min_periods=min_fast).min() - 1.0
    range_slow = high.rolling(slow_window, min_periods=min_slow).max() / low.rolling(slow_window, min_periods=min_slow).min() - 1.0
    range_ratio = _safe_ratio(range_fast, range_slow)

    squeeze_flag = (bb_width_rank <= 0.20) & (vol_rank <= 0.30)
    deep_squeeze_flag = (bb_width_rank <= 0.10) & (vol_rank <= 0.20)
    range_squeeze_flag = (range_rank <= 0.20) | (range_ratio <= 0.35)

    compression_depth = pd.concat([bb_compression, vol_compression], axis=1).mean(axis=1)
    compression_depth = compression_depth.clip(lower=0.0, upper=1.0)
    compression_area_fast = _rolling_sum_when(compression_depth, squeeze_flag, fast_window)
    compression_area_slow = _rolling_sum_when(compression_depth, squeeze_flag, slow_window)
    deep_compression_area_fast = _rolling_sum_when(compression_depth, deep_squeeze_flag, fast_window)
    range_compression_area_fast = _rolling_sum_when(1.0 - range_rank, range_squeeze_flag, fast_window)

    expansion_pressure = (fast_vol / slow_vol.replace(0, np.nan) - 1.0).clip(lower=0.0)
    compression_release_pressure = compression_area_fast.shift(1) * expansion_pressure
    range_release_pressure = range_compression_area_fast.shift(1) * expansion_pressure

    ret_fast = close.pct_change(fast_window)
    ret_slow = close.pct_change(slow_window)
    directional_pressure = np.sign(ret_fast.fillna(0.0)) * compression_area_fast
    upside_pressure = directional_pressure.clip(lower=0.0)
    downside_pressure = (-directional_pressure).clip(lower=0.0)

    vol_slope_6 = realized_vol / realized_vol.shift(6) - 1.0
    vol_slope_12 = realized_vol / realized_vol.shift(12) - 1.0
    vol_slope_24 = realized_vol / realized_vol.shift(24) - 1.0
    vol_accel_6_12 = vol_slope_6 - vol_slope_12
    vol_accel_12_24 = vol_slope_12 - vol_slope_24
    vol_ignition = compression_area_fast.shift(1) * vol_accel_6_12.clip(lower=0.0)

    high_fast = high.rolling(fast_window, min_periods=min_fast).max()
    high_slow = high.rolling(slow_window, min_periods=min_slow).max()
    low_fast = low.rolling(fast_window, min_periods=min_fast).min()
    low_slow = low.rolling(slow_window, min_periods=min_slow).min()
    range_position_fast = (close - low_fast) / (high_fast - low_fast).replace(0, np.nan)
    range_position_slow = (close - low_slow) / (high_slow - low_slow).replace(0, np.nan)

    breakout_tension_fast = compression_area_fast * range_position_fast.clip(0.0, 1.0)
    breakdown_tension_fast = compression_area_fast * (1.0 - range_position_fast.clip(0.0, 1.0))
    breakout_tension_slow = compression_area_slow * range_position_slow.clip(0.0, 1.0)
    breakdown_tension_slow = compression_area_slow * (1.0 - range_position_slow.clip(0.0, 1.0))

    ret_abs_rank = _rolling_rank_pct(ret.abs(), slow_window, min_slow)
    quiet_absorption = compression_depth * (1.0 - ret_abs_rank)
    quiet_absorption_area = quiet_absorption.rolling(fast_window, min_periods=1).sum()

    out["bb_width_fast"] = bb_width_fast
    out["bb_width_slow"] = bb_width_slow
    out["bb_width_ratio"] = _safe_ratio(bb_width_fast, bb_width_slow)
    out["bb_width_rank"] = bb_width_rank
    out["bb_compression_score"] = bb_compression
    out["range_ratio_fast_slow"] = range_ratio
    out["squeeze_flag"] = squeeze_flag.astype(float)
    out["squeeze_duration"] = _consecutive_count(squeeze_flag)
    out["deep_squeeze_flag"] = deep_squeeze_flag.astype(float)
    out["deep_squeeze_duration"] = _consecutive_count(deep_squeeze_flag)
    out["range_squeeze_flag"] = range_squeeze_flag.astype(float)
    out["range_squeeze_duration"] = _consecutive_count(range_squeeze_flag)

    out["vol_compression_score"] = vol_compression
    out["compression_depth"] = compression_depth
    out["compression_area_fast"] = compression_area_fast
    out["compression_area_slow"] = compression_area_slow
    out["deep_compression_area_fast"] = deep_compression_area_fast
    out["range_compression_area_fast"] = range_compression_area_fast
    out["expansion_pressure"] = expansion_pressure
    out["compression_release_pressure"] = compression_release_pressure
    out["range_release_pressure"] = range_release_pressure
    out["directional_pressure"] = directional_pressure
    out["upside_pressure"] = upside_pressure
    out["downside_pressure"] = downside_pressure
    out["vol_slope_6"] = vol_slope_6
    out["vol_slope_12"] = vol_slope_12
    out["vol_slope_24"] = vol_slope_24
    out["vol_accel_6_12"] = vol_accel_6_12
    out["vol_accel_12_24"] = vol_accel_12_24
    out["vol_ignition"] = vol_ignition
    out["breakout_tension_fast"] = breakout_tension_fast
    out["breakdown_tension_fast"] = breakdown_tension_fast
    out["breakout_tension_slow"] = breakout_tension_slow
    out["breakdown_tension_slow"] = breakdown_tension_slow
    out["quiet_absorption"] = quiet_absorption
    out["quiet_absorption_area"] = quiet_absorption_area

    return out
